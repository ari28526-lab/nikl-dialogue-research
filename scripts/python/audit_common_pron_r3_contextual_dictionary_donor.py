"""Independently audit the read-only r3 contextual dictionary donor stage."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import read_mfa_dictionary  # noqa: E402
from build_common_pron_r3_contextual_dictionary_donor_audit import (  # noqa: E402
    CLASS_CONFLICT,
    CLASS_MULTIPLE,
    CLASS_NONE,
    CLASS_UNANIMOUS,
    HOLD_FIELDS,
    INVENTORY_FIELDS,
    ISSUE_FIELDS,
    SCHEMA_VERSION,
)
from build_common_pron_r3_selection_readiness_v2 import (  # noqa: E402
    OUTPUT_FIELDS as READINESS_FIELDS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
)


AUDIT_SCHEMA = "common_pron_r3_contextual_dictionary_donor_independent_audit.v1"
FALSE_FIELDS_INVENTORY = (
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
)
FALSE_FIELDS_ISSUE = FALSE_FIELDS_INVENTORY
FALSE_FIELDS_HOLD = (
    "researcher_review_required_now",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
    "canonical_selection_performed",
)


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


def independent_issue_class(canonical: set[str], frozen: set[str]) -> str:
    if not canonical and not frozen:
        return CLASS_NONE
    if canonical and frozen and canonical.isdisjoint(frozen):
        return CLASS_CONFLICT
    if len(canonical | frozen) == 1:
        return CLASS_UNANIMOUS
    return CLASS_MULTIPLE


def independent_aggregate(classes: list[str], *, variant_count: int = 1) -> str:
    if not classes:
        return CLASS_NONE
    if CLASS_CONFLICT in classes:
        return CLASS_CONFLICT
    if CLASS_NONE in classes:
        return CLASS_NONE
    if CLASS_MULTIPLE in classes or variant_count > 1:
        return CLASS_MULTIPLE
    return CLASS_UNANIMOUS


def audit(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("contextual donor manifest differs")
    scope = manifest.get("scope", {})
    required_true = ("contextual_donor_inventory_built", "all_zero_fallback_holds_classified")
    required_false = (
        "global_phone_to_phoneme_mapping_applied",
        "candidate_generation_performed",
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "source_files_modified",
        "actual_realization_claimed",
    )
    if any(scope.get(key) is not True for key in required_true) or any(
        scope.get(key) is not False for key in required_false
    ):
        raise RuntimeError("contextual donor scope invariants differ")

    readiness_path = verify(manifest["inputs"]["readiness_v2"], label="readiness v2")
    dictionary_path = verify(manifest["inputs"]["base_dictionary"], label="base dictionary")
    verify(manifest["inputs"]["readiness_v2_manifest"], label="readiness manifest")
    verify(manifest["inputs"]["acoustic_model"], label="acoustic model")
    verify(manifest["inputs"]["policy_contract"], label="policy")
    inventory_path = verify(
        manifest["outputs"]["frozen_dictionary_contextual_inventory"], label="inventory"
    )
    issue_path = verify(
        manifest["outputs"]["residual_hold_contextual_evidence"], label="issue evidence"
    )
    hold_path = verify(
        manifest["outputs"]["residual_hold_contextual_classification"], label="hold classification"
    )

    _, dictionary = read_mfa_dictionary(dictionary_path)
    expected_dictionary_variants = {
        (token, index)
        for token in dictionary
        for index, _ in enumerate(sorted(dictionary[token]), 1)
    }
    observed_dictionary_variants: set[tuple[str, int]] = set()
    inventory_counts: Counter[str] = Counter()
    with gzip.open(inventory_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != INVENTORY_FIELDS:
            raise RuntimeError("inventory column contract differs")
        for row in reader:
            marker = (row["token"], int(row["variant_index"]))
            if marker in observed_dictionary_variants:
                raise RuntimeError(f"duplicate dictionary inventory variant: {marker}")
            observed_dictionary_variants.add(marker)
            if any(row[field] != "false" for field in FALSE_FIELDS_INVENTORY):
                raise RuntimeError(f"inventory mutation/claim flag differs: {marker}")
            mappings = json.loads(row["contextual_mappings_json"])
            unsupported = json.loads(row["unsupported_operations_json"])
            if not isinstance(mappings, list) or not isinstance(unsupported, list):
                raise RuntimeError(f"inventory JSON contract differs: {marker}")
            direct = sum(item.get("relation_kind") == "direct_unit" for item in mappings)
            secondary = sum(
                item.get("relation_kind") == "secondary_articulation_cluster"
                for item in mappings
            )
            if direct != int(row["direct_mapping_count"]) or secondary != int(
                row["secondary_articulation_mapping_count"]
            ):
                raise RuntimeError(f"inventory mapping count differs: {marker}")
            expected_status = (
                "complete_contextual_mapping" if not unsupported else "partial_unsupported_mapping"
            )
            if row["mapping_status"] != expected_status:
                raise RuntimeError(f"inventory status differs: {marker}")
            inventory_counts["variant_rows"] += 1
            inventory_counts[expected_status] += 1
            inventory_counts["direct_mapping_rows"] += direct
            inventory_counts["secondary_articulation_mapping_rows"] += secondary
    missing_inventory = expected_dictionary_variants - observed_dictionary_variants
    extra_inventory = observed_dictionary_variants - expected_dictionary_variants
    # Tokens without a project rule are deliberately absent, but an observed
    # row must always be a true frozen-dictionary variant.
    if extra_inventory:
        raise RuntimeError(f"inventory includes non-dictionary variants: {len(extra_inventory)}")
    inventory_counts["dictionary_variant_rows_not_inventory_due_to_no_rule"] = len(missing_inventory)

    readiness_holds: dict[str, dict[str, object]] = {}
    readiness_occurrences = 0
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness v2 column contract differs")
        for row in reader:
            if row["planning_zero_fallback_hold"] != "true":
                continue
            token = row["token"]
            if token in readiness_holds:
                raise RuntimeError(f"duplicate readiness hold: {token}")
            variants = json.loads(row["r2_pron_phones_json"])
            if not isinstance(variants, list) or not variants:
                raise RuntimeError(f"readiness hold variant contract differs: {token}")
            readiness_holds[token] = {
                "occurrences": int(row["total_occurrences"]),
                "planning_status": row["planning_status"],
                "variant_count": len(variants),
            }
            readiness_occurrences += int(row["total_occurrences"])

    issues_by_variant: dict[tuple[str, int], list[str]] = defaultdict(list)
    issue_counts_by_token: Counter[str] = Counter()
    canonical_counts_by_token: Counter[str] = Counter()
    frozen_counts_by_token: Counter[str] = Counter()
    issue_class_rows: Counter[str] = Counter()
    issue_rows = 0
    with gzip.open(issue_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != ISSUE_FIELDS:
            raise RuntimeError("issue evidence column contract differs")
        expected_issue_index: Counter[tuple[str, int]] = Counter()
        for row in reader:
            token = row["token"]
            if token not in readiness_holds:
                raise RuntimeError(f"issue token outside readiness holds: {token}")
            if row["planning_status"] != readiness_holds[token]["planning_status"]:
                raise RuntimeError(f"issue planning status differs: {token}")
            variant_index = int(row["variant_index"])
            if not 1 <= variant_index <= int(readiness_holds[token]["variant_count"]):
                raise RuntimeError(f"issue variant index differs: {token}")
            marker = (token, variant_index)
            expected_issue_index[marker] += 1
            if int(row["issue_index"]) != expected_issue_index[marker]:
                raise RuntimeError(f"issue order differs: {marker}")
            if any(row[field] != "false" for field in FALSE_FIELDS_ISSUE):
                raise RuntimeError(f"issue mutation/claim flag differs: {marker}")
            canonical_counts = json.loads(row["canonical_phone_counts_json"])
            frozen_counts = json.loads(row["frozen_phone_counts_json"])
            if not isinstance(canonical_counts, dict) or not isinstance(frozen_counts, dict):
                raise RuntimeError(f"issue phone counts differ: {marker}")
            expected_class = independent_issue_class(set(canonical_counts), set(frozen_counts))
            if row["evidence_class"] != expected_class:
                raise RuntimeError(f"issue class differs: {marker}")
            supported = set(canonical_counts) | set(frozen_counts)
            expected_supported = bool(
                row["current_candidate_phone"]
                and row["current_candidate_phone"] in supported
            )
            if row["current_candidate_supported"] != str(expected_supported).lower():
                raise RuntimeError(f"issue current-candidate support differs: {marker}")
            issues_by_variant[marker].append(expected_class)
            issue_counts_by_token[token] += 1
            canonical_counts_by_token[token] += int(bool(row["canonical_context_level"]))
            frozen_counts_by_token[token] += int(bool(row["frozen_context_level"]))
            issue_class_rows[expected_class] += 1
            issue_rows += 1

    expected_token_class: dict[str, str] = {}
    for token, metadata in readiness_holds.items():
        variant_classes = [
            independent_aggregate(issues_by_variant[(token, index)])
            for index in range(1, int(metadata["variant_count"]) + 1)
        ]
        expected_token_class[token] = independent_aggregate(
            variant_classes, variant_count=int(metadata["variant_count"])
        )

    hold_types: Counter[str] = Counter()
    hold_occurrences: Counter[str] = Counter()
    observed_holds: set[str] = set()
    with gzip.open(hold_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != HOLD_FIELDS:
            raise RuntimeError("hold classification column contract differs")
        for row in reader:
            token = row["token"]
            if token in observed_holds or token not in readiness_holds:
                raise RuntimeError(f"hold classification identity differs: {token}")
            observed_holds.add(token)
            metadata = readiness_holds[token]
            if (
                int(row["total_occurrences"]) != int(metadata["occurrences"])
                or row["planning_status"] != metadata["planning_status"]
                or int(row["audited_variant_count"]) != int(metadata["variant_count"])
                or int(row["audited_issue_count"]) != issue_counts_by_token[token]
                or int(row["canonical_supported_issue_count"])
                != canonical_counts_by_token[token]
                or int(row["frozen_supported_issue_count"]) != frozen_counts_by_token[token]
                or row["contextual_support_class"] != expected_token_class[token]
            ):
                raise RuntimeError(f"hold classification content differs: {token}")
            audit_json = json.loads(row["variant_audit_json"])
            if not isinstance(audit_json, list) or len(audit_json) != int(metadata["variant_count"]):
                raise RuntimeError(f"hold variant audit differs: {token}")
            if any(row[field] != "false" for field in FALSE_FIELDS_HOLD):
                raise RuntimeError(f"hold mutation/claim flag differs: {token}")
            category = row["contextual_support_class"]
            hold_types[category] += 1
            hold_occurrences[category] += int(metadata["occurrences"])
    if observed_holds != set(readiness_holds):
        raise RuntimeError("hold classification does not cover readiness holds")

    expected_counts = manifest["counts"]
    if (
        int(expected_counts["hold_types"]) != len(readiness_holds)
        or int(expected_counts["hold_occurrences"]) != readiness_occurrences
        or int(expected_counts["hold_issue_rows"]) != issue_rows
        or expected_counts["issue_evidence_class_rows"] != dict(sorted(issue_class_rows.items()))
        or expected_counts["hold_contextual_support_class_types"] != dict(sorted(hold_types.items()))
        or expected_counts["hold_contextual_support_class_occurrences"]
        != dict(sorted(hold_occurrences.items()))
    ):
        raise RuntimeError("manifest contextual donor counts differ")

    report = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "audited_at": now_iso(),
        "manifest": file_fingerprint(manifest_path, with_sha256=True),
        "verified_inputs": {
            key: file_fingerprint(verify(record, label=f"audit {key}"), with_sha256=True)
            for key, record in manifest["inputs"].items()
        },
        "verified_outputs": {
            key: file_fingerprint(verify(record, label=f"audit {key}"), with_sha256=True)
            for key, record in manifest["outputs"].items()
        },
        "independent_counts": {
            "dictionary_inventory_rows": dict(sorted(inventory_counts.items())),
            "readiness_hold_types": len(readiness_holds),
            "readiness_hold_occurrences": readiness_occurrences,
            "issue_rows": issue_rows,
            "issue_evidence_class_rows": dict(sorted(issue_class_rows.items())),
            "hold_contextual_support_class_types": dict(sorted(hold_types.items())),
            "hold_contextual_support_class_occurrences": dict(sorted(hold_occurrences.items())),
        },
        "checks": {
            "all_output_fingerprints_match": True,
            "inventory_rows_are_frozen_dictionary_variants": True,
            "issue_classes_recomputed": True,
            "hold_classes_recomputed": True,
            "readiness_hold_coverage_complete": True,
            "candidate_generation_performed": False,
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
