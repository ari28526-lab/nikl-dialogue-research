"""입력 감사·quarantine 증거에서 연구자 제외 검토 CSV를 만든다.

이 스크립트는 모든 행을 ``pending``으로만 쓴다. 승인 계약은 연구자가
행별 사유·범위를 확인해 ``approved``로 바꾼 뒤
``mfa_exclusion_contract.py build``로 별도 생성한다.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from mfa_exclusion_contract import REVIEW_FIELDS
from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint
from realign_eojeol_build_corpus import input_contract

SCHEMA_VERSION = "mfa_exclusion_review_candidates.v1"
AUDIO_PAIRING_ISSUES = {
    "csv_duration_invalid",
    "duration_residual_mismatch",
    "duration_wav_missing",
    "duration_wav_too_small",
    "wav_header_unreadable",
}
DIRECT_AUDIO_PAIRING_EXCLUSION_ISSUES = {"csv_duration_invalid"}
AUDIO_PLAN_EXCLUSION_STATUSES = {
    "ambiguous_short_match",
    "target_unresolved",
}


def _candidate_from_issue(issue: dict[str, object]) -> dict[str, str] | None:
    utt_id = str(issue.get("utt_id", "") or "").strip()
    issue_name = str(issue.get("issue", "") or "").strip()
    disposition = str(issue.get("morph_disposition", "") or "").strip()
    if not utt_id:
        return None
    if issue_name == "source_segment_text_duration_impossible":
        reason, scope = "text_duration_impossible", "alignment_and_analysis"
    elif issue_name in DIRECT_AUDIO_PAIRING_EXCLUSION_ISSUES:
        reason, scope = "audio_pairing_unresolved", "alignment_and_analysis"
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
    audio_recovery_plan: Path | None = None,
    lab_report: Path | None = None,
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
    active_audio_issue_ids: set[str] = set()
    direct_audio_exclusion_ids: set[str] = set()
    for issue in year_reports[0].get("issue_inventory", []):
        if not isinstance(issue, dict):
            continue
        if str(issue.get("issue") or "") in AUDIO_PAIRING_ISSUES:
            utt_id = str(issue.get("utt_id") or "").strip()
            if utt_id:
                active_audio_issue_ids.add(utt_id)
                if str(issue.get("issue") or "") in (
                    DIRECT_AUDIO_PAIRING_EXCLUSION_ISSUES
                ):
                    direct_audio_exclusion_ids.add(utt_id)
        candidate = _candidate_from_issue(issue)
        if candidate is None:
            continue
        prior = by_utt.get(candidate["utt_id"])
        if (
            prior is None
            or candidate["exclusion_scope"] == "alignment_and_analysis"
        ):
            by_utt[candidate["utt_id"]] = candidate

    lab_report_fingerprint = None
    unresolved_inventory_fingerprint = None
    unresolved_symbol_ids: set[str] = set()
    empty_reference_unresolved_ids: set[str] = set()
    if lab_report is not None:
        lab_report = lab_report.resolve()
        lab_report_fingerprint = file_fingerprint(
            lab_report, with_sha256=True
        )
        lab_data = json.loads(lab_report.read_text(encoding="utf-8-sig"))
        if str(lab_data.get("status") or "") != "passed":
            raise RuntimeError("lab report status가 passed가 아님")
        if str(lab_data.get("year") or "") != str(year):
            raise RuntimeError("lab report year 불일치")
        if str(lab_data.get("input_contract_id") or "") != contract_id:
            raise RuntimeError("lab report input_contract_id 불일치")
        inventory_value = str(
            lab_data.get("unresolved_symbol_inventory") or ""
        ).strip()
        if not inventory_value:
            raise RuntimeError("lab report unresolved_symbol_inventory 누락")
        unresolved_inventory = Path(inventory_value).resolve()
        unresolved_inventory_fingerprint = file_fingerprint(
            unresolved_inventory, with_sha256=True
        )
        with unresolved_inventory.open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.DictReader(stream)
            required = {
                "year",
                "utt_id",
                "pron_reference_status",
                "lab_text",
            }
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(
                    "unresolved symbol inventory 필수 열 누락: "
                    f"{sorted(missing)}"
                )
            for line_number, row in enumerate(reader, 2):
                row_year = str(row.get("year") or "").strip()
                if row_year != str(year):
                    raise RuntimeError(
                        "unresolved symbol inventory year 불일치: "
                        f"line={line_number}, year={row_year!r}"
                    )
                status = str(
                    row.get("pron_reference_status") or ""
                ).strip()
                if status != "unresolved_symbol":
                    raise RuntimeError(
                        "unresolved symbol inventory status 불일치: "
                        f"line={line_number}, status={status!r}"
                    )
                utt_id = str(row.get("utt_id") or "").strip()
                if not utt_id or utt_id in unresolved_symbol_ids:
                    raise RuntimeError(
                        "unresolved symbol inventory 빈/중복 utt_id: "
                        f"line={line_number}, utt_id={utt_id!r}"
                    )
                unresolved_symbol_ids.add(utt_id)
                if str(row.get("lab_text") or "").strip():
                    continue
                empty_reference_unresolved_ids.add(utt_id)
                by_utt[utt_id] = {
                    "utt_id": utt_id,
                    "reason_code": "empty_reference_unresolved_symbol",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": str(unresolved_inventory),
                    "notes": (
                        "empty_reference_form; unresolved_symbol; "
                        "no_LAB_generated"
                    ),
                }
        expected_unresolved = int(
            lab_data.get("pron_reference_unresolved", -1)
        )
        if len(unresolved_symbol_ids) != expected_unresolved:
            raise RuntimeError(
                "lab report/inventory unresolved count 불일치: "
                f"report={expected_unresolved}, "
                f"inventory={len(unresolved_symbol_ids)}"
            )
        expected_empty = int(lab_data.get("empty_reference_form", -1))
        if len(empty_reference_unresolved_ids) != expected_empty:
            raise RuntimeError(
                "lab report/inventory empty reference count 불일치: "
                f"report={expected_empty}, "
                f"inventory={len(empty_reference_unresolved_ids)}"
            )

    audio_plan_fingerprint = None
    audio_plan_exclusion_ids: set[str] = set()
    if audio_recovery_plan is not None:
        audio_recovery_plan = audio_recovery_plan.resolve()
        audio_plan_fingerprint = file_fingerprint(
            audio_recovery_plan, with_sha256=True
        )
        with audio_recovery_plan.open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.DictReader(stream)
            required = {"year", "target_utt_id", "status"}
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(
                    f"audio recovery plan 필수 열 누락: {sorted(missing)}"
                )
            for row in reader:
                if str(row.get("year") or "").strip() != str(year):
                    continue
                status = str(row.get("status") or "").strip()
                if status not in AUDIO_PLAN_EXCLUSION_STATUSES:
                    continue
                utt_id = str(row.get("target_utt_id") or "").strip()
                if not utt_id:
                    raise RuntimeError(
                        "audio recovery plan 제외 후보의 target_utt_id 누락"
                    )
                audio_plan_exclusion_ids.add(utt_id)
                by_utt[utt_id] = {
                    "utt_id": utt_id,
                    "reason_code": "audio_pairing_unresolved",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": str(audio_recovery_plan),
                    "notes": status,
                }

    uncovered_audio_issues = sorted(
        active_audio_issue_ids
        - audio_plan_exclusion_ids
        - direct_audio_exclusion_ids
    )
    if uncovered_audio_issues:
        raise RuntimeError(
            "CSV-WAV 대응 복구가 완료되지 않음: 감사 issue 중 복구계획의 "
            "unresolved/ambiguous로 분류되지 않은 발화 "
            f"{len(uncovered_audio_issues):,}건; 예={uncovered_audio_issues[:20]}"
        )

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
    candidate_counts = Counter(row["reason_code"] for row in rows)
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
        "audio_recovery_plan": audio_plan_fingerprint,
        "lab_report": lab_report_fingerprint,
        "unresolved_symbol_inventory": unresolved_inventory_fingerprint,
        "unresolved_symbol_count": len(unresolved_symbol_ids),
        "partial_lab_unresolved_symbol_count": (
            len(unresolved_symbol_ids) - len(empty_reference_unresolved_ids)
        ),
        "empty_reference_unresolved_symbol_count": len(
            empty_reference_unresolved_ids
        ),
        "active_audio_pairing_issue_count": len(active_audio_issue_ids),
        "audio_plan_exclusion_count": len(audio_plan_exclusion_ids),
        "direct_audio_exclusion_count": len(direct_audio_exclusion_ids),
        "uncovered_audio_pairing_issue_count": len(uncovered_audio_issues),
        "review_csv": file_fingerprint(
            output_csv.resolve(), with_sha256=True
        ),
        "candidate_count": len(rows),
        "candidate_counts_by_reason": dict(sorted(candidate_counts.items())),
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
    parser.add_argument("--audio-recovery-plan", type=Path)
    parser.add_argument("--lab-report", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_review(
        audit_report=args.audit_report,
        year=args.year,
        search_master_root=args.search_master_root,
        output_csv=args.output_csv,
        output_report=args.output_report,
        quarantine_log=args.quarantine_log,
        input_contract_id=args.input_contract_id,
        audio_recovery_plan=args.audio_recovery_plan,
        lab_report=args.lab_report,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
