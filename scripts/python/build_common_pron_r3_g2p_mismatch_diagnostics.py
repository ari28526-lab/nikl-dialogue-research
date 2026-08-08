"""Diagnose every r3 G2P/rule mismatch without selecting pronunciations.

This stage aligns ordered broad-Roman comparison units, records deterministic
edit signatures, and separates a narrow representation-equivalence candidate
from contrast or substantive-difference review classes.  Every class remains
unapproved: the output is diagnostic evidence, not a canonical lexicon.
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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import (  # noqa: E402
    YEARS,
    phone_units,
    roman_units,
)
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    SCHEMA_VERSION as AGREEMENT_SCHEMA,
    SOURCE_RESULT_FIELDS,
    TARGET_RESULT_FIELDS,
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
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_g2p_mismatch_diagnostics.v1"
TARGET_DIAGNOSTIC_FIELDS = (
    *TARGET_RESULT_FIELDS,
    "candidate_comparison_keys_json",
    "rule_comparison_keys_json",
    "edit_operations_json",
    "edit_operation_counts_json",
    "edit_signature",
    "diagnostic_layer",
    "diagnostic_class",
    "representation_equivalence_candidate",
    "automatic_equivalence_approved",
    "manual_decision_id",
)
SOURCE_DIAGNOSTIC_FIELDS = (
    *SOURCE_RESULT_FIELDS,
    "edit_signature",
    "diagnostic_layer",
    "diagnostic_class",
    "representation_equivalence_candidate",
    "automatic_equivalence_approved",
)
PATTERN_SUMMARY_FIELDS = (
    "diagnostic_layer",
    "diagnostic_class",
    "comparison_edit_distance",
    "edit_signature",
    "target_count",
    "source_type_count",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
    "example_targets_json",
    "example_tokens_json",
    "automatic_equivalence_approved",
)
csv.field_size_limit(10_000_000)


RULE_MODEL_GROUP = {
    "G": "K_GROUP",
    "k": "K_GROUP",
    "K": "K_GROUP",
    "KK": "K_GROUP",
    "M": "M_GROUP",
    "m": "M_GROUP",
    "N": "N_GROUP",
    "n": "N_GROUP",
    "NG": "NG_GROUP",
    "ng": "NG_GROUP",
    "B": "P_GROUP",
    "p": "P_GROUP",
    "P": "P_GROUP",
    "PP": "P_GROUP",
    "S": "S_GROUP",
    "SS": "S_GROUP",
    "D": "T_GROUP",
    "t": "T_GROUP",
    "T": "T_GROUP",
    "TT": "T_GROUP",
    "J": "C_GROUP",
    "CH": "C_GROUP",
    "JJ": "C_GROUP",
    "Y": "Y_GROUP",
    "W": "W_GROUP",
    "H": "H_GROUP",
    "EU_G": "EU_GLIDE_GROUP",
    "R": "L_GROUP",
    "l": "L_GROUP",
    "E": "E_GROUP",
    "I": "I_GROUP",
    "O": "O_GROUP",
    "U": "U_GROUP",
    "A": "A_GROUP",
    "AE": "AE_GROUP",
    "EU": "EU_GROUP",
    "EO": "EO_GROUP",
}


@dataclass(frozen=True)
class EditOperation:
    operation: str
    candidate_index: int | None
    rule_index: int | None
    candidate_phone: str
    candidate_display: str
    candidate_key: str
    candidate_model_group: str
    candidate_has_length: bool | None
    rule_display: str
    rule_key: str
    rule_model_group: str


def clean(value: object) -> str:
    return str(value or "").strip()


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


def unit_edit_alignment(
    candidate: Sequence[PhoneClass], rule: Sequence[RomanUnit]
) -> list[EditOperation]:
    """Return a deterministic unit-cost Levenshtein alignment."""

    n, m = len(candidate), len(rule)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, str] | None]] = [
        [None] * (m + 1) for _ in range(n + 1)
    ]
    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = (i - 1, 0, "candidate_only")
    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = (0, j - 1, "rule_only")
    priority = {"match": 0, "substitution": 1, "candidate_only": 2, "rule_only": 3}
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            same = candidate[i - 1].comparison_key == rule[j - 1].comparison_key
            diagonal = "match" if same else "substitution"
            options = [
                (dp[i - 1][j - 1] + (0 if same else 1), priority[diagonal], i - 1, j - 1, diagonal),
                (dp[i - 1][j] + 1, priority["candidate_only"], i - 1, j, "candidate_only"),
                (dp[i][j - 1] + 1, priority["rule_only"], i, j - 1, "rule_only"),
            ]
            cost, _, pi, pj, operation = min(options)
            dp[i][j] = cost
            back[i][j] = (pi, pj, operation)
    result: list[EditOperation] = []
    i, j = n, m
    while i or j:
        prior = back[i][j]
        if prior is None:
            raise RuntimeError(f"edit alignment backtrace missing: i={i} j={j}")
        pi, pj, operation = prior
        candidate_index = i - 1 if operation in {"match", "substitution", "candidate_only"} else None
        rule_index = j - 1 if operation in {"match", "substitution", "rule_only"} else None
        phone = candidate[candidate_index] if candidate_index is not None else None
        reference = rule[rule_index] if rule_index is not None else None
        rule_group = RULE_MODEL_GROUP.get(reference.display, "") if reference else ""
        if reference is not None and not rule_group:
            raise RuntimeError(f"rule Roman unit lacks model group: {reference.display}")
        result.append(
            EditOperation(
                operation=operation,
                candidate_index=candidate_index,
                rule_index=rule_index,
                candidate_phone=phone.phone_mfa if phone else "",
                candidate_display=phone.phone_class_r_auto if phone else "",
                candidate_key=phone.comparison_key if phone else "",
                candidate_model_group=phone.model_group_r if phone else "",
                candidate_has_length=phone.has_length if phone else None,
                rule_display=reference.display if reference else "",
                rule_key=reference.comparison_key if reference else "",
                rule_model_group=rule_group,
            )
        )
        i, j = pi, pj
    result.reverse()
    return result


def operation_edit_distance(operations: Sequence[EditOperation]) -> int:
    return sum(operation.operation != "match" for operation in operations)


def edit_signature(operations: Sequence[EditOperation]) -> str:
    parts: list[str] = []
    for operation in operations:
        if operation.operation == "match":
            continue
        if operation.operation == "substitution":
            parts.append(f"SUB:{operation.candidate_key}>{operation.rule_key}")
        elif operation.operation == "candidate_only":
            parts.append(f"CANDIDATE_ONLY:{operation.candidate_key}")
        elif operation.operation == "rule_only":
            parts.append(f"RULE_ONLY:{operation.rule_key}")
        else:
            raise RuntimeError(f"unknown edit operation: {operation.operation}")
    return ";".join(parts)


def key_runs(keys: Sequence[str]) -> list[tuple[str, int, int]]:
    runs: list[tuple[str, int, int]] = []
    start = 0
    while start < len(keys):
        end = start + 1
        while end < len(keys) and keys[end] == keys[start]:
            end += 1
        runs.append((keys[start], start, end))
        start = end
    return runs


def phone_encodes_glide(phone: str, glide: str) -> bool:
    """Return whether one MFA phone overtly encodes a Roman glide gesture."""

    if glide == "W":
        return "ʷ" in phone
    if glide != "Y":
        return False
    if "ʲ" in phone:
        return True
    # Korean MFA also uses inherently palatal/alveolo-palatal IPA bases without
    # a superscript palatalization mark (e.g. /ɟ, c, ɲ, tɕ, dʑ, ç, ʝ, ʎ/).
    return any(symbol in phone for symbol in ("c", "ɟ", "ɲ", "ç", "ʝ", "ɕ", "ʑ", "ʎ"))


def representation_support(
    operations: Sequence[EditOperation],
) -> set[str] | None:
    """Identify narrowly supported many-to-one phone representations.

    A result is only a *candidate* equivalence.  It never approves a
    pronunciation.  All non-match operations must be independently supported
    by either an MFA length mark or a secondary/palatal glide gesture.
    """

    support: set[str] = set()
    edits = [index for index, op in enumerate(operations) if op.operation != "match"]
    if not edits:
        return None
    for index in edits:
        operation = operations[index]
        if operation.operation != "rule_only":
            return None
        neighbors = [
            operations[position]
            for position in (index - 1, index + 1)
            if 0 <= position < len(operations)
            and operations[position].operation == "match"
            and operations[position].candidate_index is not None
        ]
        if operation.rule_key in {"Y", "W"} and any(
            phone_encodes_glide(neighbor.candidate_phone, operation.rule_key)
            for neighbor in neighbors
        ):
            support.add("secondary_articulation_glide")
            continue
        if any(
            neighbor.candidate_key == operation.rule_key
            and neighbor.candidate_has_length is True
            for neighbor in neighbors
        ):
            support.add("length_marked_identical_unit")
            continue
        return None
    return support


def classify_diagnostic(
    candidate: Sequence[PhoneClass],
    rule: Sequence[RomanUnit],
    operations: Sequence[EditOperation],
) -> tuple[str, str, bool]:
    support = representation_support(operations)
    if support:
        if support == {"length_marked_identical_unit"}:
            diagnostic_class = "length_supported_adjacent_identical_coalescence"
        elif support == {"secondary_articulation_glide"}:
            diagnostic_class = "secondary_articulation_encodes_glide"
        else:
            diagnostic_class = "combined_length_and_glide_encoding"
        return (
            "representation_equivalence_candidate",
            diagnostic_class,
            True,
        )
    candidate_keys = [item.comparison_key for item in candidate]
    rule_keys = [item.comparison_key for item in rule]
    candidate_runs = key_runs(candidate_keys)
    rule_runs = key_runs(rule_keys)
    if [row[0] for row in candidate_runs] == [row[0] for row in rule_runs]:
        differences = [
            (candidate_run, rule_run)
            for candidate_run, rule_run in zip(candidate_runs, rule_runs, strict=True)
            if candidate_run[2] - candidate_run[1] != rule_run[2] - rule_run[1]
        ]
        return (
            "representation_review_required",
            "run_length_difference_without_complete_length_support",
            False,
        )

    edits = [operation for operation in operations if operation.operation != "match"]
    if len(edits) == 1:
        edit = edits[0]
        if edit.operation == "substitution":
            if edit.candidate_model_group == edit.rule_model_group:
                return (
                    "contrast_review_required",
                    "single_contrast_within_acoustic_model_group",
                    False,
                )
            return (
                "substantive_difference_candidate",
                "single_cross_group_substitution",
                False,
            )
        if edit.operation == "candidate_only":
            return (
                "substantive_difference_candidate",
                "single_candidate_unit_extra",
                False,
            )
        if edit.operation == "rule_only":
            return (
                "substantive_difference_candidate",
                "single_rule_unit_missing_from_candidate",
                False,
            )

    substitutions = [edit for edit in edits if edit.operation == "substitution"]
    gaps = [edit for edit in edits if edit.operation != "substitution"]
    if substitutions and not gaps and all(
        edit.candidate_model_group == edit.rule_model_group for edit in substitutions
    ):
        return (
            "contrast_review_required",
            "multiple_contrasts_within_acoustic_model_group",
            False,
        )
    if gaps and not substitutions:
        return (
            "substantive_difference_candidate",
            "multiple_segment_count_difference",
            False,
        )
    return (
        "substantive_difference_candidate",
        "mixed_or_cross_group_difference",
        False,
    )


def verify_existing(output_root: Path, *, agreement_manifest: Path) -> dict[str, object]:
    manifest_path = output_root / "G2P_MISMATCH_DIAGNOSTICS_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"diagnostic root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_diagnostics_not_selected":
        raise RuntimeError("existing mismatch diagnostic manifest is not reusable")
    verify_fingerprint(manifest["inputs"]["agreement_manifest"], agreement_manifest, label="existing agreement manifest")
    for key, record in manifest["outputs"].items():
        verify_fingerprint(record, Path(str(record["path"])), label=f"existing output {key}")
    return manifest


def build_diagnostics(*, agreement_manifest_path: Path, output_root: Path) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(output_root, agreement_manifest=agreement_manifest_path)
    agreement = json.loads(agreement_manifest_path.read_text(encoding="utf-8-sig"))
    if agreement.get("schema_version") != AGREEMENT_SCHEMA or agreement.get("status") != "success_candidates_not_selected":
        raise RuntimeError("agreement Gate is not a completed candidate-only input")
    if agreement.get("scope", {}).get("candidate_is_final_selection") is not False:
        raise RuntimeError("agreement Gate exceeded candidate-only scope")
    agreement_outputs = {
        key: Path(str(record["path"])).resolve()
        for key, record in agreement["outputs"].items()
    }
    for key, path in agreement_outputs.items():
        verify_fingerprint(agreement["outputs"][key], path, label=f"agreement output {key}")
    acoustic_model = Path(str(agreement["inputs"]["acoustic_model"]["path"])).resolve()
    verify_fingerprint(agreement["inputs"]["acoustic_model"], acoustic_model, label="acoustic model")
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))

    diagnostics: dict[str, dict[str, object]] = {}
    target_class_counts: Counter[str] = Counter()
    target_layer_counts: Counter[str] = Counter()
    target_pattern_counts: Counter[tuple[str, str, int, str]] = Counter()
    with gzip.open(agreement_outputs["target_agreement"], "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_RESULT_FIELDS:
            raise RuntimeError("agreement target column contract mismatch")
        for row in reader:
            if clean(row["comparison_status"]) != "different_rule_roman":
                continue
            target = clean(row["target_hangul"])
            phones = tuple(clean(row["g2p_candidate_phones"]).split())
            candidate = tuple(classify_phone(phone, group_lookup) for phone in phones)
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            operations = unit_edit_alignment(candidate, rule)
            distance = operation_edit_distance(operations)
            if distance != int(row["comparison_edit_distance"]):
                raise RuntimeError(f"edit distance differs from agreement Gate: {target}")
            layer, diagnostic_class, equivalence_candidate = classify_diagnostic(candidate, rule, operations)
            signature = edit_signature(operations)
            operation_counts = Counter(operation.operation for operation in operations if operation.operation != "match")
            diagnostic = {
                **row,
                "candidate_comparison_keys_json": json.dumps([item.comparison_key for item in candidate], ensure_ascii=False),
                "rule_comparison_keys_json": json.dumps([item.comparison_key for item in rule], ensure_ascii=False),
                "edit_operations_json": json.dumps([asdict(operation) for operation in operations], ensure_ascii=False, sort_keys=True),
                "edit_operation_counts_json": json.dumps(dict(sorted(operation_counts.items())), ensure_ascii=False, sort_keys=True),
                "edit_signature": signature,
                "diagnostic_layer": layer,
                "diagnostic_class": diagnostic_class,
                "representation_equivalence_candidate": str(equivalence_candidate).lower(),
                "automatic_equivalence_approved": "false",
                "manual_decision_id": "",
            }
            diagnostics[target] = diagnostic
            target_class_counts[diagnostic_class] += 1
            target_layer_counts[layer] += 1
            target_pattern_counts[(layer, diagnostic_class, distance, signature)] += 1
    if len(diagnostics) != int(agreement["counts"]["target_gate_classes"]["mismatch_not_eligible"]):
        raise RuntimeError("mismatch target coverage differs from agreement manifest")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True)
    target_output = temp_root / "g2p_mismatch_target_diagnostics.csv.gz"
    source_output = temp_root / "g2p_mismatch_source_diagnostics.csv.gz"
    pattern_output = temp_root / "g2p_mismatch_pattern_summary.csv"
    manifest_output = temp_root / "G2P_MISMATCH_DIAGNOSTICS_MANIFEST.json"
    final_target = output_root / target_output.name
    final_source = output_root / source_output.name
    final_pattern = output_root / pattern_output.name
    final_manifest = output_root / manifest_output.name

    with gzip_writer(target_output) as stream:
        writer = csv.DictWriter(stream, fieldnames=TARGET_DIAGNOSTIC_FIELDS, lineterminator="\n")
        writer.writeheader()
        for target in sorted(diagnostics):
            writer.writerow(diagnostics[target])

    pattern_aggregate: dict[tuple[str, str, int, str], dict[str, object]] = {
        key: {
            "targets": set(),
            "source_type_count": 0,
            "total_occurrences": 0,
            **{f"count_{year}": 0 for year in YEARS},
            "example_targets": [],
            "example_tokens": [],
        }
        for key in target_pattern_counts
    }
    source_rows = 0
    source_class_counts: Counter[str] = Counter()
    source_layer_counts: Counter[str] = Counter()
    with gzip.open(agreement_outputs["source_agreement"], "rt", encoding="utf-8-sig", newline="") as source_stream, gzip_writer(source_output) as target_stream:
        reader = csv.DictReader(source_stream)
        if tuple(reader.fieldnames or ()) != SOURCE_RESULT_FIELDS:
            raise RuntimeError("agreement source column contract mismatch")
        writer = csv.DictWriter(target_stream, fieldnames=SOURCE_DIAGNOSTIC_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            if clean(row["comparison_status"]) != "different_rule_roman":
                continue
            target = clean(row["target_hangul"])
            if target not in diagnostics:
                raise RuntimeError(f"source mismatch target missing: {row['token']}")
            diagnostic = diagnostics[target]
            output = {
                **row,
                "edit_signature": diagnostic["edit_signature"],
                "diagnostic_layer": diagnostic["diagnostic_layer"],
                "diagnostic_class": diagnostic["diagnostic_class"],
                "representation_equivalence_candidate": diagnostic["representation_equivalence_candidate"],
                "automatic_equivalence_approved": "false",
            }
            writer.writerow(output)
            source_rows += 1
            diagnostic_class = str(diagnostic["diagnostic_class"])
            layer = str(diagnostic["diagnostic_layer"])
            source_class_counts[diagnostic_class] += 1
            source_layer_counts[layer] += 1
            key = (layer, diagnostic_class, int(row["comparison_edit_distance"]), str(diagnostic["edit_signature"]))
            aggregate = pattern_aggregate[key]
            aggregate["targets"].add(target)
            aggregate["source_type_count"] += 1
            aggregate["total_occurrences"] += int(row["total_occurrences"])
            for year in YEARS:
                aggregate[f"count_{year}"] += int(row[f"count_{year}"])
            if len(aggregate["example_targets"]) < 5 and target not in aggregate["example_targets"]:
                aggregate["example_targets"].append(target)
            token = clean(row["token"])
            if len(aggregate["example_tokens"]) < 5 and token not in aggregate["example_tokens"]:
                aggregate["example_tokens"].append(token)
    if source_rows != int(agreement["counts"]["source_gate_classes"]["mismatch_not_eligible"]):
        raise RuntimeError("mismatch source coverage differs from agreement manifest")

    with pattern_output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PATTERN_SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for (layer, diagnostic_class, distance, signature), aggregate in sorted(
            pattern_aggregate.items(),
            key=lambda item: (-int(item[1]["total_occurrences"]), item[0]),
        ):
            writer.writerow(
                {
                    "diagnostic_layer": layer,
                    "diagnostic_class": diagnostic_class,
                    "comparison_edit_distance": distance,
                    "edit_signature": signature,
                    "target_count": len(aggregate["targets"]),
                    "source_type_count": aggregate["source_type_count"],
                    "total_occurrences": aggregate["total_occurrences"],
                    **{f"count_{year}": aggregate[f"count_{year}"] for year in YEARS},
                    "example_targets_json": json.dumps(aggregate["example_targets"], ensure_ascii=False),
                    "example_tokens_json": json.dumps(aggregate["example_tokens"], ensure_ascii=False),
                    "automatic_equivalence_approved": "false",
                }
            )

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_diagnostics_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "diagnostic_only": True,
            "representation_equivalence_candidate_is_approved": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "agreement_manifest": file_fingerprint(agreement_manifest_path, with_sha256=True),
            "target_agreement": file_fingerprint(agreement_outputs["target_agreement"], with_sha256=True),
            "source_agreement": file_fingerprint(agreement_outputs["source_agreement"], with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        },
        "counts": {
            "target_rows": len(diagnostics),
            "source_rows": source_rows,
            "pattern_rows": len(pattern_aggregate),
            "target_layers": dict(sorted(target_layer_counts.items())),
            "target_classes": dict(sorted(target_class_counts.items())),
            "source_layers": dict(sorted(source_layer_counts.items())),
            "source_classes": dict(sorted(source_class_counts.items())),
            "automatic_equivalence_approved": 0,
        },
        "outputs": {
            "target_diagnostics": fingerprint_for_final(target_output, final_target),
            "source_diagnostics": fingerprint_for_final(source_output, final_source),
            "pattern_summary": fingerprint_for_final(pattern_output, final_pattern),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    with manifest_output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temp_root, output_root)
    return json.loads(final_manifest.read_text(encoding="utf-8-sig"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--agreement-manifest", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = build_diagnostics(
        agreement_manifest_path=args.agreement_manifest.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
