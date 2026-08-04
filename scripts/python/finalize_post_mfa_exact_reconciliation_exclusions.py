"""Finalize explicitly reviewed post-MFA exact-reconciliation exclusions.

This generic 2021--2025 path is deliberately separate from the frozen 2020
audio-listening finalizer.  It never approves candidates automatically and it
never edits the retained MFA database.  Candidate identity is bound to the
prepare-review summary, export failure inventory, database state, and an
explicit researcher token.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

from mfa_exclusion_contract import REVIEW_FIELDS, build_contract, load_contract
from pipeline_common import atomic_write_json, file_fingerprint, sha256_file
from prepare_post_mfa_alignment_review import candidate_identity_sha256


SCHEMA_VERSION = "mfa_post_exact_finalization.v1"
POST_MFA_REASON_CODES = {
    "mfa_alignment_missing",
    "mfa_feature_generation_failed",
}


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if list(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise RuntimeError("post-MFA 결정표 schema 불일치")
        return [
            {key: str(row.get(key, "") or "").strip() for key in REVIEW_FIELDS}
            for row in reader
        ]


def verify_recorded_artifact(
    *,
    label: str,
    recorded: object,
    actual_path: Path,
    require_sha256: bool,
) -> None:
    if not isinstance(recorded, dict):
        raise RuntimeError(f"review summary artifact 누락: {label}")
    actual_path = actual_path.resolve()
    if Path(str(recorded.get("path") or "")).resolve() != actual_path:
        raise RuntimeError(f"review summary artifact 경로 불일치: {label}")
    stat = actual_path.stat()
    if int(recorded.get("bytes", -1)) != stat.st_size:
        raise RuntimeError(f"review summary artifact 크기 불일치: {label}")
    if int(recorded.get("mtime_ns", -1)) != stat.st_mtime_ns:
        raise RuntimeError(f"review summary artifact 수정시각 불일치: {label}")
    if require_sha256:
        expected = str(recorded.get("sha256") or "")
        if not expected or sha256_file(actual_path) != expected:
            raise RuntimeError(f"review summary artifact SHA256 불일치: {label}")


def write_csv_atomic(
    path: Path, fields: list[str], rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    try:
        with partial.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=fields, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def db_post_mfa_reasons(
    db_path: Path, candidate_ids: set[str]
) -> dict[str, str]:
    connection = sqlite3.connect(
        f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True, timeout=120
    )
    connection.execute("PRAGMA query_only=ON")
    reasons: dict[str, str] = {}
    try:
        rows = connection.execute(
            """
            SELECT f.name, u.ignored, u.num_frames,
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
            """
        )
        for utt_id_raw, ignored, num_frames, has_word, has_phone in rows:
            utt_id = str(utt_id_raw)
            if utt_id not in candidate_ids:
                continue
            if bool(ignored):
                if num_frames is not None:
                    raise RuntimeError(
                        f"ignored 후보에 num_frames가 존재함: {utt_id}"
                    )
                reasons[utt_id] = "mfa_feature_generation_failed"
            elif not (bool(has_word) and bool(has_phone)):
                reasons[utt_id] = "mfa_alignment_missing"
            else:
                raise RuntimeError(
                    f"post-MFA 후보가 DB에서는 이미 정렬됨: {utt_id}"
                )
    finally:
        connection.close()
    absent = candidate_ids - set(reasons)
    if absent:
        raise RuntimeError(
            "post-MFA 후보가 보존 DB에서 분류되지 않음: "
            f"count={len(absent)} sample={sorted(absent)[:5]}"
        )
    return reasons


def export_unknown_ids(export_report: Path) -> set[str]:
    report = read_json(export_report)
    reconciliation = report.get("exact_id_reconciliation")
    if not isinstance(reconciliation, dict):
        raise RuntimeError("export exact_id_reconciliation 누락")
    inventories = reconciliation.get("inventories")
    if not isinstance(inventories, dict):
        raise RuntimeError("export reconciliation inventories 누락")
    return {
        str(value).strip()
        for value in inventories.get(
            "unknown_active_lab_without_alignment", []
        )
        if str(value).strip()
    }


def finalize(
    *,
    year: str,
    input_contract_id: str,
    db_path: Path,
    export_report: Path,
    pre_approved_contract: Path,
    review_summary: Path,
    researcher_decisions: Path,
    output_root: Path,
    approved_by: str,
    approved_at: str,
    approval_token: str,
    approval_statement: str,
    preflight_only: bool = False,
) -> dict[str, object]:
    if not approved_by.strip() or not approved_at.strip():
        raise RuntimeError("approved_by/approved_at은 필수")
    if not approval_statement.strip():
        raise RuntimeError("연구자 승인 문구는 필수")
    paths = [
        db_path.resolve(),
        export_report.resolve(),
        pre_approved_contract.resolve(),
        review_summary.resolve(),
        researcher_decisions.resolve(),
    ]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    db_path, export_report, pre_approved_contract, review_summary, researcher_decisions = paths
    output_root = output_root.resolve()

    summary = read_json(review_summary)
    if (
        summary.get("schema_version") != "mfa_post_alignment_review.v2"
        or summary.get("status") != "pending_researcher_review"
        or str(summary.get("year")) != year
        or str(summary.get("input_contract_id")) != input_contract_id
    ):
        raise RuntimeError("post-MFA review summary identity/status 불일치")
    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict):
        raise RuntimeError("post-MFA review summary artifacts 누락")
    verify_recorded_artifact(
        label="export_report",
        recorded=artifacts.get("export_report"),
        actual_path=export_report,
        require_sha256=True,
    )
    verify_recorded_artifact(
        label="database",
        recorded=artifacts.get("database"),
        actual_path=db_path,
        require_sha256=False,
    )
    verify_recorded_artifact(
        label="approved_exclusions_contract",
        recorded=artifacts.get("approved_exclusions_contract"),
        actual_path=pre_approved_contract,
        require_sha256=True,
    )
    original_decisions = Path(
        str(
            (artifacts.get("decisions") or {}).get("path")
            if isinstance(artifacts.get("decisions"), dict)
            else ""
        )
    )
    verify_recorded_artifact(
        label="decisions",
        recorded=artifacts.get("decisions"),
        actual_path=original_decisions,
        require_sha256=True,
    )

    post_rows = read_review_csv(researcher_decisions)
    if not post_rows:
        raise RuntimeError("post-MFA 결정표가 비어 있음")
    post_ids = {row["utt_id"] for row in post_rows}
    if "" in post_ids or len(post_ids) != len(post_rows):
        raise RuntimeError("post-MFA 결정표 빈/중복 utt_id")
    if any(
        row["year"] != year
        or row["input_contract_id"] != input_contract_id
        or row["exclusion_scope"] != "alignment_and_analysis"
        or row["reason_code"] not in POST_MFA_REASON_CODES
        or row["decision"] != "approved"
        for row in post_rows
    ):
        raise RuntimeError("post-MFA 결정표 identity/reason/scope/승인 불일치")

    candidate_identity = candidate_identity_sha256(post_rows)
    if candidate_identity != str(summary.get("candidate_identity_sha256") or ""):
        raise RuntimeError("post-MFA 후보 identity SHA 불일치")
    expected_token = str(summary.get("required_approval_token") or "")
    if not expected_token or approval_token != expected_token:
        raise RuntimeError("post-MFA 명시 승인 token 불일치")
    if len(post_rows) != int(summary.get("candidate_count", -1)):
        raise RuntimeError("post-MFA summary/candidate count 불일치")

    report_ids = export_unknown_ids(export_report)
    if post_ids != report_ids:
        raise RuntimeError(
            "post-MFA 결정표/export unknown ID 불일치: "
            f"decision={len(post_ids)} export={len(report_ids)}"
        )
    db_reasons = db_post_mfa_reasons(db_path, post_ids)
    row_reasons = {row["utt_id"]: row["reason_code"] for row in post_rows}
    if row_reasons != db_reasons:
        raise RuntimeError("post-MFA 결정표 reason과 보존 DB 분류 불일치")

    _, pre_rows_by_id = load_contract(
        pre_approved_contract,
        year=year,
        input_contract_id=input_contract_id,
    )
    overlap = post_ids & set(pre_rows_by_id)
    if overlap:
        raise RuntimeError(f"pre/post-MFA 제외 ID 중복: {len(overlap)}")
    combined_rows = [pre_rows_by_id[key] for key in sorted(pre_rows_by_id)]
    combined_rows.extend(sorted(post_rows, key=lambda row: row["utt_id"]))

    post_reason_counts = Counter(row["reason_code"] for row in post_rows)
    combined_reason_counts = Counter(row["reason_code"] for row in combined_rows)
    if preflight_only:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "validated_preflight",
            "year": year,
            "input_contract_id": input_contract_id,
            "candidate_identity_sha256": candidate_identity,
            "automatic_approval_performed": False,
            "mfa_database_modified": False,
            "output_created": False,
            "counts": {
                "pre_mfa_approved": len(pre_rows_by_id),
                "post_mfa_approved": len(post_rows),
                "combined_approved": len(combined_rows),
            },
            "post_mfa_reason_counts": dict(sorted(post_reason_counts.items())),
        }

    if output_root.exists():
        raise FileExistsError(f"기존 출력 보호: {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)
    try:
        review_csv = output_root / "03_RESEARCHER_REVIEW.csv"
        contract_path = output_root / "approved_exclusions.json"
        write_csv_atomic(review_csv, REVIEW_FIELDS, combined_rows)
        contract = build_contract(
            review_csv=review_csv,
            output=contract_path,
            year=year,
            input_contract_id=input_contract_id,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        manifest: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "status": "approved",
            "year": year,
            "input_contract_id": input_contract_id,
            "approved_by": approved_by,
            "approved_at": approved_at,
            "approval_token": approval_token,
            "approval_statement": approval_statement,
            "candidate_identity_sha256": candidate_identity,
            "automatic_approval_performed": False,
            "mfa_database_modified": False,
            "full_year_mfa_rerun_required": False,
            "resume_from_retained_db": True,
            "counts": {
                "pre_mfa_approved": len(pre_rows_by_id),
                "post_mfa_approved": len(post_rows),
                "combined_approved": len(combined_rows),
            },
            "post_mfa_reason_counts": dict(sorted(post_reason_counts.items())),
            "combined_reason_counts": dict(
                sorted(combined_reason_counts.items())
            ),
            "database": file_fingerprint(db_path, with_sha256=False),
            "export_report": file_fingerprint(
                export_report, with_sha256=True
            ),
            "pre_approved_contract": file_fingerprint(
                pre_approved_contract, with_sha256=True
            ),
            "review_summary": file_fingerprint(
                review_summary, with_sha256=True
            ),
            "researcher_decisions": file_fingerprint(
                researcher_decisions, with_sha256=True
            ),
            "combined_review_csv": file_fingerprint(
                review_csv, with_sha256=True
            ),
            "approved_exclusions_contract": file_fingerprint(
                contract_path, with_sha256=True
            ),
            "contract_row_count": contract["row_count"],
        }
        atomic_write_json(
            output_root / "03_RESEARCHER_REVIEW_MANIFEST.json", manifest
        )
    except Exception:
        for path in output_root.glob("*"):
            path.unlink(missing_ok=True)
        output_root.rmdir()
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--input-contract-id", required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--export-report", type=Path, required=True)
    parser.add_argument("--pre-approved-contract", type=Path, required=True)
    parser.add_argument("--review-summary", type=Path, required=True)
    parser.add_argument("--researcher-decisions", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approved-at", required=True)
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--approval-statement", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    result = finalize(
        year=args.year,
        input_contract_id=args.input_contract_id,
        db_path=args.db,
        export_report=args.export_report,
        pre_approved_contract=args.pre_approved_contract,
        review_summary=args.review_summary,
        researcher_decisions=args.researcher_decisions,
        output_root=args.output_root,
        approved_by=args.approved_by,
        approved_at=args.approved_at,
        approval_token=args.approval_token,
        approval_statement=args.approval_statement,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
