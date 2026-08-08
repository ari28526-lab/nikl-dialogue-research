"""Read-only independent audit of the full r3 selection-readiness matrix."""

from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_r3_projection_candidates import independent_relation  # noqa: E402
from audit_common_pron_rule_consistency import YEARS, phone_units, roman_units  # noqa: E402
from build_common_pron_r3_projection_candidates import SOURCE_PROJECTION_FIELDS  # noqa: E402
from build_common_pron_r3_selection_readiness import (  # noqa: E402
    DONOR_FIELDS,
    LINK_FIELDS,
    READINESS_FIELDS,
    SCHEMA_VERSION,
)
from phoneme_roman import expand_roman_eojeol, load_acoustic_meta, model_group_lookup  # noqa: E402
from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCHEMA = "common_pron_r3_selection_readiness_audit.v1"
REGRESSION_TOKENS = ("있는", "있지", "놨던", "어쨌든", "없는")
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


def verify(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")
    return path


def dedupe(phones: Sequence[str], romans: Sequence[str]) -> tuple[list[str], list[str]]:
    if len(phones) != len(romans):
        raise RuntimeError("variant count differs")
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


def dictionary_r2(row: dict[str, str]) -> tuple[list[str], list[str]]:
    keys = {
        tuple(roman_units(value)[1])
        for value in string_list(row["dictionary_pron_roman_json"], label=f"dictionary {row['token']}")
        if roman_units(value)[1]
    }
    phones = string_list(row["r2_pron_phones_json"], label=f"r2 phones {row['token']}")
    romans = string_list(row["r2_pron_roman_json"], label=f"r2 Roman {row['token']}")
    selected = [(phone, roman) for phone, roman in zip(phones, romans, strict=True) if tuple(roman_units(roman)[1]) in keys]
    return dedupe([item[0] for item in selected], [item[1] for item in selected])


def relation_r2(row: dict[str, str], group_lookup: dict[str, int]) -> tuple[list[str], list[str], list[str]]:
    phones = string_list(row["r2_pron_phones_json"], label=f"r2 phones {row['token']}")
    romans = string_list(row["r2_pron_roman_json"], label=f"r2 Roman {row['token']}")
    if len(phones) != len(romans):
        raise RuntimeError(f"r2 variant count differs: {row['token']}")
    rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
    raw: list[tuple[str, str, str]] = []
    for phone_sequence in phones:
        phone_values = tuple(clean(phone_sequence).split())
        relation, _ = independent_relation(phone_values, rule, group_lookup)
        if relation != "not_equivalent":
            displays = phone_units(phone_values, group_lookup)[0]
            raw.append((phone_sequence, " ".join(displays), relation))
    out_phones, out_romans = dedupe([item[0] for item in raw], [item[1] for item in raw])
    relation_map = {(phone, roman): relation for phone, roman, relation in raw}
    return out_phones, out_romans, [relation_map[(p, r)] for p, r in zip(out_phones, out_romans, strict=True)]


def projection_variants(linked: dict[str, str] | None) -> tuple[list[str], list[str]]:
    if linked is None:
        return [], []
    return dedupe(
        string_list(linked["projected_pron_phones_json"], label=f"projection phones {linked['token']}"),
        string_list(linked["projected_pron_roman_json"], label=f"projection Roman {linked['token']}"),
    )


def expected(
    row: dict[str, str],
    linked: dict[str, str] | None,
    relation_phones: list[str],
    relation_romans: list[str],
) -> tuple[list[str], list[str], str, str, str, bool]:
    selected = dedupe(
        string_list(row["selected_pron_phones_json"], label=f"selected phones {row['token']}"),
        string_list(row["selected_pron_roman_json"], label=f"selected Roman {row['token']}"),
    )
    donor = dedupe(
        string_list(row["candidate_pron_phones_json"], label=f"donor phones {row['token']}"),
        string_list(row["candidate_pron_roman_json"], label=f"donor Roman {row['token']}"),
    )
    dictionary = dictionary_r2(row)
    projection = projection_variants(linked)
    status = row["selection_status"]
    if status == "provisional_retain_exact_rule":
        return *selected, "candidate_r2_exact_mandatory_rule", "r2_exact_rule", "r2 variant already exactly matches the mandatory surface-rule Roman target", False
    if row["candidate_status"] == "surface_donor_exact_rule":
        if status == "review_rule_dictionary_conflict":
            phones, romans = dedupe([*donor[0], *dictionary[0]], [*donor[1], *dictionary[1]])
            return phones, romans, "policy_candidate_multiple_surface_rule_dictionary_conflict", "surface_donor_plus_dictionary_supported_r2", "retain both rule-exact donor and dictionary-supported r2 variants pending explicit multiple-variant policy", True
        return *donor, "candidate_surface_donor_exact_mandatory_rule", "surface_donor_exact_rule", "same target surface has an exact-rule phone donor", False
    if status == "candidate_dictionary_supported_exception":
        return *dictionary, "candidate_r2_dictionary_supported_exception", "r2_variant_dictionary_attested", "r2 differs from the plain rule target but matches an independently recorded dictionary pronunciation", False
    if status == "review_no_surface_rule_mismatch":
        if relation_phones:
            return relation_phones, relation_romans, "candidate_r2_model_unitization_equivalent_no_rule_change", "r2_model_unitization_relation", "r2 differs only by the frozen technical model-unitization relation and no surface rule changed", False
        return [], [], "hold_no_surface_rule_substantive_mismatch", "zero_fallback_hold", "r2 differs substantively from the plain rule target without independent dictionary agreement", False
    if linked is None:
        return [], [], "hold_missing_projection_link", "zero_fallback_hold", "rule-sensitive source has no audited projection row", False
    if int(linked["target_projection_candidate_count"]) == 0:
        return [], [], "hold_target_projection_unresolved", "zero_fallback_hold", f"audited target projection remains unresolved: {linked['target_projection_status']}", False
    gate = linked["source_projection_gate_class"]
    if gate == "candidate_projection_dictionary_agree":
        return *projection, "candidate_rule_projection_dictionary_agree", "audited_exact_context_projection_plus_dictionary", "mandatory rule target, audited phone projection, and dictionary evidence agree", False
    if gate == "hold_projection_no_independent_dictionary":
        return *projection, "candidate_rule_projection_mandatory_rule_no_conflict", "audited_exact_context_projection", "mandatory within-eojeol rule has an audited projection and no conflicting dictionary evidence", False
    if gate == "hold_projection_dictionary_conflict":
        phones, romans = dedupe([*projection[0], *dictionary[0]], [*projection[1], *dictionary[1]])
        return phones, romans, "policy_candidate_multiple_rule_dictionary_conflict", "audited_projection_plus_dictionary_supported_r2", "retain both mandatory-rule and dictionary-supported variants pending explicit multiple-variant policy", True
    raise RuntimeError(f"unexpected projection route: {row['token']} {gate}")


def audit_readiness(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("readiness manifest differs")
    scope = manifest.get("scope", {})
    if any(value is not False for value in scope.values()):
        raise RuntimeError("readiness exceeded planning-only scope")
    inputs = {key: verify(record, label=f"input {key}") for key, record in manifest["inputs"].items()}
    output = verify(manifest["outputs"]["selection_readiness"], label="readiness output")
    policy = json.loads(inputs["policy_contract"].read_text(encoding="utf-8-sig"))
    if policy.get("status") != "planning_candidates_only" or tuple(str(year) for year in policy.get("scope_years", [])) != YEARS:
        raise RuntimeError("readiness policy differs")
    allowed_rules = set(policy["mandatory_surface_rules"])
    group_lookup = model_group_lookup(load_acoustic_meta(inputs["acoustic_model"]))
    inventory = set(group_lookup)

    status_counts: Counter[str] = Counter()
    status_occurrences: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    candidate_types = candidate_occurrences = policy_types = policy_occurrences = hold_types = hold_occurrences = 0
    row_count = projection_links = 0
    regressions: dict[str, dict[str, object]] = {}
    with gzip.open(inputs["donor_inventory"], "rt", encoding="utf-8-sig", newline="") as donor_stream, gzip.open(inputs["projection_source"], "rt", encoding="utf-8-sig", newline="") as projection_stream, gzip.open(output, "rt", encoding="utf-8-sig", newline="") as output_stream:
        donor_reader = csv.DictReader(donor_stream)
        projection_reader = csv.DictReader(projection_stream)
        output_reader = csv.DictReader(output_stream)
        if tuple(donor_reader.fieldnames or ()) != DONOR_FIELDS or tuple(projection_reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS or tuple(output_reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness audit column contract differs")
        linked = next(projection_reader, None)
        for base, row in itertools.zip_longest(donor_reader, output_reader):
            if base is None or row is None:
                raise RuntimeError("readiness audit row coverage differs")
            token = base["token"]
            if any(row[field] != base[field] for field in DONOR_FIELDS):
                raise RuntimeError(f"readiness base differs: {token}")
            projection = linked if linked is not None and linked["token"] == token else None
            if linked is not None and linked["token"] < token:
                raise RuntimeError(f"projection order differs: {linked['token']}")
            if projection is not None:
                if any(projection[field] != base[field] for field in LINK_FIELDS) or projection["original_selection_status"] != base["selection_status"] or projection["original_selection_reason"] != base["selection_reason"]:
                    raise RuntimeError(f"projection base link differs: {token}")
                projection_links += 1
                linked = next(projection_reader, None)
            if row["projection_linked"] != str(projection is not None).lower():
                raise RuntimeError(f"projection marker differs: {token}")
            rules = [value for value in row["surface_rule_names"].split("|") if value]
            if any(value not in allowed_rules for value in rules):
                raise RuntimeError(f"non-mandatory rule in readiness: {token}")
            for rule in rules:
                rule_counts[rule] += 1
            relation_phones, relation_romans, relations = relation_r2(base, group_lookup)
            if (
                string_list(row["r2_model_relation_phones_json"], label=f"relation phones {token}") != relation_phones
                or string_list(row["r2_model_relation_roman_json"], label=f"relation Roman {token}") != relation_romans
                or string_list(row["r2_model_relation_classes_json"], label=f"relation class {token}") != relations
                or int(row["r2_model_relation_variant_count"]) != len(relation_phones)
            ):
                raise RuntimeError(f"r2 model relation differs: {token}")
            expected_phones, expected_romans, status, source, reason, requires_policy = expected(base, projection, relation_phones, relation_romans)
            actual_phones = string_list(row["planning_candidate_phones_json"], label=f"planning phones {token}")
            actual_romans = string_list(row["planning_candidate_roman_json"], label=f"planning Roman {token}")
            if (
                actual_phones != expected_phones
                or actual_romans != expected_romans
                or int(row["planning_candidate_variant_count"]) != len(expected_phones)
                or row["planning_status"] != status
                or row["planning_source"] != source
                or row["planning_reason"] != reason
                or row["planning_requires_policy_decision"] != str(requires_policy).lower()
                or row["planning_zero_fallback_hold"] != str(not bool(expected_phones)).lower()
                or row["planning_is_final_selection"] != "false"
                or any(phone not in inventory for value in actual_phones for phone in value.split())
            ):
                raise RuntimeError(f"planning decision differs: {token}")
            total = int(row["total_occurrences"])
            if requires_policy:
                policy_types += 1
                policy_occurrences += total
            elif expected_phones:
                candidate_types += 1
                candidate_occurrences += total
            else:
                hold_types += 1
                hold_occurrences += total
            status_counts[status] += 1
            status_occurrences[status] += total
            row_count += 1
            if token in REGRESSION_TOKENS:
                regressions[token] = {
                    "rule_pron_hangul": row["rule_pron_hangul"],
                    "surface_rule_names": row["surface_rule_names"],
                    "planning_status": status,
                    "planning_candidate_phones_json": row["planning_candidate_phones_json"],
                    "planning_zero_fallback_hold": not bool(expected_phones),
                }
        if linked is not None:
            raise RuntimeError("unconsumed projection rows")

    recomputed = {
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
    }
    if recomputed != manifest["counts"]:
        raise RuntimeError("readiness manifest counts differ")
    if set(regressions) != set(REGRESSION_TOKENS):
        raise RuntimeError("readiness regression coverage differs")
    report: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": recomputed,
        "regression_examples": regressions,
        "contracts": {
            "planning_candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "readiness_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "selection_readiness": file_fingerprint(output, with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(audit_report, report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--audit-report", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    report = audit_readiness(
        manifest_path=args.manifest.resolve(), audit_report=args.audit_report.resolve()
    )
    print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
