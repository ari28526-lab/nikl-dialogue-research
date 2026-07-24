"""연도별 실제 화자 층화 MFA 소표본을 독립 실행 폴더에 구성한다.

기본 표본은 2020--2025 각 연도에서 서로 다른 실제 ``speaker_id`` 5명,
화자당 2발화(총 10발화)다. 각 화자는 서로 다른 원 세션에서 선택한다.
원본 WAV/CSV/TextGrid는 읽기만 하고, 다음 자료를 run root 아래에 복사한다.

* ``corpus/{year}/{speaker_id}/{utt_id}.wav|lab``: MFA 입력
* ``csv/{year}/bareun_selected.csv``: 바른 형태소 분석 선택행
* ``csv/{year}/search_master_selected.csv``: 검색 마스터 선택행
* ``csv/{year}/speaker_metadata_selected.csv``: 선택 화자 메타데이터
* ``selection_manifest.csv|json``: 모든 파일의 연결 좌표와 선정 근거

표본은 seed 기반 SHA256 순서로 정해져 파일시스템 열거 순서와 무관하며,
같은 seed·입력에는 같은 결과가 나온다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    promote_staged,
    runtime_snapshot,
    staged_text_writer,
)
from realign_eojeol_build_corpus import YEAR_DIRS, form_to_lab  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = P("layers") / "01_bareun_raw"
SEARCH_ROOT = P("search_master")
WAV_ROOT = P("wav") / "individual"
MORPH_TG_ROOT = P("textgrid_merged")
DEFAULT_YEARS = tuple(sorted(YEAR_DIRS))
MANIFEST_FIELDS = [
    "year",
    "sample_index",
    "speaker_sample_index",
    "speaker_id",
    "session_id",
    "utt_id",
    "form",
    "tagged",
    "n_morphs",
    "lab_text",
    "wav_duration_seconds",
    "wav_sample_rate",
    "wav_channels",
    "source_wav",
    "source_bareun_csv",
    "source_search_master_csv",
    "source_morpheme_textgrid",
    "corpus_wav_relpath",
    "corpus_lab_relpath",
]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def stable_key(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}\0{value}".encode("utf-8")).hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        return fields, list(reader)


def write_csv_atomic(
    path: Path, fields: list[str], rows: list[dict[str, object]]
) -> None:
    if not fields:
        raise ValueError(f"CSV 헤더가 비어 있음: {path}")
    with staged_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, temp):
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    with open(temp, encoding="utf-8-sig", newline="") as stream:
        check = list(csv.DictReader(stream))
    if len(check) != len(rows):
        raise RuntimeError(
            f"임시 CSV 행수 검증 실패: {path} expected={len(rows)} actual={len(check)}"
        )
    promote_staged(temp, path)


def inspect_wav(path: Path) -> dict[str, float | int]:
    if path.stat().st_size < 44:
        raise ValueError("WAV가 44바이트보다 작음")
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        channels = wav.getnchannels()
        if frames <= 0 or rate <= 0 or channels <= 0:
            raise ValueError(
                f"잘못된 WAV 헤더: frames={frames} rate={rate} channels={channels}"
            )
        return {
            "duration": frames / rate,
            "sample_rate": rate,
            "channels": channels,
        }


def locate_wav(wav_year: Path, session_id: str, utt_id: str) -> Path | None:
    nested = wav_year / session_id / f"{utt_id}.wav"
    if nested.is_file():
        return nested
    flat = wav_year / f"{utt_id}.wav"
    if flat.is_file():
        return flat
    return None


def eligible_rows(
    rows: list[dict[str, str]],
    *,
    year: str,
    session_id: str,
    speaker_id: str,
    wav_year: Path,
    morph_year: Path,
    per_speaker: int,
    seed: str,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    speaker_rows = [
        row for row in rows
        if (row.get("speaker_id") or "").strip() == speaker_id
    ]
    speaker_rows.sort(
        key=lambda row: stable_key(
            f"{seed}:{year}:{speaker_id}", row.get("utt_id", "")
        )
    )
    for row in speaker_rows:
        utt_id = (row.get("utt_id") or "").strip()
        if not utt_id or utt_id.split(".")[0] != session_id:
            continue
        lab_text = form_to_lab(row.get("form", ""))
        if not lab_text:
            continue
        wav_path = locate_wav(wav_year, session_id, utt_id)
        morph_path = morph_year / session_id / f"{utt_id}.TextGrid"
        if wav_path is None or not morph_path.is_file():
            continue
        try:
            wav_info = inspect_wav(wav_path)
        except (OSError, EOFError, wave.Error, ValueError):
            continue
        item: dict[str, object] = dict(row)
        item.update({
            "year": year,
            "session_id": session_id,
            "speaker_id": speaker_id,
            "lab_text": lab_text,
            "source_wav": str(wav_path.resolve()),
            "source_morpheme_textgrid": str(morph_path.resolve()),
            "wav_duration_seconds": round(float(wav_info["duration"]), 6),
            "wav_sample_rate": int(wav_info["sample_rate"]),
            "wav_channels": int(wav_info["channels"]),
        })
        candidates.append(item)
        if len(candidates) == per_speaker:
            return candidates
    return []


def select_year(
    *,
    year: str,
    raw_dir: Path,
    wav_year: Path,
    morph_year: Path,
    utterances: int,
    speakers: int,
    seed: str,
) -> list[dict[str, object]]:
    if utterances <= 0 or speakers <= 0 or utterances % speakers:
        raise ValueError("발화 수는 양수이며 화자 수의 배수여야 함")
    per_speaker = utterances // speakers
    session_files = sorted(
        (path for path in raw_dir.glob("*.csv") if not path.name.startswith("_")),
        key=lambda path: stable_key(f"{seed}:{year}:session", path.stem),
    )
    if not session_files:
        raise RuntimeError(f"{year} 세션 CSV 0개: {raw_dir}")

    selected: list[dict[str, object]] = []
    selected_speakers: set[str] = set()
    selected_sessions: set[str] = set()
    for csv_path in session_files:
        session_id = csv_path.stem
        if session_id in selected_sessions:
            continue
        fields, rows = read_csv(csv_path)
        required = {"utt_id", "speaker_id", "form", "tagged", "n_morphs"}
        missing = required - set(fields)
        if missing:
            raise RuntimeError(
                f"{csv_path} 필수 열 누락: {sorted(missing)}"
            )
        speakers_here = sorted(
            {
                (row.get("speaker_id") or "").strip()
                for row in rows
                if (row.get("speaker_id") or "").strip()
            },
            key=lambda value: stable_key(
                f"{seed}:{year}:{session_id}:speaker", value
            ),
        )
        for speaker_id in speakers_here:
            if speaker_id in selected_speakers:
                continue
            picked = eligible_rows(
                rows,
                year=year,
                session_id=session_id,
                speaker_id=speaker_id,
                wav_year=wav_year,
                morph_year=morph_year,
                per_speaker=per_speaker,
                seed=seed,
            )
            if len(picked) != per_speaker:
                continue
            for item in picked:
                item["source_bareun_csv"] = str(csv_path.resolve())
            selected.extend(picked)
            selected_speakers.add(speaker_id)
            selected_sessions.add(session_id)
            break  # 서로 다른 세션에서 화자 한 명만 채택
        if len(selected_speakers) == speakers:
            break

    if len(selected) != utterances:
        raise RuntimeError(
            f"{year} 층화 표본 부족: {len(selected)}/{utterances}발화, "
            f"{len(selected_speakers)}/{speakers}화자, "
            f"{len(selected_sessions)}/{speakers}세션"
        )
    counts = Counter(str(row["speaker_id"]) for row in selected)
    if set(counts.values()) != {per_speaker}:
        raise RuntimeError(f"{year} 화자별 표본 수 불균형: {dict(counts)}")
    if len(selected_sessions) != speakers:
        raise RuntimeError(
            f"{year} 서로 다른 세션 {speakers}개를 확보하지 못함"
        )
    selected.sort(
        key=lambda row: (
            str(row["speaker_id"]),
            stable_key(f"{seed}:{year}:final", str(row["utt_id"])),
        )
    )
    for index, item in enumerate(selected, 1):
        item["sample_index"] = index
        item["speaker_sample_index"] = 1 + sum(
            1
            for prior in selected[: index - 1]
            if prior["speaker_id"] == item["speaker_id"]
        )
    return selected


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.name}.{os.getpid()}.partial")
    if temp.exists():
        raise FileExistsError(f"이전 임시 복사본 존재: {temp}")
    shutil.copy2(source, temp)
    if temp.stat().st_size != source.stat().st_size:
        raise RuntimeError(f"복사 크기 불일치: {source} -> {temp}")
    os.replace(temp, destination)


def read_selected_search_rows(
    year: str,
    selected: list[dict[str, object]],
    search_root: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    wanted_by_session: dict[str, set[str]] = defaultdict(set)
    for item in selected:
        wanted_by_session[str(item["session_id"])].add(str(item["utt_id"]))
    fields: list[str] | None = None
    found: dict[str, dict[str, str]] = {}
    for session_id, wanted in wanted_by_session.items():
        path = search_root / year / f"{session_id}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"검색 마스터 세션 CSV 없음: {path}")
        current_fields, rows = read_csv(path)
        if fields is None:
            fields = current_fields
        elif current_fields != fields:
            raise RuntimeError(f"검색 마스터 헤더 불일치: {path}")
        for row in rows:
            utt_id = row.get("utt_id", "")
            if utt_id in wanted:
                found[utt_id] = row
        for item in selected:
            if str(item["session_id"]) == session_id:
                item["source_search_master_csv"] = str(path.resolve())
    missing = sorted(
        str(item["utt_id"]) for item in selected
        if str(item["utt_id"]) not in found
    )
    if missing:
        raise RuntimeError(f"{year} 검색 마스터 선택행 누락: {missing}")
    return fields or [], [found[str(item["utt_id"])] for item in selected]


def validate_existing(
    run_root: Path,
    years: list[str],
    utterances: int,
    speakers: int,
    seed: str,
) -> bool:
    manifest_path = run_root / "selection_manifest.csv"
    json_path = run_root / "selection_manifest.json"
    if not manifest_path.is_file() or not json_path.is_file():
        return False
    try:
        metadata = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    if (
        metadata.get("status") != "selection_complete"
        or metadata.get("utterances_per_year") != utterances
        or metadata.get("speakers_per_year") != speakers
        or metadata.get("selection_seed") != seed
        or not set(years).issubset(set(metadata.get("years", [])))
    ):
        return False
    _, rows = read_csv(manifest_path)
    for year in years:
        year_rows = [row for row in rows if row.get("year") == year]
        if len(year_rows) != utterances:
            return False
        if len({row["speaker_id"] for row in year_rows}) != speakers:
            return False
        if len({row["session_id"] for row in year_rows}) != speakers:
            return False
        for row in year_rows:
            wav = run_root / row["corpus_wav_relpath"]
            lab = run_root / row["corpus_lab_relpath"]
            if not wav.is_file() or wav.stat().st_size < 44:
                return False
            if not lab.is_file() or not lab.read_text(encoding="utf-8").strip():
                return False
    return True


def build_run(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    years = list(args.years)
    if any(year not in YEAR_DIRS for year in years):
        raise ValueError(f"지원하지 않는 연도: {years}")
    if validate_existing(
        run_root,
        years,
        args.utterances_per_year,
        args.speakers_per_year,
        args.seed,
    ):
        print(f"검증된 기존 표본 재사용: {run_root}", flush=True)
        return 0
    if run_root.exists() and any(run_root.iterdir()):
        raise RuntimeError(
            f"완료 manifest 없는 비어 있지 않은 run root는 덮어쓰지 않음: "
            f"{run_root}. 새 --run-root를 사용하거나 수동 점검 필요"
        )
    run_root.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    source_fingerprints: list[dict] = []
    for year in years:
        raw_dir = args.raw_root / YEAR_DIRS[year]
        selected = select_year(
            year=year,
            raw_dir=raw_dir,
            wav_year=args.wav_root / year,
            morph_year=args.morph_root / year,
            utterances=args.utterances_per_year,
            speakers=args.speakers_per_year,
            seed=args.seed,
        )
        search_fields, search_rows = read_selected_search_rows(
            year, selected, args.search_root
        )

        bareun_fields = ["utt_id", "speaker_id", "form", "tagged", "n_morphs"]
        speaker_path = raw_dir / "_speakers.csv"
        speaker_fields, speaker_rows = read_csv(speaker_path)
        wanted_speakers = {str(row["speaker_id"]) for row in selected}
        selected_speaker_rows = [
            row for row in speaker_rows if row.get("id") in wanted_speakers
        ]
        if {row.get("id") for row in selected_speaker_rows} != wanted_speakers:
            raise RuntimeError(f"{year} 선택 화자 메타데이터 누락")

        for item in selected:
            speaker = str(item["speaker_id"])
            utt_id = str(item["utt_id"])
            wav_rel = Path("corpus") / year / speaker / f"{utt_id}.wav"
            lab_rel = Path("corpus") / year / speaker / f"{utt_id}.lab"
            atomic_copy(Path(str(item["source_wav"])), run_root / wav_rel)
            with atomic_text_writer(
                run_root / lab_rel, encoding="utf-8", newline="\n"
            ) as (stream, _):
                stream.write(str(item["lab_text"]) + "\n")
            inspect_wav(run_root / wav_rel)
            item["corpus_wav_relpath"] = wav_rel.as_posix()
            item["corpus_lab_relpath"] = lab_rel.as_posix()

        csv_dir = run_root / "csv" / year
        write_csv_atomic(
            csv_dir / "bareun_selected.csv",
            bareun_fields,
            [{field: item.get(field, "") for field in bareun_fields}
             for item in selected],
        )
        write_csv_atomic(
            csv_dir / "search_master_selected.csv",
            search_fields,
            search_rows,
        )
        write_csv_atomic(
            csv_dir / "speaker_metadata_selected.csv",
            speaker_fields,
            selected_speaker_rows,
        )
        all_rows.extend(selected)
        for path in sorted({Path(str(row["source_bareun_csv"])) for row in selected}):
            source_fingerprints.append(file_fingerprint(path))
        print(
            f"[{year}] {len(selected)}발화 / "
            f"{len({row['speaker_id'] for row in selected})}화자 / "
            f"{len({row['session_id'] for row in selected})}세션 구성 완료",
            flush=True,
        )

    write_csv_atomic(
        run_root / "selection_manifest.csv",
        MANIFEST_FIELDS,
        all_rows,
    )
    payload = {
        "schema_version": 1,
        "created_at": now_iso(),
        "purpose": "연도별 실제 화자 층화 G2P MFA end-to-end 파일럿",
        "years": years,
        "utterances_per_year": args.utterances_per_year,
        "speakers_per_year": args.speakers_per_year,
        "utterances_per_speaker": (
            args.utterances_per_year // args.speakers_per_year
        ),
        "distinct_sessions_per_year": args.speakers_per_year,
        "selection_seed": args.seed,
        "run_root": str(run_root),
        "source_roots": {
            "bareun": str(args.raw_root.resolve()),
            "search_master": str(args.search_root.resolve()),
            "wav": str(args.wav_root.resolve()),
            "morpheme_textgrid": str(args.morph_root.resolve()),
        },
        "source_bareun_csv_fingerprints": source_fingerprints,
        "runtime": runtime_snapshot(PROJECT_ROOT),
        "rows": len(all_rows),
        "status": "selection_complete",
    }
    atomic_write_json(run_root / "selection_manifest.json", payload)
    print(f"표본 manifest: {run_root / 'selection_manifest.csv'}", flush=True)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--years", nargs="+", default=list(DEFAULT_YEARS))
    parser.add_argument("--utterances-per-year", type=int, default=10)
    parser.add_argument("--speakers-per-year", type=int, default=5)
    parser.add_argument("--seed", default="speaker5_year10_v1")
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--search-root", type=Path, default=SEARCH_ROOT)
    parser.add_argument("--wav-root", type=Path, default=WAV_ROOT)
    parser.add_argument("--morph-root", type=Path, default=MORPH_TG_ROOT)
    return parser.parse_args()


def main() -> int:
    return build_run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
