from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from augment_stage2_two_hour_pt_nal_shortfalls import FINAL_FIELDS
from build_pv_preview_samples import link_selected_time
from pipeline_common import sha256_file
from pv_preview_common import PHENOMENON_LABELS, atomic_write_csv, atomic_write_json, stable_rank

sys.stdout.reconfigure(encoding="utf-8")


class ScopeCorrectionError(RuntimeError):
    pass


EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
EXPECTED_YEARS = list(range(2020, 2026))
VCP_QUERY_ID = "P2H_NI_EXP_VCP_SURFACE_BRANCH_V1"
PRIMARY_QUERY_ID = "P2H_NI_PRI_C_IJ_INTRA_NO_JEVCP_V1"
DEFAULT_FINAL_INPUT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/shortfall_augmentation/P2H_SAMPLES_FINAL.csv"
)
DEFAULT_AUGMENT_RECEIPT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/shortfall_augmentation/"
    "P2H_SHORTFALL_AUGMENTATION_RECEIPT.json"
)
DEFAULT_CANDIDATES = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/query_probe/P2H_CANDIDATE_ACCOUNTING.csv"
)
DEFAULT_QUERY_RECEIPT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/query_probe/P2H_QUERY_PROBE_RECEIPT.json"
)
DEFAULT_OUTPUT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/ni_scope_correction_v2"
)

ACCOUNTING_FIELDS = [
    "record_kind",
    "original_sample_id",
    "original_occurrence_ref",
    "final_sample_id",
    "final_occurrence_ref",
    "year",
    "query_id",
    "scope_status",
    "scope_reason",
    "source_candidate_row_id",
    "surface_target_token",
    "surface_suffix_after_left_morph",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScopeCorrectionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    require(bool(rows), f"empty CSV: {path}")
    return rows


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def declared_output_sha(receipt: Mapping[str, Any], filename: str) -> str:
    matches = [row for row in receipt.get("outputs", []) if row.get("path") == filename]
    require(len(matches) == 1, f"receipt output declaration count for {filename}: {len(matches)}")
    return str(matches[0].get("sha256", ""))


def cleaned_orth_token(value: str) -> str:
    return re.sub(r"^[^가-힣]*|[^가-힣]*$", "", value)


def vcp_surface_class(row: Mapping[str, Any]) -> dict[str, str]:
    """Classify orthographic scope only; never classify acoustic realization."""

    try:
        evidence = json.loads(str(row.get("match_evidence_json", "{}")))
    except json.JSONDecodeError:
        evidence = {}
    if str(evidence.get("right_pos", "")) != "VCP":
        return {
            "status": "not_vcp_branch",
            "reason": "right POS is not VCP",
            "token": "",
            "suffix": "",
        }
    try:
        eojeol_index = int(str(evidence.get("right_eojeol_idx", "")))
    except ValueError:
        eojeol_index = 0
    tokens = [part for part in str(row.get("active_form", "")).split() if part]
    token = cleaned_orth_token(tokens[eojeol_index - 1]) if 1 <= eojeol_index <= len(tokens) else ""
    left = str(evidence.get("left_morph_surface", ""))
    suffix = token[len(left) :] if left and token.startswith(left) else ""
    if suffix.startswith("요"):
        return {
            "status": "eligible_surface_yo_analyzer_i_yo",
            "reason": "surface token begins with left morpheme plus 요; analyzer VCP branch retained",
            "token": token,
            "suffix": suffix,
        }
    if suffix.startswith("이"):
        return {
            "status": "excluded_overt_surface_copular_i",
            "reason": "surface token overtly begins with 이 after the left morpheme",
            "token": token,
            "suffix": suffix,
        }
    return {
        "status": "unresolved_surface_roundtrip",
        "reason": "orthographic target could not be resolved as surface 요 or overt 이",
        "token": token,
        "suffix": suffix,
    }


def bind_inputs(
    final_path: Path,
    augment_receipt_path: Path,
    candidate_path: Path,
    query_receipt_path: Path,
) -> dict[str, Any]:
    augment_receipt = load_json(augment_receipt_path)
    query_receipt = load_json(query_receipt_path)
    measured_final = sha256_file(final_path)
    measured_candidates = sha256_file(candidate_path)
    require(
        measured_final == declared_output_sha(augment_receipt, final_path.name),
        "final sample input SHA does not match augmentation receipt",
    )
    require(
        measured_candidates == declared_output_sha(query_receipt, candidate_path.name),
        "candidate accounting SHA does not match query receipt",
    )
    return {
        "final_samples": {"path": str(final_path), "sha256": measured_final},
        "candidate_accounting": {"path": str(candidate_path), "sha256": measured_candidates},
        "augmentation_receipt": {
            "path": str(augment_receipt_path),
            "sha256": sha256_file(augment_receipt_path),
        },
        "query_receipt": {
            "path": str(query_receipt_path),
            "sha256": sha256_file(query_receipt_path),
        },
    }


def preflight(
    *,
    final_path: Path,
    augment_receipt_path: Path,
    candidate_path: Path,
    query_receipt_path: Path,
) -> dict[str, Any]:
    inputs = bind_inputs(final_path, augment_receipt_path, candidate_path, query_receipt_path)
    final_rows = read_csv(final_path)
    candidates = read_csv(candidate_path)
    require(len(final_rows) == 84, f"expected 84 final rows, measured {len(final_rows)}")
    require(len({row["sample_id"] for row in final_rows}) == 84, "duplicate final sample_id")
    vcp_selected = [
        row
        for row in final_rows
        if row.get("phenomenon_code") == "NI" and row.get("query_id") == VCP_QUERY_ID
    ]
    classifications = [vcp_surface_class(row) for row in vcp_selected]
    candidate_vcp = [row for row in candidates if row.get("query_id") == VCP_QUERY_ID]
    candidate_classes = Counter(vcp_surface_class(row)["status"] for row in candidate_vcp)
    return {
        "schema_version": "stage2_two_hour_ni_scope_correction_preflight.v1",
        "passed": True,
        "status": "ready_no_source_scan_no_realization_judgement",
        "inputs": inputs,
        "selected_vcp_rows": len(vcp_selected),
        "selected_vcp_classifications": classifications,
        "candidate_vcp_scope_counts": dict(sorted(candidate_classes.items())),
        "safety": {
            "source_rows_scanned": 0,
            "audio_processed": 0,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
        },
    }


def final_row_from_candidate(candidate: Mapping[str, str], sample_id: str) -> dict[str, str]:
    linked = link_selected_time(dict(candidate))
    require(str(linked.get("timing_status", "")).startswith("linked_"), "replacement timing not linked")
    return {
        "sample_id": sample_id,
        "source_sample_id": "",
        "augmentation_source": "ni_scope_correction_from_retained_query_accounting",
        "phenomenon_code": "NI",
        "phenomenon_label": PHENOMENON_LABELS["NI"],
        "population_role": "primary",
        "priority": str(candidate.get("priority", "1")),
        "environment_scope": str(candidate.get("environment_scope", "intra_eojeol")),
        "year": str(candidate["year"]),
        "utt_id": str(candidate["utt_id"]),
        "session_id": str(candidate["session_id"]),
        "speaker_id": str(candidate.get("speaker_id", "")),
        "physical_occurrence_ref": str(candidate["physical_occurrence_ref"]),
        "query_id": PRIMARY_QUERY_ID,
        "active_form": str(candidate["active_form"]),
        "morpheme_combination": str(candidate["morpheme_combination"]),
        "word_group": str(candidate["word_group"]),
        "compoundness_status": "not_applicable",
        "grouped_order": "",
        "shuffled_order": "",
        "wav_path": str(linked.get("wav_path", "")),
        "active_textgrid_path": str(linked.get("active_textgrid_path", "")),
        "target_xmin": str(linked.get("target_xmin", "")),
        "target_xmax": str(linked.get("target_xmax", "")),
        "timing_status": str(linked.get("timing_status", "")),
        "target_word_indices_json": str(linked.get("target_word_indices_json", "")),
        "target_word_labels_json": str(linked.get("target_word_labels_json", "")),
        "surface_analysis_status": "not_yet_manually_verified",
        "realization_status": "not_judged",
        "selection_reason": "replace_excluded_overt_surface_vcp_with_same_year_primary",
        "match_evidence_json": str(candidate["match_evidence_json"]),
        "interpretation_limit": str(candidate.get("interpretation_limit", "")),
    }


def retained_candidate_ready(candidate: Mapping[str, str]) -> bool:
    """Use the renamed availability field in the zero-drop accounting CSV."""

    return (
        candidate.get("candidate_availability_status")
        == "candidate_ready_for_manual_realization_review"
        and Path(str(candidate.get("wav_path", ""))).is_file()
        and Path(str(candidate.get("active_textgrid_path", ""))).is_file()
    )


def assign_orders(rows: list[dict[str, str]]) -> None:
    grouped = sorted(
        rows,
        key=lambda row: (
            EXPECTED_CODES.index(row["phenomenon_code"]),
            row["morpheme_combination"],
            row["active_form"],
            int(row["year"]),
            row["sample_id"],
        ),
    )
    shuffled = sorted(
        rows,
        key=lambda row: stable_rank(
            "stage2-two-hour-seven-phenomena-20260823-v2",
            row["phenomenon_code"],
            "shuffle",
            row["physical_occurrence_ref"],
        ),
    )
    grouped_index = {row["sample_id"]: index for index, row in enumerate(grouped, 1)}
    shuffled_index = {row["sample_id"]: index for index, row in enumerate(shuffled, 1)}
    for row in rows:
        row["grouped_order"] = str(grouped_index[row["sample_id"]])
        row["shuffled_order"] = str(shuffled_index[row["sample_id"]])
    rows.sort(key=lambda row: grouped_index[row["sample_id"]])


def build(
    *,
    final_path: Path,
    augment_receipt_path: Path,
    candidate_path: Path,
    query_receipt_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    require(not output_dir.exists(), f"output already exists: {output_dir}")
    report = preflight(
        final_path=final_path,
        augment_receipt_path=augment_receipt_path,
        candidate_path=candidate_path,
        query_receipt_path=query_receipt_path,
    )
    original = read_csv(final_path)
    candidates = read_csv(candidate_path)
    excluded: list[tuple[dict[str, str], dict[str, str]]] = []
    retained: list[dict[str, str]] = []
    accounting: list[dict[str, str]] = []
    for row in original:
        classification = vcp_surface_class(row) if row.get("query_id") == VCP_QUERY_ID else None
        if classification and classification["status"] != "eligible_surface_yo_analyzer_i_yo":
            require(
                classification["status"] == "excluded_overt_surface_copular_i",
                f"unresolved selected VCP row requires researcher decision: {row['sample_id']}",
            )
            excluded.append((row, classification))
            accounting.append(
                {
                    "record_kind": "original_selected_row",
                    "original_sample_id": row["sample_id"],
                    "original_occurrence_ref": row["physical_occurrence_ref"],
                    "final_sample_id": "",
                    "final_occurrence_ref": "",
                    "year": row["year"],
                    "query_id": row["query_id"],
                    "scope_status": classification["status"],
                    "scope_reason": classification["reason"],
                    "source_candidate_row_id": "",
                    "surface_target_token": classification["token"],
                    "surface_suffix_after_left_morph": classification["suffix"],
                }
            )
        else:
            retained.append(dict(row))
            accounting.append(
                {
                    "record_kind": "original_selected_row",
                    "original_sample_id": row["sample_id"],
                    "original_occurrence_ref": row["physical_occurrence_ref"],
                    "final_sample_id": row["sample_id"],
                    "final_occurrence_ref": row["physical_occurrence_ref"],
                    "year": row["year"],
                    "query_id": row["query_id"],
                    "scope_status": (
                        "retained_surface_yo_analyzer_i_yo"
                        if classification
                        else "retained_not_vcp_branch"
                    ),
                    "scope_reason": classification["reason"] if classification else "not a VCP surface branch",
                    "source_candidate_row_id": "",
                    "surface_target_token": classification["token"] if classification else "",
                    "surface_suffix_after_left_morph": classification["suffix"] if classification else "",
                }
            )

    used_refs = {row["physical_occurrence_ref"] for row in retained}
    replacements: list[dict[str, str]] = []
    for removed, classification in sorted(excluded, key=lambda item: item[0]["sample_id"]):
        pool = [
            row
            for row in candidates
            if row.get("phenomenon_code") == "NI"
            and row.get("query_id") == PRIMARY_QUERY_ID
            and row.get("year") == removed["year"]
            and row.get("physical_occurrence_ref") not in used_refs
            and retained_candidate_ready(row)
        ]
        pool.sort(
            key=lambda row: stable_rank(
                "stage2-two-hour-ni-scope-correction-20260823",
                removed["year"],
                row["physical_occurrence_ref"],
            )
        )
        replacement = None
        for candidate in pool:
            try:
                linked = final_row_from_candidate(candidate, removed["sample_id"])
            except ScopeCorrectionError:
                continue
            replacement = linked
            source_candidate = candidate
            break
        require(replacement is not None, f"no same-year NI primary replacement for {removed['sample_id']}")
        used_refs.add(replacement["physical_occurrence_ref"])
        replacements.append(replacement)
        accounting.append(
            {
                "record_kind": "replacement_row",
                "original_sample_id": removed["sample_id"],
                "original_occurrence_ref": removed["physical_occurrence_ref"],
                "final_sample_id": replacement["sample_id"],
                "final_occurrence_ref": replacement["physical_occurrence_ref"],
                "year": replacement["year"],
                "query_id": replacement["query_id"],
                "scope_status": "replacement_primary_selected",
                "scope_reason": "same-year primary NI candidate replaces overt-surface copular 이",
                "source_candidate_row_id": str(source_candidate.get("candidate_row_id", "")),
                "surface_target_token": classification["token"],
                "surface_suffix_after_left_morph": classification["suffix"],
            }
        )

    final = retained + replacements
    assign_orders(final)
    require(len(final) == 84, f"corrected final row count: {len(final)}")
    require(len({row["sample_id"] for row in final}) == 84, "corrected sample IDs are not unique")
    require(
        len({(row["phenomenon_code"], row["physical_occurrence_ref"]) for row in final}) == 84,
        "corrected occurrences are duplicated within a phenomenon",
    )
    counts = Counter(row["phenomenon_code"] for row in final)
    year_counts = Counter((row["phenomenon_code"], row["year"]) for row in final)
    require(all(counts[code] == 12 for code in EXPECTED_CODES), f"phenomenon counts: {counts}")
    require(
        all(year_counts[(code, str(year))] == 2 for code in EXPECTED_CODES for year in EXPECTED_YEARS),
        "phenomenon-year quota differs from two",
    )
    selected_vcp = [row for row in final if row["query_id"] == VCP_QUERY_ID]
    require(
        all(vcp_surface_class(row)["status"] == "eligible_surface_yo_analyzer_i_yo" for row in selected_vcp),
        "corrected output contains an invalid selected VCP branch",
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    final_output = output_dir / "P2H_SAMPLES_FINAL_V2.csv"
    accounting_output = output_dir / "P2H_NI_SCOPE_CORRECTION_ACCOUNTING.csv"
    receipt_output = output_dir / "P2H_NI_SCOPE_CORRECTION_RECEIPT.json"
    atomic_write_csv(final_output, FINAL_FIELDS, final)
    atomic_write_csv(accounting_output, ACCOUNTING_FIELDS, accounting)
    receipt = {
        "schema_version": "stage2_two_hour_ni_scope_correction_receipt.v1",
        "passed": True,
        "status": "ready_84_samples_user_ni_scope_applied_no_realization_judgement",
        "inputs": report["inputs"],
        "counts": {
            "input_selected_rows": len(original),
            "input_rows_accounted": sum(row["record_kind"] == "original_selected_row" for row in accounting),
            "excluded_overt_surface_copular_i": len(excluded),
            "replacement_primary_rows": len(replacements),
            "final_samples": len(final),
            "final_by_phenomenon": dict(sorted(counts.items())),
            "selected_surface_yo_analyzer_i_yo": len(selected_vcp),
            "candidate_vcp_scope_counts": report["candidate_vcp_scope_counts"],
        },
        "zero_drop": {
            "input_selected_rows": len(original),
            "retained_plus_excluded": len(retained) + len(excluded),
            "equal": len(original) == len(retained) + len(excluded),
            "excluded_rows_explicitly_accounted": len(excluded),
        },
        "replacements": [
            {
                "sample_id": row["sample_id"],
                "year": row["year"],
                "utt_id": row["utt_id"],
                "physical_occurrence_ref": row["physical_occurrence_ref"],
            }
            for row in replacements
        ],
        "outputs": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in (final_output, accounting_output)
        ],
        "safety": {
            "source_rows_scanned": 0,
            "source_modified": False,
            "audio_copied_or_processed": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "prior_outputs_overwritten": False,
        },
    }
    atomic_write_json(receipt_output, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Derive the approved NI surface-scope correction")
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--final-input", type=Path, default=root / DEFAULT_FINAL_INPUT)
    parser.add_argument("--augmentation-receipt", type=Path, default=root / DEFAULT_AUGMENT_RECEIPT)
    parser.add_argument("--candidate-accounting", type=Path, default=root / DEFAULT_CANDIDATES)
    parser.add_argument("--query-receipt", type=Path, default=root / DEFAULT_QUERY_RECEIPT)
    parser.add_argument("--output-dir", type=Path, default=root / DEFAULT_OUTPUT)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.preflight_only:
            report = preflight(
                final_path=args.final_input.resolve(),
                augment_receipt_path=args.augmentation_receipt.resolve(),
                candidate_path=args.candidate_accounting.resolve(),
                query_receipt_path=args.query_receipt.resolve(),
            )
        else:
            report = build(
                final_path=args.final_input.resolve(),
                augment_receipt_path=args.augmentation_receipt.resolve(),
                candidate_path=args.candidate_accounting.resolve(),
                query_receipt_path=args.query_receipt.resolve(),
                output_dir=args.output_dir.resolve(),
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
