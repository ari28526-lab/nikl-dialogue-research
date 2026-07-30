"""MFA SQLite DB에서 4-tier를 재생성해 final TextGrid와 표본 대조한다.

이 도구는 DB를 read-only URI로 열고, 정렬 interval이 있는 발화 가운데
서로 다른 세션의 결정적 표본을 고른다. 같은 export 함수를 별도 scratch
경로에 실행한 뒤 tier 이름·라벨·모든 시간값과 파일 SHA256을 비교한다.

final TextGrid와 DB를 수정하거나 scratch 결과를 자동 삭제하지 않는다.
기존 scratch TextGrid가 있으면 stale 결과를 증거로 쓰지 않도록 실패한다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

from export_mfa_db_4tier import (
    export_session,
    load_session_forms,
)
from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


def session_name(relative_path: object, utterance_name: str) -> str:
    value = str(relative_path or "").strip()
    return value or utterance_name.split(".", 1)[0]


def deterministic_session_sample(
    connection: sqlite3.Connection,
    *,
    year: str,
    sample_size: int,
) -> tuple[list[tuple[int, str, str, float]], dict[str, int]]:
    """정렬된 발화 중 세션별 최저 hash 하나를 뽑고 전역 최저 N개를 반환."""
    if sample_size <= 0:
        raise ValueError("sample_size는 양수여야 함")

    query = """
        SELECT u.id, f.name, f.relative_path, sf.duration
        FROM utterance u
        JOIN file f ON f.id = u.file_id
        JOIN sound_file sf ON sf.file_id = f.id
        WHERE u.ignored = 0
          AND EXISTS (
              SELECT 1 FROM word_interval wi
              WHERE wi.utterance_id = u.id
          )
          AND EXISTS (
              SELECT 1 FROM phone_interval pi
              WHERE pi.utterance_id = u.id
          )
        ORDER BY u.id
    """
    best_by_session: dict[
        str, tuple[bytes, int, str, str, float]
    ] = {}
    eligible_utterances = 0
    for uid, name, relative_path, duration in connection.execute(query):
        name = str(name)
        session = session_name(relative_path, name)
        digest = hashlib.sha256(
            f"{year}\0{session}\0{name}".encode("utf-8")
        ).digest()
        candidate = (
            digest,
            int(uid),
            name,
            session,
            float(duration),
        )
        previous = best_by_session.get(session)
        if previous is None or candidate[:3] < previous[:3]:
            best_by_session[session] = candidate
        eligible_utterances += 1

    selected = sorted(best_by_session.values())[:sample_size]
    rows = [
        (uid, name, session, duration)
        for _digest, uid, name, session, duration in selected
    ]
    return rows, {
        "eligible_utterances": eligible_utterances,
        "eligible_sessions": len(best_by_session),
        "selected_utterances": len(rows),
        "selected_sessions": len({row[2] for row in rows}),
    }


def tier_payload(path: Path) -> dict[str, object]:
    duration, tiers = parse_mfa_textgrid(path)
    return {
        "duration": duration,
        "tier_order": list(tiers),
        "tiers": {
            tier_name: [list(interval) for interval in intervals]
            for tier_name, intervals in tiers.items()
        },
    }


def write_comparison_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "year",
        "session",
        "utt_id",
        "status",
        "tier_equal",
        "byte_equal",
        "final_path",
        "reexport_path",
        "final_sha256",
        "reexport_sha256",
    ]
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def verify_sample(
    *,
    db_path: Path,
    year: str,
    search_master_root: Path,
    final_root: Path,
    scratch_root: Path,
    report_path: Path,
    sample_csv_path: Path,
    sample_size: int = 24,
    input_contract_id: str | None = None,
) -> dict[str, object]:
    started = time.monotonic()
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if not (search_master_root / year).is_dir():
        raise FileNotFoundError(search_master_root / year)
    if not (final_root / year).is_dir():
        raise FileNotFoundError(final_root / year)
    if scratch_root.exists() and next(
        scratch_root.rglob("*.TextGrid"), None
    ) is not None:
        raise FileExistsError(
            f"기존 scratch TextGrid가 있어 검증을 중단함: {scratch_root}"
        )

    connection = sqlite3.connect(
        f"file:{db_path.resolve().as_posix()}?mode=ro",
        uri=True,
        timeout=120,
    )
    try:
        selected, selection_counts = deterministic_session_sample(
            connection,
            year=year,
            sample_size=sample_size,
        )
        if len(selected) < sample_size:
            raise RuntimeError(
                "서로 다른 정렬 세션이 표본 크기보다 적음: "
                f"selected={len(selected)} requested={sample_size}"
            )

        word_labels = dict(
            connection.execute("SELECT id, word FROM word")
        )
        phone_labels = {
            row[0]: (row[1], row[2])
            for row in connection.execute(
                "SELECT id, phone, phone_type FROM phone"
            )
        }
        grouped: dict[str, list[tuple[int, str, float]]] = defaultdict(list)
        for uid, name, session, duration in selected:
            grouped[session].append((uid, name, duration))

        export_counts: defaultdict[str, int] = defaultdict(int)
        for session, utterances in sorted(grouped.items()):
            result = export_session(
                connection,
                year=year,
                output_root=scratch_root,
                session=session,
                utterances=utterances,
                word_labels=word_labels,
                phone_labels=phone_labels,
                forms=load_session_forms(
                    search_master_root, year, session
                ),
            )
            for key, value in result.items():
                if isinstance(value, int):
                    export_counts[key] += value
    finally:
        connection.close()

    comparisons: list[dict[str, object]] = []
    tier_equal_count = 0
    byte_equal_count = 0
    for _uid, name, session, _duration in selected:
        final_path = final_root / year / session / f"{name}.TextGrid"
        reexport_path = (
            scratch_root / year / session / f"{name}.TextGrid"
        )
        final_exists = final_path.is_file()
        reexport_exists = reexport_path.is_file()
        final_sha = sha256_file(final_path) if final_exists else ""
        reexport_sha = (
            sha256_file(reexport_path) if reexport_exists else ""
        )
        byte_equal = bool(
            final_exists
            and reexport_exists
            and final_sha == reexport_sha
        )
        tier_equal = False
        status = "missing_final"
        if final_exists and not reexport_exists:
            status = "missing_reexport"
        elif final_exists and reexport_exists:
            tier_equal = tier_payload(final_path) == tier_payload(
                reexport_path
            )
            if not tier_equal:
                status = "tier_mismatch"
            elif byte_equal:
                status = "exact_match"
            else:
                status = "tier_equal_byte_different"
        if tier_equal:
            tier_equal_count += 1
        if byte_equal:
            byte_equal_count += 1
        comparisons.append(
            {
                "year": year,
                "session": session,
                "utt_id": name,
                "status": status,
                "tier_equal": tier_equal,
                "byte_equal": byte_equal,
                "final_path": str(final_path),
                "reexport_path": str(reexport_path),
                "final_sha256": final_sha,
                "reexport_sha256": reexport_sha,
            }
        )

    write_comparison_csv(sample_csv_path, comparisons)
    status = (
        "success"
        if len(comparisons) == sample_size
        and tier_equal_count == sample_size
        and export_counts["created"] == sample_size
        and export_counts["alignment_missing"] == 0
        and export_counts["form_missing"] == 0
        and export_counts["failed"] == 0
        else "failed"
    )
    report: dict[str, object] = {
        "schema_version": 1,
        "status": status,
        "read_only_sources": True,
        "generated_at": now_iso(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "year": year,
        "input_contract_id": input_contract_id,
        "sample_policy": (
            "정렬 interval이 있는 발화 중 세션별 SHA256 최저 1개를 고른 "
            "뒤 전역 SHA256 최저 N개"
        ),
        "sample_size_requested": sample_size,
        "selection_counts": selection_counts,
        "comparison_counts": {
            "compared": len(comparisons),
            "tier_equal": tier_equal_count,
            "byte_equal": byte_equal_count,
            "tier_mismatch": sum(
                row["status"] == "tier_mismatch"
                for row in comparisons
            ),
            "missing_final": sum(
                row["status"] == "missing_final"
                for row in comparisons
            ),
            "missing_reexport": sum(
                row["status"] == "missing_reexport"
                for row in comparisons
            ),
        },
        "export_counts": dict(sorted(export_counts.items())),
        "db": file_fingerprint(db_path),
        "search_master_root": str(search_master_root.resolve()),
        "final_root": str(final_root.resolve()),
        "scratch_root": str(scratch_root.resolve()),
        "sample_csv": file_fingerprint(
            sample_csv_path, with_sha256=True
        ),
        "selected_utterances": [
            {"utt_id": name, "session": session}
            for _uid, name, session, _duration in selected
        ],
    }
    atomic_write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--final-root", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--sample-csv", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=24)
    parser.add_argument("--input-contract-id")
    args = parser.parse_args()

    report = verify_sample(
        db_path=args.db,
        year=args.year,
        search_master_root=args.search_master_root,
        final_root=args.final_root,
        scratch_root=args.scratch_root,
        report_path=args.report,
        sample_csv_path=args.sample_csv,
        sample_size=args.sample_size,
        input_contract_id=args.input_contract_id,
    )
    print(
        {
            "status": report["status"],
            "selection_counts": report["selection_counts"],
            "comparison_counts": report["comparison_counts"],
            "export_counts": report["export_counts"],
        }
    )
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
