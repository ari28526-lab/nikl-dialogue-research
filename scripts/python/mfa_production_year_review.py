"""Prepare and validate a minimal researcher review for one production MFA year.

The review checks infrastructure linkage and usability, not phonological realization.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    promote_staged,
    sha256_file,
)

MANIFEST_SCHEMA = "mfa_production_year_review_manifest.v1"
REPORT_SCHEMA = "mfa_production_year_researcher_review.v1"
FIELDS = [
    "review_order",
    "year",
    "session",
    "speaker_id",
    "utt_id",
    "wav_path",
    "lab_path",
    "textgrid_path",
    "decision",
    "notes",
]
IDENTITY_FIELDS = FIELDS[:-2]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise RuntimeError(
                f"review columns differ: actual={reader.fieldnames}, expected={FIELDS}"
            )
        return [dict(row) for row in reader]


def load_search_row(root: Path, year: str, session: str, utt_id: str) -> dict[str, str]:
    candidates = [
        root / year / f"{session}.csv",
        root / year / session / f"{session}.csv",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("utt_id") or row.get("id") or "").strip() == utt_id:
                    return dict(row)
    raise RuntimeError(f"search row missing: {year}/{session}/{utt_id}")


def prepare(
    *,
    year: str,
    sample_csv: Path,
    sample_report: Path,
    align_marker: Path,
    alignment_contract: Path,
    search_master_root: Path,
    wav_root: Path,
    output_csv: Path,
    output_manifest: Path,
) -> dict[str, Any]:
    for output in (output_csv, output_manifest):
        if output.exists():
            raise FileExistsError(f"existing researcher file is preserved: {output}")
    sample = read_json(sample_report)
    align = read_json(align_marker)
    alignment = read_json(alignment_contract)
    if (
        sample.get("schema_version")
        != "mfa_db_research_6tier_sample_equivalence.v1"
        or sample.get("status") != "success"
        or str(sample.get("year")) != year
    ):
        raise RuntimeError("sample report is not a successful production-year sample")
    sample_fp = file_fingerprint(sample_csv.resolve(), with_sha256=True)
    recorded_sample = sample.get("sample_csv") or {}
    if recorded_sample.get("sha256") != sample_fp["sha256"]:
        raise RuntimeError("sample CSV SHA differs from sample report")
    input_id = str(sample.get("input_contract_id") or "")
    alignment_id = str(sample.get("alignment_contract_id") or "")
    if (
        not input_id
        or not alignment_id
        or alignment.get("status") != "passed"
        or alignment.get("lab_input_contract_id") != input_id
        or alignment.get("alignment_contract_id") != alignment_id
    ):
        raise RuntimeError("sample and alignment contract identity differ")
    db_path = Path(str((align.get("details") or {}).get("alignment_db") or ""))
    if not db_path.is_file() or db_path.stat().st_size == 0:
        raise RuntimeError(f"retained alignment DB missing: {db_path}")

    with sample_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        sample_rows = list(csv.DictReader(stream))
    if len(sample_rows) < 5 or len({row["session"] for row in sample_rows}) < 5:
        raise RuntimeError("production review requires at least five sampled sessions")

    rows: list[dict[str, str]] = []
    for order, sample_row in enumerate(sample_rows, 1):
        session = sample_row["session"]
        utt_id = sample_row["utt_id"]
        search = load_search_row(search_master_root, year, session, utt_id)
        speaker = (search.get("speaker_id") or "").strip()
        wav = wav_root / year / session / f"{utt_id}.wav"
        lab = wav_root / year / session / f"{utt_id}.lab"
        textgrid = Path(sample_row["final_path"])
        missing = [str(path) for path in (wav, lab, textgrid) if not path.is_file()]
        if missing:
            raise RuntimeError(f"review payload missing for {utt_id}: {missing}")
        rows.append(
            {
                "review_order": str(order),
                "year": year,
                "session": session,
                "speaker_id": speaker,
                "utt_id": utt_id,
                "wav_path": str(wav.resolve()),
                "lab_path": str(lab.resolve()),
                "textgrid_path": str(textgrid.resolve()),
                "decision": "pending",
                "notes": "",
            }
        )

    with atomic_text_writer(
        output_csv.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "status": "pending_researcher_review",
        "created_at": now_iso(),
        "year": year,
        "input_contract_id": input_id,
        "alignment_contract_id": alignment_id,
        "database": str(db_path.resolve()),
        "sample_report": file_fingerprint(sample_report.resolve(), with_sha256=True),
        "sample_csv": sample_fp,
        "alignment_contract": file_fingerprint(
            alignment_contract.resolve(), with_sha256=True
        ),
        "review_csv_template": file_fingerprint(
            output_csv.resolve(), with_sha256=True
        ),
        "row_identities": [
            {key: row[key] for key in IDENTITY_FIELDS} for row in rows
        ],
        "counts": {
            "rows": len(rows),
            "sessions": len({row["session"] for row in rows}),
            "speakers_nonempty": len(
                {row["speaker_id"] for row in rows if row["speaker_id"]}
            ),
        },
        "realization_judgment_requested": False,
        "automatic_approval_performed": False,
    }
    atomic_write_json(output_manifest.resolve(), manifest)
    return manifest


def approve(
    *,
    review_csv: Path,
    review_manifest: Path,
    approved_by: str,
    output: Path,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"existing approval is preserved: {output}")
    manifest = read_json(review_manifest)
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("status") != "pending_researcher_review"
        or manifest.get("automatic_approval_performed") is not False
    ):
        raise RuntimeError("review manifest is not a valid pending template")
    rows = read_csv(review_csv)
    expected = manifest.get("row_identities") or []
    actual = [{key: row[key] for key in IDENTITY_FIELDS} for row in rows]
    if actual != expected:
        raise RuntimeError("review identity/path columns changed")
    if len(rows) < 5 or len({row["session"] for row in rows}) < 5:
        raise RuntimeError("at least five sessions must be reviewed")
    pending = [
        row["utt_id"] for row in rows if row["decision"].strip().lower() != "approved"
    ]
    if pending:
        raise RuntimeError(f"unapproved review rows remain: {pending[:10]}")
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "status": "approved",
        "approved_at": now_iso(),
        "approved_by": approved_by,
        "year": str(manifest["year"]),
        "allow_next_year_mfa": True,
        "realization_judgment_performed": False,
        "automatic_approval_performed": False,
        "counts": {
            "rows": len(rows),
            "sessions": len({row["session"] for row in rows}),
            "speakers_nonempty": len(
                {row["speaker_id"] for row in rows if row["speaker_id"]}
            ),
        },
        "year_contract": {
            "year": str(manifest["year"]),
            "alignment_contract_id": str(manifest["alignment_contract_id"]),
            "lab_input_contract_id": str(manifest["input_contract_id"]),
            "database": str(manifest["database"]),
        },
        "review_csv": file_fingerprint(review_csv.resolve(), with_sha256=True),
        "review_manifest": file_fingerprint(
            review_manifest.resolve(), with_sha256=True
        ),
    }
    atomic_write_json(output.resolve(), report)
    return report


def _preserve_exact_pending_csv(
    *,
    review_csv: Path,
    pending_archive: Path,
    expected_sha256: str,
) -> dict[str, Any]:
    """Preserve the untouched pending template once, byte for byte."""

    pending_archive = pending_archive.resolve()
    if pending_archive.exists():
        archived = file_fingerprint(pending_archive, with_sha256=True)
        if archived["sha256"] != expected_sha256:
            raise RuntimeError("pending review archive differs from manifest template")
        return archived

    current = file_fingerprint(review_csv.resolve(), with_sha256=True)
    if current["sha256"] != expected_sha256:
        raise RuntimeError(
            "review CSV changed before the original pending template was archived"
        )
    pending_archive.parent.mkdir(parents=True, exist_ok=True)
    partial = pending_archive.with_name(f".{pending_archive.name}.partial")
    if partial.exists():
        raise FileExistsError(f"stale pending archive partial is preserved: {partial}")
    partial.write_bytes(review_csv.read_bytes())
    if sha256_file(partial) != expected_sha256:
        raise RuntimeError("pending review archive copy SHA mismatch")
    promote_staged(partial, pending_archive)
    return file_fingerprint(pending_archive, with_sha256=True)


def approve_explicit(
    *,
    review_csv: Path,
    review_manifest: Path,
    approved_by: str,
    approval_statement: str,
    expected_row_count: int,
    pending_archive: Path,
    decision_record: Path,
    output: Path,
    row_note: str,
) -> dict[str, Any]:
    """Materialize an explicit researcher decision without manual CSV editing.

    This command does not infer approval.  It requires a non-empty statement,
    exact expected row count, and the unchanged identity/path contract.  The
    original pending CSV is preserved before any decision cell is changed.
    """

    approved_by = approved_by.strip()
    approval_statement = approval_statement.strip()
    row_note = row_note.strip()
    if not approved_by or not approval_statement:
        raise RuntimeError("approved_by and approval_statement are required")
    if expected_row_count < 5:
        raise RuntimeError("expected_row_count must be at least five")

    manifest = read_json(review_manifest)
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("status") != "pending_researcher_review"
        or manifest.get("automatic_approval_performed") is not False
    ):
        raise RuntimeError("review manifest is not a valid pending template")
    template = manifest.get("review_csv_template") or {}
    template_sha = str(template.get("sha256") or "")
    if not template_sha:
        raise RuntimeError("review manifest lacks the pending CSV SHA")

    pending_fp = _preserve_exact_pending_csv(
        review_csv=review_csv,
        pending_archive=pending_archive,
        expected_sha256=template_sha,
    )
    rows = read_csv(review_csv)
    expected_identities = manifest.get("row_identities") or []
    actual_identities = [
        {key: row[key] for key in IDENTITY_FIELDS} for row in rows
    ]
    if actual_identities != expected_identities:
        raise RuntimeError("review identity/path columns changed")
    if len(rows) != expected_row_count:
        raise RuntimeError(
            "explicit approval row count differs: "
            f"actual={len(rows)} expected={expected_row_count}"
        )
    invalid = [
        row["utt_id"]
        for row in rows
        if row["decision"].strip().lower() not in {"pending", "approved"}
    ]
    if invalid:
        raise RuntimeError(
            f"non-pending/non-approved decisions cannot be overwritten: {invalid[:10]}"
        )

    if any(row["decision"].strip().lower() != "approved" for row in rows):
        for row in rows:
            row["decision"] = "approved"
            if row_note and not row["notes"].strip():
                row["notes"] = row_note
        with atomic_text_writer(
            review_csv.resolve(), encoding="utf-8-sig", newline=""
        ) as (stream, _temp):
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    approved_rows = read_csv(review_csv)
    if [
        {key: row[key] for key in IDENTITY_FIELDS} for row in approved_rows
    ] != expected_identities:
        raise RuntimeError("approved CSV identity verification failed")
    if any(row["decision"].strip().lower() != "approved" for row in approved_rows):
        raise RuntimeError("approved CSV still contains a non-approved row")
    approved_fp = file_fingerprint(review_csv.resolve(), with_sha256=True)

    decision_payload: dict[str, Any] = {
        "schema_version": "mfa_production_year_explicit_decision.v1",
        "status": "approved",
        "approved_at": now_iso(),
        "approved_by": approved_by,
        "approval_statement": approval_statement,
        "year": str(manifest["year"]),
        "expected_row_count": expected_row_count,
        "reviewed_utt_ids": [row["utt_id"] for row in approved_rows],
        "pending_review_archive": pending_fp,
        "approved_review_csv": approved_fp,
        "materialized_from_explicit_researcher_statement": True,
        "automatic_approval_performed": False,
        "realization_judgment_performed": False,
    }
    decision_record = decision_record.resolve()
    if decision_record.exists():
        existing_decision = read_json(decision_record)
        stable_keys = (
            "approved_by",
            "approval_statement",
            "year",
            "expected_row_count",
            "reviewed_utt_ids",
        )
        if any(
            existing_decision.get(key) != decision_payload.get(key)
            for key in stable_keys
        ):
            raise RuntimeError("existing explicit decision record differs")
        if (
            (existing_decision.get("approved_review_csv") or {}).get("sha256")
            != approved_fp["sha256"]
        ):
            raise RuntimeError("existing explicit decision CSV SHA differs")
    else:
        atomic_write_json(decision_record, decision_payload)

    if output.exists():
        validation = validate(report_path=output, review_csv=review_csv)
        report = validation["report"]
        if (
            validation["status"] != "passed"
            or report.get("approved_by") != approved_by
        ):
            raise RuntimeError("existing approval report differs or is invalid")
    else:
        report = approve(
            review_csv=review_csv,
            review_manifest=review_manifest,
            approved_by=approved_by,
            output=output,
        )
    report["explicit_researcher_decision"] = file_fingerprint(
        decision_record, with_sha256=True
    )
    report["materialized_from_explicit_researcher_statement"] = True
    atomic_write_json(output.resolve(), report)
    return report


def validate(*, report_path: Path, review_csv: Path) -> dict[str, Any]:
    report = read_json(report_path)
    current = file_fingerprint(review_csv.resolve(), with_sha256=True)
    valid = (
        report.get("schema_version") == REPORT_SCHEMA
        and report.get("status") == "approved"
        and report.get("allow_next_year_mfa") is True
        and report.get("realization_judgment_performed") is False
        and report.get("automatic_approval_performed") is False
        and (report.get("review_csv") or {}).get("sha256") == current["sha256"]
        and int((report.get("counts") or {}).get("sessions") or 0) >= 5
    )
    return {"status": "passed" if valid else "failed", "report": report}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--year", required=True)
    prep.add_argument("--sample-csv", type=Path, required=True)
    prep.add_argument("--sample-report", type=Path, required=True)
    prep.add_argument("--align-marker", type=Path, required=True)
    prep.add_argument("--alignment-contract", type=Path, required=True)
    prep.add_argument("--search-master-root", type=Path, required=True)
    prep.add_argument("--wav-root", type=Path, required=True)
    prep.add_argument("--output-csv", type=Path, required=True)
    prep.add_argument("--output-manifest", type=Path, required=True)
    accept = sub.add_parser("approve")
    accept.add_argument("--review-csv", type=Path, required=True)
    accept.add_argument("--review-manifest", type=Path, required=True)
    accept.add_argument("--approved-by", required=True)
    accept.add_argument("--output", type=Path, required=True)
    explicit = sub.add_parser("approve-explicit")
    explicit.add_argument("--review-csv", type=Path, required=True)
    explicit.add_argument("--review-manifest", type=Path, required=True)
    explicit.add_argument("--approved-by", required=True)
    explicit.add_argument("--approval-statement", required=True)
    explicit.add_argument("--expected-row-count", type=int, required=True)
    explicit.add_argument("--pending-archive", type=Path, required=True)
    explicit.add_argument("--decision-record", type=Path, required=True)
    explicit.add_argument("--row-note", default="")
    explicit.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("validate")
    check.add_argument("--report", type=Path, required=True)
    check.add_argument("--review-csv", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(
                year=args.year,
                sample_csv=args.sample_csv,
                sample_report=args.sample_report,
                align_marker=args.align_marker,
                alignment_contract=args.alignment_contract,
                search_master_root=args.search_master_root,
                wav_root=args.wav_root,
                output_csv=args.output_csv,
                output_manifest=args.output_manifest,
            )
        elif args.command == "approve":
            result = approve(
                review_csv=args.review_csv,
                review_manifest=args.review_manifest,
                approved_by=args.approved_by,
                output=args.output,
            )
        elif args.command == "approve-explicit":
            result = approve_explicit(
                review_csv=args.review_csv,
                review_manifest=args.review_manifest,
                approved_by=args.approved_by,
                approval_statement=args.approval_statement,
                expected_row_count=args.expected_row_count,
                pending_archive=args.pending_archive,
                decision_record=args.decision_record,
                output=args.output,
                row_note=args.row_note,
            )
        else:
            result = validate(report_path=args.report, review_csv=args.review_csv)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in {
            "pending_researcher_review",
            "approved",
            "passed",
        } else 1
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
