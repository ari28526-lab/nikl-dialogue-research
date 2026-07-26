"""남은 연도 MFA 입력을 수정 없이 전수 감사한다.

대량 실행기의 lab 생성과 같은 ``pron_reference_form -> Hangul-only lab``
계약을 사용하되, WAV·lab·CSV를 읽기만 한다. 특히 다음을 연도별로 수치화한다.

- 검색 CSV 행/세션, 화자 메타 결측, 미해결 기호 발음
- WAV 누락·44바이트 미만 파일
- 현재 lab의 존재/0바이트/예상 내용 일치 여부
- 검색 입력에 속하지 않는데 WAV와 함께 남아 MFA가 읽을 수 있는 stale lab
- 과거 residual 조사에서 확인한 원본 PCM 결함

기본 실행은 파일명/크기만 감사한다. 기존 lab 내용까지 전수 대조하려면
``--compare-lab-content``를 붙인다. 결과는 JSON으로 원자적으로 기록한다.
원자료·WAV·lab·MFA marker는 변경하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline_common import atomic_write_json
from realign_eojeol_build_corpus import MISSING, form_to_lab

csv.field_size_limit(10_000_000)

YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
REQUIRED_COLUMNS = {
    "utt_id",
    "form",
    "pron_reference_form",
    "pron_reference_source",
    "pron_reference_status",
    "sex",
}


def directory_entries(path: Path) -> dict[str, int]:
    """한 세션의 파일명과 크기를 한 번의 scandir로 읽는다."""
    try:
        return {
            entry.name: entry.stat().st_size
            for entry in os.scandir(path)
            if entry.is_file()
        }
    except OSError:
        return {}


def normalized_lab_text(text: str) -> str:
    return " ".join((text or "").split())


def load_known_pcm_risks(path: Path | None) -> dict[str, Counter]:
    result: dict[str, Counter] = defaultdict(Counter)
    if path is None or not path.is_file():
        return result
    with open(path, encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            year = (row.get("year") or "").strip()
            category = (row.get("category") or "미분류").strip()
            if year:
                result[year][category] += 1
    return result


def _add_example(examples: dict[str, list[str]], key: str, value: str) -> None:
    bucket = examples.setdefault(key, [])
    if len(bucket) < 20:
        bucket.append(value)


def compare_lab(path: Path, expected_text: str) -> tuple[str, str]:
    """lab 하나를 읽어 ``match/mismatch/unreadable``로 분류한다."""
    try:
        actual = normalized_lab_text(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError):
        return path.stem, "unreadable"
    if actual == normalized_lab_text(expected_text):
        return path.stem, "match"
    return path.stem, "mismatch"


def audit_year(
    *,
    year: str,
    search_master_root: Path,
    wav_root: Path,
    compare_lab_content: bool,
    known_pcm: Counter | None = None,
    lab_workers: int = 8,
) -> dict:
    """한 연도를 읽기 전용으로 전수 감사한다."""
    source_dir = search_master_root / year
    csv_files = sorted(
        path
        for path in source_dir.glob("*.csv")
        if not path.name.startswith("_")
    )
    if not csv_files:
        raise RuntimeError(f"{year} search master CSV 0개: {source_dir}")

    counts: Counter = Counter()
    examples: dict[str, list[str]] = {}
    risky_sessions: Counter = Counter()
    scanned_sessions: set[str] = set()
    started = time.monotonic()
    executor = (
        ThreadPoolExecutor(max_workers=max(1, lab_workers))
        if compare_lab_content
        else None
    )

    try:
        for file_index, csv_path in enumerate(csv_files, 1):
            rows_by_session: dict[str, list[dict[str, str]]] = defaultdict(list)
            with open(csv_path, encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
                if missing:
                    raise RuntimeError(
                        f"{csv_path}: 필수 열 누락 {sorted(missing)}"
                    )
                for row in reader:
                    utt_id = (row.get("utt_id") or "").strip()
                    if not utt_id:
                        raise RuntimeError(f"{csv_path}: 빈 utt_id")
                    session = utt_id.split(".", 1)[0]
                    rows_by_session[session].append(row)

            for session, rows in rows_by_session.items():
                session_dir = wav_root / year / session
                entries = directory_entries(session_dir)
                if session in scanned_sessions:
                    raise RuntimeError(
                        f"{year} 세션이 여러 CSV에 중복됨: {session}"
                    )
                scanned_sessions.add(session)
                counts["search_sessions"] += 1
                if not session_dir.is_dir():
                    counts["session_folder_missing"] += 1
                    _add_example(examples, "session_folder_missing", session)

                wav_ids = {
                    name[:-4]
                    for name in entries
                    if name.lower().endswith(".wav")
                }
                lab_ids = {
                    name[:-4]
                    for name in entries
                    if name.lower().endswith(".lab")
                }
                counts["wav_files"] += len(wav_ids)
                counts["lab_files"] += len(lab_ids)
                for utt_id in wav_ids:
                    if entries.get(f"{utt_id}.wav", 0) < 44:
                        counts["wav_too_small"] += 1
                        risky_sessions[session] += 1
                        _add_example(examples, "wav_too_small", utt_id)

                search_ids: set[str] = set()
                expected_lab_ids: set[str] = set()
                lab_checks: list[tuple[Path, str]] = []
                for row in rows:
                    counts["search_rows"] += 1
                    utt_id = row["utt_id"].strip()
                    search_ids.add(utt_id)
                    if row.get("sex") == "미상":
                        counts["speaker_missing"] += 1
                    if row.get("pron_reference_status") == "unresolved_symbol":
                        counts["pron_reference_unresolved"] += 1

                    form = (row.get("form") or "").strip()
                    reference_form = (
                        row.get("pron_reference_form") or ""
                    ).strip()
                    if reference_form in MISSING:
                        reference_form = form
                    if reference_form != form:
                        counts["reference_form_changed"] += 1
                    expected_text = form_to_lab(reference_form)

                    if utt_id not in wav_ids:
                        counts["wav_missing"] += 1
                        risky_sessions[session] += 1
                        _add_example(examples, "wav_missing", utt_id)
                        if utt_id in lab_ids:
                            counts["lab_without_wav"] += 1
                            _add_example(examples, "lab_without_wav", utt_id)
                        continue

                    if not expected_text.strip():
                        counts["empty_reference_form"] += 1
                        if utt_id in lab_ids:
                            counts["stale_lab_for_empty_input"] += 1
                            risky_sessions[session] += 1
                            _add_example(
                                examples, "stale_lab_for_empty_input", utt_id
                            )
                        continue

                    expected_lab_ids.add(utt_id)
                    counts["expected_usable_lab"] += 1
                    lab_size = entries.get(f"{utt_id}.lab")
                    if lab_size is None:
                        counts["expected_lab_missing"] += 1
                        continue
                    if lab_size == 0:
                        counts["expected_lab_zero_byte"] += 1
                        risky_sessions[session] += 1
                        _add_example(examples, "expected_lab_zero_byte", utt_id)
                        continue
                    counts["expected_lab_nonzero"] += 1
                    if compare_lab_content:
                        lab_checks.append(
                            (session_dir / f"{utt_id}.lab", expected_text)
                        )

                if executor is not None:
                    for utt_id, status in executor.map(
                        lambda item: compare_lab(*item), lab_checks
                    ):
                        counts[f"lab_content_{status}"] += 1
                        if status != "match":
                            risky_sessions[session] += 1
                            _add_example(
                                examples, f"lab_content_{status}", utt_id
                            )

                extra_wav = wav_ids - search_ids
                extra_lab = lab_ids - expected_lab_ids
                extra_lab_with_wav = extra_lab & wav_ids
                counts["wav_not_in_search_master"] += len(extra_wav)
                counts["lab_not_expected"] += len(extra_lab)
                counts["lab_not_expected_with_wav"] += len(extra_lab_with_wav)
                for utt_id in sorted(extra_lab_with_wav)[:20]:
                    risky_sessions[session] += 1
                    _add_example(
                        examples, "lab_not_expected_with_wav", utt_id
                    )

            if file_index % 500 == 0 or file_index == len(csv_files):
                elapsed = max(time.monotonic() - started, 1e-9)
                print(
                    f"[{year}] {file_index:,}/{len(csv_files):,} CSV · "
                    f"{counts['search_rows']:,}행 · "
                    f"{counts['search_rows'] / elapsed:,.0f}행/s",
                    flush=True,
                )
    finally:
        if executor is not None:
            executor.shutdown(wait=True)

    elapsed = time.monotonic() - started
    result = {
        "year": year,
        "status": "audited",
        "read_only": True,
        "compare_lab_content": compare_lab_content,
        "csv_files": len(csv_files),
        "elapsed_seconds": round(elapsed, 3),
        "counts": dict(sorted(counts.items())),
        "known_source_pcm_risks": dict(sorted((known_pcm or {}).items())),
        "top_risky_sessions": [
            {"session": session, "issue_count": count}
            for session, count in risky_sessions.most_common(30)
        ],
        "examples": examples,
    }
    result["gates"] = {
        "session_folders_present": counts["session_folder_missing"] == 0,
        "no_dangerous_unexpected_labs": (
            counts["lab_not_expected_with_wav"] == 0
        ),
        "all_expected_labs_ready": (
            counts["expected_lab_missing"] == 0
            and counts["expected_lab_zero_byte"] == 0
            and (
                not compare_lab_content
                or (
                    counts["lab_content_mismatch"] == 0
                    and counts["lab_content_unreadable"] == 0
                )
            )
        ),
        "no_fatal_tiny_wav": counts["wav_too_small"] == 0,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--years",
        nargs="+",
        default=list(YEARS[1:]),
        choices=YEARS,
    )
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument(
        "--wav-root",
        type=Path,
        default=Path(r"D:\20_AUDIO\03_wav\individual"),
    )
    parser.add_argument(
        "--source-pcm-check",
        type=Path,
        default=Path(
            r"D:\10_LAYERS\05_audio_index\source_pcm_check.csv"
        ),
    )
    parser.add_argument("--compare-lab-content", action="store_true")
    parser.add_argument("--lab-workers", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    meta_path = args.search_master_root / "_build_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"search master meta 읽기 실패: {meta_path}: {exc}")
    if meta.get("status") != "success":
        raise SystemExit(
            f"search master status가 success 아님: {meta.get('status')}"
        )

    known_pcm = load_known_pcm_risks(args.source_pcm_check)
    report = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "read_only": True,
        "search_master_root": str(args.search_master_root.resolve()),
        "search_master_build_status": meta.get("status"),
        "wav_root": str(args.wav_root.resolve()),
        "years": [],
    }
    for year in args.years:
        report["years"].append(
            audit_year(
                year=year,
                search_master_root=args.search_master_root,
                wav_root=args.wav_root,
                compare_lab_content=args.compare_lab_content,
                known_pcm=known_pcm.get(year),
                lab_workers=args.lab_workers,
            )
        )
        atomic_write_json(args.output, report)
    print(f"report: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
