"""Independently audit the candidate-only global exact-donor projection v2."""

from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_r3_projection_candidates import (  # noqa: E402
    CONTEXT_LEVELS,
    Observation,
    audit_context_key,
    chosen_evidence,
    compare_base,
    expected_source_route,
    independent_relation,
    load_evidence,
    query_rule_indices,
    supported_rule_only,
)
from audit_common_pron_rule_consistency import YEARS, phone_units  # noqa: E402
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    SOURCE_RESULT_FIELDS,
    TARGET_RESULT_FIELDS,
)
from build_common_pron_r3_global_projection_v2 import (  # noqa: E402
    COMPARISON_FIELDS,
    POLICY_SCHEMA,
    SCHEMA_VERSION,
)
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    EVIDENCE_FIELDS,
    SOURCE_PROJECTION_FIELDS,
    TARGET_PROJECTION_FIELDS,
)
from build_common_pron_r3_selection_readiness import READINESS_FIELDS  # noqa: E402
from phoneme_roman import expand_roman_eojeol, load_acoustic_meta, model_group_lookup  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCHEMA = "common_pron_r3_global_projection_audit.v2"
REGRESSION_TOKENS = ("있는", "있지", "놨던", "어쨌든", "없는")
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
        raise RuntimeError(f"fingerprint mismatch: {label}")
    return path


def string_list(value: object, *, label: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON list: {label}") from exc
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise RuntimeError(f"invalid string list: {label}")
    return result


def independent_comparison_class(previous: dict[str, str], current: dict[str, str]) -> str:
    old_count = int(previous["projection_candidate_count"])
    new_count = int(current["projection_candidate_count"])
    if (
        previous["projection_status"] == current["projection_status"]
        and previous["representation_relation"] == current["representation_relation"]
        and old_count == new_count
        and previous["projected_pron_phones_json"] == current["projected_pron_phones_json"]
    ):
        return "unchanged"
    if old_count == 0 and new_count > 0:
        return "candidate_gained"
    if old_count > 0 and new_count == 0:
        return "candidate_lost"
    if (
        old_count > 0
        and new_count > 0
        and previous["projected_pron_phones_json"] != current["projected_pron_phones_json"]
    ):
        return "candidate_phone_changed"
    return "status_metadata_changed"


def audit_global_projection(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("global projection manifest differs")
    scope = manifest.get("scope", {})
    if scope.get("same_g2p_rerun_performed") is not False or scope.get("global_exact_donor_projection_applied") is not True:
        raise RuntimeError("global projection scope differs")
    false_scope = (
        "candidate_is_final_selection",
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "source_files_modified",
        "actual_realization_claimed",
    )
    if any(scope.get(key) is not False for key in false_scope):
        raise RuntimeError("global projection exceeded candidate scope")
    inputs = {key: verify_fingerprint(value, label=f"input {key}") for key, value in manifest["inputs"].items()}
    outputs = {key: verify_fingerprint(value, label=f"output {key}") for key, value in manifest["outputs"].items()}
    policy = json.loads(inputs["policy_contract"].read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "candidate_generation_only"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
        or policy.get("target_policy", {}).get("same_g2p_rerun_allowed") is not False
    ):
        raise RuntimeError("global projection policy differs")

    meta = load_acoustic_meta(inputs["acoustic_model"])
    group_lookup = model_group_lookup(meta)
    inventory = {str(phone) for phone in meta["phones"]}
    evidence = load_evidence(outputs["global_projection_evidence"], inventory)

    query_sets = {level: set() for level in CONTEXT_LEVELS}
    base_fields = TARGET_PROJECTION_FIELDS[: len(TARGET_RESULT_FIELDS) + 3]
    prior_rows = 0
    with gzip.open(inputs["prior_target_projection"], "rt", encoding="utf-8-sig", newline="") as old_stream, gzip.open(outputs["target_global_projection"], "rt", encoding="utf-8-sig", newline="") as new_stream:
        old_reader = csv.DictReader(old_stream)
        new_reader = csv.DictReader(new_stream)
        if tuple(old_reader.fieldnames or ()) != TARGET_PROJECTION_FIELDS or tuple(new_reader.fieldnames or ()) != TARGET_PROJECTION_FIELDS:
            raise RuntimeError("global target column contract differs")
        for old, new in itertools.zip_longest(old_reader, new_reader):
            if old is None or new is None:
                raise RuntimeError("global target coverage differs")
            compare_base(new, old, base_fields, old["target_hangul"])
            if old["comparison_status"] != "exact_rule_roman":
                rule = tuple(expand_roman_eojeol(old["rule_pron_roman"]))
                _, operations = independent_relation(
                    tuple(clean(old["g2p_candidate_phones"]).split()), rule, group_lookup
                )
                for rule_index in query_rule_indices(operations):
                    for level in CONTEXT_LEVELS:
                        query_sets[level].add(audit_context_key(rule, rule_index, level))
            prior_rows += 1

    donor_index: dict[str, dict[tuple[object, ...], Observation]] = {
        level: {} for level in CONTEXT_LEVELS
    }
    donor_types = donor_variants = donor_type_units = donor_variant_units = 0
    with gzip.open(inputs["selection_readiness"], "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("selection-readiness column contract differs")
        for row in reader:
            if row["planning_status"] != "candidate_r2_exact_mandatory_rule":
                continue
            target = row["token"]
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            variants = string_list(row["planning_candidate_phones_json"], label=target)
            donor_types += 1
            donor_type_units += len(rule)
            seen: set[tuple[str, tuple[object, ...]]] = set()
            for variant in variants:
                phones = tuple(clean(variant).split())
                relation, _ = independent_relation(phones, rule, group_lookup)
                if relation != "exact_comparison_keys" or len(phones) != len(rule):
                    raise RuntimeError(f"independent exact donor relation differs: {target}")
                donor_variants += 1
                donor_variant_units += len(rule)
                for index, phone in enumerate(phones):
                    for level in CONTEXT_LEVELS:
                        context = audit_context_key(rule, index, level)
                        if context not in query_sets[level]:
                            continue
                        observation = donor_index[level].setdefault(context, Observation())
                        observation.phone_counts[phone] += 1
                        observation.units += 1
                        marker = (level, context)
                        if marker not in seen:
                            observation.target_types += 1
                            seen.add(marker)
                        if target not in observation.examples and len(observation.examples) < 5:
                            observation.examples.append(target)

    for identifier, record in evidence.items():
        observation = donor_index[record["context_level"]].get(record["context"])
        if observation is None or (
            observation.target_types != int(record["support_target_type_count"])
            or observation.units != int(record["support_unit_count"])
            or dict(sorted(observation.phone_counts.items())) != record["phone_counts"]
            or observation.examples != json.loads(record["example_exact_targets_json"])
        ):
            raise RuntimeError(f"global evidence reconstruction differs: {identifier}")

    target_lookup: dict[str, tuple[str, str, int, str, str]] = {}
    target_status: Counter[str] = Counter()
    target_relation: Counter[str] = Counter()
    target_occurrences: Counter[str] = Counter()
    comparison_types: Counter[str] = Counter()
    comparison_occurrences: Counter[str] = Counter()
    referenced_evidence: set[str] = set()
    with gzip.open(inputs["prior_target_projection"], "rt", encoding="utf-8-sig", newline="") as old_stream, gzip.open(outputs["target_global_projection"], "rt", encoding="utf-8-sig", newline="") as new_stream, gzip.open(outputs["projection_comparison"], "rt", encoding="utf-8-sig", newline="") as compare_stream:
        old_reader = csv.DictReader(old_stream)
        new_reader = csv.DictReader(new_stream)
        compare_reader = csv.DictReader(compare_stream)
        if tuple(compare_reader.fieldnames or ()) != COMPARISON_FIELDS:
            raise RuntimeError("projection comparison column contract differs")
        for old, row, comparison in itertools.zip_longest(old_reader, new_reader, compare_reader):
            if old is None or row is None or comparison is None:
                raise RuntimeError("projection comparison coverage differs")
            target = old["target_hangul"]
            rule = tuple(expand_roman_eojeol(old["rule_pron_roman"]))
            original_phones = tuple(clean(old["g2p_candidate_phones"]).split())
            relation, operations = independent_relation(original_phones, rule, group_lookup)
            projected_phones = string_list(row["projected_pron_phones_json"], label=f"target phones {target}")
            projected_roman = string_list(row["projected_pron_roman_json"], label=f"target Roman {target}")
            count = int(row["projection_candidate_count"])
            status = row["projection_status"]
            if row["projection_candidate_is_final_selection"] != "false" or count != len(projected_phones) or count != len(projected_roman):
                raise RuntimeError(f"global target candidate contract differs: {target}")
            if old["comparison_status"] == "exact_rule_roman":
                expected = "candidate_exact_gate_unchanged"
                if relation != "exact_comparison_keys" or projected_phones != [old["g2p_candidate_phones"]] or row["diagnostic_layer"] != "exact_gate":
                    raise RuntimeError(f"global exact target route differs: {target}")
            elif row["diagnostic_layer"] == "representation_equivalence_candidate":
                expected = "candidate_model_unitization_equivalent_unchanged"
                if relation == "not_equivalent" or projected_phones != [old["g2p_candidate_phones"]]:
                    raise RuntimeError(f"global representation route differs: {target}")
            else:
                supported = supported_rule_only(operations)
                rebuilt: list[str] = []
                missing = candidate_only = False
                expected_ids: set[str] = set()
                for index, operation in enumerate(operations):
                    if operation.operation == "match":
                        rebuilt.append(operation.candidate_phone)
                    elif operation.operation == "rule_only" and index in supported:
                        continue
                    elif operation.operation == "candidate_only":
                        candidate_only = True
                    elif operation.rule_index is not None:
                        selected = chosen_evidence(donor_index, rule, operation.rule_index)
                        if selected is None:
                            missing = True
                        else:
                            identifier, phone = selected
                            expected_ids.add(identifier)
                            rebuilt.append(phone)
                recorded_ids = set(string_list(row["projection_evidence_ids_json"], label=f"target evidence {target}"))
                if recorded_ids != expected_ids:
                    raise RuntimeError(f"global target evidence differs: {target}")
                referenced_evidence.update(recorded_ids)
                if candidate_only:
                    expected = "hold_candidate_only_deletion_requires_policy"
                elif missing:
                    expected = "hold_no_unanimous_exact_context_donor"
                else:
                    rebuilt_relation, _ = independent_relation(rebuilt, rule, group_lookup)
                    expected = "candidate_exact_context_projection" if rebuilt_relation != "not_equivalent" else "hold_projected_sequence_not_equivalent"
                    if expected.startswith("candidate_"):
                        displays = phone_units(tuple(rebuilt), group_lookup)[0]
                        if projected_phones != [" ".join(rebuilt)] or projected_roman != [" ".join(displays)]:
                            raise RuntimeError(f"global projected sequence differs: {target}")
            expected_relation = (
                independent_relation(tuple(projected_phones[0].split()), rule, group_lookup)[0]
                if count else "not_equivalent"
            )
            if status != expected or row["representation_relation"] != expected_relation:
                raise RuntimeError(f"global target projection route differs: {target}")
            if any(phone not in inventory for value in projected_phones for phone in value.split()):
                raise RuntimeError(f"global projected phone outside inventory: {target}")
            category = independent_comparison_class(old, row)
            if (
                comparison["target_hangul"] != target
                or comparison["total_occurrences"] != old["total_occurrences"]
                or comparison["comparison_class"] != category
                or comparison["previous_projection_status"] != old["projection_status"]
                or comparison["global_projection_status"] != status
                or comparison["previous_projected_pron_phones_json"] != old["projected_pron_phones_json"]
                or comparison["global_projected_pron_phones_json"] != row["projected_pron_phones_json"]
                or comparison["candidate_is_final_selection"] != "false"
            ):
                raise RuntimeError(f"global comparison row differs: {target}")
            target_lookup[target] = (
                status,
                row["representation_relation"],
                count,
                row["projected_pron_phones_json"],
                row["projected_pron_roman_json"],
            )
            target_status[status] += 1
            target_relation[row["representation_relation"]] += 1
            target_occurrences[status] += int(row["total_occurrences"])
            comparison_types[category] += 1
            comparison_occurrences[category] += int(row["total_occurrences"])
    if referenced_evidence != set(evidence):
        raise RuntimeError("global evidence usage coverage differs")

    source_status: Counter[str] = Counter()
    source_occurrences: Counter[str] = Counter()
    source_rows = 0
    regressions: dict[str, dict[str, object]] = {}
    with gzip.open(inputs["prior_source_projection"], "rt", encoding="utf-8-sig", newline="") as old_stream, gzip.open(outputs["source_global_projection"], "rt", encoding="utf-8-sig", newline="") as new_stream:
        old_reader = csv.DictReader(old_stream)
        new_reader = csv.DictReader(new_stream)
        if tuple(old_reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS or tuple(new_reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS:
            raise RuntimeError("global source column contract differs")
        for old, row in itertools.zip_longest(old_reader, new_reader):
            if old is None or row is None:
                raise RuntimeError("global source coverage differs")
            compare_base(row, old, SOURCE_RESULT_FIELDS, old["token"])
            linked = target_lookup.get(old["target_hangul"])
            if linked is None:
                raise RuntimeError(f"global source target missing: {old['token']}")
            status, relation, count, phones_json, roman_json = linked
            route, agrees = expected_source_route(old, count)
            if (
                row["target_projection_status"] != status
                or row["target_representation_relation"] != relation
                or int(row["target_projection_candidate_count"]) != count
                or row["projected_pron_phones_json"] != phones_json
                or row["projected_pron_roman_json"] != roman_json
                or row["source_projection_gate_class"] != route
                or row["dictionary_rule_agreement"] != str(agrees).lower()
                or row["projection_candidate_is_final_selection"] != "false"
            ):
                raise RuntimeError(f"global source route differs: {old['token']}")
            source_rows += 1
            source_status[route] += 1
            source_occurrences[route] += int(row["total_occurrences"])
            if row["token"] in REGRESSION_TOKENS:
                regressions[row["token"]] = {
                    "target_hangul": row["target_hangul"],
                    "rule_pron_roman": row["rule_pron_roman"],
                    "g2p_candidate_phones": row["g2p_candidate_phones"],
                    "target_projection_status": status,
                    "source_projection_gate_class": route,
                    "projected_pron_phones_json": phones_json,
                }

    recomputed = {
        "target_rows": len(target_lookup),
        "source_rows": source_rows,
        "donor_exact_target_rows": donor_types,
        "donor_exact_variant_rows": donor_variants,
        "donor_exact_target_units": donor_type_units,
        "donor_exact_variant_units": donor_variant_units,
        "query_contexts": {level: len(query_sets[level]) for level in CONTEXT_LEVELS},
        "indexed_query_contexts": {level: len(donor_index[level]) for level in CONTEXT_LEVELS},
        "used_projection_evidence_rows": len(evidence),
        "target_projection_status": dict(sorted(target_status.items())),
        "target_representation_relation": dict(sorted(target_relation.items())),
        "target_occurrences_by_projection_status": dict(sorted(target_occurrences.items())),
        "comparison_class_types": dict(sorted(comparison_types.items())),
        "comparison_class_occurrences": dict(sorted(comparison_occurrences.items())),
        "source_projection_gate_class": dict(sorted(source_status.items())),
        "source_occurrences_by_gate_class": dict(sorted(source_occurrences.items())),
    }
    if recomputed != manifest["counts"]:
        raise RuntimeError("global projection manifest counts differ")
    if len(regressions) != len(REGRESSION_TOKENS):
        raise RuntimeError("global projection regression coverage differs")

    result: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": recomputed,
        "regression_examples": regressions,
        "contracts": {
            "same_g2p_rerun_performed": False,
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "global_projection_manifest": file_fingerprint(manifest_path, with_sha256=True),
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
    result = audit_global_projection(
        manifest_path=args.manifest.resolve(), audit_report=args.audit_report.resolve()
    )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
