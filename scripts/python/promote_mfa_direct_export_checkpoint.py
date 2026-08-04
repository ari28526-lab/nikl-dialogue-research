"""Promote a verified direct-DB MFA export without repeating MFA or LAB scans.

The direct exporter writes a complete year below a contract-specific partial
root.  This module accepts only a successful, full-year report whose frozen
input/alignment identities agree with the retained DB checkpoint.  It verifies
the four compressed companion tables by size and SHA-256, moves the year
directory on the same volume, and writes the normal ``align_done`` and
``merge_done`` markers atomically.

It deliberately does not promote outputs to the canonical research corpus;
the destination remains versioned staging pending independent machine QC and
researcher sampling.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Mapping

from build_mfa_alignment_contract import recompute_alignment_contract_id
from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    git_commit,
    now_iso,
    sha256_file,
)


SCHEMA_VERSION = "mfa_direct_export_checkpoint_promotion.v1"
EXPECTED_TIERS = [
    "words",
    "phones_mfa",
    "phoneme_r_auto",
    "utterance",
    "utterance_orth_r",
    "morph_analysis_utt",
]
EXPECTED_TABLES = {"utterances", "words", "phones", "excluded"}


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def same_path(left: object, right: Path) -> bool:
    try:
        return Path(str(left)).resolve() == right.resolve()
    except (OSError, ValueError, TypeError):
        return False


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_table_files(year_root: Path, manifest: Mapping[str, object]) -> dict:
    table_root = year_root / "_tables"
    stored_tables = manifest.get("tables")
    require(isinstance(stored_tables, dict), "companion tables inventory missing")
    require(set(stored_tables) == EXPECTED_TABLES, "companion table set mismatch")
    verified: dict[str, dict[str, object]] = {}
    for name in sorted(EXPECTED_TABLES):
        record = stored_tables[name]
        require(isinstance(record, dict), f"invalid table record: {name}")
        relative = Path(str(record.get("path", "")))
        require(
            relative.name == str(relative) and relative.suffix == ".gz",
            f"unsafe table path: {relative}",
        )
        path = table_root / relative
        require(path.is_file(), f"companion table missing: {path}")
        size = path.stat().st_size
        require(size == int(record.get("bytes", -1)), f"table size mismatch: {name}")
        digest = sha256_file(path)
        require(digest == str(record.get("sha256", "")), f"table SHA mismatch: {name}")
        verified[name] = {"path": str(path), "bytes": size, "sha256": digest}
    disk_manifest = table_root / "TABLES_MANIFEST.json"
    require(disk_manifest.is_file(), f"TABLES_MANIFEST missing: {disk_manifest}")
    disk_data = load_json(disk_manifest)
    require(disk_data == dict(manifest), "report/disk TABLES_MANIFEST mismatch")
    return {
        "manifest": file_fingerprint(disk_manifest, with_sha256=True),
        "tables": verified,
    }


def marker_matches(path: Path, *, year: str, stage: str, input_id: str, alignment_id: str) -> bool:
    if not path.is_file():
        return False
    value = load_json(path)
    details = value.get("details") or {}
    return (
        str(value.get("year")) == year
        and str(value.get("stage")) == stage
        and str(details.get("input_contract_id", "")) == input_id
        and str(details.get("lab_input_contract_id", "")) == input_id
        and str(details.get("alignment_contract_id", "")) == alignment_id
    )


def promote_checkpoint(
    *,
    project_root: Path,
    year: str,
    export_report_path: Path,
    alignment_contract_path: Path,
    ready_marker_path: Path,
    partial_year: Path,
    final_year: Path,
    align_marker_path: Path,
    merge_marker_path: Path,
    promotion_report_path: Path,
    staging_root: Path,
    existing_final_root: Path,
    input_integrity_report: Path,
    approved_exclusions_contract: Path,
    dry_run: bool = False,
) -> dict:
    require(year in {"2021", "2022", "2023", "2024", "2025"}, "unsupported year")
    export_report_path = export_report_path.resolve()
    alignment_contract_path = alignment_contract_path.resolve()
    ready_marker_path = ready_marker_path.resolve()
    partial_year = partial_year.resolve()
    final_year = final_year.resolve()
    staging_root = staging_root.resolve()
    require(final_year == staging_root / year, "final year is outside frozen staging root")
    require(partial_year.name == year, "partial year directory name mismatch")
    require(partial_year.drive.lower() == final_year.drive.lower(), "promotion must stay on one volume")

    report = load_json(export_report_path)
    alignment = load_json(alignment_contract_path)
    ready = load_json(ready_marker_path)
    integrity = load_json(input_integrity_report.resolve())
    input_id = str(report.get("input_contract_id", ""))
    alignment_id = str(report.get("alignment_contract_id", ""))
    require(report.get("schema_version") == "mfa_research_6tier_export.v1", "export schema mismatch")
    require(report.get("status") == "success", "export report is not successful")
    require(str(report.get("year")) == year, "export year mismatch")
    require(report.get("tier_names") == EXPECTED_TIERS, "6-tier contract mismatch")
    require(float(report.get("coverage_pct", -1)) == 100.0, "export coverage is not 100%")
    counts = report.get("counts") or {}
    require(int(counts.get("failed", 0)) == 0, "export contains failed utterances")
    require(int(counts.get("alignment_missing", 0)) == 0, "export contains missing alignments")
    require(int(counts.get("search_row_missing", 0)) == 0, "export contains missing search rows")
    require(int(counts.get("spn_intervals", 0)) == 0, "export contains spn intervals")
    resume = report.get("resume_checkpoint") or {}
    repair_evidence: dict[str, dict[str, object]] = {}
    for key in (
        "targeted_repair_manifest",
        "subsequent_targeted_repair_manifest",
    ):
        record = resume.get(key)
        if record is None:
            continue
        require(isinstance(record, dict), f"invalid repair evidence: {key}")
        path = Path(str(record.get("path", ""))).resolve()
        require(path.is_file(), f"repair evidence missing: {key}")
        require(
            path.stat().st_size == int(record.get("bytes", -1)),
            f"repair evidence size mismatch: {key}",
        )
        require(
            sha256_file(path) == str(record.get("sha256", "")),
            f"repair evidence SHA mismatch: {key}",
        )
        repair_evidence[key] = file_fingerprint(path, with_sha256=True)
    reconciliation = report.get("exact_id_reconciliation") or {}
    require(
        reconciliation.get("status") == "passed"
        and bool(reconciliation.get("full_year_gate")),
        "exact full-year ID reconciliation not passed",
    )
    require(input_id and alignment_id, "export contract identity missing")
    require(same_path(report.get("output_root"), partial_year.parent), "partial output root mismatch")

    require(alignment.get("schema_version") == "mfa_alignment_contract.v1", "alignment schema mismatch")
    require(alignment.get("status") == "passed", "alignment contract not passed")
    require(str(alignment.get("year")) == year, "alignment year mismatch")
    require(str(alignment.get("lab_input_contract_id", "")) == input_id, "alignment input ID mismatch")
    require(str(alignment.get("alignment_contract_id", "")) == alignment_id, "alignment ID mismatch")
    require(recompute_alignment_contract_id(alignment) == alignment_id, "alignment contract recomputation mismatch")

    ready_details = ready.get("details") or {}
    require(str(ready.get("year")) == year and ready.get("stage") == "direct_db_ready", "DB-ready marker mismatch")
    require(bool(ready_details.get("computation_complete")), "DB computation is not complete")
    require(str(ready_details.get("input_contract_id", "")) == input_id, "DB-ready input ID mismatch")
    require(str(ready_details.get("alignment_contract_id", "")) == alignment_id, "DB-ready alignment ID mismatch")
    db_path = Path(str(ready_details.get("alignment_db", ""))).resolve()
    require(db_path.is_file(), f"retained alignment DB missing: {db_path}")
    require(same_path(report.get("db_path"), db_path), "report/DB-ready database mismatch")
    search_root = Path(str(ready_details.get("search_master_root", ""))).resolve()
    require(search_root.is_dir(), f"frozen search master missing: {search_root}")
    require(same_path(report.get("search_master_root"), search_root), "report/DB-ready search root mismatch")
    require(same_path(integrity.get("search_master_root"), search_root), "input-audit search root mismatch")
    retained = integrity.get("retained_db_checkpoint") or {}
    require(str(retained.get("status", "")) == "validated", "input-audit retained DB not validated")
    require(str(retained.get("input_contract_id", "")) == input_id, "input-audit input ID mismatch")
    require(str(retained.get("alignment_contract_id", "")) == alignment_id, "input-audit alignment ID mismatch")
    require(same_path(retained.get("alignment_db"), db_path), "input-audit database mismatch")

    integrity_years = [
        row
        for row in (integrity.get("years") or [])
        if isinstance(row, dict) and str(row.get("year")) == year
    ]
    require(bool(integrity.get("all_years_pass")), "input integrity report not passed")
    require(len(integrity_years) == 1, "input integrity year record mismatch")
    integrity_year = integrity_years[0]
    require(bool(integrity_year.get("execution_gates_pass")), "input execution gate not passed")
    require(bool(integrity_year.get("analysis_ready_gates_pass")), "input analysis-ready gate not passed")

    partial_exists = partial_year.is_dir()
    final_exists = final_year.is_dir()
    require(not (partial_exists and final_exists), "partial and final year both exist")
    require(partial_exists or final_exists, "neither partial nor final year exists")
    active_year_root = partial_year if partial_exists else final_year
    require(not any(active_year_root.rglob("*.partial")), "stale partial files remain in year output")
    companion = report.get("companion_tables") or {}
    require(companion.get("status") == "success", "companion table manifest not successful")
    require(str(companion.get("year")) == year, "companion table year mismatch")
    require(str(companion.get("input_contract_id", "")) == input_id, "companion input ID mismatch")
    require(str(companion.get("alignment_contract_id", "")) == alignment_id, "companion alignment ID mismatch")
    exclusion_record = companion.get("approved_exclusions_contract") or {}
    approved_exclusions_contract = approved_exclusions_contract.resolve()
    require(approved_exclusions_contract.is_file(), "approved export exclusions missing")
    require(
        same_path(exclusion_record.get("path"), approved_exclusions_contract),
        "approved export exclusions path mismatch",
    )
    require(
        approved_exclusions_contract.stat().st_size
        == int(exclusion_record.get("bytes", -1)),
        "approved export exclusions size mismatch",
    )
    require(
        sha256_file(approved_exclusions_contract)
        == str(exclusion_record.get("sha256", "")),
        "approved export exclusions SHA mismatch",
    )
    table_verification = verify_table_files(active_year_root, companion)

    textgrid_count = int(counts.get("created", 0)) + int(counts.get("validated_existing", 0))
    lab_count = int((reconciliation.get("counts") or {}).get("active_lab_ids", 0))
    require(textgrid_count > 0 and lab_count > 0, "non-positive TextGrid/LAB count")
    require(textgrid_count == int((companion.get("counts") or {}).get("utterances", -1)), "TextGrid/table utterance count mismatch")

    common_details = {
        "input_contract_id": input_id,
        "lab_input_contract_id": input_id,
        "alignment_contract_id": alignment_id,
        "mfa_runtime": alignment.get("runtime"),
        "mfa_models": alignment.get("models"),
        "search_master_root": ready_details.get("search_master_root"),
    }
    tier_provenance = {
        "words": "mfa_db.word_interval",
        "phones_mfa": "mfa_db.phone_interval",
        "phoneme_r_auto": "phones_mfa_only",
        "utterance": "frozen_search_master.form",
        "utterance_orth_r": "deterministic orth_roman_v2(form); mixed literals preserved",
        "morph_analysis_utt": "frozen_search_master.tagged_whole_span",
    }
    integrity_value = str(input_integrity_report.resolve())
    integrity_counts = integrity_year.get("counts") or {}
    align_details = {
        **common_details,
        "textgrids": textgrid_count,
        "labs": lab_count,
        "coverage_pct": 100.0,
        "export_mode": "direct_db_research_6tier_v1_checkpoint_resume",
        "alignment_db": str(db_path),
        "input_integrity_report": integrity_value,
        "input_integrity_gate_profile": str(integrity.get("gate_profile", "")),
        "input_integrity_execution_gates_pass": True,
        "input_integrity_analysis_ready_gates_pass": True,
        "morph_source_missing": int(integrity_counts.get("morph_source_missing", 0) or 0),
        "morph_source_unclassified": int(integrity_counts.get("morph_source_unclassified", 0) or 0),
        "tier_provenance": tier_provenance,
        "direct_export_report": str(export_report_path),
        "checkpoint_promotion_report": str(promotion_report_path.resolve()),
    }
    merge_details = {
        **common_details,
        "export_mode": "direct_db_research_6tier_v1_checkpoint_resume",
        "direct_export_report": str(export_report_path),
        "staging_output_root": str(staging_root),
        "existing_final_root": str(existing_final_root.resolve()),
        "promotion_required": True,
        "raw_mfa_textgrid_duplicated": False,
        "alignment_db_retained": True,
        "input_integrity_report": integrity_value,
        "input_integrity_gate_profile": str(integrity.get("gate_profile", "")),
        "input_integrity_execution_gates_pass": True,
        "input_integrity_analysis_ready_gates_pass": True,
        "morph_source_missing": int(integrity_counts.get("morph_source_missing", 0) or 0),
        "morph_source_unclassified": int(integrity_counts.get("morph_source_unclassified", 0) or 0),
        "tier_provenance": tier_provenance,
        "checkpoint_promotion_report": str(promotion_report_path.resolve()),
    }
    completed_at = now_iso()
    commit = git_commit(project_root.resolve())
    align_payload = {
        "year": year,
        "stage": "align",
        "g2p_model": "common_pron_mfa_r2_latest_jamo",
        "completed_at": completed_at,
        "git_commit": commit,
        "details": align_details,
    }
    merge_payload = {
        "year": year,
        "stage": "merge",
        "g2p_model": "common_pron_mfa_r2_latest_jamo",
        "completed_at": completed_at,
        "git_commit": commit,
        "details": merge_details,
    }
    for marker_path, stage in ((align_marker_path, "align"), (merge_marker_path, "merge")):
        if marker_path.exists():
            require(
                marker_matches(marker_path, year=year, stage=stage, input_id=input_id, alignment_id=alignment_id),
                f"existing {stage} marker identity mismatch",
            )

    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed" if dry_run else "pending",
        "year": year,
        "input_contract_id": input_id,
        "alignment_contract_id": alignment_id,
        "source_state": "partial" if partial_exists else "already_moved",
        "paths": {
            "partial_year": str(partial_year),
            "final_year": str(final_year),
            "export_report": str(export_report_path),
            "alignment_contract": str(alignment_contract_path),
            "direct_db_ready": str(ready_marker_path),
            "align_marker": str(align_marker_path.resolve()),
            "merge_marker": str(merge_marker_path.resolve()),
            "input_integrity_report": str(input_integrity_report.resolve()),
            "approved_exclusions_contract": str(
                approved_exclusions_contract
            ),
        },
        "evidence": {
            "export_report": file_fingerprint(export_report_path, with_sha256=True),
            "alignment_contract": file_fingerprint(alignment_contract_path, with_sha256=True),
            "direct_db_ready": file_fingerprint(ready_marker_path, with_sha256=True),
            "input_integrity_report": file_fingerprint(
                input_integrity_report.resolve(), with_sha256=True
            ),
            "approved_exclusions_contract": file_fingerprint(
                approved_exclusions_contract, with_sha256=True
            ),
            "repair_manifests": repair_evidence,
        },
        "counts": {"textgrids": textgrid_count, "active_labs": lab_count},
        "table_verification": table_verification,
        "dry_run": dry_run,
        "recorded_at": now_iso(),
        "git_commit": commit,
    }
    if dry_run:
        atomic_write_json(promotion_report_path.resolve(), result)
        return result

    if partial_exists:
        final_year.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial_year, final_year)
    require(final_year.is_dir() and not partial_year.exists(), "year directory promotion failed")
    if not align_marker_path.exists():
        atomic_write_json(align_marker_path.resolve(), align_payload)
    if not merge_marker_path.exists():
        atomic_write_json(merge_marker_path.resolve(), merge_payload)
    result["status"] = "success"
    result["promoted_at"] = now_iso()
    result["final_year"] = file_fingerprint(final_year / "_tables" / "TABLES_MANIFEST.json", with_sha256=True)
    atomic_write_json(promotion_report_path.resolve(), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--export-report", type=Path, required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument("--direct-db-ready", type=Path, required=True)
    parser.add_argument("--partial-year", type=Path, required=True)
    parser.add_argument("--final-year", type=Path, required=True)
    parser.add_argument("--align-marker", type=Path, required=True)
    parser.add_argument("--merge-marker", type=Path, required=True)
    parser.add_argument("--promotion-report", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--existing-final-root", type=Path, required=True)
    parser.add_argument("--input-integrity-report", type=Path, required=True)
    parser.add_argument(
        "--approved-exclusions-contract", type=Path, required=True
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = promote_checkpoint(
        project_root=args.project_root,
        year=args.year,
        export_report_path=args.export_report,
        alignment_contract_path=args.alignment_contract,
        ready_marker_path=args.direct_db_ready,
        partial_year=args.partial_year,
        final_year=args.final_year,
        align_marker_path=args.align_marker,
        merge_marker_path=args.merge_marker,
        promotion_report_path=args.promotion_report,
        staging_root=args.staging_root,
        existing_final_root=args.existing_final_root,
        input_integrity_report=args.input_integrity_report,
        approved_exclusions_contract=args.approved_exclusions_contract,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
