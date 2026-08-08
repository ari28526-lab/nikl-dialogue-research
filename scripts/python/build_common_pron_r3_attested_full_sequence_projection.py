"""Audit full model-phone projections for attested dictionary/rule exact holds."""

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
from typing import Iterator, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_contextual_dictionary_donor_audit import (  # noqa: E402
    CLASS_CONFLICT,
    CLASS_MULTIPLE,
    CLASS_NONE,
    CLASS_UNANIMOUS,
    DIRECT_FROZEN_LEVELS,
    INVENTORY_FIELDS,
    Mapping,
    Observation,
    build_canonical_index,
    choose_evidence,
    context_keys,
)
from build_common_pron_r3_morph_context_evidence import (  # noqa: E402
    SCHEMA_VERSION as STAGE16_SCHEMA,
    STATUS as STAGE16_STATUS,
    TOKEN_FIELDS as MORPH_COVERAGE_FIELDS,
)
from build_common_pron_r3_selection_readiness_v2 import (  # noqa: E402
    SCHEMA_VERSION as READINESS_V2_SCHEMA,
)
from build_common_pron_r3_selection_readiness_v3 import (  # noqa: E402
    OUTPUT_FIELDS as READINESS_V3_FIELDS,
    SCHEMA_VERSION as READINESS_V3_SCHEMA,
)
from build_common_pron_r3_unanimous_phone_change_audit import (  # noqa: E402
    SCHEMA_VERSION as STAGE15_SCHEMA,
    STATUS as STAGE15_STATUS,
    TOKEN_AUDIT_FIELDS as STAGE15_FIELDS,
)
from phoneme_roman import (  # noqa: E402
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
SCHEMA_VERSION = "common_pron_r3_attested_full_sequence_projection.v1"
POLICY_SCHEMA = "common_pron_r3_attested_full_sequence_projection_policy.v1"
STATUS = "success_candidate_plan_not_selected"
ATTESTED_MARKERS = {"NIKL_lexicon_full_v2:pron_1", "NIKL_lexicon_full_v2:pron_2"}
LEGACY_MARKER = "NIKL_lexicon_full_legacy:pron_g2p"
CANONICAL_LEVELS = ("window2_boundary", "window1_boundary", "unit_boundary")
CANONICAL_THRESHOLDS = {level: 2 for level in CANONICAL_LEVELS}
FROZEN_THRESHOLDS = {
    "word_exact": 1,
    "syllable_signature": 2,
    "window2_boundary": 2,
    "window1_boundary": 2,
}

OUTPUT_FIELDS = (
    "token",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
    "primary_audit_route",
    "rule_pron_hangul",
    "rule_pron_roman",
    "dictionary_pron_hangul_json",
    "dictionary_pron_roman_json",
    "dictionary_source_refs_json",
    "dictionary_evidence_class",
    "morph_link_status",
    "morph_context_status",
    "top_morph_analysis",
    "r2_pron_phones_json",
    "rule_unit_count",
    "unit_evidence_json",
    "complete_unanimous_unit_count",
    "full_sequence_projection_status",
    "planning_candidate_variant_count",
    "planning_candidate_phones_json",
    "planning_candidate_roman_json",
    "planning_candidate_role",
    "planning_status",
    "planning_reason",
    "automatic_candidate_eligible",
    "partial_phone_edit_performed",
    "canonical_selection_performed",
    "adoption_performed",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
)

SUMMARY_FIELDS = (
    "dictionary_evidence_class",
    "full_sequence_projection_status",
    "type_count",
    "occurrence_count",
    "example_tokens_json",
    "automatic_candidate_eligible",
)

csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], path: Path, *, label: str) -> None:
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
        or policy.get("status") != "read_only_candidate_planning"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
    ):
        raise RuntimeError("Stage 17 policy identity differs")
    contract = policy.get("input_contract", {})
    expected = {
        "expected_stage15_types": 4453,
        "expected_stage15_occurrences": 72030,
        "expected_dictionary_rule_exact_types": 141,
        "expected_attested_pron_1_or_2_exact_types": 65,
        "expected_legacy_machine_only_exact_types": 76,
    }
    if any(int(contract.get(key, -1)) != value for key, value in expected.items()):
        raise RuntimeError("Stage 17 input contract differs")
    if any(value is not True for value in policy.get("evidence_policy", {}).values()):
        raise RuntimeError("Stage 17 evidence policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("Stage 17 policy exceeds planning scope")
    return policy


def freeze(value: object) -> object:
    if isinstance(value, list):
        return tuple(freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), freeze(item)) for key, item in value.items()))
    return value


def build_frozen_direct_index(path: Path) -> dict[str, dict[tuple[object, ...], Observation]]:
    index: dict[str, dict[tuple[object, ...], Observation]] = defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != INVENTORY_FIELDS:
            raise RuntimeError("Stage 13 frozen inventory columns differ")
        for row in reader:
            if row["mapping_status"] != "complete_contextual_mapping":
                continue
            token = row["token"]
            for mapping in json.loads(row["contextual_mappings_json"] or "[]"):
                if mapping.get("relation_kind") != "direct_unit":
                    continue
                phone = clean(mapping.get("phone"))
                for level, raw_key in mapping.get("contexts", {}).items():
                    if level not in DIRECT_FROZEN_LEVELS:
                        continue
                    key = freeze(raw_key)
                    if not isinstance(key, tuple):
                        raise RuntimeError(f"invalid frozen context key: {token}")
                    observation = index[level].setdefault(key, Observation())
                    observation.phone_counts[phone] += 1
                    observation.token_types.add(token)
                    observation.variant_rows += 1
                    if token not in observation.examples and len(observation.examples) < 8:
                        observation.examples.append(token)
    return index


def dictionary_evidence_class(row: dict[str, str]) -> str:
    variants = set(json.loads(row["dictionary_pron_roman_json"] or "[]"))
    if row["rule_pron_roman"] not in variants:
        return "no_dictionary_rule_exact"
    refs = set(json.loads(row["dictionary_source_refs_json"] or "[]"))
    if refs & ATTESTED_MARKERS:
        return "attested_pron_1_or_2_rule_exact"
    if refs == {LEGACY_MARKER}:
        return "legacy_machine_only_rule_exact"
    return "other_nonattested_rule_exact"


def empty_mapping(index: int) -> Mapping:
    return Mapping(
        relation_kind="direct_unit",
        rule_indices=(index,),
        phone="",
        phone_display="",
        phone_key="",
        phone_model_group="",
        secondary_articulation="",
    )


def unit_projection(
    *, token: str, rule: Sequence[object], unit_index: int,
    canonical_index: dict[str, dict[tuple[object, ...], Observation]],
    frozen_index: dict[str, dict[tuple[object, ...], Observation]],
    group_lookup: dict[str, int],
) -> tuple[dict[str, object], str | None]:
    mapping = empty_mapping(unit_index)
    keys = context_keys(token=token, rule=rule, mapping=mapping)
    canonical = choose_evidence(
        canonical_index,
        keys=keys,
        levels=CANONICAL_LEVELS,
        thresholds=CANONICAL_THRESHOLDS,
    )
    frozen = choose_evidence(
        frozen_index,
        keys=keys,
        levels=DIRECT_FROZEN_LEVELS,
        thresholds=FROZEN_THRESHOLDS,
    )
    canonical_set = set(canonical.phone_counts if canonical else ())
    frozen_set = set(frozen.phone_counts if frozen else ())
    if not canonical_set and not frozen_set:
        evidence_class = CLASS_NONE
    elif canonical_set and frozen_set and canonical_set.isdisjoint(frozen_set):
        evidence_class = CLASS_CONFLICT
    elif len(canonical_set | frozen_set) == 1:
        evidence_class = CLASS_UNANIMOUS
    else:
        evidence_class = CLASS_MULTIPLE
    donor = next(iter(canonical_set | frozen_set)) if evidence_class == CLASS_UNANIMOUS else None
    if donor is not None:
        phone = classify_phone(donor, group_lookup)
        if phone.comparison_key != rule[unit_index].comparison_key:
            raise RuntimeError(f"projected phone relation differs: {token} unit={unit_index}")
    record = {
        "unit_index": unit_index,
        "rule_unit": rule[unit_index].display,
        "canonical_level": canonical.level if canonical else "",
        "canonical_phone_counts": canonical.phone_counts if canonical else {},
        "canonical_token_type_count": canonical.token_type_count if canonical else 0,
        "frozen_level": frozen.level if frozen else "",
        "frozen_phone_counts": frozen.phone_counts if frozen else {},
        "frozen_token_type_count": frozen.token_type_count if frozen else 0,
        "evidence_class": evidence_class,
        "projected_phone": donor or "",
    }
    return record, donor


def load_unique_rows(path: Path, fields: tuple[str, ...], *, label: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise RuntimeError(f"{label} columns differ")
        for row in reader:
            token = row["token"]
            if token in rows:
                raise RuntimeError(f"duplicate {label} token: {token}")
            rows[token] = row
    return rows


def verify_existing(
    output_root: Path, *, stage13_manifest_path: Path, stage14_manifest_path: Path,
    stage15_manifest_path: Path, stage16_manifest_path: Path, policy_path: Path,
) -> dict[str, object]:
    manifest_path = output_root / "ATTESTED_FULL_SEQUENCE_PROJECTION_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Stage 17 root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RuntimeError("existing Stage 17 identity differs")
    for key, path in (
        ("stage13_manifest", stage13_manifest_path),
        ("stage14_manifest", stage14_manifest_path),
        ("stage15_manifest", stage15_manifest_path),
        ("stage16_manifest", stage16_manifest_path),
        ("policy_contract", policy_path),
    ):
        verify(manifest["inputs"][key], path, label=f"existing {key}")
    for key in ("projection_inventory", "projection_summary"):
        record = manifest["outputs"][key]
        verify(record, Path(str(record["path"])), label=f"existing {key}")
    return manifest


def build_projection(
    *, stage13_manifest_path: Path, stage14_manifest_path: Path,
    stage15_manifest_path: Path, stage16_manifest_path: Path,
    policy_path: Path, output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            stage13_manifest_path=stage13_manifest_path,
            stage14_manifest_path=stage14_manifest_path,
            stage15_manifest_path=stage15_manifest_path,
            stage16_manifest_path=stage16_manifest_path,
            policy_path=policy_path,
        )
    policy = validate_policy(policy_path)
    stage13 = json.loads(stage13_manifest_path.read_text(encoding="utf-8-sig"))
    stage14 = json.loads(stage14_manifest_path.read_text(encoding="utf-8-sig"))
    stage15 = json.loads(stage15_manifest_path.read_text(encoding="utf-8-sig"))
    stage16 = json.loads(stage16_manifest_path.read_text(encoding="utf-8-sig"))
    if stage14.get("schema_version") != READINESS_V3_SCHEMA:
        raise RuntimeError("Stage 14 identity differs")
    if stage15.get("schema_version") != STAGE15_SCHEMA or stage15.get("status") != STAGE15_STATUS:
        raise RuntimeError("Stage 15 identity differs")
    if stage16.get("schema_version") != STAGE16_SCHEMA or stage16.get("status") != STAGE16_STATUS:
        raise RuntimeError("Stage 16 identity differs")
    readiness_v2_manifest_path = Path(str(stage13["inputs"]["readiness_v2_manifest"]["path"])).resolve()
    readiness_v2_manifest = json.loads(readiness_v2_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness_v2_manifest.get("schema_version") != READINESS_V2_SCHEMA:
        raise RuntimeError("readiness v2 identity differs")
    readiness_v2_path = Path(str(stage13["inputs"]["readiness_v2"]["path"])).resolve()
    frozen_inventory_path = Path(str(stage13["outputs"]["frozen_dictionary_contextual_inventory"]["path"])).resolve()
    acoustic_model = Path(str(stage13["inputs"]["acoustic_model"]["path"])).resolve()
    readiness_v3_path = Path(str(stage14["outputs"]["selection_readiness_v3"]["path"])).resolve()
    stage15_path = Path(str(stage15["outputs"]["token_inventory"]["path"])).resolve()
    morph_path = Path(str(stage16["outputs"]["token_evidence_coverage"]["path"])).resolve()
    for record, path, label in (
        (stage13["inputs"]["readiness_v2_manifest"], readiness_v2_manifest_path, "readiness v2 manifest"),
        (stage13["inputs"]["readiness_v2"], readiness_v2_path, "readiness v2"),
        (stage13["outputs"]["frozen_dictionary_contextual_inventory"], frozen_inventory_path, "frozen inventory"),
        (stage13["inputs"]["acoustic_model"], acoustic_model, "acoustic model"),
        (stage14["outputs"]["selection_readiness_v3"], readiness_v3_path, "readiness v3"),
        (stage15["outputs"]["token_inventory"], stage15_path, "Stage 15 token inventory"),
        (stage16["outputs"]["token_evidence_coverage"], morph_path, "Stage 16 morphology coverage"),
    ):
        verify(record, path, label=label)

    stage15_rows = load_unique_rows(stage15_path, STAGE15_FIELDS, label="Stage 15")
    morph_rows = load_unique_rows(morph_path, MORPH_COVERAGE_FIELDS, label="Stage 16")
    if len(stage15_rows) != int(policy["input_contract"]["expected_stage15_types"]):
        raise RuntimeError("Stage 15 target count differs")
    if sum(int(row["total_occurrences"]) for row in stage15_rows.values()) != int(
        policy["input_contract"]["expected_stage15_occurrences"]
    ):
        raise RuntimeError("Stage 15 occurrence count differs")

    readiness_rows: dict[str, dict[str, str]] = {}
    with gzip.open(readiness_v3_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_V3_FIELDS:
            raise RuntimeError("readiness v3 columns differ")
        for row in reader:
            if row["token"] in stage15_rows:
                readiness_rows[row["token"]] = row
    if set(readiness_rows) != set(stage15_rows) or set(morph_rows) != set(stage15_rows):
        raise RuntimeError("Stage 15/16/readiness target identity differs")

    exact_rows = {
        token: row for token, row in readiness_rows.items()
        if dictionary_evidence_class(row) != "no_dictionary_rule_exact"
    }
    evidence_counts = Counter(dictionary_evidence_class(row) for row in exact_rows.values())
    if len(exact_rows) != int(policy["input_contract"]["expected_dictionary_rule_exact_types"]):
        raise RuntimeError("dictionary-rule exact target count differs")
    if evidence_counts["attested_pron_1_or_2_rule_exact"] != int(
        policy["input_contract"]["expected_attested_pron_1_or_2_exact_types"]
    ):
        raise RuntimeError("attested dictionary exact count differs")
    if evidence_counts["legacy_machine_only_rule_exact"] != int(
        policy["input_contract"]["expected_legacy_machine_only_exact_types"]
    ):
        raise RuntimeError("legacy machine-only exact count differs")

    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))
    canonical_index, canonical_counts = build_canonical_index(readiness_v2_path, group_lookup)
    frozen_index = build_frozen_direct_index(frozen_inventory_path)

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    inventory_temp = temp_root / "attested_full_sequence_projection_inventory.csv.gz"
    summary_temp = temp_root / "attested_full_sequence_projection_summary.csv"
    inventory_final = output_root / inventory_temp.name
    summary_final = output_root / summary_temp.name
    status_types: Counter[tuple[str, str]] = Counter()
    status_occurrences: Counter[tuple[str, str]] = Counter()
    status_examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    candidate_types = candidate_occurrences = 0
    with gzip_writer(inventory_temp) as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for token in sorted(exact_rows):
            ready = exact_rows[token]
            stage15_row = stage15_rows[token]
            morph = morph_rows[token]
            evidence_class = dictionary_evidence_class(ready)
            rule = tuple(expand_roman_eojeol(ready["rule_pron_roman"]))
            unit_records: list[dict[str, object]] = []
            donors: list[str] = []
            if evidence_class == "attested_pron_1_or_2_rule_exact":
                for unit_index in range(len(rule)):
                    record, donor = unit_projection(
                        token=token,
                        rule=rule,
                        unit_index=unit_index,
                        canonical_index=canonical_index,
                        frozen_index=frozen_index,
                        group_lookup=group_lookup,
                    )
                    unit_records.append(record)
                    if donor is not None:
                        donors.append(donor)
                complete = len(donors) == len(rule)
                if complete:
                    projection_status = "complete_unanimous_full_sequence"
                    planning_status = "candidate_attested_rule_exact_full_context_projection"
                    reason = "attested pron_1/2 agrees with rule Roman and every rule unit has one compatible contextual model phone"
                    candidate_phones = [" ".join(donors)]
                    candidate_roman = [ready["rule_pron_roman"]]
                    eligible = True
                    candidate_types += 1
                    candidate_occurrences += int(ready["total_occurrences"])
                else:
                    projection_status = "incomplete_or_conflicting_full_sequence"
                    planning_status = "hold_attested_exact_full_sequence_unresolved"
                    reason = "attested rule target exists but at least one rule unit lacks a single compatible contextual model phone"
                    candidate_phones = []
                    candidate_roman = []
                    eligible = False
            else:
                projection_status = "excluded_nonattested_legacy_machine_evidence"
                planning_status = "hold_legacy_machine_not_attested"
                reason = "legacy pron_g2p is machine-generated fallback, not attested dictionary pronunciation"
                candidate_phones = []
                candidate_roman = []
                eligible = False
            key = (evidence_class, projection_status)
            status_types[key] += 1
            status_occurrences[key] += int(ready["total_occurrences"])
            if len(status_examples[key]) < 12:
                status_examples[key].append(token)
            writer.writerow(
                {
                    "token": token,
                    "total_occurrences": ready["total_occurrences"],
                    "n_years_present": ready["n_years_present"],
                    **{f"count_{year}": ready[f"count_{year}"] for year in YEARS},
                    "primary_audit_route": stage15_row["primary_audit_route"],
                    "rule_pron_hangul": ready["rule_pron_hangul"],
                    "rule_pron_roman": ready["rule_pron_roman"],
                    "dictionary_pron_hangul_json": ready["dictionary_pron_hangul_json"],
                    "dictionary_pron_roman_json": ready["dictionary_pron_roman_json"],
                    "dictionary_source_refs_json": ready["dictionary_source_refs_json"],
                    "dictionary_evidence_class": evidence_class,
                    "morph_link_status": morph["morph_link_status"],
                    "morph_context_status": morph["morph_context_status"],
                    "top_morph_analysis": morph["top_morph_analysis"],
                    "r2_pron_phones_json": ready["r2_pron_phones_json"],
                    "rule_unit_count": len(rule),
                    "unit_evidence_json": json.dumps(unit_records, ensure_ascii=False),
                    "complete_unanimous_unit_count": len(donors),
                    "full_sequence_projection_status": projection_status,
                    "planning_candidate_variant_count": len(candidate_phones),
                    "planning_candidate_phones_json": json.dumps(candidate_phones, ensure_ascii=False),
                    "planning_candidate_roman_json": json.dumps(candidate_roman, ensure_ascii=False),
                    "planning_candidate_role": "alignment_lexicon_candidate_only" if eligible else "",
                    "planning_status": planning_status,
                    "planning_reason": reason,
                    "automatic_candidate_eligible": str(eligible).lower(),
                    "partial_phone_edit_performed": "false",
                    "canonical_selection_performed": "false",
                    "adoption_performed": "false",
                    "standard_pronunciation_claimed": "false",
                    "actual_realization_claimed": "false",
                }
            )

    with summary_temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for key in sorted(status_types):
            evidence_class, projection_status = key
            writer.writerow(
                {
                    "dictionary_evidence_class": evidence_class,
                    "full_sequence_projection_status": projection_status,
                    "type_count": status_types[key],
                    "occurrence_count": status_occurrences[key],
                    "example_tokens_json": json.dumps(status_examples[key], ensure_ascii=False),
                    "automatic_candidate_eligible": str(
                        projection_status == "complete_unanimous_full_sequence"
                    ).lower(),
                }
            )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "scope": {
            "candidate_role": "alignment_lexicon_candidate_only",
            "partial_phone_edit_performed": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "standard_pronunciation_claimed": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "stage13_manifest": file_fingerprint(stage13_manifest_path, with_sha256=True),
            "stage14_manifest": file_fingerprint(stage14_manifest_path, with_sha256=True),
            "stage15_manifest": file_fingerprint(stage15_manifest_path, with_sha256=True),
            "stage16_manifest": file_fingerprint(stage16_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "readiness_v2": file_fingerprint(readiness_v2_path, with_sha256=True),
            "frozen_dictionary_contextual_inventory": file_fingerprint(frozen_inventory_path, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
            "readiness_v3": file_fingerprint(readiness_v3_path, with_sha256=True),
            "stage15_token_inventory": file_fingerprint(stage15_path, with_sha256=True),
            "stage16_morph_coverage": file_fingerprint(morph_path, with_sha256=True),
        },
        "counts": {
            "stage15_types": len(stage15_rows),
            "dictionary_rule_exact_types": len(exact_rows),
            "dictionary_evidence_class_types": dict(sorted(evidence_counts.items())),
            "canonical_context_donor_types": canonical_counts["token_types"],
            "candidate_types": candidate_types,
            "candidate_occurrences": candidate_occurrences,
            "status_types": {"|".join(key): value for key, value in sorted(status_types.items())},
            "status_occurrences": {"|".join(key): value for key, value in sorted(status_occurrences.items())},
        },
        "outputs": {
            "projection_inventory": fingerprint_for_final(inventory_temp, inventory_final),
            "projection_summary": fingerprint_for_final(summary_temp, summary_final),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "ATTESTED_FULL_SEQUENCE_PROJECTION_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage13-manifest", type=Path, required=True)
    parser.add_argument("--stage14-manifest", type=Path, required=True)
    parser.add_argument("--stage15-manifest", type=Path, required=True)
    parser.add_argument("--stage16-manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "common_pron_r3_attested_full_sequence_projection_v1.json")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_projection(
        stage13_manifest_path=args.stage13_manifest.resolve(),
        stage14_manifest_path=args.stage14_manifest.resolve(),
        stage15_manifest_path=args.stage15_manifest.resolve(),
        stage16_manifest_path=args.stage16_manifest.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
