"""Merge independently audited Stage 17 candidate-only rows into readiness v4."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_r3_attested_full_sequence_projection import (  # noqa: E402
    OUTPUT_FIELDS as STAGE17_FIELDS,
    SCHEMA_VERSION as STAGE17_SCHEMA,
    STATUS as STAGE17_STATUS,
)
from build_common_pron_r3_selection_readiness_v3 import (  # noqa: E402
    OUTPUT_FIELDS,
    SCHEMA_VERSION as READINESS_V3_SCHEMA,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_selection_readiness_v4.v1"
POLICY_SCHEMA = "common_pron_r3_selection_readiness_v4_policy.v1"
STATUS = "success_planning_not_selected"
NEW_STATUS = "candidate_attested_rule_exact_full_context_projection"
ALLOWED_CHANGED_FIELDS = {
    "planning_candidate_variant_count",
    "planning_candidate_phones_json",
    "planning_candidate_roman_json",
    "planning_status",
    "planning_source",
    "planning_reason",
    "planning_requires_policy_decision",
    "planning_zero_fallback_hold",
    "planning_is_final_selection",
    "planning_candidate_role",
    "planning_standard_relation",
    "planning_actual_realization_status",
}

csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], path: Path, *, label: str) -> None:
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


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "planning_merge_only":
        raise RuntimeError("readiness v4 policy identity differs")
    eligibility = policy.get("eligibility", {})
    if (
        eligibility.get("required_stage17_status") != "complete_unanimous_full_sequence"
        or eligibility.get("required_dictionary_evidence_class") != "attested_pron_1_or_2_rule_exact"
        or eligibility.get("required_candidate_role") != "alignment_lexicon_candidate_only"
        or int(eligibility.get("expected_newly_eligible_types", 0)) != 14
        or int(eligibility.get("expected_newly_eligible_occurrences", 0)) != 200
    ):
        raise RuntimeError("readiness v4 eligibility contract differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("readiness v4 policy exceeds planning scope")
    return policy


def apply_candidate(row: dict[str, str], candidate: dict[str, str]) -> dict[str, str]:
    if row["planning_zero_fallback_hold"] != "true":
        raise RuntimeError(f"Stage 17 target is not a v3 hold: {row['token']}")
    phones = json.loads(candidate["planning_candidate_phones_json"] or "[]")
    romans = json.loads(candidate["planning_candidate_roman_json"] or "[]")
    if len(phones) != 1 or romans != [row["rule_pron_roman"]]:
        raise RuntimeError(f"Stage 17 candidate contract differs: {row['token']}")
    updated = dict(row)
    updated.update(
        {
            "planning_candidate_variant_count": "1",
            "planning_candidate_phones_json": candidate["planning_candidate_phones_json"],
            "planning_candidate_roman_json": candidate["planning_candidate_roman_json"],
            "planning_status": NEW_STATUS,
            "planning_source": "attested_pron_1_or_2_plus_full_context_model_projection",
            "planning_reason": "attested dictionary pron_1/2 agrees with the rule target and every rule unit has one independently audited contextual acoustic-model phone; candidate-only, not final selection or realization",
            "planning_requires_policy_decision": "false",
            "planning_zero_fallback_hold": "false",
            "planning_is_final_selection": "false",
            "planning_candidate_role": "mfa_alignment_lexicon_candidate",
            "planning_standard_relation": "attested_dictionary_rule_exact_with_model_phone_projection",
            "planning_actual_realization_status": "not_performed",
        }
    )
    changed = {field for field in OUTPUT_FIELDS if updated[field] != row[field]}
    if not changed or not changed <= ALLOWED_CHANGED_FIELDS:
        raise RuntimeError(f"readiness v4 changed-field contract differs: {row['token']} {sorted(changed)}")
    return updated


def verify_existing(
    output_root: Path, *, readiness_v3_manifest_path: Path,
    stage17_manifest_path: Path, stage17_audit_path: Path, policy_path: Path,
) -> dict[str, object]:
    manifest_path = output_root / "SELECTION_READINESS_V4_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"readiness v4 root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RuntimeError("existing readiness v4 identity differs")
    for key, path in (
        ("readiness_v3_manifest", readiness_v3_manifest_path),
        ("stage17_manifest", stage17_manifest_path),
        ("stage17_independent_audit", stage17_audit_path),
        ("policy_contract", policy_path),
    ):
        verify(manifest["inputs"][key], path, label=f"existing {key}")
    record = manifest["outputs"]["selection_readiness_v4"]
    verify(record, Path(str(record["path"])), label="existing readiness v4")
    return manifest


def build_readiness_v4(
    *, readiness_v3_manifest_path: Path, stage17_manifest_path: Path,
    stage17_audit_path: Path, policy_path: Path, output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            readiness_v3_manifest_path=readiness_v3_manifest_path,
            stage17_manifest_path=stage17_manifest_path,
            stage17_audit_path=stage17_audit_path,
            policy_path=policy_path,
        )
    policy = validate_policy(policy_path)
    readiness_manifest = json.loads(readiness_v3_manifest_path.read_text(encoding="utf-8-sig"))
    stage17 = json.loads(stage17_manifest_path.read_text(encoding="utf-8-sig"))
    audit = json.loads(stage17_audit_path.read_text(encoding="utf-8-sig"))
    if readiness_manifest.get("schema_version") != READINESS_V3_SCHEMA:
        raise RuntimeError("readiness v3 identity differs")
    if stage17.get("schema_version") != STAGE17_SCHEMA or stage17.get("status") != STAGE17_STATUS:
        raise RuntimeError("Stage 17 identity differs")
    if audit.get("status") != "passed_independent_candidate_plan_audit":
        raise RuntimeError("Stage 17 independent audit did not pass")
    if clean(audit.get("manifest", {}).get("sha256")) != sha256_file(stage17_manifest_path):
        raise RuntimeError("Stage 17 audit is not bound to manifest")
    readiness_path = Path(str(readiness_manifest["outputs"]["selection_readiness_v3"]["path"])).resolve()
    stage17_path = Path(str(stage17["outputs"]["projection_inventory"]["path"])).resolve()
    verify(readiness_manifest["outputs"]["selection_readiness_v3"], readiness_path, label="readiness v3")
    verify(stage17["outputs"]["projection_inventory"], stage17_path, label="Stage 17 inventory")
    candidates: dict[str, dict[str, str]] = {}
    with gzip.open(stage17_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != STAGE17_FIELDS:
            raise RuntimeError("Stage 17 columns differ")
        for row in reader:
            if row["automatic_candidate_eligible"] != "true":
                continue
            if (
                row["full_sequence_projection_status"] != policy["eligibility"]["required_stage17_status"]
                or row["dictionary_evidence_class"] != policy["eligibility"]["required_dictionary_evidence_class"]
                or row["planning_candidate_role"] != policy["eligibility"]["required_candidate_role"]
            ):
                raise RuntimeError(f"Stage 17 eligible identity differs: {row['token']}")
            candidates[row["token"]] = row
    if len(candidates) != int(policy["eligibility"]["expected_newly_eligible_types"]):
        raise RuntimeError("readiness v4 candidate count differs")
    if sum(int(row["total_occurrences"]) for row in candidates.values()) != int(
        policy["eligibility"]["expected_newly_eligible_occurrences"]
    ):
        raise RuntimeError("readiness v4 candidate occurrences differ")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    output_temp = temp_root / "common_pron_r3_selection_readiness_v4.csv.gz"
    output_final = output_root / output_temp.name
    status_types: Counter[str] = Counter()
    status_occurrences: Counter[str] = Counter()
    row_count = total_occurrences = candidate_types = candidate_occurrences = 0
    hold_types = hold_occurrences = new_types = new_occurrences = 0
    consumed: set[str] = set()
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(output_temp) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise RuntimeError("readiness v3 columns differ")
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            token = row["token"]
            total = int(row["total_occurrences"])
            if token in candidates:
                updated = apply_candidate(row, candidates[token])
                consumed.add(token)
                new_types += 1
                new_occurrences += total
            else:
                updated = row
            writer.writerow(updated)
            row_count += 1
            total_occurrences += total
            status = updated["planning_status"]
            status_types[status] += 1
            status_occurrences[status] += total
            is_candidate = status.startswith("candidate_")
            candidate_types += int(is_candidate)
            candidate_occurrences += total if is_candidate else 0
            is_hold = updated["planning_zero_fallback_hold"] == "true"
            hold_types += int(is_hold)
            hold_occurrences += total if is_hold else 0
    if consumed != set(candidates):
        raise RuntimeError("unconsumed Stage 17 candidates")
    counts = {
        "canonical_types": row_count,
        "total_occurrences": total_occurrences,
        "candidate_ready_types": candidate_types,
        "candidate_ready_occurrences": candidate_occurrences,
        "zero_fallback_hold_types": hold_types,
        "zero_fallback_hold_occurrences": hold_occurrences,
    }
    if any(int(policy["expected_output"][key]) != value for key, value in counts.items()):
        raise RuntimeError(f"readiness v4 output accounting differs: {counts}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "scope": {
            "existing_non_target_rows_changed": False,
            "planning_candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "standard_pronunciation_claimed": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "readiness_v3_manifest": file_fingerprint(readiness_v3_manifest_path, with_sha256=True),
            "stage17_manifest": file_fingerprint(stage17_manifest_path, with_sha256=True),
            "stage17_independent_audit": file_fingerprint(stage17_audit_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "readiness_v3": file_fingerprint(readiness_path, with_sha256=True),
            "stage17_projection_inventory": file_fingerprint(stage17_path, with_sha256=True),
        },
        "counts": {
            **counts,
            "newly_eligible_attested_full_sequence_types": new_types,
            "newly_eligible_attested_full_sequence_occurrences": new_occurrences,
            "planning_status_types": dict(sorted(status_types.items())),
            "planning_status_occurrences": dict(sorted(status_occurrences.items())),
        },
        "outputs": {
            "selection_readiness_v4": fingerprint_for_final(output_temp, output_final),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "SELECTION_READINESS_V4_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness-v3-manifest", type=Path, required=True)
    parser.add_argument("--stage17-manifest", type=Path, required=True)
    parser.add_argument("--stage17-audit", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "common_pron_r3_selection_readiness_v4.json")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_readiness_v4(
        readiness_v3_manifest_path=args.readiness_v3_manifest.resolve(),
        stage17_manifest_path=args.stage17_manifest.resolve(),
        stage17_audit_path=args.stage17_audit.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
