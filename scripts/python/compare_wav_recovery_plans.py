"""Compare WAV-ID recovery plans without mutating any corpus files.

Only utterances already identified by the input audit as audio-pairing issues
are compared. A mapping is called consensus only when every supplied plan marks
it high-confidence and proposes the exact same source WAV ID.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint


SCHEMA_VERSION = "wav_recovery_plan_comparison.v1"
RELEVANT_ISSUES = {
    "duration_residual_mismatch",
    "duration_wav_missing",
    "duration_wav_too_small",
    "wav_header_unreadable",
}
HIGH_STATUSES = {"identity_high_confidence", "remap_high_confidence"}


def parse_plan_argument(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--plan은 LABEL=PATH 형식이어야 함")
    label, raw_path = value.split("=", 1)
    label = label.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", label):
        raise argparse.ArgumentTypeError(f"plan label 형식 오류: {label}")
    return label, Path(raw_path)


def load_affected_ids(audit_path: Path, year: str) -> set[str]:
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    reports = [
        item for item in audit.get("years", [])
        if str(item.get("year")) == str(year)
    ]
    if len(reports) != 1:
        raise RuntimeError("감사 보고서 연도 결과가 정확히 1개가 아님")
    result: set[str] = set()
    for issue in reports[0].get("issue_inventory", []):
        if str(issue.get("issue") or "") not in RELEVANT_ISSUES:
            continue
        utt_id = str(issue.get("utt_id") or "").strip()
        if not utt_id:
            raise RuntimeError("audio pairing issue에 utt_id가 없음")
        result.add(utt_id)
    if not result:
        raise RuntimeError("비교할 audio pairing issue가 0개임")
    return result


def load_plan(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            target = (row.get("target_utt_id") or "").strip()
            if not target:
                continue
            if target in rows:
                raise RuntimeError(f"plan target 중복: {target} ({path})")
            rows[target] = row
    return rows


def compare(
    *,
    year: str,
    audit_path: Path,
    plans: list[tuple[str, Path]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if len(plans) < 2:
        raise RuntimeError("비교 계획은 최소 2개여야 함")
    labels = [label for label, _path in plans]
    if len(set(labels)) != len(labels):
        raise RuntimeError("plan label 중복")

    affected_ids = load_affected_ids(audit_path, year)
    plan_rows = {
        label: load_plan(path.resolve()) for label, path in plans
    }
    for label, rows in plan_rows.items():
        missing = sorted(affected_ids - set(rows))
        if missing:
            raise RuntimeError(f"{label} plan에서 issue 누락: {missing[:20]}")

    output_rows: list[dict[str, object]] = []
    classification_counts: Counter[str] = Counter()
    high_label_signature_counts: Counter[str] = Counter()
    high_counts: dict[str, Counter[str]] = {
        label: Counter() for label in labels
    }
    mapped_source_targets: dict[str, dict[str, list[str]]] = {
        label: defaultdict(list) for label in labels
    }

    for target in sorted(affected_ids):
        current = {label: plan_rows[label][target] for label in labels}
        sessions = {str(row.get("session") or "") for row in current.values()}
        if len(sessions) != 1 or not next(iter(sessions)):
            raise RuntimeError(f"plan 간 session 불일치: {target} -> {sessions}")
        session = next(iter(sessions))
        high_sources: list[str] = []
        high_labels: list[str] = []
        all_high = True
        for label in labels:
            status = current[label].get("status", "")
            source = current[label].get("source_utt_id", "")
            high_counts[label][status] += 1
            if status in HIGH_STATUSES and source:
                high_sources.append(source)
                high_labels.append(label)
                mapped_source_targets[label][source].append(target)
            else:
                all_high = False

        distinct_high_sources = set(high_sources)
        consensus_source = ""
        if all_high and len(distinct_high_sources) == 1:
            consensus_source = next(iter(distinct_high_sources))
            if consensus_source == target:
                classification = "consensus_identity"
            else:
                classification = "consensus_remap"
        elif len(distinct_high_sources) > 1:
            classification = "conflicting_high_source"
        elif high_sources:
            classification = "partial_high_same_source"
            consensus_source = high_sources[0]
        else:
            classification = "no_high_mapping"
        classification_counts[classification] += 1
        high_signature = "+".join(high_labels) if high_labels else "none"
        high_label_signature_counts[high_signature] += 1

        output: dict[str, object] = {
            "year": year,
            "session": session,
            "target_utt_id": target,
            "classification": classification,
            "consensus_source_utt_id": consensus_source,
            "high_plan_count": len(high_labels),
            "high_labels": high_signature,
        }
        for label in labels:
            row = current[label]
            output[f"status_{label}"] = row.get("status", "")
            output[f"source_utt_id_{label}"] = row.get("source_utt_id", "")
            output[f"block_length_{label}"] = row.get("block_length", "")
            output[f"duration_residual_seconds_{label}"] = row.get(
                "duration_residual_seconds", ""
            )
        output_rows.append(output)

    duplicate_sources = {
        label: {
            source: targets
            for source, targets in source_targets.items()
            if len(targets) > 1
        }
        for label, source_targets in mapped_source_targets.items()
    }
    duplicate_counts = {
        label: len(items) for label, items in duplicate_sources.items()
    }
    conflicts = [
        row for row in output_rows
        if row["classification"] == "conflicting_high_source"
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "comparison_complete",
        "year": year,
        "mutates_wav": False,
        "audit_report": file_fingerprint(audit_path.resolve(), with_sha256=True),
        "plans": {
            label: file_fingerprint(path.resolve(), with_sha256=True)
            for label, path in plans
        },
        "labels": labels,
        "affected_target_count": len(affected_ids),
        "classification_counts": dict(sorted(classification_counts.items())),
        "high_label_signature_counts": dict(
            sorted(high_label_signature_counts.items())
        ),
        "high_status_counts_by_plan": {
            label: dict(sorted(counts.items()))
            for label, counts in high_counts.items()
        },
        "duplicate_high_source_counts_by_plan": duplicate_counts,
        "conflicting_high_source_examples": conflicts[:20],
        "safe_to_auto_apply": False,
        "next_step": (
            "consensus remap도 연속구간 감사와 연구자 표본 청취 뒤 별도 staging에 적용"
        ),
    }
    return output_rows, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument(
        "--plan", action="append", type=parse_plan_argument, required=True
    )
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()

    rows, report = compare(
        year=str(args.year),
        audit_path=args.audit_report.resolve(),
        plans=[(label, path.resolve()) for label, path in args.plan],
    )
    fields = list(rows[0])
    with atomic_text_writer(
        args.output_csv.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temporary):
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    atomic_write_json(args.output_report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
