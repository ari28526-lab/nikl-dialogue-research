"""Summarize r3 mismatch diagnostics and build a compact pattern handoff."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_g2p_agreement_gate import REGRESSION_TOKENS  # noqa: E402
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    PATTERN_SUMMARY_FIELDS,
    SCHEMA_VERSION,
    SOURCE_DIAGNOSTIC_FIELDS,
    TARGET_DIAGNOSTIC_FIELDS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_SCHEMA = "common_pron_r3_g2p_mismatch_diagnostics_summary.v1"
DECISION_FIELDS = (
    "review_order",
    "selection_reasons",
    "diagnostic_layer",
    "diagnostic_class",
    "comparison_edit_distance",
    "edit_signature",
    "target_count",
    "source_type_count",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
    "mismatch_occurrence_percent",
    "example_targets_json",
    "example_tokens_json",
    "proposed_policy",
    "review_question_ko",
    "decision",
    "notes",
    "automatic_equivalence_approved",
)
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def percentage(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 3) if denominator else 0.0


def verify_fingerprint(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"mismatch diagnostic fingerprint differs: {label}")
    return path


def atomic_write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with temp.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=DECISION_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def proposed_policy(row: dict[str, str]) -> tuple[str, str]:
    diagnostic_class = clean(row["diagnostic_class"])
    layer = clean(row["diagnostic_layer"])
    if diagnostic_class == "length_supported_adjacent_identical_coalescence":
        return (
            "review_model_unitization_equivalence",
            "장음 phone 하나가 같은 규칙 단위 둘을 나타내는 표상으로 인정할 수 있는가?",
        )
    if diagnostic_class == "secondary_articulation_encodes_glide":
        return (
            "review_model_unitization_equivalence",
            "palatal/labial phone 하나가 규칙 Roman Y/W를 포함하는 표상으로 인정할 수 있는가?",
        )
    if diagnostic_class == "combined_length_and_glide_encoding":
        return (
            "review_model_unitization_equivalence",
            "장음 병합과 Y/W 흡수를 함께 model phone 표상 차이로 인정할 수 있는가?",
        )
    if layer == "representation_review_required":
        return (
            "hold_for_pattern_review",
            "길이 차이를 지지하는 phone 표지가 없으므로 별도 보류할 것인가?",
        )
    if layer == "contrast_review_required":
        return (
            "preserve_phonological_contrast_hold",
            "같은 acoustic group이어도 평음·격음·경음 대립을 자동 합치지 않는 정책을 유지할 것인가?",
        )
    return (
        "reject_automatic_g2p_selection_seek_alternative_projection",
        "규칙 단위와 실질적으로 달라 G2P 자동 선택에서 제외하고 규칙 기반 phone projection을 찾을 것인가?",
    )


def summarize(
    *, manifest_path: Path, report_path: Path, decision_table_path: Path
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_diagnostics_not_selected":
        raise RuntimeError("mismatch diagnostics are not complete")
    if manifest.get("scope", {}).get("representation_equivalence_candidate_is_approved") is not False:
        raise RuntimeError("diagnostic manifest already approved equivalence")
    outputs = {key: verify_fingerprint(record, label=key) for key, record in manifest["outputs"].items()}

    target_layers: Counter[str] = Counter()
    target_classes: Counter[str] = Counter()
    target_distances: Counter[int] = Counter()
    with gzip.open(outputs["target_diagnostics"], "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_DIAGNOSTIC_FIELDS:
            raise RuntimeError("target diagnostic column contract mismatch")
        for row in reader:
            target_layers[clean(row["diagnostic_layer"])] += 1
            target_classes[clean(row["diagnostic_class"])] += 1
            target_distances[int(row["comparison_edit_distance"])] += 1

    source_layers: Counter[str] = Counter()
    source_classes: Counter[str] = Counter()
    occurrence_layers: Counter[str] = Counter()
    occurrence_classes: Counter[str] = Counter()
    year_layers: dict[str, Counter[str]] = {year: Counter() for year in YEARS}
    year_classes: dict[str, Counter[str]] = {year: Counter() for year in YEARS}
    regression: dict[str, dict[str, str]] = {}
    with gzip.open(outputs["source_diagnostics"], "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SOURCE_DIAGNOSTIC_FIELDS:
            raise RuntimeError("source diagnostic column contract mismatch")
        for row in reader:
            layer = clean(row["diagnostic_layer"])
            diagnostic_class = clean(row["diagnostic_class"])
            total = int(row["total_occurrences"])
            source_layers[layer] += 1
            source_classes[diagnostic_class] += 1
            occurrence_layers[layer] += total
            occurrence_classes[diagnostic_class] += total
            for year in YEARS:
                count = int(row[f"count_{year}"])
                year_layers[year][layer] += count
                year_classes[year][diagnostic_class] += count
            if clean(row["token"]) in REGRESSION_TOKENS:
                regression[clean(row["token"])] = row

    patterns: list[dict[str, str]] = []
    with outputs["pattern_summary"].open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PATTERN_SUMMARY_FIELDS:
            raise RuntimeError("pattern summary column contract mismatch")
        patterns = list(reader)
    pattern_lookup = {
        (
            clean(row["diagnostic_layer"]),
            clean(row["diagnostic_class"]),
            int(row["comparison_edit_distance"]),
            clean(row["edit_signature"]),
        ): row
        for row in patterns
    }
    if len(pattern_lookup) != len(patterns):
        raise RuntimeError("pattern summary contains duplicate keys")

    selected: dict[tuple[str, str, int, str], set[str]] = defaultdict(set)
    sorted_patterns = sorted(patterns, key=lambda row: (-int(row["total_occurrences"]), clean(row["diagnostic_class"]), clean(row["edit_signature"])))
    for row in sorted_patterns[:30]:
        key = (clean(row["diagnostic_layer"]), clean(row["diagnostic_class"]), int(row["comparison_edit_distance"]), clean(row["edit_signature"]))
        selected[key].add("top_30_by_occurrence")
    by_class: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in sorted_patterns:
        by_class[clean(row["diagnostic_class"])].append(row)
    for diagnostic_class, rows in by_class.items():
        for row in rows[:5]:
            key = (clean(row["diagnostic_layer"]), diagnostic_class, int(row["comparison_edit_distance"]), clean(row["edit_signature"]))
            selected[key].add("top_5_within_class")
    for row in patterns:
        if clean(row["diagnostic_layer"]) == "representation_review_required":
            key = (clean(row["diagnostic_layer"]), clean(row["diagnostic_class"]), int(row["comparison_edit_distance"]), clean(row["edit_signature"]))
            selected[key].add("all_unresolved_representation_patterns")
    for token, row in regression.items():
        key = (clean(row["diagnostic_layer"]), clean(row["diagnostic_class"]), int(row["comparison_edit_distance"]), clean(row["edit_signature"]))
        if key not in pattern_lookup:
            raise RuntimeError(f"regression pattern missing: {token}")
        selected[key].add(f"known_regression:{token}")

    total_mismatch_occurrences = sum(occurrence_layers.values())
    decision_rows: list[dict[str, object]] = []
    selected_patterns = sorted(
        [(pattern_lookup[key], reasons) for key, reasons in selected.items()],
        key=lambda item: (
            -int(item[0]["total_occurrences"]),
            clean(item[0]["diagnostic_class"]),
            clean(item[0]["edit_signature"]),
        ),
    )
    for order, (row, reasons) in enumerate(selected_patterns, 1):
        policy, question = proposed_policy(row)
        decision_rows.append(
            {
                "review_order": order,
                "selection_reasons": ";".join(sorted(reasons)),
                **{field: row[field] for field in (
                    "diagnostic_layer",
                    "diagnostic_class",
                    "comparison_edit_distance",
                    "edit_signature",
                    "target_count",
                    "source_type_count",
                    "total_occurrences",
                    *(f"count_{year}" for year in YEARS),
                    "example_targets_json",
                    "example_tokens_json",
                )},
                "mismatch_occurrence_percent": percentage(int(row["total_occurrences"]), total_mismatch_occurrences),
                "proposed_policy": policy,
                "review_question_ko": question,
                "decision": "pending",
                "notes": "",
                "automatic_equivalence_approved": "false",
            }
        )
    atomic_write_csv(decision_table_path, decision_rows)

    selected_occurrences = sum(int(row["total_occurrences"]) for row, _ in selected_patterns)
    result: dict[str, object] = {
        "schema_version": REPORT_SCHEMA,
        "status": "summarized_diagnostics_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "pattern_handoff_only": True,
            "review_required_before_canonical_selection": True,
            "researcher_review_required_now": False,
            "representation_equivalence_candidate_is_approved": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
        },
        "target_results": {
            "total": sum(target_layers.values()),
            "layers": dict(sorted(target_layers.items())),
            "classes": dict(sorted(target_classes.items())),
            "edit_distance_distribution": {str(key): value for key, value in sorted(target_distances.items())},
        },
        "source_results": {
            "total_rows": sum(source_layers.values()),
            "rows_by_layer": dict(sorted(source_layers.items())),
            "rows_by_class": dict(sorted(source_classes.items())),
            "total_occurrences": total_mismatch_occurrences,
            "occurrences_by_layer": dict(sorted(occurrence_layers.items())),
            "occurrences_by_class": dict(sorted(occurrence_classes.items())),
            "occurrence_percent_by_layer": {
                key: percentage(value, total_mismatch_occurrences)
                for key, value in sorted(occurrence_layers.items())
            },
        },
        "year_results": {
            year: {
                "total_occurrences": sum(year_layers[year].values()),
                "occurrences_by_layer": dict(sorted(year_layers[year].items())),
                "occurrence_percent_by_layer": {
                    key: percentage(value, sum(year_layers[year].values()))
                    for key, value in sorted(year_layers[year].items())
                },
                "occurrences_by_class": dict(sorted(year_classes[year].items())),
            }
            for year in YEARS
        },
        "regression_sources": {
            token: {
                "comparison_status": clean(row["comparison_status"]),
                "diagnostic_layer": clean(row["diagnostic_layer"]),
                "diagnostic_class": clean(row["diagnostic_class"]),
                "edit_signature": clean(row["edit_signature"]),
                "automatic_equivalence_approved": False,
            }
            for token, row in sorted(regression.items())
        },
        "exact_regression_sources_not_in_mismatch": [
            token for token in REGRESSION_TOKENS if token not in regression
        ],
        "handoff": {
            "all_pattern_rows": len(patterns),
            "decision_rows": len(decision_rows),
            "selected_occurrences": selected_occurrences,
            "selected_occurrence_percent": percentage(selected_occurrences, total_mismatch_occurrences),
            "not_an_adoption_approval": True,
            "decision_table": file_fingerprint(decision_table_path, with_sha256=True),
        },
        "inputs": {
            "diagnostic_manifest": file_fingerprint(manifest_path, with_sha256=True),
            **{key: file_fingerprint(path, with_sha256=True) for key, path in outputs.items()},
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(report_path, result)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--decision-table", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = summarize(
        manifest_path=args.manifest.resolve(),
        report_path=args.report.resolve(),
        decision_table_path=args.decision_table.resolve(),
    )
    print(json.dumps({
        "source_results": result["source_results"],
        "handoff": result["handoff"],
        "regression_sources": result["regression_sources"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
