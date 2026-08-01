"""Synthetic scale benchmark for the 6-tier DB exporter (no MFA required)."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
import tracemalloc
import zipfile
from pathlib import Path

from export_mfa_db_research_6tier import export_database
from pipeline_common import atomic_write_json, now_iso

SCHEMA_VERSION = "mfa_research_6tier_export_benchmark.v1"
SEARCH_FIELDS = [
    "utt_id", "year", "session_id", "speaker_id", "dialogue_id",
    "dialogue_speaker_ids", "co_speaker_ids", "form", "original_form",
    "form_roman", "tagged", "tagged_roman_v2", "n_eojeol", "start", "end",
    "pron_reference_form", "pron_reference_n_eojeol",
    "pron_reference_hangul", "pron_reference_roman", "pron_reference_ipa",
    "pron_reference_source", "pron_reference_status",
]


def _build_fixture(root: Path, *, year: str, sessions: int, per_session: int) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    db = root / "fixture.db"
    search_root = root / "search"
    acoustic = root / "acoustic.zip"
    contract = root / "alignment_contract.json"
    with zipfile.ZipFile(acoustic, "w") as archive:
        archive.writestr(
            "acoustic/meta.json",
            json.dumps({"phones": ["k"], "phone_groups": {"0": ["k"]}}),
        )
    contract.write_text(
        json.dumps(
            {
                "status": "passed",
                "year": year,
                "alignment_contract_id": "BENCH_ALIGNMENT_V1",
                "lab_input_contract_id": "BENCH_INPUT_V1",
                "models": {},
            }
        ),
        encoding="utf-8",
    )
    con = sqlite3.connect(db)
    con.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE file(id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT);
        CREATE TABLE sound_file(file_id INTEGER PRIMARY KEY, duration FLOAT, sound_file_path TEXT);
        CREATE TABLE utterance(id INTEGER PRIMARY KEY, file_id INTEGER, ignored BOOLEAN, alignment_score FLOAT);
        CREATE TABLE word(id INTEGER PRIMARY KEY, word TEXT);
        CREATE TABLE phone(id INTEGER PRIMARY KEY, phone TEXT, phone_type TEXT);
        CREATE TABLE word_interval(id INTEGER PRIMARY KEY, utterance_id INTEGER, begin FLOAT, end FLOAT, word_id INTEGER);
        CREATE TABLE phone_interval(id INTEGER PRIMARY KEY, utterance_id INTEGER, begin FLOAT, end FLOAT, phone_id INTEGER, word_interval_id INTEGER);
        INSERT INTO word VALUES(1, '가');
        INSERT INTO word VALUES(2, '<eps>');
        INSERT INTO phone VALUES(1, 'k', 'non_silence');
        INSERT INTO phone VALUES(2, 'sil', 'silence');
        """
    )
    file_rows = []
    sound_rows = []
    utterance_rows = []
    word_rows = []
    phone_rows = []
    uid = 0
    interval_id = 0
    for session_number in range(1, sessions + 1):
        session = f"BENCH{session_number:05d}"
        search_path = search_root / year / f"{session}.csv"
        search_path.parent.mkdir(parents=True, exist_ok=True)
        with search_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SEARCH_FIELDS, lineterminator="\n")
            writer.writeheader()
            for item in range(1, per_session + 1):
                uid += 1
                name = f"{session}.1.1.{item}"
                file_rows.append((uid, name, session))
                sound_rows.append((uid, 1.0, f"D:/synthetic/{session}/{name}.wav"))
                utterance_rows.append((uid, uid, 0, -10.0))
                word_ids = []
                for begin, end, word_id in ((0.0, 0.1, 2), (0.1, 0.9, 1), (0.9, 1.0, 2)):
                    interval_id += 1
                    word_ids.append(interval_id)
                    word_rows.append((interval_id, uid, begin, end, word_id))
                for index, (begin, end, phone_id) in enumerate(
                    ((0.0, 0.1, 2), (0.1, 0.9, 1), (0.9, 1.0, 2))
                ):
                    phone_rows.append(
                        (len(phone_rows) + 1, uid, begin, end, phone_id, word_ids[index])
                    )
                writer.writerow(
                    {
                        "utt_id": name, "year": year, "session_id": session,
                        "speaker_id": session, "dialogue_id": session,
                        "dialogue_speaker_ids": session, "co_speaker_ids": "",
                        "form": "가", "original_form": "가", "form_roman": "G A",
                        "tagged": "가/NNG", "tagged_roman_v2": "G A/NNG",
                        "n_eojeol": "1", "start": "0", "end": "1",
                        "pron_reference_form": "가",
                        "pron_reference_n_eojeol": "1",
                        "pron_reference_hangul": "가",
                        "pron_reference_roman": "G A",
                        "pron_reference_ipa": "ka",
                        "pron_reference_source": "synthetic",
                        "pron_reference_status": "resolved",
                    }
                )
    con.executemany("INSERT INTO file VALUES(?,?,?)", file_rows)
    con.executemany("INSERT INTO sound_file VALUES(?,?,?)", sound_rows)
    con.executemany("INSERT INTO utterance VALUES(?,?,?,?)", utterance_rows)
    con.executemany("INSERT INTO word_interval VALUES(?,?,?,?,?)", word_rows)
    con.executemany("INSERT INTO phone_interval VALUES(?,?,?,?,?,?)", phone_rows)
    con.commit()
    con.close()
    return {
        "db": db,
        "search_root": search_root,
        "acoustic": acoustic,
        "contract": contract,
        "utterances": uid,
        "word_intervals": len(word_rows),
        "phone_intervals": len(phone_rows),
    }


def _run_export(fixture: dict, *, year: str, output: Path, report: Path) -> dict:
    tracemalloc.start()
    started = time.monotonic()
    result = export_database(
        db_path=fixture["db"], year=year,
        search_master_root=fixture["search_root"], output_root=output,
        acoustic_model=fixture["acoustic"], alignment_contract=fixture["contract"],
        workers=4,
    )
    elapsed = time.monotonic() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    atomic_write_json(report, result)
    return {
        "elapsed_seconds": round(elapsed, 3),
        "python_peak_mib": round(peak / 1024 / 1024, 3),
        "created": int(result["counts"].get("created", 0)),
        "validated_existing": int(result["counts"].get("validated_existing", 0)),
        "status": result["status"],
    }


def benchmark(*, root: Path, year: str, sessions: int, per_session: int) -> dict:
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise RuntimeError(f"benchmark root must be empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    fixture_started = time.monotonic()
    fixture = _build_fixture(
        root / "fixture", year=year, sessions=sessions, per_session=per_session
    )
    fixture_seconds = time.monotonic() - fixture_started
    output = root / "output"
    first = _run_export(fixture, year=year, output=output, report=root / "first.json")
    resume = _run_export(fixture, year=year, output=output, report=root / "resume.json")
    files = [path for path in output.rglob("*") if path.is_file()]
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "success" if first["status"] == resume["status"] == "success" else "failed",
        "generated_at": now_iso(),
        "synthetic_data_only": True,
        "mfa_executed": False,
        "parameters": {"year": year, "sessions": sessions, "per_session": per_session},
        "fixture": {
            "utterances": fixture["utterances"],
            "word_intervals": fixture["word_intervals"],
            "phone_intervals": fixture["phone_intervals"],
            "build_seconds": round(fixture_seconds, 3),
        },
        "first_export": first,
        "resume_export": resume,
        "output": {
            "files": len(files),
            "bytes": sum(path.stat().st_size for path in files),
            "active_partial_files": sum(path.name.endswith(".partial") for path in files),
        },
        "memory_note": "tracemalloc Python allocations only; OS/SQLite buffers excluded",
    }
    atomic_write_json(root / "BENCHMARK.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--year", default="2025")
    parser.add_argument("--sessions", type=int, default=100)
    parser.add_argument("--per-session", type=int, default=100)
    args = parser.parse_args()
    if args.sessions < 1 or args.per_session < 1:
        parser.error("session/utterance counts must be positive")
    result = benchmark(
        root=args.root, year=args.year,
        sessions=args.sessions, per_session=args.per_session,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
