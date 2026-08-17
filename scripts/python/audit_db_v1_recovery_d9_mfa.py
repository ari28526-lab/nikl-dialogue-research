#!/usr/bin/env python3
"""Audit D9 TextGrid coverage without adopting results into r3 or DB v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d9_common import D9_ID, D9_OUTPUT_ROOT, D9_SHARD_ID, PROJECT_ROOT, load_json
from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot


def tier_names(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("name = "):
            names.append(stripped.split("=", 1)[1].strip().strip('"'))
    return names


def run(args: argparse.Namespace) -> dict:
    package = args.package.resolve()
    output_root = args.output_root.resolve()
    rows = load_json(package / "D9_RUN_SHARD.json")["rows"]
    expected = {row["utt_id"]: row for row in rows}
    observed: dict[str, Path] = {}
    duplicates: list[str] = []
    for path in output_root.rglob("*.TextGrid"):
        if path.stem in observed:
            duplicates.append(path.stem)
        observed[path.stem] = path
    extras = sorted(set(observed) - set(expected))
    if duplicates or extras:
        raise RuntimeError(f"D9 TextGrid identity mismatch: duplicates={duplicates[:3]}, extras={extras[:3]}")
    results: list[dict] = []
    for row in rows:
        path = observed.get(row["utt_id"])
        present = path is not None
        tiers = tier_names(path) if path else []
        if present and not {"words", "phones"}.issubset(set(tiers)):
            raise RuntimeError(f"D9 TextGrid required tiers missing: {row['utt_id']}: {tiers}")
        results.append(
            {
                "run_order": row["run_order"],
                "year": row["year"],
                "utt_id": row["utt_id"],
                "session_id": row["session_id"],
                "source_overlap": row["source_overlap"],
                "textgrid_present": present,
                "textgrid": file_fingerprint(path, with_sha256=True) if path else None,
                "tier_names": tiers,
                "adoption_status": "pending_separate_researcher_review" if present else "not_recovered",
            }
        )
    report = {
        "schema_version": "research_db_v1_recovery_d9_mfa_audit.v1",
        "status": "completed_controlled_retry_no_merge",
        "recorded_at": now_iso(),
        "shard_id": D9_SHARD_ID,
        "expected": len(expected),
        "textgrid_present": sum(row["textgrid_present"] for row in results),
        "textgrid_missing": sum(not row["textgrid_present"] for row in results),
        "results": results,
        "output_root": str(output_root),
        "automatic_merge_performed": False,
        "next_gate": "review recovered exact IDs; adoption and 6-tier generation remain separately closed",
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D9_ID)
    parser.add_argument("--output-root", type=Path, default=D9_OUTPUT_ROOT / "mfa_output")
    parser.add_argument("--report", type=Path, default=D9_OUTPUT_ROOT / "state" / "MFA_AUDIT.json")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
