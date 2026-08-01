"""다음 연도 MFA 전에 직전 연도 QC·marker·DB 계약을 읽기 전용으로 검증한다.

대량 정렬이 끝났다는 콘솔 문구나 exit code만 신뢰하지 않는다. 독립 연도
감사, align/merge marker, direct export 보고서, 보존 SQLite DB와 temp
입력계약, DB 재수출 표본, 연구자 인프라 검토가 모두 같은 입력계약·검색
마스터를 가리킬 때만 통과한다.

``direct_db_research_6tier_v1``은 새 계약 gate로 자동 분기하며, 역사적
``direct_db_4tier`` 결과에는 기존 검증을 보존한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Any

from pipeline_common import atomic_write_json, now_iso, sha256_file

SUPPORTED_PRONUNCIATION_MODES = {
    "korean_mfa",
    "common_pron_mfa_r2_latest_jamo",
}


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, f"파일 없음: {path}"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"JSON 읽기 실패: {path} ({exc})"
    if not isinstance(value, dict):
        return None, f"JSON 최상위가 object가 아님: {path}"
    return value, None


def _canonical(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def _same_path(left: str | Path | None, right: str | Path | None) -> bool:
    if not left or not right:
        return False
    return _canonical(left) == _canonical(right)


def _nested(data: dict[str, Any] | None, *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _as_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return converted if converted >= 0 else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return converted if math.isfinite(converted) else None


def _read_classification_ids(
    path: Path, expected_year: str
) -> tuple[set[str] | None, str | None]:
    """동결 형태소 분류표의 연도·ID 유일성을 검증해 ID 집합을 반환한다."""

    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"year", "utt_id", "recommended_action"}
            missing = required - set(reader.fieldnames or ())
            if missing:
                return None, f"필수 열 누락: {sorted(missing)}"
            ids: set[str] = set()
            for line_number, row in enumerate(reader, start=2):
                year = (row.get("year") or "").strip()
                utt_id = (row.get("utt_id") or "").strip()
                action = (row.get("recommended_action") or "").strip()
                if year != expected_year:
                    return (
                        None,
                        f"{line_number}행 연도 불일치: "
                        f"{year!r} != {expected_year!r}",
                    )
                if not utt_id or not action:
                    return None, f"{line_number}행 utt_id/action 공백"
                if utt_id in ids:
                    return None, f"{line_number}행 중복 utt_id: {utt_id}"
                ids.add(utt_id)
    except (OSError, UnicodeError, csv.Error) as exc:
        return None, f"분류 CSV 읽기 실패: {exc}"
    return ids, None


def validate_next_year_gate(
    *,
    prior_year: str,
    next_year: str,
    audit_report: Path,
    align_marker: Path,
    merge_marker: Path,
    temp_contract: Path,
    sample_equivalence_report: Path,
    researcher_review_report: Path,
    expected_search_master_root: Path,
    expected_final_year_root: Path,
    expected_pronunciation_mode: str,
    report_path: Path,
    minimum_coverage_pct: float = 99.0,
) -> dict[str, Any]:
    """검증 결과를 원자 저장하고 보고서 dict를 반환한다."""

    inputs = {
        "audit_report": audit_report.resolve(strict=False),
        "align_marker": align_marker.resolve(strict=False),
        "merge_marker": merge_marker.resolve(strict=False),
        "temp_contract": temp_contract.resolve(strict=False),
        "sample_equivalence_report": (
            sample_equivalence_report.resolve(strict=False)
        ),
        "researcher_review_report": (
            researcher_review_report.resolve(strict=False)
        ),
    }
    loaded: dict[str, dict[str, Any] | None] = {}
    read_errors: dict[str, str | None] = {}
    for name, path in inputs.items():
        loaded[name], read_errors[name] = _read_json(path)

    audit = loaded["audit_report"]
    align = loaded["align_marker"]
    merge = loaded["merge_marker"]
    contract = loaded["temp_contract"]
    sample = loaded["sample_equivalence_report"]
    researcher_review = loaded["researcher_review_report"]
    if _nested(audit, "schema_version") == "mfa_research_6tier_year_audit.v1":
        from preflight_next_year_after_research_qc import (
            validate_research_next_year_gate,
        )

        return validate_research_next_year_gate(
            prior_year=prior_year,
            next_year=next_year,
            audit_report=audit_report,
            align_marker=align_marker,
            merge_marker=merge_marker,
            temp_contract=temp_contract,
            sample_equivalence_report=sample_equivalence_report,
            researcher_review_report=researcher_review_report,
            expected_search_master_root=expected_search_master_root,
            expected_final_year_root=expected_final_year_root,
            expected_pronunciation_mode=expected_pronunciation_mode,
            report_path=report_path,
        )
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append(
            {"name": name, "status": "passed" if passed else "failed",
             "detail": detail}
        )

    for name, path in inputs.items():
        error = read_errors[name]
        add(
            f"{name}_readable",
            error is None,
            "JSON object 읽기 성공" if error is None else str(error),
        )
    add(
        "expected_pronunciation_mode_supported",
        expected_pronunciation_mode in SUPPORTED_PRONUNCIATION_MODES,
        f"expected={expected_pronunciation_mode!r}",
    )

    audit_contract = str(_nested(audit, "input_contract_id") or "")
    align_contract = str(
        _nested(align, "details", "input_contract_id") or ""
    )
    merge_contract = str(
        _nested(merge, "details", "input_contract_id") or ""
    )
    temp_contract_id = str(_nested(contract, "input_contract_id") or "")

    add(
        "audit_identity",
        str(_nested(audit, "year") or "") == prior_year
        and _nested(audit, "status") == "success",
        f"year={_nested(audit, 'year')!r}, status={_nested(audit, 'status')!r}",
    )
    coverage = _as_float(_nested(audit, "coverage_pct"))
    hard_failures = _nested(audit, "hard_failure_counts")
    hard_failure_values = (
        [_as_nonnegative_int(value) for value in hard_failures.values()]
        if isinstance(hard_failures, dict)
        else []
    )
    hard_failures_ok = (
        isinstance(hard_failures, dict)
        and bool(hard_failures)
        and all(value == 0 for value in hard_failure_values)
    )
    add(
        "audit_hard_gate",
        coverage is not None
        and coverage >= minimum_coverage_pct
        and hard_failures_ok,
        f"coverage={coverage}%, hard_failure_counts={hard_failures!r}",
    )
    add(
        "audit_final_root",
        _same_path(_nested(audit, "textgrid_root"),
                   expected_final_year_root)
        and expected_final_year_root.is_dir(),
        f"audit={_nested(audit, 'textgrid_root')!r}, "
        f"expected={str(expected_final_year_root.resolve(strict=False))!r}",
    )
    missing_csv_value = _nested(audit, "missing_csv")
    missing_csv_path = (
        Path(str(missing_csv_value)).resolve(strict=False)
        if missing_csv_value
        else None
    )
    add(
        "audit_missing_inventory",
        missing_csv_path is not None and missing_csv_path.is_file(),
        f"missing_csv={str(missing_csv_path) if missing_csv_path else None!r}",
    )

    add(
        "align_marker_identity",
        str(_nested(align, "year") or "") == prior_year
        and _nested(align, "stage") == "align"
        and _nested(align, "g2p_model")
        == expected_pronunciation_mode
        and _nested(align, "details", "export_mode")
        == "direct_db_4tier",
        "직전 연도 align/direct-DB marker 확인",
    )
    add(
        "merge_marker_identity",
        str(_nested(merge, "year") or "") == prior_year
        and _nested(merge, "stage") == "merge"
        and _nested(merge, "g2p_model")
        == expected_pronunciation_mode
        and _nested(merge, "details", "export_mode")
        == "direct_db_4tier",
        "직전 연도 merge/direct-DB marker 확인",
    )
    contracts = {
        audit_contract,
        align_contract,
        merge_contract,
        temp_contract_id,
    }
    add(
        "input_contract_match",
        all((audit_contract, align_contract, merge_contract,
             temp_contract_id))
        and len(contracts) == 1,
        "audit/align/merge/temp contract="
        f"{[audit_contract, align_contract, merge_contract, temp_contract_id]}",
    )

    expected_search = expected_search_master_root.resolve(strict=False)
    search_values = [
        _nested(align, "details", "search_master_root"),
        _nested(merge, "details", "search_master_root"),
        _nested(contract, "search_master_root"),
    ]
    add(
        "search_master_match",
        expected_search.is_dir()
        and all(_same_path(value, expected_search)
                for value in search_values),
        f"recorded={search_values!r}, expected={str(expected_search)!r}",
    )
    add(
        "merge_staging_root",
        _same_path(
            _nested(merge, "details", "staging_output_root"),
            expected_final_year_root.parent,
        ),
        "merge staging base가 audit final 연도 폴더의 부모와 일치",
    )

    alignment_db_value = _nested(align, "details", "alignment_db")
    alignment_db = (
        Path(str(alignment_db_value)).resolve(strict=False)
        if alignment_db_value
        else None
    )
    temp_year_value = _nested(contract, "temp_year")
    temp_year = (
        Path(str(temp_year_value)).resolve(strict=False)
        if temp_year_value
        else None
    )
    db_retained = _nested(merge, "details", "alignment_db_retained") is True
    db_in_contract_dir = (
        alignment_db is not None
        and temp_year is not None
        and alignment_db.parent == temp_year
        and alignment_db.name == f"{prior_year}.db"
    )
    add(
        "alignment_db_retained",
        db_retained
        and alignment_db is not None
        and alignment_db.is_file()
        and alignment_db.stat().st_size > 0
        and db_in_contract_dir
        and _nested(contract, "status")
        == "direct_merge_completed_temp_retained_for_qc",
        f"db={str(alignment_db) if alignment_db else None!r}, "
        f"retained={db_retained}, temp_status={_nested(contract, 'status')!r}",
    )
    sample_compared = _as_nonnegative_int(
        _nested(sample, "comparison_counts", "compared")
    )
    sample_tier_equal = _as_nonnegative_int(
        _nested(sample, "comparison_counts", "tier_equal")
    )
    sample_sessions = _as_nonnegative_int(
        _nested(sample, "selection_counts", "selected_sessions")
    )
    add(
        "db_textgrid_sample_equivalence",
        _nested(sample, "schema_version") == 1
        and _nested(sample, "status") == "success"
        and str(_nested(sample, "year") or "") == prior_year
        and _nested(sample, "input_contract_id") == audit_contract
        and _same_path(_nested(sample, "db", "path"), alignment_db)
        and sample_compared is not None
        and sample_compared >= 5
        and sample_tier_equal == sample_compared
        and sample_sessions is not None
        and sample_sessions >= 5,
        "status="
        f"{_nested(sample, 'status')!r}, "
        f"contract={_nested(sample, 'input_contract_id')!r}, "
        f"db={_nested(sample, 'db', 'path')!r}, "
        f"compared={sample_compared}, tier_equal={sample_tier_equal}, "
        f"sessions={sample_sessions}",
    )

    review_years = _nested(researcher_review, "counts", "years")
    review_speakers = _as_nonnegative_int(
        _nested(researcher_review, "counts", "speakers")
    )
    review_contract = _nested(
        researcher_review, "year_contracts", prior_year
    )
    alignment_method_id = _nested(
        align, "details", "alignment_contract_id"
    )
    add(
        "researcher_infrastructure_review",
        _nested(researcher_review, "schema_version")
        == "mfa_r2_infrastructure_researcher_review.v1"
        and _nested(researcher_review, "status") == "approved"
        and _nested(researcher_review, "allow_bulk_mfa") is True
        and _nested(researcher_review, "review_scope")
        == "infrastructure_acceptance_only"
        and _nested(
            researcher_review, "realization_judgment_performed"
        )
        is False
        and isinstance(review_years, dict)
        and set(review_years) == {prior_year}
        and _as_nonnegative_int(review_years.get(prior_year)) is not None
        and _as_nonnegative_int(review_years.get(prior_year)) > 0
        and review_speakers is not None
        and review_speakers >= 5
        and isinstance(review_contract, dict)
        and review_contract.get("alignment_contract_id")
        == alignment_method_id
        and review_contract.get("lab_input_contract_id")
        == audit_contract
        and _same_path(
            review_contract.get("database"), alignment_db
        ),
        "status="
        f"{_nested(researcher_review, 'status')!r}, "
        f"years={review_years!r}, speakers={review_speakers}, "
        f"contract={review_contract!r}",
    )

    direct_report_value = _nested(
        merge, "details", "direct_export_report"
    )
    direct_report_path = (
        Path(str(direct_report_value)).resolve(strict=False)
        if direct_report_value
        else None
    )
    direct, direct_error = (
        _read_json(direct_report_path)
        if direct_report_path is not None
        else (None, "direct_export_report 경로 없음")
    )
    add(
        "direct_report_readable",
        direct_error is None,
        "JSON object 읽기 성공"
        if direct_error is None
        else str(direct_error),
    )
    direct_hard_values = [
        _as_nonnegative_int(_nested(direct, "counts", key))
        for key in ("form_missing", "failed")
    ]
    direct_hard_failure = (
        sum(value for value in direct_hard_values if value is not None)
        if all(value is not None for value in direct_hard_values)
        else None
    )
    add(
        "direct_report_gate",
        _nested(direct, "status") == "success"
        and str(_nested(direct, "year") or "") == prior_year
        and direct_hard_failure == 0
        and _same_path(_nested(direct, "db_path"), alignment_db)
        and _same_path(_nested(direct, "search_master_root"),
                       expected_search),
        f"status={_nested(direct, 'status')!r}, "
        f"hard_failure_sum={direct_hard_failure}",
    )
    direct_morph_missing = _as_nonnegative_int(
        _nested(direct, "counts", "morpheme_tier_missing")
    )
    morphology = _nested(audit, "morphology_classification")
    classification_path_value = _nested(
        morphology, "source_fingerprint", "path"
    )
    classification_path = (
        Path(str(classification_path_value)).resolve(strict=False)
        if classification_path_value
        else None
    )
    recorded_classification_sha = str(
        _nested(morphology, "source_fingerprint", "sha256") or ""
    )
    classification_sha_matches = False
    classification_ids: set[str] | None = None
    classification_ids_error: str | None = "분류 CSV 경로/해시 없음"
    if (
        classification_path is not None
        and classification_path.is_file()
        and recorded_classification_sha
    ):
        try:
            classification_sha_matches = (
                sha256_file(classification_path)
                == recorded_classification_sha
            )
        except OSError:
            classification_sha_matches = False
        if classification_sha_matches:
            classification_ids, classification_ids_error = (
                _read_classification_ids(
                    classification_path, prior_year
                )
            )
        else:
            classification_ids_error = "분류 CSV SHA256 불일치"
    direct_morph_inventory_raw = _nested(
        direct, "morpheme_tier_missing_inventory"
    )
    direct_morph_ids: set[str] | None = None
    direct_morph_inventory_error: str | None = None
    if direct_morph_missing == 0:
        if direct_morph_inventory_raw in (None, []):
            direct_morph_ids = set()
        else:
            direct_morph_inventory_error = (
                "누락 수는 0이나 누락 inventory가 비어 있지 않음"
            )
    elif direct_morph_missing is None:
        direct_morph_inventory_error = "형태소 누락 수가 유효하지 않음"
    elif not isinstance(direct_morph_inventory_raw, list):
        direct_morph_inventory_error = "누락 inventory가 list가 아님"
    else:
        normalized_inventory = [
            value.strip()
            for value in direct_morph_inventory_raw
            if isinstance(value, str) and value.strip()
        ]
        if len(normalized_inventory) != len(direct_morph_inventory_raw):
            direct_morph_inventory_error = (
                "누락 inventory에 공백/비문자 ID가 있음"
            )
        elif len(set(normalized_inventory)) != len(normalized_inventory):
            direct_morph_inventory_error = (
                "누락 inventory에 중복 ID가 있음"
            )
        elif len(normalized_inventory) != direct_morph_missing:
            direct_morph_inventory_error = (
                "누락 수와 inventory ID 수가 다름"
            )
        else:
            direct_morph_ids = set(normalized_inventory)
    classification_needed = (
        direct_morph_missing is None or direct_morph_missing > 0
    )
    direct_ids_classified = bool(
        direct_morph_ids is not None
        and classification_ids is not None
        and direct_morph_ids <= classification_ids
    )
    classification_evidence_ok = (
        not classification_needed
        or (
            isinstance(morphology, dict)
            and classification_sha_matches
            and classification_ids_error is None
            and direct_morph_inventory_error is None
            and direct_ids_classified
            and _as_nonnegative_int(
                _nested(morphology, "unclassified_ids")
            )
            == 0
            and _as_nonnegative_int(
                _nested(morphology, "classification_ids_without_lab")
            )
            == 0
            and _as_nonnegative_int(
                _nested(morphology, "recovery_candidate_not_valid")
            )
            == 0
        )
    )
    add(
        "morphology_classification_evidence",
        classification_evidence_ok,
        "direct_morph_missing="
        f"{direct_morph_missing}, classification={classification_path}, "
        f"sha_match={classification_sha_matches}, "
        f"classification_ids={len(classification_ids) if classification_ids is not None else None}, "
        f"direct_inventory_ids={len(direct_morph_ids) if direct_morph_ids is not None else None}, "
        f"classification_error={classification_ids_error!r}, "
        f"direct_inventory_error={direct_morph_inventory_error!r}",
    )
    action_counts = _nested(morphology, "counts_by_action")
    classified_issue_values = (
        [_as_nonnegative_int(value) for value in action_counts.values()]
        if isinstance(action_counts, dict)
        else []
    )
    classified_issue_count = (
        sum(value for value in classified_issue_values if value is not None)
        if classified_issue_values
        and all(value is not None for value in classified_issue_values)
        else None
    )
    morphology_accounted = (
        direct_morph_missing is not None
        and (
            direct_morph_missing == 0
            or (
                classified_issue_count is not None
                and direct_morph_missing <= classified_issue_count
                and direct_ids_classified
                and classification_evidence_ok
            )
        )
    )
    add(
        "direct_morphology_accounted",
        morphology_accounted,
        f"direct_missing={direct_morph_missing}, "
        f"classified_source_issues={classified_issue_count}",
    )

    audit_lab = _as_nonnegative_int(
        _nested(audit, "counts", "lab_ids")
    )
    audit_textgrids = _as_nonnegative_int(
        _nested(audit, "counts", "textgrid_ids")
    )
    marker_lab = _as_nonnegative_int(
        _nested(align, "details", "labs")
    )
    marker_textgrids = _as_nonnegative_int(
        _nested(align, "details", "textgrids")
    )
    direct_created = _as_nonnegative_int(
        _nested(direct, "counts", "created")
    )
    direct_validated = _as_nonnegative_int(
        _nested(direct, "counts", "validated_existing")
    )
    direct_textgrids = (
        direct_created + direct_validated
        if direct_created is not None and direct_validated is not None
        else None
    )
    add(
        "artifact_counts_match",
        audit_lab is not None
        and audit_textgrids is not None
        and marker_lab is not None
        and marker_textgrids is not None
        and direct_textgrids is not None
        and audit_lab > 0
        and audit_textgrids > 0
        and audit_lab == marker_lab
        and audit_textgrids == marker_textgrids == direct_textgrids,
        f"audit(lab={audit_lab},tg={audit_textgrids}), "
        f"marker(lab={marker_lab},tg={marker_textgrids}), "
        f"direct(tg={direct_textgrids})",
    )

    failed = [check["name"] for check in checks
              if check["status"] == "failed"]
    report = {
        "schema_version": 1,
        "supported_export_mode": "direct_db_4tier",
        "status": "passed" if not failed else "failed",
        "checked_at": now_iso(),
        "prior_year": prior_year,
        "next_year": next_year,
        "minimum_coverage_pct": minimum_coverage_pct,
        "expected_pronunciation_mode": expected_pronunciation_mode,
        "expected_search_master_root": str(expected_search),
        "expected_final_year_root": str(
            expected_final_year_root.resolve(strict=False)
        ),
        "inputs": {
            **{name: str(path) for name, path in inputs.items()},
            "direct_export_report": (
                str(direct_report_path) if direct_report_path else None
            ),
            "alignment_db": (
                str(alignment_db) if alignment_db else None
            ),
            "morph_classification_csv": (
                str(classification_path)
                if classification_path is not None
                else None
            ),
        },
        "input_contract_id": (
            audit_contract if len(contracts) == 1 else None
        ),
        "checks": checks,
        "failed_checks": failed,
    }
    atomic_write_json(report_path.resolve(strict=False), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-year", required=True)
    parser.add_argument("--next-year", required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--align-marker", type=Path, required=True)
    parser.add_argument("--merge-marker", type=Path, required=True)
    parser.add_argument("--temp-contract", type=Path, required=True)
    parser.add_argument(
        "--sample-equivalence-report", type=Path, required=True
    )
    parser.add_argument(
        "--researcher-review-report", type=Path, required=True
    )
    parser.add_argument(
        "--expected-search-master-root", type=Path, required=True
    )
    parser.add_argument(
        "--expected-final-year-root", type=Path, required=True
    )
    parser.add_argument(
        "--expected-pronunciation-mode",
        choices=sorted(SUPPORTED_PRONUNCIATION_MODES),
        required=True,
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--minimum-coverage-pct", type=float, default=99.0)
    args = parser.parse_args()
    report = validate_next_year_gate(
        prior_year=args.prior_year,
        next_year=args.next_year,
        audit_report=args.audit_report,
        align_marker=args.align_marker,
        merge_marker=args.merge_marker,
        temp_contract=args.temp_contract,
        sample_equivalence_report=args.sample_equivalence_report,
        researcher_review_report=args.researcher_review_report,
        expected_search_master_root=args.expected_search_master_root,
        expected_final_year_root=args.expected_final_year_root,
        expected_pronunciation_mode=args.expected_pronunciation_mode,
        report_path=args.report,
        minimum_coverage_pct=args.minimum_coverage_pct,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
