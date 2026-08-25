"""Fail-closed small-sample KOINA runner for stage-2 PV-B.

Preflight is the default. Execution requires Linux, an explicit full KOINA Git
commit, and a new output namespace. KOINA output remains a machine candidate.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from pv_b_aux_common import (
    input_summary,
    load_input_manifest,
    now_iso,
    promote_partial,
    public_input_records,
    require_new_output_root,
    sha256_file,
    write_json_new,
)


FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().lower()


def git_tag_commit(repo: Path, tag: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"refs/tags/{tag}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().lower()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=70)
    parser.add_argument("--max-per-phenomenon", type=int, default=10)
    parser.add_argument("--koina-root", type=Path)
    parser.add_argument("--expected-koina-commit")
    parser.add_argument("--expected-koina-tag", default="v1.1.0")
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    return parser


def preflight(args: argparse.Namespace) -> tuple[list[dict], dict]:
    if args.n_jobs != 1:
        raise RuntimeError("PV-B scaffold permits n_jobs=1 only")
    rows = load_input_manifest(
        args.input_manifest.resolve(),
        limit=args.limit,
        max_per_phenomenon=args.max_per_phenomenon,
    )
    partial = require_new_output_root(args.output_dir)
    report = {
        "schema_version": "stage2_pv_b_koina_preflight.v1",
        "status": "preflight_passed",
        "execution_requested": bool(args.execute),
        "platform": sys.platform,
        "input": input_summary(rows),
        "output_target_exists": args.output_dir.resolve().exists(),
        "partial_target_exists": partial.exists(),
        "constraints": {
            "machine_candidate_only": True,
            "canonical_textgrid_write": False,
            "canonical_mfa_write": False,
            "source_wav_write": False,
            "silent_parselmouth_fallback": False,
        },
    }
    return rows, report


def execute(args: argparse.Namespace, rows: list[dict], report: dict) -> None:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("KOINA execution requires Linux; preflight is portable")
    if args.koina_root is None or args.expected_koina_commit is None:
        raise RuntimeError("execution requires koina-root and expected-koina-commit")
    expected = args.expected_koina_commit.lower()
    if not FULL_COMMIT.fullmatch(expected):
        raise RuntimeError("expected-koina-commit must be a full 40-hex commit")
    koina_root = args.koina_root.resolve()
    transcriber = koina_root / "src" / "transcribe" / "transcriber.py"
    if not transcriber.is_file():
        raise RuntimeError("KOINA transcriber.py not found")
    actual = git_head(koina_root)
    if actual != expected:
        raise RuntimeError(f"KOINA commit mismatch: expected {expected}, got {actual}")
    tag_commit = git_tag_commit(koina_root, args.expected_koina_tag)
    if tag_commit != expected:
        raise RuntimeError(
            f"KOINA tag mismatch: {args.expected_koina_tag} -> {tag_commit}, "
            f"expected {expected}"
        )

    target = args.output_dir.resolve()
    partial = require_new_output_root(target)
    partial.mkdir(parents=True)
    wav_root = partial / "input_wav_links"
    koina_output = partial / "koina_output"
    wav_root.mkdir()
    koina_output.mkdir()
    tsv_path = partial / "input.tsv"
    with tsv_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["filename", "sex", "text"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for index, row in enumerate(rows, 1):
            safe_name = f"{index:03d}__{row['pv_id']}.wav"
            os.symlink(str(row["_wav_path"]), str(wav_root / safe_name))
            writer.writerow(
                {"filename": safe_name, "sex": row["sex"], "text": row["text"]}
            )

    start = {
        "schema_version": "stage2_pv_b_koina_run_start.v1",
        "status": "running_machine_candidate_only",
        "started_at": now_iso(),
        "koina": {
            "repository": "https://github.com/YugwonWon/KOINA",
            "declared_version": args.expected_koina_tag,
            "commit": actual,
        },
        "input": public_input_records(rows),
        "preflight": report,
    }
    write_json_new(partial / "RUN_START.json", start)
    command = [
        sys.executable,
        str(transcriber),
        str(tsv_path),
        "--wav_root_dir",
        str(wav_root),
        "--save_dir",
        str(koina_output),
        "--n_jobs",
        "1",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    (partial / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (partial / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        write_json_new(
            partial / "RUN_FAILURE.json",
            {
                "schema_version": "stage2_pv_b_koina_failure.v1",
                "status": "failed_partial_preserved",
                "finished_at": now_iso(),
                "returncode": completed.returncode,
            },
        )
        raise RuntimeError(
            f"KOINA failed with exit {completed.returncode}; partial preserved: {partial}"
        )

    artifacts = []
    for path in sorted(koina_output.rglob("*")):
        if path.is_file() and not path.is_symlink():
            artifacts.append(
                {
                    "relative_path": path.relative_to(partial).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    write_json_new(
        partial / "RUN_RESULT.json",
        {
            "schema_version": "stage2_pv_b_koina_result.v1",
            "status": "completed_machine_candidate_not_realization",
            "finished_at": now_iso(),
            "koina_commit": actual,
            "koina_tag": args.expected_koina_tag,
            "input_count": len(rows),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "canonical_assets_modified": False,
        },
    )
    promote_partial(partial, target)
    print(json.dumps({"status": "completed", "output_dir": str(target)}))


def main() -> None:
    args = build_parser().parse_args()
    rows, report = preflight(args)
    if not args.execute:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    execute(args, rows, report)


if __name__ == "__main__":
    main()
