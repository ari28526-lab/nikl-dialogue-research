"""입력 감사·quarantine 증거에서 연구자 제외 검토 CSV를 만든다.

이 스크립트는 모든 행을 ``pending``으로만 쓴다. 승인 계약은 연구자가
행별 사유·범위를 확인해 ``approved``로 바꾼 뒤
``mfa_exclusion_contract.py build``로 별도 생성한다.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from mfa_exclusion_contract import REVIEW_FIELDS
from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint
from realign_eojeol_build_corpus import input_contract

SCHEMA_VERSION = "mfa_exclusion_review_candidates.v1"


def _candidate_from_issue(issue: dict[str, object]) -> dict[str, str] | None:
    utt_id = str(issue.get("utt_id", "") or "").strip()
    issue_name = str(issue.get("issue", "") or "").strip()
    disposition = str(issue.get("morph_disposition", "") or "").strip()
    if not utt_id:
        return None
    if issue_name == "source_segment_text_duration_impossible":
        reason, scope = "text_duration_impossible", "alignment_and_analysis"
    elif disposition == "exclude_source_audio_unusable":
        reason, scope = "audio_unusable", "analysis_only"
    elif disposition == "manual_review_unclassified":
        reason, scope = "manual_review_unclassified", "analysis_only"
    else:
        return None
    evidence = str(issue.get("path", "") or issue.get("detail", "") or "")
    return {
        "utt_id": utt_id,
        "reason_code": reason,
        "exclusion_scope": scope,
        "evidence_path": evidence,
        "notes": issue_name,
    }


def prepare_review(
    *,
    audit_report: Path,
    year: str,
    search_master_root: Path,
    output_csv: Path,
    output_report: Path,
    quarantine_log: Path | None = None,
    input_contract_id: str | None = None,
) -> dict[str, object]:
    audit_report = audit_report.resolve()
    audit = json.loads(audit_report.read_text(encoding="utf-8-sig"))
    year_reports = [
        row for row in audit.get("years", []) if str(row.get("year")) == str(year)
    ]
    if len(year_reports) != 1:
        raise RuntimeError(f"audit report에 {year} 결과가 1개가 아님")
    contract_id = (
        input_contract_id.strip()
        if input_contract_id and input_contract_id.strip()
        else input_contract(search_master_root.resolve(), year)[
            "input_contract_id"
        ]
    )
    by_utt: dict[str, dict[str, str]] = {}
    for issue in year_reports[0].get("issue_inventory", []):
        if not isinstance(issue, dict):
            continue
        candidate = _candidate_from_issue(issue)
        if candidate is None:
            continue
        prior = by_utt.get(candidate["utt_id"])
        if (
            prior is None
            or candidate["exclusion_scope"] == "alignment_and_analysis"
        ):
            by_utt[candidate["utt_id"]] = candidate

    quarantine_fingerprint = None
    if quarantine_log is not None and quarantine_log.is_file():
        quarantine_fingerprint = file_fingerprint(
            quarantine_log.resolve(), with_sha256=True
        )
        with quarantine_log.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if "name" not in set(reader.fieldnames or ()):
                raise RuntimeError("quarantine log name 열 누락")
            for row in reader:
                name = str(row.get("name", "") or "").strip()
                if not name:
                    continue
                utt_id = Path(name).stem
                by_utt[utt_id] = {
                    "utt_id": utt_id,
                    "reason_code": "quarantined_wav",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": str(
                        row.get("quarantine_path", "") or quarantine_log
                    ),
                    "notes": "quarantine_bad_wavs",
                }

    rows = []
    for utt_id, candidate in sorted(by_utt.items()):
        rows.append(
            {
                "year": str(year),
                "input_contract_id": contract_id,
                "utt_id": utt_id,
                "reason_code": candidate["reason_code"],
                "exclusion_scope": candidate["exclusion_scope"],
                "evidence_path": candidate["evidence_path"],
                "decision": "pending",
                "notes": candidate["notes"],
            }
        )
    with atomic_text_writer(
        output_csv.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(
            stream, fieldnames=REVIEW_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_review",
        "year": str(year),
        "input_contract_id": contract_id,
        "audit_report": file_fingerprint(audit_report, with_sha256=True),
        "quarantine_log": quarantine_fingerprint,
        "review_csv": file_fingerprint(
            output_csv.resolve(), with_sha256=True
        ),
        "candidate_count": len(rows),
        "automatic_approval_performed": False,
    }
    atomic_write_json(output_report.resolve(), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--quarantine-log", type=Path)
    parser.add_argument("--input-contract-id")
    args = parser.parse_args()
    result = prepare_review(
        audit_report=args.audit_report,
        year=args.year,
        search_master_root=args.search_master_root,
        output_csv=args.output_csv,
        output_report=args.output_report,
        quarantine_log=args.quarantine_log,
        input_contract_id=args.input_contract_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
