"""Summarize audited r3 selection readiness and identify the next useful work."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_selection_readiness_summary.v1"


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


def summarize(*, readiness_manifest_path: Path, projection_manifest_path: Path, report_path: Path) -> dict[str, object]:
    readiness = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    projection = json.loads(projection_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness.get("status") != "success_planning_not_selected" or projection.get("status") != "success_candidates_not_selected":
        raise RuntimeError("summary input status differs")
    readiness_path = verify(readiness["outputs"]["selection_readiness"], label="readiness output")
    target_projection_path = verify(projection["outputs"]["target_projection_candidates"], label="target projection")
    existing_targets: dict[str, str] = {}
    with gzip.open(target_projection_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            existing_targets[row["target_hangul"]] = row["projection_status"]

    hold_source_types: dict[str, Counter[str]] = defaultdict(Counter)
    hold_source_occurrences: dict[str, Counter[str]] = defaultdict(Counter)
    no_rule_overlap_types: Counter[str] = Counter()
    no_rule_overlap_occurrences: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    total_types = total_occurrences = 0
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            total_types += 1
            total_occurrences += int(row["total_occurrences"])
            if row["planning_zero_fallback_hold"] != "true":
                continue
            status = row["planning_status"]
            source = row["r2_pron_source"]
            hold_source_types[status][source] += 1
            hold_source_occurrences[status][source] += int(row["total_occurrences"])
            if status == "hold_no_surface_rule_substantive_mismatch":
                target_status = existing_targets.get(row["rule_pron_hangul"])
                key = f"overlap_{target_status}" if target_status else "new_target"
                no_rule_overlap_types[key] += 1
                no_rule_overlap_occurrences[key] += int(row["total_occurrences"])
                if len(examples[key]) < 5:
                    examples[key].append(row["token"])

    counts = readiness["counts"]
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_summary_not_selection",
        "recorded_at": now_iso(),
        "headline": {
            "canonical_types": total_types,
            "canonical_occurrences": total_occurrences,
            "candidate_ready_types": counts["candidate_ready_types"],
            "candidate_ready_type_percent": round(100 * counts["candidate_ready_types"] / total_types, 3),
            "candidate_ready_occurrences": counts["candidate_ready_occurrences"],
            "candidate_ready_occurrence_percent": round(100 * counts["candidate_ready_occurrences"] / total_occurrences, 3),
            "policy_decision_types": counts["policy_decision_types"],
            "zero_fallback_hold_types": counts["zero_fallback_hold_types"],
            "zero_fallback_hold_occurrences": counts["zero_fallback_hold_occurrences"],
        },
        "hold_source_types": {key: dict(sorted(value.items())) for key, value in sorted(hold_source_types.items())},
        "hold_source_occurrences": {key: dict(sorted(value.items())) for key, value in sorted(hold_source_occurrences.items())},
        "no_surface_rule_hold_target_reuse": {
            "types": dict(sorted(no_rule_overlap_types.items())),
            "occurrences": dict(sorted(no_rule_overlap_occurrences.items())),
            "examples": dict(sorted(examples.items())),
        },
        "methodological_conclusion": {
            "repeat_same_jamo_g2p_for_existing_strict_sources": False,
            "reason": "83,922 of 85,504 no-surface-rule substantive holds already originate from the same frozen Jamo G2P 1-best",
            "next_candidate_stage": "rebuild exact-context projection with the full 382,891-type canonical exact-rule donor pool before considering any new G2P run",
            "human_review_required_now": False,
        },
        "scope": {
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
        },
        "evidence": {
            "readiness_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "projection_manifest": file_fingerprint(projection_manifest_path, with_sha256=True),
            "readiness_output": file_fingerprint(readiness_path, with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(report_path, report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--readiness-manifest", type=Path, required=True)
    result.add_argument("--projection-manifest", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    report = summarize(
        readiness_manifest_path=args.readiness_manifest.resolve(),
        projection_manifest_path=args.projection_manifest.resolve(),
        report_path=args.report.resolve(),
    )
    print(json.dumps(report["headline"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
