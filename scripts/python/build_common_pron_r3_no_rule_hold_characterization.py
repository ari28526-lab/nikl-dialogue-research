"""Characterize all no-surface-rule r3 holds without generating candidates."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    classify_diagnostic,
    edit_signature,
    operation_edit_distance,
    unit_edit_alignment,
)
from build_common_pron_r3_selection_readiness import READINESS_FIELDS  # noqa: E402
from phoneme_roman import classify_phone, expand_roman_eojeol, load_acoustic_meta, model_group_lookup  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_no_rule_hold_characterization.v1"
POLICY_SCHEMA = "common_pron_r3_no_rule_hold_characterization_policy.v1"
READINESS_SCHEMA = "common_pron_r3_selection_readiness.v1"
TARGET_STATUS = "hold_no_surface_rule_substantive_mismatch"
OUTPUT_FIELDS = (
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
    "character_stratum",
    "unicode_categories_json",
    "has_hangul_syllable",
    "has_compatibility_or_modern_jamo",
    "has_digit",
    "has_latin",
    "has_punctuation_or_symbol",
    "dictionary_variant_count",
    "r2_variant_count",
    "diagnostic_layers_json",
    "diagnostic_classes_json",
    "edit_signatures_json",
    "edit_distances_json",
    "variant_diagnostics_json",
    "all_variants_same_edit_signature",
    "evidence_stratum",
    "candidate_generation_performed",
    "canonical_selection_performed",
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


def character_profile(token: str) -> dict[str, object]:
    has_hangul = any("\uac00" <= char <= "\ud7a3" for char in token)
    has_jamo = any(
        "\u1100" <= char <= "\u11ff"
        or "\u3130" <= char <= "\u318f"
        or "\ua960" <= char <= "\ua97f"
        or "\ud7b0" <= char <= "\ud7ff"
        for char in token
    )
    has_digit = any(char.isdigit() for char in token)
    has_latin = any("LATIN" in unicodedata.name(char, "") for char in token)
    has_symbol = any(unicodedata.category(char)[0] in {"P", "S"} for char in token)
    categories = sorted({unicodedata.category(char) for char in token})
    if has_jamo:
        stratum = "jamo_present"
    elif has_hangul and has_digit:
        stratum = "hangul_with_digits"
    elif has_hangul and has_latin:
        stratum = "hangul_with_latin"
    elif has_hangul and has_symbol:
        stratum = "hangul_with_punctuation_or_symbol"
    elif has_hangul and all("\uac00" <= char <= "\ud7a3" for char in token):
        stratum = "hangul_syllables_only"
    elif not has_hangul and (has_digit or has_latin or has_symbol):
        stratum = "digits_symbols_or_latin_without_hangul"
    else:
        stratum = "other_unicode"
    return {
        "character_stratum": stratum,
        "unicode_categories_json": json.dumps(categories, ensure_ascii=False),
        "has_hangul_syllable": str(has_hangul).lower(),
        "has_compatibility_or_modern_jamo": str(has_jamo).lower(),
        "has_digit": str(has_digit).lower(),
        "has_latin": str(has_latin).lower(),
        "has_punctuation_or_symbol": str(has_symbol).lower(),
    }


def evidence_stratum(
    *, character_stratum: str, dictionary_count: int, r2_source: str, variant_count: int
) -> str:
    if character_stratum != "hangul_syllables_only":
        return "non_plain_hangul_requires_form_mapping"
    if dictionary_count:
        return "hangul_dictionary_present_but_not_phone_supported"
    if r2_source == "base_dictionary_preserved":
        return "hangul_base_dictionary_without_supported_dictionary_link"
    if variant_count > 1:
        return "hangul_multiple_r2_variants"
    return "hangul_single_frozen_g2p_variant"


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "read_only_characterization"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
        or policy.get("input_planning_status") != TARGET_STATUS
    ):
        raise RuntimeError("no-rule characterization policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("no-rule characterization policy exceeds read-only scope")
    return policy


def verify_existing(
    output_root: Path, *, readiness_manifest_path: Path, policy_path: Path
) -> dict[str, object]:
    manifest_path = output_root / "NO_RULE_HOLD_CHARACTERIZATION_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"characterization root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_characterized_not_candidate":
        raise RuntimeError("existing no-rule characterization differs")
    for key, path in (
        ("selection_readiness_manifest", readiness_manifest_path),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
    for key, record in manifest["outputs"].items():
        verify_fingerprint(record, Path(str(record["path"])), label=f"existing output {key}")
    return manifest


def build_characterization(
    *, readiness_manifest_path: Path, policy_path: Path, output_root: Path
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            readiness_manifest_path=readiness_manifest_path,
            policy_path=policy_path,
        )
    readiness = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness.get("schema_version") != READINESS_SCHEMA or readiness.get("status") != "success_planning_not_selected":
        raise RuntimeError("selection-readiness input differs")
    validate_policy(policy_path)
    readiness_path = Path(str(readiness["outputs"]["selection_readiness"]["path"])).resolve()
    acoustic_model = Path(str(readiness["inputs"]["acoustic_model"]["path"])).resolve()
    verify_fingerprint(readiness["outputs"]["selection_readiness"], readiness_path, label="selection readiness")
    verify_fingerprint(readiness["inputs"]["acoustic_model"], acoustic_model, label="acoustic model")
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    temp_output = temp_root / "no_rule_hold_characterization.csv.gz"
    temp_manifest = temp_root / "NO_RULE_HOLD_CHARACTERIZATION_MANIFEST.json"
    final_output = output_root / temp_output.name
    row_count = occurrence_count = 0
    character_types: Counter[str] = Counter()
    character_occurrences: Counter[str] = Counter()
    evidence_types: Counter[str] = Counter()
    evidence_occurrences: Counter[str] = Counter()
    source_types: Counter[str] = Counter()
    source_occurrences: Counter[str] = Counter()
    layer_types: Counter[str] = Counter()
    class_types: Counter[str] = Counter()
    signature_types: Counter[str] = Counter()
    multi_variant_types = dictionary_present_types = 0
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(temp_output) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("selection-readiness column contract differs")
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            if row["planning_status"] != TARGET_STATUS:
                continue
            token = row["token"]
            phones = string_list(row["r2_pron_phones_json"], label=f"r2 phones {token}")
            romans = string_list(row["r2_pron_roman_json"], label=f"r2 Roman {token}")
            if not phones or len(phones) != len(romans):
                raise RuntimeError(f"no-rule r2 variant contract differs: {token}")
            dictionary_variants = string_list(
                row["dictionary_pron_roman_json"], label=f"dictionary Roman {token}"
            )
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            diagnostics: list[dict[str, object]] = []
            for phone_value, roman_value in zip(phones, romans, strict=True):
                candidate = tuple(
                    classify_phone(phone, group_lookup) for phone in phone_value.split()
                )
                operations = unit_edit_alignment(candidate, rule)
                layer, diagnostic_class, equivalence_candidate = classify_diagnostic(
                    candidate, rule, operations
                )
                if equivalence_candidate:
                    raise RuntimeError(f"no-rule hold contains technical equivalent: {token}")
                diagnostics.append(
                    {
                        "r2_pron_phones": phone_value,
                        "r2_pron_roman": roman_value,
                        "diagnostic_layer": layer,
                        "diagnostic_class": diagnostic_class,
                        "edit_signature": edit_signature(operations),
                        "edit_distance": operation_edit_distance(operations),
                    }
                )
            layers = sorted({str(item["diagnostic_layer"]) for item in diagnostics})
            classes = sorted({str(item["diagnostic_class"]) for item in diagnostics})
            signatures = sorted({str(item["edit_signature"]) for item in diagnostics})
            distances = sorted({int(item["edit_distance"]) for item in diagnostics})
            profile = character_profile(token)
            total = int(row["total_occurrences"])
            evidence = evidence_stratum(
                character_stratum=str(profile["character_stratum"]),
                dictionary_count=len(dictionary_variants),
                r2_source=row["r2_pron_source"],
                variant_count=len(phones),
            )
            writer.writerow(
                {
                    **{field: row[field] for field in OUTPUT_FIELDS[:20]},
                    **profile,
                    "dictionary_variant_count": len(dictionary_variants),
                    "r2_variant_count": len(phones),
                    "diagnostic_layers_json": json.dumps(layers, ensure_ascii=False),
                    "diagnostic_classes_json": json.dumps(classes, ensure_ascii=False),
                    "edit_signatures_json": json.dumps(signatures, ensure_ascii=False),
                    "edit_distances_json": json.dumps(distances, ensure_ascii=False),
                    "variant_diagnostics_json": json.dumps(diagnostics, ensure_ascii=False, sort_keys=True),
                    "all_variants_same_edit_signature": str(len(signatures) == 1).lower(),
                    "evidence_stratum": evidence,
                    "candidate_generation_performed": "false",
                    "canonical_selection_performed": "false",
                }
            )
            row_count += 1
            occurrence_count += total
            character_types[str(profile["character_stratum"])] += 1
            character_occurrences[str(profile["character_stratum"])] += total
            evidence_types[evidence] += 1
            evidence_occurrences[evidence] += total
            source_types[row["r2_pron_source"]] += 1
            source_occurrences[row["r2_pron_source"]] += total
            for value in layers:
                layer_types[value] += 1
            for value in classes:
                class_types[value] += 1
            for value in signatures:
                signature_types[value] += 1
            multi_variant_types += int(len(phones) > 1)
            dictionary_present_types += int(bool(dictionary_variants))
    expected_rows = int(readiness["counts"]["planning_status_types"][TARGET_STATUS])
    expected_occurrences = int(
        readiness["counts"]["planning_status_occurrences"][TARGET_STATUS]
    )
    if row_count != expected_rows or occurrence_count != expected_occurrences:
        raise RuntimeError("no-rule characterization coverage differs")
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_characterized_not_candidate",
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
        "inputs": {
            "selection_readiness_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "selection_readiness": file_fingerprint(readiness_path, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        },
        "counts": {
            "rows": row_count,
            "occurrences": occurrence_count,
            "multi_variant_types": multi_variant_types,
            "dictionary_present_types": dictionary_present_types,
            "character_stratum_types": dict(sorted(character_types.items())),
            "character_stratum_occurrences": dict(sorted(character_occurrences.items())),
            "evidence_stratum_types": dict(sorted(evidence_types.items())),
            "evidence_stratum_occurrences": dict(sorted(evidence_occurrences.items())),
            "r2_source_types": dict(sorted(source_types.items())),
            "r2_source_occurrences": dict(sorted(source_occurrences.items())),
            "diagnostic_layer_types": dict(sorted(layer_types.items())),
            "diagnostic_class_types": dict(sorted(class_types.items())),
            "distinct_edit_signatures": len(signature_types),
            "top_edit_signature_types": dict(signature_types.most_common(100)),
        },
        "outputs": {
            "no_rule_hold_characterization": fingerprint_for_final(temp_output, final_output)
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_manifest, manifest)
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--selection-readiness-manifest", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_characterization(
        readiness_manifest_path=args.selection_readiness_manifest.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
