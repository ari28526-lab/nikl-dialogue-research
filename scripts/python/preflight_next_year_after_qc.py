"""다음 연도 MFA 전에 직전 연도 QC·marker·DB 계약을 읽기 전용으로 검증한다.

대량 정렬이 끝났다는 콘솔 문구나 exit code만 신뢰하지 않는다. 독립 4-tier
전수 감사, align/merge marker, direct export 보고서, 보존 SQLite DB와 temp
입력계약이 모두 같은 입력계약·검색 마스터를 가리킬 때만 통과한다.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

from pipeline_common import atomic_write_json, now_iso


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


def validate_next_year_gate(
    *,
    prior_year: str,
    next_year: str,
    audit_report: Path,
    align_marker: Path,
    merge_marker: Path,
    temp_contract: Path,
    expected_search_master_root: Path,
    expected_final_year_root: Path,
    report_path: Path,
    minimum_coverage_pct: float = 99.0,
) -> dict[str, Any]:
    """검증 결과를 원자 저장하고 보고서 dict를 반환한다."""

    inputs = {
        "audit_report": audit_report.resolve(strict=False),
        "align_marker": align_marker.resolve(strict=False),
        "merge_marker": merge_marker.resolve(strict=False),
        "temp_contract": temp_contract.resolve(strict=False),
    }
    loaded: dict[str, dict[str, Any] | None] = {}
    read_errors: dict[str, str | None] = {}
    for name, path in inputs.items():
        loaded[name], read_errors[name] = _read_json(path)

    audit = loaded["audit_report"]
    align = loaded["align_marker"]
    merge = loaded["merge_marker"]
    contract = loaded["temp_contract"]
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
        and _nested(align, "g2p_model") == "korean_mfa"
        and _nested(align, "details", "export_mode")
        == "direct_db_4tier",
        "직전 연도 align/direct-DB marker 확인",
    )
    add(
        "merge_marker_identity",
        str(_nested(merge, "year") or "") == prior_year
        and _nested(merge, "stage") == "merge"
        and _nested(merge, "g2p_model") == "korean_mfa"
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
        for key in ("form_missing", "morpheme_tier_missing", "failed")
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
        "status": "passed" if not failed else "failed",
        "checked_at": now_iso(),
        "prior_year": prior_year,
        "next_year": next_year,
        "minimum_coverage_pct": minimum_coverage_pct,
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
        "--expected-search-master-root", type=Path, required=True
    )
    parser.add_argument(
        "--expected-final-year-root", type=Path, required=True
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
        expected_search_master_root=args.expected_search_master_root,
        expected_final_year_root=args.expected_final_year_root,
        report_path=args.report,
        minimum_coverage_pct=args.minimum_coverage_pct,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
