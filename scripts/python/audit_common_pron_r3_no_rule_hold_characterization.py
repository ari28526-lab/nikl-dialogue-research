"""Independently audit the read-only characterization of no-rule holds."""

from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    classify_diagnostic,
    edit_signature,
    operation_edit_distance,
    unit_edit_alignment,
)
from build_common_pron_r3_no_rule_hold_characterization import (  # noqa: E402
    OUTPUT_FIELDS,
    POLICY_SCHEMA,
    SCHEMA_VERSION,
    TARGET_STATUS,
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
AUDIT_SCHEMA = "common_pron_r3_no_rule_hold_characterization_audit.v1"
csv.field_size_limit(10_000_000)


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


def audit_character_profile(token: str) -> dict[str, object]:
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
        "unicode_categories_json": json.dumps(
            sorted({unicodedata.category(char) for char in token}), ensure_ascii=False
        ),
        "has_hangul_syllable": str(has_hangul).lower(),
        "has_compatibility_or_modern_jamo": str(has_jamo).lower(),
        "has_digit": str(has_digit).lower(),
        "has_latin": str(has_latin).lower(),
        "has_punctuation_or_symbol": str(has_symbol).lower(),
    }


def audit_evidence_stratum(
    character_stratum: str, dictionary_count: int, r2_source: str, variant_count: int
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


def audit_characterization(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_characterized_not_candidate":
        raise RuntimeError("no-rule characterization manifest differs")
    scope = manifest.get("scope", {})
    if any(value is not False for value in scope.values()):
        raise RuntimeError("no-rule characterization exceeded read-only scope")
    inputs = {key: verify_fingerprint(value, label=f"input {key}") for key, value in manifest["inputs"].items()}
    output = verify_fingerprint(
        manifest["outputs"]["no_rule_hold_characterization"], label="characterization output"
    )
    policy = json.loads(inputs["policy_contract"].read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "read_only_characterization"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
        or policy.get("input_planning_status") != TARGET_STATUS
    ):
        raise RuntimeError("no-rule characterization policy differs")
    group_lookup = model_group_lookup(load_acoustic_meta(inputs["acoustic_model"]))

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
    examples: dict[str, list[dict[str, object]]] = {}
    with gzip.open(inputs["selection_readiness"], "rt", encoding="utf-8-sig", newline="") as readiness_stream, gzip.open(output, "rt", encoding="utf-8-sig", newline="") as output_stream:
        readiness_reader = csv.DictReader(readiness_stream)
        output_reader = csv.DictReader(output_stream)
        if tuple(readiness_reader.fieldnames or ()) != READINESS_FIELDS or tuple(output_reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise RuntimeError("no-rule characterization column contract differs")
        current = next(output_reader, None)
        for base in readiness_reader:
            if base["planning_status"] != TARGET_STATUS:
                continue
            if current is None or current["token"] != base["token"]:
                raise RuntimeError(f"no-rule characterization coverage/order differs: {base['token']}")
            row = current
            current = next(output_reader, None)
            if any(row[field] != base[field] for field in OUTPUT_FIELDS[:20]):
                raise RuntimeError(f"no-rule characterization base differs: {base['token']}")
            token = base["token"]
            phones = string_list(base["r2_pron_phones_json"], label=f"r2 phones {token}")
            romans = string_list(base["r2_pron_roman_json"], label=f"r2 Roman {token}")
            dictionary_variants = string_list(
                base["dictionary_pron_roman_json"], label=f"dictionary Roman {token}"
            )
            rule = tuple(expand_roman_eojeol(base["rule_pron_roman"]))
            diagnostics: list[dict[str, object]] = []
            for phone_value, roman_value in zip(phones, romans, strict=True):
                candidate = tuple(
                    classify_phone(phone, group_lookup) for phone in phone_value.split()
                )
                operations = unit_edit_alignment(candidate, rule)
                layer, diagnostic_class, equivalent = classify_diagnostic(
                    candidate, rule, operations
                )
                if equivalent:
                    raise RuntimeError(f"audited no-rule hold is technically equivalent: {token}")
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
            profile = audit_character_profile(token)
            evidence = audit_evidence_stratum(
                str(profile["character_stratum"]),
                len(dictionary_variants),
                base["r2_pron_source"],
                len(phones),
            )
            expected = {
                **profile,
                "dictionary_variant_count": str(len(dictionary_variants)),
                "r2_variant_count": str(len(phones)),
                "diagnostic_layers_json": json.dumps(layers, ensure_ascii=False),
                "diagnostic_classes_json": json.dumps(classes, ensure_ascii=False),
                "edit_signatures_json": json.dumps(signatures, ensure_ascii=False),
                "edit_distances_json": json.dumps(distances, ensure_ascii=False),
                "variant_diagnostics_json": json.dumps(
                    diagnostics, ensure_ascii=False, sort_keys=True
                ),
                "all_variants_same_edit_signature": str(len(signatures) == 1).lower(),
                "evidence_stratum": evidence,
                "candidate_generation_performed": "false",
                "canonical_selection_performed": "false",
            }
            if any(row[key] != str(value) for key, value in expected.items()):
                raise RuntimeError(f"no-rule characterization value differs: {token}")
            total = int(base["total_occurrences"])
            row_count += 1
            occurrence_count += total
            character_types[str(profile["character_stratum"])] += 1
            character_occurrences[str(profile["character_stratum"])] += total
            evidence_types[evidence] += 1
            evidence_occurrences[evidence] += total
            source_types[base["r2_pron_source"]] += 1
            source_occurrences[base["r2_pron_source"]] += total
            for value in layers:
                layer_types[value] += 1
            for value in classes:
                class_types[value] += 1
            for value in signatures:
                signature_types[value] += 1
            multi_variant_types += int(len(phones) > 1)
            dictionary_present_types += int(bool(dictionary_variants))
            bucket = examples.setdefault(evidence, [])
            if len(bucket) < 5:
                bucket.append(
                    {
                        "token": token,
                        "total_occurrences": total,
                        "r2_pron_source": base["r2_pron_source"],
                        "diagnostic_classes": classes,
                        "edit_signatures": signatures,
                    }
                )
        if current is not None:
            raise RuntimeError("unconsumed no-rule characterization rows")
    recomputed = {
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
    }
    if recomputed != manifest["counts"]:
        raise RuntimeError("no-rule characterization manifest counts differ")
    report: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": recomputed,
        "examples_by_evidence_stratum": examples,
        "contracts": {
            "candidate_generation_performed": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "characterization_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "characterization_output": file_fingerprint(output, with_sha256=True),
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
    report = audit_characterization(
        manifest_path=args.manifest.resolve(), audit_report=args.audit_report.resolve()
    )
    print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
