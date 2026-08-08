"""Build an 881,237-type r3 selection-readiness matrix without selecting it."""

from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import os
import sys
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS, phone_units, roman_units  # noqa: E402
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    SOURCE_PROJECTION_FIELDS,
    representation_relation,
)
from phoneme_roman import (  # noqa: E402
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
from resolve_common_pron_r3_surface_donors import (  # noqa: E402
    OUTPUT_FIELDS as DONOR_FIELDS,
    SCHEMA_VERSION as DONOR_SCHEMA,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_selection_readiness.v1"
POLICY_SCHEMA = "common_pron_r3_selection_readiness_policy.v1"
READINESS_FIELDS = (
    *DONOR_FIELDS,
    "r2_model_relation_variant_count",
    "r2_model_relation_phones_json",
    "r2_model_relation_roman_json",
    "r2_model_relation_classes_json",
    "projection_linked",
    "target_projection_status",
    "target_representation_relation",
    "source_projection_gate_class",
    "projection_candidate_count",
    "projection_candidate_phones_json",
    "projection_candidate_roman_json",
    "planning_candidate_variant_count",
    "planning_candidate_phones_json",
    "planning_candidate_roman_json",
    "planning_status",
    "planning_source",
    "planning_reason",
    "planning_requires_policy_decision",
    "planning_zero_fallback_hold",
    "planning_is_final_selection",
)
LINK_FIELDS = (
    "token",
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
    "morph_context_required",
    "manual_decision_id",
)
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def string_list(value: object, *, label: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON list: {label}") from exc
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise RuntimeError(f"invalid string list: {label}")
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


def dedupe_variants(phones: Sequence[str], romans: Sequence[str]) -> tuple[list[str], list[str]]:
    if len(phones) != len(romans):
        raise RuntimeError("phone/Roman variant count differs")
    seen: set[tuple[str, str]] = set()
    out_phones: list[str] = []
    out_romans: list[str] = []
    for phone, roman in zip(phones, romans, strict=True):
        pair = (clean(phone), clean(roman))
        if not all(pair) or pair in seen:
            continue
        seen.add(pair)
        out_phones.append(pair[0])
        out_romans.append(pair[1])
    return out_phones, out_romans


def dictionary_supported_r2(row: dict[str, str]) -> tuple[list[str], list[str]]:
    dictionary_keys = {
        tuple(roman_units(value)[1])
        for value in string_list(row["dictionary_pron_roman_json"], label=f"dictionary {row['token']}")
        if roman_units(value)[1]
    }
    phones = string_list(row["r2_pron_phones_json"], label=f"r2 phones {row['token']}")
    romans = string_list(row["r2_pron_roman_json"], label=f"r2 Roman {row['token']}")
    selected_phones: list[str] = []
    selected_romans: list[str] = []
    for phone, roman in zip(phones, romans, strict=True):
        if tuple(roman_units(roman)[1]) in dictionary_keys:
            selected_phones.append(phone)
            selected_romans.append(roman)
    return dedupe_variants(selected_phones, selected_romans)


def r2_relation_variants(
    row: dict[str, str], group_lookup: dict[str, int]
) -> tuple[list[str], list[str], list[str]]:
    phones = string_list(row["r2_pron_phones_json"], label=f"r2 phones {row['token']}")
    romans = string_list(row["r2_pron_roman_json"], label=f"r2 Roman {row['token']}")
    if len(phones) != len(romans):
        raise RuntimeError(f"r2 variant count differs: {row['token']}")
    rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
    selected_phones: list[str] = []
    selected_romans: list[str] = []
    relations: list[str] = []
    for phone_sequence in phones:
        phone_values = tuple(clean(phone_sequence).split())
        relation, _ = representation_relation(phone_values, rule, group_lookup)
        if relation == "not_equivalent":
            continue
        displays, _ = phone_units(phone_values, group_lookup)
        selected_phones.append(phone_sequence)
        selected_romans.append(" ".join(displays))
        relations.append(relation)
    out_phones, out_romans = dedupe_variants(selected_phones, selected_romans)
    relation_by_pair = {
        (phone, roman): relation
        for phone, roman, relation in zip(selected_phones, selected_romans, relations, strict=True)
    }
    return out_phones, out_romans, [relation_by_pair[(p, r)] for p, r in zip(out_phones, out_romans, strict=True)]


def projection_values(row: dict[str, str] | None) -> tuple[list[str], list[str]]:
    if row is None:
        return [], []
    phones = string_list(row["projected_pron_phones_json"], label=f"projection phones {row['token']}")
    romans = string_list(row["projected_pron_roman_json"], label=f"projection Roman {row['token']}")
    return dedupe_variants(phones, romans)


def planning_decision(
    row: dict[str, str],
    projection: dict[str, str] | None,
    relation_phones: list[str],
    relation_romans: list[str],
) -> dict[str, object]:
    selected_phones = string_list(row["selected_pron_phones_json"], label=f"selected phones {row['token']}")
    selected_romans = string_list(row["selected_pron_roman_json"], label=f"selected Roman {row['token']}")
    donor_phones = string_list(row["candidate_pron_phones_json"], label=f"donor phones {row['token']}")
    donor_romans = string_list(row["candidate_pron_roman_json"], label=f"donor Roman {row['token']}")
    dictionary_phones, dictionary_romans = dictionary_supported_r2(row)
    projection_phones, projection_romans = projection_values(projection)
    status = clean(row["selection_status"])

    def result(
        phones: Sequence[str],
        romans: Sequence[str],
        *,
        code: str,
        source: str,
        reason: str,
        requires_policy: bool = False,
    ) -> dict[str, object]:
        out_phones, out_romans = dedupe_variants(phones, romans)
        return {
            "phones": out_phones,
            "romans": out_romans,
            "status": code,
            "source": source,
            "reason": reason,
            "requires_policy": requires_policy,
            "hold": not bool(out_phones),
        }

    if status == "provisional_retain_exact_rule":
        return result(
            selected_phones,
            selected_romans,
            code="candidate_r2_exact_mandatory_rule",
            source="r2_exact_rule",
            reason="r2 variant already exactly matches the mandatory surface-rule Roman target",
        )

    if row["candidate_status"] == "surface_donor_exact_rule":
        if status == "review_rule_dictionary_conflict":
            return result(
                [*donor_phones, *dictionary_phones],
                [*donor_romans, *dictionary_romans],
                code="policy_candidate_multiple_surface_rule_dictionary_conflict",
                source="surface_donor_plus_dictionary_supported_r2",
                reason="retain both rule-exact donor and dictionary-supported r2 variants pending explicit multiple-variant policy",
                requires_policy=True,
            )
        return result(
            donor_phones,
            donor_romans,
            code="candidate_surface_donor_exact_mandatory_rule",
            source="surface_donor_exact_rule",
            reason="same target surface has an exact-rule phone donor",
        )

    if status == "candidate_dictionary_supported_exception":
        return result(
            dictionary_phones,
            dictionary_romans,
            code="candidate_r2_dictionary_supported_exception",
            source="r2_variant_dictionary_attested",
            reason="r2 differs from the plain rule target but matches an independently recorded dictionary pronunciation",
        )

    if status == "review_no_surface_rule_mismatch":
        if relation_phones:
            return result(
                relation_phones,
                relation_romans,
                code="candidate_r2_model_unitization_equivalent_no_rule_change",
                source="r2_model_unitization_relation",
                reason="r2 differs only by the frozen technical model-unitization relation and no surface rule changed",
            )
        return result(
            [],
            [],
            code="hold_no_surface_rule_substantive_mismatch",
            source="zero_fallback_hold",
            reason="r2 differs substantively from the plain rule target without independent dictionary agreement",
        )

    if projection is None:
        return result(
            [], [], code="hold_missing_projection_link", source="zero_fallback_hold",
            reason="rule-sensitive source has no audited projection row",
        )
    projection_count = int(projection["target_projection_candidate_count"])
    if projection_count == 0:
        return result(
            [], [], code="hold_target_projection_unresolved", source="zero_fallback_hold",
            reason=f"audited target projection remains unresolved: {projection['target_projection_status']}",
        )
    gate = projection["source_projection_gate_class"]
    if gate == "candidate_projection_dictionary_agree":
        return result(
            projection_phones,
            projection_romans,
            code="candidate_rule_projection_dictionary_agree",
            source="audited_exact_context_projection_plus_dictionary",
            reason="mandatory rule target, audited phone projection, and dictionary evidence agree",
        )
    if gate == "hold_projection_no_independent_dictionary":
        return result(
            projection_phones,
            projection_romans,
            code="candidate_rule_projection_mandatory_rule_no_conflict",
            source="audited_exact_context_projection",
            reason="mandatory within-eojeol rule has an audited projection and no conflicting dictionary evidence",
        )
    if gate == "hold_projection_dictionary_conflict":
        return result(
            [*projection_phones, *dictionary_phones],
            [*projection_romans, *dictionary_romans],
            code="policy_candidate_multiple_rule_dictionary_conflict",
            source="audited_projection_plus_dictionary_supported_r2",
            reason="retain both mandatory-rule and dictionary-supported variants pending explicit multiple-variant policy",
            requires_policy=True,
        )
    raise RuntimeError(f"unexpected projection gate: {row['token']} {gate}")


def build_readiness(
    *, donor_manifest_path: Path, projection_manifest_path: Path, policy_path: Path, output_root: Path
) -> dict[str, object]:
    if output_root.exists():
        manifest_path = output_root / "SELECTION_READINESS_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_planning_not_selected":
            raise RuntimeError("existing readiness output is not reusable")
        for key, path in (("donor_manifest", donor_manifest_path), ("projection_manifest", projection_manifest_path), ("policy_contract", policy_path)):
            verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
        verify_fingerprint(manifest["outputs"]["selection_readiness"], Path(manifest["outputs"]["selection_readiness"]["path"]), label="existing readiness")
        return manifest

    donor_manifest = json.loads(donor_manifest_path.read_text(encoding="utf-8-sig"))
    projection_manifest = json.loads(projection_manifest_path.read_text(encoding="utf-8-sig"))
    policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    if donor_manifest.get("schema_version") != DONOR_SCHEMA or donor_manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("donor manifest differs")
    if projection_manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("projection manifest differs")
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "planning_candidates_only":
        raise RuntimeError("readiness policy differs")
    if tuple(str(year) for year in policy.get("scope_years", [])) != YEARS:
        raise RuntimeError("readiness policy years differ")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("readiness policy exceeds planning scope")

    donor_path = Path(donor_manifest["outputs"]["candidate_inventory"]["path"]).resolve()
    projection_path = Path(projection_manifest["outputs"]["source_projection_candidates"]["path"]).resolve()
    acoustic_path = Path(projection_manifest["inputs"]["acoustic_model"]["path"]).resolve()
    verify_fingerprint(donor_manifest["outputs"]["candidate_inventory"], donor_path, label="donor inventory")
    verify_fingerprint(projection_manifest["outputs"]["source_projection_candidates"], projection_path, label="projection source")
    verify_fingerprint(projection_manifest["inputs"]["acoustic_model"], acoustic_path, label="acoustic model")
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_path))
    inventory = set(group_lookup)
    allowed_rules = set(policy["mandatory_surface_rules"])

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True)
    temp_output = temp_root / "common_pron_r3_selection_readiness.csv.gz"
    temp_manifest = temp_root / "SELECTION_READINESS_MANIFEST.json"
    final_output = output_root / temp_output.name

    status_counts: Counter[str] = Counter()
    status_occurrences: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    candidate_types = candidate_occurrences = policy_types = policy_occurrences = hold_types = hold_occurrences = 0
    row_count = projection_links = 0
    with gzip.open(donor_path, "rt", encoding="utf-8-sig", newline="") as donor_stream, gzip.open(projection_path, "rt", encoding="utf-8-sig", newline="") as projection_stream, gzip_writer(temp_output) as target:
        donor_reader = csv.DictReader(donor_stream)
        projection_reader = csv.DictReader(projection_stream)
        if tuple(donor_reader.fieldnames or ()) != DONOR_FIELDS or tuple(projection_reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS:
            raise RuntimeError("readiness input column contract differs")
        projection = next(projection_reader, None)
        writer = csv.DictWriter(target, fieldnames=READINESS_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in donor_reader:
            token = row["token"]
            while projection is not None and projection["token"] < token:
                raise RuntimeError(f"projection token outside donor inventory order: {projection['token']}")
            linked = projection if projection is not None and projection["token"] == token else None
            if linked is not None:
                if (
                    any(linked[field] != row[field] for field in LINK_FIELDS)
                    or linked["original_selection_status"] != row["selection_status"]
                    or linked["original_selection_reason"] != row["selection_reason"]
                ):
                    raise RuntimeError(f"projection/donor link differs: {token}")
                projection_links += 1
                projection = next(projection_reader, None)
            rules = [value for value in row["surface_rule_names"].split("|") if value]
            if any(value not in allowed_rules for value in rules):
                raise RuntimeError(f"non-mandatory rule entered readiness: {token} {rules}")
            for rule in rules:
                rule_counts[rule] += 1
            relation_phones, relation_romans, relation_classes = r2_relation_variants(row, group_lookup)
            decision = planning_decision(row, linked, relation_phones, relation_romans)
            phones = list(decision["phones"])
            romans = list(decision["romans"])
            if any(phone not in inventory for value in phones for phone in value.split()):
                raise RuntimeError(f"planning phone outside inventory: {token}")
            count = len(phones)
            total = int(row["total_occurrences"])
            if decision["requires_policy"]:
                policy_types += 1
                policy_occurrences += total
            elif count:
                candidate_types += 1
                candidate_occurrences += total
            else:
                hold_types += 1
                hold_occurrences += total
            status_counts[str(decision["status"])] += 1
            status_occurrences[str(decision["status"])] += total
            projection_phones, projection_romans = projection_values(linked)
            writer.writerow(
                {
                    **row,
                    "r2_model_relation_variant_count": len(relation_phones),
                    "r2_model_relation_phones_json": json.dumps(relation_phones, ensure_ascii=False),
                    "r2_model_relation_roman_json": json.dumps(relation_romans, ensure_ascii=False),
                    "r2_model_relation_classes_json": json.dumps(relation_classes, ensure_ascii=False),
                    "projection_linked": str(linked is not None).lower(),
                    "target_projection_status": linked["target_projection_status"] if linked else "",
                    "target_representation_relation": linked["target_representation_relation"] if linked else "",
                    "source_projection_gate_class": linked["source_projection_gate_class"] if linked else "",
                    "projection_candidate_count": len(projection_phones),
                    "projection_candidate_phones_json": json.dumps(projection_phones, ensure_ascii=False),
                    "projection_candidate_roman_json": json.dumps(projection_romans, ensure_ascii=False),
                    "planning_candidate_variant_count": count,
                    "planning_candidate_phones_json": json.dumps(phones, ensure_ascii=False),
                    "planning_candidate_roman_json": json.dumps(romans, ensure_ascii=False),
                    "planning_status": decision["status"],
                    "planning_source": decision["source"],
                    "planning_reason": decision["reason"],
                    "planning_requires_policy_decision": str(decision["requires_policy"]).lower(),
                    "planning_zero_fallback_hold": str(decision["hold"]).lower(),
                    "planning_is_final_selection": "false",
                }
            )
            row_count += 1
    if projection is not None:
        raise RuntimeError("unconsumed projection rows")
    if row_count != int(donor_manifest["coverage"]["total_types"]):
        raise RuntimeError("readiness canonical coverage differs")
    if projection_links != int(projection_manifest["counts"]["source_rows"]):
        raise RuntimeError("readiness projection coverage differs")

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_planning_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "planning_candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "donor_manifest": file_fingerprint(donor_manifest_path, with_sha256=True),
            "projection_manifest": file_fingerprint(projection_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "donor_inventory": file_fingerprint(donor_path, with_sha256=True),
            "projection_source": file_fingerprint(projection_path, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_path, with_sha256=True),
        },
        "counts": {
            "canonical_types": row_count,
            "projection_linked_types": projection_links,
            "candidate_ready_types": candidate_types,
            "candidate_ready_occurrences": candidate_occurrences,
            "policy_decision_types": policy_types,
            "policy_decision_occurrences": policy_occurrences,
            "zero_fallback_hold_types": hold_types,
            "zero_fallback_hold_occurrences": hold_occurrences,
            "planning_status_types": dict(sorted(status_counts.items())),
            "planning_status_occurrences": dict(sorted(status_occurrences.items())),
            "mandatory_rule_types": dict(sorted(rule_counts.items())),
        },
        "outputs": {
            "selection_readiness": fingerprint_for_final(temp_output, final_output)
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_manifest, manifest)
    os.replace(temp_root, output_root)
    return manifest


def recover_complete_partial(
    *,
    donor_manifest_path: Path,
    projection_manifest_path: Path,
    policy_path: Path,
    partial_root: Path,
    output_root: Path,
) -> dict[str, object]:
    """Validate a complete gzip left by the historical post-close check bug."""

    if output_root.exists():
        raise RuntimeError("recovery output root already exists")
    if (
        not partial_root.is_dir()
        or partial_root.parent.resolve() != output_root.parent.resolve()
        or not partial_root.name.endswith(".partial")
    ):
        raise RuntimeError("recovery partial root contract differs")
    partial_output = partial_root / "common_pron_r3_selection_readiness.csv.gz"
    partial_manifest = partial_root / "SELECTION_READINESS_MANIFEST.json"
    if not partial_output.is_file() or partial_manifest.exists():
        raise RuntimeError("recovery requires one completed gzip and no manifest")

    donor_manifest = json.loads(donor_manifest_path.read_text(encoding="utf-8-sig"))
    projection_manifest = json.loads(projection_manifest_path.read_text(encoding="utf-8-sig"))
    policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    if donor_manifest.get("schema_version") != DONOR_SCHEMA or donor_manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("recovery donor manifest differs")
    if projection_manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("recovery projection manifest differs")
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "planning_candidates_only":
        raise RuntimeError("recovery policy differs")
    if tuple(str(year) for year in policy.get("scope_years", [])) != YEARS:
        raise RuntimeError("recovery policy years differ")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("recovery policy exceeds planning scope")

    donor_path = Path(donor_manifest["outputs"]["candidate_inventory"]["path"]).resolve()
    projection_path = Path(projection_manifest["outputs"]["source_projection_candidates"]["path"]).resolve()
    acoustic_path = Path(projection_manifest["inputs"]["acoustic_model"]["path"]).resolve()
    verify_fingerprint(donor_manifest["outputs"]["candidate_inventory"], donor_path, label="recovery donor inventory")
    verify_fingerprint(projection_manifest["outputs"]["source_projection_candidates"], projection_path, label="recovery projection source")
    verify_fingerprint(projection_manifest["inputs"]["acoustic_model"], acoustic_path, label="recovery acoustic model")
    inventory = set(model_group_lookup(load_acoustic_meta(acoustic_path)))
    allowed_rules = set(policy["mandatory_surface_rules"])

    status_counts: Counter[str] = Counter()
    status_occurrences: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    candidate_types = candidate_occurrences = policy_types = policy_occurrences = hold_types = hold_occurrences = 0
    row_count = projection_links = 0
    with gzip.open(donor_path, "rt", encoding="utf-8-sig", newline="") as donor_stream, gzip.open(projection_path, "rt", encoding="utf-8-sig", newline="") as projection_stream, gzip.open(partial_output, "rt", encoding="utf-8-sig", newline="") as output_stream:
        donor_reader = csv.DictReader(donor_stream)
        projection_reader = csv.DictReader(projection_stream)
        output_reader = csv.DictReader(output_stream)
        if (
            tuple(donor_reader.fieldnames or ()) != DONOR_FIELDS
            or tuple(projection_reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS
            or tuple(output_reader.fieldnames or ()) != READINESS_FIELDS
        ):
            raise RuntimeError("recovery column contract differs")
        projection = next(projection_reader, None)
        for base, row in itertools.zip_longest(donor_reader, output_reader):
            if base is None or row is None:
                raise RuntimeError("recovery row coverage differs")
            token = base["token"]
            if any(row[field] != base[field] for field in DONOR_FIELDS):
                raise RuntimeError(f"recovery base row differs: {token}")
            linked = projection if projection is not None and projection["token"] == token else None
            if projection is not None and projection["token"] < token:
                raise RuntimeError(f"recovery projection order differs: {projection['token']}")
            if (row["projection_linked"] == "true") != (linked is not None):
                raise RuntimeError(f"recovery projection marker differs: {token}")
            if linked is not None:
                if (
                    any(linked[field] != base[field] for field in LINK_FIELDS)
                    or linked["original_selection_status"] != base["selection_status"]
                    or linked["original_selection_reason"] != base["selection_reason"]
                    or row["target_projection_status"] != linked["target_projection_status"]
                    or row["target_representation_relation"] != linked["target_representation_relation"]
                    or row["source_projection_gate_class"] != linked["source_projection_gate_class"]
                    or row["projection_candidate_phones_json"] != linked["projected_pron_phones_json"]
                    or row["projection_candidate_roman_json"] != linked["projected_pron_roman_json"]
                ):
                    raise RuntimeError(f"recovery projection link differs: {token}")
                projection_links += 1
                projection = next(projection_reader, None)
            rules = [value for value in row["surface_rule_names"].split("|") if value]
            if any(value not in allowed_rules for value in rules):
                raise RuntimeError(f"recovery non-mandatory rule: {token}")
            for rule in rules:
                rule_counts[rule] += 1
            relation_phones = string_list(row["r2_model_relation_phones_json"], label=f"recovery relation phones {token}")
            relation_romans = string_list(row["r2_model_relation_roman_json"], label=f"recovery relation Roman {token}")
            relation_classes = string_list(row["r2_model_relation_classes_json"], label=f"recovery relation class {token}")
            projection_phones = string_list(row["projection_candidate_phones_json"], label=f"recovery projection phones {token}")
            projection_romans = string_list(row["projection_candidate_roman_json"], label=f"recovery projection Roman {token}")
            planning_phones = string_list(row["planning_candidate_phones_json"], label=f"recovery planning phones {token}")
            planning_romans = string_list(row["planning_candidate_roman_json"], label=f"recovery planning Roman {token}")
            if (
                len(relation_phones) != len(relation_romans)
                or len(relation_phones) != len(relation_classes)
                or len(relation_phones) != int(row["r2_model_relation_variant_count"])
                or len(projection_phones) != len(projection_romans)
                or len(projection_phones) != int(row["projection_candidate_count"])
                or len(planning_phones) != len(planning_romans)
                or len(planning_phones) != int(row["planning_candidate_variant_count"])
                or row["planning_is_final_selection"] != "false"
                or (row["planning_zero_fallback_hold"] == "true") != (not planning_phones)
                or any(phone not in inventory for value in planning_phones for phone in value.split())
            ):
                raise RuntimeError(f"recovery planning structure differs: {token}")
            total = int(row["total_occurrences"])
            if row["planning_requires_policy_decision"] == "true":
                policy_types += 1
                policy_occurrences += total
            elif planning_phones:
                candidate_types += 1
                candidate_occurrences += total
            else:
                hold_types += 1
                hold_occurrences += total
            status_counts[row["planning_status"]] += 1
            status_occurrences[row["planning_status"]] += total
            row_count += 1
        if projection is not None:
            raise RuntimeError("recovery unconsumed projection rows")

    if row_count != int(donor_manifest["coverage"]["total_types"]):
        raise RuntimeError("recovery canonical coverage differs")
    if projection_links != int(projection_manifest["counts"]["source_rows"]):
        raise RuntimeError("recovery projection coverage differs")
    final_output = output_root / partial_output.name
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_planning_not_selected",
        "recorded_at": now_iso(),
        "recovery": {
            "performed": True,
            "reason": "complete gzip survived historical post-close iterator check failure",
            "full_recomputation_avoided": True,
        },
        "scope": {
            "planning_candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "donor_manifest": file_fingerprint(donor_manifest_path, with_sha256=True),
            "projection_manifest": file_fingerprint(projection_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "donor_inventory": file_fingerprint(donor_path, with_sha256=True),
            "projection_source": file_fingerprint(projection_path, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_path, with_sha256=True),
        },
        "counts": {
            "canonical_types": row_count,
            "projection_linked_types": projection_links,
            "candidate_ready_types": candidate_types,
            "candidate_ready_occurrences": candidate_occurrences,
            "policy_decision_types": policy_types,
            "policy_decision_occurrences": policy_occurrences,
            "zero_fallback_hold_types": hold_types,
            "zero_fallback_hold_occurrences": hold_occurrences,
            "planning_status_types": dict(sorted(status_counts.items())),
            "planning_status_occurrences": dict(sorted(status_occurrences.items())),
            "mandatory_rule_types": dict(sorted(rule_counts.items())),
        },
        "outputs": {
            "selection_readiness": fingerprint_for_final(partial_output, final_output)
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(partial_manifest, manifest)
    os.replace(partial_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--donor-manifest", type=Path, required=True)
    result.add_argument("--projection-manifest", type=Path, required=True)
    result.add_argument("--policy-contract", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    result.add_argument("--recover-partial-root", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    common = {
        "donor_manifest_path": args.donor_manifest.resolve(),
        "projection_manifest_path": args.projection_manifest.resolve(),
        "policy_path": args.policy_contract.resolve(),
        "output_root": args.output_root.resolve(),
    }
    if args.recover_partial_root:
        manifest = recover_complete_partial(
            **common,
            partial_root=args.recover_partial_root.resolve(),
        )
    else:
        manifest = build_readiness(**common)
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
