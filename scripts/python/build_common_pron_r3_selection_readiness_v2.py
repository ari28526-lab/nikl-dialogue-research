"""Add audited no-rule alignment candidates to the full r3 readiness matrix.

This remains a planning artifact.  It does not select a canonical lexicon,
adopt a release, run MFA, or modify TextGrids.
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
from build_common_pron_r3_rule_phone_coverage_audit import (  # noqa: E402
    SCHEMA_VERSION as COVERAGE_SCHEMA,
    VARIANT_FIELDS,
)
from build_common_pron_r3_selection_readiness import (  # noqa: E402
    READINESS_FIELDS as V1_FIELDS,
    SCHEMA_VERSION as V1_SCHEMA,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_selection_readiness.v2"
POLICY_SCHEMA = "common_pron_r3_selection_readiness_v2_policy.v1"
TARGET_V1_STATUS = "hold_no_surface_rule_substantive_mismatch"
OUTPUT_FIELDS = (
    *V1_FIELDS,
    "no_rule_coverage_status",
    "no_rule_coverage_evidence_json",
    "planning_candidate_role",
    "planning_standard_relation",
    "planning_actual_realization_status",
)
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def parse_list(value: object, *, label: str) -> list[str]:
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


def coverage_decision(rows: list[dict[str, str]]) -> dict[str, object]:
    if not rows:
        raise RuntimeError("empty no-rule coverage group")
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
        "planning_status": TARGET_V1_STATUS,
        "source": "zero_fallback_hold",
        "reason": "no-rule coverage evidence does not support every r2 variant; preserve the zero-fallback hold",
        "role": "",
        "standard_relation": "unresolved_hold",
        "evidence": evidence,
    }


def read_coverage_groups(path: Path) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != VARIANT_FIELDS:
            raise RuntimeError("coverage variant column contract differs")
        for row in reader:
            token = row["token"]
            expected_index = len(groups[token]) + 1
            if int(row["variant_index"]) != expected_index:
                raise RuntimeError(f"coverage variant order differs: {token}")
            groups[token].append(row)
    return dict(groups)


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "planning_candidates_only"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
    ):
        raise RuntimeError("readiness v2 policy differs")
    candidate_policies = policy.get("candidate_policies", {})
    if set(candidate_policies) != {
        "all_variants_optional_place_assimilation",
        "all_variants_exact_frozen_dictionary",
        "some_variants_optional_place_assimilation",
        "some_variants_exact_frozen_dictionary",
        "unresolved_g2p_or_rule_mapping",
    }:
        raise RuntimeError("readiness v2 candidate policy coverage differs")
    if not candidate_policies["all_variants_optional_place_assimilation"]["eligible"]:
        raise RuntimeError("optional alignment candidate policy differs")
    if not candidate_policies["all_variants_exact_frozen_dictionary"]["eligible"]:
        raise RuntimeError("frozen dictionary candidate policy differs")
    if any(
        candidate_policies[key]["eligible"]
        for key in (
            "some_variants_optional_place_assimilation",
            "some_variants_exact_frozen_dictionary",
            "unresolved_g2p_or_rule_mapping",
        )
    ):
        raise RuntimeError("readiness v2 fail-closed policy differs")
    if any(value is not True for value in policy.get("interpretation_policy", {}).values()):
        raise RuntimeError("readiness v2 interpretation policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("readiness v2 policy exceeds planning scope")
    return policy


def verify_existing(
    output_root: Path,
    *,
    readiness_v1_manifest_path: Path,
    coverage_manifest_path: Path,
    policy_path: Path,
) -> dict[str, object]:
    manifest_path = output_root / "SELECTION_READINESS_V2_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"readiness v2 root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("existing readiness v2 differs")
    for key, path in (
        ("readiness_v1_manifest", readiness_v1_manifest_path),
        ("coverage_manifest", coverage_manifest_path),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
    verify_fingerprint(
        manifest["outputs"]["selection_readiness_v2"],
        Path(str(manifest["outputs"]["selection_readiness_v2"]["path"])),
        label="existing readiness v2",
    )
    return manifest


def build_readiness_v2(
    *,
    readiness_v1_manifest_path: Path,
    coverage_manifest_path: Path,
    policy_path: Path,
    output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            readiness_v1_manifest_path=readiness_v1_manifest_path,
            coverage_manifest_path=coverage_manifest_path,
            policy_path=policy_path,
        )
    readiness_manifest = json.loads(readiness_v1_manifest_path.read_text(encoding="utf-8-sig"))
    coverage_manifest = json.loads(coverage_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness_manifest.get("schema_version") != V1_SCHEMA or readiness_manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("readiness v1 input differs")
    if coverage_manifest.get("schema_version") != COVERAGE_SCHEMA or coverage_manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("coverage input differs")
    validate_policy(policy_path)
    readiness_v1_path = Path(str(readiness_manifest["outputs"]["selection_readiness"]["path"])).resolve()
    coverage_path = Path(str(coverage_manifest["outputs"]["variant_coverage"]["path"])).resolve()
    verify_fingerprint(readiness_manifest["outputs"]["selection_readiness"], readiness_v1_path, label="readiness v1")
    verify_fingerprint(coverage_manifest["outputs"]["variant_coverage"], coverage_path, label="coverage variants")
    coverage_groups = read_coverage_groups(coverage_path)

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    temp_output = temp_root / "common_pron_r3_selection_readiness_v2.csv.gz"
    final_output = output_root / temp_output.name
    temp_manifest = temp_root / "SELECTION_READINESS_V2_MANIFEST.json"

    row_count = total_occurrences = candidate_types = candidate_occurrences = 0
    hold_types = hold_occurrences = policy_types = policy_occurrences = 0
    newly_eligible_types = newly_eligible_occurrences = 0
    preserved_v1_rows = 0
    planning_types: Counter[str] = Counter()
    planning_occurrences: Counter[str] = Counter()
    coverage_types: Counter[str] = Counter()
    coverage_occurrences: Counter[str] = Counter()
    consumed_coverage: set[str] = set()
    with gzip.open(readiness_v1_path, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(temp_output) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != V1_FIELDS:
            raise RuntimeError("readiness v1 column contract differs")
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            token = row["token"]
            total = int(row["total_occurrences"])
            updated = dict(row)
            if row["planning_status"] == TARGET_V1_STATUS:
                rows = coverage_groups.get(token)
                if not rows:
                    raise RuntimeError(f"missing no-rule coverage: {token}")
                consumed_coverage.add(token)
                phone_values = parse_list(row["r2_pron_phones_json"], label=f"r2 phones {token}")
                roman_values = parse_list(row["r2_pron_roman_json"], label=f"r2 Roman {token}")
                if len(rows) != len(phone_values) or any(
                    detail["r2_pron_phones"] != phone or detail["r2_pron_roman"] != roman
                    for detail, phone, roman in zip(rows, phone_values, roman_values, strict=True)
                ):
                    raise RuntimeError(f"coverage/r2 variants differ: {token}")
                decision = coverage_decision(rows)
                updated["no_rule_coverage_status"] = str(decision["status"])
                updated["no_rule_coverage_evidence_json"] = json.dumps(decision["evidence"], ensure_ascii=False)
                updated["planning_candidate_role"] = str(decision["role"])
                updated["planning_standard_relation"] = str(decision["standard_relation"])
                updated["planning_actual_realization_status"] = "not_performed"
                if decision["eligible"]:
                    updated["planning_candidate_variant_count"] = str(len(phone_values))
                    updated["planning_candidate_phones_json"] = json.dumps(phone_values, ensure_ascii=False)
                    updated["planning_candidate_roman_json"] = json.dumps(roman_values, ensure_ascii=False)
                    updated["planning_status"] = str(decision["planning_status"])
                    updated["planning_source"] = str(decision["source"])
                    updated["planning_reason"] = str(decision["reason"])
                    updated["planning_requires_policy_decision"] = "false"
                    updated["planning_zero_fallback_hold"] = "false"
                    updated["planning_is_final_selection"] = "false"
                    newly_eligible_types += 1
                    newly_eligible_occurrences += total
                else:
                    if any(updated[field] != row[field] for field in V1_FIELDS):
                        raise RuntimeError(f"held v1 fields changed: {token}")
            else:
                updated["no_rule_coverage_status"] = "not_applicable_existing_planning"
                updated["no_rule_coverage_evidence_json"] = "[]"
                updated["planning_candidate_role"] = ""
                updated["planning_standard_relation"] = "existing_v1_planning_unchanged"
                updated["planning_actual_realization_status"] = "not_performed"
                if any(updated[field] != row[field] for field in V1_FIELDS):
                    raise RuntimeError(f"non-target v1 fields changed: {token}")
                preserved_v1_rows += 1
            writer.writerow(updated)
            status = updated["planning_status"]
            planning_types[status] += 1
            planning_occurrences[status] += total
            coverage_status = updated["no_rule_coverage_status"]
            coverage_types[coverage_status] += 1
            coverage_occurrences[coverage_status] += total
            if status.startswith("candidate_"):
                candidate_types += 1
                candidate_occurrences += total
            if updated["planning_zero_fallback_hold"] == "true":
                hold_types += 1
                hold_occurrences += total
            if updated["planning_requires_policy_decision"] == "true":
                policy_types += 1
                policy_occurrences += total
            row_count += 1
            total_occurrences += total
    if consumed_coverage != set(coverage_groups):
        raise RuntimeError("unconsumed no-rule coverage tokens")
    if row_count != int(readiness_manifest["counts"]["canonical_types"]):
        raise RuntimeError("readiness v2 canonical coverage differs")
    if newly_eligible_types != 37_379 or newly_eligible_occurrences != 754_924:
        raise RuntimeError("audited no-rule candidate increment differs")
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_planning_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "planning_candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "readiness_v1_manifest": file_fingerprint(readiness_v1_manifest_path, with_sha256=True),
            "coverage_manifest": file_fingerprint(coverage_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "readiness_v1": file_fingerprint(readiness_v1_path, with_sha256=True),
            "coverage_variants": file_fingerprint(coverage_path, with_sha256=True),
        },
        "counts": {
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
        },
        "outputs": {
            "selection_readiness_v2": fingerprint_for_final(temp_output, final_output)
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_manifest, manifest)
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--readiness-v1-manifest", type=Path, required=True)
    result.add_argument("--coverage-manifest", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_readiness_v2(
        readiness_v1_manifest_path=args.readiness_v1_manifest.resolve(),
        coverage_manifest_path=args.coverage_manifest.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
