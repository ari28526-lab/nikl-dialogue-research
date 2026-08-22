"""Build the bounded, year-balanced PV-A sample and logical review events.

The script reuses the existing declarative query matcher and RC0/RC1 asset-row
builder, but adds the researcher-approved hard *row* cap.  It materializes one
physical package per occurrence and separate logical review events for VH/HIA.
No acoustic realization is inferred.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from build_db_v1_target_manifest import (
    build_rows as build_asset_rows,
    row_matches,
)
from link_db_v1_target_intervals import (
    nonempty_words,
    resolve_boundary_span,
    validate_word_sequence,
)
from pipeline_common import sha256_file
from pv_preview_common import (
    DEFAULT_ACTIVE_VIEW_ROOT,
    DEFAULT_CONFIG,
    DEFAULT_MORPH_ROOT,
    DEFAULT_R3_ROOT,
    DEFAULT_RC0_ROOT,
    PHENOMENON_LABELS,
    PROJECT_ROOT,
    annual_primary_quotas,
    annual_table_contract,
    atomic_write_csv,
    atomic_write_json,
    atomic_write_text,
    base_build_receipt,
    capped_rows_by_id_allow_missing,
    count_by,
    load_json,
    physical_occurrence_ref,
    read_active_exceptions,
    require_under,
    scope_quotas,
    session_from_utt,
    source_receipt,
    stable_rank,
    validate_config,
    validate_header,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


CANDIDATE_FIELDS = [
    "candidate_row_id",
    "pv_query_id",
    "source_query_id",
    "query_role",
    "phenomenon_code",
    "environment_scope",
    "year",
    "utt_id",
    "session_id",
    "speaker_id",
    "matched_table",
    "occurrence_index",
    "physical_occurrence_ref",
    "membership_codes_json",
    "active_form",
    "wav_path",
    "active_textgrid_path",
    "inclusion_status",
    "match_evidence_json",
    "selection_status",
    "selected_pv_id",
    "selection_note",
]

SAMPLE_FIELDS = [
    "pv_id",
    "primary_phenomenon_code",
    "primary_phenomenon_label",
    "phenomenon_memberships_json",
    "review_event_ids_json",
    "pv_query_id",
    "source_query_id",
    "query_role",
    "environment_scope",
    "requested_scope",
    "scope_reallocation_status",
    "year",
    "utt_id",
    "session_id",
    "speaker_id",
    "physical_occurrence_ref",
    "matched_table",
    "occurrence_index",
    "active_form",
    "active_form_source",
    "wav_path",
    "active_textgrid_path",
    "inclusion_status",
    "target_xmin",
    "target_xmax",
    "timing_status",
    "target_word_indices_json",
    "target_word_labels_json",
    "textgrid_words_tier_count",
    "active_textgrid_sha256",
    "timing_method",
    "timing_notes",
    "match_evidence_json",
    "interpretation_limit",
]

EVENT_FIELDS = [
    "review_event_id",
    "pv_id",
    "phenomenon_code",
    "phenomenon_label",
    "is_primary_phenomenon",
    "pv_query_ids_json",
    "environment_scope",
    "year",
    "utt_id",
    "physical_occurrence_ref",
    "record_role",
]

UNIVERSAL_REALIZATION_INTERPRETATION_LIMIT = (
    "PV-A environment preview only; not an automatic realization judgement."
)


def ni_source_root(year: int) -> Path:
    stage = "g3" if year == 2020 else "g4"
    return (
        PROJECT_ROOT
        / "outputs"
        / "candidates"
        / f"n_insertion_v1_{year}_{stage}_20260818"
    )


def scan_declarative_queries(
    *, config: Mapping[str, Any], morph_root: Path
) -> tuple[list[tuple[dict[str, Any], dict[str, str]]], list[dict[str, Any]]]:
    row_cap = int(config["safety"]["max_rows_scanned_per_table_year"])
    global_candidate_cap = int(
        config["safety"]["max_materialized_candidates_per_query_year"]
    )
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for query in config["queries"]:
        for year in query["years"]:
            grouped[(int(year), str(query["source_table"]))].append(dict(query))
    materialized: list[tuple[dict[str, Any], dict[str, str]]] = []
    receipts: list[dict[str, Any]] = []
    for (year, table), queries in sorted(grouped.items()):
        path, record, annual_manifest = annual_table_contract(morph_root, year, table)
        measured_header = validate_header(path, table)
        counts: dict[str, int] = defaultdict(int)
        matches_seen_before_query_cap: dict[str, int] = defaultdict(int)
        rows_scanned = 0
        stop_reason = "hard_row_cap"
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                rows_scanned += 1
                for query in queries:
                    query_id = str(query["query_id"])
                    limit = min(
                        int(query.get("max_occurrences_per_year", 0) or 0),
                        global_candidate_cap,
                    )
                    if counts[query_id] >= limit:
                        continue
                    if not row_matches(row, query["conditions"]):
                        continue
                    matches_seen_before_query_cap[query_id] += 1
                    copied = dict(row)
                    copied["__year"] = str(year)
                    materialized.append((query, copied))
                    counts[query_id] += 1
                if all(
                    counts[str(query["query_id"])]
                    >= min(
                        int(query.get("max_occurrences_per_year", 0) or 0),
                        global_candidate_cap,
                    )
                    for query in queries
                ):
                    stop_reason = "all_query_candidate_caps_reached"
                    break
                if rows_scanned >= row_cap:
                    break
        receipt = source_receipt(
            path,
            record,
            annual_manifest,
            rows_scanned=rows_scanned,
            stopped_at_row_cap=rows_scanned >= row_cap,
        )
        receipt.update(
            {
                "year": year,
                "table": table,
                "measured_header": measured_header,
                "materialized_candidate_counts": dict(sorted(counts.items())),
                "matches_seen_before_query_cap": dict(
                    sorted(matches_seen_before_query_cap.items())
                ),
                "stop_reason": stop_reason,
            }
        )
        receipts.append(receipt)
    return materialized, receipts


def load_internal_candidates(path: Path) -> list[tuple[dict[str, Any], dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    result = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "query_id",
            "phenomenon_code",
            "year",
            "utt_id",
            "occurrence_index",
            "match_evidence_json",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"internal candidate fields missing: {sorted(missing)}")
        for row in reader:
            evidence = json.loads(row["match_evidence_json"])
            hit = {
                **{key: str(value) for key, value in evidence.items()},
                "utt_id": row["utt_id"],
                "internal_pair_index": row["occurrence_index"],
                "__year": row["year"],
            }
            query = {
                "query_id": row["query_id"],
                "query_version": int(row.get("query_version", "1")),
                "query_role": "preview_environment_sweep",
                "phenomenon_code": row["phenomenon_code"],
                "environment_scope": "morph_internal",
                "source_table": "morph_units",
                "occurrence_index_field": "internal_pair_index",
                "interpretation": (
                    "Adjacent Hangul syllables inside one Bareun morpheme; "
                    "environment preview only, not a realization judgement."
                ),
            }
            result.append((query, hit))
    if not result:
        raise RuntimeError("internal candidate input is empty")
    return result


def materialize_asset_rows(
    *,
    query_hits: list[tuple[dict[str, Any], dict[str, str]]],
    config: Mapping[str, Any],
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
) -> tuple[
    list[tuple[dict[str, Any], dict[str, Any]]],
    list[dict[str, Any]],
]:
    row_cap = int(config["safety"]["max_rows_scanned_per_table_year"])
    ids_by_year: dict[int, set[str]] = defaultdict(set)
    for _, hit in query_hits:
        ids_by_year[int(hit["__year"])].add(hit["utt_id"])
    masters: dict[str, dict[str, str]] = {}
    ledgers: dict[str, dict[str, str]] = {}
    lookup_receipts: list[dict[str, Any]] = []
    for year, identifiers in sorted(ids_by_year.items()):
        master_path, _, _ = annual_table_contract(
            morph_root, year, "utterance_master_v2"
        )
        selected, master_rows_scanned, missing_master = capped_rows_by_id_allow_missing(
            master_path, identifiers, max_rows=row_cap
        )
        masters.update(selected)
        ledger_path = rc0_root / "ledgers" / f"{year}_utterance_status.csv.gz"
        selected_ledger, ledger_rows_scanned, missing_ledger = (
            capped_rows_by_id_allow_missing(
            ledger_path, identifiers, max_rows=row_cap
            )
        )
        ledgers.update(selected_ledger)
        lookup_receipts.extend(
            [
                {
                    "year": year,
                    "table": "utterance_master_v2_selected_id_lookup",
                    "path": str(master_path),
                    "rows_scanned": master_rows_scanned,
                    "requested_ids": len(identifiers),
                    "found_ids": len(selected),
                    "missing_ids_retained_with_status": len(missing_master),
                    "scan_stopped_at_hard_row_cap": master_rows_scanned >= row_cap,
                },
                {
                    "year": year,
                    "table": "rc0_utterance_status_selected_id_lookup",
                    "path": str(ledger_path),
                    "rows_scanned": ledger_rows_scanned,
                    "requested_ids": len(identifiers),
                    "found_ids": len(selected_ledger),
                    "missing_ids_retained_with_status": len(missing_ledger),
                    "scan_stopped_at_hard_row_cap": ledger_rows_scanned >= row_cap,
                },
            ]
        )
    active_exceptions = read_active_exceptions(active_view_root)
    query_set = {
        "study_id": config["study_id"],
        "query_set_id": config["query_set_id"],
    }
    grouped: dict[str, tuple[dict[str, Any], list[dict[str, str]]]] = {}
    for query, hit in query_hits:
        query_id = str(query["query_id"])
        grouped.setdefault(query_id, (query, []))[1].append(hit)
    result: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for query_id in sorted(grouped):
        query, hits = grouped[query_id]
        ready_hits = [
            hit
            for hit in hits
            if hit["utt_id"] in masters and hit["utt_id"] in ledgers
        ]
        rows = build_asset_rows(
            query_set=query_set,
            query=query,
            hits=ready_hits,
            masters=masters,
            ledgers=ledgers,
            active_exceptions=active_exceptions,
            r3_root=r3_root,
        )
        result.extend((query, row) for row in rows)
        for hit in hits:
            utt_id = hit["utt_id"]
            if utt_id in masters and utt_id in ledgers:
                continue
            year = int(hit["__year"])
            master = masters.get(utt_id, {})
            session_id = master.get("session_id") or session_from_utt(utt_id)
            occurrence_index = str(hit.get(query["occurrence_index_field"], ""))
            missing_parts = []
            if utt_id not in masters:
                missing_parts.append("utterance_master_v2")
            if utt_id not in ledgers:
                missing_parts.append("rc0_utterance_status")
            fallback = {
                "study_id": config["study_id"],
                "query_set_id": config["query_set_id"],
                "query_id": query["query_id"],
                "query_version": query["query_version"],
                "query_role": query["query_role"],
                "year": year,
                "utt_id": utt_id,
                "target_occurrence_id": (
                    f"{query['query_id']}:{year}:{utt_id}:{occurrence_index}"
                ),
                "matched_table": query["source_table"],
                "occurrence_index": occurrence_index,
                "session_id": session_id,
                "speaker_id": master.get("speaker_id", ""),
                "base_form": master.get("form", ""),
                "active_form": master.get("form", ""),
                "active_form_source": "base_metadata_only",
                "wav_path": str(
                    r3_root / "corpus" / str(year) / session_id / f"{utt_id}.wav"
                ),
                "base_textgrid_path": "",
                "curated_textgrid_path": "",
                "active_textgrid_path": "",
                "target_xmin": "",
                "target_xmax": "",
                "timing_status": "not_linked_release_lookup_missing",
                "quality_flags_json": json.dumps(
                    [f"missing_capped_lookup:{part}" for part in missing_parts],
                    ensure_ascii=False,
                ),
                "inclusion_status": (
                    "candidate_metadata_only_missing_capped_release_lookup"
                ),
                "interpretation_limit": query["interpretation"],
                "match_evidence_json": json.dumps(
                    {key: value for key, value in hit.items() if not key.startswith("__")},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
            result.append((query, fallback))
    return result, lookup_receipts


def load_ni_candidates(
    *, config: Mapping[str, Any]
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
    row_cap = int(config["safety"]["max_rows_scanned_per_table_year"])
    candidate_cap = int(
        config["safety"]["max_materialized_candidates_per_query_year"]
    )
    mapping = config["n_insertion_source"]["query_map"]
    expected_query_sha = config["n_insertion_source"]["query_set_sha256"]
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    receipts: list[dict[str, Any]] = []
    for year in config["pilot_allocation"]["years"]:
        year = int(year)
        root = ni_source_root(year)
        manifest_path = root / "TARGET_MANIFEST_BUILD.json"
        manifest = load_json(manifest_path)
        if manifest.get("status") != "pilot_candidates_built_no_realization_judgement":
            raise RuntimeError(f"unexpected frozen NI candidate status: {year}")
        if manifest.get("query_set_sha256") != expected_query_sha:
            raise RuntimeError(f"frozen NI query SHA mismatch: {year}")
        path = root / "TARGET_CANDIDATES.csv"
        declared = next(
            item for item in manifest["files"] if item["path"] == path.name
        )
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"frozen NI candidate byte mismatch: {path}")
        measured_sha256 = sha256_file(path)
        if measured_sha256 != declared["sha256"]:
            raise RuntimeError(f"frozen NI candidate SHA-256 mismatch: {path}")
        counts: dict[str, int] = defaultdict(int)
        seen_sessions: dict[str, set[str]] = defaultdict(set)
        rows_scanned = 0
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for source in reader:
                rows_scanned += 1
                source_query_id = source["query_id"]
                spec = mapping.get(source_query_id)
                if spec and counts[source_query_id] < candidate_cap:
                    session_id = source["session_id"]
                    if session_id not in seen_sessions[source_query_id]:
                        seen_sessions[source_query_id].add(session_id)
                        query = {
                            "query_id": spec["pv_query_id"],
                            "source_query_id": source_query_id,
                            "query_version": 1,
                            "query_role": "preview_environment_sweep",
                            "phenomenon_code": "NI",
                            "environment_scope": spec["environment_scope"],
                            "source_table": "morph_boundaries",
                            "interpretation": (
                                "Sampled from frozen n-insertion G3/G4 candidate "
                                "output; environment only, no realization judgement."
                            ),
                        }
                        copied = dict(source)
                        copied["query_id"] = spec["pv_query_id"]
                        copied["query_role"] = "preview_environment_sweep"
                        rows.append((query, copied))
                        counts[source_query_id] += 1
                if all(counts[key] >= candidate_cap for key in mapping):
                    break
                if rows_scanned >= row_cap:
                    break
        receipts.append(
            {
                "year": year,
                "table": "frozen_n_insertion_candidates",
                "path": str(path),
                "bytes": path.stat().st_size,
                "declared_sha256": declared["sha256"],
                "measured_sha256": measured_sha256,
                "build_manifest_path": str(manifest_path),
                "build_manifest_sha256": sha256_file(manifest_path),
                "rows_scanned": rows_scanned,
                "scan_stopped_at_hard_row_cap": rows_scanned >= row_cap,
                "materialized_candidate_counts": dict(sorted(counts.items())),
            }
        )
    return rows, receipts


def unified_candidate(
    query: Mapping[str, Any], row: Mapping[str, Any], sequence: int
) -> dict[str, Any]:
    year = int(row["year"])
    table = str(row.get("matched_table") or query.get("source_table"))
    if table == "morph_units":
        physical_table = "morph_units_pair"
    else:
        physical_table = table
    occurrence_index = str(row["occurrence_index"])
    ref = physical_occurrence_ref(
        physical_table, year, str(row["utt_id"]), occurrence_index
    )
    source_query_id = str(query.get("source_query_id", query["query_id"]))
    return {
        **dict(row),
        "candidate_row_id": f"C{sequence:06d}",
        "pv_query_id": str(query["query_id"]),
        "source_query_id": source_query_id,
        "query_role": "preview_environment_sweep",
        "phenomenon_code": str(query["phenomenon_code"]),
        "environment_scope": str(query["environment_scope"]),
        "year": str(year),
        "physical_occurrence_ref": ref,
        "selection_status": "not_selected_pending_allocation",
        "selected_pv_id": "",
        "selection_note": "",
    }


def infer_memberships(group: list[dict[str, Any]]) -> list[str]:
    memberships = {str(row["phenomenon_code"]) for row in group}
    if "HIA" in memberships:
        memberships.add("VH")
    for row in group:
        if row["environment_scope"] == "orth_contraction_probe" and row[
            "phenomenon_code"
        ] in {"VH", "HIA"}:
            memberships.update({"VH", "HIA"})
        if row["phenomenon_code"] == "VH":
            evidence = json.loads(row["match_evidence_json"])
            if evidence.get("left_coda_jamo") == "":
                memberships.add("HIA")
    order = list(PHENOMENON_LABELS)
    return sorted(memberships, key=order.index)


def candidate_ready(row: Mapping[str, Any]) -> bool:
    return (
        row.get("inclusion_status")
        == "candidate_ready_for_manual_realization_review"
        and Path(str(row.get("wav_path", ""))).is_file()
        and Path(str(row.get("active_textgrid_path", ""))).is_file()
    )


def choose_rows(
    candidates: list[dict[str, Any]],
    *,
    count: int,
    year: int,
    phenomenon: str,
    seed: str,
    used_refs: set[str],
    used_sessions: set[str],
    timing_ready_cache: dict[str, bool],
) -> list[dict[str, Any]]:
    available = [
        row for row in candidates if row["physical_occurrence_ref"] not in used_refs
    ]
    available.sort(
        key=lambda row: (
            not candidate_ready(row),
            row["session_id"] in used_sessions,
            phenomenon == "VH"
            and json.loads(row["membership_codes_json"]) != ["VH"],
            stable_rank(
                seed,
                year,
                phenomenon,
                row["physical_occurrence_ref"],
            ),
        )
    )
    selected: list[dict[str, Any]] = []
    for row in available:
        if len(selected) >= count:
            break
        if not candidate_ready(row):
            continue
        ref = str(row["physical_occurrence_ref"])
        if ref not in timing_ready_cache:
            timing_ready_cache[ref] = str(
                link_selected_time(dict(row)).get("timing_status", "")
            ).startswith("linked_")
        if not timing_ready_cache[ref]:
            continue
        selected.append(row)
        used_refs.add(row["physical_occurrence_ref"])
        used_sessions.add(row["session_id"])
    return selected


def link_selected_time(row: dict[str, Any]) -> dict[str, Any]:
    linked = dict(row)
    for field in (
        "target_word_indices_json",
        "target_word_labels_json",
        "textgrid_words_tier_count",
        "active_textgrid_sha256",
        "timing_method",
        "timing_notes",
    ):
        linked[field] = ""
    textgrid_path = Path(str(row.get("active_textgrid_path", "")))
    if not textgrid_path.is_file():
        linked["timing_status"] = "pending_textgrid_asset_unavailable"
        linked["timing_notes"] = "selected occurrence retained; target time not claimed"
        return linked
    try:
        words = validate_word_sequence(
            str(row["active_form"]), nonempty_words(textgrid_path)
        )
        evidence = json.loads(str(row["match_evidence_json"]))
        if "left_eojeol_idx" not in evidence:
            index = evidence.get("eojeol_idx") or evidence.get("orth_eojeol_idx")
            if not index:
                raise RuntimeError("eojeol index absent from selected evidence")
            evidence["left_eojeol_idx"] = index
            evidence["right_eojeol_idx"] = index
            evidence["boundary_scope"] = row["environment_scope"]
        timing = resolve_boundary_span(words, evidence)
        linked.update({key: str(value) for key, value in timing.items()})
        linked["textgrid_words_tier_count"] = str(len(words))
        linked["active_textgrid_sha256"] = sha256_file(textgrid_path)
    except Exception as exc:
        linked["timing_status"] = "pending_textgrid_word_mapping_review"
        linked["timing_notes"] = f"{type(exc).__name__}: {exc}"
    return linked


def allocate_samples(
    *, config: Mapping[str, Any], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    order = list(config["pilot_allocation"]["phenomenon_order"])
    seed = str(config["pilot_allocation"]["selection_seed"])
    by_ref: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_ref[row["physical_occurrence_ref"]].append(row)
    physical: list[dict[str, Any]] = []
    for ref, group in sorted(by_ref.items()):
        memberships = infer_memberships(group)
        for row in group:
            row["membership_codes_json"] = json.dumps(
                memberships, ensure_ascii=False
            )
        representative = min(group, key=lambda row: row["candidate_row_id"])
        physical.append(
            {
                **representative,
                "membership_codes_json": json.dumps(
                    memberships, ensure_ascii=False
                ),
                "member_rows": group,
            }
        )
    selected_specs: list[dict[str, Any]] = []
    allocation_rows: list[dict[str, Any]] = []
    shortfalls: list[dict[str, Any]] = []
    for year in config["pilot_allocation"]["years"]:
        year = int(year)
        quotas = annual_primary_quotas(config, year)
        used_refs: set[str] = set()
        used_sessions: set[str] = set()
        timing_ready_cache: dict[str, bool] = {}
        for phenomenon in order:
            total = quotas[phenomenon]
            weights = config["pilot_allocation"]["scope_weights"][phenomenon]
            desired = scope_quotas(
                weights, total, rotation=(year - 2020 + order.index(phenomenon))
            )
            eligible = [
                row
                for row in physical
                if int(row["year"]) == year
                and phenomenon in json.loads(row["membership_codes_json"])
            ]
            phenomenon_selected: list[dict[str, Any]] = []
            for scope, requested in desired.items():
                scope_rows = [
                    row for row in eligible if row["environment_scope"] == scope
                ]
                chosen = choose_rows(
                    scope_rows,
                    count=requested,
                    year=year,
                    phenomenon=phenomenon,
                    seed=seed,
                    used_refs=used_refs,
                    used_sessions=used_sessions,
                    timing_ready_cache=timing_ready_cache,
                )
                for row in chosen:
                    phenomenon_selected.append(
                        {
                            **row,
                            "primary_phenomenon_code": phenomenon,
                            "requested_scope": scope,
                            "scope_reallocation_status": "as_requested",
                        }
                    )
                allocation_rows.append(
                    {
                        "year": year,
                        "phenomenon_code": phenomenon,
                        "requested_scope": scope,
                        "requested": requested,
                        "selected_as_requested": len(chosen),
                    }
                )
            remaining = total - len(phenomenon_selected)
            if remaining:
                chosen = choose_rows(
                    eligible,
                    count=remaining,
                    year=year,
                    phenomenon=phenomenon,
                    seed=seed,
                    used_refs=used_refs,
                    used_sessions=used_sessions,
                    timing_ready_cache=timing_ready_cache,
                )
                for row in chosen:
                    phenomenon_selected.append(
                        {
                            **row,
                            "primary_phenomenon_code": phenomenon,
                            "requested_scope": "reallocated_within_phenomenon",
                            "scope_reallocation_status": "within_phenomenon",
                        }
                    )
            if len(phenomenon_selected) != total:
                shortfalls.append(
                    {
                        "year": year,
                        "phenomenon_code": phenomenon,
                        "requested": total,
                        "selected": len(phenomenon_selected),
                        "missing": total - len(phenomenon_selected),
                    }
                )
            selected_specs.extend(phenomenon_selected)
    selected_specs.sort(
        key=lambda row: (
            int(row["year"]),
            order.index(row["primary_phenomenon_code"]),
            stable_rank(seed, row["physical_occurrence_ref"]),
        )
    )
    selected: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    selected_by_ref: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(selected_specs, 1):
        pv_id = f"PV{index:04d}"
        phenomenon = item["primary_phenomenon_code"]
        member_rows: list[dict[str, Any]] = item["member_rows"]
        memberships = json.loads(item["membership_codes_json"])
        representative_options = [
            row for row in member_rows if row["phenomenon_code"] == phenomenon
        ] or member_rows
        representative = min(
            representative_options,
            key=lambda row: stable_rank(seed, phenomenon, row["candidate_row_id"]),
        )
        query_ids_by_membership = {
            code: sorted(
                {
                    row["pv_query_id"]
                    for row in member_rows
                    if row["phenomenon_code"] == code
                }
                or {representative["pv_query_id"]}
            )
            for code in memberships
        }
        event_ids = [f"{pv_id}__{code}" for code in memberships]
        sample = link_selected_time(
            {
                **representative,
                "pv_id": pv_id,
                "primary_phenomenon_code": phenomenon,
                "primary_phenomenon_label": PHENOMENON_LABELS[phenomenon],
                "phenomenon_memberships_json": json.dumps(
                    memberships, ensure_ascii=False
                ),
                "review_event_ids_json": json.dumps(event_ids, ensure_ascii=False),
                "requested_scope": item["requested_scope"],
                "scope_reallocation_status": item[
                    "scope_reallocation_status"
                ],
                "interpretation_limit": (
                    str(representative.get("interpretation_limit", "")).strip()
                    + " "
                    + UNIVERSAL_REALIZATION_INTERPRETATION_LIMIT
                ).strip(),
            }
        )
        selected.append(sample)
        selected_by_ref[item["physical_occurrence_ref"]] = sample
        for code in memberships:
            events.append(
                {
                    "review_event_id": f"{pv_id}__{code}",
                    "pv_id": pv_id,
                    "phenomenon_code": code,
                    "phenomenon_label": PHENOMENON_LABELS[code],
                    "is_primary_phenomenon": str(code == phenomenon),
                    "pv_query_ids_json": json.dumps(
                        query_ids_by_membership[code], ensure_ascii=False
                    ),
                    "environment_scope": sample["environment_scope"],
                    "year": sample["year"],
                    "utt_id": sample["utt_id"],
                    "physical_occurrence_ref": sample[
                        "physical_occurrence_ref"
                    ],
                    "record_role": "exploratory_pv_event_not_g7_ledger",
                }
            )
    for row in candidates:
        sample = selected_by_ref.get(row["physical_occurrence_ref"])
        if sample is None:
            row["selection_status"] = "not_selected_quota_or_duplicate"
            row["selection_note"] = "materialized candidate retained in accounting"
        else:
            row["selected_pv_id"] = sample["pv_id"]
            if row["phenomenon_code"] == sample["primary_phenomenon_code"]:
                row["selection_status"] = "selected_primary"
            else:
                row["selection_status"] = "selected_shared_membership"
            row["selection_note"] = (
                "one physical package; logical review event per membership"
            )
    return selected, events, allocation_rows + shortfalls


def preflight(
    *,
    config_path: Path,
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
) -> dict[str, Any]:
    config = load_json(config_path)
    validate_config(config)
    if not rc0_root.is_dir() or not active_view_root.is_dir() or not r3_root.is_dir():
        raise FileNotFoundError("RC0, active-view, or r3 root is absent")
    read_active_exceptions(active_view_root)
    measured = []
    tables = sorted({str(query["source_table"]) for query in config["queries"]})
    tables.extend(["morph_units", "utterance_master_v2"])
    tables = sorted(set(tables))
    for year in config["pilot_allocation"]["years"]:
        for table in tables:
            path, record, manifest_path = annual_table_contract(
                morph_root, int(year), table
            )
            measured.append(
                {
                    "year": int(year),
                    "table": table,
                    "path": str(path),
                    "bytes": int(record["bytes"]),
                    "declared_sha256": record["sha256"],
                    "annual_manifest_sha256": sha256_file(manifest_path),
                    "measured_header": validate_header(path, table),
                }
            )
        ledger = rc0_root / "ledgers" / f"{year}_utterance_status.csv.gz"
        if not ledger.is_file():
            raise FileNotFoundError(ledger)
        ni_manifest = load_json(ni_source_root(int(year)) / "TARGET_MANIFEST_BUILD.json")
        if ni_manifest.get("query_set_sha256") != config["n_insertion_source"][
            "query_set_sha256"
        ]:
            raise RuntimeError(f"NI source query SHA mismatch: {year}")
    return {
        "status": "preflight_passed_no_candidate_scan_no_output",
        "config_sha256": sha256_file(config_path),
        "row_cap": config["safety"]["max_rows_scanned_per_table_year"],
        "annual_unique_package_quota": 30,
        "sources": measured,
    }


def build(
    *,
    config_path: Path,
    internal_candidates_path: Path,
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    require_under(output_dir, PROJECT_ROOT / "outputs" / "pilots")
    output_paths = [
        output_dir / "PV_CANDIDATE_ACCOUNTING.csv",
        output_dir / "PV_SAMPLES.csv",
        output_dir / "PV_REVIEW_EVENTS.csv",
        output_dir / "PV_SAMPLE_BUILD.json",
        output_dir / "PV_QUERY_SET.json",
    ]
    for path in output_paths:
        if path.exists():
            raise FileExistsError(f"existing output is never overwritten: {path}")
    config = load_json(config_path)
    validate_config(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    boundary_hits, source_receipts = scan_declarative_queries(
        config=config, morph_root=morph_root
    )
    internal_hits = load_internal_candidates(internal_candidates_path)
    asset_rows, lookup_receipts = materialize_asset_rows(
        query_hits=boundary_hits + internal_hits,
        config=config,
        morph_root=morph_root,
        rc0_root=rc0_root,
        active_view_root=active_view_root,
        r3_root=r3_root,
    )
    ni_rows, ni_receipts = load_ni_candidates(config=config)
    unified: list[dict[str, Any]] = []
    for sequence, (query, row) in enumerate(asset_rows + ni_rows, 1):
        unified.append(unified_candidate(query, row, sequence))
    selected, events, allocation_rows = allocate_samples(
        config=config, candidates=unified
    )
    annual_counts = count_by(selected, "year")
    shortfalls = [
        {
            "year": int(year),
            "selected": annual_counts.get(str(year), 0),
            "requested": 30,
        }
        for year in config["pilot_allocation"]["years"]
        if annual_counts.get(str(year), 0) != 30
    ]
    asset_not_ready = [row["pv_id"] for row in selected if not candidate_ready(row)]
    timing_pending = [
        row["pv_id"]
        for row in selected
        if not str(row["timing_status"]).startswith("linked_")
    ]
    status = (
        "ready_for_context_build_no_realization_judgement"
        if not shortfalls and not asset_not_ready and not timing_pending
        else "blocked_shortfall_or_selected_asset_timing_pending"
    )
    atomic_write_csv(
        output_dir / "PV_CANDIDATE_ACCOUNTING.csv", CANDIDATE_FIELDS, unified
    )
    atomic_write_csv(output_dir / "PV_SAMPLES.csv", SAMPLE_FIELDS, selected)
    atomic_write_csv(output_dir / "PV_REVIEW_EVENTS.csv", EVENT_FIELDS, events)
    atomic_write_text(
        output_dir / "PV_QUERY_SET.json",
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
    )
    manifest = {
        "schema_version": "pv_preview_sample_build.v1",
        "status": status,
        **base_build_receipt(config_path),
        "counts": {
            "materialized_candidate_rows": len(unified),
            "unique_candidate_occurrences": len(
                {row["physical_occurrence_ref"] for row in unified}
            ),
            "selected_physical_packages": len(selected),
            "logical_review_events": len(events),
            "selected_by_year": annual_counts,
            "selected_primary_year_phenomenon": count_by(
                selected, "year", "primary_phenomenon_code"
            ),
            "selected_scope": count_by(
                selected, "primary_phenomenon_code", "environment_scope"
            ),
        },
        "shortfalls": shortfalls,
        "approved_primary_quota_exceptions": config["pilot_allocation"].get(
            "approved_primary_quota_exceptions", {}
        ),
        "selected_asset_not_ready_pv_ids": asset_not_ready,
        "selected_timing_pending_pv_ids": timing_pending,
        "allocation_records": allocation_rows,
        "sources": source_receipts + lookup_receipts + ni_receipts,
        "outputs": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in output_paths[:3]
        ],
        "safety": {
            "annual_row_cap": 200000,
            "automatic_cap_increase": False,
            "vh_hia_physical_dedup": True,
            "logical_review_separate": True,
            "realization_judgement_performed": False,
            "target_time_is_word_context_not_narrow_boundary": True,
            "source_assets_modified": False,
            "mfa_run": False,
            "koina_run": False,
            "wav2vec2_run": False,
        },
    }
    atomic_write_json(output_dir / "PV_SAMPLE_BUILD.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--internal-candidates", type=Path)
    parser.add_argument("--morph-root", type=Path, default=DEFAULT_MORPH_ROOT)
    parser.add_argument("--rc0-root", type=Path, default=DEFAULT_RC0_ROOT)
    parser.add_argument(
        "--active-view-root", type=Path, default=DEFAULT_ACTIVE_VIEW_ROOT
    )
    parser.add_argument("--r3-root", type=Path, default=DEFAULT_R3_ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.preflight_only:
            result = preflight(
                config_path=args.config.resolve(),
                morph_root=args.morph_root.resolve(),
                rc0_root=args.rc0_root.resolve(),
                active_view_root=args.active_view_root.resolve(),
                r3_root=args.r3_root.resolve(),
            )
        else:
            if args.internal_candidates is None or args.output_dir is None:
                parser.error(
                    "--internal-candidates and --output-dir are required"
                )
            result = build(
                config_path=args.config.resolve(),
                internal_candidates_path=args.internal_candidates.resolve(),
                morph_root=args.morph_root.resolve(),
                rc0_root=args.rc0_root.resolve(),
                active_view_root=args.active_view_root.resolve(),
                r3_root=args.r3_root.resolve(),
                output_dir=args.output_dir.resolve(),
            )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith(("ready_", "preflight_")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
