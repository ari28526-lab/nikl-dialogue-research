#!/usr/bin/env python3
"""Audit D5 MFA output without merging it into the frozen research body."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d5_common import D5_ID, D5_OUTPUT_ROOT, D5_SHARD_ID, PROJECT_ROOT, read_gzip_csv
from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint, now_iso, runtime_snapshot


def run(args: argparse.Namespace) -> dict:
    package = args.package.resolve()
    output_root = args.output_root.resolve()
    _, rows = read_gzip_csv(package / "D5_RUN_SHARD.csv.gz")
    expected = {(row["year"], row["utt_id"]): row for row in rows}
    observed: dict[str, Path] = {}
    duplicates: list[str] = []
    for path in output_root.rglob("*.TextGrid"):
        if path.stem in observed:
            duplicates.append(path.stem)
        observed[path.stem] = path
    missing = [
        {"year": year, "utt_id": utt_id, "session_id": row["session_id"], "reason_code": row["reason_code"]}
        for (year, utt_id), row in expected.items() if utt_id not in observed
    ]
    extras = sorted(set(observed) - {utt_id for _, utt_id in expected})
    if duplicates or extras:
        raise RuntimeError(f"D5 TextGrid identity mismatch: duplicates={duplicates[:3]}, extras={extras[:3]}")
    missing_path = args.missing_csv.resolve()
    with atomic_text_writer(missing_path, encoding="utf-8-sig", newline="") as (stream, _):
        writer = csv.DictWriter(
            stream,
            fieldnames=("year", "utt_id", "session_id", "reason_code"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(missing)
    report = {
        "schema_version": "research_db_v1_recovery_d5_mfa_audit.v1",
        "status": "completed_diagnostic_no_merge",
        "recorded_at": now_iso(),
        "shard_id": D5_SHARD_ID,
        "expected": len(expected),
        "textgrid_present": len(expected) - len(missing),
        "textgrid_missing": len(missing),
        "missing_inventory": file_fingerprint(missing_path, with_sha256=True),
        "output_root": str(output_root),
        "automatic_merge_performed": False,
        "next_gate": "review diagnostic output and decide exact-ID adoption or further recovery",
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D5_ID)
    parser.add_argument("--output-root", type=Path, default=D5_OUTPUT_ROOT / "mfa_output")
    parser.add_argument("--missing-csv", type=Path, default=D5_OUTPUT_ROOT / "state" / "MFA_MISSING.csv")
    parser.add_argument("--report", type=Path, default=D5_OUTPUT_ROOT / "state" / "MFA_AUDIT.json")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
