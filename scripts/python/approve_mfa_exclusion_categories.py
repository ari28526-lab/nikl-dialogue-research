"""Record explicit researcher approval of every observed exclusion category.

The pending candidate CSV remains immutable.  This script creates a separate
approved CSV, an input-contract-bound exclusion contract, and an approval
record.  It never starts MFA or changes WAV/LAB data.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from mfa_exclusion_contract import (
    ALLOWED_REASON_CODES,
    REVIEW_FIELDS,
    build_contract,
)
from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    sha256_file,
)

SCHEMA_VERSION = "mfa_exclusion_category_approval.v1"


def approve_categories(
    *,
    candidate_csv: Path,
    candidate_manifest: Path,
    output_approved_csv: Path,
    output_approval_record: Path,
    output_contract: Path,
    approved_reason_codes: set[str],
    approved_by: str,
    approval_statement: str,
    approved_at: str | None = None,
) -> dict[str, object]:
    candidate_csv = candidate_csv.resolve()
    candidate_manifest = candidate_manifest.resolve()
    output_approved_csv = output_approved_csv.resolve()
    output_approval_record = output_approval_record.resolve()
    output_contract = output_contract.resolve()
    for output in (
        output_approved_csv,
        output_approval_record,
        output_contract,
    ):
        if output.exists():
            raise RuntimeError(f"approval output already exists: {output}")
    approved_by = approved_by.strip()
    approval_statement = approval_statement.strip()
    if not approved_by or not approval_statement:
        raise RuntimeError("approved_by and approval_statement are required")
    approved_reason_codes = {
        str(value).strip() for value in approved_reason_codes if str(value).strip()
    }
    if not approved_reason_codes:
        raise RuntimeError("at least one explicitly approved reason code is required")
    unknown_reasons = approved_reason_codes - ALLOWED_REASON_CODES
    if unknown_reasons:
        raise RuntimeError(
            f"unknown approved reason codes: {sorted(unknown_reasons)}"
        )

    manifest = json.loads(
        candidate_manifest.read_text(encoding="utf-8-sig")
    )
    if (
        manifest.get("schema_version")
        != "mfa_exclusion_review_candidates.v1"
        or manifest.get("status") != "pending_researcher_review"
        or bool(manifest.get("automatic_approval_performed"))
    ):
        raise RuntimeError("candidate manifest identity/status mismatch")
    year = str(manifest.get("year") or "").strip()
    input_contract_id = str(
        manifest.get("input_contract_id") or ""
    ).strip()
    if not year or not input_contract_id:
        raise RuntimeError("candidate manifest year/input_contract_id missing")
    csv_fingerprint = manifest.get("review_csv")
    if not isinstance(csv_fingerprint, dict):
        raise RuntimeError("candidate manifest review_csv fingerprint missing")
    manifest_csv_path = Path(str(csv_fingerprint.get("path") or "")).resolve()
    if manifest_csv_path != candidate_csv:
        raise RuntimeError("candidate CSV path differs from manifest")
    if sha256_file(candidate_csv) != str(csv_fingerprint.get("sha256") or ""):
        raise RuntimeError("candidate CSV SHA256 differs from manifest")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with candidate_csv.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if list(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise RuntimeError("candidate CSV schema mismatch")
        for line_number, raw in enumerate(reader, 2):
            row = {
                field: str(raw.get(field, "") or "").strip()
                for field in REVIEW_FIELDS
            }
            if row["year"] != year:
                raise RuntimeError(f"candidate year mismatch: line={line_number}")
            if row["input_contract_id"] != input_contract_id:
                raise RuntimeError(
                    f"candidate input_contract_id mismatch: line={line_number}"
                )
            if not row["utt_id"] or row["utt_id"] in seen:
                raise RuntimeError(
                    f"candidate blank/duplicate utt_id: line={line_number}"
                )
            if row["decision"] != "pending":
                raise RuntimeError(
                    f"candidate is not immutable pending snapshot: line={line_number}"
                )
            seen.add(row["utt_id"])
            rows.append(row)
    if len(rows) != int(manifest.get("candidate_count", -1)):
        raise RuntimeError("candidate row count differs from manifest")
    reason_counts = Counter(row["reason_code"] for row in rows)
    observed_reasons = set(reason_counts)
    if approved_reason_codes != observed_reasons:
        raise RuntimeError(
            "explicit category approval must equal observed categories: "
            f"approved={sorted(approved_reason_codes)}, "
            f"observed={sorted(observed_reasons)}"
        )

    approved_rows = []
    for row in rows:
        approved_row = dict(row)
        approved_row["decision"] = "approved"
        approved_rows.append(approved_row)
    with atomic_text_writer(
        output_approved_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(
            stream, fieldnames=REVIEW_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(approved_rows)

    timestamp = (
        approved_at.strip()
        if approved_at and approved_at.strip()
        else datetime.now().astimezone().isoformat()
    )
    contract = build_contract(
        review_csv=output_approved_csv,
        output=output_contract,
        year=year,
        input_contract_id=input_contract_id,
        approved_by=approved_by,
        approved_at=timestamp,
    )
    record: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "approved",
        "year": year,
        "input_contract_id": input_contract_id,
        "approved_by": approved_by,
        "approved_at": timestamp,
        "approval_statement": approval_statement,
        "approved_categories": {
            reason: reason_counts[reason] for reason in sorted(reason_counts)
        },
        "approved_row_count": len(approved_rows),
        "candidate_manifest": file_fingerprint(
            candidate_manifest, with_sha256=True
        ),
        "pending_candidate_csv": file_fingerprint(
            candidate_csv, with_sha256=True
        ),
        "approved_csv": file_fingerprint(
            output_approved_csv, with_sha256=True
        ),
        "approved_exclusions_contract": file_fingerprint(
            output_contract, with_sha256=True
        ),
        "contract_row_count": int(contract["row_count"]),
        "policy": {
            "explicit_researcher_category_approval": True,
            "pending_candidate_snapshot_unchanged": True,
            "automatic_approval": False,
            "starts_mfa": False,
            "changes_wav_or_lab": False,
        },
    }
    atomic_write_json(output_approval_record, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output-approved-csv", type=Path, required=True)
    parser.add_argument("--output-approval-record", type=Path, required=True)
    parser.add_argument("--output-contract", type=Path, required=True)
    parser.add_argument(
        "--approve-reason-code", action="append", required=True
    )
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approval-statement", required=True)
    parser.add_argument("--approved-at")
    args = parser.parse_args()
    result = approve_categories(
        candidate_csv=args.candidate_csv,
        candidate_manifest=args.candidate_manifest,
        output_approved_csv=args.output_approved_csv,
        output_approval_record=args.output_approval_record,
        output_contract=args.output_contract,
        approved_reason_codes=set(args.approve_reason_code),
        approved_by=args.approved_by,
        approval_statement=args.approval_statement,
        approved_at=args.approved_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
