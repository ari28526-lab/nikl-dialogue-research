"""Classify unanimous contextual holds that still require an r2 phone edit.

This is a read-only Stage 15 audit.  It converts neither dictionary evidence
nor corpus frequency into a pronunciation candidate.  Instead, it inventories
the insertion/substitution mechanism and routes each token to the next narrow
linguistic/model audit while preserving the readiness-v3 zero-fallback hold.
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
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_contextual_dictionary_donor_audit import (  # noqa: E402
    CLASS_UNANIMOUS,
    HOLD_FIELDS,
    ISSUE_FIELDS,
    SCHEMA_VERSION as CONTEXT_SCHEMA,
)
from build_common_pron_r3_selection_readiness_v3 import (  # noqa: E402
    OUTPUT_FIELDS as READINESS_FIELDS,
    SCHEMA_VERSION as READINESS_SCHEMA,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_unanimous_phone_change_audit.v1"
POLICY_SCHEMA = "common_pron_r3_unanimous_phone_change_audit_policy.v1"
STATUS = "success_audited_not_candidate"
TARGET_HOLD_STATUSES = {
    "hold_target_projection_unresolved",
    "hold_no_surface_rule_substantive_mismatch",
}

ISSUE_AUDIT_FIELDS = (
    *ISSUE_FIELDS,
    "edit_mechanism",
    "rule_unit_family",
    "supported_donor_phones_json",
    "research_evidence_route",
    "automatic_candidate_eligible",
)

TOKEN_AUDIT_FIELDS = (
    "token",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
    "rule_pron_hangul",
    "rule_pron_roman",
    "surface_rule_names",
    "r2_pron_phones_json",
    "r2_pron_roman_json",
    "r2_pron_source",
    "planning_status",
    "audited_variant_count",
    "audited_issue_count",
    "unsupported_issue_count",
    "insertion_issue_count",
    "substitution_issue_count",
    "secondary_articulation_substitution_issue_count",
    "edit_mechanisms_json",
    "rule_unit_families_json",
    "primary_audit_route",
    "research_evidence_routes_json",
    "issue_evidence_json",
    "researcher_review_required_now",
    "automatic_candidate_eligible",
    "planning_zero_fallback_hold_preserved",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
    "canonical_selection_performed",
)

SUMMARY_FIELDS = (
    "primary_audit_route",
    "type_count",
    "occurrence_count",
    "example_tokens_json",
    "automatic_candidate_eligible",
)

UI_UNITS = {"EU_G"}
GLIDE_UNITS = {"Y", "W"}
VELAR_NASAL_UNITS = {"ng"}
CODA_OR_SONORANT_UNITS = {"k", "t", "p", "l", "m", "n", "R"}
ONSET_UNITS = {
    "G", "K", "KK", "B", "P", "PP", "D", "T", "TT",
    "J", "CH", "JJ", "S", "SS", "H", "M", "N",
}
VOWEL_UNITS = {"A", "AE", "E", "EO", "I", "O", "U", "EU"}

csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def parse_json_list(value: object, *, label: str) -> list[object]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON list: {label}") from exc
    if not isinstance(result, list):
        raise RuntimeError(f"expected JSON list: {label}")
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


def rule_unit_family(relation_kind: str, units: list[str]) -> str:
    unit_set = set(units)
    if relation_kind == "secondary_articulation_cluster":
        return "secondary_articulation_cluster"
    if unit_set and unit_set <= UI_UNITS:
        return "ui_glide_component"
    if unit_set and unit_set <= GLIDE_UNITS:
        return "compound_vowel_glide_component"
    if unit_set and unit_set <= VELAR_NASAL_UNITS:
        return "velar_nasal_unit"
    if unit_set and unit_set <= CODA_OR_SONORANT_UNITS:
        return "coda_or_sonorant_unit"
    if unit_set and unit_set <= ONSET_UNITS:
        return "onset_laryngeal_or_manner_unit"
    if unit_set and unit_set <= VOWEL_UNITS:
        return "vowel_quality_or_length_unit"
    return "other_rule_unit"


def edit_mechanism(row: dict[str, str]) -> str:
    if row["relation_kind"] == "secondary_articulation_cluster":
        return "secondary_articulation_substitution"
    if not clean(row["current_candidate_phone"]):
        return "segment_insertion"
    return "segment_substitution"


def evidence_route(mechanism: str) -> str:
    if mechanism == "segment_insertion":
        return "audit_rule_parser_and_model_unitization"
    if mechanism == "secondary_articulation_substitution":
        return "audit_contextual_model_allophone_relation"
    return "audit_dictionary_rule_and_model_phone_relation"


def primary_route(mechanisms: set[str], families: set[str]) -> str:
    if len(mechanisms) != 1 or len(families) != 1:
        return "multi_operation_mixed_edit"
    mechanism = next(iter(mechanisms))
    family = next(iter(families))
    if mechanism == "segment_insertion":
        return {
            "ui_glide_component": "ui_glide_component_insertion",
            "compound_vowel_glide_component": "compound_vowel_glide_insertion",
            "velar_nasal_unit": "velar_nasal_insertion",
            "coda_or_sonorant_unit": "coda_or_sonorant_insertion",
        }.get(family, "other_segment_insertion")
    if mechanism == "secondary_articulation_substitution":
        return "secondary_articulation_substitution"
    return {
        "onset_laryngeal_or_manner_unit": "onset_laryngeal_or_manner_substitution",
        "vowel_quality_or_length_unit": "vowel_quality_or_length_substitution",
        "velar_nasal_unit": "nasal_or_coda_substitution",
        "coda_or_sonorant_unit": "nasal_or_coda_substitution",
    }.get(family, "other_segment_substitution")


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "read_only_audit_only"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
    ):
        raise RuntimeError("Stage 15 policy identity differs")
    contract = policy.get("input_contract", {})
    if (
        contract.get("required_contextual_support_class") != CLASS_UNANIMOUS
        or contract.get("required_candidate_eligible_flag") is not False
        or contract.get("required_zero_fallback_hold_flag") is not True
        or int(contract.get("expected_types", 0)) != 4453
        or int(contract.get("expected_occurrences", 0)) != 72030
    ):
        raise RuntimeError("Stage 15 input contract differs")
    if any(value is not True for value in policy.get("routing_policy", {}).values()):
        raise RuntimeError("Stage 15 routing policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("Stage 15 policy exceeds read-only scope")
    return policy


def load_context_rows(
    classification_path: Path, evidence_path: Path
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    classifications: dict[str, dict[str, str]] = {}
    with gzip.open(classification_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != HOLD_FIELDS:
            raise RuntimeError("contextual classification columns differ")
        for row in reader:
            if row["token"] in classifications:
                raise RuntimeError(f"duplicate contextual classification: {row['token']}")
            classifications[row["token"]] = row
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)
    with gzip.open(evidence_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != ISSUE_FIELDS:
            raise RuntimeError("contextual evidence columns differ")
        for row in reader:
            evidence[row["token"]].append(row)
    if set(evidence) - set(classifications):
        raise RuntimeError("contextual evidence contains unknown tokens")
    return classifications, evidence


def verify_existing(
    output_root: Path, *, readiness_manifest_path: Path,
    contextual_manifest_path: Path, policy_path: Path,
) -> dict[str, object]:
    manifest_path = output_root / "UNANIMOUS_PHONE_CHANGE_AUDIT_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Stage 15 root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RuntimeError("existing Stage 15 manifest differs")
    for key, path in (
        ("readiness_v3_manifest", readiness_manifest_path),
        ("contextual_donor_manifest", contextual_manifest_path),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
    for key in ("token_inventory", "issue_inventory", "route_summary"):
        record = manifest["outputs"][key]
        verify_fingerprint(record, Path(str(record["path"])), label=f"existing {key}")
    return manifest


def build_audit(
    *, readiness_manifest_path: Path, contextual_manifest_path: Path,
    policy_path: Path, output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            readiness_manifest_path=readiness_manifest_path,
            contextual_manifest_path=contextual_manifest_path,
            policy_path=policy_path,
        )
    policy = validate_policy(policy_path)
    readiness_manifest = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    context_manifest = json.loads(contextual_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness_manifest.get("schema_version") != READINESS_SCHEMA:
        raise RuntimeError("readiness v3 identity differs")
    if readiness_manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("readiness v3 is not a planning result")
    if context_manifest.get("schema_version") != CONTEXT_SCHEMA or context_manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("contextual donor audit identity differs")

    readiness_path = Path(str(readiness_manifest["outputs"]["selection_readiness_v3"]["path"])).resolve()
    classification_path = Path(str(context_manifest["outputs"]["residual_hold_contextual_classification"]["path"])).resolve()
    evidence_path = Path(str(context_manifest["outputs"]["residual_hold_contextual_evidence"]["path"])).resolve()
    for record, path, label in (
        (readiness_manifest["outputs"]["selection_readiness_v3"], readiness_path, "readiness v3"),
        (context_manifest["outputs"]["residual_hold_contextual_classification"], classification_path, "classification"),
        (context_manifest["outputs"]["residual_hold_contextual_evidence"], evidence_path, "evidence"),
    ):
        verify_fingerprint(record, path, label=label)
    classifications, evidence = load_context_rows(classification_path, evidence_path)

    targets: dict[str, dict[str, str]] = {}
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness v3 column contract differs")
        for row in reader:
            is_target = (
                row["contextual_donor_support_class"] == CLASS_UNANIMOUS
                and row["contextual_secondary_articulation_candidate_eligible"] == "false"
                and row["planning_zero_fallback_hold"] == "true"
            )
            if is_target:
                if row["planning_status"] not in TARGET_HOLD_STATUSES:
                    raise RuntimeError(f"unexpected Stage 15 planning status: {row['token']}")
                targets[row["token"]] = row

    expected = policy["input_contract"]
    occurrence_count = sum(int(row["total_occurrences"]) for row in targets.values())
    if len(targets) != int(expected["expected_types"]) or occurrence_count != int(expected["expected_occurrences"]):
        raise RuntimeError("Stage 15 target accounting differs")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    token_output = temp_root / "unanimous_phone_change_token_inventory.csv.gz"
    issue_output = temp_root / "unanimous_phone_change_issue_inventory.csv.gz"
    summary_output = temp_root / "unanimous_phone_change_route_summary.csv"
    final_token = output_root / token_output.name
    final_issue = output_root / issue_output.name
    final_summary = output_root / summary_output.name

    audited_issues: dict[str, list[dict[str, object]]] = defaultdict(list)
    issue_mechanisms: Counter[str] = Counter()
    issue_families: Counter[str] = Counter()
    unsupported_issue_count = 0
    with gzip_writer(issue_output) as stream:
        writer = csv.DictWriter(stream, fieldnames=ISSUE_AUDIT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for token in sorted(targets):
            classification = classifications.get(token)
            rows = evidence.get(token, [])
            if classification is None or classification["contextual_support_class"] != CLASS_UNANIMOUS:
                raise RuntimeError(f"Stage 15 classification differs: {token}")
            if int(classification["audited_variant_count"]) != 1 or not rows:
                raise RuntimeError(f"Stage 15 evidence scope differs: {token}")
            for source in rows:
                if source["evidence_class"] != CLASS_UNANIMOUS:
                    raise RuntimeError(f"non-unanimous issue in Stage 15: {token}")
                if source["current_candidate_supported"] == "true":
                    continue
                units = [str(item) for item in parse_json_list(source["rule_units_json"], label=f"rule units {token}")]
                mechanism = edit_mechanism(source)
                family = rule_unit_family(source["relation_kind"], units)
                canonical = json.loads(source["canonical_phone_counts_json"] or "{}")
                frozen = json.loads(source["frozen_phone_counts_json"] or "{}")
                donor_phones = sorted(set(canonical) | set(frozen))
                if len(donor_phones) != 1:
                    raise RuntimeError(f"unanimous donor phone count differs: {token}")
                updated: dict[str, object] = dict(source)
                updated.update(
                    {
                        "edit_mechanism": mechanism,
                        "rule_unit_family": family,
                        "supported_donor_phones_json": json.dumps(donor_phones, ensure_ascii=False),
                        "research_evidence_route": evidence_route(mechanism),
                        "automatic_candidate_eligible": "false",
                    }
                )
                writer.writerow(updated)
                audited_issues[token].append(updated)
                issue_mechanisms[mechanism] += 1
                issue_families[family] += 1
                unsupported_issue_count += 1

    route_types: Counter[str] = Counter()
    route_occurrences: Counter[str] = Counter()
    route_examples: dict[str, list[str]] = defaultdict(list)
    with gzip_writer(token_output) as stream:
        writer = csv.DictWriter(stream, fieldnames=TOKEN_AUDIT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for token in sorted(targets):
            source = targets[token]
            classification = classifications[token]
            issues = audited_issues.get(token, [])
            if not issues:
                raise RuntimeError(f"Stage 15 target has no unsupported issue: {token}")
            mechanisms = {str(row["edit_mechanism"]) for row in issues}
            families = {str(row["rule_unit_family"]) for row in issues}
            routes = {str(row["research_evidence_route"]) for row in issues}
            route = primary_route(mechanisms, families)
            total = int(source["total_occurrences"])
            route_types[route] += 1
            route_occurrences[route] += total
            if len(route_examples[route]) < 10:
                route_examples[route].append(token)
            compact_issues = [
                {
                    "issue_index": int(row["issue_index"]),
                    "relation_kind": row["relation_kind"],
                    "rule_units": json.loads(row["rule_units_json"]),
                    "current_phone": row["current_candidate_phone"],
                    "supported_donor_phones": json.loads(str(row["supported_donor_phones_json"])),
                    "edit_mechanism": row["edit_mechanism"],
                    "rule_unit_family": row["rule_unit_family"],
                }
                for row in issues
            ]
            output_row: dict[str, object] = {
                "token": token,
                "total_occurrences": source["total_occurrences"],
                "n_years_present": source["n_years_present"],
                **{f"count_{year}": source[f"count_{year}"] for year in YEARS},
                "rule_pron_hangul": source["rule_pron_hangul"],
                "rule_pron_roman": source["rule_pron_roman"],
                "surface_rule_names": source["surface_rule_names"],
                "r2_pron_phones_json": source["r2_pron_phones_json"],
                "r2_pron_roman_json": source["r2_pron_roman_json"],
                "r2_pron_source": source["r2_pron_source"],
                "planning_status": source["planning_status"],
                "audited_variant_count": classification["audited_variant_count"],
                "audited_issue_count": classification["audited_issue_count"],
                "unsupported_issue_count": len(issues),
                "insertion_issue_count": sum(row["edit_mechanism"] == "segment_insertion" for row in issues),
                "substitution_issue_count": sum(row["edit_mechanism"] == "segment_substitution" for row in issues),
                "secondary_articulation_substitution_issue_count": sum(row["edit_mechanism"] == "secondary_articulation_substitution" for row in issues),
                "edit_mechanisms_json": json.dumps(sorted(mechanisms), ensure_ascii=False),
                "rule_unit_families_json": json.dumps(sorted(families), ensure_ascii=False),
                "primary_audit_route": route,
                "research_evidence_routes_json": json.dumps(sorted(routes), ensure_ascii=False),
                "issue_evidence_json": json.dumps(compact_issues, ensure_ascii=False),
                "researcher_review_required_now": "false",
                "automatic_candidate_eligible": "false",
                "planning_zero_fallback_hold_preserved": "true",
                "standard_pronunciation_claimed": "false",
                "actual_realization_claimed": "false",
                "candidate_generation_performed": "false",
                "canonical_selection_performed": "false",
            }
            writer.writerow(output_row)

    with summary_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for route in sorted(route_types, key=lambda key: (-route_occurrences[key], key)):
            writer.writerow(
                {
                    "primary_audit_route": route,
                    "type_count": route_types[route],
                    "occurrence_count": route_occurrences[route],
                    "example_tokens_json": json.dumps(route_examples[route], ensure_ascii=False),
                    "automatic_candidate_eligible": "false",
                }
            )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "scope": {
            "target_is_unanimous_contextual_hold_requiring_phone_change": True,
            "readiness_v3_hold_preserved": True,
            **policy["invariants"],
        },
        "inputs": {
            "readiness_v3_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "contextual_donor_manifest": file_fingerprint(contextual_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "readiness_v3": file_fingerprint(readiness_path, with_sha256=True),
            "contextual_classification": file_fingerprint(classification_path, with_sha256=True),
            "contextual_evidence": file_fingerprint(evidence_path, with_sha256=True),
        },
        "counts": {
            "target_types": len(targets),
            "target_occurrences": occurrence_count,
            "unsupported_issue_rows": unsupported_issue_count,
            "edit_mechanism_issue_rows": dict(sorted(issue_mechanisms.items())),
            "rule_unit_family_issue_rows": dict(sorted(issue_families.items())),
            "primary_audit_route_types": dict(sorted(route_types.items())),
            "primary_audit_route_occurrences": dict(sorted(route_occurrences.items())),
            "automatic_candidate_types": 0,
            "preserved_zero_fallback_hold_types": len(targets),
        },
        "outputs": {
            "token_inventory": fingerprint_for_final(token_output, final_token),
            "issue_inventory": fingerprint_for_final(issue_output, final_issue),
            "route_summary": fingerprint_for_final(summary_output, final_summary),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "UNANIMOUS_PHONE_CHANGE_AUDIT_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--readiness-v3-manifest", type=Path, required=True)
    result.add_argument("--contextual-donor-manifest", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_audit(
        readiness_manifest_path=args.readiness_v3_manifest.resolve(),
        contextual_manifest_path=args.contextual_donor_manifest.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
