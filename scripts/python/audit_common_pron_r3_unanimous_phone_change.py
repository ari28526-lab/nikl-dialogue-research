"""Independently audit the read-only Stage 15 phone-change taxonomy."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_r3_contextual_dictionary_donor_audit import (  # noqa: E402
    CLASS_UNANIMOUS,
    ISSUE_FIELDS,
)
from build_common_pron_r3_selection_readiness_v3 import (  # noqa: E402
    OUTPUT_FIELDS as READINESS_FIELDS,
)
from build_common_pron_r3_unanimous_phone_change_audit import (  # noqa: E402
    ISSUE_AUDIT_FIELDS,
    SCHEMA_VERSION,
    STATUS,
    SUMMARY_FIELDS,
    TOKEN_AUDIT_FIELDS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
)


AUDIT_SCHEMA = "common_pron_r3_unanimous_phone_change_independent_audit.v1"
UI = {"EU_G"}
GLIDE = {"Y", "W"}
NG = {"ng"}
CODA = {"k", "t", "p", "l", "m", "n", "R"}
ONSET = {
    "G", "K", "KK", "B", "P", "PP", "D", "T", "TT",
    "J", "CH", "JJ", "S", "SS", "H", "M", "N",
}
VOWEL = {"A", "AE", "E", "EO", "I", "O", "U", "EU"}
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


def independent_mechanism(row: dict[str, str]) -> str:
    if row["relation_kind"] == "secondary_articulation_cluster":
        return "secondary_articulation_substitution"
    return "segment_substitution" if clean(row["current_candidate_phone"]) else "segment_insertion"


def independent_family(relation: str, units: list[str]) -> str:
    values = set(units)
    if relation == "secondary_articulation_cluster":
        return "secondary_articulation_cluster"
    for accepted, name in (
        (UI, "ui_glide_component"),
        (GLIDE, "compound_vowel_glide_component"),
        (NG, "velar_nasal_unit"),
        (CODA, "coda_or_sonorant_unit"),
        (ONSET, "onset_laryngeal_or_manner_unit"),
        (VOWEL, "vowel_quality_or_length_unit"),
    ):
        if values and values.issubset(accepted):
            return name
    return "other_rule_unit"


def independent_evidence_route(mechanism: str) -> str:
    return {
        "segment_insertion": "audit_rule_parser_and_model_unitization",
        "segment_substitution": "audit_dictionary_rule_and_model_phone_relation",
        "secondary_articulation_substitution": "audit_contextual_model_allophone_relation",
    }[mechanism]


def independent_primary_route(mechanisms: set[str], families: set[str]) -> str:
    if len(mechanisms) != 1 or len(families) != 1:
        return "multi_operation_mixed_edit"
    mechanism = next(iter(mechanisms))
    family = next(iter(families))
    if mechanism == "segment_insertion":
        mapping = {
            "ui_glide_component": "ui_glide_component_insertion",
            "compound_vowel_glide_component": "compound_vowel_glide_insertion",
            "velar_nasal_unit": "velar_nasal_insertion",
            "coda_or_sonorant_unit": "coda_or_sonorant_insertion",
        }
        return mapping.get(family, "other_segment_insertion")
    if mechanism == "secondary_articulation_substitution":
        return "secondary_articulation_substitution"
    mapping = {
        "onset_laryngeal_or_manner_unit": "onset_laryngeal_or_manner_substitution",
        "vowel_quality_or_length_unit": "vowel_quality_or_length_substitution",
        "velar_nasal_unit": "nasal_or_coda_substitution",
        "coda_or_sonorant_unit": "nasal_or_coda_substitution",
    }
    return mapping.get(family, "other_segment_substitution")


def audit(manifest_path: Path, output: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RuntimeError("Stage 15 manifest identity differs")
    scope = manifest.get("scope", {})
    required_true = (
        "target_is_unanimous_contextual_hold_requiring_phone_change",
        "readiness_v3_hold_preserved",
    )
    required_false = (
        "candidate_generation_performed",
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "source_files_modified",
        "standard_pronunciation_claimed",
        "actual_realization_claimed",
    )
    if any(scope.get(key) is not True for key in required_true) or any(
        scope.get(key) is not False for key in required_false
    ):
        raise RuntimeError("Stage 15 scope invariants differ")

    readiness_path = verify(manifest["inputs"]["readiness_v3"], label="readiness v3")
    evidence_path = verify(manifest["inputs"]["contextual_evidence"], label="contextual evidence")
    token_path = verify(manifest["outputs"]["token_inventory"], label="token inventory")
    issue_path = verify(manifest["outputs"]["issue_inventory"], label="issue inventory")
    summary_path = verify(manifest["outputs"]["route_summary"], label="route summary")
    verify(manifest["inputs"]["readiness_v3_manifest"], label="readiness manifest")
    verify(manifest["inputs"]["contextual_donor_manifest"], label="context manifest")
    verify(manifest["inputs"]["contextual_classification"], label="context classification")
    verify(manifest["inputs"]["policy_contract"], label="policy")

    targets: dict[str, dict[str, str]] = {}
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness v3 fields differ")
        for row in reader:
            if (
                row["contextual_donor_support_class"] == CLASS_UNANIMOUS
                and row["contextual_secondary_articulation_candidate_eligible"] == "false"
                and row["planning_zero_fallback_hold"] == "true"
            ):
                targets[row["token"]] = row
    if len(targets) != 4453 or sum(int(row["total_occurrences"]) for row in targets.values()) != 72030:
        raise RuntimeError("independent Stage 15 target accounting differs")

    source_issues: dict[tuple[str, str, str], dict[str, str]] = {}
    with gzip.open(evidence_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != ISSUE_FIELDS:
            raise RuntimeError("source issue fields differ")
        for row in reader:
            if row["token"] in targets and row["current_candidate_supported"] == "false":
                key = (row["token"], row["variant_index"], row["issue_index"])
                source_issues[key] = row

    audited_by_token: dict[str, list[dict[str, str]]] = defaultdict(list)
    mechanisms: Counter[str] = Counter()
    families: Counter[str] = Counter()
    seen_issues: set[tuple[str, str, str]] = set()
    with gzip.open(issue_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != ISSUE_AUDIT_FIELDS:
            raise RuntimeError("Stage 15 issue fields differ")
        for row in reader:
            key = (row["token"], row["variant_index"], row["issue_index"])
            source = source_issues.get(key)
            if source is None or key in seen_issues:
                raise RuntimeError(f"Stage 15 issue identity differs: {key}")
            seen_issues.add(key)
            if any(row[field] != source[field] for field in ISSUE_FIELDS):
                raise RuntimeError(f"Stage 15 source issue changed: {key}")
            units = json.loads(row["rule_units_json"])
            mechanism = independent_mechanism(row)
            family = independent_family(row["relation_kind"], units)
            canonical = json.loads(row["canonical_phone_counts_json"] or "{}")
            frozen = json.loads(row["frozen_phone_counts_json"] or "{}")
            donor_phones = sorted(set(canonical) | set(frozen))
            if (
                row["edit_mechanism"] != mechanism
                or row["rule_unit_family"] != family
                or json.loads(row["supported_donor_phones_json"]) != donor_phones
                or len(donor_phones) != 1
                or row["research_evidence_route"] != independent_evidence_route(mechanism)
                or row["automatic_candidate_eligible"] != "false"
            ):
                raise RuntimeError(f"Stage 15 issue taxonomy differs: {key}")
            mechanisms[mechanism] += 1
            families[family] += 1
            audited_by_token[row["token"]].append(row)
    if seen_issues != set(source_issues):
        raise RuntimeError("Stage 15 unsupported issue coverage differs")

    route_types: Counter[str] = Counter()
    route_occurrences: Counter[str] = Counter()
    seen_tokens: set[str] = set()
    with gzip.open(token_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TOKEN_AUDIT_FIELDS:
            raise RuntimeError("Stage 15 token fields differ")
        for row in reader:
            token = row["token"]
            source = targets.get(token)
            if source is None or token in seen_tokens:
                raise RuntimeError(f"Stage 15 token identity differs: {token}")
            seen_tokens.add(token)
            issues = audited_by_token.get(token, [])
            issue_mechanisms = {item["edit_mechanism"] for item in issues}
            issue_families = {item["rule_unit_family"] for item in issues}
            routes = {item["research_evidence_route"] for item in issues}
            route = independent_primary_route(issue_mechanisms, issue_families)
            if (
                not issues
                or row["total_occurrences"] != source["total_occurrences"]
                or row["planning_status"] != source["planning_status"]
                or int(row["unsupported_issue_count"]) != len(issues)
                or int(row["insertion_issue_count"]) != sum(item["edit_mechanism"] == "segment_insertion" for item in issues)
                or int(row["substitution_issue_count"]) != sum(item["edit_mechanism"] == "segment_substitution" for item in issues)
                or int(row["secondary_articulation_substitution_issue_count"]) != sum(item["edit_mechanism"] == "secondary_articulation_substitution" for item in issues)
                or json.loads(row["edit_mechanisms_json"]) != sorted(issue_mechanisms)
                or json.loads(row["rule_unit_families_json"]) != sorted(issue_families)
                or json.loads(row["research_evidence_routes_json"]) != sorted(routes)
                or row["primary_audit_route"] != route
                or row["automatic_candidate_eligible"] != "false"
                or row["planning_zero_fallback_hold_preserved"] != "true"
                or row["researcher_review_required_now"] != "false"
                or any(row[key] != "false" for key in (
                    "standard_pronunciation_claimed",
                    "actual_realization_claimed",
                    "candidate_generation_performed",
                    "canonical_selection_performed",
                ))
            ):
                raise RuntimeError(f"Stage 15 token audit differs: {token}")
            route_types[route] += 1
            route_occurrences[route] += int(row["total_occurrences"])
    if seen_tokens != set(targets):
        raise RuntimeError("Stage 15 token coverage differs")

    summary_types: dict[str, int] = {}
    summary_occurrences: dict[str, int] = {}
    with summary_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SUMMARY_FIELDS:
            raise RuntimeError("Stage 15 summary fields differ")
        for row in reader:
            route = row["primary_audit_route"]
            summary_types[route] = int(row["type_count"])
            summary_occurrences[route] = int(row["occurrence_count"])
            if row["automatic_candidate_eligible"] != "false":
                raise RuntimeError("Stage 15 summary implies automatic candidate")
    if summary_types != dict(route_types) or summary_occurrences != dict(route_occurrences):
        raise RuntimeError("Stage 15 summary accounting differs")

    expected_counts = {
        "target_types": len(targets),
        "target_occurrences": sum(int(row["total_occurrences"]) for row in targets.values()),
        "unsupported_issue_rows": len(source_issues),
        "edit_mechanism_issue_rows": dict(sorted(mechanisms.items())),
        "rule_unit_family_issue_rows": dict(sorted(families.items())),
        "primary_audit_route_types": dict(sorted(route_types.items())),
        "primary_audit_route_occurrences": dict(sorted(route_occurrences.items())),
        "automatic_candidate_types": 0,
        "preserved_zero_fallback_hold_types": len(targets),
    }
    if manifest.get("counts") != expected_counts:
        raise RuntimeError("Stage 15 manifest counts differ")

    result = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "manifest": file_fingerprint(manifest_path, with_sha256=True),
        "recomputed_counts": expected_counts,
        "invariants": {
            "all_target_tokens_accounted": True,
            "all_unsupported_issues_accounted": True,
            "all_donor_sets_unanimous": True,
            "readiness_v3_hold_preserved": True,
            "automatic_candidate_types": 0,
            "canonical_selection_performed": False,
            "mfa_or_textgrid_modified": False,
        },
    }
    atomic_write_json(output, result)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = audit(args.manifest.resolve(), args.output.resolve())
    print(json.dumps(result["recomputed_counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
