#!/usr/bin/env python3
"""Record researcher-reviewed D5 diagnostic alignments without main-body adoption.

The reviewed Dropbox CSV is copied byte-for-byte as evidence.  Structured
decisions are emitted as JSON and a separate SQLite inventory.  The frozen r3
body, research 6-tier outputs, and DB v1 are never opened for writing.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import sys
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
D6_REVIEW_ROOT = PROJECT_ROOT / "outputs/reviews/db_v1_recovery_d6_20260815"
D6_RELEASE_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d6_gate_20260815"
DROPBOX_REVIEW_ROOT = Path(r"C:\Users\ari30\Dropbox\DB_V1_RECOVERY_D6_REVIEW_11_20260815")
D7_ID = "nikl_dialogue_research_db_v1_recovery_d7_partial_alignment_gate_20260817"


DECISION_MAP = {
    "SDRW2000000057.1.1.70": ("noise_hold", "preserve_diagnostic_only"),
    "SDRW2000000109.1.1.149": ("noise_hold", "preserve_diagnostic_only"),
    "SDRW2000000120.1.1.296": ("noise_hold", "preserve_diagnostic_only"),
    "SDRW2200000009.1.1.329": (
        "transcript_segment_missing",
        "recover_missing_transcript_then_new_exact_id_gate",
    ),
    "SDRW2200000029.1.1.234": (
        "transcript_correction_candidate",
        "correct_transcript_then_controlled_exact_id_realign",
    ),
    "SARW2400000064.1.1.1": (
        "partial_alignment_available",
        "retain_searchable_partial_alignment_separate_from_main_body",
    ),
    "SARW2400000065.1.1.165": (
        "partial_alignment_available",
        "retain_searchable_partial_alignment_separate_from_main_body",
    ),
    "SARW2500000015.1.1.18": (
        "partial_alignment_available",
        "retain_searchable_partial_alignment_separate_from_main_body",
    ),
    "SARW2500000024.1.1.91": (
        "partial_alignment_available",
        "retain_searchable_partial_alignment_separate_from_main_body",
    ),
    "SARW2500000058.1.1.55": (
        "partial_alignment_available",
        "retain_searchable_partial_alignment_separate_from_main_body",
    ),
    "SARW2500000083.1.1.79": (
        "partial_alignment_available",
        "retain_searchable_partial_alignment_separate_from_main_body",
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def file_record(path: Path, root: Path) -> dict[str, object]:
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_review_rows(rows: list[dict[str, str]]) -> None:
    if len(rows) != 11:
        raise RuntimeError(f"review row count differs: {len(rows)}")
    ids = [row.get("utt_id", "") for row in rows]
    if len(set(ids)) != 11 or set(ids) != set(DECISION_MAP):
        raise RuntimeError("review exact-ID set differs from approved D7 map")
    for row in rows:
        if not row.get("notes", "").strip():
            raise RuntimeError(f"researcher note missing: {row['utt_id']}")
        if row.get("decision") != "pending":
            raise RuntimeError("Dropbox evidence decision cells must remain original pending values")


def build_decisions(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    decisions: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: int(item["review_order"])):
        utt_id = row["utt_id"]
        usability, future_action = DECISION_MAP[utt_id]
        review_wav = D6_REVIEW_ROOT / row["review_wav"]
        review_lab = D6_REVIEW_ROOT / row["review_lab"]
        review_textgrid = D6_REVIEW_ROOT / row["review_textgrid"]
        for path in (review_wav, review_lab, review_textgrid):
            if not path.is_file():
                raise RuntimeError(f"preserved diagnostic file missing: {path}")
        if sha256_file(review_wav) != row["wav_sha256"]:
            raise RuntimeError(f"WAV hash differs: {utt_id}")
        if sha256_file(review_lab) != row["lab_sha256"]:
            raise RuntimeError(f"LAB hash differs: {utt_id}")
        if sha256_file(review_textgrid) != row["textgrid_sha256"]:
            raise RuntimeError(f"TextGrid hash differs: {utt_id}")
        decisions.append(
            {
                "review_order": int(row["review_order"]),
                "year": int(row["year"]),
                "utt_id": utt_id,
                "session_id": row["session_id"],
                "form": row["form"],
                "original_form": row["original_form"],
                "researcher_note": row["notes"],
                "exclusion_scope": "main_alignment_and_analysis",
                "main_body_status": "excluded_not_adopted",
                "diagnostic_alignment_status": "diagnostic_2tier_preserved_unadopted",
                "research_usability": usability,
                "future_action": future_action,
                "searchable_in_separate_recovery_db": True,
                "counted_as_main_alignment_success": False,
                "automatic_merge_allowed": False,
                "requires_separate_future_approval": True,
                "wav_path": str(review_wav.resolve()),
                "lab_path": str(review_lab.resolve()),
                "textgrid_path": str(review_textgrid.resolve()),
                "wav_sha256": row["wav_sha256"],
                "lab_sha256": row["lab_sha256"],
                "textgrid_sha256": row["textgrid_sha256"],
                "source_csv": row["source_csv"],
                "source_start_seconds": row["source_start_seconds"],
                "source_end_seconds": row["source_end_seconds"],
            }
        )
    return decisions


def build_sqlite(path: Path, decisions: list[dict[str, object]], metadata: dict[str, str]) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute(
            """
            CREATE TABLE partial_alignment_inventory (
                review_order INTEGER PRIMARY KEY,
                year INTEGER NOT NULL,
                utt_id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL,
                form TEXT NOT NULL,
                original_form TEXT NOT NULL,
                researcher_note TEXT NOT NULL,
                exclusion_scope TEXT NOT NULL,
                main_body_status TEXT NOT NULL,
                diagnostic_alignment_status TEXT NOT NULL,
                research_usability TEXT NOT NULL,
                future_action TEXT NOT NULL,
                searchable_in_separate_recovery_db INTEGER NOT NULL CHECK(searchable_in_separate_recovery_db IN (0,1)),
                counted_as_main_alignment_success INTEGER NOT NULL CHECK(counted_as_main_alignment_success IN (0,1)),
                automatic_merge_allowed INTEGER NOT NULL CHECK(automatic_merge_allowed IN (0,1)),
                requires_separate_future_approval INTEGER NOT NULL CHECK(requires_separate_future_approval IN (0,1)),
                wav_path TEXT NOT NULL,
                lab_path TEXT NOT NULL,
                textgrid_path TEXT NOT NULL,
                wav_sha256 TEXT NOT NULL,
                lab_sha256 TEXT NOT NULL,
                textgrid_sha256 TEXT NOT NULL,
                source_csv TEXT NOT NULL,
                source_start_seconds TEXT NOT NULL,
                source_end_seconds TEXT NOT NULL
            )
            """
        )
        fields = list(decisions[0])
        placeholders = ",".join("?" for _ in fields)
        connection.executemany(
            f"INSERT INTO partial_alignment_inventory ({','.join(fields)}) VALUES ({placeholders})",
            [[int(value) if isinstance(value, bool) else value for value in (row[field] for field in fields)] for row in decisions],
        )
        connection.execute("CREATE INDEX idx_partial_alignment_year ON partial_alignment_inventory(year)")
        connection.execute("CREATE INDEX idx_partial_alignment_usability ON partial_alignment_inventory(research_usability)")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", sorted(metadata.items()))
        connection.commit()
    finally:
        connection.close()


def build(args: argparse.Namespace) -> dict[str, object]:
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"D7 output exists: {output_root}")
    partial = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    partial.mkdir(parents=True)

    reviewed_csv = DROPBOX_REVIEW_ROOT / "00_REVIEW_11.csv"
    rows = read_csv(reviewed_csv)
    verify_review_rows(rows)
    decisions = build_decisions(rows)
    source_snapshot = partial / "RESEARCHER_REVIEW_SOURCE.csv"
    shutil.copy2(reviewed_csv, source_snapshot)
    if sha256_file(source_snapshot) != sha256_file(reviewed_csv):
        raise RuntimeError("researcher review snapshot copy hash differs")

    decision_document = {
        "schema_version": "research_db_v1_recovery_d7_exact_id_decisions.v1",
        "status": "approved_excluded_from_main_body_artifacts_preserved",
        "recorded_at": now_iso(),
        "approved_by": "ari30",
        "decision_basis": "Dropbox notes reviewed; user approved exclusion with partial-alignment preservation",
        "counts": {
            "total": 11,
            "excluded_from_main_body": 11,
            "partial_alignment_available": 6,
            "noise_hold": 3,
            "transcript_segment_missing": 1,
            "transcript_correction_candidate": 1,
        },
        "decisions": decisions,
    }
    decision_path = partial / "D7_EXACT_ID_DECISIONS.json"
    decision_path.write_text(json.dumps(decision_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metadata = {
        "schema_version": "research_db_v1_recovery_d7_partial_alignment_db.v1",
        "status": "separate_recovery_inventory_no_main_body_adoption",
        "recorded_at": decision_document["recorded_at"],
        "review_source_sha256": sha256_file(source_snapshot),
        "decision_json_sha256": sha256_file(decision_path),
        "r3_body_mutation_allowed": "false",
        "research_6tier_mutation_allowed": "false",
        "db_v1_mutation_allowed": "false",
    }
    sqlite_path = partial / "D7_PARTIAL_ALIGNMENT_PRESERVATION.sqlite"
    build_sqlite(sqlite_path, decisions, metadata)

    gate = {
        "schema_version": "research_db_v1_recovery_d7_gate.v1",
        "status": "closed_researcher_review_recorded_no_main_body_adoption",
        "recorded_at": now_iso(),
        "counts": decision_document["counts"],
        "safety": {
            "r3_body_mutated": False,
            "research_6tier_mutated": False,
            "db_v1_mutated": False,
            "automatic_merge_performed": False,
            "diagnostic_wav_lab_textgrid_deleted": False,
        },
        "next_gate": "D8 exact-ID recovery feasibility for the 19 alignment-missing and 25 short/missing-PCM records",
    }
    gate_path = partial / "D7_GATE.json"
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (partial / "README.md").write_text(
        "# DB v1 recovery D7 partial-alignment preservation gate\n\n"
        "연구자가 검토한 D5 진단 TextGrid 11건을 본체 정렬 성공에서는 제외하고, "
        "원인과 향후 사용 가능성을 exact-ID로 보존한다. 6건은 "
        "`partial_alignment_available`, 3건은 `noise_hold`, 2건은 전사 회수·수정 "
        "후보다. WAV·LAB·TextGrid는 D6 검토 root에 그대로 있으며 삭제하거나 "
        "r3 본체·6-tier·DB v1에 병합하지 않았다.\n\n"
        "Dropbox CSV는 `RESEARCHER_REVIEW_SOURCE.csv`에 바이트 그대로 보존했고, "
        "권위 구조화 결정은 JSON과 별도 SQLite다.\n",
        encoding="utf-8",
    )
    manifest_path = partial / "OUTPUT_MANIFEST.json"
    manifest = {
        "schema_version": "research_db_v1_recovery_d7_output_manifest.v1",
        "recorded_at": now_iso(),
        "inputs": {
            "dropbox_review_csv_sha256": sha256_file(reviewed_csv),
            "d6_decision_table_sha256": sha256_file(D6_RELEASE_ROOT / "D6_SUCCESS_11_REVIEW.csv"),
            "d6_review_manifest_sha256": sha256_file(D6_REVIEW_ROOT / "REVIEW_MANIFEST.json"),
        },
        "files": [file_record(path, partial) for path in sorted(partial.iterdir()) if path.is_file()],
        "implementation": {
            "builder_sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, output_root)

    report = {
        "schema_version": "research_db_v1_recovery_d7_result.v1",
        "status": gate["status"],
        "recorded_at": now_iso(),
        "output_root": str(output_root),
        "counts": decision_document["counts"],
        "safety": gate["safety"],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs/releases" / D7_ID)
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "outputs/reports/RESULT_db_v1_recovery_D7_20260817.json")
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
