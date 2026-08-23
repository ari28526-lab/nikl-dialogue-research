from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from build_db_v1_target_manifest import SUPPORTED_OPERATORS
from build_pv_preview_samples import (
    candidate_ready,
    link_selected_time,
    materialize_asset_rows,
    scan_declarative_queries,
    unified_candidate,
)
from pipeline_common import sha256_file
from pv_preview_common import (
    DEFAULT_ACTIVE_VIEW_ROOT,
    DEFAULT_MORPH_ROOT,
    DEFAULT_R3_ROOT,
    DEFAULT_RC0_ROOT,
    EXPECTED_HEADERS,
    PHENOMENON_LABELS,
    annual_table_contract,
    atomic_write_csv,
    atomic_write_json,
    load_json,
    stable_rank,
    validate_header,
)

sys.stdout.reconfigure(encoding="utf-8")


EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
EXPECTED_YEARS = list(range(2020, 2026))
QUERY_CONFIG = Path("config/target_queries/stage2_two_hour_pilot_candidate_v1_20260823.json")
CLAIM_PATH = Path("work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl")
SOURCE_PATH = Path("work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl")
NI_FROZEN_QUERY = Path("config/target_queries/n_insertion_production_v1_20260818.json")
NI_FROZEN_SHA256 = "744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6"
DEFAULT_OUTPUT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/query_probe"
)

CANDIDATE_FIELDS = [
    "candidate_row_id",
    "query_id",
    "phenomenon_code",
    "population_role",
    "priority",
    "environment_scope",
    "year",
    "utt_id",
    "session_id",
    "speaker_id",
    "physical_occurrence_ref",
    "matched_table",
    "occurrence_index",
    "active_form",
    "morpheme_combination",
    "word_group",
    "candidate_availability_status",
    "timing_status",
    "selection_status",
    "selected_sample_id",
    "selection_note",
    "surface_analysis_status",
    "wav_path",
    "active_textgrid_path",
    "match_evidence_json",
    "interpretation_limit",
]

SAMPLE_FIELDS = [
    "sample_id",
    "phenomenon_code",
    "phenomenon_label",
    "population_role",
    "priority",
    "environment_scope",
    "year",
    "utt_id",
    "session_id",
    "speaker_id",
    "physical_occurrence_ref",
    "query_id",
    "active_form",
    "morpheme_combination",
    "word_group",
    "grouped_order",
    "shuffled_order",
    "wav_path",
    "active_textgrid_path",
    "target_xmin",
    "target_xmax",
    "timing_status",
    "target_word_indices_json",
    "target_word_labels_json",
    "surface_analysis_status",
    "realization_status",
    "selection_reason",
    "match_evidence_json",
    "interpretation_limit",
]


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def repo_path(root: Path, relative: Path | str) -> Path:
    root = root.resolve()
    value = (root / relative).resolve()
    require(value == root or root in value.parents, f"path escapes repo: {relative}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            require(bool(line.strip()), f"blank JSONL line: {path}:{line_number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL object expected: {path}:{line_number}")
            rows.append(value)
    return rows


def validate_query_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    require(config.get("schema_version") == "stage2_two_hour_query_candidate_set.v1", "query schema")
    require(config.get("status") == "candidate_not_frozen_pending_probe", "query status")
    safety = config.get("safety", {})
    require(safety.get("max_rows_scanned_per_table_year") == 200000, "row cap must be 200000")
    require(safety.get("max_materialized_candidates_per_query_year") == 50, "candidate cap must be 50")
    require(safety.get("automatic_scan_cap_increase") is False, "automatic cap increase forbidden")
    require(safety.get("realization_judgement") is False, "realization judgement forbidden")
    require(safety.get("mfa_koina_wav2vec2_execution") is False, "model execution forbidden")
    allocation = config.get("pilot_allocation", {})
    require(allocation.get("years") == EXPECTED_YEARS, "pilot years")
    require(allocation.get("phenomenon_order") == EXPECTED_CODES, "phenomenon order")
    require(allocation.get("target_per_phenomenon") == 12, "sample target")
    require(allocation.get("primary_target_per_phenomenon") == 10, "primary target")
    require(allocation.get("peripheral_or_exploratory_cap") == 2, "secondary cap")
    require(allocation.get("target_per_year_per_phenomenon") == 2, "year quota")
    history = config.get("protected_ni_history", {})
    require(history.get("sha256") == NI_FROZEN_SHA256, "NI frozen SHA declaration")
    require(sha256_file(repo_path(root, NI_FROZEN_QUERY)) == NI_FROZEN_SHA256, "NI frozen query changed")

    claim_ids = {str(row.get("claim_id")) for row in read_jsonl(repo_path(root, CLAIM_PATH))}
    source_ids = {str(row.get("source_id")) for row in read_jsonl(repo_path(root, SOURCE_PATH))}
    queries = config.get("queries")
    require(isinstance(queries, list) and queries, "queries missing")
    query_ids: set[str] = set()
    counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    for query in queries:
        query_id = str(query.get("query_id", ""))
        require(query_id.startswith("P2H_"), f"query id: {query_id}")
        require(query_id not in query_ids, f"duplicate query id: {query_id}")
        query_ids.add(query_id)
        code = str(query.get("phenomenon_code", ""))
        require(code in EXPECTED_CODES, f"query phenomenon: {query_id}")
        counts[code] += 1
        role = str(query.get("population_role", ""))
        require(role in {"primary", "peripheral", "exploratory", "comparison_negative", "surface_branch_probe"}, f"population role: {query_id}")
        role_counts[role] += 1
        expected_priority = {
            "primary": 1,
            "peripheral": 2,
            "exploratory": 3,
            "surface_branch_probe": 3,
            "comparison_negative": 4,
        }[role]
        require(query.get("priority") == expected_priority, f"priority: {query_id}")
        require(query.get("years") == EXPECTED_YEARS, f"years: {query_id}")
        table = str(query.get("source_table", ""))
        require(table in {"morph_boundaries", "orth_eojeol_tokens"}, f"source table: {query_id}")
        require(int(query.get("max_occurrences_per_year", 0)) <= 50, f"candidate cap: {query_id}")
        conditions = query.get("conditions")
        require(isinstance(conditions, list) and conditions, f"conditions: {query_id}")
        for condition in conditions:
            require(condition.get("field") in EXPECTED_HEADERS[table], f"condition field: {query_id}:{condition.get('field')}")
            require(condition.get("op") in SUPPORTED_OPERATORS, f"condition op: {query_id}")
        for reference in query.get("evidence_refs", []):
            if str(reference).startswith("CLM-"):
                require(reference in claim_ids, f"claim ref: {query_id}:{reference}")
            elif str(reference).startswith("SRC-"):
                require(reference in source_ids, f"source ref: {query_id}:{reference}")
            else:
                raise ProbeError(f"invalid evidence ref: {query_id}:{reference}")
    require(set(counts) == set(EXPECTED_CODES), f"query coverage: {sorted(counts)}")
    serialized = json.dumps(config, ensure_ascii=False)
    require("표면 요" in serialized and "이/VCP+요" in serialized, "NI surface 요 retention declaration")
    require(any(query["query_id"] == "P2H_NI_EXP_VCP_SURFACE_BRANCH_V1" for query in queries), "NI VCP branch probe")
    return {
        "queries": len(queries),
        "queries_by_phenomenon": dict(sorted(counts.items())),
        "queries_by_population_role": dict(sorted(role_counts.items())),
        "row_cap": 200000,
        "candidate_cap": 50,
    }


def first_row_measurement(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        row = next(reader, None)
    require(row is not None, f"empty source table: {path}")
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "first_row_column_count": len(row),
        "first_row_utt_id": str(row.get("utt_id", "")),
        "first_row_nonempty_field_count": sum(bool(str(value).strip()) for value in row.values()),
        "first_row_sha256": hashlib.sha256(canonical).hexdigest(),
        "raw_first_row_in_report": False,
    }


def measure_sources(root: Path, config: Mapping[str, Any], morph_root: Path) -> list[dict[str, Any]]:
    table_years = sorted({(str(query["source_table"]), int(year)) for query in config["queries"] for year in query["years"]})
    result: list[dict[str, Any]] = []
    for table, year in table_years:
        path, record, manifest_path = annual_table_contract(morph_root, year, table)
        header = validate_header(path, table)
        measurement = first_row_measurement(path)
        result.append(
            {
                "table": table,
                "year": year,
                "path": str(path),
                "bytes": path.stat().st_size,
                "declared_sha256": str(record.get("sha256", "")),
                "annual_manifest_path": str(manifest_path),
                "annual_manifest_sha256": sha256_file(manifest_path),
                "measured_header": header,
                "header_matches_expected_required_subset": all(field in header for field in EXPECTED_HEADERS[table]),
                **measurement,
            }
        )
    return result


def preflight(
    *,
    root: Path,
    config_path: Path,
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
) -> dict[str, Any]:
    config = load_json(config_path)
    stats = validate_query_config(root, config)
    measurements = measure_sources(root, config, morph_root)
    require(rc0_root.is_dir(), f"RC0 root missing: {rc0_root}")
    require(active_view_root.is_dir(), f"active-view root missing: {active_view_root}")
    require(r3_root.is_dir(), f"r3 root missing: {r3_root}")
    for year in EXPECTED_YEARS:
        require((rc0_root / "ledgers" / f"{year}_utterance_status.csv.gz").is_file(), f"RC0 ledger missing: {year}")
        annual_table_contract(morph_root, year, "utterance_master_v2")
    return {
        "schema_version": "stage2_two_hour_query_probe_preflight.v1",
        "status": "preflight_ready_no_scan_no_realization_judgement",
        "passed": True,
        "query_config_path": str(config_path),
        "query_config_sha256": sha256_file(config_path),
        "query_contract": stats,
        "source_measurements": measurements,
        "protected_ni_query_sha256": NI_FROZEN_SHA256,
        "safety": {
            "rows_scanned": 0,
            "audio_processed": 0,
            "realization_judgements": 0,
            "source_modified": False,
        },
    }


def evidence_dict(row: Mapping[str, Any]) -> dict[str, str]:
    try:
        value = json.loads(str(row.get("match_evidence_json", "{}")))
    except json.JSONDecodeError:
        value = {}
    return {str(key): str(item) for key, item in value.items()}


def morpheme_group(row: Mapping[str, Any]) -> tuple[str, str]:
    evidence = evidence_dict(row)
    left = str(evidence.get("left_morph_surface", ""))
    right = str(evidence.get("right_morph_surface", ""))
    left_pos = str(evidence.get("left_pos", ""))
    right_pos = str(evidence.get("right_pos", ""))
    if left or right:
        combo = f"{left}/{left_pos}+{right}/{right_pos}"
        word = f"{left}+{right}"
    else:
        orth = str(evidence.get("orth_eojeol_form", row.get("active_form", "")))
        combo = f"ORTH:{orth}"
        word = orth
    return combo, word


def output_candidate(
    row: dict[str, Any],
    query: Mapping[str, Any],
) -> dict[str, Any]:
    combo, word = morpheme_group(row)
    query_id = str(query["query_id"])
    surface_status = (
        "pending_surface_i_vs_yo_roundtrip"
        if query_id == "P2H_NI_EXP_VCP_SURFACE_BRANCH_V1"
        else "not_yet_manually_verified"
    )
    return {
        **row,
        "query_id": query_id,
        "query_role": "two_hour_pilot_candidate",
        "population_role": str(query["population_role"]),
        "priority": str(query["priority"]),
        "morpheme_combination": combo,
        "word_group": word,
        "candidate_availability_status": str(row.get("inclusion_status", "")),
        "selection_status": "not_selected_pending_two_hour_allocation",
        "selected_sample_id": "",
        "selection_note": "candidate retained in zero-drop accounting",
        "surface_analysis_status": surface_status,
    }


def ni_vcp_surface_scope_status(row: Mapping[str, Any]) -> str:
    """Classify the written target only, never its acoustic realization."""

    if str(row.get("query_id", "")) != "P2H_NI_EXP_VCP_SURFACE_BRANCH_V1":
        return "not_vcp_surface_branch"
    evidence = evidence_dict(row)
    try:
        eojeol_index = int(evidence.get("right_eojeol_idx", ""))
    except ValueError:
        return "unresolved_surface_roundtrip"
    tokens = [part for part in str(row.get("active_form", "")).split() if part]
    if not 1 <= eojeol_index <= len(tokens):
        return "unresolved_surface_roundtrip"
    token = re.sub(r"^[^가-힣]*|[^가-힣]*$", "", tokens[eojeol_index - 1])
    left = evidence.get("left_morph_surface", "")
    if not left or not token.startswith(left):
        return "unresolved_surface_roundtrip"
    suffix = token[len(left) :]
    if suffix.startswith("요"):
        return "eligible_surface_yo_analyzer_i_yo"
    if suffix.startswith("이"):
        return "excluded_overt_surface_copular_i"
    return "unresolved_surface_roundtrip"


def choose_one(
    candidates: list[dict[str, Any]],
    *,
    seed: str,
    code: str,
    year: int,
    pass_name: str,
    used_refs: set[str],
    used_sessions: set[str],
    group_counts: Counter[str],
    timing_cache: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    eligible = [
        row
        for row in candidates
        if int(row["year"]) == year and row["physical_occurrence_ref"] not in used_refs
    ]
    eligible.sort(
        key=lambda row: (
            not candidate_ready(row),
            group_counts[str(row["morpheme_combination"])] >= 2,
            row["session_id"] in used_sessions,
            group_counts[str(row["morpheme_combination"])],
            stable_rank(seed, code, year, pass_name, row["physical_occurrence_ref"]),
        )
    )
    for row in eligible:
        if not candidate_ready(row):
            continue
        ref = str(row["physical_occurrence_ref"])
        if ref not in timing_cache:
            timing_cache[ref] = link_selected_time(dict(row))
        linked = timing_cache[ref]
        if not str(linked.get("timing_status", "")).startswith("linked_"):
            continue
        used_refs.add(ref)
        used_sessions.add(str(row["session_id"]))
        group_counts[str(row["morpheme_combination"])] += 1
        return {**row, **linked}
    return None


def select_samples(
    candidates: list[dict[str, Any]], config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seed = str(config["pilot_allocation"]["selection_seed"])
    selected: list[dict[str, Any]] = []
    shortfalls: list[dict[str, Any]] = []
    for code in EXPECTED_CODES:
        code_rows = [row for row in candidates if row["phenomenon_code"] == code]
        primary = [row for row in code_rows if row["population_role"] == "primary"]
        secondary = [
            row
            for row in code_rows
            if row["population_role"] != "primary"
            and (
                row["population_role"] != "surface_branch_probe"
                or ni_vcp_surface_scope_status(row)
                == "eligible_surface_yo_analyzer_i_yo"
            )
        ]
        used_refs: set[str] = set()
        used_sessions: set[str] = set()
        group_counts: Counter[str] = Counter()
        timing_cache: dict[str, dict[str, Any]] = {}
        year_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)

        # First pass: guarantee broad annual coverage with one primary candidate.
        for year in EXPECTED_YEARS:
            row = choose_one(
                primary,
                seed=seed,
                code=code,
                year=year,
                pass_name="primary_first",
                used_refs=used_refs,
                used_sessions=used_sessions,
                group_counts=group_counts,
                timing_cache=timing_cache,
            )
            if row is not None:
                row["selection_reason"] = "annual_primary_first"
                year_rows[year].append(row)

        # Second pass: put no more than two peripheral/exploratory/comparison cases in the pilot.
        secondary_years = sorted(
            EXPECTED_YEARS,
            key=lambda value: stable_rank(seed, code, "secondary_year", value),
        )
        secondary_selected = 0
        for year in secondary_years:
            if secondary_selected >= 2 or len(year_rows[year]) >= 2:
                continue
            row = choose_one(
                secondary,
                seed=seed,
                code=code,
                year=year,
                pass_name="secondary",
                used_refs=used_refs,
                used_sessions=used_sessions,
                group_counts=group_counts,
                timing_cache=timing_cache,
            )
            if row is not None:
                row["selection_reason"] = "peripheral_exploratory_or_comparison_cap2"
                year_rows[year].append(row)
                secondary_selected += 1

        # Fill the second annual slot with primary candidates; secondary is never expanded past two.
        for year in EXPECTED_YEARS:
            while len(year_rows[year]) < 2:
                row = choose_one(
                    primary,
                    seed=seed,
                    code=code,
                    year=year,
                    pass_name="primary_fill",
                    used_refs=used_refs,
                    used_sessions=used_sessions,
                    group_counts=group_counts,
                    timing_cache=timing_cache,
                )
                if row is None:
                    break
                row["selection_reason"] = "annual_primary_fill"
                year_rows[year].append(row)

        code_selected = [row for year in EXPECTED_YEARS for row in year_rows[year]]
        if len(code_selected) < 12:
            shortfalls.append(
                {
                    "phenomenon_code": code,
                    "requested": 12,
                    "selected": len(code_selected),
                    "missing": 12 - len(code_selected),
                    "status": "quota_shortfall_preserved",
                    "year_counts": {str(year): len(year_rows[year]) for year in EXPECTED_YEARS},
                }
            )
        for year in EXPECTED_YEARS:
            for slot, row in enumerate(year_rows[year], start=1):
                sample_id = f"P2H-{code}-{year}-{slot:02d}"
                row["sample_id"] = sample_id
                row["phenomenon_label"] = PHENOMENON_LABELS[code]
                row["realization_status"] = "not_judged"
                selected.append(row)
                row["selection_status"] = "selected_two_hour_pilot"
                row["selected_sample_id"] = sample_id
                row["selection_note"] = str(row["selection_reason"])

    grouped = sorted(
        selected,
        key=lambda row: (
            EXPECTED_CODES.index(str(row["phenomenon_code"])),
            str(row["morpheme_combination"]),
            str(row["active_form"]),
            int(row["year"]),
            str(row["sample_id"]),
        ),
    )
    shuffled = sorted(
        selected,
        key=lambda row: stable_rank(seed, row["phenomenon_code"], "shuffle", row["physical_occurrence_ref"]),
    )
    grouped_index = {row["sample_id"]: index for index, row in enumerate(grouped, start=1)}
    shuffled_index = {row["sample_id"]: index for index, row in enumerate(shuffled, start=1)}
    for row in selected:
        row["grouped_order"] = str(grouped_index[row["sample_id"]])
        row["shuffled_order"] = str(shuffled_index[row["sample_id"]])
    selected.sort(key=lambda row: grouped_index[row["sample_id"]])
    return selected, shortfalls


def build(
    *,
    root: Path,
    config_path: Path,
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    require(not output_dir.exists(), f"output already exists: {output_dir}")
    preflight_report = preflight(
        root=root,
        config_path=config_path,
        morph_root=morph_root,
        rc0_root=rc0_root,
        active_view_root=active_view_root,
        r3_root=r3_root,
    )
    config = load_json(config_path)
    query_map = {str(query["query_id"]): query for query in config["queries"]}
    hits, source_receipts = scan_declarative_queries(config=config, morph_root=morph_root)
    materialized, lookup_receipts = materialize_asset_rows(
        query_hits=hits,
        config=config,
        morph_root=morph_root,
        rc0_root=rc0_root,
        active_view_root=active_view_root,
        r3_root=r3_root,
    )
    require(len(materialized) == len(hits), f"zero-drop materialization mismatch: {len(hits)} != {len(materialized)}")
    candidates: list[dict[str, Any]] = []
    for sequence, (query, row) in enumerate(materialized, start=1):
        unified = unified_candidate(query, row, sequence)
        candidates.append(output_candidate(unified, query_map[str(query["query_id"])]))
    selected, shortfalls = select_samples(candidates, config)
    selected_by_candidate = {str(row["candidate_row_id"]): row for row in selected}
    for row in candidates:
        selected_row = selected_by_candidate.get(str(row["candidate_row_id"]))
        if selected_row is not None:
            row["selection_status"] = "selected_two_hour_pilot"
            row["selected_sample_id"] = selected_row["sample_id"]
            row["selection_note"] = selected_row["selection_reason"]
            row["timing_status"] = selected_row["timing_status"]

    output_dir.mkdir(parents=True, exist_ok=False)
    candidate_path = output_dir / "P2H_CANDIDATE_ACCOUNTING.csv"
    sample_path = output_dir / "P2H_SAMPLES.csv"
    measurement_path = output_dir / "P2H_SOURCE_MEASUREMENTS.json"
    receipt_path = output_dir / "P2H_QUERY_PROBE_RECEIPT.json"
    atomic_write_csv(candidate_path, CANDIDATE_FIELDS, candidates)
    atomic_write_csv(sample_path, SAMPLE_FIELDS, selected)
    atomic_write_json(measurement_path, {"schema_version": "stage2_two_hour_source_measurements.v1", "measurements": preflight_report["source_measurements"]})
    selected_counts = Counter(str(row["phenomenon_code"]) for row in selected)
    primary_counts = Counter(str(row["phenomenon_code"]) for row in selected if row["population_role"] == "primary")
    role_counts = Counter(f"{row['phenomenon_code']}|{row['population_role']}" for row in selected)
    query_counts = Counter(str(row["query_id"]) for row in candidates)
    status = "ready_for_two_hour_review_package_no_realization_judgement" if not shortfalls else "candidate_probe_completed_with_preserved_shortfalls"
    receipt = {
        "schema_version": "stage2_two_hour_query_probe_receipt.v1",
        "status": status,
        "passed": True,
        "query_config_path": str(config_path),
        "query_config_sha256": sha256_file(config_path),
        "counts": {
            "query_hits": len(hits),
            "candidate_accounting_rows": len(candidates),
            "selected_samples": len(selected),
            "selected_by_phenomenon": dict(sorted(selected_counts.items())),
            "selected_primary_by_phenomenon": dict(sorted(primary_counts.items())),
            "selected_by_phenomenon_role": dict(sorted(role_counts.items())),
            "candidate_by_query": dict(sorted(query_counts.items())),
        },
        "shortfalls": shortfalls,
        "source_scan_receipts": source_receipts,
        "selected_id_lookup_receipts": lookup_receipts,
        "source_measurements_path": measurement_path.name,
        "outputs": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in (candidate_path, sample_path, measurement_path)
        ],
        "zero_drop": {
            "input_query_hits": len(hits),
            "output_candidate_rows": len(candidates),
            "equal": len(hits) == len(candidates),
            "not_selected_rows_retained": sum(row["selection_status"] != "selected_two_hour_pilot" for row in candidates),
        },
        "safety": {
            "max_rows_scanned_per_table_year": 200000,
            "automatic_cap_increase": False,
            "source_modified": False,
            "audio_copied_or_processed": False,
            "mfa_koina_wav2vec2_run": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "ni_v1_modified": False,
            "surface_yo_analyzer_i_yo_deleted": False,
        },
    }
    atomic_write_json(receipt_path, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe Stage 2 two-hour query candidates")
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--config", type=Path, default=root / QUERY_CONFIG)
    parser.add_argument("--morph-root", type=Path, default=DEFAULT_MORPH_ROOT)
    parser.add_argument("--rc0-root", type=Path, default=DEFAULT_RC0_ROOT)
    parser.add_argument("--active-view-root", type=Path, default=DEFAULT_ACTIVE_VIEW_ROOT)
    parser.add_argument("--r3-root", type=Path, default=DEFAULT_R3_ROOT)
    parser.add_argument("--output-dir", type=Path, default=root / DEFAULT_OUTPUT)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        root = args.repo_root.resolve()
        if args.preflight_only:
            report = preflight(
                root=root,
                config_path=args.config.resolve(),
                morph_root=args.morph_root.resolve(),
                rc0_root=args.rc0_root.resolve(),
                active_view_root=args.active_view_root.resolve(),
                r3_root=args.r3_root.resolve(),
            )
        else:
            report = build(
                root=root,
                config_path=args.config.resolve(),
                morph_root=args.morph_root.resolve(),
                rc0_root=args.rc0_root.resolve(),
                active_view_root=args.active_view_root.resolve(),
                r3_root=args.r3_root.resolve(),
                output_dir=args.output_dir.resolve(),
            )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
