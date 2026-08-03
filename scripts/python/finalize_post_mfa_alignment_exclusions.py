"""Finalize reviewed post-MFA missing alignments without rerunning MFA.

The command combines the already approved pre-MFA exclusions with the exact
active utterances that have no word/phone intervals in a retained MFA DB.  It
requires an explicit approval token, verifies the review evidence and DB ID
sets, and writes a new contract root without overwriting either source.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

from mfa_exclusion_contract import (
    REVIEW_FIELDS,
    build_contract,
    load_contract,
)
from pipeline_common import atomic_write_json, file_fingerprint, sha256_file


SCHEMA_VERSION = "mfa_post_alignment_finalization.v1"
APPROVAL_TOKEN = "APPROVE_2020_POST_MFA_363"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return [
            {key: str(value or "").strip() for key, value in row.items()}
            for row in reader
        ]


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


def retained_db_missing_ids(db_path: Path) -> set[str]:
    connection = sqlite3.connect(
        f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True, timeout=120
    )
    connection.execute("PRAGMA query_only=ON")
    try:
        return {
            str(row[0])
            for row in connection.execute(
                """
                SELECT f.name
                FROM utterance u
                JOIN file f ON f.id = u.file_id
                WHERE u.ignored = 0
                  AND (
                    NOT EXISTS (
                        SELECT 1 FROM word_interval wi
                        WHERE wi.utterance_id = u.id
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM phone_interval pi
                        WHERE pi.utterance_id = u.id
                    )
                  )
                """
            )
        }
    finally:
        connection.close()


def verify_bundle(
    manifest_path: Path, post_decisions: Path
) -> tuple[dict[str, object], set[str]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != "simple_post_mfa_review_bundle.v2"
        or manifest.get("status") != "success"
        or str(manifest.get("year")) != "2020"
    ):
        raise RuntimeError("검토 bundle manifest identity/status 불일치")
    candidate = manifest.get("post_mfa_candidates_csv")
    if not isinstance(candidate, dict):
        raise RuntimeError("검토 bundle의 post-MFA 후보 fingerprint 누락")
    if sha256_file(post_decisions) != str(candidate.get("sha256") or ""):
        raise RuntimeError("post-MFA 결정표 SHA가 검토 bundle과 다름")
    audio_ids = {
        str(value).strip()
        for value in manifest.get("approved_audio_unusable_utt_ids", [])
        if str(value).strip()
    }
    if len(audio_ids) != int(
        manifest.get("approved_audio_unusable_exclusion_count", -1)
    ):
        raise RuntimeError("audio_unusable ID/count 불일치")
    review_csv = manifest_path.parent / "00_REVIEW.csv"
    review_rows = read_csv(review_csv)
    decisions = Counter(row.get("decision", "") for row in review_rows)
    if decisions != Counter({"match": 13, "exclude_audio_unusable": 3}):
        raise RuntimeError(f"16표본 연구자 결정 불일치: {dict(decisions)}")
    review_audio = {
        row["utt_id"]
        for row in review_rows
        if row.get("decision") == "exclude_audio_unusable"
    }
    if review_audio != audio_ids:
        raise RuntimeError("검토표와 manifest의 audio_unusable ID 불일치")
    return manifest, audio_ids


def finalize(
    *,
    year: str,
    input_contract_id: str,
    db_path: Path,
    pre_approved_contract: Path,
    post_decisions: Path,
    review_bundle_manifest: Path,
    output_root: Path,
    approved_by: str,
    approved_at: str,
    approval_token: str,
    approval_statement: str,
) -> dict[str, object]:
    if year != "2020" or approval_token != APPROVAL_TOKEN:
        raise RuntimeError("2020 post-MFA 명시 승인 token 불일치")
    if not approved_by.strip() or not approved_at.strip():
        raise RuntimeError("approved_by/approved_at은 필수")
    if not approval_statement.strip():
        raise RuntimeError("연구자 승인 문구는 필수")
    db_path = db_path.resolve()
    pre_approved_contract = pre_approved_contract.resolve()
    post_decisions = post_decisions.resolve()
    review_bundle_manifest = review_bundle_manifest.resolve()
    output_root = output_root.resolve()
    for path in (
        db_path,
        pre_approved_contract,
        post_decisions,
        review_bundle_manifest,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output_root.exists():
        raise FileExistsError(f"기존 출력 보호: {output_root}")

    pre_contract, pre_rows_by_id = load_contract(
        pre_approved_contract,
        year=year,
        input_contract_id=input_contract_id,
    )
    post_rows = read_csv(post_decisions)
    if not post_rows or list(post_rows[0]) != REVIEW_FIELDS:
        raise RuntimeError("post-MFA 결정표 schema/행 누락")
    post_ids = {row["utt_id"] for row in post_rows}
    if len(post_ids) != len(post_rows):
        raise RuntimeError("post-MFA 결정표 빈/중복 utt_id")
    if any(
        row["year"] != year
        or row["input_contract_id"] != input_contract_id
        or row["reason_code"] != "mfa_alignment_missing"
        or row["exclusion_scope"] != "alignment_and_analysis"
        or row["decision"] != "pending"
        for row in post_rows
    ):
        raise RuntimeError("post-MFA 원본 후보의 identity/pending 계약 불일치")

    db_missing_ids = retained_db_missing_ids(db_path)
    if post_ids != db_missing_ids:
        raise RuntimeError(
            "post-MFA 후보와 보존 DB 미정렬 ID 불일치: "
            f"candidate={len(post_ids)} db={len(db_missing_ids)}"
        )
    if post_ids & set(pre_rows_by_id):
        raise RuntimeError("pre-MFA 제외와 active post-MFA 제외 ID가 겹침")

    bundle, audio_ids = verify_bundle(review_bundle_manifest, post_decisions)
    if not audio_ids <= post_ids:
        raise RuntimeError("audio_unusable ID가 DB 미정렬 집합 밖에 있음")

    combined_rows = [pre_rows_by_id[key] for key in sorted(pre_rows_by_id)]
    for row in sorted(post_rows, key=lambda item: item["utt_id"]):
        item = dict(row)
        if item["utt_id"] in audio_ids:
            item["reason_code"] = "audio_unusable"
            item["evidence_path"] = str(review_bundle_manifest)
            item["notes"] = (
                "2026-08-03 researcher listening review: audio not audible; "
                "exclude from alignment and analysis"
            )
        else:
            item["reason_code"] = "mfa_alignment_missing"
            item["evidence_path"] = str(post_decisions)
            item["notes"] = (
                "2026-08-03 researcher infrastructure review complete; "
                "retain MFA DB and exclude unaligned utterance without rerun"
            )
        item["decision"] = "approved"
        combined_rows.append(item)

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
        reason_counts = Counter(row["reason_code"] for row in combined_rows)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "approved",
            "year": year,
            "input_contract_id": input_contract_id,
            "approved_by": approved_by,
            "approved_at": approved_at,
            "approval_token": approval_token,
            "approval_statement": approval_statement,
            "automatic_approval_performed": False,
            "full_year_mfa_rerun_required": False,
            "resume_from_retained_db": True,
            "counts": {
                "pre_mfa_approved": len(pre_rows_by_id),
                "post_mfa_approved": len(post_rows),
                "post_mfa_audio_unusable": len(audio_ids),
                "post_mfa_alignment_missing": len(post_rows) - len(audio_ids),
                "combined_approved": len(combined_rows),
            },
            "reason_counts": dict(sorted(reason_counts.items())),
            "database": file_fingerprint(db_path, with_sha256=False),
            "pre_approved_contract": file_fingerprint(
                pre_approved_contract, with_sha256=True
            ),
            "post_decisions": file_fingerprint(
                post_decisions, with_sha256=True
            ),
            "review_bundle_manifest": file_fingerprint(
                review_bundle_manifest, with_sha256=True
            ),
            "review_bundle_researcher_evidence": bundle.get(
                "researcher_review_evidence"
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
    parser.add_argument("--pre-approved-contract", type=Path, required=True)
    parser.add_argument("--post-decisions", type=Path, required=True)
    parser.add_argument("--review-bundle-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approved-at", required=True)
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--approval-statement", required=True)
    args = parser.parse_args()
    result = finalize(
        year=args.year,
        input_contract_id=args.input_contract_id,
        db_path=args.db,
        pre_approved_contract=args.pre_approved_contract,
        post_decisions=args.post_decisions,
        review_bundle_manifest=args.review_bundle_manifest,
        output_root=args.output_root,
        approved_by=args.approved_by,
        approved_at=args.approved_at,
        approval_token=args.approval_token,
        approval_statement=args.approval_statement,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
