"""프로젝트 필수 MFA 3.4 설치 패치의 존재를 읽기 전용으로 검증한다.

MFA 버전 문자열만으로는 대용량 교착·export 실패를 막는 로컬 패치를 재현할 수
없다. 이 검사는 설치 소스의 구조와 SHA256을 기록하고, 필수 패치가 사라졌으면
exit 1로 대량 실행을 차단한다.
"""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso


def package_root_from_install() -> Path:
    spec = importlib.util.find_spec("montreal_forced_aligner")
    if spec is None or spec.origin is None:
        raise RuntimeError("montreal_forced_aligner 패키지를 찾지 못함")
    return Path(spec.origin).resolve().parent


def _attribute_calls(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    ]


def inspect_mfa_source(package_root: Path) -> dict:
    files = {
        "align": package_root / "command_line" / "align.py",
        "base": package_root / "alignment" / "base.py",
        "multiprocessing": package_root / "alignment" / "multiprocessing.py",
        "textgrid": package_root / "textgrid.py",
    }
    result = {
        "checked_at": now_iso(),
        "package_root": str(package_root.resolve()),
        "checks": [],
        "files": {},
    }
    for key, path in files.items():
        if not path.exists():
            result["checks"].append({
                "name": f"{key}_exists", "ok": False, "detail": str(path),
            })
            continue
        result["files"][key] = file_fingerprint(path, with_sha256=True)

    if len(result["files"]) != len(files):
        result["ok"] = False
        return result

    align_text = files["align"].read_text(encoding="utf-8")
    align_tree = ast.parse(align_text)
    analyze_calls = _attribute_calls(align_tree, "analyze_alignments")
    result["checks"].append({
        "name": "quality_analysis_call_removed",
        "ok": len(analyze_calls) == 0,
        "detail": f"AST call count={len(analyze_calls)}",
    })
    export_calls = _attribute_calls(align_tree, "export_files")
    correct_exports = 0
    for call in export_calls:
        for keyword in call.keywords:
            if (
                keyword.arg == "output_format"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "output_format"
            ):
                correct_exports += 1
                break
    result["checks"].append({
        "name": "export_output_format_keyword_valid",
        "ok": correct_exports >= 2,
        "detail": f"valid calls={correct_exports}",
    })
    skip_flag_count = align_text.count("MFA_PROJECT_SKIP_TEXTGRID_EXPORT")
    result["checks"].append({
        "name": "project_direct_db_skip_export_flag_available",
        "ok": skip_flag_count >= 2,
        "detail": f"flag occurrences={skip_flag_count}",
    })

    mp_text = files["multiprocessing"].read_text(encoding="utf-8")
    for name, marker in (
        ("export_output_path_initialized", "output_path = None"),
        ("export_finished_finally_documented", "finally:"),
        ("export_finished_flag_set", "self.finished_processing.set()"),
    ):
        result["checks"].append({
            "name": name,
            "ok": marker in mp_text,
            "detail": f"marker={marker!r}",
        })
    result["checks"].append({
        "name": "export_worker_waits_for_sentinel",
        "ok": (
            "file_batch = self.for_write_queue.get()" in mp_text
            and "if file_batch is None:" in mp_text
            and "self.for_write_queue.get(timeout=1)" not in mp_text
        ),
        "detail": "blocking get + None sentinel; no 1s worker timeout",
    })

    base_text = files["base"].read_text(encoding="utf-8")
    result["checks"].append({
        "name": "export_producer_sends_worker_sentinels",
        "ok": (
            "for _ in export_procs:" in base_text
            and "for_write_queue.put(None)" in base_text
            and "time.sleep(1)\n                    finished_adding.set()"
            not in base_text
        ),
        "detail": "one None sentinel per export worker; no fixed 1s drain guess",
    })

    tg_text = files["textgrid"].read_text(encoding="utf-8")
    tg_tree = ast.parse(tg_text)
    functions = {
        node.name: node for node in ast.walk(tg_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    result["checks"].append({
        "name": "textgrid_chunk_impl_split",
        "ok": (
            "construct_textgrid_output" in functions
            and "_construct_textgrid_output_impl" in functions
        ),
        "detail": "wrapper+impl functions",
    })
    chunk_values = [
        node.value.value
        for node in ast.walk(functions.get("construct_textgrid_output", tg_tree))
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "_CHUNK"
                for t in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, int)
    ]
    result["checks"].append({
        "name": "textgrid_chunk_size_safe",
        "ok": bool(chunk_values) and max(chunk_values) <= 50_000,
        "detail": f"chunk_values={chunk_values}",
    })
    result["ok"] = all(item["ok"] for item in result["checks"])
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", type=Path,
                    help="테스트용 MFA 패키지 루트(기본: 현재 Python 설치본)")
    ap.add_argument("--json-output", type=Path)
    args = ap.parse_args()

    root = args.package_root or package_root_from_install()
    result = inspect_mfa_source(root)
    try:
        result["mfa_version"] = importlib.metadata.version(
            "montreal-forced-aligner"
        )
    except importlib.metadata.PackageNotFoundError:
        result["mfa_version"] = "unknown"

    for item in result["checks"]:
        label = "OK" if item["ok"] else "FAIL"
        print(f"[{label}] {item['name']}: {item['detail']}")
    print(f"MFA source patch verdict: {'PASS' if result['ok'] else 'FAIL'}")
    if args.json_output:
        atomic_write_json(args.json_output, result)
        print(f"report: {args.json_output}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
