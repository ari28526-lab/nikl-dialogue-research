"""Prepare a fail-closed researcher review for post-MFA alignment failures.

The helper never approves exclusions and never changes the MFA database.  It
turns the exact-ID reconciliation inventory into two auditable CSV files and,
optionally, a small WAV/LAB pilot for checking transcript/audio pairing.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
from collections import Counter
from pathlib import Path

from mfa_exclusion_contract import REVIEW_FIELDS, load_contract
from pipeline_common import atomic_write_json, file_fingerprint


DETAIL_FIELDS = [
    "review_order",
    "year",
    "utt_id",
    "session_id",
    "duration_sec",
    "num_frames",
    "normalized_text",
    "job_id",
    "word_interval_present",
    "phone_interval_present",
    "alignment_log_likelihood",
    "reason_code",
    "evidence",
    "recommended_next_step",
]

PILOT_FIELDS = [
    "review_order",
    "sample_role",
    "year",
    "utt_id",
    "session_id",
    "duration_sec",
    "normalized_text",
    "wav_path",
    "lab_path",
    "decision",
    "notes",
]


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_missing_rows(db_path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    connection = sqlite3.connect(
        f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True
    )
    try:
        rows = connection.execute(
            """
            SELECT f.name, f.relative_path, u.begin, u.end, u.num_frames,
                   u.normalized_text, u.job_id, u.alignment_log_likelihood,
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
            WHERE u.ignored=0
            ORDER BY f.name
            """
        ).fetchall()
    finally:
        connection.close()

    missing: list[dict[str, object]] = []
    aligned: list[dict[str, object]] = []
    for row in rows:
        record = {
            "utt_id": str(row[0]),
            "session_id": str(row[1]),
            "duration_sec": round(float(row[3]) - float(row[2]), 6),
            "num_frames": int(row[4]) if row[4] is not None else None,
            "normalized_text": str(row[5] or ""),
            "job_id": int(row[6]) if row[6] is not None else None,
            "alignment_log_likelihood": row[7],
            "word_interval_present": bool(row[8]),
            "phone_interval_present": bool(row[9]),
        }
        if record["word_interval_present"] and record["phone_interval_present"]:
            aligned.append(record)
        else:
            missing.append(record)
    return missing, aligned


def _select_pilot(
    missing: list[dict[str, object]],
    aligned: list[dict[str, object]],
) -> list[tuple[str, dict[str, object]]]:
    by_session: dict[str, list[dict[str, object]]] = {}
    for row in missing:
        by_session.setdefault(str(row["session_id"]), []).append(row)
    ranked = sorted(by_session, key=lambda key: (-len(by_session[key]), key))

    selected: list[tuple[str, dict[str, object]]] = []
    seen: set[str] = set()

    def add(role: str, row: dict[str, object]) -> None:
        utt_id = str(row["utt_id"])
        if utt_id not in seen:
            selected.append((role, row))
            seen.add(utt_id)

    if ranked:
        dominant = by_session[ranked[0]]
        positions = sorted({0, len(dominant) // 3, 2 * len(dominant) // 3, len(dominant) - 1})
        for position in positions:
            add("dominant_session_missing", dominant[position])
    for session in ranked[1:5]:
        add("other_cluster_missing", by_session[session][0])
    for session in ranked[5:9]:
        add("distributed_missing", by_session[session][0])

    dominant_session = ranked[0] if ranked else ""
    controls = [
        row for row in aligned if str(row["session_id"]) == dominant_session
    ]
    if controls:
        positions = sorted({0, len(controls) // 3, 2 * len(controls) // 3, len(controls) - 1})
        for position in positions:
            add("dominant_session_aligned_control", controls[position])
    return selected


def prepare_review(
    *,
    db_path: Path,
    year: str,
    export_report: Path,
    approved_exclusions_contract: Path,
    lab_root: Path,
    output_root: Path,
    copy_sample_files: bool,
) -> dict[str, object]:
    db_path = db_path.resolve()
    export_report = export_report.resolve()
    approved_exclusions_contract = approved_exclusions_contract.resolve()
    lab_root = lab_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"review output already exists: {output_root}")

    report = _read_json(export_report)
    reconciliation = report.get("exact_id_reconciliation")
    if not isinstance(reconciliation, dict):
        raise RuntimeError("export report exact_id_reconciliation missing")
    inventories = reconciliation.get("inventories")
    if not isinstance(inventories, dict):
        raise RuntimeError("export report inventories missing")
    expected = {
        str(value)
        for value in inventories.get("unknown_active_lab_without_alignment", [])
    }
    if not expected:
        raise RuntimeError("post-MFA missing inventory is empty")

    contract_data = _read_json(approved_exclusions_contract)
    input_contract_id = str(contract_data.get("input_contract_id") or "")
    if not input_contract_id:
        raise RuntimeError("approved exclusion input_contract_id missing")
    _, existing_rows = load_contract(
        approved_exclusions_contract,
        year=year,
        input_contract_id=input_contract_id,
    )

    missing, aligned = _load_missing_rows(db_path)
    observed = {str(row["utt_id"]) for row in missing}
    if observed != expected:
        raise RuntimeError(
            "DB/report post-MFA missing inventory mismatch: "
            f"db_only={len(observed - expected)} report_only={len(expected - observed)}"
        )
    if observed & set(existing_rows):
        raise RuntimeError("post-MFA candidates already present in approved contract")

    output_root.mkdir(parents=True)
    details_path = output_root / "01_CANDIDATE_DETAILS.csv"
    decisions_path = output_root / "02_RESEARCHER_DECISIONS.csv"
    detail_rows: list[dict[str, object]] = []
    decision_rows: list[dict[str, object]] = []
    for order, row in enumerate(missing, 1):
        utt_id = str(row["utt_id"])
        detail_rows.append(
            {
                "review_order": order,
                "year": year,
                **row,
                "reason_code": "mfa_alignment_missing",
                "evidence": str(export_report),
                "recommended_next_step": "check clustered input; then approve exclusion or targeted recovery",
            }
        )
        decision_rows.append(
            {
                "year": year,
                "input_contract_id": input_contract_id,
                "utt_id": utt_id,
                "reason_code": "mfa_alignment_missing",
                "exclusion_scope": "alignment_and_analysis",
                "evidence_path": str(export_report),
                "decision": "pending",
                "notes": "MFA beam=10 and retry_beam=40 produced no word/phone intervals",
            }
        )
    _write_csv(details_path, DETAIL_FIELDS, detail_rows)
    _write_csv(decisions_path, REVIEW_FIELDS, decision_rows)

    pilot_rows: list[dict[str, object]] = []
    pilot_root = output_root / "03_AUDIO_LAB_PILOT"
    for order, (role, row) in enumerate(_select_pilot(missing, aligned), 1):
        utt_id = str(row["utt_id"])
        session = str(row["session_id"])
        source_root = lab_root / year / session
        source_wav = source_root / f"{utt_id}.wav"
        source_lab = source_root / f"{utt_id}.lab"
        if not source_wav.is_file() or not source_lab.is_file():
            raise FileNotFoundError(f"pilot WAV/LAB missing: {utt_id}")
        wav_path = source_wav
        lab_path = source_lab
        if copy_sample_files:
            pilot_root.mkdir(parents=True, exist_ok=True)
            wav_path = pilot_root / source_wav.name
            lab_path = pilot_root / source_lab.name
            shutil.copy2(source_wav, wav_path)
            shutil.copy2(source_lab, lab_path)
        pilot_rows.append(
            {
                "review_order": order,
                "sample_role": role,
                "year": year,
                "utt_id": utt_id,
                "session_id": session,
                "duration_sec": row["duration_sec"],
                "normalized_text": row["normalized_text"],
                "wav_path": str(wav_path),
                "lab_path": str(lab_path),
                "decision": "pending",
                "notes": "Does WAV content match normalized_text/LAB?",
            }
        )
    pilot_csv = output_root / "03_AUDIO_LAB_PILOT_REVIEW.csv"
    _write_csv(pilot_csv, PILOT_FIELDS, pilot_rows)

    session_counts = Counter(str(row["session_id"]) for row in missing)
    summary: dict[str, object] = {
        "schema_version": "mfa_post_alignment_review.v1",
        "status": "pending_researcher_review",
        "year": year,
        "input_contract_id": input_contract_id,
        "auto_approval_performed": False,
        "mfa_database_modified": False,
        "full_year_mfa_rerun_required": False,
        "candidate_count": len(missing),
        "candidate_session_count": len(session_counts),
        "top_sessions": [
            {"session_id": key, "candidate_count": value}
            for key, value in session_counts.most_common(20)
        ],
        "pilot_count": len(pilot_rows),
        "existing_approved_exclusion_count": len(existing_rows),
        "artifacts": {
            "details": file_fingerprint(details_path, with_sha256=True),
            "decisions": file_fingerprint(decisions_path, with_sha256=True),
            "pilot_review": file_fingerprint(pilot_csv, with_sha256=True),
            "export_report": file_fingerprint(export_report, with_sha256=True),
            "database": file_fingerprint(db_path, with_sha256=False),
            "approved_exclusions_contract": file_fingerprint(
                approved_exclusions_contract, with_sha256=True
            ),
        },
        "researcher_question": (
            "Check the pilot for WAV/LAB pairing, especially the dominant "
            "session; then approve exclusion or request targeted recovery."
        ),
    }
    atomic_write_json(output_root / "SUMMARY.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--export-report", type=Path, required=True)
    parser.add_argument("--approved-exclusions-contract", type=Path, required=True)
    parser.add_argument("--lab-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--copy-sample-files", action="store_true")
    args = parser.parse_args()
    summary = prepare_review(
        db_path=args.db,
        year=args.year,
        export_report=args.export_report,
        approved_exclusions_contract=args.approved_exclusions_contract,
        lab_root=args.lab_root,
        output_root=args.output_root,
        copy_sample_files=args.copy_sample_files,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
