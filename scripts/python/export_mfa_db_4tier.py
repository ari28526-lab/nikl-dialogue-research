"""MFA SQLite DB에서 연구용 4-tier TextGrid를 직접 생성한다.

목적은 MFA의 raw 2-tier TextGrid를 수백만 개 쓴 뒤 다시 읽어 4-tier로
재작성하는 이중 I/O를 피하는 것이다. DB의 word/phone interval을 읽어 기존
형태소 경계와 frozen search master의 form을 한 번에 결합한다.

정렬/파일 생성의 성공과 연구용 형태소 tier 완비를 분리한다. 형태소 원천이
없는 발화도 words/phones/utterance와 빈 morphemes 경계를 가진 4-tier로
보존하되, 보고서의 ``analysis_ready_status``를 차단하고 전수 inventory를
남긴다. 다음 연도 및 analysis-ready 승격은 독립 QC가 이 상태를 거부한다.
DB는 SQLite read-only URI로 열고, 기존 형태소 TextGrid도 읽기만 한다.
"""

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
from realign_eojeol_merge_output import (
    morpheme_tier,
    validate_4tier,
    write_4tier,
)

csv.field_size_limit(10_000_000)
SILENCE_WORDS = {"", "<eps>", "sil", "<unk>"}
SILENCE_PHONES = {"", "sil", "sp"}


def count_spn_intervals(
    connection: sqlite3.Connection,
) -> int:
    """Count ``spn`` phones actually used in aligned utterance intervals.

    MFA injects unused reserved rows such as ``<unk> -> spn`` into every
    corpus DB. Their mere presence is not an aligned OOV and must not block
    export. A used ``spn`` phone interval is the research-relevant failure.
    """

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


def load_session_forms(
    search_master_root: Path, year: str, session: str
) -> dict[str, str]:
    forms: dict[str, str] = {}
    path = search_master_root / year / f"{session}.csv"
    if not path.is_file():
        return forms
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"utt_id", "form"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"{path}: 필수 열 누락 {sorted(missing)}")
        for row in reader:
            utt_id = row["utt_id"]
            if utt_id in forms:
                raise RuntimeError(f"중복 utt_id: {utt_id}")
            forms[utt_id] = row["form"]
    return forms


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
    forms: dict[str, str],
) -> dict[str, object]:
    counts = defaultdict(int)
    missing_alignment_examples: list[str] = []
    form_missing_examples: list[str] = []
    morpheme_missing_inventory: list[str] = []
    failed_examples: list[dict[str, str]] = []
    todo = []
    out_dir = output_root / year / session
    for uid, name, duration in utterances:
        output = out_dir / f"{name}.TextGrid"
        if output.is_file() and validate_4tier(output)["valid"]:
            counts["validated_existing"] += 1
            # Resume 시 이미 쓴 빈 morphemes tier를 단순 valid로 오인하지 않는다.
            # 연구 준비도는 원천 tier의 현재 존재·내용으로 다시 계수한다.
            if not morpheme_tier(year, session, name):
                counts["morpheme_tier_missing"] += 1
                morpheme_missing_inventory.append(name)
            continue
        todo.append((uid, name, duration, output))
    if not todo:
        result: dict[str, object] = dict(counts)
        result["alignment_missing_examples"] = missing_alignment_examples
        result["form_missing_examples"] = form_missing_examples
        result["morpheme_tier_missing_inventory"] = (
            morpheme_missing_inventory
        )
        result["failed_examples"] = failed_examples
        return result

    ids = [row[0] for row in todo]
    ph = placeholders(len(ids))
    words_by_utt: dict[int, list[tuple[float, float, str]]] = defaultdict(list)
    for uid, begin, end, word_id in connection.execute(
        "SELECT utterance_id, begin, end, word_id "
        f"FROM word_interval WHERE utterance_id IN ({ph}) "
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
        f"FROM phone_interval WHERE utterance_id IN ({ph}) "
        "ORDER BY utterance_id, begin, end",
        ids,
    ):
        label, phone_type = phone_labels.get(phone_id, ("", ""))
        if label in SILENCE_PHONES or phone_type == "silence":
            label = ""
        phones_by_utt[uid].append((float(begin), float(end), label))

    out_dir.mkdir(parents=True, exist_ok=True)
    for uid, name, duration, output in todo:
        words = words_by_utt.get(uid, [])
        phones = phones_by_utt.get(uid, [])
        if not words or not phones:
            counts["alignment_missing"] += 1
            if len(missing_alignment_examples) < 20:
                missing_alignment_examples.append(name)
            continue
        form = forms.get(name)
        if form is None:
            counts["form_missing"] += 1
            if len(form_missing_examples) < 100:
                form_missing_examples.append(name)
            continue
        morphs = morpheme_tier(year, session, name)
        if not morphs:
            counts["morpheme_tier_missing"] += 1
            morpheme_missing_inventory.append(name)
        try:
            write_4tier(
                output,
                duration,
                words,
                phones,
                morphs,
                form,
            )
        except Exception as exc:
            counts["failed"] += 1
            if len(failed_examples) < 100:
                failed_examples.append(
                    {
                        "utt_id": name,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            continue
        counts["created"] += 1
    result = dict(counts)
    result["alignment_missing_examples"] = missing_alignment_examples
    result["form_missing_examples"] = form_missing_examples
    result["morpheme_tier_missing_inventory"] = (
        morpheme_missing_inventory
    )
    result["failed_examples"] = failed_examples
    return result


def export_database(
    *,
    db_path: Path,
    year: str,
    search_master_root: Path,
    output_root: Path,
    limit_sessions: int = 0,
    workers: int = 4,
) -> dict:
    started = time.monotonic()
    connection = sqlite3.connect(
        f"file:{db_path.resolve().as_posix()}?mode=ro",
        uri=True,
        timeout=120,
    )
    try:
        spn_intervals = count_spn_intervals(connection)
        if spn_intervals:
            return {
                "schema_version": 2,
                "year": year,
                "db_path": str(db_path.resolve()),
                "search_master_root": str(
                    search_master_root.resolve()
                ),
                "output_root": str(output_root.resolve()),
                "elapsed_seconds": round(
                    time.monotonic() - started, 3
                ),
                "counts": {
                    "spn_intervals": spn_intervals,
                },
                "status": "failed",
                "morphology_complete": False,
                "analysis_ready_status": "blocked_spn_intervals",
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
            sessions[str(session)].append((uid, str(name), float(duration)))
        selected = sorted(sessions.items())
        if limit_sessions:
            selected = selected[:limit_sessions]
    finally:
        connection.close()

    def process_session(item):
        session, utterances = item
        session_forms = load_session_forms(
            search_master_root, year, session
        )
        local_connection = sqlite3.connect(
            f"file:{db_path.resolve().as_posix()}?mode=ro",
            uri=True,
            timeout=120,
        )
        try:
            result = export_session(
                local_connection,
                year=year,
                output_root=output_root,
                session=session,
                utterances=utterances,
                word_labels=word_labels,
                phone_labels=phone_labels,
                forms=session_forms,
            )
        finally:
            local_connection.close()
        return session, len(utterances), result

    totals = defaultdict(int)
    totals["spn_intervals"] = spn_intervals
    alignment_missing_examples: list[str] = []
    form_missing_examples: list[str] = []
    morpheme_missing_inventory: list[str] = []
    failed_examples: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(process_session, item): item[0]
            for item in selected
        }
        for index, future in enumerate(as_completed(futures), 1):
            _session, utterance_count, result = future.result()
            totals["source_utterances"] += utterance_count
            for key, value in result.items():
                if key == "alignment_missing_examples":
                    alignment_missing_examples.extend(
                        value[: max(0, 100 - len(alignment_missing_examples))]
                    )
                elif key == "form_missing_examples":
                    form_missing_examples.extend(
                        value[: max(0, 100 - len(form_missing_examples))]
                    )
                elif key == "morpheme_tier_missing_inventory":
                    morpheme_missing_inventory.extend(value)
                elif key == "failed_examples":
                    failed_examples.extend(
                        value[: max(0, 100 - len(failed_examples))]
                    )
                else:
                    totals[key] += value
            if index % 50 == 0 or index == len(selected):
                elapsed = max(time.monotonic() - started, 1e-9)
                print(
                    f"[{year}] {index:,}/{len(selected):,} sessions · "
                    f"created {totals['created']:,} · "
                    f"{totals['created'] / elapsed:,.0f}/s",
                    flush=True,
                )

    elapsed = time.monotonic() - started
    hard_failures = totals["form_missing"] + totals["failed"]
    accounted = (
        totals["created"]
        + totals["validated_existing"]
        + totals["alignment_missing"]
        + totals["form_missing"]
        + totals["failed"]
    )
    export_success = bool(
        totals["source_utterances"] > 0
        and hard_failures == 0
        and (
            totals["created"] + totals["validated_existing"]
        ) / totals["source_utterances"] >= 0.99
        and accounted == totals["source_utterances"]
    )
    morphology_complete = totals["morpheme_tier_missing"] == 0
    return {
        "schema_version": 2,
        "year": year,
        "db_path": str(db_path.resolve()),
        "search_master_root": str(search_master_root.resolve()),
        "output_root": str(output_root.resolve()),
        "tier_provenance": {
            "words": "mfa_word_intervals_eojeol",
            "phones": "phones_mfa",
            "morphemes": (
                "morphemes_legacy_copy_of_06_textgrid_merged_words"
            ),
            "utterance": "frozen_search_master_form",
        },
        "elapsed_seconds": round(elapsed, 3),
        "counts": dict(sorted(totals.items())),
        "alignment_missing_examples": alignment_missing_examples[:100],
        "form_missing_examples": form_missing_examples[:100],
        "morpheme_tier_missing_inventory": sorted(
            set(morpheme_missing_inventory)
        ),
        "failed_examples": failed_examples[:100],
        "accounted": accounted,
        "coverage_pct": round(
            100
            * (totals["created"] + totals["validated_existing"])
            / totals["source_utterances"],
            4,
        ) if totals["source_utterances"] else 0,
        # ``status``는 DB export/파일 구조의 성공 여부다. 형태소 완비는
        # 별도 analysis-ready gate이므로 빈 tier를 조용히 연구용으로
        # 승격하지 않는다.
        "status": "success" if export_success else "failed",
        "morphology_complete": morphology_complete,
        "analysis_ready_status": (
            "ready"
            if export_success and morphology_complete
            else (
                "blocked_morphology"
                if export_success
                else "blocked_export_failure"
            )
        ),
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
