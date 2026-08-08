"""Audit rule/phone coverage without selecting r3 pronunciations.

This stage deliberately keeps three notions separate:

* the project's mandatory standard-pronunciation rule layer;
* pronunciation variants present in the frozen Korean MFA dictionary/G2P;
* the phone sequence used by MFA for alignment.

The outputs are diagnostic tables only.  They cannot authorize a lexicon
candidate, annual MFA run, or TextGrid rewrite.
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
from pathlib import Path
from typing import Iterator, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_mfa_lexicon import read_mfa_dictionary  # noqa: E402
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    EditOperation,
    edit_signature,
    operation_edit_distance,
    unit_edit_alignment,
)
from build_common_pron_r3_no_rule_hold_characterization import (  # noqa: E402
    OUTPUT_FIELDS as CHARACTERIZATION_FIELDS,
    SCHEMA_VERSION as CHARACTERIZATION_SCHEMA,
)
from phoneme_roman import (  # noqa: E402
    PhoneClass,
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
SCHEMA_VERSION = "common_pron_r3_rule_phone_coverage_audit.v1"
POLICY_SCHEMA = "common_pron_r3_rule_phone_coverage_policy.v1"

VARIANT_FIELDS = (
    "token",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
    "r2_pron_source",
    "variant_index",
    "r2_pron_phones",
    "r2_pron_roman",
    "rule_pron_hangul",
    "rule_pron_roman",
    "edit_signature",
    "edit_distance",
    "frozen_dictionary_exact_variant",
    "frozen_dictionary_variant_count",
    "optional_place_assimilation_only",
    "optional_place_assimilation_edits_json",
    "noninjective_phones_json",
    "evidence_labels_json",
    "diagnostic_status",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
)

PHONE_FIELDS = (
    "phone_mfa",
    "phone_class_r_auto",
    "comparison_key",
    "model_group_id",
    "model_group_r",
    "has_length",
    "secondary_articulation",
    "unreleased",
    "same_length_positional_variant_rows",
    "same_length_positional_token_types",
    "rule_keys_json",
    "rule_key_token_types_json",
    "rule_key_variant_rows_json",
    "example_tokens_by_rule_key_json",
    "noninjective_for_rule_recovery",
    "direct_mapping_authorized",
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


def expected_nasal_place(next_rule_key: str) -> str:
    if next_rule_key in {"B", "P", "PP", "M"}:
        return "M"
    if next_rule_key in {"G", "K", "KK", "NG"}:
        return "NG"
    if next_rule_key in {"D", "T", "TT", "J", "CH", "JJ", "S", "SS", "N", "L"}:
        return "N"
    return ""


def optional_place_assimilation_edits(
    operations: Sequence[EditOperation], rule: Sequence[RomanUnit]
) -> list[dict[str, object]] | None:
    """Recognize only a complete, context-supported nasal place alternation.

    This is a descriptive flag for an optional phonetic variant.  A positive
    result must not be added to the mandatory standard-pronunciation engine.
    """

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
        if current.display not in {"n", "m", "ng"}:
            return None
        if following.syllable_index != current.syllable_index + 1:
            return None
        expected = expected_nasal_place(following.comparison_key)
        if (
            operation.rule_key not in {"N", "M", "NG"}
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


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "read_only_methodological_audit"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
        or policy.get("input_status") != "success_characterized_not_candidate"
    ):
        raise RuntimeError("rule/phone coverage policy differs")
    interpretation = policy.get("interpretation_policy", {})
    if not interpretation or any(value is not True for value in interpretation.values()):
        raise RuntimeError("rule/phone interpretation policy is incomplete")
    sources = policy.get("methodological_sources", [])
    if len(sources) < 3 or any(not row.get("url") or not row.get("claim") for row in sources):
        raise RuntimeError("methodological source contract is incomplete")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("rule/phone coverage policy exceeds read-only scope")
    return policy


def dictionary_phone_rule_cooccurrence(
    *, pronunciations: dict[str, set[tuple[str, ...]]], group_lookup: dict[str, int]
) -> tuple[
    dict[tuple[str, str], set[str]],
    Counter[tuple[str, str]],
    dict[tuple[str, str], list[str]],
    Counter[str],
]:
    """Collect same-length positional co-occurrence, never a direct mapping."""

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
                key = (phone, reference.comparison_key)
                pair_tokens[key].add(token)
                pair_rows[key] += 1
                phone_rows[phone] += 1
                if token not in examples[key] and len(examples[key]) < 8:
                    examples[key].append(token)
    return pair_tokens, pair_rows, examples, phone_rows


def noninjective_phone_keys(
    pair_tokens: dict[tuple[str, str], set[str]], *, minimum_token_types: int = 2
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for (phone, rule_key), tokens in pair_tokens.items():
        if len(tokens) >= minimum_token_types:
            result[phone].add(rule_key)
    return {phone: keys for phone, keys in result.items() if len(keys) > 1}


def verify_existing(
    output_root: Path,
    *,
    characterization_manifest_path: Path,
    base_dictionary: Path,
    policy_path: Path,
) -> dict[str, object]:
    manifest_path = output_root / "RULE_PHONE_COVERAGE_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"coverage root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("existing rule/phone coverage audit differs")
    for key, path in (
        ("characterization_manifest", characterization_manifest_path),
        ("base_dictionary", base_dictionary),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
    for key, record in manifest["outputs"].items():
        verify_fingerprint(record, Path(str(record["path"])), label=f"existing {key}")
    return manifest


def build_audit(
    *,
    characterization_manifest_path: Path,
    base_dictionary: Path,
    policy_path: Path,
    output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            characterization_manifest_path=characterization_manifest_path,
            base_dictionary=base_dictionary,
            policy_path=policy_path,
        )
    characterization = json.loads(
        characterization_manifest_path.read_text(encoding="utf-8-sig")
    )
    if (
        characterization.get("schema_version") != CHARACTERIZATION_SCHEMA
        or characterization.get("status") != "success_characterized_not_candidate"
    ):
        raise RuntimeError("no-rule characterization input differs")
    validate_policy(policy_path)
    characterization_path = Path(
        str(characterization["outputs"]["no_rule_hold_characterization"]["path"])
    ).resolve()
    acoustic_model = Path(str(characterization["inputs"]["acoustic_model"]["path"])).resolve()
    verify_fingerprint(
        characterization["outputs"]["no_rule_hold_characterization"],
        characterization_path,
        label="characterization output",
    )
    verify_fingerprint(
        characterization["inputs"]["acoustic_model"], acoustic_model, label="acoustic model"
    )
    _, pronunciations = read_mfa_dictionary(base_dictionary)
    meta = load_acoustic_meta(acoustic_model)
    group_lookup = model_group_lookup(meta)
    pair_tokens, pair_rows, pair_examples, phone_rows = dictionary_phone_rule_cooccurrence(
        pronunciations=pronunciations, group_lookup=group_lookup
    )
    noninjective = noninjective_phone_keys(pair_tokens)

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    temp_variants = temp_root / "no_rule_variant_rule_phone_coverage.csv.gz"
    temp_phones = temp_root / "frozen_dictionary_phone_rule_cooccurrence.csv"
    final_variants = output_root / temp_variants.name
    final_phones = output_root / temp_phones.name
    temp_manifest = temp_root / "RULE_PHONE_COVERAGE_MANIFEST.json"

    token_rows = variant_rows = total_occurrences = 0
    any_optional = all_optional = any_frozen = all_frozen = any_noninjective = 0
    token_diagnostic: Counter[str] = Counter()
    variant_status: Counter[str] = Counter()
    source_types: Counter[str] = Counter()
    with gzip.open(
        characterization_path, "rt", encoding="utf-8-sig", newline=""
    ) as source, gzip_writer(temp_variants) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != CHARACTERIZATION_FIELDS:
            raise RuntimeError("characterization column contract differs")
        writer = csv.DictWriter(target, fieldnames=VARIANT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            token = row["token"]
            phones_values = string_list(row["r2_pron_phones_json"], label=f"phones {token}")
            roman_values = string_list(row["r2_pron_roman_json"], label=f"Roman {token}")
            if not phones_values or len(phones_values) != len(roman_values):
                raise RuntimeError(f"variant contract differs: {token}")
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            frozen_variants = pronunciations.get(token, set())
            token_optional: list[bool] = []
            token_frozen: list[bool] = []
            token_noninjective = False
            for variant_index, (phone_value, roman_value) in enumerate(
                zip(phones_values, roman_values, strict=True), 1
            ):
                raw_phones = tuple(phone_value.split())
                candidate = tuple(classify_phone(phone, group_lookup) for phone in raw_phones)
                operations = unit_edit_alignment(candidate, rule)
                optional_edits = optional_place_assimilation_edits(operations, rule)
                exact_frozen = raw_phones in frozen_variants
                ambiguous = sorted(
                    {
                        phone
                        for phone in raw_phones
                        if phone in noninjective
                    }
                )
                evidence: list[str] = []
                if optional_edits:
                    evidence.append("optional_place_assimilation_not_mandatory_standard")
                if exact_frozen:
                    evidence.append("exact_frozen_mfa_dictionary_variant")
                if ambiguous:
                    evidence.append("noninjective_phone_to_rule_cooccurrence")
                if optional_edits:
                    status = "hold_optional_place_assimilation_alignment_variant"
                elif exact_frozen:
                    status = "hold_frozen_dictionary_variant_standard_relation_unresolved"
                else:
                    status = "hold_g2p_or_rule_mapping_unresolved"
                writer.writerow(
                    {
                        "token": token,
                        "total_occurrences": row["total_occurrences"],
                        "n_years_present": row["n_years_present"],
                        **{f"count_{year}": row[f"count_{year}"] for year in YEARS},
                        "r2_pron_source": row["r2_pron_source"],
                        "variant_index": variant_index,
                        "r2_pron_phones": phone_value,
                        "r2_pron_roman": roman_value,
                        "rule_pron_hangul": row["rule_pron_hangul"],
                        "rule_pron_roman": row["rule_pron_roman"],
                        "edit_signature": edit_signature(operations),
                        "edit_distance": operation_edit_distance(operations),
                        "frozen_dictionary_exact_variant": str(exact_frozen).lower(),
                        "frozen_dictionary_variant_count": len(frozen_variants),
                        "optional_place_assimilation_only": str(bool(optional_edits)).lower(),
                        "optional_place_assimilation_edits_json": json.dumps(
                            optional_edits or [], ensure_ascii=False, sort_keys=True
                        ),
                        "noninjective_phones_json": json.dumps(ambiguous, ensure_ascii=False),
                        "evidence_labels_json": json.dumps(evidence, ensure_ascii=False),
                        "diagnostic_status": status,
                        "standard_pronunciation_claimed": "false",
                        "actual_realization_claimed": "false",
                        "candidate_generation_performed": "false",
                    }
                )
                token_optional.append(bool(optional_edits))
                token_frozen.append(exact_frozen)
                token_noninjective = token_noninjective or bool(ambiguous)
                variant_rows += 1
                variant_status[status] += 1
            any_optional += int(any(token_optional))
            all_optional += int(all(token_optional))
            any_frozen += int(any(token_frozen))
            all_frozen += int(all(token_frozen))
            any_noninjective += int(token_noninjective)
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
            token_diagnostic[token_status] += 1
            source_types[row["r2_pron_source"]] += 1
            token_rows += 1
            total_occurrences += int(row["total_occurrences"])

    phone_classes = {row.phone_mfa: row for row in build_phone_inventory(meta)}
    with temp_phones.open("x", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=PHONE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for phone in sorted(phone_classes):
            phone_class = phone_classes[phone]
            keys = sorted({key for p, key in pair_tokens if p == phone})
            token_counts = {
                key: len(pair_tokens[(phone, key)]) for key in keys
            }
            row_counts = {key: pair_rows[(phone, key)] for key in keys}
            examples = {key: pair_examples[(phone, key)] for key in keys}
            writer.writerow(
                {
                    "phone_mfa": phone,
                    "phone_class_r_auto": phone_class.phone_class_r_auto,
                    "comparison_key": phone_class.comparison_key,
                    "model_group_id": phone_class.model_group_id,
                    "model_group_r": phone_class.model_group_r,
                    "has_length": str(phone_class.has_length).lower(),
                    "secondary_articulation": phone_class.secondary_articulation,
                    "unreleased": str(phone_class.unreleased).lower(),
                    "same_length_positional_variant_rows": phone_rows[phone],
                    "same_length_positional_token_types": len(
                        set().union(*(pair_tokens[(phone, key)] for key in keys))
                    ) if keys else 0,
                    "rule_keys_json": json.dumps(keys, ensure_ascii=False),
                    "rule_key_token_types_json": json.dumps(token_counts, ensure_ascii=False, sort_keys=True),
                    "rule_key_variant_rows_json": json.dumps(row_counts, ensure_ascii=False, sort_keys=True),
                    "example_tokens_by_rule_key_json": json.dumps(examples, ensure_ascii=False, sort_keys=True),
                    "noninjective_for_rule_recovery": str(phone in noninjective).lower(),
                    "direct_mapping_authorized": "false",
                }
            )

    expected_tokens = int(characterization["counts"]["rows"])
    expected_occurrences = int(characterization["counts"]["occurrences"])
    if token_rows != expected_tokens or total_occurrences != expected_occurrences:
        raise RuntimeError("rule/phone audit coverage differs")
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_audited_not_candidate",
        "recorded_at": now_iso(),
        "scope": {
            "candidate_generation_performed": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "interpretation": {
            "optional_place_assimilation_is_mandatory_standard_rule": False,
            "dictionary_rule_cooccurrence_is_direct_mapping": False,
            "mfa_phone_is_actual_realization_transcription": False,
            "noninjective_phone_can_be_forced_to_one_phoneme": False,
        },
        "inputs": {
            "characterization_manifest": file_fingerprint(
                characterization_manifest_path, with_sha256=True
            ),
            "characterization_output": file_fingerprint(characterization_path, with_sha256=True),
            "base_dictionary": file_fingerprint(base_dictionary, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
        },
        "counts": {
            "token_types": token_rows,
            "total_occurrences": total_occurrences,
            "variant_rows": variant_rows,
            "tokens_with_any_optional_place_assimilation": any_optional,
            "tokens_all_variants_optional_place_assimilation": all_optional,
            "tokens_with_any_exact_frozen_dictionary_variant": any_frozen,
            "tokens_all_variants_exact_frozen_dictionary": all_frozen,
            "tokens_with_any_noninjective_phone": any_noninjective,
            "noninjective_phone_types": len(noninjective),
            "acoustic_phone_inventory_types": len(phone_classes),
            "token_diagnostic_status_types": dict(sorted(token_diagnostic.items())),
            "variant_diagnostic_status_rows": dict(sorted(variant_status.items())),
            "r2_source_types": dict(sorted(source_types.items())),
        },
        "outputs": {
            "variant_coverage": fingerprint_for_final(temp_variants, final_variants),
            "phone_rule_cooccurrence": fingerprint_for_final(temp_phones, final_phones),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_manifest, manifest)
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--characterization-manifest", type=Path, required=True)
    result.add_argument("--base-dictionary", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_audit(
        characterization_manifest_path=args.characterization_manifest.resolve(),
        base_dictionary=args.base_dictionary.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
