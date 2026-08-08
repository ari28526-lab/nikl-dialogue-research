"""Add only unchanged contextual secondary-articulation candidates to r3 readiness.

The stage consumes the independently audited contextual donor tables.  It does
not replace or insert phones.  Eligible rows retain their existing r2 phone and
Roman sequences byte-for-byte and remain planning candidates rather than a
selected or adopted MFA lexicon.
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
from build_common_pron_r3_selection_readiness_v2 import (  # noqa: E402
    OUTPUT_FIELDS as V2_FIELDS,
    SCHEMA_VERSION as V2_SCHEMA,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_selection_readiness.v3"
POLICY_SCHEMA = "common_pron_r3_selection_readiness_v3_policy.v1"
NEW_STATUS = "candidate_r2_contextual_secondary_articulation_equivalent"
OUTPUT_FIELDS = (
    *V2_FIELDS,
    "contextual_donor_support_class",
    "contextual_secondary_articulation_evidence_json",
    "contextual_secondary_articulation_candidate_eligible",
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
        raise RuntimeError(f"expected JSON string list: {label}")
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


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "planning_candidates_only"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
    ):
        raise RuntimeError("readiness v3 policy differs")
    eligibility = policy.get("eligibility", {})
    if (
        eligibility.get("required_contextual_support_class") != CLASS_UNANIMOUS
        or int(eligibility.get("required_variant_count", 0)) != 1
        or eligibility.get("allowed_relation_kinds") != ["secondary_articulation_cluster"]
        or eligibility.get("every_issue_current_candidate_supported") is not True
        or eligibility.get("every_issue_frozen_context_required") is not True
        or eligibility.get("canonical_context_for_secondary_relation_required") is not False
        or eligibility.get("existing_r2_phone_sequence_must_remain_byte_identical") is not True
        or eligibility.get("existing_r2_roman_sequence_must_remain_byte_identical") is not True
    ):
        raise RuntimeError("readiness v3 eligibility differs")
    if any(value is not False for value in policy.get("hold_policy", {}).values()):
        raise RuntimeError("readiness v3 hold policy permits unsafe fallback")
    if any(value is not True for value in policy.get("interpretation_policy", {}).values()):
        raise RuntimeError("readiness v3 interpretation policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("readiness v3 policy exceeds planning scope")
    return policy


def read_contextual_rows(
    *, classification_path: Path, evidence_path: Path
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    classifications: dict[str, dict[str, str]] = {}
    with gzip.open(classification_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != HOLD_FIELDS:
            raise RuntimeError("contextual hold classification columns differ")
        for row in reader:
            token = row["token"]
            if token in classifications:
                raise RuntimeError(f"duplicate contextual classification: {token}")
            classifications[token] = row
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)
    with gzip.open(evidence_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != ISSUE_FIELDS:
            raise RuntimeError("contextual evidence columns differ")
        for row in reader:
            evidence[row["token"]].append(row)
    extras = set(evidence) - set(classifications)
    if extras:
        raise RuntimeError(
            f"contextual evidence contains tokens outside classification: {len(extras)}"
        )
    # A held token can have zero extracted edit issues.  It remains fail-closed
    # and therefore legitimately has no row in the issue-level table.
    return classifications, {
        token: list(evidence.get(token, ())) for token in classifications
    }


def eligible_secondary(
    classification: dict[str, str], evidence: list[dict[str, str]]
) -> bool:
    return (
        classification["contextual_support_class"] == CLASS_UNANIMOUS
        and int(classification["audited_variant_count"]) == 1
        and bool(evidence)
        and all(
            row["variant_index"] == "1"
            and row["relation_kind"] == "secondary_articulation_cluster"
            and row["evidence_class"] == CLASS_UNANIMOUS
            and row["current_candidate_supported"] == "true"
            and bool(row["current_candidate_phone"])
            and not row["canonical_context_level"]
            and bool(row["frozen_context_level"])
            for row in evidence
        )
    )


def evidence_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "rule_units": json.loads(row["rule_units_json"]),
            "existing_phone": row["current_candidate_phone"],
            "frozen_context_level": row["frozen_context_level"],
            "frozen_token_type_count": int(row["frozen_token_type_count"]),
            "phone_sequence_changed": False,
            "standard_pronunciation_claimed": False,
        }
        for row in rows
    ]


def verify_existing(
    output_root: Path, *, readiness_v2_manifest_path: Path,
    contextual_manifest_path: Path, policy_path: Path
) -> dict[str, object]:
    manifest_path = output_root / "SELECTION_READINESS_V3_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"readiness v3 root exists without manifest: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("existing readiness v3 differs")
    for key, path in (
        ("readiness_v2_manifest", readiness_v2_manifest_path),
        ("contextual_donor_manifest", contextual_manifest_path),
        ("policy_contract", policy_path),
    ):
        verify_fingerprint(manifest["inputs"][key], path, label=f"existing {key}")
    verify_fingerprint(
        manifest["outputs"]["selection_readiness_v3"],
        Path(str(manifest["outputs"]["selection_readiness_v3"]["path"])),
        label="existing readiness v3",
    )
    return manifest


def build_readiness_v3(
    *, readiness_v2_manifest_path: Path, contextual_manifest_path: Path,
    policy_path: Path, output_root: Path
) -> dict[str, object]:
    if output_root.exists():
        return verify_existing(
            output_root,
            readiness_v2_manifest_path=readiness_v2_manifest_path,
            contextual_manifest_path=contextual_manifest_path,
            policy_path=policy_path,
        )
    readiness_manifest = json.loads(readiness_v2_manifest_path.read_text(encoding="utf-8-sig"))
    contextual_manifest = json.loads(contextual_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness_manifest.get("schema_version") != V2_SCHEMA or readiness_manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("readiness v2 input differs")
    if contextual_manifest.get("schema_version") != CONTEXT_SCHEMA or contextual_manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("contextual donor input differs")
    policy = validate_policy(policy_path)
    readiness_path = Path(str(readiness_manifest["outputs"]["selection_readiness_v2"]["path"])).resolve()
    classification_path = Path(
        str(contextual_manifest["outputs"]["residual_hold_contextual_classification"]["path"])
    ).resolve()
    evidence_path = Path(
        str(contextual_manifest["outputs"]["residual_hold_contextual_evidence"]["path"])
    ).resolve()
    for record, path, label in (
        (readiness_manifest["outputs"]["selection_readiness_v2"], readiness_path, "readiness v2"),
        (contextual_manifest["outputs"]["residual_hold_contextual_classification"], classification_path, "contextual classification"),
        (contextual_manifest["outputs"]["residual_hold_contextual_evidence"], evidence_path, "contextual evidence"),
    ):
        verify_fingerprint(record, path, label=label)
    classifications, evidence = read_contextual_rows(
        classification_path=classification_path, evidence_path=evidence_path
    )

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    output = temp_root / "common_pron_r3_selection_readiness_v3.csv.gz"
    final_output = output_root / output.name
    manifest_output = temp_root / "SELECTION_READINESS_V3_MANIFEST.json"

    row_count = total_occurrences = candidate_types = candidate_occurrences = 0
    hold_types = hold_occurrences = policy_types = policy_occurrences = 0
    new_types = new_occurrences = preserved_rows = 0
    planning_types: Counter[str] = Counter()
    planning_occurrences: Counter[str] = Counter()
    contextual_types: Counter[str] = Counter()
    contextual_occurrences: Counter[str] = Counter()
    consumed: set[str] = set()
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(output) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != V2_FIELDS:
            raise RuntimeError("readiness v2 column contract differs")
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            token = row["token"]
            total = int(row["total_occurrences"])
            updated = dict(row)
            if row["planning_zero_fallback_hold"] == "true":
                classification = classifications.get(token)
                rows = evidence.get(token)
                if classification is None or rows is None:
                    raise RuntimeError(f"missing contextual donor audit: {token}")
                consumed.add(token)
                category = classification["contextual_support_class"]
                updated["contextual_donor_support_class"] = category
                if eligible_secondary(classification, rows):
                    phones = parse_list(row["r2_pron_phones_json"], label=f"r2 phones {token}")
                    romans = parse_list(row["r2_pron_roman_json"], label=f"r2 Roman {token}")
                    if len(phones) != 1 or len(romans) != 1:
                        raise RuntimeError(f"eligible contextual variants differ: {token}")
                    updated["planning_candidate_variant_count"] = "1"
                    updated["planning_candidate_phones_json"] = row["r2_pron_phones_json"]
                    updated["planning_candidate_roman_json"] = row["r2_pron_roman_json"]
                    updated["planning_status"] = NEW_STATUS
                    updated["planning_source"] = "audited_frozen_dictionary_contextual_secondary_articulation"
                    updated["planning_reason"] = (
                        "retain the existing r2 phone sequence unchanged because every unresolved onset+glide relation has unanimous frozen-dictionary contextual support; this is model unitization evidence, not a standard-pronunciation or realization claim"
                    )
                    updated["planning_requires_policy_decision"] = "false"
                    updated["planning_zero_fallback_hold"] = "false"
                    updated["planning_is_final_selection"] = "false"
                    updated["planning_candidate_role"] = "mfa_alignment_lexicon_candidate"
                    updated["planning_standard_relation"] = "contextual_model_unitization_not_standard_pronunciation_claim"
                    updated["planning_actual_realization_status"] = "not_performed"
                    updated["contextual_secondary_articulation_evidence_json"] = json.dumps(
                        evidence_summary(rows), ensure_ascii=False
                    )
                    updated["contextual_secondary_articulation_candidate_eligible"] = "true"
                    new_types += 1
                    new_occurrences += total
                else:
                    updated["contextual_secondary_articulation_evidence_json"] = "[]"
                    updated["contextual_secondary_articulation_candidate_eligible"] = "false"
                    if any(updated[field] != row[field] for field in V2_FIELDS):
                        raise RuntimeError(f"ineligible readiness v2 fields changed: {token}")
            else:
                updated["contextual_donor_support_class"] = "not_applicable_existing_planning"
                updated["contextual_secondary_articulation_evidence_json"] = "[]"
                updated["contextual_secondary_articulation_candidate_eligible"] = "false"
                if any(updated[field] != row[field] for field in V2_FIELDS):
                    raise RuntimeError(f"non-hold readiness v2 fields changed: {token}")
                preserved_rows += 1
            writer.writerow(updated)
            status = updated["planning_status"]
            planning_types[status] += 1
            planning_occurrences[status] += total
            context_status = updated["contextual_donor_support_class"]
            contextual_types[context_status] += 1
            contextual_occurrences[context_status] += total
            candidate_types += int(status.startswith("candidate_"))
            candidate_occurrences += total if status.startswith("candidate_") else 0
            hold_types += int(updated["planning_zero_fallback_hold"] == "true")
            hold_occurrences += total if updated["planning_zero_fallback_hold"] == "true" else 0
            policy_types += int(updated["planning_requires_policy_decision"] == "true")
            policy_occurrences += total if updated["planning_requires_policy_decision"] == "true" else 0
            row_count += 1
            total_occurrences += total
    if consumed != set(classifications):
        raise RuntimeError("unconsumed contextual donor audit tokens")
    eligibility = policy["eligibility"]
    if (
        new_types != int(eligibility["expected_newly_eligible_types"])
        or new_occurrences != int(eligibility["expected_newly_eligible_occurrences"])
    ):
        raise RuntimeError("contextual secondary-articulation increment differs")
    if row_count != int(readiness_manifest["counts"]["canonical_types"]):
        raise RuntimeError("readiness v3 canonical coverage differs")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_planning_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "existing_r2_phone_sequences_changed": False,
            "planning_candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "inputs": {
            "readiness_v2_manifest": file_fingerprint(readiness_v2_manifest_path, with_sha256=True),
            "contextual_donor_manifest": file_fingerprint(contextual_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "readiness_v2": file_fingerprint(readiness_path, with_sha256=True),
            "contextual_classification": file_fingerprint(classification_path, with_sha256=True),
            "contextual_evidence": file_fingerprint(evidence_path, with_sha256=True),
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
            "newly_eligible_contextual_secondary_types": new_types,
            "newly_eligible_contextual_secondary_occurrences": new_occurrences,
            "preserved_non_hold_v2_rows": preserved_rows,
            "planning_status_types": dict(sorted(planning_types.items())),
            "planning_status_occurrences": dict(sorted(planning_occurrences.items())),
            "contextual_support_class_types": dict(sorted(contextual_types.items())),
            "contextual_support_class_occurrences": dict(sorted(contextual_occurrences.items())),
        },
        "outputs": {
            "selection_readiness_v3": fingerprint_for_final(output, final_output)
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_output, manifest)
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--readiness-v2-manifest", type=Path, required=True)
    result.add_argument("--contextual-donor-manifest", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build_readiness_v3(
        readiness_v2_manifest_path=args.readiness_v2_manifest.resolve(),
        contextual_manifest_path=args.contextual_donor_manifest.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
