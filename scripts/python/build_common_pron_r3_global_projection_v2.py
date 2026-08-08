"""Re-evaluate frozen r3 G2P targets with the full canonical exact donor pool.

This is a candidate-only comparison stage.  It reuses the already generated
G2P candidates, expands only the exact-context donor pool, and never selects a
canonical pronunciation, adopts a dictionary, runs MFA, or edits TextGrids.
"""

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

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    SOURCE_RESULT_FIELDS,
    TARGET_RESULT_FIELDS,
)
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    CONTEXT_LEVELS,
    EVIDENCE_FIELDS,
    SOURCE_PROJECTION_FIELDS,
    TARGET_PROJECTION_FIELDS,
    DonorObservation,
    ProjectionEvidence,
    context_key,
    donor_query_indices,
    project_mismatch,
    representation_relation,
    source_projection_route,
    unchanged_candidate,
)
from build_common_pron_r3_selection_readiness import READINESS_FIELDS  # noqa: E402
from phoneme_roman import expand_roman_eojeol, load_acoustic_meta, model_group_lookup  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_global_projection.v2"
POLICY_SCHEMA = "common_pron_r3_global_projection_policy.v2"
PRIOR_SCHEMA = "common_pron_r3_projection_candidates.v1"
READINESS_SCHEMA = "common_pron_r3_selection_readiness.v1"
COMPARISON_FIELDS = (
    "target_hangul",
    "total_occurrences",
    "previous_projection_status",
    "global_projection_status",
    "previous_candidate_count",
    "global_candidate_count",
    "previous_projected_pron_phones_json",
    "global_projected_pron_phones_json",
    "comparison_class",
    "candidate_is_final_selection",
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


def validate_policy(path: Path, acoustic_model: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "candidate_generation_only":
        raise RuntimeError("global projection policy differs")
    if tuple(str(item) for item in policy.get("scope_years", ())) != YEARS:
        raise RuntimeError("global projection year scope differs")
    frozen = policy.get("frozen_acoustic_model", {})
    if (
        Path(str(frozen.get("path", ""))).resolve() != acoustic_model.resolve()
        or clean(frozen.get("sha256")).lower() != sha256_file(acoustic_model).lower()
    ):
        raise RuntimeError("global projection acoustic model differs")
    target = policy.get("target_policy", {})
    if target.get("same_g2p_rerun_allowed") is not False or target.get("previous_projection_is_final_selection") is not False:
        raise RuntimeError("global projection target policy exceeds candidate scope")
    donor = policy.get("exact_context_donor_policy", {})
    if (
        tuple(donor.get("specificity_order", ())) != CONTEXT_LEVELS
        or int(donor.get("minimum_distinct_target_types", 0)) != 2
        or donor.get("mode_or_first_variant_selection_allowed") is not False
    ):
        raise RuntimeError("global donor policy differs")
    invariants = policy.get("invariants", {})
    required_false = (
        "candidate_is_final_selection",
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "source_files_modified",
        "actual_realization_claimed",
    )
    if any(invariants.get(key) is not False for key in required_false):
        raise RuntimeError("global projection policy exceeds candidate-only scope")
    return policy


def build_query_sets(
    prior_target_path: Path, group_lookup: dict[str, int]
) -> tuple[dict[str, set[tuple[object, ...]]], int]:
    query_sets = {level: set() for level in CONTEXT_LEVELS}
    rows = 0
    with gzip.open(prior_target_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_PROJECTION_FIELDS:
            raise RuntimeError("prior target projection column contract differs")
        for row in reader:
            rows += 1
            if row["comparison_status"] == "exact_rule_roman":
                continue
            phones = tuple(clean(row["g2p_candidate_phones"]).split())
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            _, operations = representation_relation(phones, rule, group_lookup)
            for rule_index in donor_query_indices(operations):
                for level in CONTEXT_LEVELS:
                    query_sets[level].add(context_key(rule, rule_index, level))
    return query_sets, rows


def build_global_donor_index(
    readiness_path: Path,
    query_sets: dict[str, set[tuple[object, ...]]],
    group_lookup: dict[str, int],
) -> tuple[dict[str, dict[tuple[object, ...], DonorObservation]], dict[str, int]]:
    index: dict[str, dict[tuple[object, ...], DonorObservation]] = {
        level: {} for level in CONTEXT_LEVELS
    }
    donor_types = donor_variants = donor_type_units = donor_variant_units = 0
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("selection-readiness column contract differs")
        for row in reader:
            if row["planning_status"] != "candidate_r2_exact_mandatory_rule":
                continue
            target = clean(row["token"])
            rule = tuple(expand_roman_eojeol(row["rule_pron_roman"]))
            variants = string_list(
                row["planning_candidate_phones_json"], label=f"donor phones {target}"
            )
            if not variants:
                raise RuntimeError(f"exact donor lacks phone variant: {target}")
            donor_types += 1
            donor_type_units += len(rule)
            seen_target_context: set[tuple[str, tuple[object, ...]]] = set()
            for variant in variants:
                phones = tuple(clean(variant).split())
                relation, _ = representation_relation(phones, rule, group_lookup)
                if relation != "exact_comparison_keys" or len(phones) != len(rule):
                    raise RuntimeError(f"canonical exact donor relation differs: {target}")
                donor_variants += 1
                donor_variant_units += len(rule)
                observe_donor_variant(
                    index=index,
                    query_sets=query_sets,
                    target=target,
                    phones=phones,
                    rule=rule,
                    seen_target_context=seen_target_context,
                )
    return index, {
        "donor_exact_target_rows": donor_types,
        "donor_exact_variant_rows": donor_variants,
        "donor_exact_target_units": donor_type_units,
        "donor_exact_variant_units": donor_variant_units,
    }


def observe_donor_variant(
    *,
    index: dict[str, dict[tuple[object, ...], DonorObservation]],
    query_sets: dict[str, set[tuple[object, ...]]],
    target: str,
    phones: Sequence[str],
    rule: Sequence[object],
    seen_target_context: set[tuple[str, tuple[object, ...]]],
) -> None:
    """Accumulate one verified exact variant while counting target support once."""

    for unit_index, phone in enumerate(phones):
        for level in CONTEXT_LEVELS:
            key = context_key(rule, unit_index, level)  # type: ignore[arg-type]
            if key not in query_sets[level]:
                continue
            observation = index[level].setdefault(key, DonorObservation())
            observation.phone_counts[phone] += 1
            observation.unit_count += 1
            marker = (level, key)
            if marker not in seen_target_context:
                observation.target_type_count += 1
                seen_target_context.add(marker)
            if target not in observation.examples and len(observation.examples) < 5:
                observation.examples.append(target)


def comparison_class(previous: dict[str, str], current: dict[str, object]) -> str:
    old_count = int(previous["projection_candidate_count"])
    new_count = int(current["projection_candidate_count"])
    old_phones = clean(previous["projected_pron_phones_json"])
    new_phones = clean(current["projected_pron_phones_json"])
    if (
        previous["projection_status"] == clean(current["projection_status"])
        and previous["representation_relation"] == clean(current["representation_relation"])
        and old_count == new_count
        and old_phones == new_phones
    ):
        return "unchanged"
    if old_count == 0 and new_count > 0:
        return "candidate_gained"
    if old_count > 0 and new_count == 0:
        return "candidate_lost"
    if old_count > 0 and new_count > 0 and old_phones != new_phones:
        return "candidate_phone_changed"
    return "status_metadata_changed"


def verify_existing(
    output_root: Path,
    *,
    readiness_manifest_path: Path,
    prior_projection_manifest_path: Path,
    policy_path: Path,
) -> dict[str, object]:
    manifest_path = output_root / "GLOBAL_PROJECTION_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"global projection root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("existing global projection is not reusable")
    for key, expected in (
        ("selection_readiness_manifest", readiness_manifest_path),
        ("prior_projection_manifest", prior_projection_manifest_path),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], expected, label=f"existing {key}")
    for key, record in manifest["outputs"].items():
        verify_fingerprint(record, Path(str(record["path"])), label=f"existing output {key}")
    return manifest


def build_global_projection(
    *,
    readiness_manifest_path: Path,
    prior_projection_manifest_path: Path,
    policy_path: Path,
    output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            readiness_manifest_path=readiness_manifest_path,
            prior_projection_manifest_path=prior_projection_manifest_path,
            policy_path=policy_path,
        )
    readiness = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    prior = json.loads(prior_projection_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness.get("schema_version") != READINESS_SCHEMA or readiness.get("status") != "success_planning_not_selected":
        raise RuntimeError("selection-readiness input differs")
    if prior.get("schema_version") != PRIOR_SCHEMA or prior.get("status") != "success_candidates_not_selected":
        raise RuntimeError("prior projection input differs")
    if readiness.get("scope", {}).get("planning_candidate_is_final_selection") is not False:
        raise RuntimeError("selection-readiness exceeded planning scope")
    readiness_path = Path(str(readiness["outputs"]["selection_readiness"]["path"])).resolve()
    prior_target = Path(str(prior["outputs"]["target_projection_candidates"]["path"])).resolve()
    prior_source = Path(str(prior["outputs"]["source_projection_candidates"]["path"])).resolve()
    acoustic_model = Path(str(prior["inputs"]["acoustic_model"]["path"])).resolve()
    for record, path, label in (
        (readiness["outputs"]["selection_readiness"], readiness_path, "selection readiness"),
        (prior["outputs"]["target_projection_candidates"], prior_target, "prior target"),
        (prior["outputs"]["source_projection_candidates"], prior_source, "prior source"),
        (prior["inputs"]["acoustic_model"], acoustic_model, "acoustic model"),
    ):
        verify_fingerprint(record, path, label=label)
    validate_policy(policy_path, acoustic_model)
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))
    query_sets, prior_target_rows = build_query_sets(prior_target, group_lookup)
    donor_index, donor_counts = build_global_donor_index(
        readiness_path, query_sets, group_lookup
    )

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    target_output = temp_root / "g2p_target_global_projection_candidates.csv.gz"
    source_output = temp_root / "g2p_source_global_projection_candidates.csv.gz"
    evidence_output = temp_root / "global_exact_context_projection_evidence.csv"
    comparison_output = temp_root / "projection_v1_to_global_v2_comparison.csv.gz"
    manifest_output = temp_root / "GLOBAL_PROJECTION_MANIFEST.json"
    final_target = output_root / target_output.name
    final_source = output_root / source_output.name
    final_evidence = output_root / evidence_output.name
    final_comparison = output_root / comparison_output.name
    final_manifest = output_root / manifest_output.name

    target_lookup: dict[str, tuple[str, str, int, str, str]] = {}
    target_status: Counter[str] = Counter()
    target_relation: Counter[str] = Counter()
    target_occurrences: Counter[str] = Counter()
    comparison_counts: Counter[str] = Counter()
    comparison_occurrences: Counter[str] = Counter()
    used_evidence: dict[str, ProjectionEvidence] = {}
    with gzip.open(prior_target, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(target_output) as target, gzip_writer(comparison_output) as comparison:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != TARGET_PROJECTION_FIELDS:
            raise RuntimeError("prior target column contract differs")
        writer = csv.DictWriter(target, fieldnames=TARGET_PROJECTION_FIELDS, lineterminator="\n")
        compare_writer = csv.DictWriter(comparison, fieldnames=COMPARISON_FIELDS, lineterminator="\n")
        writer.writeheader()
        compare_writer.writeheader()
        for row in reader:
            target_hangul = clean(row["target_hangul"])
            if row["comparison_status"] == "exact_rule_roman":
                projection = unchanged_candidate(
                    row,
                    relation="exact_comparison_keys",
                    status="candidate_exact_gate_unchanged",
                )
            else:
                projection = project_mismatch(
                    row=row,
                    donor_index=donor_index,
                    group_lookup=group_lookup,
                    used_evidence=used_evidence,
                )
            output = {
                **{
                    field: row[field]
                    for field in TARGET_PROJECTION_FIELDS[: len(TARGET_RESULT_FIELDS) + 3]
                },
                **projection,
                "projection_candidate_is_final_selection": "false",
            }
            if set(output) != set(TARGET_PROJECTION_FIELDS):
                raise RuntimeError(f"global target output fields differ: {target_hangul}")
            writer.writerow(output)
            category = comparison_class(row, projection)
            compare_writer.writerow(
                {
                    "target_hangul": target_hangul,
                    "total_occurrences": row["total_occurrences"],
                    "previous_projection_status": row["projection_status"],
                    "global_projection_status": projection["projection_status"],
                    "previous_candidate_count": row["projection_candidate_count"],
                    "global_candidate_count": projection["projection_candidate_count"],
                    "previous_projected_pron_phones_json": row["projected_pron_phones_json"],
                    "global_projected_pron_phones_json": projection["projected_pron_phones_json"],
                    "comparison_class": category,
                    "candidate_is_final_selection": "false",
                }
            )
            count = int(projection["projection_candidate_count"])
            status = clean(projection["projection_status"])
            relation = clean(projection["representation_relation"])
            phones_json = clean(projection["projected_pron_phones_json"])
            romans_json = clean(projection["projected_pron_roman_json"])
            target_lookup[target_hangul] = (status, relation, count, phones_json, romans_json)
            target_status[status] += 1
            target_relation[relation] += 1
            target_occurrences[status] += int(row["total_occurrences"])
            comparison_counts[category] += 1
            comparison_occurrences[category] += int(row["total_occurrences"])
    if len(target_lookup) != prior_target_rows:
        raise RuntimeError("global target coverage differs")

    source_status: Counter[str] = Counter()
    source_occurrences: Counter[str] = Counter()
    source_rows = 0
    with gzip.open(prior_source, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(source_output) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS:
            raise RuntimeError("prior source column contract differs")
        writer = csv.DictWriter(target, fieldnames=SOURCE_PROJECTION_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            base = {field: row[field] for field in SOURCE_RESULT_FIELDS}
            linked = target_lookup.get(base["target_hangul"])
            if linked is None:
                raise RuntimeError(f"global source target missing: {base['token']}")
            status, relation, count, phones_json, romans_json = linked
            route, dictionary_agreement = source_projection_route(base, target_candidate_count=count)
            output = {
                **base,
                "target_representation_relation": relation,
                "target_projection_status": status,
                "target_projection_candidate_count": str(count),
                "projected_pron_phones_json": phones_json,
                "projected_pron_roman_json": romans_json,
                "source_projection_gate_class": route,
                "dictionary_rule_agreement": str(dictionary_agreement).lower(),
                "projection_candidate_is_final_selection": "false",
            }
            writer.writerow(output)
            source_rows += 1
            source_status[route] += 1
            source_occurrences[route] += int(base["total_occurrences"])

    with evidence_output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVIDENCE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for identifier in sorted(used_evidence):
            evidence = used_evidence[identifier]
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

    counts = {
        "target_rows": len(target_lookup),
        "source_rows": source_rows,
        **donor_counts,
        "query_contexts": {level: len(query_sets[level]) for level in CONTEXT_LEVELS},
        "indexed_query_contexts": {level: len(donor_index[level]) for level in CONTEXT_LEVELS},
        "used_projection_evidence_rows": len(used_evidence),
        "target_projection_status": dict(sorted(target_status.items())),
        "target_representation_relation": dict(sorted(target_relation.items())),
        "target_occurrences_by_projection_status": dict(sorted(target_occurrences.items())),
        "comparison_class_types": dict(sorted(comparison_counts.items())),
        "comparison_class_occurrences": dict(sorted(comparison_occurrences.items())),
        "source_projection_gate_class": dict(sorted(source_status.items())),
        "source_occurrences_by_gate_class": dict(sorted(source_occurrences.items())),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_candidates_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "same_g2p_rerun_performed": False,
            "global_exact_donor_projection_applied": True,
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "selection_readiness_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "prior_projection_manifest": file_fingerprint(prior_projection_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "selection_readiness": file_fingerprint(readiness_path, with_sha256=True),
            "prior_target_projection": file_fingerprint(prior_target, with_sha256=True),
            "prior_source_projection": file_fingerprint(prior_source, with_sha256=True),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        },
        "counts": counts,
        "outputs": {
            "target_global_projection": fingerprint_for_final(target_output, final_target),
            "source_global_projection": fingerprint_for_final(source_output, final_source),
            "global_projection_evidence": fingerprint_for_final(evidence_output, final_evidence),
            "projection_comparison": fingerprint_for_final(comparison_output, final_comparison),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_output, manifest)
    os.replace(temp_root, output_root)
    return json.loads(final_manifest.read_text(encoding="utf-8-sig"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--selection-readiness-manifest", type=Path, required=True)
    result.add_argument("--prior-projection-manifest", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_global_projection(
        readiness_manifest_path=args.selection_readiness_manifest.resolve(),
        prior_projection_manifest_path=args.prior_projection_manifest.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
