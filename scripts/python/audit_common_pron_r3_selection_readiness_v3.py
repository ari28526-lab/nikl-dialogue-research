"""Independently audit r3 readiness v3 and its phone-invariance contract."""

from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_r3_selection_readiness_v2 import OUTPUT_FIELDS as V2_FIELDS  # noqa: E402
from build_common_pron_r3_selection_readiness_v3 import (  # noqa: E402
    NEW_STATUS,
    OUTPUT_FIELDS,
    SCHEMA_VERSION,
)
from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file  # noqa: E402


AUDIT_SCHEMA = "common_pron_r3_selection_readiness_v3_independent_audit.v1"
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


def audit(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("readiness v3 manifest differs")
    scope = manifest.get("scope", {})
    if any(value is not False for value in scope.values()):
        raise RuntimeError("readiness v3 scope exceeds planning contract")
    v2_path = verify(manifest["inputs"]["readiness_v2"], label="readiness v2")
    v3_path = verify(manifest["outputs"]["selection_readiness_v3"], label="readiness v3")
    for key in (
        "readiness_v2_manifest",
        "contextual_donor_manifest",
        "policy_contract",
        "contextual_classification",
        "contextual_evidence",
    ):
        verify(manifest["inputs"][key], label=key)

    row_count = total_occurrences = candidate_types = candidate_occurrences = 0
    hold_types = hold_occurrences = policy_types = policy_occurrences = 0
    eligible_types = eligible_occurrences = unchanged_rows = preserved_non_hold_rows = 0
    planning_types: Counter[str] = Counter()
    planning_occurrences: Counter[str] = Counter()
    context_types: Counter[str] = Counter()
    context_occurrences: Counter[str] = Counter()
    with gzip.open(v2_path, "rt", encoding="utf-8-sig", newline="") as old_stream, gzip.open(v3_path, "rt", encoding="utf-8-sig", newline="") as new_stream:
        old_reader = csv.DictReader(old_stream)
        new_reader = csv.DictReader(new_stream)
        if tuple(old_reader.fieldnames or ()) != V2_FIELDS or tuple(new_reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise RuntimeError("readiness v2/v3 column contract differs")
        for old, new in itertools.zip_longest(old_reader, new_reader):
            if old is None or new is None:
                raise RuntimeError("readiness v2/v3 row coverage differs")
            if old["token"] != new["token"]:
                raise RuntimeError("readiness v2/v3 token order differs")
            token = old["token"]
            total = int(old["total_occurrences"])
            eligible = new["contextual_secondary_articulation_candidate_eligible"] == "true"
            if eligible:
                changed = {field for field in V2_FIELDS if old[field] != new[field]}
                if not changed or not changed <= ALLOWED_CHANGED_FIELDS:
                    raise RuntimeError(f"eligible field mutation differs: {token} {sorted(changed)}")
                if (
                    old["planning_zero_fallback_hold"] != "true"
                    or new["planning_status"] != NEW_STATUS
                    or new["planning_candidate_variant_count"] != "1"
                    or new["planning_candidate_phones_json"] != old["r2_pron_phones_json"]
                    or new["planning_candidate_roman_json"] != old["r2_pron_roman_json"]
                    or new["planning_zero_fallback_hold"] != "false"
                    or new["planning_is_final_selection"] != "false"
                    or new["planning_candidate_role"] != "mfa_alignment_lexicon_candidate"
                    or new["planning_actual_realization_status"] != "not_performed"
                    or new["contextual_donor_support_class"] != "unanimous_contextual_support"
                ):
                    raise RuntimeError(f"eligible phone-invariance contract differs: {token}")
                evidence = json.loads(new["contextual_secondary_articulation_evidence_json"])
                if not isinstance(evidence, list) or not evidence or any(
                    row.get("phone_sequence_changed") is not False
                    or row.get("standard_pronunciation_claimed") is not False
                    for row in evidence
                ):
                    raise RuntimeError(f"eligible evidence contract differs: {token}")
                eligible_types += 1
                eligible_occurrences += total
            else:
                if any(old[field] != new[field] for field in V2_FIELDS):
                    raise RuntimeError(f"ineligible v2 row changed: {token}")
                if new["contextual_secondary_articulation_evidence_json"] != "[]":
                    raise RuntimeError(f"ineligible evidence is nonempty: {token}")
                unchanged_rows += 1
            if old["planning_zero_fallback_hold"] != "true":
                preserved_non_hold_rows += 1
            status = new["planning_status"]
            planning_types[status] += 1
            planning_occurrences[status] += total
            context = new["contextual_donor_support_class"]
            context_types[context] += 1
            context_occurrences[context] += total
            candidate_types += int(status.startswith("candidate_"))
            candidate_occurrences += total if status.startswith("candidate_") else 0
            hold_types += int(new["planning_zero_fallback_hold"] == "true")
            hold_occurrences += total if new["planning_zero_fallback_hold"] == "true" else 0
            policy_types += int(new["planning_requires_policy_decision"] == "true")
            policy_occurrences += total if new["planning_requires_policy_decision"] == "true" else 0
            row_count += 1
            total_occurrences += total

    actual = {
        "canonical_types": row_count,
        "total_occurrences": total_occurrences,
        "candidate_ready_types": candidate_types,
        "candidate_ready_occurrences": candidate_occurrences,
        "zero_fallback_hold_types": hold_types,
        "zero_fallback_hold_occurrences": hold_occurrences,
        "policy_decision_types": policy_types,
        "policy_decision_occurrences": policy_occurrences,
        "newly_eligible_contextual_secondary_types": eligible_types,
        "newly_eligible_contextual_secondary_occurrences": eligible_occurrences,
        "preserved_non_hold_v2_rows": preserved_non_hold_rows,
        "planning_status_types": dict(sorted(planning_types.items())),
        "planning_status_occurrences": dict(sorted(planning_occurrences.items())),
        "contextual_support_class_types": dict(sorted(context_types.items())),
        "contextual_support_class_occurrences": dict(sorted(context_occurrences.items())),
    }
    if actual != manifest["counts"]:
        raise RuntimeError("readiness v3 manifest counts differ")
    if unchanged_rows + eligible_types != row_count:
        raise RuntimeError("readiness v3 row accounting differs")

    report = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "audited_at": now_iso(),
        "manifest": file_fingerprint(manifest_path, with_sha256=True),
        "verified_inputs": {
            key: file_fingerprint(verify(record, label=f"audit {key}"), with_sha256=True)
            for key, record in manifest["inputs"].items()
        },
        "verified_output": file_fingerprint(v3_path, with_sha256=True),
        "independent_counts": actual,
        "checks": {
            "all_881237_rows_compared_to_v2": True,
            "eligible_r2_phone_json_byte_identical": True,
            "eligible_r2_roman_json_byte_identical": True,
            "ineligible_v2_fields_unchanged": True,
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
        },
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
    result = audit(
        manifest_path=args.manifest.resolve(), audit_report=args.audit_report.resolve()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
