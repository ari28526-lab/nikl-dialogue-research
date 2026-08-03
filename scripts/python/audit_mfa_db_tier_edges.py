"""Audit full-year MFA DB outer-edge patterns before 6-tier export.

This is read-only.  It does not create TextGrids or modify the MFA database.
The report distinguishes the production source-time contract from review-only
WAV/TextGrid padding.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from pipeline_common import file_fingerprint


SCHEMA_VERSION = "mfa_db_tier_edge_audit.v1"
TOLERANCE = 1e-6


QUERY = """
WITH word_edges AS (
    SELECT wi.utterance_id,
           MIN(CASE
               WHEN trim(lower(w.word)) NOT IN ('', '<eps>', 'sil', '<unk>')
               THEN wi.begin END) AS speech_begin,
           MAX(CASE
               WHEN trim(lower(w.word)) NOT IN ('', '<eps>', 'sil', '<unk>')
               THEN wi.end END) AS speech_end
    FROM word_interval wi
    JOIN word w ON w.id = wi.word_id
    GROUP BY wi.utterance_id
),
phone_edges AS (
    SELECT pi.utterance_id,
           MIN(CASE
               WHEN trim(lower(p.phone)) NOT IN ('', '<eps>', 'sil', 'sp', '<unk>')
                AND lower(coalesce(p.phone_type, '')) <> 'silence'
               THEN pi.begin END) AS speech_begin,
           MAX(CASE
               WHEN trim(lower(p.phone)) NOT IN ('', '<eps>', 'sil', 'sp', '<unk>')
                AND lower(coalesce(p.phone_type, '')) <> 'silence'
               THEN pi.end END) AS speech_end
    FROM phone_interval pi
    JOIN phone p ON p.id = pi.phone_id
    GROUP BY pi.utterance_id
)
SELECT f.name, sf.duration,
       we.speech_begin, we.speech_end,
       pe.speech_begin, pe.speech_end
FROM utterance u
JOIN file f ON f.id = u.file_id
JOIN sound_file sf ON sf.file_id = f.id
JOIN word_edges we ON we.utterance_id = u.id
JOIN phone_edges pe ON pe.utterance_id = u.id
WHERE u.ignored = 0
  AND we.speech_begin IS NOT NULL
  AND we.speech_end IS NOT NULL
  AND pe.speech_begin IS NOT NULL
  AND pe.speech_end IS NOT NULL
ORDER BY u.id
"""


def open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=120
    )


def close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= TOLERANCE


def pattern(begin: float, end: float, duration: float) -> str:
    left = begin > TOLERANCE
    right = duration - end > TOLERANCE
    if left and right:
        return "natural_blank_both"
    if left:
        return "natural_blank_left_only"
    if right:
        return "natural_blank_right_only"
    return "no_natural_blank"


def audit(db_path: Path) -> dict[str, object]:
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, object]]] = {
        "word_phone_outer_edge_mismatch": [],
        "no_natural_blank": [],
        "natural_blank_both": [],
    }
    connection = open_readonly(db_path)
    connection.execute("PRAGMA query_only=ON")
    try:
        for utt_id, duration, word_begin, word_end, phone_begin, phone_end in (
            connection.execute(QUERY)
        ):
            duration = float(duration)
            word_begin = float(word_begin)
            word_end = float(word_end)
            phone_begin = float(phone_begin)
            phone_end = float(phone_end)
            counts["aligned_utterances"] += 1
            word_pattern = pattern(word_begin, word_end, duration)
            phone_pattern = pattern(phone_begin, phone_end, duration)
            counts[f"word_{word_pattern}"] += 1
            counts[f"phone_{phone_pattern}"] += 1
            start_equal = close(word_begin, phone_begin)
            end_equal = close(word_end, phone_end)
            if start_equal:
                counts["word_phone_start_equal"] += 1
            if end_equal:
                counts["word_phone_end_equal"] += 1
            if start_equal and end_equal:
                counts["word_phone_outer_edges_equal"] += 1
            else:
                counts["word_phone_outer_edge_mismatch"] += 1
                bucket = examples["word_phone_outer_edge_mismatch"]
                if len(bucket) < 10:
                    bucket.append(
                        {
                            "utt_id": str(utt_id),
                            "duration_seconds": duration,
                            "word_span": [word_begin, word_end],
                            "phone_span": [phone_begin, phone_end],
                        }
                    )
            if word_pattern in examples and len(examples[word_pattern]) < 5:
                examples[word_pattern].append(
                    {
                        "utt_id": str(utt_id),
                        "duration_seconds": duration,
                        "word_span": [word_begin, word_end],
                        "phone_span": [phone_begin, phone_end],
                    }
                )
    finally:
        connection.close()

    aligned = counts["aligned_utterances"]
    equal = counts["word_phone_outer_edges_equal"]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "observed_at": datetime.now().astimezone().isoformat(),
        "database": file_fingerprint(db_path, with_sha256=False),
        "tolerance_seconds": TOLERANCE,
        "production_contract": {
            "time_basis": "source_time_no_artificial_padding",
            "all_tiers_cover_0_to_xmax": True,
            "words_and_utterance_level_outer_speech_edges": "same_by_exporter_construction",
            "phones_mfa_and_phoneme_r_auto_edges": "same_by_exporter_construction",
            "review_padding_is_not_a_production_time_change": True,
        },
        "counts": dict(sorted(counts.items())),
        "word_phone_outer_edges_equal_percent": (
            round(100.0 * equal / aligned, 6) if aligned else 0.0
        ),
        "examples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.db)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "aligned_utterances": report["counts"].get(
                    "aligned_utterances", 0
                ),
                "word_phone_outer_edge_mismatch": report["counts"].get(
                    "word_phone_outer_edge_mismatch", 0
                ),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
