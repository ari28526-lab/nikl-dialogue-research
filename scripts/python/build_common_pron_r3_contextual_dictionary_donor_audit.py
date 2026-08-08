"""Audit contextual frozen-dictionary donors for every readiness-v2 hold.

The stage is deliberately read-only.  It inventories word-, syllable-, local-
window-, and secondary-articulation contexts in the frozen Korean MFA
dictionary, compares them with the existing exact canonical donor pool, and
classifies every zero-fallback hold.  It does not emit a pronunciation
candidate, select a canonical variant, run MFA, or modify TextGrids.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_mfa_lexicon import read_mfa_dictionary  # noqa: E402
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    EditOperation,
    RULE_MODEL_GROUP,
    edit_signature,
    phone_encodes_glide,
    unit_edit_alignment,
)
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    CONTEXT_LEVELS,
    context_key,
    supported_representation_rule_only_indices,
)
from build_common_pron_r3_selection_readiness_v2 import (  # noqa: E402
    OUTPUT_FIELDS as READINESS_FIELDS,
    SCHEMA_VERSION as READINESS_SCHEMA,
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
from predict_pron import DEFAULT_FLAGS, PLACEHOLDER, process_eojeol  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_contextual_dictionary_donor_audit.v1"
POLICY_SCHEMA = "common_pron_r3_contextual_dictionary_donor_policy.v1"
HOLD_STATUSES = {
    "hold_target_projection_unresolved",
    "hold_no_surface_rule_substantive_mismatch",
}
DIRECT_FROZEN_LEVELS = (
    "word_exact",
    "syllable_signature",
    "window2_boundary",
    "window1_boundary",
)
SECONDARY_FROZEN_LEVELS = (
    "word_exact",
    "syllable_signature",
    "compound_vowel_boundary",
)
CLASS_UNANIMOUS = "unanimous_contextual_support"
CLASS_MULTIPLE = "multiple_supported_contextual_variants"
CLASS_CONFLICT = "cross_source_conflict"
CLASS_NONE = "no_eligible_contextual_donor"

INVENTORY_FIELDS = (
    "token",
    "variant_index",
    "pron_phones",
    "rule_pron_hangul",
    "rule_pron_roman",
    "alignment_signature",
    "mapping_status",
    "direct_mapping_count",
    "secondary_articulation_mapping_count",
    "contextual_mappings_json",
    "unsupported_operations_json",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
)

ISSUE_FIELDS = (
    "token",
    "total_occurrences",
    "planning_status",
    "variant_index",
    "r2_pron_phones",
    "issue_index",
    "relation_kind",
    "rule_indices_json",
    "rule_units_json",
    "current_candidate_phone",
    "canonical_context_level",
    "canonical_context_json",
    "canonical_phone_counts_json",
    "canonical_token_type_count",
    "frozen_context_level",
    "frozen_context_json",
    "frozen_phone_counts_json",
    "frozen_token_type_count",
    "evidence_class",
    "current_candidate_supported",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
)

HOLD_FIELDS = (
    "token",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
    "rule_pron_hangul",
    "rule_pron_roman",
    "surface_rule_names",
    "r2_pron_phones_json",
    "r2_pron_source",
    "planning_status",
    "no_rule_coverage_status",
    "audited_variant_count",
    "audited_issue_count",
    "canonical_supported_issue_count",
    "frozen_supported_issue_count",
    "contextual_support_class",
    "variant_audit_json",
    "researcher_review_required_now",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
    "canonical_selection_performed",
)

csv.field_size_limit(10_000_000)


@dataclass(frozen=True)
class Mapping:
    relation_kind: str
    rule_indices: tuple[int, ...]
    phone: str
    phone_display: str
    phone_key: str
    phone_model_group: str
    secondary_articulation: str


@dataclass
class Observation:
    phone_counts: Counter[str] = field(default_factory=Counter)
    token_types: set[str] = field(default_factory=set)
    variant_rows: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Evidence:
    level: str
    context: tuple[object, ...]
    phone_counts: dict[str, int]
    token_type_count: int


def clean(value: object) -> str:
    return str(value or "").strip()


def parse_list(value: object, *, label: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON list: {label}") from exc
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise RuntimeError(f"expected JSON string list: {label}")
    return result


def verify_fingerprint(record: dict[str, object], path: Path, *, label: str) -> None:
    if (
        Path(str(record["path"])).resolve() != path.resolve()
        or not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


@contextmanager
def gzip_writer(path: Path) -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "xt", encoding="utf-8-sig", newline="", compresslevel=6) as stream:
        yield stream


def fingerprint_for_final(temp: Path, final: Path) -> dict[str, object]:
    result = file_fingerprint(temp, with_sha256=True)
    result["path"] = str(final.resolve())
    return result


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "read_only_methodological_audit"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
    ):
        raise RuntimeError("contextual dictionary donor policy differs")
    hold = policy.get("hold_scope", {})
    if (
        hold.get("required_planning_zero_fallback_hold") is not True
        or set(hold.get("expected_hold_statuses", ())) != HOLD_STATUSES
        or hold.get("all_r2_variants_must_be_audited") is not True
    ):
        raise RuntimeError("contextual hold scope differs")
    canonical = policy.get("canonical_donor_policy", {})
    if (
        canonical.get("eligible_planning_status") != "candidate_r2_exact_mandatory_rule"
        or tuple(canonical.get("specificity_order", ())) != CONTEXT_LEVELS
        or int(canonical.get("minimum_distinct_token_types", 0)) != 2
        or canonical.get("occurrence_weighting_allowed") is not False
    ):
        raise RuntimeError("canonical contextual donor policy differs")
    frozen = policy.get("frozen_dictionary_donor_policy", {})
    if (
        frozen.get("complete_contextual_mapping_required") is not True
        or tuple(frozen.get("direct_specificity_order", ())) != DIRECT_FROZEN_LEVELS
        or tuple(frozen.get("secondary_articulation_specificity_order", ()))
        != SECONDARY_FROZEN_LEVELS
        or frozen.get("global_phone_to_phoneme_mapping_allowed") is not False
        or frozen.get("word_or_syllable_context_may_be_dropped") is not False
        or frozen.get("occurrence_weighting_allowed") is not False
    ):
        raise RuntimeError("frozen contextual donor policy differs")
    thresholds = frozen.get("minimum_distinct_token_types", {})
    expected_thresholds = {
        "word_exact": 1,
        "syllable_signature": 2,
        "window2_boundary": 2,
        "window1_boundary": 2,
        "compound_vowel_boundary": 2,
    }
    if {key: int(value) for key, value in thresholds.items()} != expected_thresholds:
        raise RuntimeError("frozen contextual donor thresholds differ")
    if any(value is not True for value in policy.get("interpretation_policy", {}).values()):
        raise RuntimeError("contextual interpretation policy is incomplete")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("contextual donor policy exceeds read-only scope")
    return policy


def unit_syllable_indices(rule: Sequence[RomanUnit], syllable_index: int) -> list[int]:
    return [index for index, unit in enumerate(rule) if unit.syllable_index == syllable_index]


def syllable_signature(rule: Sequence[RomanUnit], indices: Sequence[int]) -> tuple[object, ...]:
    if not indices:
        raise ValueError("empty rule indices")
    syllables = {rule[index].syllable_index for index in indices}
    if len(syllables) != 1:
        raise ValueError("mapping crosses syllable boundary")
    syllable_index = next(iter(syllables))
    members = unit_syllable_indices(rule, syllable_index)
    local_positions = tuple(members.index(index) for index in indices)
    previous = "<BOS>" if members[0] == 0 else rule[members[0] - 1].display
    following = "<EOS>" if members[-1] == len(rule) - 1 else rule[members[-1] + 1].display
    return (
        tuple(rule[index].display for index in members),
        local_positions,
        previous,
        following,
        members[0] == 0,
        members[-1] == len(rule) - 1,
    )


def compound_vowel_boundary(rule: Sequence[RomanUnit], indices: Sequence[int]) -> tuple[object, ...]:
    if len(indices) != 2:
        raise ValueError("secondary mapping must contain onset and glide")
    onset, glide = indices
    if glide != onset + 1 or rule[onset].syllable_index != rule[glide].syllable_index:
        raise ValueError("secondary mapping is not an adjacent onset+glide")
    members = unit_syllable_indices(rule, rule[onset].syllable_index)
    following = rule[glide + 1].display if glide + 1 in members else "<NO_VOWEL>"
    previous = rule[onset - 1].display if onset > 0 else "<BOS>"
    return (
        rule[onset].display,
        rule[glide].display,
        following,
        previous,
        members[0] == 0,
        members[-1] == len(rule) - 1,
    )


def context_keys(
    *, token: str, rule: Sequence[RomanUnit], mapping: Mapping
) -> dict[str, tuple[object, ...]]:
    indices = mapping.rule_indices
    result: dict[str, tuple[object, ...]] = {
        "word_exact": (
            token,
            tuple(unit.display for unit in rule),
            indices,
            mapping.relation_kind,
        ),
        "syllable_signature": (
            *syllable_signature(rule, indices),
            mapping.relation_kind,
        ),
    }
    if mapping.relation_kind == "direct_unit":
        index = indices[0]
        for level in ("window2_boundary", "window1_boundary", "unit_boundary"):
            result[level] = context_key(rule, index, level)
    elif mapping.relation_kind == "secondary_articulation_cluster":
        result["compound_vowel_boundary"] = compound_vowel_boundary(rule, indices)
    return result


def _secondary_cluster(
    operations: Sequence[EditOperation], rule: Sequence[RomanUnit], index: int
) -> tuple[Mapping, int] | None:
    if index + 1 >= len(operations):
        return None
    first, second = operations[index], operations[index + 1]
    onset: EditOperation | None = None
    glide: EditOperation | None = None
    phone_op: EditOperation | None = None
    if (
        first.operation == "rule_only"
        and first.rule_index is not None
        and second.rule_index == first.rule_index + 1
        and second.operation in {"match", "substitution"}
        and second.candidate_index is not None
    ):
        onset, glide, phone_op = first, second, second
    elif (
        first.operation in {"match", "substitution"}
        and first.candidate_index is not None
        and first.rule_index is not None
        and second.operation == "rule_only"
        and second.rule_index == first.rule_index + 1
    ):
        onset, glide, phone_op = first, second, first
    if onset is None or glide is None or phone_op is None:
        return None
    if (
        onset.rule_index is None
        or glide.rule_index is None
        or glide.rule_key not in {"Y", "W"}
        or rule[onset.rule_index].syllable_index != rule[glide.rule_index].syllable_index
        or not phone_encodes_glide(phone_op.candidate_phone, glide.rule_key)
        or RULE_MODEL_GROUP.get(onset.rule_display) != phone_op.candidate_model_group
    ):
        return None
    phone_class = classify_phone_placeholder(phone_op)
    return (
        Mapping(
            relation_kind="secondary_articulation_cluster",
            rule_indices=(onset.rule_index, glide.rule_index),
            phone=phone_op.candidate_phone,
            phone_display=phone_op.candidate_display,
            phone_key=phone_op.candidate_key,
            phone_model_group=phone_op.candidate_model_group,
            secondary_articulation=phone_class,
        ),
        index + 2,
    )


def classify_phone_placeholder(operation: EditOperation) -> str:
    value = []
    if "ʲ" in operation.candidate_phone or phone_encodes_glide(operation.candidate_phone, "Y"):
        value.append("palatalized")
    if "ʷ" in operation.candidate_phone:
        value.append("labialized")
    return "+".join(value)


def extract_mappings(
    phones: Sequence[str], rule: Sequence[RomanUnit], group_lookup: dict[str, int]
) -> tuple[list[Mapping], list[dict[str, object]], list[EditOperation]]:
    classified = tuple(classify_phone(phone, group_lookup) for phone in phones)
    operations = unit_edit_alignment(classified, rule)
    supported_rule_only = supported_representation_rule_only_indices(operations)
    mappings: list[Mapping] = []
    unsupported: list[dict[str, object]] = []
    index = 0
    while index < len(operations):
        compound = _secondary_cluster(operations, rule, index)
        if compound is not None:
            mapping, index = compound
            mappings.append(mapping)
            continue
        operation = operations[index]
        if operation.operation in {"match", "substitution"}:
            if operation.rule_index is None:
                raise RuntimeError("paired operation lacks rule index")
            phone = classified[operation.candidate_index]  # type: ignore[index]
            mappings.append(
                Mapping(
                    relation_kind="direct_unit",
                    rule_indices=(operation.rule_index,),
                    phone=phone.phone_mfa,
                    phone_display=phone.phone_class_r_auto,
                    phone_key=phone.comparison_key,
                    phone_model_group=phone.model_group_r,
                    secondary_articulation=phone.secondary_articulation,
                )
            )
        elif operation.operation == "rule_only" and index in supported_rule_only:
            pass
        else:
            unsupported.append(
                {
                    "operation_index": index,
                    "operation": operation.operation,
                    "candidate_phone": operation.candidate_phone,
                    "candidate_key": operation.candidate_key,
                    "rule_index": operation.rule_index,
                    "rule_display": operation.rule_display,
                    "rule_key": operation.rule_key,
                }
            )
        index += 1
    return mappings, unsupported, operations


def mapping_record(
    *, token: str, rule: Sequence[RomanUnit], mapping: Mapping
) -> dict[str, object]:
    keys = context_keys(token=token, rule=rule, mapping=mapping)
    return {
        "relation_kind": mapping.relation_kind,
        "rule_indices": list(mapping.rule_indices),
        "rule_units": [rule[index].display for index in mapping.rule_indices],
        "phone": mapping.phone,
        "phone_display": mapping.phone_display,
        "phone_key": mapping.phone_key,
        "phone_model_group": mapping.phone_model_group,
        "secondary_articulation": mapping.secondary_articulation,
        "contexts": {level: list(key) for level, key in keys.items()},
    }


def observe(
    index: dict[str, dict[str, dict[tuple[object, ...], Observation]]],
    *, source: str, token: str, mapping: Mapping, rule: Sequence[RomanUnit]
) -> None:
    for level, key in context_keys(token=token, rule=rule, mapping=mapping).items():
        observation = index[source][level].setdefault(key, Observation())
        observation.phone_counts[mapping.phone] += 1
        observation.token_types.add(token)
        observation.variant_rows += 1
        if token not in observation.examples and len(observation.examples) < 8:
            observation.examples.append(token)


def build_frozen_inventory(
    *, pronunciations: dict[str, set[tuple[str, ...]]], group_lookup: dict[str, int], writer: csv.DictWriter
) -> tuple[dict[str, dict[str, dict[tuple[object, ...], Observation]]], Counter[str]]:
    index: dict[str, dict[str, dict[tuple[object, ...], Observation]]] = {
        "direct_unit": defaultdict(dict),
        "secondary_articulation_cluster": defaultdict(dict),
    }
    counts: Counter[str] = Counter()
    for token in sorted(pronunciations):
        rule_hangul, _, rule_roman = process_eojeol(token, DEFAULT_FLAGS)
        if rule_roman == PLACEHOLDER:
            counts["tokens_without_rule"] += 1
            continue
        rule = tuple(expand_roman_eojeol(rule_roman))
        counts["tokens_with_rule"] += 1
        for variant_index, phones in enumerate(sorted(pronunciations[token]), 1):
            mappings, unsupported, operations = extract_mappings(phones, rule, group_lookup)
            complete = not unsupported
            status = "complete_contextual_mapping" if complete else "partial_unsupported_mapping"
            counts["variant_rows"] += 1
            counts[status] += 1
            counts["direct_mapping_rows"] += sum(item.relation_kind == "direct_unit" for item in mappings)
            counts["secondary_articulation_mapping_rows"] += sum(
                item.relation_kind == "secondary_articulation_cluster" for item in mappings
            )
            records = [mapping_record(token=token, rule=rule, mapping=item) for item in mappings]
            writer.writerow(
                {
                    "token": token,
                    "variant_index": variant_index,
                    "pron_phones": " ".join(phones),
                    "rule_pron_hangul": rule_hangul,
                    "rule_pron_roman": rule_roman,
                    "alignment_signature": edit_signature(operations),
                    "mapping_status": status,
                    "direct_mapping_count": sum(item.relation_kind == "direct_unit" for item in mappings),
                    "secondary_articulation_mapping_count": sum(
                        item.relation_kind == "secondary_articulation_cluster" for item in mappings
                    ),
                    "contextual_mappings_json": json.dumps(records, ensure_ascii=False),
                    "unsupported_operations_json": json.dumps(unsupported, ensure_ascii=False),
                    "standard_pronunciation_claimed": "false",
                    "actual_realization_claimed": "false",
                    "candidate_generation_performed": "false",
                }
            )
            if complete:
                for mapping in mappings:
                    observe(index, source=mapping.relation_kind, token=token, mapping=mapping, rule=rule)
    return index, counts


def build_canonical_index(
    readiness_path: Path, group_lookup: dict[str, int]
) -> tuple[dict[str, dict[tuple[object, ...], Observation]], Counter[str]]:
    index: dict[str, dict[tuple[object, ...], Observation]] = {
        level: {} for level in CONTEXT_LEVELS
    }
    counts: Counter[str] = Counter()
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness v2 column contract differs")
        for row in reader:
            if row["planning_status"] != "candidate_r2_exact_mandatory_rule":
                continue
            token = row["token"]
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            variants = parse_list(row["planning_candidate_phones_json"], label=f"canonical {token}")
            if not variants:
                raise RuntimeError(f"canonical exact donor has no variants: {token}")
            counts["token_types"] += 1
            seen: set[tuple[str, tuple[object, ...]]] = set()
            for variant in variants:
                phones = tuple(clean(variant).split())
                if len(phones) != len(rule):
                    raise RuntimeError(f"canonical donor length differs: {token}")
                counts["variant_rows"] += 1
                for unit_index, phone_value in enumerate(phones):
                    phone = classify_phone(phone_value, group_lookup)
                    if phone.comparison_key != rule[unit_index].comparison_key:
                        raise RuntimeError(f"canonical donor relation differs: {token}")
                    for level in CONTEXT_LEVELS:
                        key = context_key(rule, unit_index, level)
                        observation = index[level].setdefault(key, Observation())
                        observation.phone_counts[phone_value] += 1
                        marker = (level, key)
                        if marker not in seen:
                            observation.token_types.add(token)
                            seen.add(marker)
                        observation.variant_rows += 1
                        if token not in observation.examples and len(observation.examples) < 8:
                            observation.examples.append(token)
    return index, counts


def choose_evidence(
    index: dict[str, dict[tuple[object, ...], Observation]],
    *, keys: dict[str, tuple[object, ...]], levels: Sequence[str], thresholds: dict[str, int]
) -> Evidence | None:
    for level in levels:
        key = keys[level]
        observation = index.get(level, {}).get(key)
        if observation is None or len(observation.token_types) < thresholds[level]:
            continue
        return Evidence(
            level=level,
            context=key,
            phone_counts=dict(sorted(observation.phone_counts.items())),
            token_type_count=len(observation.token_types),
        )
    return None


def evidence_class(canonical: Evidence | None, frozen: Evidence | None) -> str:
    canonical_set = set(canonical.phone_counts) if canonical else set()
    frozen_set = set(frozen.phone_counts) if frozen else set()
    if not canonical_set and not frozen_set:
        return CLASS_NONE
    if canonical_set and frozen_set and canonical_set.isdisjoint(frozen_set):
        return CLASS_CONFLICT
    if len(canonical_set | frozen_set) == 1:
        return CLASS_UNANIMOUS
    return CLASS_MULTIPLE


def aggregate_classes(classes: Sequence[str], *, variant_count: int = 1) -> str:
    if not classes:
        return CLASS_NONE
    if CLASS_CONFLICT in classes:
        return CLASS_CONFLICT
    if CLASS_NONE in classes:
        return CLASS_NONE
    if CLASS_MULTIPLE in classes or variant_count > 1:
        return CLASS_MULTIPLE
    return CLASS_UNANIMOUS


def issue_mappings(
    phones: Sequence[str], rule: Sequence[RomanUnit], group_lookup: dict[str, int]
) -> tuple[list[Mapping | None], list[EditOperation]]:
    mappings, _, operations = extract_mappings(phones, rule, group_lookup)
    complete_by_operation: dict[int, Mapping] = {}
    for mapping in mappings:
        if mapping.relation_kind == "secondary_articulation_cluster":
            for index, operation in enumerate(operations):
                if operation.rule_index in mapping.rule_indices and operation.operation != "match":
                    complete_by_operation[index] = mapping
    supported = supported_representation_rule_only_indices(operations)
    issues: list[Mapping | None] = []
    seen_secondary: set[tuple[int, ...]] = set()
    for index, operation in enumerate(operations):
        if operation.operation == "match":
            continue
        secondary = complete_by_operation.get(index)
        if secondary is not None:
            if secondary.rule_indices not in seen_secondary:
                issues.append(secondary)
                seen_secondary.add(secondary.rule_indices)
            continue
        if operation.operation == "rule_only" and index in supported:
            continue
        if operation.operation == "candidate_only" or operation.rule_index is None:
            issues.append(None)
            continue
        phone = (
            classify_phone(operation.candidate_phone, group_lookup)
            if operation.candidate_phone
            else None
        )
        issues.append(
            Mapping(
                relation_kind="direct_unit",
                rule_indices=(operation.rule_index,),
                phone=operation.candidate_phone,
                phone_display=phone.phone_class_r_auto if phone else "",
                phone_key=phone.comparison_key if phone else "",
                phone_model_group=phone.model_group_r if phone else "",
                secondary_articulation=phone.secondary_articulation if phone else "",
            )
        )
    return issues, operations


def evidence_row(
    *, row: dict[str, str], variant_index: int, variant: str, issue_index: int,
    mapping: Mapping | None, rule: Sequence[RomanUnit],
    canonical_index: dict[str, dict[tuple[object, ...], Observation]],
    frozen_index: dict[str, dict[str, dict[tuple[object, ...], Observation]]],
) -> tuple[dict[str, object], str]:
    if mapping is None:
        canonical = frozen = None
        relation_kind = "unsupported_candidate_only"
        indices: tuple[int, ...] = ()
        units: list[str] = []
        current_phone = ""
    else:
        relation_kind = mapping.relation_kind
        indices = mapping.rule_indices
        units = [rule[index].display for index in indices]
        current_phone = mapping.phone
        keys = context_keys(token=row["token"], rule=rule, mapping=mapping)
        if relation_kind == "direct_unit":
            canonical = choose_evidence(
                canonical_index,
                keys=keys,
                levels=CONTEXT_LEVELS,
                thresholds={level: 2 for level in CONTEXT_LEVELS},
            )
            frozen = choose_evidence(
                frozen_index["direct_unit"],
                keys=keys,
                levels=DIRECT_FROZEN_LEVELS,
                thresholds={
                    "word_exact": 1,
                    "syllable_signature": 2,
                    "window2_boundary": 2,
                    "window1_boundary": 2,
                },
            )
        else:
            canonical = None
            frozen = choose_evidence(
                frozen_index["secondary_articulation_cluster"],
                keys=keys,
                levels=SECONDARY_FROZEN_LEVELS,
                thresholds={
                    "word_exact": 1,
                    "syllable_signature": 2,
                    "compound_vowel_boundary": 2,
                },
            )
    category = evidence_class(canonical, frozen)
    supported_phones = set(canonical.phone_counts if canonical else ()) | set(
        frozen.phone_counts if frozen else ()
    )
    result = {
        "token": row["token"],
        "total_occurrences": row["total_occurrences"],
        "planning_status": row["planning_status"],
        "variant_index": variant_index,
        "r2_pron_phones": variant,
        "issue_index": issue_index,
        "relation_kind": relation_kind,
        "rule_indices_json": json.dumps(indices, ensure_ascii=False),
        "rule_units_json": json.dumps(units, ensure_ascii=False),
        "current_candidate_phone": current_phone,
        "canonical_context_level": canonical.level if canonical else "",
        "canonical_context_json": json.dumps(canonical.context, ensure_ascii=False) if canonical else "[]",
        "canonical_phone_counts_json": json.dumps(canonical.phone_counts, ensure_ascii=False, sort_keys=True) if canonical else "{}",
        "canonical_token_type_count": canonical.token_type_count if canonical else 0,
        "frozen_context_level": frozen.level if frozen else "",
        "frozen_context_json": json.dumps(frozen.context, ensure_ascii=False) if frozen else "[]",
        "frozen_phone_counts_json": json.dumps(frozen.phone_counts, ensure_ascii=False, sort_keys=True) if frozen else "{}",
        "frozen_token_type_count": frozen.token_type_count if frozen else 0,
        "evidence_class": category,
        "current_candidate_supported": str(bool(current_phone and current_phone in supported_phones)).lower(),
        "standard_pronunciation_claimed": "false",
        "actual_realization_claimed": "false",
        "candidate_generation_performed": "false",
    }
    return result, category


def verify_existing(
    output_root: Path, *, readiness_manifest_path: Path, base_dictionary: Path,
    policy_path: Path
) -> dict[str, object]:
    manifest_path = output_root / "CONTEXTUAL_DICTIONARY_DONOR_AUDIT_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"contextual donor root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("existing contextual donor audit differs")
    for key, path in (
        ("readiness_v2_manifest", readiness_manifest_path),
        ("base_dictionary", base_dictionary),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
    for key, record in manifest["outputs"].items():
        verify_fingerprint(record, Path(str(record["path"])), label=f"existing {key}")
    return manifest


def build_audit(
    *, readiness_manifest_path: Path, base_dictionary: Path,
    policy_path: Path, output_root: Path
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            readiness_manifest_path=readiness_manifest_path,
            base_dictionary=base_dictionary,
            policy_path=policy_path,
        )
    readiness_manifest = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    if (
        readiness_manifest.get("schema_version") != READINESS_SCHEMA
        or readiness_manifest.get("status") != "success_planning_not_selected"
    ):
        raise RuntimeError("readiness v2 input differs")
    validate_policy(policy_path)
    readiness_path = Path(
        str(readiness_manifest["outputs"]["selection_readiness_v2"]["path"])
    ).resolve()
    acoustic_model = Path(str(readiness_manifest["inputs"]["coverage_manifest"]["path"])).resolve()
    coverage_manifest = json.loads(acoustic_model.read_text(encoding="utf-8-sig"))
    acoustic_model = Path(str(coverage_manifest["inputs"]["acoustic_model"]["path"])).resolve()
    for record, path, label in (
        (readiness_manifest["outputs"]["selection_readiness_v2"], readiness_path, "readiness v2"),
        (coverage_manifest["inputs"]["base_dictionary"], base_dictionary, "base dictionary"),
        (coverage_manifest["inputs"]["acoustic_model"], acoustic_model, "acoustic model"),
    ):
        verify_fingerprint(record, path, label=label)
    _, pronunciations = read_mfa_dictionary(base_dictionary)
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    inventory_output = temp_root / "frozen_dictionary_contextual_donor_inventory.csv.gz"
    issue_output = temp_root / "residual_hold_contextual_donor_evidence.csv.gz"
    hold_output = temp_root / "residual_hold_contextual_donor_classification.csv.gz"
    manifest_output = temp_root / "CONTEXTUAL_DICTIONARY_DONOR_AUDIT_MANIFEST.json"
    final_inventory = output_root / inventory_output.name
    final_issue = output_root / issue_output.name
    final_hold = output_root / hold_output.name
    final_manifest = output_root / manifest_output.name

    with gzip_writer(inventory_output) as stream:
        writer = csv.DictWriter(stream, fieldnames=INVENTORY_FIELDS, lineterminator="\n")
        writer.writeheader()
        frozen_index, inventory_counts = build_frozen_inventory(
            pronunciations=pronunciations, group_lookup=group_lookup, writer=writer
        )
    canonical_index, canonical_counts = build_canonical_index(readiness_path, group_lookup)

    hold_class_types: Counter[str] = Counter()
    hold_class_occurrences: Counter[str] = Counter()
    issue_class_rows: Counter[str] = Counter()
    planning_types: Counter[str] = Counter()
    planning_occurrences: Counter[str] = Counter()
    hold_types = hold_occurrences = variant_rows = issue_rows = 0
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(issue_output) as issue_stream, gzip_writer(hold_output) as hold_stream:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness v2 column contract differs")
        issue_writer = csv.DictWriter(issue_stream, fieldnames=ISSUE_FIELDS, lineterminator="\n")
        hold_writer = csv.DictWriter(hold_stream, fieldnames=HOLD_FIELDS, lineterminator="\n")
        issue_writer.writeheader()
        hold_writer.writeheader()
        for row in reader:
            is_hold = row["planning_zero_fallback_hold"] == "true"
            if not is_hold:
                continue
            if row["planning_status"] not in HOLD_STATUSES:
                raise RuntimeError(f"unexpected readiness hold status: {row['token']}")
            token = row["token"]
            occurrences = int(row["total_occurrences"])
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            variants = parse_list(row["r2_pron_phones_json"], label=f"hold variants {token}")
            if not variants:
                raise RuntimeError(f"hold lacks r2 variants: {token}")
            token_variant_audit: list[dict[str, object]] = []
            token_classes: list[str] = []
            token_issue_count = canonical_supported = frozen_supported = 0
            for variant_index, variant in enumerate(variants, 1):
                phones = tuple(clean(variant).split())
                issues, operations = issue_mappings(phones, rule, group_lookup)
                variant_classes: list[str] = []
                variant_issue_rows: list[dict[str, object]] = []
                for issue_index, mapping in enumerate(issues, 1):
                    output, category = evidence_row(
                        row=row,
                        variant_index=variant_index,
                        variant=variant,
                        issue_index=issue_index,
                        mapping=mapping,
                        rule=rule,
                        canonical_index=canonical_index,
                        frozen_index=frozen_index,
                    )
                    issue_writer.writerow(output)
                    variant_issue_rows.append(output)
                    variant_classes.append(category)
                    issue_class_rows[category] += 1
                    issue_rows += 1
                    token_issue_count += 1
                    canonical_supported += int(bool(output["canonical_context_level"]))
                    frozen_supported += int(bool(output["frozen_context_level"]))
                variant_class = aggregate_classes(variant_classes)
                token_classes.append(variant_class)
                token_variant_audit.append(
                    {
                        "variant_index": variant_index,
                        "r2_pron_phones": variant,
                        "alignment_signature": edit_signature(operations),
                        "issue_count": len(issues),
                        "issue_classes": variant_classes,
                        "variant_support_class": variant_class,
                    }
                )
                variant_rows += 1
            token_class = aggregate_classes(token_classes, variant_count=len(variants))
            hold_writer.writerow(
                {
                    **{field: row[field] for field in HOLD_FIELDS[: 5 + len(YEARS)]},
                    "rule_pron_hangul": row["rule_pron_hangul"],
                    "rule_pron_roman": row["rule_pron_roman"],
                    "surface_rule_names": row["surface_rule_names"],
                    "r2_pron_phones_json": row["r2_pron_phones_json"],
                    "r2_pron_source": row["r2_pron_source"],
                    "planning_status": row["planning_status"],
                    "no_rule_coverage_status": row["no_rule_coverage_status"],
                    "audited_variant_count": len(variants),
                    "audited_issue_count": token_issue_count,
                    "canonical_supported_issue_count": canonical_supported,
                    "frozen_supported_issue_count": frozen_supported,
                    "contextual_support_class": token_class,
                    "variant_audit_json": json.dumps(token_variant_audit, ensure_ascii=False),
                    "researcher_review_required_now": "false",
                    "standard_pronunciation_claimed": "false",
                    "actual_realization_claimed": "false",
                    "candidate_generation_performed": "false",
                    "canonical_selection_performed": "false",
                }
            )
            hold_types += 1
            hold_occurrences += occurrences
            hold_class_types[token_class] += 1
            hold_class_occurrences[token_class] += occurrences
            planning_types[row["planning_status"]] += 1
            planning_occurrences[row["planning_status"]] += occurrences

    expected_types = int(readiness_manifest["counts"]["zero_fallback_hold_types"])
    expected_occurrences = int(readiness_manifest["counts"]["zero_fallback_hold_occurrences"])
    if (hold_types, hold_occurrences) != (expected_types, expected_occurrences):
        raise RuntimeError("contextual hold coverage differs from readiness v2")

    counts = {
        "dictionary_inventory": dict(sorted(inventory_counts.items())),
        "canonical_exact_donors": dict(sorted(canonical_counts.items())),
        "hold_types": hold_types,
        "hold_occurrences": hold_occurrences,
        "hold_variant_rows": variant_rows,
        "hold_issue_rows": issue_rows,
        "planning_status_types": dict(sorted(planning_types.items())),
        "planning_status_occurrences": dict(sorted(planning_occurrences.items())),
        "issue_evidence_class_rows": dict(sorted(issue_class_rows.items())),
        "hold_contextual_support_class_types": dict(sorted(hold_class_types.items())),
        "hold_contextual_support_class_occurrences": dict(sorted(hold_class_occurrences.items())),
        "canonical_context_rows": {level: len(canonical_index[level]) for level in CONTEXT_LEVELS},
        "frozen_context_rows": {
            relation: {level: len(rows) for level, rows in sorted(levels.items())}
            for relation, levels in sorted(frozen_index.items())
        },
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_audited_not_candidate",
        "recorded_at": now_iso(),
        "scope": {
            "contextual_donor_inventory_built": True,
            "all_zero_fallback_holds_classified": True,
            "global_phone_to_phoneme_mapping_applied": False,
            "candidate_generation_performed": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "readiness_v2_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "readiness_v2": file_fingerprint(readiness_path, with_sha256=True),
            "base_dictionary": file_fingerprint(base_dictionary, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
        },
        "counts": counts,
        "outputs": {
            "frozen_dictionary_contextual_inventory": fingerprint_for_final(inventory_output, final_inventory),
            "residual_hold_contextual_evidence": fingerprint_for_final(issue_output, final_issue),
            "residual_hold_contextual_classification": fingerprint_for_final(hold_output, final_hold),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_output, manifest)
    os.replace(temp_root, output_root)
    return json.loads(final_manifest.read_text(encoding="utf-8-sig"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--readiness-v2-manifest", type=Path, required=True)
    result.add_argument("--base-dictionary", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_audit(
        readiness_manifest_path=args.readiness_v2_manifest.resolve(),
        base_dictionary=args.base_dictionary.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
