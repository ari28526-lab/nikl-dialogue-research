"""Read-only independent audit of r3 G2P mismatch diagnostics."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS, edit_distance  # noqa: E402
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    REGRESSION_TOKENS,
    SOURCE_RESULT_FIELDS,
    TARGET_RESULT_FIELDS,
)
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    PATTERN_SUMMARY_FIELDS,
    RULE_MODEL_GROUP,
    SCHEMA_VERSION,
    SOURCE_DIAGNOSTIC_FIELDS,
    TARGET_DIAGNOSTIC_FIELDS,
)
from phoneme_roman import (  # noqa: E402
    PhoneClass,
    RomanUnit,
    classify_phone,
    expand_roman_eojeol,
    load_acoustic_meta,
    model_group_lookup,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCHEMA = "common_pron_r3_g2p_mismatch_diagnostics_audit.v1"
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify_fingerprint(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"diagnostic fingerprint mismatch: {label}")
    return path


def independent_phone_encodes_glide(phone: str, glide: str) -> bool:
    if glide == "W":
        return "ʷ" in phone
    if glide == "Y":
        return "ʲ" in phone or any(
            symbol in phone for symbol in ("c", "ɟ", "ɲ", "ç", "ʝ", "ɕ", "ʑ", "ʎ")
        )
    return False


def independent_representation_support(operations: Sequence[dict[str, object]]) -> set[str] | None:
    support: set[str] = set()
    edits = [index for index, operation in enumerate(operations) if operation["operation"] != "match"]
    if not edits:
        return None
    for index in edits:
        operation = operations[index]
        if operation["operation"] != "rule_only":
            return None
        neighbors = [
            operations[position]
            for position in (index - 1, index + 1)
            if 0 <= position < len(operations)
            and operations[position]["operation"] == "match"
            and operations[position]["candidate_index"] is not None
        ]
        rule_key = clean(operation["rule_key"])
        if rule_key in {"Y", "W"} and any(
            independent_phone_encodes_glide(clean(neighbor["candidate_phone"]), rule_key)
            for neighbor in neighbors
        ):
            support.add("secondary_articulation_glide")
            continue
        if any(
            clean(neighbor["candidate_key"]) == rule_key
            and neighbor["candidate_has_length"] is True
            for neighbor in neighbors
        ):
            support.add("length_marked_identical_unit")
            continue
        return None
    return support


def key_runs(keys: Sequence[str]) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for key in keys:
        if result and result[-1][0] == key:
            result[-1] = (key, result[-1][1] + 1)
        else:
            result.append((key, 1))
    return result


def independent_expected_class(
    candidate: Sequence[PhoneClass],
    rule: Sequence[RomanUnit],
    operations: Sequence[dict[str, object]],
) -> tuple[str, str, bool]:
    support = independent_representation_support(operations)
    if support:
        if support == {"length_marked_identical_unit"}:
            name = "length_supported_adjacent_identical_coalescence"
        elif support == {"secondary_articulation_glide"}:
            name = "secondary_articulation_encodes_glide"
        else:
            name = "combined_length_and_glide_encoding"
        return "representation_equivalence_candidate", name, True
    candidate_keys = [item.comparison_key for item in candidate]
    rule_keys = [item.comparison_key for item in rule]
    candidate_runs = key_runs(candidate_keys)
    rule_runs = key_runs(rule_keys)
    if [item[0] for item in candidate_runs] == [item[0] for item in rule_runs]:
        return (
            "representation_review_required",
            "run_length_difference_without_complete_length_support",
            False,
        )
    edits = [operation for operation in operations if operation["operation"] != "match"]
    if len(edits) == 1:
        edit = edits[0]
        if edit["operation"] == "substitution":
            if edit["candidate_model_group"] == edit["rule_model_group"]:
                return "contrast_review_required", "single_contrast_within_acoustic_model_group", False
            return "substantive_difference_candidate", "single_cross_group_substitution", False
        if edit["operation"] == "candidate_only":
            return "substantive_difference_candidate", "single_candidate_unit_extra", False
        if edit["operation"] == "rule_only":
            return "substantive_difference_candidate", "single_rule_unit_missing_from_candidate", False
    substitutions = [edit for edit in edits if edit["operation"] == "substitution"]
    gaps = [edit for edit in edits if edit["operation"] != "substitution"]
    if substitutions and not gaps and all(
        edit["candidate_model_group"] == edit["rule_model_group"] for edit in substitutions
    ):
        return "contrast_review_required", "multiple_contrasts_within_acoustic_model_group", False
    if gaps and not substitutions:
        return "substantive_difference_candidate", "multiple_segment_count_difference", False
    return "substantive_difference_candidate", "mixed_or_cross_group_difference", False


def validate_operations(
    *,
    target: str,
    candidate: Sequence[PhoneClass],
    rule: Sequence[RomanUnit],
    operations: Sequence[dict[str, object]],
) -> tuple[int, str]:
    candidate_seen: list[int] = []
    rule_seen: list[int] = []
    signature: list[str] = []
    for operation in operations:
        name = clean(operation["operation"])
        candidate_index = operation["candidate_index"]
        rule_index = operation["rule_index"]
        if candidate_index is not None:
            index = int(candidate_index)
            candidate_seen.append(index)
            phone = candidate[index]
            expected_candidate = {
                "candidate_phone": phone.phone_mfa,
                "candidate_display": phone.phone_class_r_auto,
                "candidate_key": phone.comparison_key,
                "candidate_model_group": phone.model_group_r,
                "candidate_has_length": phone.has_length,
            }
            if any(operation[key] != value for key, value in expected_candidate.items()):
                raise RuntimeError(f"candidate operation evidence differs: {target}")
        else:
            if any(clean(operation[key]) for key in ("candidate_phone", "candidate_display", "candidate_key", "candidate_model_group")) or operation["candidate_has_length"] is not None:
                raise RuntimeError(f"candidate gap evidence differs: {target}")
        if rule_index is not None:
            index = int(rule_index)
            rule_seen.append(index)
            reference = rule[index]
            expected_rule = {
                "rule_display": reference.display,
                "rule_key": reference.comparison_key,
                "rule_model_group": RULE_MODEL_GROUP[reference.display],
            }
            if any(operation[key] != value for key, value in expected_rule.items()):
                raise RuntimeError(f"rule operation evidence differs: {target}")
        elif any(clean(operation[key]) for key in ("rule_display", "rule_key", "rule_model_group")):
            raise RuntimeError(f"rule gap evidence differs: {target}")
        if name == "match":
            if candidate_index is None or rule_index is None or operation["candidate_key"] != operation["rule_key"]:
                raise RuntimeError(f"invalid match operation: {target}")
        elif name == "substitution":
            if candidate_index is None or rule_index is None or operation["candidate_key"] == operation["rule_key"]:
                raise RuntimeError(f"invalid substitution operation: {target}")
            signature.append(f"SUB:{operation['candidate_key']}>{operation['rule_key']}")
        elif name == "candidate_only":
            if candidate_index is None or rule_index is not None:
                raise RuntimeError(f"invalid candidate-only operation: {target}")
            signature.append(f"CANDIDATE_ONLY:{operation['candidate_key']}")
        elif name == "rule_only":
            if candidate_index is not None or rule_index is None:
                raise RuntimeError(f"invalid rule-only operation: {target}")
            signature.append(f"RULE_ONLY:{operation['rule_key']}")
        else:
            raise RuntimeError(f"unknown operation: {target} {name}")
    if candidate_seen != list(range(len(candidate))) or rule_seen != list(range(len(rule))):
        raise RuntimeError(f"operation index coverage differs: {target}")
    return len(signature), ";".join(signature)


def next_mismatch(reader: csv.DictReader) -> dict[str, str] | None:
    for row in reader:
        if clean(row["comparison_status"]) == "different_rule_roman":
            return row
    return None


def audit_diagnostics(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_diagnostics_not_selected":
        raise RuntimeError("diagnostic manifest is not successful")
    scope = manifest.get("scope", {})
    required_false = (
        "representation_equivalence_candidate_is_approved",
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "actual_realization_claimed",
    )
    if any(scope.get(key) is not False for key in required_false):
        raise RuntimeError("diagnostic manifest exceeded scope")
    inputs = {key: verify_fingerprint(record, label=f"input {key}") for key, record in manifest["inputs"].items()}
    outputs = {key: verify_fingerprint(record, label=f"output {key}") for key, record in manifest["outputs"].items()}
    group_lookup = model_group_lookup(load_acoustic_meta(inputs["acoustic_model"]))

    target_class: Counter[str] = Counter()
    target_layer: Counter[str] = Counter()
    target_rows = 0
    target_lookup: dict[str, tuple[str, str, str, str]] = {}
    agreement_targets: dict[str, dict[str, str]] = {}
    with gzip.open(inputs["target_agreement"], "rt", encoding="utf-8-sig", newline="") as agreement_stream:
        agreement_reader = csv.DictReader(agreement_stream)
        if tuple(agreement_reader.fieldnames or ()) != TARGET_RESULT_FIELDS:
            raise RuntimeError("agreement target column contract mismatch")
        for row in agreement_reader:
            if clean(row["comparison_status"]) != "different_rule_roman":
                continue
            target = clean(row["target_hangul"])
            if target in agreement_targets:
                raise RuntimeError(f"duplicate agreement target: {target}")
            agreement_targets[target] = row
    with gzip.open(outputs["target_diagnostics"], "rt", encoding="utf-8-sig", newline="") as diagnostic_stream:
        diagnostic_reader = csv.DictReader(diagnostic_stream)
        if tuple(diagnostic_reader.fieldnames or ()) != TARGET_DIAGNOSTIC_FIELDS:
            raise RuntimeError("target column contract mismatch")
        for diagnostic in diagnostic_reader:
            target = clean(diagnostic["target_hangul"])
            agreement = agreement_targets.pop(target, None)
            if agreement is None:
                raise RuntimeError(f"extra target diagnostic row: {target}")
            if any(diagnostic[field] != agreement[field] for field in TARGET_RESULT_FIELDS):
                raise RuntimeError(f"target diagnostic/base differs: {target}")
            phones = tuple(clean(diagnostic["g2p_candidate_phones"]).split())
            candidate = tuple(classify_phone(phone, group_lookup) for phone in phones)
            rule = tuple(expand_roman_eojeol(diagnostic["rule_pron_roman"]))
            operations = json.loads(diagnostic["edit_operations_json"])
            if not isinstance(operations, list) or any(not isinstance(item, dict) for item in operations):
                raise RuntimeError(f"invalid operations JSON: {target}")
            distance, signature = validate_operations(target=target, candidate=candidate, rule=rule, operations=operations)
            candidate_keys = [item.comparison_key for item in candidate]
            rule_keys = [item.comparison_key for item in rule]
            if (
                distance != int(diagnostic["comparison_edit_distance"])
                or distance != edit_distance(tuple(candidate_keys), tuple(rule_keys))
                or signature != clean(diagnostic["edit_signature"])
                or json.loads(diagnostic["candidate_comparison_keys_json"]) != candidate_keys
                or json.loads(diagnostic["rule_comparison_keys_json"]) != rule_keys
            ):
                raise RuntimeError(f"target edit recomputation differs: {target}")
            expected_layer, expected_class, expected_equivalence = independent_expected_class(candidate, rule, operations)
            if (
                clean(diagnostic["diagnostic_layer"]) != expected_layer
                or clean(diagnostic["diagnostic_class"]) != expected_class
                or clean(diagnostic["representation_equivalence_candidate"]) != str(expected_equivalence).lower()
                or clean(diagnostic["automatic_equivalence_approved"]) != "false"
                or clean(diagnostic["manual_decision_id"])
            ):
                raise RuntimeError(f"target diagnostic class differs: {target}")
            target_lookup[target] = (signature, expected_layer, expected_class, str(expected_equivalence).lower())
            target_rows += 1
            target_layer[expected_layer] += 1
            target_class[expected_class] += 1
    if agreement_targets:
        raise RuntimeError(f"target diagnostic coverage incomplete: {len(agreement_targets)}")

    source_class: Counter[str] = Counter()
    source_layer: Counter[str] = Counter()
    source_rows = 0
    pattern: dict[tuple[str, str, int, str], dict[str, object]] = {}
    regression: dict[str, dict[str, str]] = {}
    with gzip.open(inputs["source_agreement"], "rt", encoding="utf-8-sig", newline="") as agreement_stream, gzip.open(outputs["source_diagnostics"], "rt", encoding="utf-8-sig", newline="") as diagnostic_stream:
        agreement_reader = csv.DictReader(agreement_stream)
        diagnostic_reader = csv.DictReader(diagnostic_stream)
        if tuple(agreement_reader.fieldnames or ()) != SOURCE_RESULT_FIELDS or tuple(diagnostic_reader.fieldnames or ()) != SOURCE_DIAGNOSTIC_FIELDS:
            raise RuntimeError("source column contract mismatch")
        for diagnostic in diagnostic_reader:
            agreement = next_mismatch(agreement_reader)
            if agreement is None:
                raise RuntimeError("extra source diagnostic row")
            token = clean(diagnostic["token"])
            if any(diagnostic[field] != agreement[field] for field in SOURCE_RESULT_FIELDS):
                raise RuntimeError(f"source diagnostic/base differs: {token}")
            target = clean(diagnostic["target_hangul"])
            if target not in target_lookup:
                raise RuntimeError(f"source diagnostic target missing: {token}")
            signature, layer, diagnostic_class, equivalence = target_lookup[target]
            if (
                clean(diagnostic["edit_signature"]) != signature
                or clean(diagnostic["diagnostic_layer"]) != layer
                or clean(diagnostic["diagnostic_class"]) != diagnostic_class
                or clean(diagnostic["representation_equivalence_candidate"]) != equivalence
                or clean(diagnostic["automatic_equivalence_approved"]) != "false"
            ):
                raise RuntimeError(f"source diagnostic link differs: {token}")
            key = (layer, diagnostic_class, int(diagnostic["comparison_edit_distance"]), signature)
            aggregate = pattern.setdefault(
                key,
                {
                    "targets": set(),
                    "source_type_count": 0,
                    "total_occurrences": 0,
                    **{f"count_{year}": 0 for year in YEARS},
                    "example_targets": [],
                    "example_tokens": [],
                },
            )
            aggregate["targets"].add(target)
            aggregate["source_type_count"] += 1
            aggregate["total_occurrences"] += int(diagnostic["total_occurrences"])
            for year in YEARS:
                aggregate[f"count_{year}"] += int(diagnostic[f"count_{year}"])
            if len(aggregate["example_targets"]) < 5 and target not in aggregate["example_targets"]:
                aggregate["example_targets"].append(target)
            if len(aggregate["example_tokens"]) < 5 and token not in aggregate["example_tokens"]:
                aggregate["example_tokens"].append(token)
            source_rows += 1
            source_layer[layer] += 1
            source_class[diagnostic_class] += 1
            if token in REGRESSION_TOKENS:
                regression[token] = diagnostic
        if next_mismatch(agreement_reader) is not None:
            raise RuntimeError("source diagnostic coverage incomplete")

    actual_patterns: dict[tuple[str, str, int, str], dict[str, str]] = {}
    with outputs["pattern_summary"].open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PATTERN_SUMMARY_FIELDS:
            raise RuntimeError("pattern summary column contract mismatch")
        for row in reader:
            key = (clean(row["diagnostic_layer"]), clean(row["diagnostic_class"]), int(row["comparison_edit_distance"]), clean(row["edit_signature"]))
            if key in actual_patterns:
                raise RuntimeError(f"duplicate pattern row: {key}")
            actual_patterns[key] = row
    if set(actual_patterns) != set(pattern):
        raise RuntimeError("pattern summary key set differs")
    for key, expected in pattern.items():
        row = actual_patterns[key]
        numbers = {
            "target_count": len(expected["targets"]),
            "source_type_count": expected["source_type_count"],
            "total_occurrences": expected["total_occurrences"],
            **{f"count_{year}": expected[f"count_{year}"] for year in YEARS},
        }
        if (
            any(int(row[field]) != value for field, value in numbers.items())
            or json.loads(row["example_targets_json"]) != expected["example_targets"]
            or json.loads(row["example_tokens_json"]) != expected["example_tokens"]
            or clean(row["automatic_equivalence_approved"]) != "false"
        ):
            raise RuntimeError(f"pattern summary aggregate differs: {key}")

    counts = manifest["counts"]
    if (
        int(counts["target_rows"]) != target_rows
        or int(counts["source_rows"]) != source_rows
        or int(counts["pattern_rows"]) != len(pattern)
        or counts["target_layers"] != dict(sorted(target_layer.items()))
        or counts["target_classes"] != dict(sorted(target_class.items()))
        or counts["source_layers"] != dict(sorted(source_layer.items()))
        or counts["source_classes"] != dict(sorted(source_class.items()))
        or int(counts["automatic_equivalence_approved"]) != 0
    ):
        raise RuntimeError("diagnostic manifest aggregate counts differ")

    result: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": {
            "target_rows": target_rows,
            "source_rows": source_rows,
            "pattern_rows": len(pattern),
            "target_layers": dict(sorted(target_layer.items())),
            "target_classes": dict(sorted(target_class.items())),
            "source_layers": dict(sorted(source_layer.items())),
            "source_classes": dict(sorted(source_class.items())),
            "automatic_equivalence_approved": 0,
        },
        "regression_mismatch_sources": {
            token: {
                "diagnostic_layer": clean(row["diagnostic_layer"]),
                "diagnostic_class": clean(row["diagnostic_class"]),
                "edit_signature": clean(row["edit_signature"]),
            }
            for token, row in sorted(regression.items())
        },
        "contracts": {
            "representation_equivalence_candidate_is_approved": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "diagnostic_manifest": file_fingerprint(manifest_path, with_sha256=True),
            **{key: file_fingerprint(path, with_sha256=True) for key, path in outputs.items()},
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(audit_report, result)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--audit-report", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = audit_diagnostics(
        manifest_path=args.manifest.resolve(),
        audit_report=args.audit_report.resolve(),
    )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
