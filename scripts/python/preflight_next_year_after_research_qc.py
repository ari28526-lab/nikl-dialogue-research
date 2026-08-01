"""연구 6-tier 연도 완료 뒤 다음 연도 진입 gate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pipeline_common import atomic_write_json, now_iso

SCHEMA_VERSION = "mfa_research_6tier_next_year_gate.v1"
EXPORT_MODE = "direct_db_research_6tier_v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object가 아님: {path}")
    return value


def _nested(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _same_path(left: object, right: object) -> bool:
    if not left or not right:
        return False
    return os.path.normcase(str(Path(str(left)).resolve(strict=False))) == os.path.normcase(
        str(Path(str(right)).resolve(strict=False))
    )


def validate_research_next_year_gate(
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
) -> dict[str, Any]:
    paths = {
        "audit": audit_report,
        "align": align_marker,
        "merge": merge_marker,
        "temp": temp_contract,
        "sample": sample_equivalence_report,
        "review": researcher_review_report,
    }
    data: dict[str, dict[str, Any] | None] = {}
    checks: list[dict[str, str]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "name": name,
                "status": "passed" if passed else "failed",
                "detail": detail,
            }
        )

    for name, path in paths.items():
        try:
            data[name] = _read(path)
            add(f"{name}_readable", True, str(path))
        except Exception as exc:
            data[name] = None
            add(f"{name}_readable", False, f"{type(exc).__name__}: {exc}")

    audit = data["audit"] or {}
    align = data["align"] or {}
    merge = data["merge"] or {}
    temp = data["temp"] or {}
    sample = data["sample"] or {}
    review = data["review"] or {}
    input_ids = {
        str(audit.get("input_contract_id") or ""),
        str(_nested(align, "details", "input_contract_id") or ""),
        str(_nested(merge, "details", "input_contract_id") or ""),
        str(temp.get("input_contract_id") or ""),
        str(sample.get("input_contract_id") or ""),
    }
    alignment_ids = {
        str(audit.get("alignment_contract_id") or ""),
        str(_nested(align, "details", "alignment_contract_id") or ""),
        str(_nested(merge, "details", "alignment_contract_id") or ""),
        str(temp.get("alignment_contract_id") or ""),
        str(sample.get("alignment_contract_id") or ""),
    }
    hard = audit.get("hard_failure_counts")
    add(
        "audit_research_6tier_success",
        audit.get("schema_version") == "mfa_research_6tier_year_audit.v1"
        and audit.get("status") == "success"
        and str(audit.get("year")) == prior_year
        and float(audit.get("coverage_pct", 0)) == 100.0
        and isinstance(hard, dict)
        and all(value == 0 for value in hard.values()),
        f"status={audit.get('status')}, coverage={audit.get('coverage_pct')}",
    )
    add(
        "exact_contract_identity",
        "" not in input_ids
        and len(input_ids) == 1
        and "" not in alignment_ids
        and len(alignment_ids) == 1,
        f"input={sorted(input_ids)}, alignment={sorted(alignment_ids)}",
    )
    add(
        "marker_export_mode",
        _nested(align, "details", "export_mode") == EXPORT_MODE
        and _nested(merge, "details", "export_mode") == EXPORT_MODE
        and align.get("g2p_model") == expected_pronunciation_mode
        and merge.get("g2p_model") == expected_pronunciation_mode,
        f"align={_nested(align, 'details', 'export_mode')}, "
        f"merge={_nested(merge, 'details', 'export_mode')}",
    )
    audit_year_root = Path(str(audit.get("textgrid_root", ""))) / prior_year
    add(
        "final_root_identity",
        _same_path(audit_year_root, expected_final_year_root)
        and expected_final_year_root.is_dir(),
        f"audit={audit_year_root}, expected={expected_final_year_root}",
    )
    search_values = [
        _nested(align, "details", "search_master_root"),
        _nested(merge, "details", "search_master_root"),
        temp.get("search_master_root"),
    ]
    add(
        "search_master_identity",
        expected_search_master_root.is_dir()
        and all(_same_path(value, expected_search_master_root) for value in search_values),
        f"recorded={search_values}",
    )
    db_path = Path(str(_nested(align, "details", "alignment_db") or ""))
    add(
        "retained_alignment_db",
        _nested(merge, "details", "alignment_db_retained") is True
        and db_path.is_file()
        and db_path.stat().st_size > 0
        and temp.get("status") == "direct_merge_completed_temp_retained_for_qc",
        f"db={db_path}, temp_status={temp.get('status')}",
    )
    compared = int(_nested(sample, "comparison_counts", "compared") or 0)
    semantic = int(_nested(sample, "comparison_counts", "semantic_equal") or 0)
    sessions = int(_nested(sample, "selection_counts", "selected_sessions") or 0)
    add(
        "db_sample_equivalence",
        sample.get("schema_version") == "mfa_db_research_6tier_sample_equivalence.v1"
        and sample.get("status") == "success"
        and str(sample.get("year")) == prior_year
        and compared >= 5
        and semantic == compared
        and sessions >= 5
        and _same_path(_nested(sample, "db", "path"), db_path),
        f"compared={compared}, semantic={semantic}, sessions={sessions}",
    )
    review_contract = _nested(review, "year_contracts", prior_year)
    add(
        "researcher_infrastructure_review",
        review.get("schema_version") == "mfa_r2_infrastructure_researcher_review.v1"
        and review.get("status") == "approved"
        and review.get("allow_bulk_mfa") is True
        and review.get("realization_judgment_performed") is False
        and int(_nested(review, "counts", "speakers") or 0) >= 5
        and isinstance(review_contract, dict)
        and review_contract.get("alignment_contract_id") in alignment_ids
        and review_contract.get("lab_input_contract_id") in input_ids
        and _same_path(review_contract.get("database"), db_path),
        f"status={review.get('status')}, contract={review_contract}",
    )
    direct_path = Path(str(_nested(merge, "details", "direct_export_report") or ""))
    try:
        direct = _read(direct_path)
        direct_ok = (
            direct.get("status") == "success"
            and _nested(direct, "exact_id_reconciliation", "status") == "passed"
            and _nested(direct, "exact_id_reconciliation", "full_year_gate") is True
            and _nested(direct, "companion_tables", "status") == "success"
            and direct.get("input_contract_id") in input_ids
            and direct.get("alignment_contract_id") in alignment_ids
        )
        add("direct_export_exact_gate", direct_ok, str(direct_path))
    except Exception as exc:
        add("direct_export_exact_gate", False, f"{type(exc).__name__}: {exc}")

    table_manifest = audit.get("table_manifest")
    add(
        "companion_manifest_contract",
        isinstance(table_manifest, dict)
        and table_manifest.get("status") == "success"
        and table_manifest.get("input_contract_id") in input_ids
        and table_manifest.get("alignment_contract_id") in alignment_ids,
        f"status={_nested(table_manifest, 'status')}",
    )
    failed = [row["name"] for row in checks if row["status"] == "failed"]
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "supported_export_mode": EXPORT_MODE,
        "status": "passed" if not failed else "failed",
        "checked_at": now_iso(),
        "prior_year": prior_year,
        "next_year": next_year,
        "input_contract_id": next(iter(input_ids)) if len(input_ids) == 1 else None,
        "alignment_contract_id": (
            next(iter(alignment_ids)) if len(alignment_ids) == 1 else None
        ),
        "checks": checks,
        "failed_checks": failed,
    }
    atomic_write_json(report_path.resolve(), report)
    return report
