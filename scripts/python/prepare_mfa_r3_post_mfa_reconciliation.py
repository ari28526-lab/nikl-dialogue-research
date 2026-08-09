"""Prepare the exact-ID r3 post-MFA reconciliation review.

This stage is read-only with respect to the retained MFA database, corpus, and
source data.  It never approves exclusions.  It proves that the database IDs
equal the frozen r3 input denominator and writes only the utterances that have
no complete word+phone alignment into a researcher approval queue.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Mapping

from mfa_exclusion_contract import REVIEW_FIELDS
from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
)


SCHEMA_VERSION = "mfa_r3_post_mfa_reconciliation_review.v1"
DETAIL_FIELDS = [
    "review_order",
    "year",
    "utt_id",
    "session_id",
    "duration_sec",
    "num_frames",
    "normalized_text",
    "job_id",
    "ignored_by_mfa",
    "word_interval_present",
    "phone_interval_present",
    "alignment_log_likelihood",
    "reason_code",
    "recommended_scope",
    "evidence",
]


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _verify_fingerprint(record: Mapping[str, object], label: str) -> Path:
    path = Path(str(record.get("path", ""))).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label}: {path}")
    if int(record.get("bytes", -1)) != path.stat().st_size:
        raise RuntimeError(f"{label} bytes differ")
    if str(record.get("sha256", "")).lower() != sha256_file(path).lower():
        raise RuntimeError(f"{label} SHA-256 differs")
    return path


def _load_expected_ids(path: Path, year: str) -> tuple[set[str], dict[str, str]]:
    ids: set[str] = set()
    sessions: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"year", "utt_id", "session_id"}
        if not required.issubset(reader.fieldnames or ()):
            raise RuntimeError("expected MFA input schema differs")
        for line_number, row in enumerate(reader, 2):
            if str(row.get("year", "")).strip() != str(year):
                raise RuntimeError(f"expected input year differs at {line_number}")
            utt_id = str(row.get("utt_id", "")).strip()
            session_id = str(row.get("session_id", "")).strip()
            if not utt_id or not session_id or utt_id in ids:
                raise RuntimeError(
                    f"expected input empty/duplicate at {line_number}: {utt_id!r}"
                )
            ids.add(utt_id)
            sessions[utt_id] = session_id
    return ids, sessions


def _database_rows(db_path: Path) -> tuple[list[dict[str, object]], int]:
    connection = sqlite3.connect(
        f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True, timeout=120
    )
    try:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        if quick_check != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {quick_check}")
        rows = connection.execute(
            """
            SELECT f.name, f.relative_path, u.begin, u.end, u.num_frames,
                   u.normalized_text, u.job_id, u.alignment_log_likelihood,
                   u.ignored,
                   EXISTS(
                       SELECT 1 FROM word_interval wi
                       WHERE wi.utterance_id=u.id
                   ),
                   EXISTS(
                       SELECT 1 FROM phone_interval pi
                       WHERE pi.utterance_id=u.id
                   )
            FROM utterance u
            JOIN file f ON f.id=u.file_id
            ORDER BY f.name
            """
        ).fetchall()
    finally:
        connection.close()
    records: list[dict[str, object]] = []
    for row in rows:
        records.append(
            {
                "utt_id": str(row[0]),
                "session_id": str(row[1]),
                "duration_sec": round(float(row[3]) - float(row[2]), 6),
                "num_frames": int(row[4]) if row[4] is not None else None,
                "normalized_text": str(row[5] or ""),
                "job_id": int(row[6]) if row[6] is not None else None,
                "alignment_log_likelihood": row[7],
                "ignored_by_mfa": bool(row[8]),
                "word_interval_present": bool(row[9]),
                "phone_interval_present": bool(row[10]),
            }
        )
    return records, len(rows)


def _candidate_identity(rows: list[dict[str, object]]) -> str:
    payload = "\n".join(
        "|".join(
            [
                str(row["year"]),
                str(row["input_contract_id"]),
                str(row["utt_id"]),
                str(row["reason_code"]),
                str(row["exclusion_scope"]),
            ]
        )
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def prepare(
    *,
    db_path: Path,
    year: str,
    alignment_marker: Path,
    alignment_contract: Path,
    output_root: Path,
) -> dict[str, object]:
    db_path = db_path.resolve()
    alignment_marker = alignment_marker.resolve()
    alignment_contract = alignment_contract.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"post-MFA review already exists: {output_root}")

    marker = _read_json(alignment_marker)
    contract = _read_json(alignment_contract)
    if (
        marker.get("schema_version") != "mfa_r3_alignment_done.v1"
        or marker.get("status") != "passed"
        or str(marker.get("year")) != str(year)
        or contract.get("schema_version") != "mfa_r3_alignment_contract.v1"
        or str(contract.get("year")) != str(year)
        or str(marker.get("alignment_contract_id"))
        != str(contract.get("alignment_contract_id"))
    ):
        raise RuntimeError("r3 marker/alignment contract identity differs")
    source_db = marker.get("source_db")
    if not isinstance(source_db, Mapping):
        raise RuntimeError("ALIGN_DONE source DB fingerprint missing")
    if db_path != Path(str(source_db.get("path", ""))).resolve():
        raise RuntimeError("ALIGN_DONE source DB path differs")
    if (
        int(source_db.get("bytes", -1)) != db_path.stat().st_size
        or str(source_db.get("sha256", "")).lower()
        != sha256_file(db_path).lower()
    ):
        raise RuntimeError("ALIGN_DONE source DB fingerprint differs")

    identity = contract.get("identity")
    year_input = contract.get("year_input")
    if not isinstance(identity, Mapping) or not isinstance(year_input, Mapping):
        raise RuntimeError("r3 alignment identity/year input missing")
    input_contract_id = str(identity.get("year_input_contract_id", "")).strip()
    expected_record = year_input.get("expected_mfa_input_ids")
    if not input_contract_id or not isinstance(expected_record, Mapping):
        raise RuntimeError("r3 expected MFA input identity missing")
    if str(identity.get("expected_mfa_input_sha256", "")).lower() != str(
        expected_record.get("sha256", "")
    ).lower():
        raise RuntimeError("r3 expected MFA input SHA identity differs")
    expected_path = _verify_fingerprint(
        expected_record, "expected MFA input IDs"
    )
    expected_ids, expected_sessions = _load_expected_ids(expected_path, year)
    if len(expected_ids) != int(year_input.get("expected_mfa_input", -1)):
        raise RuntimeError("expected MFA input count differs")

    db_rows, db_row_count = _database_rows(db_path)
    db_ids = [str(row["utt_id"]) for row in db_rows]
    if len(set(db_ids)) != db_row_count:
        raise RuntimeError("MFA DB duplicate utterance ID")
    db_id_set = set(db_ids)
    if db_id_set != expected_ids:
        raise RuntimeError(
            "MFA DB/input exact-ID mismatch: "
            f"db_only={len(db_id_set - expected_ids)} "
            f"input_only={len(expected_ids - db_id_set)}"
        )

    missing: list[dict[str, object]] = []
    aligned = 0
    for row in db_rows:
        utt_id = str(row["utt_id"])
        if str(row["session_id"]) != expected_sessions[utt_id]:
            raise RuntimeError(f"session identity differs: {utt_id}")
        if row["ignored_by_mfa"]:
            reason = "mfa_feature_generation_failed"
        elif not (
            row["word_interval_present"] and row["phone_interval_present"]
        ):
            reason = "mfa_alignment_missing"
        else:
            aligned += 1
            continue
        missing.append({**row, "reason_code": reason})

    if aligned + len(missing) != len(expected_ids):
        raise RuntimeError("r3 post-MFA accounting equation differs")

    staging = output_root.with_name(
        f".{output_root.name}.{os.getpid()}.partial"
    )
    staging.mkdir(parents=True, exist_ok=False)
    details: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    marker_evidence = str(alignment_marker)
    for order, row in enumerate(missing, 1):
        reason = str(row["reason_code"])
        details.append(
            {
                "review_order": order,
                "year": year,
                **row,
                "recommended_scope": "alignment_and_analysis",
                "evidence": marker_evidence,
            }
        )
        decisions.append(
            {
                "year": year,
                "input_contract_id": input_contract_id,
                "utt_id": row["utt_id"],
                "reason_code": reason,
                "exclusion_scope": "alignment_and_analysis",
                "evidence_path": marker_evidence,
                "decision": "pending",
                "notes": (
                    "retained r3 DB has no complete word+phone intervals; "
                    "preserve WAV/LAB/DB and route exact ID to follow-up"
                ),
            }
        )

    details_path = staging / "01_CANDIDATE_DETAILS.csv"
    decisions_path = staging / "02_RESEARCHER_DECISIONS.csv"
    _write_csv(details_path, DETAIL_FIELDS, details)
    _write_csv(decisions_path, REVIEW_FIELDS, decisions)
    reason_counts = Counter(str(row["reason_code"]) for row in missing)
    session_counts = Counter(str(row["session_id"]) for row in missing)
    summary_path = staging / "03_REVIEW_SUMMARY.json"
    details_fingerprint = file_fingerprint(details_path, with_sha256=True)
    details_fingerprint["path"] = str(
        (output_root / details_path.name).resolve()
    )
    decisions_fingerprint = file_fingerprint(decisions_path, with_sha256=True)
    decisions_fingerprint["path"] = str(
        (output_root / decisions_path.name).resolve()
    )
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_approval",
        "recorded_at": now_iso(),
        "year": str(year),
        "release_id": marker.get("release_id"),
        "alignment_contract_id": marker.get("alignment_contract_id"),
        "input_contract_id": input_contract_id,
        "candidate_identity_sha256": _candidate_identity(decisions),
        "counts": {
            "expected_mfa_input": len(expected_ids),
            "database_utterances": db_row_count,
            "aligned_utterances": aligned,
            "post_mfa_candidates": len(missing),
            "reason_counts": dict(sorted(reason_counts.items())),
            "sessions_with_candidates": len(session_counts),
        },
        "largest_candidate_sessions": [
            {"session_id": session, "count": count}
            for session, count in session_counts.most_common(20)
        ],
        "inputs": {
            "alignment_done": file_fingerprint(
                alignment_marker, with_sha256=True
            ),
            "alignment_contract": file_fingerprint(
                alignment_contract, with_sha256=True
            ),
            "source_db": file_fingerprint(db_path, with_sha256=False),
            "expected_mfa_input_ids": file_fingerprint(
                expected_path, with_sha256=True
            ),
        },
        "outputs": {
            "candidate_details": details_fingerprint,
            "researcher_decisions": decisions_fingerprint,
        },
        "policy": {
            "automatic_approval_performed": False,
            "source_or_mfa_database_modified": False,
            "full_year_realign_requested": False,
            "actual_phonological_realization_judged": False,
            "listening_required_for_exact_id_accounting": False,
            "successful_alignments_preserved": True,
        },
        "approval_instruction": (
            "Approve the frozen candidate identity as technical post-MFA "
            "alignment exclusions before materializing 6-tier outputs."
        ),
    }
    atomic_write_json(summary_path, summary)
    os.replace(staging, output_root)
    final_summary = output_root / summary_path.name
    return _read_json(final_summary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--alignment-marker", type=Path, required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(
        db_path=args.db,
        year=str(args.year),
        alignment_marker=args.alignment_marker,
        alignment_contract=args.alignment_contract,
        output_root=args.output_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
