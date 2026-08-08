"""Independently audit r3 model-projection candidates without adopting them.

The auditor rebuilds every queried donor context from the frozen exact-agreement
pool, recomputes the narrow model-unitization relation, verifies all target and
source routes, and confirms that no final pronunciation/MFA/TextGrid action was
performed.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS, phone_units, roman_units  # noqa: E402
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    SOURCE_RESULT_FIELDS,
    TARGET_RESULT_FIELDS,
)
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    EditOperation,
    phone_encodes_glide,
    unit_edit_alignment,
)
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    EVIDENCE_FIELDS,
    SCHEMA_VERSION,
    SOURCE_PROJECTION_FIELDS,
    TARGET_PROJECTION_FIELDS,
)
from phoneme_roman import (  # noqa: E402
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
AUDIT_SCHEMA = "common_pron_r3_projection_candidates_audit.v1"
CONTEXT_LEVELS = ("window2_boundary", "window1_boundary", "unit_boundary")
REGRESSION_TOKENS = ("있는", "있지", "놨던", "어쨌든", "없는")
csv.field_size_limit(10_000_000)


@dataclass
class Observation:
    phone_counts: Counter[str] = field(default_factory=Counter)
    target_types: int = 0
    units: int = 0
    examples: list[str] = field(default_factory=list)


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


def unit_boundaries(rule: Sequence[RomanUnit], index: int) -> tuple[bool, bool, bool, bool]:
    current = rule[index]
    return (
        index == 0 or rule[index - 1].syllable_index != current.syllable_index,
        index == len(rule) - 1 or rule[index + 1].syllable_index != current.syllable_index,
        index == 0,
        index == len(rule) - 1,
    )


def audit_context_key(rule: Sequence[RomanUnit], index: int, level: str) -> tuple[object, ...]:
    def display(position: int) -> str:
        if position < 0:
            return "<BOS>"
        if position >= len(rule):
            return "<EOS>"
        return rule[position].display

    current = rule[index].display
    boundaries = unit_boundaries(rule, index)
    if level == "window2_boundary":
        return (display(index - 2), display(index - 1), current, display(index + 1), display(index + 2), *boundaries)
    if level == "window1_boundary":
        return (display(index - 1), current, display(index + 1), *boundaries)
    if level == "unit_boundary":
        return (current, *boundaries)
    raise RuntimeError(f"unknown context level: {level}")


def supported_rule_only(operations: Sequence[EditOperation]) -> dict[int, str]:
    result: dict[int, str] = {}
    for index, operation in enumerate(operations):
        if operation.operation != "rule_only":
            continue
        neighbors = [
            operations[position]
            for position in (index - 1, index + 1)
            if 0 <= position < len(operations)
            and operations[position].operation == "match"
            and operations[position].candidate_index is not None
        ]
        if operation.rule_key in {"Y", "W"} and any(
            phone_encodes_glide(item.candidate_phone, operation.rule_key)
            for item in neighbors
        ):
            result[index] = "secondary_articulation_glide"
        elif any(
            item.candidate_key == operation.rule_key
            and item.candidate_has_length is True
            for item in neighbors
        ):
            result[index] = "length_marked_identical_unit"
    return result


def independent_relation(
    phones: Sequence[str], rule: Sequence[RomanUnit], group_lookup: dict[str, int]
) -> tuple[str, list[EditOperation]]:
    operations = unit_edit_alignment(
        tuple(classify_phone(phone, group_lookup) for phone in phones), rule
    )
    edits = [(index, item) for index, item in enumerate(operations) if item.operation != "match"]
    if not edits:
        return "exact_comparison_keys", operations
    supported = supported_rule_only(operations)
    if any(index not in supported for index, _ in edits):
        return "not_equivalent", operations
    kinds = {supported[index] for index, _ in edits}
    return {
        frozenset({"length_marked_identical_unit"}): "equivalent_length_unitization",
        frozenset({"secondary_articulation_glide"}): "equivalent_glide_unitization",
        frozenset({"length_marked_identical_unit", "secondary_articulation_glide"}): "equivalent_combined_unitization",
    }[frozenset(kinds)], operations


def query_rule_indices(operations: Sequence[EditOperation]) -> set[int]:
    supported = supported_rule_only(operations)
    result: set[int] = set()
    for index, operation in enumerate(operations):
        if operation.operation == "substitution" and operation.rule_index is not None:
            result.add(operation.rule_index)
        elif operation.operation == "rule_only" and index not in supported and operation.rule_index is not None:
            result.add(operation.rule_index)
    return result


def evidence_id(level: str, context: tuple[object, ...], phone: str) -> str:
    payload = json.dumps(
        {"level": level, "context": context, "phone": phone},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "projctx-" + hashlib.sha256(payload).hexdigest()[:20]


def chosen_evidence(
    donor_index: dict[str, dict[tuple[object, ...], Observation]],
    rule: Sequence[RomanUnit],
    rule_index: int,
) -> tuple[str, str] | None:
    for level in CONTEXT_LEVELS:
        context = audit_context_key(rule, rule_index, level)
        observation = donor_index[level].get(context)
        if observation and observation.target_types >= 2 and len(observation.phone_counts) == 1:
            phone = next(iter(observation.phone_counts))
            return evidence_id(level, context, phone), phone
    return None


def dictionary_rule_agreement(row: dict[str, str]) -> bool:
    _, rule_keys = roman_units(row["rule_pron_roman"])
    return any(
        roman_units(value)[1] == rule_keys and bool(rule_keys)
        for value in string_list(row["dictionary_pron_roman_json"], label=row["token"])
    )


def expected_source_route(row: dict[str, str], target_count: int) -> tuple[str, bool]:
    agrees = dictionary_rule_agreement(row)
    if target_count == 0:
        return "hold_target_projection_unresolved", agrees
    routes = {
        "candidate_replace_rule_dictionary_agree": "candidate_projection_dictionary_agree",
        "review_rule_dictionary_conflict": "hold_projection_dictionary_conflict",
        "review_rule_sensitive_no_attested_agreement": "hold_projection_no_independent_dictionary",
    }
    original = clean(row["original_selection_status"])
    if original not in routes:
        raise RuntimeError(f"unexpected source route: {row['token']}")
    return routes[original], agrees


def load_evidence(path: Path, inventory: set[str]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != EVIDENCE_FIELDS:
            raise RuntimeError("evidence column contract differs")
        for row in reader:
            identifier = clean(row["evidence_id"])
            context_value = json.loads(row["context_json"])
            if not isinstance(context_value, list):
                raise RuntimeError(f"invalid evidence context: {identifier}")
            context = tuple(context_value)
            level = clean(row["context_level"])
            phone = clean(row["projected_phone"])
            phone_counts = json.loads(row["observed_phone_counts_json"])
            if (
                identifier in result
                or level not in CONTEXT_LEVELS
                or phone not in inventory
                or identifier != evidence_id(level, context, phone)
                or clean(row["unanimous_phone"]) != "true"
                or clean(row["candidate_is_final_selection"]) != "false"
                or int(row["support_target_type_count"]) < 2
                or phone_counts != {phone: int(row["support_unit_count"])}
            ):
                raise RuntimeError(f"invalid projection evidence: {identifier}")
            result[identifier] = {**row, "context": context, "phone_counts": phone_counts}
    return result


def compare_base(row: dict[str, str], base: dict[str, str], fields: Sequence[str], label: str) -> None:
    if any(row[field] != base[field] for field in fields):
        raise RuntimeError(f"base row changed: {label}")


def audit_projection(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("projection manifest is not successful candidate-only output")
    scope = manifest.get("scope", {})
    false_scope = (
        "candidate_is_final_selection", "canonical_selection_performed", "adoption_performed",
        "annual_mfa_started", "textgrids_modified", "source_files_modified", "actual_realization_claimed",
    )
    if scope.get("model_representation_relation_applied") is not True or any(scope.get(key) is not False for key in false_scope):
        raise RuntimeError("projection scope contract differs")
    inputs = {key: verify_fingerprint(value, label=f"input {key}") for key, value in manifest["inputs"].items()}
    outputs = {key: verify_fingerprint(value, label=f"output {key}") for key, value in manifest["outputs"].items()}
    policy = json.loads(inputs["policy_contract"].read_text(encoding="utf-8-sig"))
    if policy.get("status") != "candidate_generation_only" or tuple(str(x) for x in policy.get("scope_years", [])) != YEARS:
        raise RuntimeError("projection policy contract differs")
    meta = load_acoustic_meta(inputs["acoustic_model"])
    group_lookup = model_group_lookup(meta)
    inventory = {str(phone) for phone in meta["phones"]}
    evidence = load_evidence(outputs["exact_context_projection_evidence"], inventory)

    diagnostic_meta: dict[str, tuple[str, str, str]] = {}
    with gzip.open(inputs["diagnostic_target"], "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            diagnostic_meta[row["target_hangul"]] = (
                row["diagnostic_layer"], row["diagnostic_class"], row["edit_signature"]
            )

    query_sets = {level: set() for level in CONTEXT_LEVELS}
    with gzip.open(inputs["agreement_target"], "rt", encoding="utf-8-sig", newline="") as base_stream, gzip.open(outputs["target_projection_candidates"], "rt", encoding="utf-8-sig", newline="") as output_stream:
        base_reader = csv.DictReader(base_stream)
        output_reader = csv.DictReader(output_stream)
        if tuple(base_reader.fieldnames or ()) != TARGET_RESULT_FIELDS or tuple(output_reader.fieldnames or ()) != TARGET_PROJECTION_FIELDS:
            raise RuntimeError("target column contract differs")
        rows = 0
        for base, row in itertools.zip_longest(base_reader, output_reader):
            if base is None or row is None:
                raise RuntimeError("target row coverage differs")
            compare_base(row, base, TARGET_RESULT_FIELDS, base["target_hangul"])
            if base["comparison_status"] != "exact_rule_roman":
                rule = tuple(expand_roman_eojeol(base["rule_pron_roman"]))
                _, operations = independent_relation(tuple(clean(base["g2p_candidate_phones"]).split()), rule, group_lookup)
                for rule_index in query_rule_indices(operations):
                    for level in CONTEXT_LEVELS:
                        query_sets[level].add(audit_context_key(rule, rule_index, level))
            rows += 1

    donor_index: dict[str, dict[tuple[object, ...], Observation]] = {level: {} for level in CONTEXT_LEVELS}
    donor_rows = donor_units = 0
    with gzip.open(inputs["agreement_target"], "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["comparison_status"] != "exact_rule_roman" or row["rewrite_rule"] != "none":
                continue
            target = row["target_hangul"]
            phones = tuple(clean(row["g2p_candidate_phones"]).split())
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            if len(phones) != len(rule):
                raise RuntimeError(f"exact donor unit count differs: {target}")
            donor_rows += 1
            donor_units += len(rule)
            seen: set[tuple[str, tuple[object, ...]]] = set()
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
            raise RuntimeError(f"evidence reconstruction differs: {identifier}")

    target_lookup: dict[str, tuple[str, str, int, str, str]] = {}
    target_status: Counter[str] = Counter()
    target_relation: Counter[str] = Counter()
    target_occurrences: Counter[str] = Counter()
    referenced_evidence: set[str] = set()
    regressions: dict[str, dict[str, object]] = {}
    with gzip.open(inputs["agreement_target"], "rt", encoding="utf-8-sig", newline="") as base_stream, gzip.open(outputs["target_projection_candidates"], "rt", encoding="utf-8-sig", newline="") as output_stream:
        for base, row in zip(csv.DictReader(base_stream), csv.DictReader(output_stream), strict=True):
            target = base["target_hangul"]
            rule = tuple(expand_roman_eojeol(base["rule_pron_roman"]))
            original_phones = tuple(clean(base["g2p_candidate_phones"]).split())
            relation, operations = independent_relation(original_phones, rule, group_lookup)
            projected_phones = string_list(row["projected_pron_phones_json"], label=f"target phones {target}")
            projected_roman = string_list(row["projected_pron_roman_json"], label=f"target Roman {target}")
            count = int(row["projection_candidate_count"])
            status = clean(row["projection_status"])
            if clean(row["projection_candidate_is_final_selection"]) != "false" or count != len(projected_phones) or count != len(projected_roman):
                raise RuntimeError(f"target candidate contract differs: {target}")
            if base["comparison_status"] == "exact_rule_roman":
                expected = "candidate_exact_gate_unchanged"
                if relation != "exact_comparison_keys" or projected_phones != [base["g2p_candidate_phones"]] or row["diagnostic_layer"] != "exact_gate":
                    raise RuntimeError(f"exact target route differs: {target}")
            else:
                if target not in diagnostic_meta or tuple(row[key] for key in ("diagnostic_layer", "diagnostic_class", "edit_signature")) != diagnostic_meta[target]:
                    raise RuntimeError(f"target diagnostic link differs: {target}")
                if row["diagnostic_layer"] == "representation_equivalence_candidate":
                    expected = "candidate_model_unitization_equivalent_unchanged"
                    if relation == "not_equivalent" or projected_phones != [base["g2p_candidate_phones"]]:
                        raise RuntimeError(f"representation target route differs: {target}")
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
                        raise RuntimeError(f"target evidence selection differs: {target}")
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
                                raise RuntimeError(f"projected sequence differs: {target}")
            if status != expected or clean(row["representation_relation"]) != (independent_relation(tuple(projected_phones[0].split()), rule, group_lookup)[0] if count else "not_equivalent"):
                raise RuntimeError(f"target projection route differs: {target}")
            if any(phone not in inventory for value in projected_phones for phone in value.split()):
                raise RuntimeError(f"projected phone outside inventory: {target}")
            target_lookup[target] = (status, row["representation_relation"], count, row["projected_pron_phones_json"], row["projected_pron_roman_json"])
            target_status[status] += 1
            target_relation[row["representation_relation"]] += 1
            target_occurrences[status] += int(row["total_occurrences"])

    if referenced_evidence != set(evidence):
        raise RuntimeError("evidence usage coverage differs")

    source_status: Counter[str] = Counter()
    source_occurrences: Counter[str] = Counter()
    source_rows = 0
    with gzip.open(inputs["agreement_source"], "rt", encoding="utf-8-sig", newline="") as base_stream, gzip.open(outputs["source_projection_candidates"], "rt", encoding="utf-8-sig", newline="") as output_stream:
        base_reader = csv.DictReader(base_stream)
        output_reader = csv.DictReader(output_stream)
        if tuple(base_reader.fieldnames or ()) != SOURCE_RESULT_FIELDS or tuple(output_reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS:
            raise RuntimeError("source column contract differs")
        for base, row in itertools.zip_longest(base_reader, output_reader):
            if base is None or row is None:
                raise RuntimeError("source row coverage differs")
            token = base["token"]
            compare_base(row, base, SOURCE_RESULT_FIELDS, token)
            linked = target_lookup.get(base["target_hangul"])
            if linked is None:
                raise RuntimeError(f"source target missing: {token}")
            status, relation, count, phones_json, roman_json = linked
            route, agrees = expected_source_route(base, count)
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
                raise RuntimeError(f"source projection route differs: {token}")
            source_rows += 1
            source_status[route] += 1
            source_occurrences[route] += int(row["total_occurrences"])
            if token in REGRESSION_TOKENS:
                regressions[token] = {
                    "target_hangul": base["target_hangul"],
                    "rule_pron_roman": base["rule_pron_roman"],
                    "g2p_candidate_phones": base["g2p_candidate_phones"],
                    "target_projection_status": status,
                    "source_projection_gate_class": route,
                    "projected_pron_phones_json": phones_json,
                }

    counts = manifest["counts"]
    recomputed = {
        "target_rows": len(target_lookup),
        "source_rows": source_rows,
        "donor_exact_target_rows": donor_rows,
        "donor_exact_units": donor_units,
        "query_contexts": {level: len(query_sets[level]) for level in CONTEXT_LEVELS},
        "indexed_query_contexts": {level: len(donor_index[level]) for level in CONTEXT_LEVELS},
        "used_projection_evidence_rows": len(evidence),
        "target_projection_status": dict(sorted(target_status.items())),
        "target_representation_relation": dict(sorted(target_relation.items())),
        "target_occurrences_by_projection_status": dict(sorted(target_occurrences.items())),
        "source_projection_gate_class": dict(sorted(source_status.items())),
        "source_occurrences_by_gate_class": dict(sorted(source_occurrences.items())),
    }
    if recomputed != counts:
        raise RuntimeError("projection manifest counts differ")
    if set(regressions) != set(REGRESSION_TOKENS):
        raise RuntimeError("regression token coverage differs")

    result: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": recomputed,
        "regression_examples": regressions,
        "contracts": {
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "projection_manifest": file_fingerprint(manifest_path, with_sha256=True),
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
    result = audit_projection(
        manifest_path=args.manifest.resolve(),
        audit_report=args.audit_report.resolve(),
    )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
