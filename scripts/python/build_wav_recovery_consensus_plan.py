"""Build a fail-closed recovery plan from multi-resolution topology evidence."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint


SCHEMA_VERSION = "wav_recovery_consensus_plan.v1"
PLAN_FIELDS = [
    "year", "session", "target_utt_id", "source_utt_id", "status",
    "block_length", "target_duration_seconds", "source_duration_seconds",
    "duration_residual_seconds", "source_wav",
]
EVIDENCE_FIELDS = [
    "recovery_evidence_tier",
    "high_labels",
    "candidate_id_offset",
]
OUTPUT_FIELDS = PLAN_FIELDS + EVIDENCE_FIELDS
DEFAULT_SELECTED_TIERS = {
    "A_ALL_SCALE_CONSENSUS",
    "B_Q2_Q5_BRACKETED_SAME_OFFSET",
}
HIGH_STATUSES = {"identity_high_confidence", "remap_high_confidence"}


def read_by_target(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            target = (row.get("target_utt_id") or "").strip()
            if not target:
                continue
            if target in result:
                raise RuntimeError(f"target 중복: {target} ({path})")
            result[target] = row
    return result


def build(
    *,
    year: str,
    topology_rows: list[dict[str, str]],
    q1_rows: dict[str, dict[str, str]],
    q2_rows: dict[str, dict[str, str]],
    selected_tiers: set[str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    selected_tiers = selected_tiers or set(DEFAULT_SELECTED_TIERS)
    output: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    selected_tier_counts: Counter[str] = Counter()
    source_targets: dict[str, list[str]] = defaultdict(list)
    seen_targets: set[str] = set()

    for topology in topology_rows:
        target = topology["target_utt_id"]
        if target in seen_targets:
            raise RuntimeError(f"topology target 중복: {target}")
        seen_targets.add(target)
        if target not in q1_rows or target not in q2_rows:
            raise RuntimeError(f"원 계획에서 target 누락: {target}")
        tier = topology["topology_tier"]
        tier_counts[tier] += 1
        if tier == "A_ALL_SCALE_CONSENSUS":
            chosen = dict(q1_rows[target])
        elif tier == "B_Q2_Q5_BRACKETED_SAME_OFFSET":
            chosen = dict(q2_rows[target])
        else:
            chosen = dict(q1_rows[target])

        if tier in selected_tiers:
            if chosen.get("status") not in HIGH_STATUSES:
                raise RuntimeError(f"선택 tier가 고신뢰 상태가 아님: {target}")
            expected_source = topology.get("consensus_source_utt_id", "")
            if not expected_source or chosen.get("source_utt_id") != expected_source:
                raise RuntimeError(f"topology/source 불일치: {target}")
            selected_tier_counts[tier] += 1
            source_targets[expected_source].append(target)
        else:
            chosen.update(
                {
                    "source_utt_id": "",
                    "status": "target_unresolved",
                    "block_length": "0",
                    "source_duration_seconds": "",
                    "duration_residual_seconds": "",
                    "source_wav": "",
                }
            )
        if chosen.get("year") != year:
            raise RuntimeError(f"계획 연도 불일치: {target}")
        normalized = {field: chosen.get(field, "") for field in PLAN_FIELDS}
        normalized.update(
            {
                "recovery_evidence_tier": tier,
                "high_labels": topology.get("high_labels", ""),
                "candidate_id_offset": topology.get("candidate_id_offset", ""),
            }
        )
        output.append(normalized)
        status_counts[normalized["status"]] += 1

    duplicates = {
        source: targets
        for source, targets in source_targets.items()
        if len(targets) > 1
    }
    if duplicates:
        first_source = sorted(duplicates)[0]
        raise RuntimeError(
            "선택 계획에서 source WAV 중복 배정: "
            f"{first_source} -> {duplicates[first_source][:10]}"
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "consensus_plan_built",
        "year": year,
        "mutates_wav": False,
        "target_count": len(output),
        "selected_tiers": sorted(selected_tiers),
        "topology_tier_counts": dict(sorted(tier_counts.items())),
        "selected_tier_counts": dict(sorted(selected_tier_counts.items())),
        "plan_status_counts": dict(sorted(status_counts.items())),
        "duplicate_selected_source_count": 0,
        "safe_to_auto_apply": False,
        "next_step": (
            "manifest에 고정된 층화 청취 검토를 승인한 뒤 corpus dry-run"
        ),
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--topology-csv", type=Path, required=True)
    parser.add_argument("--q1-plan", type=Path, required=True)
    parser.add_argument("--q2-plan", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()

    with args.topology_csv.open(encoding="utf-8-sig", newline="") as stream:
        topology_rows = list(csv.DictReader(stream))
    rows, report = build(
        year=str(args.year),
        topology_rows=topology_rows,
        q1_rows=read_by_target(args.q1_plan),
        q2_rows=read_by_target(args.q2_plan),
    )
    report["topology_csv"] = file_fingerprint(
        args.topology_csv.resolve(), with_sha256=True
    )
    report["q1_plan"] = file_fingerprint(args.q1_plan.resolve(), with_sha256=True)
    report["q2_plan"] = file_fingerprint(args.q2_plan.resolve(), with_sha256=True)
    with atomic_text_writer(
        args.output_csv.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temporary):
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    atomic_write_json(args.output_report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
