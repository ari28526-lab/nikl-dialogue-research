"""MFA SQLite DB에서 새 연구 계약 4-tier TextGrid를 직접 생성한다."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pipeline_common import atomic_write_json
from research_textgrid import (
    validate_research_textgrid,
    write_research_textgrid,
)
from textgrid_labels import SEARCH_LABEL_SCHEMA_VERSION, TARGET_TIERS

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SILENCE_WORDS = {"", "<eps>", "sil", "<unk>"}
SILENCE_PHONES = {"", "sil", "sp"}
REQUIRED_SEARCH_FIELDS = {
    "utt_id",
    "form",
    "form_roman",
    "tagged",
    "align_warn",
}


def count_spn_intervals(connection: sqlite3.Connection) -> int:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if not {"phone", "phone_interval"}.issubset(tables):
        raise RuntimeError(
            "MFA DB spn gate requires phone and phone_interval tables"
        )
    return int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM phone_interval pi
            JOIN phone p ON p.id = pi.phone_id
            WHERE trim(lower(p.phone)) = 'spn'
            """
        ).fetchone()[0]
    )


def load_session_rows(
    search_master_root: Path, year: str, session: str
) -> dict[str, dict[str, str]]:
    path = search_master_root / year / f"{session}.csv"
    if not path.is_file():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_SEARCH_FIELDS - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"{path}: 필수 열 누락 {sorted(missing)}")
        for row in reader:
            utt_id = row["utt_id"]
            if not utt_id:
                raise RuntimeError(f"{path}: 빈 utt_id")
            if utt_id in rows:
                raise RuntimeError(f"{path}: 중복 utt_id {utt_id}")
            rows[utt_id] = row
    return rows


def placeholders(count: int) -> str:
    if count <= 0:
        raise ValueError("SQL placeholder count는 양수여야 함")
    return ",".join("?" for _ in range(count))


def export_session(
    connection: sqlite3.Connection,
    *,
    year: str,
    output_root: Path,
    session: str,
    utterances: list[tuple[int, str, float]],
    word_labels: dict[int, str],
    phone_labels: dict[int, tuple[str, str]],
    search_rows: dict[str, dict[str, str]],
) -> dict[str, object]:
    counts: defaultdict[str, int] = defaultdict(int)
    failures: list[dict[str, str]] = []
    missing_alignment: list[str] = []
    missing_search_row: list[str] = []
    todo: list[tuple[int, str, float, Path, dict[str, str]]] = []
    out_dir = output_root / year / session
    for uid, utt_id, duration in utterances:
        search_row = search_rows.get(utt_id)
        if search_row is None:
            counts["search_row_missing"] += 1
            missing_search_row.append(utt_id)
            continue
        output = out_dir / f"{utt_id}.TextGrid"
        if output.is_file():
            validation = validate_research_textgrid(
                output,
                expected_duration=duration,
                expected_row=search_row,
            )
            if validation["valid"]:
                counts["validated_existing"] += 1
                continue
        todo.append((uid, utt_id, duration, output, search_row))
    if not todo:
        return {
            **counts,
            "failed_examples": failures,
            "alignment_missing_examples": missing_alignment,
            "search_row_missing_inventory": missing_search_row,
        }

    ids = [row[0] for row in todo]
    marks = placeholders(len(ids))
    words_by_utt: dict[int, list[tuple[float, float, str]]] = defaultdict(list)
    for uid, begin, end, word_id in connection.execute(
        "SELECT utterance_id, begin, end, word_id "
        f"FROM word_interval WHERE utterance_id IN ({marks}) "
        "ORDER BY utterance_id, begin, end",
        ids,
    ):
        label = word_labels.get(word_id, "")
        if label in SILENCE_WORDS:
            label = ""
        words_by_utt[uid].append((float(begin), float(end), label))
    phones_by_utt: dict[int, list[tuple[float, float, str]]] = defaultdict(list)
    for uid, begin, end, phone_id in connection.execute(
        "SELECT utterance_id, begin, end, phone_id "
        f"FROM phone_interval WHERE utterance_id IN ({marks}) "
        "ORDER BY utterance_id, begin, end",
        ids,
    ):
        label, phone_type = phone_labels.get(phone_id, ("", ""))
        if label in SILENCE_PHONES or phone_type == "silence":
            label = ""
        phones_by_utt[uid].append((float(begin), float(end), label))

    out_dir.mkdir(parents=True, exist_ok=True)
    for uid, utt_id, duration, output, search_row in todo:
        words = words_by_utt.get(uid, [])
        phones = phones_by_utt.get(uid, [])
        if not words or not phones:
            counts["alignment_missing"] += 1
            missing_alignment.append(utt_id)
            continue
        try:
            validation = write_research_textgrid(
                output,
                duration=duration,
                words=words,
                phones=phones,
                search_row=search_row,
            )
            if validation.get("word_span_fallback"):
                counts["word_span_fallback"] += 1
        except Exception as exc:
            counts["failed"] += 1
            if len(failures) < 100:
                failures.append(
                    {
                        "utt_id": utt_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            continue
        counts["created"] += 1
    return {
        **counts,
        "failed_examples": failures,
        "alignment_missing_examples": missing_alignment,
        "search_row_missing_inventory": missing_search_row,
    }


def export_database(
    *,
    db_path: Path,
    year: str,
    search_master_root: Path,
    output_root: Path,
    limit_sessions: int = 0,
    workers: int = 4,
) -> dict[str, object]:
    started = time.monotonic()
    db_path = db_path.resolve()
    search_master_root = search_master_root.resolve()
    output_root = output_root.resolve()
    connection = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=120
    )
    try:
        spn_intervals = count_spn_intervals(connection)
        if spn_intervals:
            return {
                "schema_version": "mfa_research_4tier_export.v1",
                "status": "failed",
                "analysis_ready_status": "blocked_spn_intervals",
                "year": year,
                "counts": {"spn_intervals": spn_intervals},
            }
        word_labels = dict(connection.execute("SELECT id, word FROM word"))
        phone_labels = {
            row[0]: (row[1], row[2])
            for row in connection.execute(
                "SELECT id, phone, phone_type FROM phone"
            )
        }
        sessions: dict[str, list[tuple[int, str, float]]] = defaultdict(list)
        for uid, name, relative_path, duration in connection.execute(
            "SELECT u.id, f.name, f.relative_path, sf.duration "
            "FROM utterance u "
            "JOIN file f ON f.id = u.file_id "
            "JOIN sound_file sf ON sf.file_id = f.id "
            "WHERE u.ignored = 0 "
            "ORDER BY f.relative_path, f.name"
        ):
            session = relative_path or str(name).split(".", 1)[0]
            sessions[str(session)].append(
                (int(uid), str(name), float(duration))
            )
        selected = sorted(sessions.items())
        if limit_sessions:
            selected = selected[:limit_sessions]
    finally:
        connection.close()

    def process(item):
        session, utterances = item
        search_rows = load_session_rows(
            search_master_root, year, session
        )
        local = sqlite3.connect(
            f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=120
        )
        try:
            result = export_session(
                local,
                year=year,
                output_root=output_root,
                session=session,
                utterances=utterances,
                word_labels=word_labels,
                phone_labels=phone_labels,
                search_rows=search_rows,
            )
        finally:
            local.close()
        return session, len(utterances), result

    totals: defaultdict[str, int] = defaultdict(int)
    totals["spn_intervals"] = 0
    failures: list[dict[str, str]] = []
    alignment_missing: list[str] = []
    search_row_missing: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(process, item): item[0] for item in selected
        }
        for index, future in enumerate(as_completed(futures), 1):
            _session, source_count, result = future.result()
            totals["source_utterances"] += source_count
            for key, value in result.items():
                if key == "failed_examples":
                    failures.extend(
                        value[: max(0, 100 - len(failures))]
                    )
                elif key == "alignment_missing_examples":
                    alignment_missing.extend(value)
                elif key == "search_row_missing_inventory":
                    search_row_missing.extend(value)
                else:
                    totals[key] += int(value)
            if index % 50 == 0 or index == len(selected):
                print(
                    f"[{year}] research 4-tier "
                    f"{index:,}/{len(selected):,} sessions · "
                    f"created={totals['created']:,}",
                    flush=True,
                )

    accounted = (
        totals["created"]
        + totals["validated_existing"]
        + totals["alignment_missing"]
        + totals["search_row_missing"]
        + totals["failed"]
    )
    success = (
        totals["source_utterances"] > 0
        and accounted == totals["source_utterances"]
        and totals["alignment_missing"] == 0
        and totals["search_row_missing"] == 0
        and totals["failed"] == 0
        and totals["word_span_fallback"] == 0
    )
    return {
        "schema_version": "mfa_research_4tier_export.v1",
        "status": "success" if success else "failed",
        "analysis_ready_status": "ready" if success else "blocked",
        "year": year,
        "db_path": str(db_path),
        "search_master_root": str(search_master_root),
        "output_root": str(output_root),
        "tier_names": TARGET_TIERS,
        "search_label_schema_version": SEARCH_LABEL_SCHEMA_VERSION,
        "tier_provenance": {
            "words": "mfa_db.word_interval",
            "phones_mfa": "mfa_db.phone_interval; not realization",
            "utterance": "frozen_search_master.form",
            "utterance_search": (
                "frozen_search_master form_roman/tagged + "
                "deterministic tagged_roman_v2"
            ),
        },
        "counts": dict(sorted(totals.items())),
        "accounted": accounted,
        "coverage_pct": (
            round(
                100
                * (totals["created"] + totals["validated_existing"])
                / totals["source_utterances"],
                4,
            )
            if totals["source_utterances"]
            else 0
        ),
        "failed_examples": failures,
        "alignment_missing_examples": alignment_missing[:100],
        "search_row_missing_inventory": sorted(set(search_row_missing)),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--limit-sessions", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = export_database(
        db_path=args.db,
        year=args.year,
        search_master_root=args.search_master_root,
        output_root=args.output_root,
        limit_sessions=args.limit_sessions,
        workers=args.workers,
    )
    atomic_write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
