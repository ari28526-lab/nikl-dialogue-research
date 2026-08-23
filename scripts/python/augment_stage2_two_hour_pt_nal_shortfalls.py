from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping

from build_pv_preview_samples import candidate_ready, link_selected_time, materialize_asset_rows, unified_candidate
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
    physical_occurrence_ref,
    session_from_utt,
    source_receipt,
    stable_rank,
    validate_header,
)
from scan_pv_morph_internal_lite import evidence as internal_evidence
from scan_pv_morph_internal_lite import same_morph

sys.stdout.reconfigure(encoding="utf-8")


class AugmentError(RuntimeError):
    pass


EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
EXPECTED_YEARS = list(range(2020, 2026))
PT_LEFT_CODAS = {"", "ㄴ", "ㄹ", "ㅁ", "ㅇ"}
PT_RIGHT_ONSETS = {"ㄱ", "ㄷ", "ㅂ", "ㅅ", "ㅈ"}
PT_NOUN_POS = {"NNG", "NNP"}
DEFAULT_QUERY_CONFIG = Path("config/target_queries/stage2_two_hour_pilot_candidate_v1_20260823.json")
DEFAULT_PROBE_ROOT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/query_probe"
)
DEFAULT_LEGACY_SAMPLES = Path("outputs/pilots/pv_seven_phenomena_20260819/samples/PV_SAMPLES.csv")
DEFAULT_OUTPUT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/shortfall_augmentation"
)

FINAL_FIELDS = [
    "sample_id",
    "source_sample_id",
    "augmentation_source",
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
    "compoundness_status",
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

PT_CANDIDATE_FIELDS = [
    "candidate_row_id",
    "year",
    "utt_id",
    "session_id",
    "physical_occurrence_ref",
    "active_form",
    "morpheme_combination",
    "compoundness_status",
    "candidate_availability_status",
    "timing_status",
    "selection_status",
    "selected_sample_id",
    "wav_path",
    "active_textgrid_path",
    "match_evidence_json",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AugmentError(message)


def repo_path(root: Path, relative: Path | str) -> Path:
    root = root.resolve()
    value = (root / relative).resolve()
    require(value == root or root in value.parents, f"path escapes repo: {relative}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def query_config(root: Path) -> dict[str, Any]:
    with repo_path(root, DEFAULT_QUERY_CONFIG).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    require(value.get("safety", {}).get("max_rows_scanned_per_table_year") == 200000, "row cap")
    require(value.get("safety", {}).get("max_materialized_candidates_per_query_year") == 50, "candidate cap")
    return value


def pt_rule(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return (
        left.get("unit_type") == "hangul"
        and right.get("unit_type") == "hangul"
        and left.get("pos") in PT_NOUN_POS
        and right.get("pos") == left.get("pos")
        and left.get("coda_jamo", "") in PT_LEFT_CODAS
        and right.get("onset_jamo", "") in PT_RIGHT_ONSETS
    )


def pt_internal_query() -> dict[str, Any]:
    return {
        "query_id": "P2H_PT_EXP_NOUN_INTERNAL_COMPOUNDNESS_V1",
        "query_version": 1,
        "query_role": "two_hour_pilot_candidate",
        "phenomenon_code": "PT",
        "population_role": "compoundness_probe",
        "priority": 3,
        "environment_scope": "morph_internal",
        "source_table": "morph_units",
        "occurrence_index_field": "internal_pair_index",
        "interpretation": (
            "단일 NNG/NNP 내부의 공명음·모음 뒤 평장애음 연쇄. 합성어 경계인지 "
            "수동으로 확인하기 전에는 PT 중심 모집단이 아니다. 실현 미판정."
        ),
    }


def scan_pt_internal(
    *, morph_root: Path, row_cap: int = 200000, candidate_cap: int = 50
) -> tuple[list[tuple[dict[str, Any], dict[str, str]]], list[dict[str, Any]]]:
    query = pt_internal_query()
    hits: list[tuple[dict[str, Any], dict[str, str]]] = []
    receipts: list[dict[str, Any]] = []
    for year in EXPECTED_YEARS:
        path, record, manifest_path = annual_table_contract(morph_root, year, "morph_units")
        header = validate_header(path, "morph_units")
        rows_scanned = 0
        pairs_evaluated = 0
        count = 0
        previous: dict[str, str] | None = None
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for current in reader:
                rows_scanned += 1
                if previous is not None and same_morph(previous, current):
                    pairs_evaluated += 1
                    if count < candidate_cap and pt_rule(previous, current):
                        occurrence_index = (
                            f"{current['morph_idx_in_utterance']}:"
                            f"{previous['unit_idx_in_morph']}-{current['unit_idx_in_morph']}"
                        )
                        hit = {
                            **internal_evidence(previous, current),
                            "utt_id": current["utt_id"],
                            "internal_pair_index": occurrence_index,
                            "__year": str(year),
                        }
                        hits.append((query, hit))
                        count += 1
                previous = dict(current)
                if count >= candidate_cap or rows_scanned >= row_cap:
                    break
        receipt = source_receipt(
            path,
            record,
            manifest_path,
            rows_scanned=rows_scanned,
            stopped_at_row_cap=rows_scanned >= row_cap,
        )
        receipt.update(
            {
                "year": year,
                "table": "morph_units",
                "measured_header": header,
                "pairs_evaluated": pairs_evaluated,
                "candidate_rows": count,
                "stop_reason": "candidate_cap" if count >= candidate_cap else "hard_row_cap",
            }
        )
        receipts.append(receipt)
    return hits, receipts


def morph_group(row: Mapping[str, str]) -> tuple[str, str]:
    try:
        evidence = json.loads(row.get("match_evidence_json", "{}"))
    except json.JSONDecodeError:
        evidence = {}
    if evidence.get("morph_surface"):
        morph = str(evidence.get("morph_surface", ""))
        units = f"{evidence.get('left_unit_surface', '')}+{evidence.get('right_unit_surface', '')}"
        return f"{morph}/{evidence.get('pos', '')}:{units}", morph
    left = str(evidence.get("left_morph_surface", ""))
    right = str(evidence.get("right_morph_surface", ""))
    return f"{left}/{evidence.get('left_pos', '')}+{right}/{evidence.get('right_pos', '')}", f"{left}+{right}"


def materialize_pt_candidates(
    *,
    hits: list[tuple[dict[str, Any], dict[str, str]]],
    config: Mapping[str, Any],
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    materialized, lookup_receipts = materialize_asset_rows(
        query_hits=hits,
        config=config,
        morph_root=morph_root,
        rc0_root=rc0_root,
        active_view_root=active_view_root,
        r3_root=r3_root,
    )
    require(len(materialized) == len(hits), "PT augmentation zero-drop materialization")
    rows: list[dict[str, Any]] = []
    for index, (query, row) in enumerate(materialized, start=1):
        unified = unified_candidate(query, row, index)
        combo, word = morph_group(unified)
        rows.append(
            {
                **unified,
                "query_id": query["query_id"],
                "population_role": "compoundness_probe",
                "priority": "3",
                "morpheme_combination": combo,
                "word_group": word,
                "compoundness_status": "pending_manual_compound_boundary",
                "candidate_availability_status": unified.get("inclusion_status", ""),
                "selection_status": "not_selected_pending_shortfall_augmentation",
                "selected_sample_id": "",
                "surface_analysis_status": "not_yet_manually_verified",
                "realization_status": "not_judged",
                "augmentation_source": "bounded_morph_units_noun_internal_probe",
                "source_sample_id": "",
                "selection_reason": "",
            }
        )
    return rows, lookup_receipts


def convert_legacy(row: dict[str, str], code: str) -> dict[str, Any]:
    combo, word = morph_group(row)
    scope = row["environment_scope"]
    if code == "NAL":
        role = "primary" if scope in {"morph_internal", "intra_eojeol"} else "exploratory"
        priority = "1" if role == "primary" else "3"
        compoundness = "not_applicable"
        interpretation = "기존 PV-A의 연결·자산 검증을 통과한 NAL 환경 재사용. 실제 실현은 미판정."
    else:
        role = "compoundness_probe"
        priority = "3"
        compoundness = "pending_manual_compound_boundary"
        interpretation = "기존 PV-A의 넓은 PT 환경 비교 후보. 합성어 경계와 자동 경음화 구분 전 중심 모집단 아님."
    return {
        "sample_id": "",
        "source_sample_id": row["pv_id"],
        "augmentation_source": "legacy_pv_a_linked_sample",
        "phenomenon_code": code,
        "phenomenon_label": PHENOMENON_LABELS[code],
        "population_role": role,
        "priority": priority,
        "environment_scope": scope,
        "year": row["year"],
        "utt_id": row["utt_id"],
        "session_id": row["session_id"],
        "speaker_id": row["speaker_id"],
        "physical_occurrence_ref": row["physical_occurrence_ref"],
        "query_id": row["pv_query_id"],
        "active_form": row["active_form"],
        "morpheme_combination": combo,
        "word_group": word,
        "compoundness_status": compoundness,
        "grouped_order": "",
        "shuffled_order": "",
        "wav_path": row["wav_path"],
        "active_textgrid_path": row["active_textgrid_path"],
        "target_xmin": row["target_xmin"],
        "target_xmax": row["target_xmax"],
        "timing_status": row["timing_status"],
        "target_word_indices_json": row["target_word_indices_json"],
        "target_word_labels_json": row["target_word_labels_json"],
        "surface_analysis_status": "not_yet_manually_verified",
        "realization_status": "not_judged",
        "selection_reason": "legacy_linked_shortfall_fill",
        "match_evidence_json": row["match_evidence_json"],
        "interpretation_limit": interpretation,
    }


def convert_probe(row: dict[str, str]) -> dict[str, Any]:
    return {
        **row,
        "source_sample_id": row["sample_id"],
        "augmentation_source": "two_hour_query_probe_v1",
        "compoundness_status": "not_applicable",
    }


def convert_pt_internal(row: dict[str, Any]) -> dict[str, Any] | None:
    if not candidate_ready(row):
        return None
    linked = link_selected_time(dict(row))
    if not str(linked.get("timing_status", "")).startswith("linked_"):
        return None
    return {
        "sample_id": "",
        "source_sample_id": row["candidate_row_id"],
        "augmentation_source": row["augmentation_source"],
        "phenomenon_code": "PT",
        "phenomenon_label": PHENOMENON_LABELS["PT"],
        "population_role": "compoundness_probe",
        "priority": "3",
        "environment_scope": "morph_internal",
        "year": str(row["year"]),
        "utt_id": row["utt_id"],
        "session_id": row["session_id"],
        "speaker_id": row.get("speaker_id", ""),
        "physical_occurrence_ref": row["physical_occurrence_ref"],
        "query_id": row["query_id"],
        "active_form": row["active_form"],
        "morpheme_combination": row["morpheme_combination"],
        "word_group": row["word_group"],
        "compoundness_status": row["compoundness_status"],
        "grouped_order": "",
        "shuffled_order": "",
        "wav_path": row["wav_path"],
        "active_textgrid_path": row["active_textgrid_path"],
        "target_xmin": linked["target_xmin"],
        "target_xmax": linked["target_xmax"],
        "timing_status": linked["timing_status"],
        "target_word_indices_json": linked["target_word_indices_json"],
        "target_word_labels_json": linked["target_word_labels_json"],
        "surface_analysis_status": "not_yet_manually_verified",
        "realization_status": "not_judged",
        "selection_reason": "bounded_noun_internal_compoundness_probe",
        "match_evidence_json": row["match_evidence_json"],
        "interpretation_limit": pt_internal_query()["interpretation"],
    }


def choose_two_per_year(
    pool: list[dict[str, Any]],
    *,
    code: str,
    seed: str,
    prefer: Callable[[Mapping[str, Any]], Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    used_refs: set[str] = set()
    used_sessions: set[str] = set()
    group_counts: Counter[str] = Counter()
    for year in EXPECTED_YEARS:
        eligible = [
            row
            for row in pool
            if int(row["year"]) == year
            and row["physical_occurrence_ref"] not in used_refs
            and str(row.get("timing_status", "")).startswith("linked_")
            and Path(str(row.get("wav_path", ""))).is_file()
            and Path(str(row.get("active_textgrid_path", ""))).is_file()
        ]
        eligible.sort(
            key=lambda row: (
                prefer(row),
                group_counts[str(row["morpheme_combination"])] >= 2,
                row["session_id"] in used_sessions,
                group_counts[str(row["morpheme_combination"])],
                stable_rank(seed, code, year, row["physical_occurrence_ref"]),
            )
        )
        for row in eligible:
            if len([item for item in result if int(item["year"]) == year]) >= 2:
                break
            ref = str(row["physical_occurrence_ref"])
            if ref in used_refs:
                continue
            result.append(dict(row))
            used_refs.add(ref)
            used_sessions.add(str(row["session_id"]))
            group_counts[str(row["morpheme_combination"])] += 1
    return result


def finalize_orders(rows: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    for code in EXPECTED_CODES:
        code_rows = [row for row in rows if row["phenomenon_code"] == code]
        for year in EXPECTED_YEARS:
            annual = sorted(
                [row for row in code_rows if int(row["year"]) == year],
                key=lambda row: stable_rank(seed, code, year, row["physical_occurrence_ref"]),
            )
            for slot, row in enumerate(annual, start=1):
                row["sample_id"] = f"P2H-{code}-{year}-{slot:02d}"
    grouped = sorted(
        rows,
        key=lambda row: (
            EXPECTED_CODES.index(str(row["phenomenon_code"])),
            str(row["morpheme_combination"]),
            str(row["active_form"]),
            int(row["year"]),
        ),
    )
    shuffled = sorted(rows, key=lambda row: stable_rank(seed, row["phenomenon_code"], "shuffle_v2", row["physical_occurrence_ref"]))
    group_index = {row["sample_id"]: index for index, row in enumerate(grouped, start=1)}
    shuffle_index = {row["sample_id"]: index for index, row in enumerate(shuffled, start=1)}
    for row in rows:
        row["grouped_order"] = str(group_index[row["sample_id"]])
        row["shuffled_order"] = str(shuffle_index[row["sample_id"]])
    return sorted(rows, key=lambda row: group_index[row["sample_id"]])


def preflight(root: Path, morph_root: Path) -> dict[str, Any]:
    config = query_config(root)
    measurements = []
    for year in EXPECTED_YEARS:
        path, record, manifest_path = annual_table_contract(morph_root, year, "morph_units")
        header = validate_header(path, "morph_units")
        measurements.append(
            {
                "year": year,
                "path": str(path),
                "bytes": path.stat().st_size,
                "declared_sha256": record.get("sha256"),
                "annual_manifest_sha256": sha256_file(manifest_path),
                "measured_header": header,
                "header_matches_expected_required_subset": all(field in header for field in EXPECTED_HEADERS["morph_units"]),
            }
        )
    probe_samples = repo_path(root, DEFAULT_PROBE_ROOT / "P2H_SAMPLES.csv")
    legacy_samples = repo_path(root, DEFAULT_LEGACY_SAMPLES)
    require(probe_samples.is_file(), f"missing query probe samples: {probe_samples}")
    require(legacy_samples.is_file(), f"missing legacy PV samples: {legacy_samples}")
    return {
        "schema_version": "stage2_two_hour_pt_nal_augmentation_preflight.v1",
        "passed": True,
        "status": "preflight_ready_no_scan",
        "row_cap": config["safety"]["max_rows_scanned_per_table_year"],
        "candidate_cap_per_year": 50,
        "probe_samples_sha256": sha256_file(probe_samples),
        "legacy_samples_sha256": sha256_file(legacy_samples),
        "source_measurements": measurements,
        "realization_judgement": False,
    }


def build(
    *,
    root: Path,
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    require(not output_dir.exists(), f"output already exists: {output_dir}")
    preflight_report = preflight(root, morph_root)
    config = query_config(root)
    hits, source_receipts = scan_pt_internal(morph_root=morph_root)
    pt_candidates, lookup_receipts = materialize_pt_candidates(
        hits=hits,
        config=config,
        morph_root=morph_root,
        rc0_root=rc0_root,
        active_view_root=active_view_root,
        r3_root=r3_root,
    )
    pt_internal_ready = [value for row in pt_candidates if (value := convert_pt_internal(row)) is not None]
    probe_rows = read_csv(repo_path(root, DEFAULT_PROBE_ROOT / "P2H_SAMPLES.csv"))
    legacy_rows = read_csv(repo_path(root, DEFAULT_LEGACY_SAMPLES))
    legacy_pt = [convert_legacy(row, "PT") for row in legacy_rows if row["primary_phenomenon_code"] == "PT"]
    legacy_nal = [convert_legacy(row, "NAL") for row in legacy_rows if row["primary_phenomenon_code"] == "NAL"]
    probe_pt = [convert_probe(row) for row in probe_rows if row["phenomenon_code"] == "PT"]
    probe_nal = [convert_probe(row) for row in probe_rows if row["phenomenon_code"] == "NAL"]
    for row in probe_pt:
        row["population_role"] = "compoundness_probe"
        row["priority"] = "3"
        row["compoundness_status"] = "pending_manual_compound_boundary"
        row["interpretation_limit"] = "명사+명사 분석 후보이나 합성어성 수동 확인 전 PT 중심 모집단이 아니다."

    def pt_preference(row: Mapping[str, Any]) -> tuple[int, int]:
        source_rank = {
            "bounded_morph_units_noun_internal_probe": 0,
            "two_hour_query_probe_v1": 1,
            "legacy_pv_a_linked_sample": 2,
        }.get(str(row.get("augmentation_source")), 3)
        evidence = json.loads(str(row.get("match_evidence_json", "{}")))
        noun_pair = int(not (
            evidence.get("left_pos") in PT_NOUN_POS
            and evidence.get("right_pos") in PT_NOUN_POS
        ))
        return source_rank, noun_pair

    pt_final = choose_two_per_year(
        [*pt_internal_ready, *probe_pt, *legacy_pt],
        code="PT",
        seed=str(config["pilot_allocation"]["selection_seed"]),
        prefer=pt_preference,
    )

    def nal_preference(row: Mapping[str, Any]) -> tuple[int, int]:
        scope_rank = {"morph_internal": 0, "intra_eojeol": 1, "inter_eojeol": 2}.get(str(row.get("environment_scope")), 3)
        source_rank = 0 if row.get("augmentation_source") == "two_hour_query_probe_v1" else 1
        return scope_rank, source_rank

    nal_final = choose_two_per_year(
        [*probe_nal, *legacy_nal],
        code="NAL",
        seed=str(config["pilot_allocation"]["selection_seed"]),
        prefer=nal_preference,
    )
    other_rows = [convert_probe(row) for row in probe_rows if row["phenomenon_code"] not in {"PT", "NAL"}]
    final = finalize_orders([*pt_final, *nal_final, *other_rows], str(config["pilot_allocation"]["selection_seed"]))
    counts = Counter(str(row["phenomenon_code"]) for row in final)
    year_counts = Counter(f"{row['phenomenon_code']}|{row['year']}" for row in final)
    shortfalls = [
        {"phenomenon_code": code, "requested": 12, "selected": counts[code], "missing": 12 - counts[code], "status": "quota_shortfall_preserved"}
        for code in EXPECTED_CODES
        if counts[code] != 12
    ]
    require(all(value <= 2 for value in year_counts.values()), "annual quota exceeded")
    selected_pt_refs = {row["physical_occurrence_ref"]: row["sample_id"] for row in pt_final}
    for row in pt_candidates:
        sample_id = selected_pt_refs.get(row["physical_occurrence_ref"], "")
        if sample_id:
            row["selection_status"] = "selected_two_hour_pilot"
            row["selected_sample_id"] = sample_id
    output_dir.mkdir(parents=True, exist_ok=False)
    candidate_path = output_dir / "P2H_PT_INTERNAL_CANDIDATE_ACCOUNTING.csv"
    final_path = output_dir / "P2H_SAMPLES_FINAL.csv"
    receipt_path = output_dir / "P2H_SHORTFALL_AUGMENTATION_RECEIPT.json"
    atomic_write_csv(candidate_path, PT_CANDIDATE_FIELDS, pt_candidates)
    atomic_write_csv(final_path, FINAL_FIELDS, final)
    status = "ready_84_samples_no_realization_judgement" if not shortfalls else "completed_with_preserved_shortfalls"
    receipt = {
        "schema_version": "stage2_two_hour_pt_nal_augmentation_receipt.v1",
        "passed": True,
        "status": status,
        "counts": {
            "pt_internal_query_hits": len(hits),
            "pt_internal_candidate_rows": len(pt_candidates),
            "pt_internal_timing_ready": len(pt_internal_ready),
            "final_samples": len(final),
            "final_by_phenomenon": dict(sorted(counts.items())),
            "final_by_phenomenon_year": dict(sorted(year_counts.items())),
            "pt_augmentation_source": dict(sorted(Counter(str(row["augmentation_source"]) for row in pt_final).items())),
            "nal_augmentation_source": dict(sorted(Counter(str(row["augmentation_source"]) for row in nal_final).items())),
        },
        "shortfalls": shortfalls,
        "source_scan_receipts": source_receipts,
        "selected_id_lookup_receipts": lookup_receipts,
        "preflight": preflight_report,
        "inputs": {
            "query_probe_samples": {"path": str(repo_path(root, DEFAULT_PROBE_ROOT / "P2H_SAMPLES.csv")), "sha256": sha256_file(repo_path(root, DEFAULT_PROBE_ROOT / "P2H_SAMPLES.csv"))},
            "legacy_pv_samples": {"path": str(repo_path(root, DEFAULT_LEGACY_SAMPLES)), "sha256": sha256_file(repo_path(root, DEFAULT_LEGACY_SAMPLES))},
        },
        "outputs": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in (candidate_path, final_path)
        ],
        "zero_drop": {
            "pt_internal_input_hits": len(hits),
            "pt_internal_accounting_rows": len(pt_candidates),
            "equal": len(hits) == len(pt_candidates),
            "unselected_pt_internal_retained": sum(row["selection_status"] != "selected_two_hour_pilot" for row in pt_candidates),
        },
        "interpretation": {
            "pt": "12개 모두 합성어성 확인 probe이며 실제 PT 중심 모집단으로 자동 승격되지 않는다.",
            "nal": "기존 PV-A의 연결 완료 NAL 환경을 재사용하되 실제 실현은 미판정이다.",
        },
        "safety": {
            "row_cap": 200000,
            "automatic_cap_increase": False,
            "source_modified": False,
            "audio_copied_or_processed": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
        },
    }
    atomic_write_json(receipt_path, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Augment PT/NAL two-hour pilot shortfalls")
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--repo-root", type=Path, default=root)
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
            report = preflight(root, args.morph_root.resolve())
        else:
            report = build(
                root=root,
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
