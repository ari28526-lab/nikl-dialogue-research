"""Finalize a direct DB export from a proven failed-pass repair checkpoint.

This skips only the already completed TextGrid validation pass.  It rechecks
the live ID universe and every frozen identity, verifies the exact repair and
archive fingerprints, writes all companion tables, and emits the same success
contract consumed by the annual runner.  The independent annual audit remains
mandatory after promotion.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import export_mfa_db_research_6tier as exporter
from mfa_exclusion_contract import load_contract as load_exclusion_contract
from phoneme_roman import classify_phone, load_acoustic_meta, model_group_lookup
from pipeline_common import atomic_write_json, file_fingerprint
from research_companion_schema import (
    load_schema as load_companion_schema,
    validate_field_order as validate_companion_field_order,
)


def build_reconciliation(
    *,
    db_ids: set[str],
    aligned_ids: set[str],
    active_lab_ids: set[str],
    source_search_ids: set[str],
    alignment_exclusion_ids: set[str],
    analysis_only_ids: set[str],
    quarantine_ids: set[str],
) -> dict[str, object]:
    unapproved_quarantine = quarantine_ids - alignment_exclusion_ids
    unknown_active_missing = active_lab_ids - aligned_ids - alignment_exclusion_ids
    approved_inactive_database_exclusions = (
        db_ids - active_lab_ids
    ) & alignment_exclusion_ids
    unexpected_db_ids = db_ids - active_lab_ids - alignment_exclusion_ids
    approved_upstream_exclusions = alignment_exclusion_ids - active_lab_ids
    approved_active_exclusions = alignment_exclusion_ids & active_lab_ids
    unapproved_source_without_active_lab = (
        source_search_ids - active_lab_ids - alignment_exclusion_ids
    )
    active_lab_ids_outside_source = active_lab_ids - source_search_ids
    approved_exclusion_ids_outside_source = (
        alignment_exclusion_ids - source_search_ids
    )
    invalid_analysis_only = analysis_only_ids - aligned_ids
    hard_sets = {
        "unapproved_quarantine_ids": unapproved_quarantine,
        "unknown_active_lab_without_alignment": unknown_active_missing,
        "db_ids_without_active_lab": unexpected_db_ids,
        "unapproved_source_without_active_lab": unapproved_source_without_active_lab,
        "active_lab_ids_outside_source": active_lab_ids_outside_source,
        "approved_exclusion_ids_outside_source": approved_exclusion_ids_outside_source,
        "analysis_only_ids_without_alignment": invalid_analysis_only,
    }
    return {
        "status": (
            "passed" if all(not values for values in hard_sets.values()) else "failed"
        ),
        "full_year_gate": True,
        "counts": {
            "source_search_ids": len(source_search_ids),
            "active_lab_ids": len(active_lab_ids),
            "database_utterance_ids": len(db_ids),
            "aligned_database_ids": len(aligned_ids),
            "approved_alignment_exclusions": len(alignment_exclusion_ids),
            "approved_analysis_only_exclusions": len(analysis_only_ids),
            "approved_upstream_alignment_exclusions": len(
                approved_upstream_exclusions
            ),
            "approved_active_alignment_exclusions": len(
                approved_active_exclusions
            ),
            "approved_inactive_database_exclusions": len(
                approved_inactive_database_exclusions
            ),
            "quarantine_ids": len(quarantine_ids),
            **{name: len(values) for name, values in hard_sets.items()},
        },
        "inventories": {
            name: sorted(values) for name, values in hard_sets.items()
        },
        "equation": (
            "source_search_ids = active_lab_ids union "
            "approved_upstream_alignment_exclusions; active_lab_ids = "
            "aligned_database_ids union approved_active_alignment_exclusions; "
            "database_utterance_ids subset active_lab_ids union "
            "approved_alignment_exclusions; quarantine_ids subset "
            "approved_alignment_exclusions"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-report", type=Path, required=True)
    parser.add_argument("--repair-manifest", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument(
        "--approved-exclusions-contract", type=Path, required=True
    )
    parser.add_argument("--lab-root", type=Path, required=True)
    parser.add_argument("--quarantine-log", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()

    year = str(args.year)
    db_path = args.db.resolve()
    search_root = args.search_master_root.resolve()
    output_root = args.output_root.resolve()
    acoustic_model = args.acoustic_model.resolve()
    alignment_contract_path = args.alignment_contract.resolve()
    exclusion_path = args.approved_exclusions_contract.resolve()
    contract_id, contract_data = exporter.load_alignment_contract(
        alignment_contract_path, year
    )
    input_contract_id = str(
        contract_data.get("lab_input_contract_id", "") or ""
    ).strip()
    if not input_contract_id:
        raise RuntimeError("alignment contract has no lab_input_contract_id")
    exclusion_data, approved_exclusions = load_exclusion_contract(
        exclusion_path,
        year=year,
        input_contract_id=input_contract_id,
    )
    alignment_exclusion_ids = {
        utt_id
        for utt_id, row in approved_exclusions.items()
        if row["exclusion_scope"] == "alignment_and_analysis"
    }
    analysis_only_ids = set(approved_exclusions) - alignment_exclusion_ids
    quarantine_ids = exporter.load_quarantine_ids(args.quarantine_log)

    groups = model_group_lookup(load_acoustic_meta(acoustic_model))

    def phone_mapper(phone: str) -> str:
        return classify_phone(phone, groups).phone_class_r_auto

    connection = exporter.open_readonly(db_path)
    try:
        if exporter.count_spn_intervals(connection):
            raise RuntimeError("spn intervals present in retained database")
        word_labels, phone_labels = exporter._db_inventory(connection)
        sessions = exporter._sessions(connection)
        db_ids = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT f.name FROM utterance u
                JOIN file f ON f.id=u.file_id
                WHERE u.ignored=0
                """
            )
        }
        aligned_ids = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT f.name FROM utterance u
                JOIN file f ON f.id=u.file_id
                WHERE u.ignored=0
                  AND EXISTS(SELECT 1 FROM word_interval wi
                             WHERE wi.utterance_id=u.id)
                  AND EXISTS(SELECT 1 FROM phone_interval pi
                             WHERE pi.utterance_id=u.id)
                """
            )
        }
        used_phones = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT DISTINCT p.phone FROM phone_interval pi
                JOIN phone p ON p.id=pi.phone_id
                WHERE trim(p.phone) <> ''
                """
            )
            if str(row[0]).strip().lower() not in exporter.SILENCE
        }
    finally:
        connection.close()
    outside = sorted(used_phones - set(groups))
    if outside:
        raise RuntimeError(f"phones outside acoustic inventory: {outside[:10]}")

    active_lab_ids = exporter.load_active_lab_ids(args.lab_root.resolve(), year)
    source_search_ids = exporter.load_search_master_ids(search_root, year)
    reconciliation = build_reconciliation(
        db_ids=db_ids,
        aligned_ids=aligned_ids,
        active_lab_ids=active_lab_ids,
        source_search_ids=source_search_ids,
        alignment_exclusion_ids=alignment_exclusion_ids,
        analysis_only_ids=analysis_only_ids,
        quarantine_ids=quarantine_ids,
    )
    if reconciliation["status"] != "passed":
        raise RuntimeError("current exact ID reconciliation failed")

    totals, examples, max_adjustment, resume_checkpoint = (
        exporter.load_targeted_repair_resume(
            failed_report_path=args.failed_report,
            repair_manifest_path=args.repair_manifest,
            db_path=db_path,
            year=year,
            search_master_root=search_root,
            output_root=output_root,
            acoustic_model=acoustic_model,
            alignment_contract=alignment_contract_path,
            alignment_contract_id=contract_id,
            input_contract_id=input_contract_id,
            reconciliation=reconciliation,
            source_utterance_count=sum(
                len(rows) for _session, rows in sessions
            ),
        )
    )
    print(
        f"[{year}] targeted repair checkpoint accepted: "
        f"repaired={totals['targeted_repaired_existing']:,}",
        flush=True,
    )

    companion_schema_path, companion_schema = load_companion_schema()
    validate_companion_field_order(
        companion_schema,
        {
            "utterances": exporter.UTTERANCE_FIELDS,
            "words": exporter.WORD_FIELDS,
            "phones": exporter.PHONE_FIELDS,
            "excluded": exporter.EXCLUDED_FIELDS,
        },
    )
    tables_manifest = exporter.write_companion_tables(
        db_path=db_path,
        year=year,
        sessions=sessions,
        search_master_root=search_root,
        output_root=output_root,
        word_labels=word_labels,
        phone_labels=phone_labels,
        phone_mapper=phone_mapper,
        alignment_contract_id=contract_id,
        input_contract_id=input_contract_id,
        approved_exclusions=approved_exclusions,
        exclusion_contract_fingerprint=file_fingerprint(
            exclusion_path, with_sha256=True
        ),
        companion_schema_path=companion_schema_path,
        companion_schema=companion_schema,
    )
    if tables_manifest.get("status") != "success":
        raise RuntimeError("companion table manifest did not pass")

    accounted = sum(
        totals[key]
        for key in (
            "created",
            "validated_existing",
            "alignment_missing",
            "search_row_missing",
            "failed",
            "approved_excluded",
        )
    )
    eligible = totals["source_utterances"] - totals["approved_excluded"]
    coverage = round(
        100 * (totals["created"] + totals["validated_existing"]) / eligible,
        4,
    )
    if accounted != totals["source_utterances"] or coverage != 100:
        raise RuntimeError("final repaired export coverage/accounting mismatch")
    previous = json.loads(
        args.failed_report.read_text(encoding="utf-8-sig")
    )
    prior_float32 = previous.get("float32_boundary_normalization") or {}
    result = {
        **previous,
        "status": "success",
        "analysis_ready_status": (
            "ready_with_approved_exclusions"
            if approved_exclusions
            else "ready"
        ),
        "db_path": str(db_path),
        "search_master_root": str(search_root),
        "output_root": str(output_root),
        "alignment_contract": file_fingerprint(
            alignment_contract_path, with_sha256=True
        ),
        "alignment_contract_id": contract_id,
        "input_contract_id": input_contract_id,
        "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        "counts": dict(sorted(totals.items())),
        "accounted": accounted,
        "coverage_pct": coverage,
        "phone_inventory": {
            "used_non_silence": len(used_phones),
            "outside_acoustic": outside,
        },
        "float32_boundary_normalization": {
            **prior_float32,
            "max_adjustment_seconds": max_adjustment,
            "examples": examples[:100],
            "measurement_scope": (
                "in-memory DB endpoints normalized before expected-output "
                "construction; counts do not imply every existing file was rewritten"
            ),
            "existing_files_rewritten_by_targeted_repair": totals[
                "targeted_repaired_existing"
            ],
        },
        "resume_checkpoint": resume_checkpoint,
        "companion_tables": tables_manifest,
        "approved_exclusions_contract": exclusion_data,
        "exact_id_reconciliation": reconciliation,
        "failed_examples": [],
        "search_row_missing_inventory": [],
        "alignment_missing_inventory": [],
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    atomic_write_json(args.report.resolve(), result)
    print(args.report.resolve())
    print(
        f"SUCCESS textgrids={totals['created'] + totals['validated_existing']:,} "
        f"coverage={coverage}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
