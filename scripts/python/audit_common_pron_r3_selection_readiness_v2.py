"""Independently audit the full candidate-only r3 readiness v2 matrix."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_r3_rule_phone_coverage_audit import VARIANT_FIELDS  # noqa: E402
from build_common_pron_r3_selection_readiness import READINESS_FIELDS as V1_FIELDS  # noqa: E402
from build_common_pron_r3_selection_readiness_v2 import (  # noqa: E402
    OUTPUT_FIELDS,
    POLICY_SCHEMA,
    SCHEMA_VERSION,
    TARGET_V1_STATUS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCHEMA = "common_pron_r3_selection_readiness_v2_audit.v1"
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


def read_groups(path: Path) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != VARIANT_FIELDS:
            raise RuntimeError("coverage column contract differs")
        for row in reader:
            groups[row["token"]].append(row)
    return dict(groups)


def audit_coverage_decision(rows: list[dict[str, str]]) -> dict[str, object]:
    optional = [row["optional_place_assimilation_only"] == "true" for row in rows]
    frozen = [row["frozen_dictionary_exact_variant"] == "true" for row in rows]
    evidence = sorted(
        {
            value
            for row in rows
            for value in parse_list(row["evidence_labels_json"], label=f"evidence {row['token']}")
        }
    )
    if all(optional):
        return {
            "status": "all_variants_optional_place_assimilation",
            "eligible": True,
            "planning_status": "candidate_r2_optional_place_assimilation_alignment_variant",
            "source": "audited_r2_optional_place_assimilation",
            "reason": "retain all r2 variants as frozen-model alignment candidates; optional place assimilation is not added to the mandatory standard-pronunciation reference",
            "role": "mfa_alignment_lexicon_candidate",
            "standard_relation": "optional_variant_not_mandatory_standard",
            "evidence": evidence,
        }
    if any(optional):
        status = "some_variants_optional_place_assimilation"
    elif all(frozen):
        return {
            "status": "all_variants_exact_frozen_dictionary",
            "eligible": True,
            "planning_status": "candidate_r2_exact_frozen_dictionary_alignment_variant",
            "source": "audited_exact_frozen_mfa_dictionary",
            "reason": "retain all exact frozen-dictionary variants as model-compatible alignment candidates without claiming standard pronunciation or actual realization",
            "role": "mfa_alignment_lexicon_candidate",
            "standard_relation": "frozen_alignment_variant_standard_relation_not_claimed",
            "evidence": evidence,
        }
    elif any(frozen):
        status = "some_variants_exact_frozen_dictionary"
    else:
        status = "unresolved_g2p_or_rule_mapping"
    return {
        "status": status,
        "eligible": False,
        "role": "",
        "standard_relation": "unresolved_hold",
        "evidence": evidence,
    }


def audit_readiness(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("readiness v2 manifest differs")
    if any(value is not False for value in manifest.get("scope", {}).values()):
        raise RuntimeError("readiness v2 exceeded planning scope")
    inputs = {key: verify(record, label=f"input {key}") for key, record in manifest["inputs"].items()}
    output = verify(manifest["outputs"]["selection_readiness_v2"], label="readiness v2")
    policy = json.loads(inputs["policy_contract"].read_text(encoding="utf-8-sig"))
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "planning_candidates_only":
        raise RuntimeError("readiness v2 policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("readiness v2 policy invariants differ")
    if any(value is not True for value in policy.get("interpretation_policy", {}).values()):
        raise RuntimeError("readiness v2 interpretation policy differs")
    coverage_groups = read_groups(inputs["coverage_variants"])

    row_count = total_occurrences = candidate_types = candidate_occurrences = 0
    hold_types = hold_occurrences = policy_types = policy_occurrences = 0
    newly_eligible_types = newly_eligible_occurrences = preserved_v1_rows = 0
    planning_types: Counter[str] = Counter()
    planning_occurrences: Counter[str] = Counter()
    coverage_types: Counter[str] = Counter()
    coverage_occurrences: Counter[str] = Counter()
    consumed: set[str] = set()
    examples: dict[str, list[dict[str, object]]] = defaultdict(list)
    with gzip.open(inputs["readiness_v1"], "rt", encoding="utf-8-sig", newline="") as old_stream, gzip.open(output, "rt", encoding="utf-8-sig", newline="") as new_stream:
        old_reader = csv.DictReader(old_stream)
        new_reader = csv.DictReader(new_stream)
        if tuple(old_reader.fieldnames or ()) != V1_FIELDS or tuple(new_reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise RuntimeError("readiness v1/v2 column contract differs")
        for old, new in zip(old_reader, new_reader, strict=True):
            token = old["token"]
            if new["token"] != token:
                raise RuntimeError(f"readiness order differs: {token}")
            total = int(old["total_occurrences"])
            if old["planning_status"] == TARGET_V1_STATUS:
                details = coverage_groups.get(token)
                if not details:
                    raise RuntimeError(f"missing coverage details: {token}")
                consumed.add(token)
                phones = parse_list(old["r2_pron_phones_json"], label=f"r2 phones {token}")
                romans = parse_list(old["r2_pron_roman_json"], label=f"r2 Roman {token}")
                if len(details) != len(phones):
                    raise RuntimeError(f"coverage variant count differs: {token}")
                decision = audit_coverage_decision(details)
                expected_appended = {
                    "no_rule_coverage_status": str(decision["status"]),
                    "no_rule_coverage_evidence_json": json.dumps(decision["evidence"], ensure_ascii=False),
                    "planning_candidate_role": str(decision["role"]),
                    "planning_standard_relation": str(decision["standard_relation"]),
                    "planning_actual_realization_status": "not_performed",
                }
                if any(new[key] != value for key, value in expected_appended.items()):
                    raise RuntimeError(f"appended readiness values differ: {token}")
                if decision["eligible"]:
                    expected_changes = {
                        "planning_candidate_variant_count": str(len(phones)),
                        "planning_candidate_phones_json": json.dumps(phones, ensure_ascii=False),
                        "planning_candidate_roman_json": json.dumps(romans, ensure_ascii=False),
                        "planning_status": str(decision["planning_status"]),
                        "planning_source": str(decision["source"]),
                        "planning_reason": str(decision["reason"]),
                        "planning_requires_policy_decision": "false",
                        "planning_zero_fallback_hold": "false",
                        "planning_is_final_selection": "false",
                    }
                    allowed = set(expected_changes)
                    for field in V1_FIELDS:
                        expected = expected_changes.get(field, old[field])
                        if new[field] != expected:
                            raise RuntimeError(f"eligible readiness field differs: {token} {field}")
                    if new["rule_pron_roman"] != old["rule_pron_roman"]:
                        raise RuntimeError(f"mandatory rule reference changed: {token}")
                    newly_eligible_types += 1
                    newly_eligible_occurrences += total
                else:
                    if any(new[field] != old[field] for field in V1_FIELDS):
                        raise RuntimeError(f"held readiness v1 fields changed: {token}")
                bucket = examples[str(decision["status"])]
                if len(bucket) < 8:
                    bucket.append({"token": token, "occurrences": total, "planning_status": new["planning_status"], "rule_pron_roman": new["rule_pron_roman"], "candidate_roman_json": new["planning_candidate_roman_json"]})
            else:
                if any(new[field] != old[field] for field in V1_FIELDS):
                    raise RuntimeError(f"non-target readiness v1 fields changed: {token}")
                expected_appended = {
                    "no_rule_coverage_status": "not_applicable_existing_planning",
                    "no_rule_coverage_evidence_json": "[]",
                    "planning_candidate_role": "",
                    "planning_standard_relation": "existing_v1_planning_unchanged",
                    "planning_actual_realization_status": "not_performed",
                }
                if any(new[key] != value for key, value in expected_appended.items()):
                    raise RuntimeError(f"non-target appended values differ: {token}")
                preserved_v1_rows += 1
            status = new["planning_status"]
            coverage_status = new["no_rule_coverage_status"]
            planning_types[status] += 1
            planning_occurrences[status] += total
            coverage_types[coverage_status] += 1
            coverage_occurrences[coverage_status] += total
            if status.startswith("candidate_"):
                candidate_types += 1
                candidate_occurrences += total
            if new["planning_zero_fallback_hold"] == "true":
                hold_types += 1
                hold_occurrences += total
            if new["planning_requires_policy_decision"] == "true":
                policy_types += 1
                policy_occurrences += total
            if new["planning_is_final_selection"] != "false" or new["planning_actual_realization_status"] != "not_performed":
                raise RuntimeError(f"readiness v2 interpretation contract differs: {token}")
            row_count += 1
            total_occurrences += total
    if consumed != set(coverage_groups):
        raise RuntimeError("unconsumed coverage groups")
    counts = {
        "canonical_types": row_count,
        "total_occurrences": total_occurrences,
        "candidate_ready_types": candidate_types,
        "candidate_ready_occurrences": candidate_occurrences,
        "zero_fallback_hold_types": hold_types,
        "zero_fallback_hold_occurrences": hold_occurrences,
        "policy_decision_types": policy_types,
        "policy_decision_occurrences": policy_occurrences,
        "newly_eligible_no_rule_types": newly_eligible_types,
        "newly_eligible_no_rule_occurrences": newly_eligible_occurrences,
        "preserved_v1_rows": preserved_v1_rows,
        "planning_status_types": dict(sorted(planning_types.items())),
        "planning_status_occurrences": dict(sorted(planning_occurrences.items())),
        "no_rule_coverage_status_types": dict(sorted(coverage_types.items())),
        "no_rule_coverage_status_occurrences": dict(sorted(coverage_occurrences.items())),
    }
    if counts != manifest["counts"]:
        raise RuntimeError("readiness v2 manifest counts differ")
    report: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": counts,
        "examples_by_no_rule_coverage_status": dict(examples),
        "contracts": {
            "all_non_target_v1_fields_preserved": True,
            "all_held_v1_fields_preserved": True,
            "mandatory_rule_references_preserved": True,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "manifest": file_fingerprint(manifest_path, with_sha256=True),
            "readiness_v2": file_fingerprint(output, with_sha256=True),
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
