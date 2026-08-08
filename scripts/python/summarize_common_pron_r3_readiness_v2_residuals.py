"""Summarize the two audited zero-fallback hold layers in readiness v2."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file


SCHEMA_VERSION = "common_pron_r3_readiness_v2_residual_priorities.v1"
TARGET_HOLD = "hold_target_projection_unresolved"
NO_RULE_HOLD = "hold_no_surface_rule_substantive_mismatch"


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


def no_rule_pattern_key(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    return (
        rows[0]["r2_pron_source"],
        rows[0]["diagnostic_status"] if len(rows) == 1 else "multiple_variant_diagnostics",
        " || ".join(sorted({row["edit_signature"] for row in rows})),
    )


def sorted_patterns(
    type_counts: Counter[tuple[str, ...]],
    occurrence_counts: Counter[tuple[str, ...]],
    examples: dict[tuple[str, ...], list[dict[str, object]]],
    *,
    limit: int = 50,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    ordered = sorted(
        type_counts, key=lambda item: (-occurrence_counts[item], -type_counts[item], item)
    )[:limit]
    for key in ordered:
        result.append(
            {
                "key": list(key),
                "type_count": type_counts[key],
                "occurrence_count": occurrence_counts[key],
                "top_examples": sorted(
                    examples[key],
                    key=lambda row: (-int(row["total_occurrences"]), str(row["token"])),
                )[:10],
            }
        )
    return result


def summarize(
    *, readiness_manifest_path: Path, coverage_manifest_path: Path, output_path: Path
) -> dict[str, object]:
    readiness_manifest = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    coverage_manifest = json.loads(coverage_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness_manifest.get("status") != "success_planning_not_selected":
        raise RuntimeError("readiness v2 is not a completed planning artifact")
    if coverage_manifest.get("status") != "success_audited_not_candidate":
        raise RuntimeError("coverage input is not audited")
    readiness_path = verify(
        readiness_manifest["outputs"]["selection_readiness_v2"], label="readiness v2"
    )
    coverage_path = verify(
        coverage_manifest["outputs"]["variant_coverage"], label="coverage variants"
    )
    coverage_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    with gzip.open(coverage_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            coverage_groups[row["token"]].append(row)

    target_types: Counter[tuple[str, ...]] = Counter()
    target_occurrences: Counter[tuple[str, ...]] = Counter()
    target_examples: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    no_rule_types: Counter[tuple[str, ...]] = Counter()
    no_rule_occurrences: Counter[tuple[str, ...]] = Counter()
    no_rule_examples: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    hold_types: Counter[str] = Counter()
    hold_occurrences: Counter[str] = Counter()
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            status = row["planning_status"]
            if row["planning_zero_fallback_hold"] != "true":
                continue
            total = int(row["total_occurrences"])
            hold_types[status] += 1
            hold_occurrences[status] += total
            if status == TARGET_HOLD:
                key = (
                    row["target_projection_status"],
                    row["target_representation_relation"],
                    row["source_projection_gate_class"],
                    row["surface_rule_names"],
                )
                target_types[key] += 1
                target_occurrences[key] += total
                target_examples[key].append(
                    {
                        "token": row["token"],
                        "total_occurrences": total,
                        "rule_pron_roman": row["rule_pron_roman"],
                        "r2_pron_roman_json": row["r2_pron_roman_json"],
                    }
                )
            elif status == NO_RULE_HOLD:
                details = coverage_groups.get(row["token"])
                if not details:
                    raise RuntimeError(f"missing no-rule coverage: {row['token']}")
                key = no_rule_pattern_key(details)
                no_rule_types[key] += 1
                no_rule_occurrences[key] += total
                no_rule_examples[key].append(
                    {
                        "token": row["token"],
                        "total_occurrences": total,
                        "no_rule_coverage_status": row["no_rule_coverage_status"],
                        "rule_pron_roman": row["rule_pron_roman"],
                        "r2_pron_roman_json": row["r2_pron_roman_json"],
                    }
                )
            else:
                raise RuntimeError(f"unexpected zero-fallback hold: {status}")
    expected_types = int(readiness_manifest["counts"]["zero_fallback_hold_types"])
    expected_occurrences = int(
        readiness_manifest["counts"]["zero_fallback_hold_occurrences"]
    )
    if sum(hold_types.values()) != expected_types or sum(hold_occurrences.values()) != expected_occurrences:
        raise RuntimeError("residual hold coverage differs")
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_summary_read_only",
        "recorded_at": now_iso(),
        "hold_types": dict(sorted(hold_types.items())),
        "hold_occurrences": dict(sorted(hold_occurrences.items())),
        "target_projection_distinct_patterns": len(target_types),
        "no_rule_distinct_patterns": len(no_rule_types),
        "target_projection_patterns": sorted_patterns(
            target_types, target_occurrences, target_examples
        ),
        "no_rule_patterns": sorted_patterns(
            no_rule_types, no_rule_occurrences, no_rule_examples
        ),
        "next_methodological_priority": [
            "expand conflict-aware exact-context donors from the frozen base dictionary without rerunning G2P",
            "model secondary-articulation and glide unitization as context-sensitive compatibility, not a global phone-to-phoneme map",
            "audit mandatory Korean vowel rules such as consonant-plus-ㅢ separately from model representation",
            "keep segment-deletion cases such as 중에서 fail-closed",
        ],
        "contracts": {
            "candidate_generation_performed": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "source_files_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "readiness_v2_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "coverage_manifest": file_fingerprint(coverage_manifest_path, with_sha256=True),
            "readiness_v2": file_fingerprint(readiness_path, with_sha256=True),
            "coverage_variants": file_fingerprint(coverage_path, with_sha256=True),
        },
    }
    atomic_write_json(output_path, report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--readiness-manifest", type=Path, required=True)
    result.add_argument("--coverage-manifest", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    report = summarize(
        readiness_manifest_path=args.readiness_manifest.resolve(),
        coverage_manifest_path=args.coverage_manifest.resolve(),
        output_path=args.output.resolve(),
    )
    print(json.dumps({"hold_types": report["hold_types"], "hold_occurrences": report["hold_occurrences"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
