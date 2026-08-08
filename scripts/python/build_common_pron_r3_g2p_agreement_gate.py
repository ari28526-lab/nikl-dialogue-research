"""Build the r3 G2P/rule agreement gate without selecting final pronunciations.

The 1-best G2P output is only a backend candidate.  This stage compares its
ordered acoustic-model broad-Roman units with the independently prepared rule
target.  Target-level technical agreement and source-token evidence routing
remain separate so dictionary or morphology conflicts are not erased when
multiple source types share one respelled Hangul target.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import (  # noqa: E402
    YEARS,
    edit_distance,
    phone_units,
    roman_units,
)
from phoneme_roman import load_acoustic_meta, model_group_lookup  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)
from prepare_common_pron_r3_g2p_targets import (  # noqa: E402
    ELIGIBLE_STATUSES,
    TARGET_FIELDS,
)
from resolve_common_pron_r3_surface_donors import (  # noqa: E402
    OUTPUT_FIELDS as SOURCE_FIELDS,
)
from verify_common_pron_r3_g2p_candidates import (  # noqa: E402
    read_one_best_output,
    verify_existing_report,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_g2p_agreement_gate.v1"
TARGET_RESULT_FIELDS = (
    "target_hangul",
    "g2p_model_input",
    "rule_pron_roman",
    "rule_pron_roman_normalized",
    "g2p_candidate_phones",
    "g2p_candidate_roman",
    "comparison_status",
    "comparison_edit_distance",
    "gate_class",
    "source_type_count",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
    "source_selection_statuses_json",
    "priority",
    "rewrite_rule",
    "candidate_is_final_selection",
)
SOURCE_RESULT_FIELDS = (
    "token",
    "target_hangul",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
    "orth_roman",
    "rule_pron_hangul",
    "rule_pron_roman",
    "surface_rule_names",
    "dictionary_pron_hangul_json",
    "dictionary_pron_roman_json",
    "dictionary_source_refs_json",
    "r2_pron_phones_json",
    "r2_pron_roman_json",
    "r2_pron_source",
    "original_selection_status",
    "original_selection_reason",
    "g2p_model_input",
    "g2p_candidate_phones",
    "g2p_candidate_roman",
    "comparison_status",
    "comparison_edit_distance",
    "target_gate_class",
    "source_gate_class",
    "candidate_is_final_selection",
    "morph_context_required",
    "manual_decision_id",
)
SUMMARY_FIELDS = (
    "layer",
    "gate_class",
    "target_count",
    "source_type_count",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
)
REGRESSION_TOKENS = ("놨던", "어쨌든", "없는", "있는", "있지")


def clean(value: object) -> str:
    return str(value or "").strip()


def load_string_list(value: object, *, label: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} JSON is invalid") from exc
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise RuntimeError(f"{label} must be a JSON string list")
    return result


def verify_fingerprint(record: dict[str, object], path: Path, *, label: str) -> None:
    if (
        Path(str(record["path"])).resolve() != path.resolve()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def target_gate_class(
    *, comparison_status: str, statuses: set[str], rewrite_rule: str
) -> str:
    if comparison_status != "exact_rule_roman":
        return "mismatch_not_eligible"
    if rewrite_rule != "none":
        return "hold_exact_model_input_rewrite"
    if statuses == {"candidate_replace_rule_dictionary_agree"}:
        return "exact_candidate_dictionary_agree_all_sources"
    return "hold_exact_source_evidence_review"


def source_gate_class(
    *, comparison_status: str, selection_status: str, rewrite_rule: str
) -> str:
    if comparison_status != "exact_rule_roman":
        return "mismatch_not_eligible"
    if rewrite_rule != "none":
        return "hold_exact_model_input_rewrite"
    routes = {
        "candidate_replace_rule_dictionary_agree": (
            "exact_candidate_dictionary_agree"
        ),
        "review_rule_dictionary_conflict": "hold_exact_dictionary_conflict",
        "review_rule_sensitive_no_attested_agreement": (
            "hold_exact_no_attested_agreement"
        ),
    }
    if selection_status not in routes:
        raise RuntimeError(f"unexpected r3 source selection status: {selection_status}")
    return routes[selection_status]


@contextmanager
def gzip_writer(path: Path) -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(
        path, "xt", encoding="utf-8-sig", newline="", compresslevel=6
    ) as stream:
        yield stream


def fingerprint_for_final(temp: Path, final: Path) -> dict[str, object]:
    result = file_fingerprint(temp, with_sha256=True)
    result["path"] = str(final.resolve())
    return result


def verify_existing_gate(
    output_root: Path, *, expected_inputs: dict[str, Path]
) -> dict[str, object]:
    manifest_path = output_root / "G2P_AGREEMENT_GATE_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"agreement root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "success_candidates_not_selected"
    ):
        raise RuntimeError("existing agreement manifest is not reusable")
    if set(manifest["inputs"]) != set(expected_inputs):
        raise RuntimeError("existing agreement input contract differs")
    for key, path in expected_inputs.items():
        verify_fingerprint(
            manifest["inputs"][key], path, label=f"existing input {key}"
        )
    for record in manifest["outputs"].values():
        verify_fingerprint(record, Path(str(record["path"])), label="existing output")
    return manifest


def load_candidate_outputs(
    *,
    target_manifest: dict[str, object],
    phase_manifest: dict[str, object],
    candidate_root: Path,
    acoustic_model: Path,
) -> dict[str, tuple[str, ...]]:
    output_records = {
        int(record["shard_index"]): record
        for record in phase_manifest["outputs"]["output_shards"]
    }
    candidates: dict[str, tuple[str, ...]] = {}
    for shard in target_manifest["outputs"]["input_shards"]:
        index = int(shard["shard_index"])
        input_path = Path(str(shard["path"])).resolve()
        output_path = (
            candidate_root / "output_shards" / str(shard["expected_output_name"])
        ).resolve()
        report_path = (
            candidate_root / "shard_reports" / f"g2p_target_{index:05d}.json"
        ).resolve()
        if index not in output_records:
            raise RuntimeError(f"phase manifest lacks shard {index}")
        verify_fingerprint(
            output_records[index], output_path, label=f"candidate shard {index}"
        )
        verify_existing_report(
            input_shard=input_path,
            output_shard=output_path,
            acoustic_model=acoustic_model,
            report=report_path,
        )
        shard_candidates = read_one_best_output(output_path)
        overlap = set(candidates) & set(shard_candidates)
        if overlap:
            raise RuntimeError(f"candidate keys repeat across shards: {index}")
        candidates.update(shard_candidates)
    return candidates


def selected_source(row: dict[str, str]) -> bool:
    return (
        clean(row["selected_variant_count"]) == "0"
        and clean(row["candidate_status"]) == "none"
        and clean(row["selection_status"]) in ELIGIBLE_STATUSES
    )


def add_summary(
    summary: dict[tuple[str, str], dict[str, object]],
    *,
    layer: str,
    gate_class: str,
    target: str,
    source_types: int,
    total: int,
    year_counts: dict[str, int],
) -> None:
    key = (layer, gate_class)
    record = summary.setdefault(
        key,
        {
            "targets": set(),
            "source_type_count": 0,
            "total_occurrences": 0,
            **{f"count_{year}": 0 for year in YEARS},
        },
    )
    record["targets"].add(target)
    record["source_type_count"] += source_types
    record["total_occurrences"] += total
    for year in YEARS:
        record[f"count_{year}"] += year_counts[year]


def build_gate(
    *,
    target_inventory: Path,
    target_manifest_path: Path,
    phase_manifest_path: Path,
    candidate_root: Path,
    source_inventory: Path,
    source_manifest_path: Path,
    acoustic_model: Path,
    output_root: Path,
) -> dict[str, object]:
    if candidate_root.resolve() != phase_manifest_path.resolve().parent:
        raise RuntimeError("candidate root must contain the candidate phase manifest")
    expected_inputs = {
        "target_inventory": target_inventory,
        "target_manifest": target_manifest_path,
        "candidate_phase_manifest": phase_manifest_path,
        "source_inventory": source_inventory,
        "source_manifest": source_manifest_path,
        "acoustic_model": acoustic_model,
    }
    if output_root.exists():
        return verify_existing_gate(output_root, expected_inputs=expected_inputs)

    target_manifest = json.loads(
        target_manifest_path.read_text(encoding="utf-8-sig")
    )
    phase_manifest = json.loads(phase_manifest_path.read_text(encoding="utf-8-sig"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8-sig"))
    if (
        target_manifest.get("schema_version") != "common_pron_r3_g2p_targets.v1"
        or target_manifest.get("status") != "prepared"
    ):
        raise RuntimeError("target manifest contract mismatch")
    if (
        phase_manifest.get("schema_version")
        != "common_pron_r3_g2p_candidate_phase.v1"
        or phase_manifest.get("status") != "success_candidates_not_selected"
        or phase_manifest["scope"].get("candidate_is_final_selection") is not False
    ):
        raise RuntimeError("candidate phase is not a completed candidate-only phase")
    if (
        source_manifest.get("schema_version")
        != "common_pron_r3_surface_donor_candidates.v1"
        or source_manifest.get("status") != "success_candidates_not_selected"
    ):
        raise RuntimeError("source candidate manifest contract mismatch")
    verify_fingerprint(
        target_manifest["outputs"]["target_inventory"],
        target_inventory,
        label="target inventory",
    )
    verify_fingerprint(
        phase_manifest["inputs"]["target_manifest"],
        target_manifest_path,
        label="target manifest",
    )
    verify_fingerprint(
        phase_manifest["inputs"]["acoustic_model"],
        acoustic_model,
        label="acoustic model",
    )
    verify_fingerprint(
        source_manifest["outputs"]["candidate_inventory"],
        source_inventory,
        label="source inventory",
    )

    candidates = load_candidate_outputs(
        target_manifest=target_manifest,
        phase_manifest=phase_manifest,
        candidate_root=candidate_root,
        acoustic_model=acoustic_model,
    )
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))
    decisions: dict[str, dict[str, object]] = {}
    model_inputs: set[str] = set()
    with gzip.open(
        target_inventory, "rt", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_FIELDS:
            raise RuntimeError("target inventory column contract mismatch")
        for row in reader:
            target = clean(row["target_hangul"])
            model_input = clean(row["g2p_model_input"])
            if target in decisions or model_input in model_inputs:
                raise RuntimeError(f"target/model input duplicate: {target}")
            if model_input not in candidates:
                raise RuntimeError(f"candidate output missing: {model_input}")
            phones = candidates[model_input]
            candidate_display, candidate_keys = phone_units(phones, group_lookup)
            rule_display, rule_keys = roman_units(row["rule_pron_roman"])
            if not candidate_keys or not rule_keys:
                raise RuntimeError(f"empty comparison units: {target}")
            comparison = (
                "exact_rule_roman"
                if candidate_keys == rule_keys
                else "different_rule_roman"
            )
            statuses = set(
                load_string_list(
                    row["source_selection_statuses_json"],
                    label=f"{target} source statuses",
                )
            )
            if not statuses or not statuses <= ELIGIBLE_STATUSES:
                raise RuntimeError(f"unexpected target source statuses: {target}")
            decisions[target] = {
                "target_hangul": target,
                "g2p_model_input": model_input,
                "rule_pron_roman": clean(row["rule_pron_roman"]),
                "rule_pron_roman_normalized": " ".join(rule_display),
                "g2p_candidate_phones": " ".join(phones),
                "g2p_candidate_roman": " ".join(candidate_display),
                "comparison_status": comparison,
                "comparison_edit_distance": edit_distance(candidate_keys, rule_keys),
                "gate_class": target_gate_class(
                    comparison_status=comparison,
                    statuses=statuses,
                    rewrite_rule=clean(row["rewrite_rule"]),
                ),
                "source_type_count": int(row["source_type_count"]),
                "total_occurrences": int(row["total_occurrences"]),
                "source_selection_statuses_json": json.dumps(
                    sorted(statuses), ensure_ascii=False
                ),
                "priority": int(row["priority"]),
                "rewrite_rule": clean(row["rewrite_rule"]),
            }
            model_inputs.add(model_input)
    if set(candidates) != model_inputs:
        raise RuntimeError("candidate output keys differ from target model inputs")
    if len(decisions) != int(target_manifest["counts"]["unique_targets"]):
        raise RuntimeError("target inventory row count differs from manifest")
    del candidates

    aggregate: dict[str, dict[str, object]] = {
        target: {
            "source_type_count": 0,
            "total_occurrences": 0,
            "statuses": set(),
            **{f"count_{year}": 0 for year in YEARS},
        }
        for target in decisions
    }
    source_count = 0
    with gzip.open(
        source_inventory, "rt", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise RuntimeError("source inventory column contract mismatch")
        for row in reader:
            if not selected_source(row):
                continue
            source_count += 1
            target = clean(row["rule_pron_hangul"])
            if target not in aggregate:
                raise RuntimeError(f"source target missing from G2P gate: {target}")
            if clean(row["rule_pron_roman"]) != decisions[target]["rule_pron_roman"]:
                raise RuntimeError(f"source/target Roman mismatch: {row['token']}")
            record = aggregate[target]
            record["source_type_count"] += 1
            record["total_occurrences"] += int(row["total_occurrences"])
            record["statuses"].add(clean(row["selection_status"]))
            for year in YEARS:
                record[f"count_{year}"] += int(row[f"count_{year}"])
    if source_count != int(target_manifest["counts"]["source_candidate_types"]):
        raise RuntimeError("source candidate type coverage mismatch")
    for target, decision in decisions.items():
        record = aggregate[target]
        if (
            record["source_type_count"] != decision["source_type_count"]
            or record["total_occurrences"] != decision["total_occurrences"]
            or json.dumps(sorted(record["statuses"]), ensure_ascii=False)
            != decision["source_selection_statuses_json"]
        ):
            raise RuntimeError(f"target aggregate mismatch: {target}")

    temp_root = output_root.with_name(
        f".{output_root.name}.{uuid.uuid4().hex}.partial"
    )
    temp_root.mkdir(parents=True)
    target_output = temp_root / "g2p_target_agreement.csv.gz"
    source_output = temp_root / "g2p_source_agreement.csv.gz"
    summary_output = temp_root / "gate_summary.csv"
    regression_output = temp_root / "regression_examples.csv"
    manifest_output = temp_root / "G2P_AGREEMENT_GATE_MANIFEST.json"
    final_target = output_root / target_output.name
    final_source = output_root / source_output.name
    final_summary = output_root / summary_output.name
    final_regression = output_root / regression_output.name
    final_manifest = output_root / manifest_output.name
    summary: dict[tuple[str, str], dict[str, object]] = {}
    target_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    with gzip_writer(target_output) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=TARGET_RESULT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for target, decision in decisions.items():
            years = {year: int(aggregate[target][f"count_{year}"]) for year in YEARS}
            output = {
                **decision,
                **{f"count_{year}": years[year] for year in YEARS},
                "candidate_is_final_selection": "false",
            }
            writer.writerow(output)
            gate = str(decision["gate_class"])
            target_counts[gate] += 1
            add_summary(
                summary,
                layer="target",
                gate_class=gate,
                target=target,
                source_types=int(decision["source_type_count"]),
                total=int(decision["total_occurrences"]),
                year_counts=years,
            )

    regression_rows: dict[str, dict[str, object]] = {}
    with gzip.open(
        source_inventory, "rt", encoding="utf-8-sig", newline=""
    ) as source_stream, gzip_writer(source_output) as target_stream:
        reader = csv.DictReader(source_stream)
        writer = csv.DictWriter(
            target_stream, fieldnames=SOURCE_RESULT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for row in reader:
            if not selected_source(row):
                continue
            target = clean(row["rule_pron_hangul"])
            decision = decisions[target]
            route = source_gate_class(
                comparison_status=str(decision["comparison_status"]),
                selection_status=clean(row["selection_status"]),
                rewrite_rule=str(decision["rewrite_rule"]),
            )
            output: dict[str, object] = {
                "token": clean(row["token"]),
                "target_hangul": target,
                "total_occurrences": int(row["total_occurrences"]),
                "n_years_present": int(row["n_years_present"]),
                **{f"count_{year}": int(row[f"count_{year}"]) for year in YEARS},
                "orth_roman": clean(row["orth_roman"]),
                "rule_pron_hangul": target,
                "rule_pron_roman": clean(row["rule_pron_roman"]),
                "surface_rule_names": clean(row["surface_rule_names"]),
                "dictionary_pron_hangul_json": clean(
                    row["dictionary_pron_hangul_json"]
                ),
                "dictionary_pron_roman_json": clean(
                    row["dictionary_pron_roman_json"]
                ),
                "dictionary_source_refs_json": clean(
                    row["dictionary_source_refs_json"]
                ),
                "r2_pron_phones_json": clean(row["r2_pron_phones_json"]),
                "r2_pron_roman_json": clean(row["r2_pron_roman_json"]),
                "r2_pron_source": clean(row["r2_pron_source"]),
                "original_selection_status": clean(row["selection_status"]),
                "original_selection_reason": clean(row["selection_reason"]),
                "g2p_model_input": decision["g2p_model_input"],
                "g2p_candidate_phones": decision["g2p_candidate_phones"],
                "g2p_candidate_roman": decision["g2p_candidate_roman"],
                "comparison_status": decision["comparison_status"],
                "comparison_edit_distance": decision[
                    "comparison_edit_distance"
                ],
                "target_gate_class": decision["gate_class"],
                "source_gate_class": route,
                "candidate_is_final_selection": "false",
                "morph_context_required": clean(row["morph_context_required"]),
                "manual_decision_id": "",
            }
            writer.writerow(output)
            source_counts[route] += 1
            years = {year: int(row[f"count_{year}"]) for year in YEARS}
            add_summary(
                summary,
                layer="source",
                gate_class=route,
                target=target,
                source_types=1,
                total=int(row["total_occurrences"]),
                year_counts=years,
            )
            if output["token"] in REGRESSION_TOKENS:
                regression_rows[str(output["token"])] = output

    missing_regression = set(REGRESSION_TOKENS) - set(regression_rows)
    if missing_regression:
        raise RuntimeError(f"regression tokens missing: {sorted(missing_regression)}")
    with regression_output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=SOURCE_RESULT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for token in REGRESSION_TOKENS:
            writer.writerow(regression_rows[token])
    with summary_output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for (layer, gate), record in sorted(summary.items()):
            writer.writerow(
                {
                    "layer": layer,
                    "gate_class": gate,
                    "target_count": len(record["targets"]),
                    "source_type_count": record["source_type_count"],
                    "total_occurrences": record["total_occurrences"],
                    **{
                        f"count_{year}": record[f"count_{year}"]
                        for year in YEARS
                    },
                }
            )

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_candidates_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "comparison": "ordered broad-Roman exact agreement",
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "target_inventory": file_fingerprint(
                target_inventory, with_sha256=True
            ),
            "target_manifest": file_fingerprint(
                target_manifest_path, with_sha256=True
            ),
            "candidate_phase_manifest": file_fingerprint(
                phase_manifest_path, with_sha256=True
            ),
            "source_inventory": file_fingerprint(
                source_inventory, with_sha256=True
            ),
            "source_manifest": file_fingerprint(
                source_manifest_path, with_sha256=True
            ),
            "acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
        },
        "counts": {
            "target_rows": len(decisions),
            "source_rows": source_count,
            "total_occurrences": sum(
                int(value["total_occurrences"]) for value in aggregate.values()
            ),
            "target_gate_classes": dict(sorted(target_counts.items())),
            "source_gate_classes": dict(sorted(source_counts.items())),
            "regression_tokens": len(regression_rows),
        },
        "outputs": {
            "target_agreement": fingerprint_for_final(
                target_output, final_target
            ),
            "source_agreement": fingerprint_for_final(
                source_output, final_source
            ),
            "gate_summary": fingerprint_for_final(summary_output, final_summary),
            "regression_examples": fingerprint_for_final(
                regression_output, final_regression
            ),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    with manifest_output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temp_root, output_root)
    return json.loads(final_manifest.read_text(encoding="utf-8-sig"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--target-inventory", type=Path, required=True)
    result.add_argument("--target-manifest", type=Path, required=True)
    result.add_argument("--phase-manifest", type=Path, required=True)
    result.add_argument("--candidate-root", type=Path, required=True)
    result.add_argument("--source-inventory", type=Path, required=True)
    result.add_argument("--source-manifest", type=Path, required=True)
    result.add_argument("--acoustic-model", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = build_gate(
        target_inventory=args.target_inventory.resolve(),
        target_manifest_path=args.target_manifest.resolve(),
        phase_manifest_path=args.phase_manifest.resolve(),
        candidate_root=args.candidate_root.resolve(),
        source_inventory=args.source_inventory.resolve(),
        source_manifest_path=args.source_manifest.resolve(),
        acoustic_model=args.acoustic_model.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
