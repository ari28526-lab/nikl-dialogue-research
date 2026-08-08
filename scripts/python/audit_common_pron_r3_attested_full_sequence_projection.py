"""Independently audit Stage 17 attested full-sequence projection planning."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_r3_attested_full_sequence_projection import (  # noqa: E402
    ATTESTED_MARKERS,
    CANONICAL_LEVELS,
    CANONICAL_THRESHOLDS,
    FROZEN_THRESHOLDS,
    LEGACY_MARKER,
    OUTPUT_FIELDS,
    SCHEMA_VERSION,
    STATUS,
    SUMMARY_FIELDS,
    freeze,
)
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
from build_common_pron_r3_selection_readiness_v3 import (  # noqa: E402
    OUTPUT_FIELDS as READINESS_FIELDS,
)
from phoneme_roman import (  # noqa: E402
    classify_phone,
    expand_roman_eojeol,
    load_acoustic_meta,
    model_group_lookup,
)
from pipeline_common import atomic_write_json, now_iso, sha256_file  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCHEMA = "common_pron_r3_attested_full_sequence_projection_audit.v1"


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


def independent_dictionary_class(row: dict[str, str]) -> str:
    variants = set(json.loads(row["dictionary_pron_roman_json"] or "[]"))
    if row["rule_pron_roman"] not in variants:
        return "no_dictionary_rule_exact"
    refs = set(json.loads(row["dictionary_source_refs_json"] or "[]"))
    if refs & ATTESTED_MARKERS:
        return "attested_pron_1_or_2_rule_exact"
    if refs == {LEGACY_MARKER}:
        return "legacy_machine_only_rule_exact"
    return "other_nonattested_rule_exact"


def build_independent_frozen_index(
    path: Path,
) -> dict[str, dict[tuple[object, ...], Observation]]:
    index: dict[str, dict[tuple[object, ...], Observation]] = defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != INVENTORY_FIELDS:
            raise RuntimeError("frozen inventory columns differ")
        for row in reader:
            if row["mapping_status"] != "complete_contextual_mapping":
                continue
            for item in json.loads(row["contextual_mappings_json"] or "[]"):
                if item.get("relation_kind") != "direct_unit":
                    continue
                for level, raw_context in item.get("contexts", {}).items():
                    if level not in DIRECT_FROZEN_LEVELS:
                        continue
                    context = freeze(raw_context)
                    if not isinstance(context, tuple):
                        raise RuntimeError("non-tuple frozen context")
                    observation = index[level].setdefault(context, Observation())
                    observation.phone_counts[clean(item.get("phone"))] += 1
                    observation.token_types.add(row["token"])
                    observation.variant_rows += 1
    return index


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


def projected_phone(
    *, token: str, rule: tuple[object, ...], unit_index: int,
    canonical_index: dict[str, dict[tuple[object, ...], Observation]],
    frozen_index: dict[str, dict[tuple[object, ...], Observation]],
    group_lookup: dict[str, int],
) -> tuple[str, str]:
    keys = context_keys(token=token, rule=rule, mapping=empty_mapping(unit_index))
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
    left = set(canonical.phone_counts if canonical else ())
    right = set(frozen.phone_counts if frozen else ())
    if not left and not right:
        category = CLASS_NONE
    elif left and right and left.isdisjoint(right):
        category = CLASS_CONFLICT
    elif len(left | right) == 1:
        category = CLASS_UNANIMOUS
    else:
        category = CLASS_MULTIPLE
    if category != CLASS_UNANIMOUS:
        return category, ""
    phone_value = next(iter(left | right))
    if classify_phone(phone_value, group_lookup).comparison_key != rule[unit_index].comparison_key:
        raise RuntimeError(f"independent phone relation differs: {token} {unit_index}")
    return category, phone_value


def audit(manifest_path: Path, output_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RuntimeError("Stage 17 manifest identity differs")
    for key, record in manifest["inputs"].items():
        if "path" in record:
            verify(record, Path(str(record["path"])), label=f"input {key}")
    for key, record in manifest["outputs"].items():
        verify(record, Path(str(record["path"])), label=f"output {key}")

    readiness_path = Path(str(manifest["inputs"]["readiness_v3"]["path"])).resolve()
    inventory_path = Path(str(manifest["outputs"]["projection_inventory"]["path"])).resolve()
    summary_path = Path(str(manifest["outputs"]["projection_summary"]["path"])).resolve()
    readiness: dict[str, dict[str, str]] = {}
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness columns differ")
        for row in reader:
            category = independent_dictionary_class(row)
            if category != "no_dictionary_rule_exact" and row["token"] not in readiness:
                if (
                    row["contextual_donor_support_class"] == "unanimous_contextual_support"
                    and row["contextual_secondary_articulation_candidate_eligible"] == "false"
                    and row["planning_zero_fallback_hold"] == "true"
                ):
                    readiness[row["token"]] = row
    if len(readiness) != 141:
        raise RuntimeError("independent exact target count differs")

    rows: dict[str, dict[str, str]] = {}
    with gzip.open(inventory_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise RuntimeError("projection inventory columns differ")
        for row in reader:
            if row["token"] in rows:
                raise RuntimeError(f"duplicate projection token: {row['token']}")
            rows[row["token"]] = row
    if set(rows) != set(readiness):
        raise RuntimeError("projection target identity differs")

    group_lookup = model_group_lookup(
        load_acoustic_meta(Path(str(manifest["inputs"]["acoustic_model"]["path"])))
    )
    canonical_index, _ = build_canonical_index(
        Path(str(manifest["inputs"]["readiness_v2"]["path"])), group_lookup
    )
    frozen_index = build_independent_frozen_index(
        Path(str(manifest["inputs"]["frozen_dictionary_contextual_inventory"]["path"]))
    )
    status_types: Counter[tuple[str, str]] = Counter()
    status_occurrences: Counter[tuple[str, str]] = Counter()
    candidate_types = candidate_occurrences = 0
    for token in sorted(rows):
        source = readiness[token]
        output = rows[token]
        category = independent_dictionary_class(source)
        if output["dictionary_evidence_class"] != category:
            raise RuntimeError(f"dictionary class differs: {token}")
        if output["partial_phone_edit_performed"] != "false":
            raise RuntimeError(f"partial edit flag differs: {token}")
        if any(output[field] != "false" for field in (
            "canonical_selection_performed",
            "adoption_performed",
            "standard_pronunciation_claimed",
            "actual_realization_claimed",
        )):
            raise RuntimeError(f"nonselection invariant differs: {token}")
        if category == "attested_pron_1_or_2_rule_exact":
            rule = tuple(expand_roman_eojeol(source["rule_pron_roman"]))
            phones: list[str] = []
            unit_classes: list[str] = []
            for unit_index in range(len(rule)):
                unit_class, phone_value = projected_phone(
                    token=token,
                    rule=rule,
                    unit_index=unit_index,
                    canonical_index=canonical_index,
                    frozen_index=frozen_index,
                    group_lookup=group_lookup,
                )
                unit_classes.append(unit_class)
                if phone_value:
                    phones.append(phone_value)
            complete = len(phones) == len(rule)
            expected_status = (
                "complete_unanimous_full_sequence"
                if complete else "incomplete_or_conflicting_full_sequence"
            )
            expected_phones = [" ".join(phones)] if complete else []
            expected_eligible = complete
            reported = json.loads(output["unit_evidence_json"] or "[]")
            if [item["evidence_class"] for item in reported] != unit_classes:
                raise RuntimeError(f"unit evidence class differs: {token}")
            if json.loads(output["planning_candidate_phones_json"] or "[]") != expected_phones:
                raise RuntimeError(f"candidate sequence differs: {token}")
        else:
            expected_status = "excluded_nonattested_legacy_machine_evidence"
            expected_eligible = False
            if json.loads(output["planning_candidate_phones_json"] or "[]"):
                raise RuntimeError(f"legacy machine candidate emitted: {token}")
        if output["full_sequence_projection_status"] != expected_status:
            raise RuntimeError(f"projection status differs: {token}")
        if (output["automatic_candidate_eligible"] == "true") != expected_eligible:
            raise RuntimeError(f"candidate eligibility differs: {token}")
        key = (category, expected_status)
        status_types[key] += 1
        status_occurrences[key] += int(output["total_occurrences"])
        if expected_eligible:
            candidate_types += 1
            candidate_occurrences += int(output["total_occurrences"])

    summary_rows = list(csv.DictReader(summary_path.open("r", encoding="utf-8-sig", newline="")))
    if tuple(summary_rows[0].keys()) != SUMMARY_FIELDS:
        raise RuntimeError("projection summary columns differ")
    summary_counts = {
        (row["dictionary_evidence_class"], row["full_sequence_projection_status"]): int(row["type_count"])
        for row in summary_rows
    }
    if summary_counts != dict(status_types):
        raise RuntimeError("projection summary accounting differs")
    manifest_counts = manifest["counts"]
    if int(manifest_counts["candidate_types"]) != candidate_types or int(
        manifest_counts["candidate_occurrences"]
    ) != candidate_occurrences:
        raise RuntimeError("manifest candidate accounting differs")

    report = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_independent_candidate_plan_audit",
        "recorded_at": now_iso(),
        "manifest": {
            "path": str(manifest_path.resolve()),
            "sha256": sha256_file(manifest_path),
        },
        "counts": {
            "target_types": len(rows),
            "attested_exact_types": sum(
                key[0] == "attested_pron_1_or_2_rule_exact" for key in status_types for _ in range(status_types[key])
            ),
            "legacy_machine_only_types": sum(
                key[0] == "legacy_machine_only_rule_exact" for key in status_types for _ in range(status_types[key])
            ),
            "candidate_types": candidate_types,
            "candidate_occurrences": candidate_occurrences,
            "status_types": {"|".join(key): value for key, value in sorted(status_types.items())},
            "status_occurrences": {"|".join(key): value for key, value in sorted(status_occurrences.items())},
        },
        "invariants": manifest["scope"],
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "reports" / "AUDIT_common_pron_r3_attested_full_sequence_projection_20260808.json",
    )
    args = parser.parse_args()
    report = audit(args.manifest.resolve(), args.output.resolve())
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
