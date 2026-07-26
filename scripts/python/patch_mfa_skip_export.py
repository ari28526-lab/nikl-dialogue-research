"""MFA align에 프로젝트용 'DB 보존, TextGrid export 생략' 플래그를 추가한다.

환경변수 ``MFA_PROJECT_SKIP_TEXTGRID_EXPORT=1``일 때만 MFA의 built-in
TextGrid export를 생략한다. 기본 동작은 그대로 유지된다. align 단계는 이미
word/phone interval을 SQLite DB에 수집하므로, 프로젝트의 검증된
``export_mfa_db_4tier.py``가 그 DB에서 연구용 4-tier를 직접 만들 수 있다.

적용 전 align.py와 SHA256 manifest를 ``--backup-root``에 보존하며, 알려진
MFA 3.4 코드 조각이 정확히 두 곳에 있을 때만 원자적으로 적용한다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from patch_mfa_export_queue import atomic_replace_text
from pipeline_common import atomic_write_json, file_fingerprint, now_iso

OLD_IMPORT = """import typing
from pathlib import Path
"""
NEW_IMPORT = """import os
import typing
from pathlib import Path
"""

OLD_EXPORT = """        aligner.export_files(
            output_directory,
            output_format=output_format,
            include_original_text=include_original_text,
        )
"""

NEW_EXPORT = """        if os.environ.get("MFA_PROJECT_SKIP_TEXTGRID_EXPORT") == "1":
            print(
                " INFO     Project direct-DB mode: built-in TextGrid export skipped; "
                "alignment DB retained"
            )
        else:
            aligner.export_files(
                output_directory,
                output_format=output_format,
                include_original_text=include_original_text,
            )
"""


def package_root_from_install() -> Path:
    spec = importlib.util.find_spec("montreal_forced_aligner")
    if spec is None or spec.origin is None:
        raise RuntimeError("montreal_forced_aligner 패키지를 찾지 못함")
    return Path(spec.origin).resolve().parent


def inspect_text(text: str) -> str:
    if text.count(NEW_EXPORT) == 2 and NEW_IMPORT in text:
        if OLD_EXPORT in text:
            raise RuntimeError("구/신 export 코드가 동시에 존재")
        return "already_patched"
    if text.count(OLD_EXPORT) != 2:
        raise RuntimeError(
            f"예상 export 호출 조각 {text.count(OLD_EXPORT)}개(정확히 2개 필요)"
        )
    if OLD_IMPORT not in text:
        raise RuntimeError("예상 import 조각을 찾지 못함")
    return "needs_patch"


def patch_text(text: str) -> str:
    state = inspect_text(text)
    if state == "already_patched":
        return text
    return text.replace(OLD_IMPORT, NEW_IMPORT, 1).replace(
        OLD_EXPORT, NEW_EXPORT
    )


def inspect_and_patch(
    package_root: Path,
    *,
    apply: bool,
    backup_root: Path | None,
) -> dict:
    path = package_root / "command_line" / "align.py"
    text = path.read_text(encoding="utf-8")
    state = inspect_text(text)
    result = {
        "schema_version": 1,
        "checked_at": now_iso(),
        "package_root": str(package_root.resolve()),
        "apply_requested": apply,
        "state_before": state,
        "file_before": file_fingerprint(path, with_sha256=True),
    }
    if not apply:
        result["status"] = state
        return result
    if state == "needs_patch":
        if backup_root is None:
            raise RuntimeError("--apply에는 --backup-root가 필요")
        backup_root.mkdir(parents=True, exist_ok=False)
        destination = backup_root / "command_line" / "align.py"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(path.read_bytes())
        atomic_write_json(backup_root / "manifest_before.json", result)
        atomic_replace_text(path, patch_text(text))
    verified = inspect_text(path.read_text(encoding="utf-8"))
    if verified != "already_patched":
        raise RuntimeError(f"적용 뒤 검증 실패: {verified}")
    result["status"] = "patched" if state == "needs_patch" else state
    result["file_after"] = file_fingerprint(path, with_sha256=True)
    if backup_root is not None and backup_root.exists():
        atomic_write_json(backup_root / "manifest_after.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_and_patch(
            args.package_root or package_root_from_install(),
            apply=args.apply,
            backup_root=args.backup_root,
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_output:
        atomic_write_json(args.json_output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
