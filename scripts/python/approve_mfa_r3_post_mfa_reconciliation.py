"""Materialize an explicit researcher approval for an r3 post-MFA queue.

The pending queue is immutable evidence.  This command creates a separate
approved CSV and an input-contract-bound exclusion contract only after an
explicit statement names the frozen year, count, scope, and candidate digest.
It never modifies the retained MFA database, WAV/LAB inputs, or TextGrids.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Mapping

from mfa_exclusion_contract import REVIEW_FIELDS, build_contract, load_contract
from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
)


SCHEMA_VERSION = "mfa_r3_post_mfa_explicit_approval.v1"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _fingerprint_matches(record: Mapping[str, object], path: Path) -> bool:
    return (
        path.is_file()
        and int(record.get("bytes", -1)) == path.stat().st_size
        and str(record.get("sha256", "")).lower()
        == sha256_file(path).lower()
    )


def _read_pending_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if list(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise RuntimeError("r3 post-MFA pending CSV schema differs")
        for line_number, raw in enumerate(reader, 2):
            row = {
                key: str(raw.get(key, "") or "").strip()
                for key in REVIEW_FIELDS
            }
            if not row["utt_id"] or row["utt_id"] in seen:
                raise RuntimeError(
                    f"pending CSV empty/duplicate ID at {line_number}"
                )
            if (
                row["decision"] != "pending"
                or row["exclusion_scope"] != "alignment_and_analysis"
                or row["reason_code"]
                not in {
                    "mfa_alignment_missing",
                    "mfa_feature_generation_failed",
                }
            ):
                raise RuntimeError(
                    f"pending CSV identity/scope differs at {line_number}"
                )
            seen.add(row["utt_id"])
            rows.append(row)
    return rows


def _candidate_identity(rows: list[dict[str, str]]) -> str:
    payload = "\n".join(
        "|".join(
            [
                row["year"],
                row["input_contract_id"],
                row["utt_id"],
                row["reason_code"],
                row["exclusion_scope"],
            ]
        )
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_existing(
    *,
    manifest_path: Path,
    approved_csv: Path,
    contract_path: Path,
    year: str,
    input_contract_id: str,
    candidate_identity: str,
    approved_by: str,
    approval_statement: str,
) -> dict[str, object]:
    manifest = _read_json(manifest_path)
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "approved"
        or str(manifest.get("year")) != year
        or manifest.get("input_contract_id") != input_contract_id
        or manifest.get("candidate_identity_sha256") != candidate_identity
        or manifest.get("approved_by") != approved_by
        or manifest.get("approval_statement") != approval_statement
        or manifest.get("automatic_approval_performed") is not False
    ):
        raise RuntimeError("existing r3 approval manifest identity differs")
    for label, path in (
        ("approved_review_csv", approved_csv),
        ("approved_exclusions_contract", contract_path),
    ):
        record = manifest.get(label)
        if not isinstance(record, Mapping) or not _fingerprint_matches(
            record, path
        ):
            raise RuntimeError(f"existing r3 approval {label} differs")
    load_contract(
        contract_path, year=year, input_contract_id=input_contract_id
    )
    return manifest


def approve(
    *,
    review_root: Path,
    approved_by: str,
    approved_at: str,
    approval_statement: str,
) -> dict[str, object]:
    review_root = review_root.resolve()
    summary_path = review_root / "03_REVIEW_SUMMARY.json"
    pending_csv = review_root / "02_RESEARCHER_DECISIONS.csv"
    approved_csv = review_root / "04_RESEARCHER_APPROVED.csv"
    contract_path = review_root / "05_APPROVED_EXCLUSIONS.json"
    manifest_path = review_root / "06_RESEARCHER_APPROVAL.json"
    approved_by = approved_by.strip()
    approved_at = approved_at.strip()
    approval_statement = approval_statement.strip()
    if not approved_by or not approved_at or not approval_statement:
        raise RuntimeError("approved_by/approved_at/statement cannot be blank")
    if not summary_path.is_file() or not pending_csv.is_file():
        raise FileNotFoundError("r3 post-MFA review summary or pending CSV")

    summary = _read_json(summary_path)
    if (
        summary.get("schema_version")
        != "mfa_r3_post_mfa_reconciliation_review.v1"
        or summary.get("status") != "pending_researcher_approval"
        or summary.get("policy", {}).get("automatic_approval_performed")
        is not False
    ):
        raise RuntimeError("r3 post-MFA review status/policy differs")
    year = str(summary.get("year", "")).strip()
    input_contract_id = str(summary.get("input_contract_id", "")).strip()
    candidate_identity = str(
        summary.get("candidate_identity_sha256", "")
    ).strip()
    count = int(summary.get("counts", {}).get("post_mfa_candidates", -1))
    pending_record = summary.get("outputs", {}).get("researcher_decisions")
    if (
        not year
        or not input_contract_id
        or len(candidate_identity) != 64
        or count < 0
        or not isinstance(pending_record, Mapping)
        or not _fingerprint_matches(pending_record, pending_csv)
    ):
        raise RuntimeError("r3 post-MFA frozen review identity differs")

    rows = _read_pending_rows(pending_csv)
    if (
        len(rows) != count
        or any(row["year"] != year for row in rows)
        or any(
            row["input_contract_id"] != input_contract_id for row in rows
        )
        or _candidate_identity(rows) != candidate_identity
    ):
        raise RuntimeError("r3 post-MFA pending rows/candidate digest differ")

    required_terms = (
        year,
        str(count),
        "alignment_and_analysis",
        candidate_identity[:12],
        approved_by,
    )
    missing_terms = [term for term in required_terms if term not in approval_statement]
    if missing_terms:
        raise RuntimeError(
            "explicit approval statement missing frozen identity terms: "
            + ", ".join(missing_terms)
        )

    if manifest_path.exists():
        return _validate_existing(
            manifest_path=manifest_path,
            approved_csv=approved_csv,
            contract_path=contract_path,
            year=year,
            input_contract_id=input_contract_id,
            candidate_identity=candidate_identity,
            approved_by=approved_by,
            approval_statement=approval_statement,
        )
    if approved_csv.exists() or contract_path.exists():
        raise RuntimeError(
            "partial approval outputs exist without final manifest; inspect first"
        )

    with atomic_text_writer(
        approved_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=REVIEW_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "decision": "approved"})
    contract = build_contract(
        review_csv=approved_csv,
        output=contract_path,
        year=year,
        input_contract_id=input_contract_id,
        approved_by=approved_by,
        approved_at=approved_at,
    )
    load_contract(
        contract_path, year=year, input_contract_id=input_contract_id
    )
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "approved",
        "recorded_at": now_iso(),
        "year": year,
        "input_contract_id": input_contract_id,
        "candidate_identity_sha256": candidate_identity,
        "approved_row_count": count,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "approval_statement": approval_statement,
        "approval_statement_sha256": hashlib.sha256(
            approval_statement.encode("utf-8")
        ).hexdigest(),
        "source_review_summary": file_fingerprint(
            summary_path, with_sha256=True
        ),
        "source_pending_csv": file_fingerprint(
            pending_csv, with_sha256=True
        ),
        "approved_review_csv": file_fingerprint(
            approved_csv, with_sha256=True
        ),
        "approved_exclusions_contract": file_fingerprint(
            contract_path, with_sha256=True
        ),
        "contract_row_count": contract.get("row_count"),
        "automatic_approval_performed": False,
        "source_or_mfa_database_modified": False,
        "successful_alignments_preserved": True,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-root", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approved-at", default=datetime.now().astimezone().isoformat())
    parser.add_argument("--approval-statement", required=True)
    args = parser.parse_args()
    report = approve(
        review_root=args.review_root,
        approved_by=args.approved_by,
        approved_at=args.approved_at,
        approval_statement=args.approval_statement,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
