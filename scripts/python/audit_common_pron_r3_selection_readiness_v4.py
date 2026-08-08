"""Independently audit readiness v4 against v3 and Stage 17."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from itertools import zip_longest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_r3_attested_full_sequence_projection import (  # noqa: E402
    OUTPUT_FIELDS as STAGE17_FIELDS,
)
from build_common_pron_r3_selection_readiness_v3 import OUTPUT_FIELDS  # noqa: E402
from build_common_pron_r3_selection_readiness_v4 import (  # noqa: E402
    ALLOWED_CHANGED_FIELDS,
    NEW_STATUS,
    SCHEMA_VERSION,
    STATUS,
)
from pipeline_common import atomic_write_json, now_iso, sha256_file  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCHEMA = "common_pron_r3_selection_readiness_v4_audit.v1"


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


def expected_target_values(source: dict[str, str], candidate: dict[str, str]) -> dict[str, str]:
    return {
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


def audit(manifest_path: Path, output_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RuntimeError("readiness v4 manifest identity differs")
    for key, record in manifest["inputs"].items():
        verify(record, Path(str(record["path"])), label=f"input {key}")
    output_record = manifest["outputs"]["selection_readiness_v4"]
    output_path_v4 = Path(str(output_record["path"])).resolve()
    verify(output_record, output_path_v4, label="readiness v4")
    source_path = Path(str(manifest["inputs"]["readiness_v3"]["path"])).resolve()
    stage17_path = Path(str(manifest["inputs"]["stage17_projection_inventory"]["path"])).resolve()
    candidates: dict[str, dict[str, str]] = {}
    with gzip.open(stage17_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != STAGE17_FIELDS:
            raise RuntimeError("Stage 17 columns differ")
        for row in reader:
            if row["automatic_candidate_eligible"] == "true":
                candidates[row["token"]] = row
    if len(candidates) != 14 or sum(int(row["total_occurrences"]) for row in candidates.values()) != 200:
        raise RuntimeError("Stage 17 audited candidate accounting differs")

    row_count = total_occurrences = changed_types = changed_occurrences = 0
    candidate_types = candidate_occurrences = hold_types = hold_occurrences = 0
    status_types: Counter[str] = Counter()
    status_occurrences: Counter[str] = Counter()
    consumed: set[str] = set()
    with gzip.open(source_path, "rt", encoding="utf-8-sig", newline="") as left, gzip.open(
        output_path_v4, "rt", encoding="utf-8-sig", newline=""
    ) as right:
        old_reader = csv.DictReader(left)
        new_reader = csv.DictReader(right)
        if tuple(old_reader.fieldnames or ()) != OUTPUT_FIELDS or tuple(new_reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise RuntimeError("readiness v3/v4 columns differ")
        for old, new in zip_longest(old_reader, new_reader):
            if old is None or new is None:
                raise RuntimeError("readiness v3/v4 row count differs")
            if old["token"] != new["token"]:
                raise RuntimeError("readiness v3/v4 row order differs")
            token = old["token"]
            changed = {field for field in OUTPUT_FIELDS if old[field] != new[field]}
            if token in candidates:
                if old["planning_zero_fallback_hold"] != "true":
                    raise RuntimeError(f"target was not a v3 hold: {token}")
                if not changed or not changed <= ALLOWED_CHANGED_FIELDS:
                    raise RuntimeError(f"target changed fields differ: {token} {sorted(changed)}")
                expected = expected_target_values(old, candidates[token])
                for field, value in expected.items():
                    if new[field] != value:
                        raise RuntimeError(f"target field differs: {token} {field}")
                consumed.add(token)
                changed_types += 1
                changed_occurrences += int(new["total_occurrences"])
            elif changed:
                raise RuntimeError(f"non-target readiness row changed: {token} {sorted(changed)}")
            total = int(new["total_occurrences"])
            row_count += 1
            total_occurrences += total
            status_types[new["planning_status"]] += 1
            status_occurrences[new["planning_status"]] += total
            is_candidate = new["planning_status"].startswith("candidate_")
            candidate_types += int(is_candidate)
            candidate_occurrences += total if is_candidate else 0
            is_hold = new["planning_zero_fallback_hold"] == "true"
            hold_types += int(is_hold)
            hold_occurrences += total if is_hold else 0
            if new["planning_is_final_selection"] != "false":
                raise RuntimeError(f"final selection flag differs: {token}")
    if consumed != set(candidates):
        raise RuntimeError("not all Stage 17 candidates were merged")
    counts = {
        "canonical_types": row_count,
        "total_occurrences": total_occurrences,
        "candidate_ready_types": candidate_types,
        "candidate_ready_occurrences": candidate_occurrences,
        "zero_fallback_hold_types": hold_types,
        "zero_fallback_hold_occurrences": hold_occurrences,
        "changed_target_types": changed_types,
        "changed_target_occurrences": changed_occurrences,
    }
    expected_counts = {
        key: int(manifest["counts"][key])
        for key in (
            "canonical_types",
            "total_occurrences",
            "candidate_ready_types",
            "candidate_ready_occurrences",
            "zero_fallback_hold_types",
            "zero_fallback_hold_occurrences",
        )
    }
    if {key: counts[key] for key in expected_counts} != expected_counts:
        raise RuntimeError("readiness v4 manifest accounting differs")
    if changed_types != 14 or changed_occurrences != 200:
        raise RuntimeError("readiness v4 delta accounting differs")

    report = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_full_v3_delta_audit",
        "recorded_at": now_iso(),
        "manifest": {
            "path": str(manifest_path.resolve()),
            "sha256": sha256_file(manifest_path),
        },
        "counts": {
            **counts,
            "planning_status_types": dict(sorted(status_types.items())),
            "planning_status_occurrences": dict(sorted(status_occurrences.items())),
        },
        "invariants": manifest["scope"],
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "reports" / "AUDIT_common_pron_r3_selection_readiness_v4_20260808.json",
    )
    args = parser.parse_args()
    report = audit(args.manifest.resolve(), args.output.resolve())
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
