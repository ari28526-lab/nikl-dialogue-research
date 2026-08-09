"""MFA DB의 계산 완료 상태를 읽기 전용으로 기록한다.

이 체크포인트는 "MFA 프로세스를 다시 돌릴 필요가 있는가"만 판단한다.
TextGrid/동반표 생성 성공이나 연구 분석 준비 완료를 뜻하지 않는다. 실제
``spn`` 및 누락 발화는 그대로 보고하며 후속 exporter/QC가 별도로 차단한다.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint

SCHEMA_VERSION = "mfa_db_computation_checkpoint.v1"


def inspect_database(db_path: Path, year: str) -> dict[str, object]:
    db_path = db_path.resolve()
    connection = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=120
    )
    try:
        quick_check = str(
            connection.execute("PRAGMA quick_check").fetchone()[0]
        )
        source_utterances = int(
            connection.execute(
                "SELECT COUNT(*) FROM utterance WHERE ignored=0"
            ).fetchone()[0]
        )
        word_rows = int(
            connection.execute("SELECT COUNT(*) FROM word_interval").fetchone()[0]
        )
        phone_rows = int(
            connection.execute("SELECT COUNT(*) FROM phone_interval").fetchone()[0]
        )
        utterances_with_words = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT wi.utterance_id)
                FROM word_interval wi
                JOIN utterance u ON u.id=wi.utterance_id
                WHERE u.ignored=0
                """
            ).fetchone()[0]
        )
        utterances_with_phones = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT pi.utterance_id)
                FROM phone_interval pi
                JOIN utterance u ON u.id=pi.utterance_id
                WHERE u.ignored=0
                """
            ).fetchone()[0]
        )
        spn_intervals = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM phone_interval pi
                JOIN phone p ON p.id=pi.phone_id
                WHERE trim(lower(p.phone))='spn'
                """
            ).fetchone()[0]
        )
        missing_alignment_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM utterance u
                WHERE u.ignored=0 AND (
                    NOT EXISTS(
                        SELECT 1 FROM word_interval wi
                        WHERE wi.utterance_id=u.id
                    ) OR NOT EXISTS(
                        SELECT 1 FROM phone_interval pi
                        WHERE pi.utterance_id=u.id
                    )
                )
                """
            ).fetchone()[0]
        )
        missing_examples = [
            str(row[0])
            for row in connection.execute(
                """
                SELECT f.name
                FROM utterance u
                JOIN file f ON f.id=u.file_id
                WHERE u.ignored=0 AND (
                    NOT EXISTS(
                        SELECT 1 FROM word_interval wi
                        WHERE wi.utterance_id=u.id
                    ) OR NOT EXISTS(
                        SELECT 1 FROM phone_interval pi
                        WHERE pi.utterance_id=u.id
                    )
                )
                ORDER BY f.name
                LIMIT 100
                """
            )
        ]
    finally:
        connection.close()

    computation_complete = (
        quick_check == "ok"
        and source_utterances > 0
        and word_rows > 0
        and phone_rows > 0
    )
    aligned_utterances = source_utterances - missing_alignment_count
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "success" if computation_complete else "failed",
        "meaning": (
            "alignment computation is reusable; this is not TextGrid export "
            "success or analysis-ready approval"
        ),
        "year": str(year),
        "database": file_fingerprint(db_path, with_sha256=False),
        "quick_check": quick_check,
        "counts": {
            "source_utterances": source_utterances,
            "utterances_with_words": utterances_with_words,
            "utterances_with_phones": utterances_with_phones,
            "utterances_with_words_and_phones": aligned_utterances,
            "aligned_utterances_lower_bound": aligned_utterances,
            "missing_alignment_utterances": missing_alignment_count,
            "word_intervals": word_rows,
            "phone_intervals": phone_rows,
            "spn_intervals": spn_intervals,
        },
        "coverage_pct": (
            round(100 * aligned_utterances / source_utterances, 4)
            if source_utterances else 0
        ),
        "analysis_ready_status": (
            "requires_export_and_independent_qc"
            if computation_complete else "blocked_incomplete_database"
        ),
        "missing_alignment_examples": missing_examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect_database(args.db, args.year)
    except Exception as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed",
            "year": str(args.year),
            "error": f"{type(exc).__name__}: {exc}",
        }
    atomic_write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
