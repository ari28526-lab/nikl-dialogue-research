"""Add within-session offset topology evidence to a recovery comparison.

This is read-only.  It does not promote mappings automatically.  In particular,
q2+q5 candidates are separated according to whether all-scale consensus anchors
with the same ID offset occur on both sides in the same session.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint


SCHEMA_VERSION = "wav_recovery_topology_analysis.v1"


def final_sequence(utt_id: str) -> int:
    match = re.search(r"(\d+)$", utt_id)
    if not match:
        raise ValueError(f"발화 ID 끝 순번을 읽을 수 없음: {utt_id}")
    return int(match.group(1))


def offset_for(row: dict[str, str]) -> int | None:
    source = row.get("consensus_source_utt_id", "")
    if not source:
        return None
    target = row["target_utt_id"]
    target_prefix = target.rsplit(".", 1)[0]
    source_prefix = source.rsplit(".", 1)[0]
    if target_prefix != source_prefix:
        raise RuntimeError(f"세션 밖 source 매핑: {target} -> {source}")
    return final_sequence(source) - final_sequence(target)


def analyze(
    rows: list[dict[str, str]],
    *,
    all_signature: str,
    secondary_signature: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_session: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_session[row["session"]].append(row)

    output_rows: list[dict[str, object]] = []
    tier_counts: Counter[str] = Counter()
    for session, session_rows in sorted(by_session.items()):
        ordered = sorted(session_rows, key=lambda row: final_sequence(row["target_utt_id"]))
        anchors = [
            row for row in ordered
            if row.get("high_labels") == all_signature
            and row.get("consensus_source_utt_id")
        ]
        anchor_positions = [final_sequence(row["target_utt_id"]) for row in anchors]

        for row in ordered:
            target_position = final_sequence(row["target_utt_id"])
            candidate_offset = offset_for(row)
            previous = None
            following = None
            for anchor, position in zip(anchors, anchor_positions):
                if position < target_position:
                    previous = anchor
                    continue
                if position > target_position:
                    following = anchor
                    break

            previous_offset = offset_for(previous) if previous else None
            following_offset = offset_for(following) if following else None
            signature = row.get("high_labels", "none")
            if signature == all_signature:
                tier = "A_ALL_SCALE_CONSENSUS"
            elif signature == secondary_signature:
                previous_matches = (
                    previous_offset is not None
                    and previous_offset == candidate_offset
                )
                following_matches = (
                    following_offset is not None
                    and following_offset == candidate_offset
                )
                if previous_matches and following_matches:
                    tier = "B_Q2_Q5_BRACKETED_SAME_OFFSET"
                elif previous_matches or following_matches:
                    tier = "B_Q2_Q5_ONE_SIDED_SAME_OFFSET"
                else:
                    tier = "B_Q2_Q5_UNANCHORED"
            elif signature == "none":
                tier = "D_NO_HIGH_MAPPING"
            else:
                tier = "C_SINGLE_SCALE_OR_NONADJACENT"
            tier_counts[tier] += 1

            enriched: dict[str, object] = dict(row)
            enriched.update(
                {
                    "topology_tier": tier,
                    "candidate_id_offset": (
                        "" if candidate_offset is None else candidate_offset
                    ),
                    "previous_anchor_target": (
                        previous["target_utt_id"] if previous else ""
                    ),
                    "previous_anchor_offset": (
                        "" if previous_offset is None else previous_offset
                    ),
                    "previous_anchor_distance": (
                        ""
                        if previous is None
                        else target_position - final_sequence(previous["target_utt_id"])
                    ),
                    "following_anchor_target": (
                        following["target_utt_id"] if following else ""
                    ),
                    "following_anchor_offset": (
                        "" if following_offset is None else following_offset
                    ),
                    "following_anchor_distance": (
                        ""
                        if following is None
                        else final_sequence(following["target_utt_id"]) - target_position
                    ),
                }
            )
            output_rows.append(enriched)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "analysis_complete",
        "mutates_wav": False,
        "row_count": len(output_rows),
        "session_count": len(by_session),
        "all_signature": all_signature,
        "secondary_signature": secondary_signature,
        "topology_tier_counts": dict(sorted(tier_counts.items())),
        "safe_to_auto_apply": False,
        "next_step": "A/B 후보의 연속구간 감사와 연구자 표본 청취",
    }
    return output_rows, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-csv", type=Path, required=True)
    parser.add_argument("--all-signature", default="q1+q2+q5")
    parser.add_argument("--secondary-signature", default="q2+q5")
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()

    with args.comparison_csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    output_rows, report = analyze(
        rows,
        all_signature=args.all_signature,
        secondary_signature=args.secondary_signature,
    )
    report["comparison_csv"] = file_fingerprint(
        args.comparison_csv.resolve(), with_sha256=True
    )
    with atomic_text_writer(
        args.output_csv.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temporary):
        writer = csv.DictWriter(
            stream, fieldnames=list(output_rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(output_rows)
    atomic_write_json(args.output_report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
