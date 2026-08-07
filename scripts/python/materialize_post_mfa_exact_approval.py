"""Materialize an explicit post-MFA exact-ID approval safely.

The researcher approves a frozen exact-ID set in chat rather than manually
editing hundreds of CSV rows.  This tool verifies the pending review identity,
archives the byte-exact pending working copy, changes only ``decision`` to
``approved``, and records the explicit statement.  It never modifies WAV, LAB,
MFA DB, TextGrid, or the immutable ``02_RESEARCHER_DECISIONS.csv`` template.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import uuid
from pathlib import Path

from finalize_post_mfa_exact_reconciliation_exclusions import (
    candidate_identity_sha256,
    read_review_csv,
)
from mfa_exclusion_contract import REVIEW_FIELDS
from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    promote_staged,
    sha256_file,
)


SCHEMA_VERSION = "mfa_post_exact_explicit_approval.v1"


def _recorded_path(record: object, label: str) -> Path:
    if not isinstance(record, dict) or not record.get("path"):
        raise RuntimeError(f"SUMMARY {label} fingerprint 누락")
    return Path(str(record["path"])).resolve()


def _verify_recorded_file(
    *, record: object, actual: Path, label: str
) -> dict[str, object]:
    if not isinstance(record, dict):
        raise RuntimeError(f"SUMMARY {label} fingerprint 누락")
    actual = actual.resolve()
    if _recorded_path(record, label) != actual or not actual.is_file():
        raise RuntimeError(f"SUMMARY {label} 경로 불일치: {actual}")
    expected_sha = str(record.get("sha256") or "")
    if not expected_sha or sha256_file(actual) != expected_sha:
        raise RuntimeError(f"SUMMARY {label} SHA256 불일치")
    return file_fingerprint(actual, with_sha256=True)


def _preserve_pending_copy(
    *, source: Path, destination: Path, expected_sha256: str
) -> dict[str, object]:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != expected_sha256:
            raise RuntimeError("기존 pending archive SHA256 불일치")
        return file_fingerprint(destination, with_sha256=True)
    temp = destination.with_name(
        f".{destination.name}.{uuid.uuid4().hex}.partial"
    )
    try:
        shutil.copyfile(source, temp)
        with temp.open("r+b") as stream:
            os.fsync(stream.fileno())
        if sha256_file(temp) != expected_sha256:
            raise RuntimeError("pending archive copy SHA256 불일치")
        promote_staged(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    return file_fingerprint(destination, with_sha256=True)


def _validate_existing(
    *,
    manifest_path: Path,
    approval_csv: Path,
    approved_by: str,
    approval_statement: str,
    approval_token: str,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "approved"
        or manifest.get("approved_by") != approved_by
        or manifest.get("approval_statement") != approval_statement
        or manifest.get("approval_token") != approval_token
        or manifest.get("automatic_approval_performed") is not False
    ):
        raise RuntimeError("기존 explicit approval manifest identity 불일치")
    approved = manifest.get("approved_review_csv")
    if (
        not isinstance(approved, dict)
        or str(approved.get("sha256") or "") != sha256_file(approval_csv)
    ):
        raise RuntimeError("기존 approved CSV SHA256 불일치")
    rows = read_review_csv(approval_csv)
    if not rows or any(row["decision"] != "approved" for row in rows):
        raise RuntimeError("기존 approved CSV에 미승인 행 존재")
    return manifest


def materialize(
    *,
    review_root: Path,
    approved_by: str,
    approval_statement: str,
    expected_row_count: int,
    approval_token: str,
) -> dict[str, object]:
    review_root = review_root.resolve()
    approved_by = approved_by.strip()
    approval_statement = approval_statement.strip()
    approval_token = approval_token.strip()
    summary_path = review_root / "SUMMARY.json"
    immutable_csv = review_root / "02_RESEARCHER_DECISIONS.csv"
    approval_csv = review_root / "04_RESEARCHER_APPROVAL.csv"
    manifest_path = review_root / "04_RESEARCHER_APPROVAL_MANIFEST.json"
    archive_path = (
        review_root
        / "archive"
        / "04_RESEARCHER_APPROVAL.pending_original.csv"
    )
    for path in (summary_path, immutable_csv, approval_csv):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not approved_by or not approval_statement or not approval_token:
        raise RuntimeError("승인자·승인 문장·승인 token은 필수")
    if manifest_path.exists():
        return _validate_existing(
            manifest_path=manifest_path,
            approval_csv=approval_csv,
            approved_by=approved_by,
            approval_statement=approval_statement,
            approval_token=approval_token,
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    if (
        summary.get("schema_version") != "mfa_post_alignment_review.v2"
        or summary.get("status") != "pending_researcher_review"
        or summary.get("auto_approval_performed") is not False
        or summary.get("mfa_database_modified") is not False
    ):
        raise RuntimeError("pending post-MFA SUMMARY identity/status 불일치")
    year = str(summary.get("year") or "")
    count = int(summary.get("candidate_count", -1))
    expected_token = str(summary.get("required_approval_token") or "")
    if count != expected_row_count or approval_token != expected_token:
        raise RuntimeError("승인 행 수 또는 token 불일치")
    for required in (year, str(count), "alignment_and_analysis", approved_by):
        if required not in approval_statement:
            raise RuntimeError(f"승인 문장 필수 범위 누락: {required}")

    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict):
        raise RuntimeError("SUMMARY artifacts 누락")
    immutable_fp = _verify_recorded_file(
        record=artifacts.get("decisions"),
        actual=immutable_csv,
        label="decisions",
    )
    pending_fp = _verify_recorded_file(
        record=artifacts.get("approval_working_copy"),
        actual=approval_csv,
        label="approval_working_copy",
    )
    rows = read_review_csv(approval_csv)
    if len(rows) != count:
        raise RuntimeError("approval working copy 행 수 불일치")
    if any(
        row["year"] != year
        or row["input_contract_id"]
        != str(summary.get("input_contract_id") or "")
        or row["reason_code"] != "mfa_alignment_missing"
        or row["exclusion_scope"] != "alignment_and_analysis"
        or row["decision"] != "pending"
        for row in rows
    ):
        raise RuntimeError("approval working copy identity/scope/pending 불일치")
    if candidate_identity_sha256(rows) != str(
        summary.get("candidate_identity_sha256") or ""
    ):
        raise RuntimeError("approval working copy candidate identity 불일치")

    archive_fp = _preserve_pending_copy(
        source=approval_csv,
        destination=archive_path,
        expected_sha256=str(pending_fp["sha256"]),
    )
    for row in rows:
        row["decision"] = "approved"
    with atomic_text_writer(
        approval_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    approved_rows = read_review_csv(approval_csv)
    if len(approved_rows) != count or any(
        row["decision"] != "approved" for row in approved_rows
    ):
        raise RuntimeError("승인 CSV materialization 검증 실패")
    if candidate_identity_sha256(approved_rows) != str(
        summary.get("candidate_identity_sha256") or ""
    ):
        raise RuntimeError("승인 뒤 candidate identity 변경")
    approved_fp = file_fingerprint(approval_csv, with_sha256=True)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "approved",
        "approved_at": now_iso(),
        "approved_by": approved_by,
        "approval_statement": approval_statement,
        "approval_token": approval_token,
        "year": year,
        "input_contract_id": summary.get("input_contract_id"),
        "approved_row_count": count,
        "reason_code": "mfa_alignment_missing",
        "exclusion_scope": "alignment_and_analysis",
        "candidate_identity_sha256": summary.get("candidate_identity_sha256"),
        "immutable_pending_decisions": immutable_fp,
        "pending_working_copy": pending_fp,
        "pending_working_copy_archive": archive_fp,
        "approved_review_csv": approved_fp,
        "materialized_from_explicit_researcher_statement": True,
        "automatic_approval_performed": False,
        "actual_phonological_realization_judged": False,
        "source_audio_modified": False,
        "mfa_database_modified": False,
        "full_year_mfa_rerun_required": False,
        "recovery_inputs_preserved": True,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-root", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approval-statement", required=True)
    parser.add_argument("--expected-row-count", type=int, required=True)
    parser.add_argument("--approval-token", required=True)
    args = parser.parse_args()
    result = materialize(
        review_root=args.review_root,
        approved_by=args.approved_by,
        approval_statement=args.approval_statement,
        expected_row_count=args.expected_row_count,
        approval_token=args.approval_token,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
