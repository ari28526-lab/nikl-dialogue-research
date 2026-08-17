#!/usr/bin/env python3
"""Independently audit D7 exclusion and partial-alignment preservation."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d7_partial_alignment_gate_20260817"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_manifest(root: Path) -> int:
    manifest = json.loads((root / "OUTPUT_MANIFEST.json").read_text(encoding="utf-8-sig"))
    count = 0
    for record in manifest["files"]:
        path = root / record["relative_path"]
        if not path.is_file() or path.stat().st_size != int(record["bytes"]):
            raise RuntimeError(f"D7 manifest file/size differs: {path}")
        if sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"D7 manifest hash differs: {path}")
        count += 1
    return count


def audit(args: argparse.Namespace) -> dict[str, object]:
    root = args.root.resolve()
    decisions_doc = json.loads((root / "D7_EXACT_ID_DECISIONS.json").read_text(encoding="utf-8-sig"))
    decisions = decisions_doc["decisions"]
    if len(decisions) != 11 or len({row["utt_id"] for row in decisions}) != 11:
        raise RuntimeError("D7 decision identity/count mismatch")
    source_rows = read_csv(root / "RESEARCHER_REVIEW_SOURCE.csv")
    if {row["utt_id"] for row in source_rows} != {row["utt_id"] for row in decisions}:
        raise RuntimeError("D7 review snapshot/decision ID mismatch")
    source_by_id = {row["utt_id"]: row for row in source_rows}
    for row in decisions:
        source = source_by_id[row["utt_id"]]
        if row["researcher_note"] != source["notes"]:
            raise RuntimeError(f"researcher note differs: {row['utt_id']}")
        if row["main_body_status"] != "excluded_not_adopted":
            raise RuntimeError(f"main-body status differs: {row['utt_id']}")
        if row["diagnostic_alignment_status"] != "diagnostic_2tier_preserved_unadopted":
            raise RuntimeError(f"diagnostic preservation differs: {row['utt_id']}")
        if row["counted_as_main_alignment_success"] or row["automatic_merge_allowed"]:
            raise RuntimeError(f"unsafe adoption flag: {row['utt_id']}")
        if not row["searchable_in_separate_recovery_db"] or not row["requires_separate_future_approval"]:
            raise RuntimeError(f"separate recovery gate differs: {row['utt_id']}")
        for field, hash_field in (("wav_path", "wav_sha256"), ("lab_path", "lab_sha256"), ("textgrid_path", "textgrid_sha256")):
            path = Path(row[field])
            if not path.is_file() or sha256_file(path) != row[hash_field]:
                raise RuntimeError(f"preserved artifact differs: {row['utt_id']} {field}")

    expected_counts = {
        "partial_alignment_available": 6,
        "noise_hold": 3,
        "transcript_segment_missing": 1,
        "transcript_correction_candidate": 1,
    }
    counts = Counter(row["research_usability"] for row in decisions)
    if dict(counts) != expected_counts:
        raise RuntimeError(f"D7 usability counts differ: {dict(counts)}")

    database = root / "D7_PARTIAL_ALIGNMENT_PRESERVATION.sqlite"
    connection = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    try:
        db_rows = connection.execute(
            """
            SELECT utt_id, main_body_status, diagnostic_alignment_status,
                   research_usability, future_action,
                   searchable_in_separate_recovery_db,
                   counted_as_main_alignment_success, automatic_merge_allowed,
                   requires_separate_future_approval, researcher_note
            FROM partial_alignment_inventory ORDER BY review_order
            """
        ).fetchall()
        metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    finally:
        connection.close()
    if len(db_rows) != 11 or {row[0] for row in db_rows} != {row["utt_id"] for row in decisions}:
        raise RuntimeError("D7 SQLite identity/count mismatch")
    by_id = {row["utt_id"]: row for row in decisions}
    for db_row in db_rows:
        source = by_id[db_row[0]]
        expected = (
            source["utt_id"], source["main_body_status"], source["diagnostic_alignment_status"],
            source["research_usability"], source["future_action"], 1, 0, 0, 1,
            source["researcher_note"],
        )
        if db_row != expected:
            raise RuntimeError(f"D7 JSON/SQLite row differs: {source['utt_id']}")
    if metadata.get("r3_body_mutation_allowed") != "false" or metadata.get("db_v1_mutation_allowed") != "false":
        raise RuntimeError("D7 SQLite safety metadata differs")

    gate = json.loads((root / "D7_GATE.json").read_text(encoding="utf-8-sig"))
    if gate["status"] != "closed_researcher_review_recorded_no_main_body_adoption":
        raise RuntimeError("D7 gate is not closed")
    if any(bool(value) for value in gate["safety"].values()):
        raise RuntimeError("D7 gate reports an unauthorized mutation/deletion")

    manifest_files = verify_manifest(root)
    report = {
        "schema_version": "research_db_v1_recovery_d7_independent_audit.v1",
        "status": "passed_excluded_from_main_body_partial_artifacts_preserved",
        "recorded_at": now_iso(),
        "counts": {"total": 11, **expected_counts},
        "sqlite_rows_verified": 11,
        "manifest_files_verified": manifest_files,
        "safety": gate["safety"],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_ROOT / "INDEPENDENT_AUDIT.json")
    args = parser.parse_args()
    audit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
