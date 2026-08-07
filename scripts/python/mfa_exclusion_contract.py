"""연도별 MFA/분석 제외에 대한 연구자 승인 계약.

자동 감사가 제외 *후보*를 만들 수는 있지만, 제외 정당성은 이 모듈이
검증한 연구자 승인 CSV+JSON 계약 없이는 성립하지 않는다. 계약은
``input_contract_id``에 묶여 다른 CSV/LAB 입력으로 조용히 재사용되지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    load_bad_wav_inventory_ids,
    sha256_file,
)

SCHEMA_VERSION = "mfa_approved_exclusions.v1"
REVIEW_FIELDS = [
    "year",
    "input_contract_id",
    "utt_id",
    "reason_code",
    "exclusion_scope",
    "evidence_path",
    "decision",
    "notes",
]
ALLOWED_REASON_CODES = {
    "audio_unusable",
    "quarantined_wav",
    "text_duration_impossible",
    "researcher_excluded",
    "manual_review_unclassified",
    "mfa_alignment_missing",
    "mfa_feature_generation_failed",
    "audio_pairing_unresolved",
    "empty_reference_unresolved_symbol",
}
ALLOWED_SCOPES = {"alignment_and_analysis", "analysis_only"}


def _read_rows(path: Path, *, year: str, input_contract_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if list(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise RuntimeError(
                f"제외 검토표 schema 불일치: {reader.fieldnames!r}"
            )
        for line_number, raw in enumerate(reader, 2):
            row = {key: str(raw.get(key, "") or "").strip() for key in REVIEW_FIELDS}
            if row["year"] != str(year):
                raise RuntimeError(f"{line_number}행 year 불일치")
            if row["input_contract_id"] != input_contract_id:
                raise RuntimeError(f"{line_number}행 input_contract_id 불일치")
            utt_id = row["utt_id"]
            if not utt_id or utt_id in seen:
                raise RuntimeError(f"{line_number}행 빈/중복 utt_id: {utt_id!r}")
            if row["reason_code"] not in ALLOWED_REASON_CODES:
                raise RuntimeError(
                    f"{line_number}행 reason_code 불허: {row['reason_code']!r}"
                )
            if row["exclusion_scope"] not in ALLOWED_SCOPES:
                raise RuntimeError(
                    f"{line_number}행 exclusion_scope 불허: "
                    f"{row['exclusion_scope']!r}"
                )
            if row["decision"] != "approved":
                raise RuntimeError(
                    f"{line_number}행 미승인 decision: {row['decision']!r}"
                )
            seen.add(utt_id)
            rows.append(row)
    return rows


def build_contract(
    *,
    review_csv: Path,
    output: Path,
    year: str,
    input_contract_id: str,
    approved_by: str,
    approved_at: str,
) -> dict[str, object]:
    review_csv = review_csv.resolve()
    if not approved_by.strip() or not approved_at.strip():
        raise RuntimeError("approved_by/approved_at은 비어 있을 수 없음")
    rows = _read_rows(
        review_csv, year=str(year), input_contract_id=input_contract_id
    )
    counts = Counter(
        (row["reason_code"], row["exclusion_scope"]) for row in rows
    )
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "approved",
        "year": str(year),
        "input_contract_id": input_contract_id,
        "approved_by": approved_by.strip(),
        "approved_at": approved_at.strip(),
        "created_at": datetime.now().astimezone().isoformat(),
        "review_csv": file_fingerprint(review_csv, with_sha256=True),
        "row_count": len(rows),
        "counts": {
            f"{reason}|{scope}": count
            for (reason, scope), count in sorted(counts.items())
        },
        "policy": {
            "automatic_approval_forbidden": True,
            "unknown_missing_is_hard_failure": True,
            "contract_bound_to_input_contract_id": True,
        },
    }
    atomic_write_json(output.resolve(), payload)
    return payload


def load_contract(
    path: Path, *, year: str, input_contract_id: str
) -> tuple[dict[str, object], dict[str, dict[str, str]]]:
    path = path.resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        data.get("schema_version") != SCHEMA_VERSION
        or data.get("status") != "approved"
        or str(data.get("year")) != str(year)
        or data.get("input_contract_id") != input_contract_id
    ):
        raise RuntimeError(f"제외 승인 계약 identity/status 불일치: {path}")
    fingerprint = data.get("review_csv")
    if not isinstance(fingerprint, dict) or not fingerprint.get("path"):
        raise RuntimeError("제외 승인 계약 review_csv fingerprint 누락")
    review_csv = Path(str(fingerprint["path"]))
    if not review_csv.is_file():
        raise FileNotFoundError(review_csv)
    if sha256_file(review_csv) != str(fingerprint.get("sha256") or ""):
        raise RuntimeError("제외 승인 CSV SHA256 불일치")
    rows = _read_rows(
        review_csv, year=str(year), input_contract_id=input_contract_id
    )
    if len(rows) != int(data.get("row_count", -1)):
        raise RuntimeError("제외 승인 계약 row_count 불일치")
    return data, {row["utt_id"]: row for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--review-csv", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--year", required=True)
    build.add_argument("--input-contract-id", required=True)
    build.add_argument("--approved-by", required=True)
    build.add_argument("--approved-at", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--contract", type=Path, required=True)
    validate.add_argument("--year", required=True)
    validate.add_argument("--input-contract-id", required=True)
    validate.add_argument("--quarantine-log", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        report = build_contract(
            review_csv=args.review_csv,
            output=args.output,
            year=args.year,
            input_contract_id=args.input_contract_id,
            approved_by=args.approved_by,
            approved_at=args.approved_at,
        )
    else:
        data, rows = load_contract(
            args.contract,
            year=args.year,
            input_contract_id=args.input_contract_id,
        )
        inventory_ids: set[str] = set()
        quarantine_ids: set[str] = set()
        if args.quarantine_log is not None and args.quarantine_log.is_file():
            inventory_ids, quarantine_ids = load_bad_wav_inventory_ids(
                args.quarantine_log
            )
        approved_alignment = {
            utt_id
            for utt_id, row in rows.items()
            if row["exclusion_scope"] == "alignment_and_analysis"
        }
        unapproved_quarantine = sorted(quarantine_ids - approved_alignment)
        if unapproved_quarantine:
            raise RuntimeError(
                "승인되지 않은 quarantine ID: "
                f"{unapproved_quarantine[:20]}"
            )
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "approved",
            "year": args.year,
            "input_contract_id": args.input_contract_id,
            "contract": file_fingerprint(
                args.contract.resolve(), with_sha256=True
            ),
            "approved_rows": len(rows),
            "bad_wav_inventory_ids": len(inventory_ids),
            "unpaired_bad_wav_ids": len(inventory_ids - quarantine_ids),
            "quarantine_ids": len(quarantine_ids),
            "unapproved_quarantine_ids": unapproved_quarantine,
            "approved_by": data.get("approved_by"),
            "approved_at": data.get("approved_at"),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
