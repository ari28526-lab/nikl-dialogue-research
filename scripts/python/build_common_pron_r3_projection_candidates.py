"""Build evidence-bound r3 phone projection candidates without selecting them.

The stage formalizes two distinct operations:

1. a narrow acoustic-model *unitization* relation (length and glide absorption),
2. an exact-context donor projection for genuine G2P/rule differences.

Neither operation selects a canonical pronunciation, adopts an MFA dictionary,
or modifies an alignment/TextGrid.  A projected phone sequence is emitted only
when its donor context is unanimous in the exact-agreement pool and the complete
sequence independently satisfies the frozen representation relation.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
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

from audit_common_pron_rule_consistency import YEARS, phone_units, roman_units  # noqa: E402
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    SCHEMA_VERSION as AGREEMENT_SCHEMA,
    SOURCE_RESULT_FIELDS,
    TARGET_RESULT_FIELDS,
)
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    SCHEMA_VERSION as DIAGNOSTIC_SCHEMA,
    SOURCE_DIAGNOSTIC_FIELDS,
    TARGET_DIAGNOSTIC_FIELDS,
    EditOperation,
    edit_signature,
    phone_encodes_glide,
    representation_support,
    unit_edit_alignment,
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
SCHEMA_VERSION = "common_pron_r3_projection_candidates.v1"
POLICY_SCHEMA = "common_pron_r3_model_projection.v1"
CONTEXT_LEVELS = ("window2_boundary", "window1_boundary", "unit_boundary")

TARGET_PROJECTION_FIELDS = (
    *TARGET_RESULT_FIELDS,
    "diagnostic_layer",
    "diagnostic_class",
    "edit_signature",
    "representation_relation",
    "projection_status",
    "projection_candidate_count",
    "projected_pron_phones_json",
    "projected_pron_roman_json",
    "projection_patch_operations_json",
    "projection_evidence_ids_json",
    "projection_candidate_is_final_selection",
)
SOURCE_PROJECTION_FIELDS = (
    *SOURCE_RESULT_FIELDS,
    "target_representation_relation",
    "target_projection_status",
    "target_projection_candidate_count",
    "projected_pron_phones_json",
    "projected_pron_roman_json",
    "source_projection_gate_class",
    "dictionary_rule_agreement",
    "projection_candidate_is_final_selection",
)
EVIDENCE_FIELDS = (
    "evidence_id",
    "context_level",
    "context_json",
    "rule_display",
    "projected_phone",
    "support_target_type_count",
    "support_unit_count",
    "observed_phone_counts_json",
    "example_exact_targets_json",
    "unanimous_phone",
    "candidate_is_final_selection",
)
csv.field_size_limit(10_000_000)


@dataclass
class DonorObservation:
    phone_counts: Counter[str] = field(default_factory=Counter)
    target_type_count: int = 0
    unit_count: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectionEvidence:
    evidence_id: str
    context_level: str
    context: tuple[object, ...]
    rule_display: str
    phone: str
    target_type_count: int
    unit_count: int
    phone_counts: dict[str, int]
    examples: tuple[str, ...]


def clean(value: object) -> str:
    return str(value or "").strip()


def load_string_list(value: object, *, label: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON string list: {label}") from exc
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


def validate_policy(path: Path, *, acoustic_model: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "candidate_generation_only":
        raise RuntimeError("model projection policy is not candidate-only v1")
    if tuple(str(year) for year in policy.get("scope_years", ())) != YEARS:
        raise RuntimeError("model projection policy year scope differs")
    frozen = policy.get("frozen_acoustic_model", {})
    if (
        Path(str(frozen.get("path", ""))).resolve() != acoustic_model.resolve()
        or clean(frozen.get("sha256")).lower() != sha256_file(acoustic_model).lower()
    ):
        raise RuntimeError("model projection policy acoustic model differs")
    donor = policy.get("exact_context_donor_policy", {})
    if tuple(donor.get("specificity_order", ())) != CONTEXT_LEVELS:
        raise RuntimeError("model projection context order differs")
    if int(donor.get("minimum_distinct_target_types", 0)) != 2:
        raise RuntimeError("model projection minimum donor support differs")
    if donor.get("mode_or_first_variant_selection_allowed") is not False:
        raise RuntimeError("mode/first projection selection is forbidden")
    required_false = (
        "candidate_is_final_selection",
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "source_files_modified",
        "actual_realization_claimed",
    )
    invariants = policy.get("invariants", {})
    if any(invariants.get(key) is not False for key in required_false):
        raise RuntimeError("model projection policy exceeds candidate scope")
    return policy


def unit_boundaries(rule: Sequence[RomanUnit], index: int) -> tuple[bool, bool, bool, bool]:
    current = rule[index]
    syllable_start = index == 0 or rule[index - 1].syllable_index != current.syllable_index
    syllable_end = index == len(rule) - 1 or rule[index + 1].syllable_index != current.syllable_index
    return syllable_start, syllable_end, index == 0, index == len(rule) - 1


def context_key(rule: Sequence[RomanUnit], index: int, level: str) -> tuple[object, ...]:
    if level not in CONTEXT_LEVELS:
        raise ValueError(f"unknown context level: {level}")

    def display(position: int) -> str:
        if position < 0:
            return "<BOS>"
        if position >= len(rule):
            return "<EOS>"
        return rule[position].display

    boundaries = unit_boundaries(rule, index)
    current = rule[index].display
    if level == "window2_boundary":
        return (display(index - 2), display(index - 1), current, display(index + 1), display(index + 2), *boundaries)
    if level == "window1_boundary":
        return (display(index - 1), current, display(index + 1), *boundaries)
    return (current, *boundaries)


def supported_representation_rule_only_indices(
    operations: Sequence[EditOperation],
) -> dict[int, str]:
    """Return individually supported rule-only edits, even in a mixed row."""

    supported: dict[int, str] = {}
    for operation_index, operation in enumerate(operations):
        if operation.operation != "rule_only":
            continue
        neighbors = [
            operations[position]
            for position in (operation_index - 1, operation_index + 1)
            if 0 <= position < len(operations)
            and operations[position].operation == "match"
            and operations[position].candidate_index is not None
        ]
        if operation.rule_key in {"Y", "W"} and any(
            phone_encodes_glide(neighbor.candidate_phone, operation.rule_key)
            for neighbor in neighbors
        ):
            supported[operation_index] = "secondary_articulation_glide"
            continue
        if any(
            neighbor.candidate_key == operation.rule_key
            and neighbor.candidate_has_length is True
            for neighbor in neighbors
        ):
            supported[operation_index] = "length_marked_identical_unit"
    return supported


def representation_relation(
    phones: Sequence[str],
    rule: Sequence[RomanUnit],
    group_lookup: dict[str, int],
) -> tuple[str, list[EditOperation]]:
    candidate = tuple(classify_phone(phone, group_lookup) for phone in phones)
    operations = unit_edit_alignment(candidate, rule)
    edits = [operation for operation in operations if operation.operation != "match"]
    if not edits:
        return "exact_comparison_keys", operations
    support = representation_support(operations)
    if support == {"length_marked_identical_unit"}:
        return "equivalent_length_unitization", operations
    if support == {"secondary_articulation_glide"}:
        return "equivalent_glide_unitization", operations
    if support == {"length_marked_identical_unit", "secondary_articulation_glide"}:
        return "equivalent_combined_unitization", operations
    return "not_equivalent", operations


def donor_query_indices(operations: Sequence[EditOperation]) -> set[int]:
    supported = supported_representation_rule_only_indices(operations)
    result: set[int] = set()
    for operation_index, operation in enumerate(operations):
        if operation.operation == "substitution" and operation.rule_index is not None:
            result.add(operation.rule_index)
        elif (
            operation.operation == "rule_only"
            and operation_index not in supported
            and operation.rule_index is not None
        ):
            result.add(operation.rule_index)
    return result


def build_query_sets(
    diagnostics_path: Path,
) -> tuple[dict[str, set[tuple[object, ...]]], int]:
    result = {level: set() for level in CONTEXT_LEVELS}
    row_count = 0
    with gzip.open(diagnostics_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_DIAGNOSTIC_FIELDS:
            raise RuntimeError("target diagnostic column contract differs")
        for row in reader:
            row_count += 1
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            operations = [EditOperation(**item) for item in json.loads(row["edit_operations_json"])]
            for rule_index in donor_query_indices(operations):
                for level in CONTEXT_LEVELS:
                    result[level].add(context_key(rule, rule_index, level))
    return result, row_count


def build_donor_index(
    *,
    agreement_target_path: Path,
    query_sets: dict[str, set[tuple[object, ...]]],
) -> tuple[dict[str, dict[tuple[object, ...], DonorObservation]], int, int]:
    index: dict[str, dict[tuple[object, ...], DonorObservation]] = {
        level: {} for level in CONTEXT_LEVELS
    }
    exact_rows = 0
    exact_units = 0
    with gzip.open(agreement_target_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_RESULT_FIELDS:
            raise RuntimeError("agreement target column contract differs")
        for row in reader:
            if row["comparison_status"] != "exact_rule_roman" or row["rewrite_rule"] != "none":
                continue
            target = clean(row["target_hangul"])
            phones = tuple(clean(row["g2p_candidate_phones"]).split())
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            if len(phones) != len(rule):
                raise RuntimeError(f"exact donor length differs: {target}")
            exact_rows += 1
            exact_units += len(rule)
            seen: set[tuple[str, tuple[object, ...]]] = set()
            for unit_index, (phone, reference) in enumerate(zip(phones, rule, strict=True)):
                for level in CONTEXT_LEVELS:
                    key = context_key(rule, unit_index, level)
                    if key not in query_sets[level]:
                        continue
                    observation = index[level].setdefault(key, DonorObservation())
                    observation.phone_counts[phone] += 1
                    observation.unit_count += 1
                    marker = (level, key)
                    if marker not in seen:
                        observation.target_type_count += 1
                        seen.add(marker)
                    if target not in observation.examples and len(observation.examples) < 5:
                        observation.examples.append(target)
    return index, exact_rows, exact_units


def projection_evidence_id(level: str, key: tuple[object, ...], phone: str) -> str:
    payload = json.dumps(
        {"level": level, "context": key, "phone": phone},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "projctx-" + hashlib.sha256(payload).hexdigest()[:20]


def choose_projection_evidence(
    *,
    donor_index: dict[str, dict[tuple[object, ...], DonorObservation]],
    rule: Sequence[RomanUnit],
    rule_index: int,
    minimum_target_types: int = 2,
) -> ProjectionEvidence | None:
    for level in CONTEXT_LEVELS:
        key = context_key(rule, rule_index, level)
        observation = donor_index[level].get(key)
        if (
            observation is None
            or observation.target_type_count < minimum_target_types
            or len(observation.phone_counts) != 1
        ):
            continue
        phone = next(iter(observation.phone_counts))
        return ProjectionEvidence(
            evidence_id=projection_evidence_id(level, key, phone),
            context_level=level,
            context=key,
            rule_display=rule[rule_index].display,
            phone=phone,
            target_type_count=observation.target_type_count,
            unit_count=observation.unit_count,
            phone_counts=dict(sorted(observation.phone_counts.items())),
            examples=tuple(observation.examples),
        )
    return None


def unchanged_candidate(
    row: dict[str, str], *, relation: str, status: str
) -> dict[str, object]:
    phones = clean(row["g2p_candidate_phones"])
    roman = clean(row["g2p_candidate_roman"])
    return {
        "representation_relation": relation,
        "projection_status": status,
        "projection_candidate_count": 1,
        "projected_pron_phones_json": json.dumps([phones], ensure_ascii=False),
        "projected_pron_roman_json": json.dumps([roman], ensure_ascii=False),
        "projection_patch_operations_json": "[]",
        "projection_evidence_ids_json": "[]",
    }


def project_mismatch(
    *,
    row: dict[str, str],
    donor_index: dict[str, dict[tuple[object, ...], DonorObservation]],
    group_lookup: dict[str, int],
    used_evidence: dict[str, ProjectionEvidence],
) -> dict[str, object]:
    phones = tuple(clean(row["g2p_candidate_phones"]).split())
    rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
    candidate = tuple(classify_phone(phone, group_lookup) for phone in phones)
    operations = unit_edit_alignment(candidate, rule)
    if edit_signature(operations) != clean(row["edit_signature"]):
        raise RuntimeError(f"diagnostic edit signature differs: {row['target_hangul']}")
    relation, _ = representation_relation(phones, rule, group_lookup)
    if clean(row["diagnostic_layer"]) == "representation_equivalence_candidate":
        if relation == "not_equivalent":
            raise RuntimeError(f"representation candidate no longer equivalent: {row['target_hangul']}")
        return unchanged_candidate(
            row,
            relation=relation,
            status="candidate_model_unitization_equivalent_unchanged",
        )

    supported = supported_representation_rule_only_indices(operations)
    projected: list[str] = []
    patches: list[dict[str, object]] = []
    evidence_ids: list[str] = []
    missing = False
    candidate_only = False
    for operation_index, operation in enumerate(operations):
        if operation.operation == "match":
            projected.append(operation.candidate_phone)
            continue
        if operation.operation == "rule_only" and operation_index in supported:
            patches.append(
                {
                    "operation_index": operation_index,
                    "action": "retain_adjacent_model_unitization",
                    "rule_index": operation.rule_index,
                    "rule_display": operation.rule_display,
                    "support": supported[operation_index],
                }
            )
            continue
        if operation.operation == "candidate_only":
            candidate_only = True
            patches.append(
                {
                    "operation_index": operation_index,
                    "action": "hold_candidate_only_deletion",
                    "candidate_index": operation.candidate_index,
                    "candidate_phone": operation.candidate_phone,
                }
            )
            continue
        if operation.rule_index is None:
            raise RuntimeError("projection operation lacks rule index")
        evidence = choose_projection_evidence(
            donor_index=donor_index,
            rule=rule,
            rule_index=operation.rule_index,
        )
        if evidence is None:
            missing = True
            patches.append(
                {
                    "operation_index": operation_index,
                    "action": "hold_no_unanimous_exact_context_donor",
                    "candidate_phone": operation.candidate_phone,
                    "rule_index": operation.rule_index,
                    "rule_display": operation.rule_display,
                }
            )
            continue
        projected.append(evidence.phone)
        used_evidence[evidence.evidence_id] = evidence
        evidence_ids.append(evidence.evidence_id)
        patches.append(
            {
                "operation_index": operation_index,
                "action": "replace" if operation.operation == "substitution" else "insert",
                "candidate_phone": operation.candidate_phone,
                "projected_phone": evidence.phone,
                "rule_index": operation.rule_index,
                "rule_display": operation.rule_display,
                "evidence_id": evidence.evidence_id,
            }
        )

    base = {
        "representation_relation": "not_equivalent",
        "projection_candidate_count": 0,
        "projected_pron_phones_json": "[]",
        "projected_pron_roman_json": "[]",
        "projection_patch_operations_json": json.dumps(patches, ensure_ascii=False, sort_keys=True),
        "projection_evidence_ids_json": json.dumps(sorted(set(evidence_ids)), ensure_ascii=False),
    }
    if candidate_only:
        return {**base, "projection_status": "hold_candidate_only_deletion_requires_policy"}
    if missing:
        return {**base, "projection_status": "hold_no_unanimous_exact_context_donor"}
    projected_relation, _ = representation_relation(projected, rule, group_lookup)
    if projected_relation == "not_equivalent":
        return {**base, "projection_status": "hold_projected_sequence_not_equivalent"}
    displays, _ = phone_units(tuple(projected), group_lookup)
    return {
        **base,
        "representation_relation": projected_relation,
        "projection_status": "candidate_exact_context_projection",
        "projection_candidate_count": 1,
        "projected_pron_phones_json": json.dumps([" ".join(projected)], ensure_ascii=False),
        "projected_pron_roman_json": json.dumps([" ".join(displays)], ensure_ascii=False),
    }


def source_projection_route(row: dict[str, str], *, target_candidate_count: int) -> tuple[str, bool]:
    _, rule_keys = roman_units(row["rule_pron_roman"])
    dictionary_agreement = False
    for value in load_string_list(
        row["dictionary_pron_roman_json"], label=f"dictionary Roman {row['token']}"
    ):
        _, keys = roman_units(value)
        if keys and keys == rule_keys:
            dictionary_agreement = True
            break
    original = clean(row["original_selection_status"])
    if original == "candidate_replace_rule_dictionary_agree" and not dictionary_agreement:
        raise RuntimeError(f"dictionary agreement route differs: {row['token']}")
    if target_candidate_count == 0:
        return "hold_target_projection_unresolved", dictionary_agreement
    routes = {
        "candidate_replace_rule_dictionary_agree": "candidate_projection_dictionary_agree",
        "review_rule_dictionary_conflict": "hold_projection_dictionary_conflict",
        "review_rule_sensitive_no_attested_agreement": "hold_projection_no_independent_dictionary",
    }
    if original not in routes:
        raise RuntimeError(f"unexpected source selection route: {original}")
    return routes[original], dictionary_agreement


def verify_existing(
    output_root: Path,
    *,
    agreement_manifest_path: Path,
    diagnostic_manifest_path: Path,
    policy_path: Path,
) -> dict[str, object]:
    manifest_path = output_root / "PROJECTION_CANDIDATES_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"projection root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("existing projection candidate manifest is not reusable")
    for key, path in (
        ("agreement_manifest", agreement_manifest_path),
        ("diagnostic_manifest", diagnostic_manifest_path),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
    for key, record in manifest["outputs"].items():
        verify_fingerprint(record, Path(str(record["path"])), label=f"existing output {key}")
    return manifest


def build_projection_candidates(
    *,
    agreement_manifest_path: Path,
    diagnostic_manifest_path: Path,
    policy_path: Path,
    output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            agreement_manifest_path=agreement_manifest_path,
            diagnostic_manifest_path=diagnostic_manifest_path,
            policy_path=policy_path,
        )
    agreement = json.loads(agreement_manifest_path.read_text(encoding="utf-8-sig"))
    diagnostics = json.loads(diagnostic_manifest_path.read_text(encoding="utf-8-sig"))
    if agreement.get("schema_version") != AGREEMENT_SCHEMA or agreement.get("status") != "success_candidates_not_selected":
        raise RuntimeError("agreement manifest is not a completed candidate-only input")
    if diagnostics.get("schema_version") != DIAGNOSTIC_SCHEMA or diagnostics.get("status") != "success_diagnostics_not_selected":
        raise RuntimeError("diagnostic manifest is not completed")
    required_false = (
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "actual_realization_claimed",
    )
    if any(agreement.get("scope", {}).get(key) is not False for key in required_false):
        raise RuntimeError("agreement manifest exceeds candidate scope")
    if any(diagnostics.get("scope", {}).get(key) is not False for key in required_false):
        raise RuntimeError("diagnostic manifest exceeds candidate scope")

    agreement_target = Path(str(agreement["outputs"]["target_agreement"]["path"])).resolve()
    agreement_source = Path(str(agreement["outputs"]["source_agreement"]["path"])).resolve()
    diagnostic_target = Path(str(diagnostics["outputs"]["target_diagnostics"]["path"])).resolve()
    diagnostic_source = Path(str(diagnostics["outputs"]["source_diagnostics"]["path"])).resolve()
    acoustic_model = Path(str(agreement["inputs"]["acoustic_model"]["path"])).resolve()
    for label, record, path in (
        ("agreement target", agreement["outputs"]["target_agreement"], agreement_target),
        ("agreement source", agreement["outputs"]["source_agreement"], agreement_source),
        ("diagnostic target", diagnostics["outputs"]["target_diagnostics"], diagnostic_target),
        ("diagnostic source", diagnostics["outputs"]["source_diagnostics"], diagnostic_source),
        ("acoustic model", agreement["inputs"]["acoustic_model"], acoustic_model),
    ):
        verify_fingerprint(record, path, label=label)
    policy = validate_policy(policy_path, acoustic_model=acoustic_model)
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))

    query_sets, diagnostic_rows = build_query_sets(diagnostic_target)
    if diagnostic_rows != int(diagnostics["counts"]["target_rows"]):
        raise RuntimeError("diagnostic query coverage differs")
    donor_index, donor_exact_rows, donor_exact_units = build_donor_index(
        agreement_target_path=agreement_target,
        query_sets=query_sets,
    )

    mismatch_projection: dict[str, dict[str, object]] = {}
    used_evidence: dict[str, ProjectionEvidence] = {}
    with gzip.open(diagnostic_target, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_DIAGNOSTIC_FIELDS:
            raise RuntimeError("diagnostic target column contract differs")
        for row in reader:
            target = clean(row["target_hangul"])
            mismatch_projection[target] = {
                "diagnostic_layer": clean(row["diagnostic_layer"]),
                "diagnostic_class": clean(row["diagnostic_class"]),
                "edit_signature": clean(row["edit_signature"]),
                "projection": project_mismatch(
                    row=row,
                    donor_index=donor_index,
                    group_lookup=group_lookup,
                    used_evidence=used_evidence,
                ),
            }

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True)
    target_output = temp_root / "g2p_target_projection_candidates.csv.gz"
    source_output = temp_root / "g2p_source_projection_candidates.csv.gz"
    evidence_output = temp_root / "exact_context_projection_evidence.csv"
    manifest_output = temp_root / "PROJECTION_CANDIDATES_MANIFEST.json"
    final_target = output_root / target_output.name
    final_source = output_root / source_output.name
    final_evidence = output_root / evidence_output.name
    final_manifest = output_root / manifest_output.name

    target_lookup: dict[str, tuple[str, str, int, str, str]] = {}
    target_status: Counter[str] = Counter()
    target_relation: Counter[str] = Counter()
    target_occurrences: Counter[str] = Counter()
    with gzip.open(agreement_target, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(target_output) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != TARGET_RESULT_FIELDS:
            raise RuntimeError("agreement target column contract differs")
        writer = csv.DictWriter(target, fieldnames=TARGET_PROJECTION_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            target_hangul = clean(row["target_hangul"])
            if row["comparison_status"] == "exact_rule_roman":
                projection = unchanged_candidate(
                    row,
                    relation="exact_comparison_keys",
                    status="candidate_exact_gate_unchanged",
                )
                diagnostic_layer = "exact_gate"
                diagnostic_class = "exact_rule_roman"
                signature = ""
            else:
                mismatch = mismatch_projection.pop(target_hangul, None)
                if mismatch is None:
                    raise RuntimeError(f"target mismatch projection missing: {target_hangul}")
                projection = mismatch["projection"]
                if not isinstance(projection, dict):
                    raise RuntimeError(f"target mismatch projection type error: {target_hangul}")
                diagnostic_layer = clean(mismatch["diagnostic_layer"])
                diagnostic_class = clean(mismatch["diagnostic_class"])
                signature = clean(mismatch["edit_signature"])
            output = {
                **row,
                "diagnostic_layer": diagnostic_layer,
                "diagnostic_class": diagnostic_class,
                "edit_signature": signature,
                **projection,
                "projection_candidate_is_final_selection": "false",
            }
            writer.writerow(output)
            status = clean(projection["projection_status"])
            relation = clean(projection["representation_relation"])
            count = int(projection["projection_candidate_count"])
            phones_json = clean(projection["projected_pron_phones_json"])
            romans_json = clean(projection["projected_pron_roman_json"])
            target_lookup[target_hangul] = (status, relation, count, phones_json, romans_json)
            target_status[status] += 1
            target_relation[relation] += 1
            target_occurrences[status] += int(row["total_occurrences"])
    if mismatch_projection:
        raise RuntimeError(f"unconsumed mismatch projections: {len(mismatch_projection)}")
    if len(target_lookup) != int(agreement["counts"]["target_rows"]):
        raise RuntimeError("projection target coverage differs")

    source_status: Counter[str] = Counter()
    source_occurrences: Counter[str] = Counter()
    source_rows = 0
    with gzip.open(agreement_source, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(source_output) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != SOURCE_RESULT_FIELDS:
            raise RuntimeError("agreement source column contract differs")
        writer = csv.DictWriter(target, fieldnames=SOURCE_PROJECTION_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            target_hangul = clean(row["target_hangul"])
            if target_hangul not in target_lookup:
                raise RuntimeError(f"source target projection missing: {row['token']}")
            status, relation, count, phones_json, romans_json = target_lookup[target_hangul]
            route, dictionary_agreement = source_projection_route(
                row, target_candidate_count=count
            )
            writer.writerow(
                {
                    **row,
                    "target_representation_relation": relation,
                    "target_projection_status": status,
                    "target_projection_candidate_count": str(count),
                    "projected_pron_phones_json": phones_json,
                    "projected_pron_roman_json": romans_json,
                    "source_projection_gate_class": route,
                    "dictionary_rule_agreement": str(dictionary_agreement).lower(),
                    "projection_candidate_is_final_selection": "false",
                }
            )
            source_rows += 1
            source_status[route] += 1
            source_occurrences[route] += int(row["total_occurrences"])
    if source_rows != int(agreement["counts"]["source_rows"]):
        raise RuntimeError("projection source coverage differs")

    with evidence_output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVIDENCE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for evidence_id in sorted(used_evidence):
            evidence = used_evidence[evidence_id]
            writer.writerow(
                {
                    "evidence_id": evidence.evidence_id,
                    "context_level": evidence.context_level,
                    "context_json": json.dumps(evidence.context, ensure_ascii=False),
                    "rule_display": evidence.rule_display,
                    "projected_phone": evidence.phone,
                    "support_target_type_count": evidence.target_type_count,
                    "support_unit_count": evidence.unit_count,
                    "observed_phone_counts_json": json.dumps(evidence.phone_counts, ensure_ascii=False, sort_keys=True),
                    "example_exact_targets_json": json.dumps(evidence.examples, ensure_ascii=False),
                    "unanimous_phone": "true",
                    "candidate_is_final_selection": "false",
                }
            )

    query_counts = {level: len(query_sets[level]) for level in CONTEXT_LEVELS}
    indexed_counts = {level: len(donor_index[level]) for level in CONTEXT_LEVELS}
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_candidates_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "model_representation_relation_applied": True,
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "agreement_manifest": file_fingerprint(agreement_manifest_path, with_sha256=True),
            "diagnostic_manifest": file_fingerprint(diagnostic_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "agreement_target": file_fingerprint(agreement_target, with_sha256=True),
            "agreement_source": file_fingerprint(agreement_source, with_sha256=True),
            "diagnostic_target": file_fingerprint(diagnostic_target, with_sha256=True),
            "diagnostic_source": file_fingerprint(diagnostic_source, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        },
        "counts": {
            "target_rows": len(target_lookup),
            "source_rows": source_rows,
            "donor_exact_target_rows": donor_exact_rows,
            "donor_exact_units": donor_exact_units,
            "query_contexts": query_counts,
            "indexed_query_contexts": indexed_counts,
            "used_projection_evidence_rows": len(used_evidence),
            "target_projection_status": dict(sorted(target_status.items())),
            "target_representation_relation": dict(sorted(target_relation.items())),
            "target_occurrences_by_projection_status": dict(sorted(target_occurrences.items())),
            "source_projection_gate_class": dict(sorted(source_status.items())),
            "source_occurrences_by_gate_class": dict(sorted(source_occurrences.items())),
        },
        "outputs": {
            "target_projection_candidates": fingerprint_for_final(target_output, final_target),
            "source_projection_candidates": fingerprint_for_final(source_output, final_source),
            "exact_context_projection_evidence": fingerprint_for_final(evidence_output, final_evidence),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_output, manifest)
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--agreement-manifest", type=Path, required=True)
    result.add_argument("--diagnostic-manifest", type=Path, required=True)
    result.add_argument("--policy-contract", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_projection_candidates(
        agreement_manifest_path=args.agreement_manifest.resolve(),
        diagnostic_manifest_path=args.diagnostic_manifest.resolve(),
        policy_path=args.policy_contract.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
