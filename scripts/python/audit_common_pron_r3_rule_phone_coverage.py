"""Independently audit stage 11 rule/phone methodological diagnostics."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import read_mfa_dictionary  # noqa: E402
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    EditOperation,
    edit_signature,
    operation_edit_distance,
    unit_edit_alignment,
)
from build_common_pron_r3_no_rule_hold_characterization import (  # noqa: E402
    OUTPUT_FIELDS as CHARACTERIZATION_FIELDS,
)
from build_common_pron_r3_rule_phone_coverage_audit import (  # noqa: E402
    PHONE_FIELDS,
    POLICY_SCHEMA,
    SCHEMA_VERSION,
    VARIANT_FIELDS,
)
from phoneme_roman import (  # noqa: E402
    RomanUnit,
    build_phone_inventory,
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
AUDIT_SCHEMA = "common_pron_r3_rule_phone_coverage_verification.v1"
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")
    return path


def parse_list(value: object, *, label: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON list: {label}") from exc
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise RuntimeError(f"invalid string list: {label}")
    return result


def audit_expected_place(next_key: str) -> str:
    if next_key in {"B", "P", "PP", "M"}:
        return "M"
    if next_key in {"G", "K", "KK", "NG"}:
        return "NG"
    if next_key in {"D", "T", "TT", "J", "CH", "JJ", "S", "SS", "N", "L"}:
        return "N"
    return ""


def audit_optional_edits(
    operations: Sequence[EditOperation], rule: Sequence[RomanUnit]
) -> list[dict[str, object]] | None:
    edits = [operation for operation in operations if operation.operation != "match"]
    if not edits:
        return None
    result: list[dict[str, object]] = []
    for operation in edits:
        if operation.operation != "substitution" or operation.rule_index is None:
            return None
        if operation.rule_index + 1 >= len(rule):
            return None
        current = rule[operation.rule_index]
        following = rule[operation.rule_index + 1]
        expected = audit_expected_place(following.comparison_key)
        if (
            current.display not in {"n", "m", "ng"}
            or following.syllable_index != current.syllable_index + 1
            or operation.rule_key not in {"N", "M", "NG"}
            or operation.candidate_key not in {"N", "M", "NG"}
            or not expected
            or operation.candidate_key != expected
            or operation.candidate_key == operation.rule_key
        ):
            return None
        result.append(
            {
                "candidate_phone": operation.candidate_phone,
                "candidate_key": operation.candidate_key,
                "rule_display": current.display,
                "rule_key": operation.rule_key,
                "following_rule_display": following.display,
                "following_rule_key": following.comparison_key,
                "interpretation": "optional_place_assimilation_not_mandatory_standard",
            }
        )
    return result


def recompute_dictionary_evidence(
    pronunciations: dict[str, set[tuple[str, ...]]], group_lookup: dict[str, int]
):
    pair_tokens: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_rows: Counter[tuple[str, str]] = Counter()
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    phone_rows: Counter[str] = Counter()
    for token in sorted(pronunciations):
        _, _, rule_roman = process_eojeol(token, DEFAULT_FLAGS)
        if rule_roman == PLACEHOLDER:
            continue
        rule = tuple(expand_roman_eojeol(rule_roman))
        for phones in sorted(pronunciations[token]):
            if len(phones) != len(rule):
                continue
            for phone, reference in zip(phones, rule, strict=True):
                classify_phone(phone, group_lookup)
                pair = (phone, reference.comparison_key)
                pair_tokens[pair].add(token)
                pair_rows[pair] += 1
                phone_rows[phone] += 1
                if token not in examples[pair] and len(examples[pair]) < 8:
                    examples[pair].append(token)
    supported: dict[str, set[str]] = defaultdict(set)
    for (phone, rule_key), tokens in pair_tokens.items():
        if len(tokens) >= 2:
            supported[phone].add(rule_key)
    noninjective = {phone: keys for phone, keys in supported.items() if len(keys) > 1}
    return pair_tokens, pair_rows, examples, phone_rows, noninjective


def audit_stage(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("rule/phone coverage manifest differs")
    if any(value is not False for value in manifest.get("scope", {}).values()):
        raise RuntimeError("rule/phone coverage exceeded read-only scope")
    if any(value is not False for value in manifest.get("interpretation", {}).values()):
        raise RuntimeError("rule/phone interpretation is unsafe")
    inputs = {key: verify(record, label=f"input {key}") for key, record in manifest["inputs"].items()}
    outputs = {key: verify(record, label=f"output {key}") for key, record in manifest["outputs"].items()}
    policy = json.loads(inputs["policy_contract"].read_text(encoding="utf-8-sig"))
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "read_only_methodological_audit":
        raise RuntimeError("rule/phone policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("rule/phone policy invariants differ")
    if any(value is not True for value in policy.get("interpretation_policy", {}).values()):
        raise RuntimeError("rule/phone interpretation policy differs")

    _, pronunciations = read_mfa_dictionary(inputs["base_dictionary"])
    meta = load_acoustic_meta(inputs["acoustic_model"])
    group_lookup = model_group_lookup(meta)
    pair_tokens, pair_rows, examples, phone_rows, noninjective = recompute_dictionary_evidence(
        pronunciations, group_lookup
    )
    inventory = {row.phone_mfa: row for row in build_phone_inventory(meta)}

    with outputs["phone_rule_cooccurrence"].open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PHONE_FIELDS:
            raise RuntimeError("phone co-occurrence column contract differs")
        observed_phones: set[str] = set()
        for row in reader:
            phone = row["phone_mfa"]
            if phone in observed_phones or phone not in inventory:
                raise RuntimeError(f"phone inventory coverage differs: {phone}")
            observed_phones.add(phone)
            item = inventory[phone]
            keys = sorted({key for p, key in pair_tokens if p == phone})
            token_counts = {key: len(pair_tokens[(phone, key)]) for key in keys}
            row_counts = {key: pair_rows[(phone, key)] for key in keys}
            example_values = {key: examples[(phone, key)] for key in keys}
            expected = {
                "phone_class_r_auto": item.phone_class_r_auto,
                "comparison_key": item.comparison_key,
                "model_group_id": str(item.model_group_id),
                "model_group_r": item.model_group_r,
                "has_length": str(item.has_length).lower(),
                "secondary_articulation": item.secondary_articulation,
                "unreleased": str(item.unreleased).lower(),
                "same_length_positional_variant_rows": str(phone_rows[phone]),
                "same_length_positional_token_types": str(
                    len(set().union(*(pair_tokens[(phone, key)] for key in keys))) if keys else 0
                ),
                "rule_keys_json": json.dumps(keys, ensure_ascii=False),
                "rule_key_token_types_json": json.dumps(token_counts, ensure_ascii=False, sort_keys=True),
                "rule_key_variant_rows_json": json.dumps(row_counts, ensure_ascii=False, sort_keys=True),
                "example_tokens_by_rule_key_json": json.dumps(example_values, ensure_ascii=False, sort_keys=True),
                "noninjective_for_rule_recovery": str(phone in noninjective).lower(),
                "direct_mapping_authorized": "false",
            }
            if any(row[key] != value for key, value in expected.items()):
                raise RuntimeError(f"phone co-occurrence value differs: {phone}")
        if observed_phones != set(inventory):
            raise RuntimeError("phone co-occurrence inventory is incomplete")

    token_rows = variant_rows = total_occurrences = 0
    any_optional = all_optional = any_frozen = all_frozen = any_noninjective = 0
    token_status_counts: Counter[str] = Counter()
    variant_status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    examples_by_status: dict[str, list[dict[str, object]]] = defaultdict(list)
    with gzip.open(inputs["characterization_output"], "rt", encoding="utf-8-sig", newline="") as source, gzip.open(outputs["variant_coverage"], "rt", encoding="utf-8-sig", newline="") as observed:
        source_reader = csv.DictReader(source)
        output_reader = csv.DictReader(observed)
        if tuple(source_reader.fieldnames or ()) != CHARACTERIZATION_FIELDS or tuple(output_reader.fieldnames or ()) != VARIANT_FIELDS:
            raise RuntimeError("variant coverage column contract differs")
        current = next(output_reader, None)
        for base in source_reader:
            token = base["token"]
            phone_values = parse_list(base["r2_pron_phones_json"], label=f"phones {token}")
            roman_values = parse_list(base["r2_pron_roman_json"], label=f"Roman {token}")
            rule = tuple(expand_roman_eojeol(base["rule_pron_roman"]))
            frozen_variants = pronunciations.get(token, set())
            token_optional: list[bool] = []
            token_frozen: list[bool] = []
            token_ambiguous = False
            for index, (phone_value, roman_value) in enumerate(zip(phone_values, roman_values, strict=True), 1):
                if current is None or current["token"] != token or int(current["variant_index"]) != index:
                    raise RuntimeError(f"variant coverage/order differs: {token}#{index}")
                raw_phones = tuple(phone_value.split())
                candidate = tuple(classify_phone(phone, group_lookup) for phone in raw_phones)
                operations = unit_edit_alignment(candidate, rule)
                optional = audit_optional_edits(operations, rule)
                frozen = raw_phones in frozen_variants
                ambiguous = sorted({phone for phone in raw_phones if phone in noninjective})
                evidence = []
                if optional:
                    evidence.append("optional_place_assimilation_not_mandatory_standard")
                if frozen:
                    evidence.append("exact_frozen_mfa_dictionary_variant")
                if ambiguous:
                    evidence.append("noninjective_phone_to_rule_cooccurrence")
                if optional:
                    status = "hold_optional_place_assimilation_alignment_variant"
                elif frozen:
                    status = "hold_frozen_dictionary_variant_standard_relation_unresolved"
                else:
                    status = "hold_g2p_or_rule_mapping_unresolved"
                expected = {
                    "total_occurrences": base["total_occurrences"],
                    "n_years_present": base["n_years_present"],
                    **{f"count_{year}": base[f"count_{year}"] for year in ("2020", "2021", "2022", "2023", "2024", "2025")},
                    "r2_pron_source": base["r2_pron_source"],
                    "r2_pron_phones": phone_value,
                    "r2_pron_roman": roman_value,
                    "rule_pron_hangul": base["rule_pron_hangul"],
                    "rule_pron_roman": base["rule_pron_roman"],
                    "edit_signature": edit_signature(operations),
                    "edit_distance": str(operation_edit_distance(operations)),
                    "frozen_dictionary_exact_variant": str(frozen).lower(),
                    "frozen_dictionary_variant_count": str(len(frozen_variants)),
                    "optional_place_assimilation_only": str(bool(optional)).lower(),
                    "optional_place_assimilation_edits_json": json.dumps(optional or [], ensure_ascii=False, sort_keys=True),
                    "noninjective_phones_json": json.dumps(ambiguous, ensure_ascii=False),
                    "evidence_labels_json": json.dumps(evidence, ensure_ascii=False),
                    "diagnostic_status": status,
                    "standard_pronunciation_claimed": "false",
                    "actual_realization_claimed": "false",
                    "candidate_generation_performed": "false",
                }
                if any(current[key] != value for key, value in expected.items()):
                    raise RuntimeError(f"variant coverage value differs: {token}#{index}")
                token_optional.append(bool(optional))
                token_frozen.append(frozen)
                token_ambiguous = token_ambiguous or bool(ambiguous)
                variant_rows += 1
                variant_status_counts[status] += 1
                bucket = examples_by_status[status]
                if len(bucket) < 8:
                    bucket.append({"token": token, "phones": phone_value, "rule_roman": base["rule_pron_roman"], "edit_signature": edit_signature(operations)})
                current = next(output_reader, None)
            any_optional += int(any(token_optional))
            all_optional += int(all(token_optional))
            any_frozen += int(any(token_frozen))
            all_frozen += int(all(token_frozen))
            any_noninjective += int(token_ambiguous)
            if all(token_optional):
                token_status = "all_variants_optional_place_assimilation"
            elif any(token_optional):
                token_status = "some_variants_optional_place_assimilation"
            elif all(token_frozen):
                token_status = "all_variants_exact_frozen_dictionary"
            elif any(token_frozen):
                token_status = "some_variants_exact_frozen_dictionary"
            else:
                token_status = "unresolved_g2p_or_rule_mapping"
            token_status_counts[token_status] += 1
            source_counts[base["r2_pron_source"]] += 1
            token_rows += 1
            total_occurrences += int(base["total_occurrences"])
        if current is not None:
            raise RuntimeError("unconsumed variant coverage rows")

    counts = {
        "token_types": token_rows,
        "total_occurrences": total_occurrences,
        "variant_rows": variant_rows,
        "tokens_with_any_optional_place_assimilation": any_optional,
        "tokens_all_variants_optional_place_assimilation": all_optional,
        "tokens_with_any_exact_frozen_dictionary_variant": any_frozen,
        "tokens_all_variants_exact_frozen_dictionary": all_frozen,
        "tokens_with_any_noninjective_phone": any_noninjective,
        "noninjective_phone_types": len(noninjective),
        "acoustic_phone_inventory_types": len(inventory),
        "token_diagnostic_status_types": dict(sorted(token_status_counts.items())),
        "variant_diagnostic_status_rows": dict(sorted(variant_status_counts.items())),
        "r2_source_types": dict(sorted(source_counts.items())),
    }
    if counts != manifest["counts"]:
        raise RuntimeError("rule/phone coverage manifest counts differ")
    report: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": counts,
        "examples_by_variant_status": dict(examples_by_status),
        "contracts": {
            "optional_place_assimilation_added_to_mandatory_rule_engine": False,
            "dictionary_rule_cooccurrence_used_as_direct_mapping": False,
            "candidate_generation_performed": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "manifest": file_fingerprint(manifest_path, with_sha256=True),
            "variant_coverage": file_fingerprint(outputs["variant_coverage"], with_sha256=True),
            "phone_rule_cooccurrence": file_fingerprint(outputs["phone_rule_cooccurrence"], with_sha256=True),
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
    report = audit_stage(
        manifest_path=args.manifest.resolve(), audit_report=args.audit_report.resolve()
    )
    print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
