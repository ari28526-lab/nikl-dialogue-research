"""연도별 실제 화자 층화 MFA 소표본을 독립 실행 폴더에 구성한다.

기본 표본은 2020--2025 각 연도에서 서로 다른 실제 ``speaker_id`` 5명,
화자당 2발화(총 10발화)다. 각 화자는 서로 다른 원 세션에서 선택한다.
원본 WAV/CSV/TextGrid는 읽기만 하고, 다음 자료를 run root 아래에 복사한다.

* ``corpus/{year}/{session_id}/{utt_id}.wav|lab``: MFA 입력
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
import statistics
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
    sha256_file,
    staged_text_writer,
)
from realign_eojeol_build_corpus import (  # noqa: E402
    TOKEN_MAP_VERSION,
    YEAR_DIRS,
    form_to_lab,
    form_to_lab_mapping,
)

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
    "pron_reference_form",
    "pron_reference_source",
    "pron_reference_status",
    "tagged",
    "n_morphs",
    "lab_text",
    "lab_source_field",
    "eojeol_map_json",
    "wav_duration_seconds",
    "csv_duration_seconds",
    "wav_csv_duration_delta_seconds",
    "session_padding_seconds",
    "session_duration_match_pct",
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
    if path.stat().st_size <= 44:
        raise ValueError("WAV가 44바이트 이하라 음성 payload가 없음")
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


def audit_session_durations(
    *,
    session_id: str,
    rows: list[dict[str, str]],
    search_rows: list[dict[str, str]],
    wav_year: Path,
    residual_tolerance: float = 0.025,
    minimum_match_pct: float = 98.0,
) -> dict[str, object]:
    """CSV 주석 길이와 같은 ID WAV 길이가 세션 전체에서 대응하는지 검사.

    2024--2025 WAV에는 앞뒤 합계 약 0.4초의 일관된 패딩이 있으므로 단순
    절대차가 아니라 세션 중앙 패딩에서 벗어난 잔차를 본다. 발화 번호가
    밀린 세션은 잔차가 발화마다 크게 달라져 대응률 기준을 통과하지 못한다.
    """
    search_by_utt = {row.get("utt_id", ""): row for row in search_rows}
    deltas: list[float] = []
    inspected: list[tuple[str, float, float]] = []
    for row in rows:
        utt_id = (row.get("utt_id") or "").strip()
        search = search_by_utt.get(utt_id)
        if search is None:
            continue
        try:
            csv_duration = float(search.get("dur") or "")
        except (TypeError, ValueError):
            continue
        wav_path = locate_wav(wav_year, session_id, utt_id)
        if wav_path is None:
            continue
        try:
            wav_info = inspect_wav(wav_path)
        except (OSError, EOFError, wave.Error, ValueError):
            continue
        wav_duration = float(wav_info["duration"])
        delta = wav_duration - csv_duration
        deltas.append(delta)
        inspected.append((utt_id, csv_duration, wav_duration))
    if not deltas:
        return {
            "valid": False,
            "reason": "비교 가능한 CSV–WAV 길이 0건",
            "inspected": 0,
            "padding": None,
            "match_pct": 0.0,
            "by_utt": {},
        }
    padding = statistics.median(deltas)
    matched = sum(
        abs(delta - padding) <= residual_tolerance for delta in deltas
    )
    match_pct = 100.0 * matched / len(deltas)
    # 음수 padding은 잘린 WAV, 0.5초 이상은 비정상 생성 정책일 가능성이 높다.
    padding_plausible = -0.025 <= padding <= 0.5
    valid = padding_plausible and match_pct >= minimum_match_pct
    reason = (
        "통과"
        if valid
        else (
            f"padding={padding:.3f}s, 대응률={match_pct:.2f}% "
            f"(<{minimum_match_pct:.1f}% 또는 padding 범위 위반)"
        )
    )
    by_utt = {
        utt_id: {
            "csv_duration": csv_duration,
            "wav_duration": wav_duration,
            "delta": wav_duration - csv_duration,
            "residual": (wav_duration - csv_duration) - padding,
        }
        for utt_id, csv_duration, wav_duration in inspected
    }
    return {
        "valid": valid,
        "reason": reason,
        "inspected": len(deltas),
        "padding": padding,
        "match_pct": match_pct,
        "by_utt": by_utt,
    }


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
    duration_audit: dict[str, object] | None = None,
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
        duration_info = (
            (duration_audit or {}).get("by_utt", {}).get(utt_id)
            if duration_audit
            else None
        )
        if duration_audit and duration_info is None:
            continue
        if duration_info and abs(float(duration_info["residual"])) > 0.025:
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
            "csv_duration_seconds": (
                round(float(duration_info["csv_duration"]), 6)
                if duration_info else ""
            ),
            "wav_csv_duration_delta_seconds": (
                round(float(duration_info["delta"]), 6)
                if duration_info else ""
            ),
            "session_padding_seconds": (
                round(float(duration_audit["padding"]), 6)
                if duration_audit else ""
            ),
            "session_duration_match_pct": (
                round(float(duration_audit["match_pct"]), 4)
                if duration_audit else ""
            ),
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
    search_year: Path | None,
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
        duration_audit = None
        if search_year is not None:
            search_path = search_year / csv_path.name
            if not search_path.is_file():
                raise RuntimeError(f"검색 마스터 세션 CSV 없음: {search_path}")
            _, session_search_rows = read_csv(search_path)
            duration_audit = audit_session_durations(
                session_id=session_id,
                rows=rows,
                search_rows=session_search_rows,
                wav_year=wav_year,
            )
            if not duration_audit["valid"]:
                print(
                    f"  [{year}] 자산 대응 불량 세션 제외 {session_id}: "
                    f"{duration_audit['reason']}",
                    flush=True,
                )
                continue
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
                duration_audit=duration_audit,
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


def freeze_selected_search_sessions(
    *,
    run_root: Path,
    year: str,
    fields: list[str],
    selected: list[dict[str, object]],
    rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    """선택된 검색행을 원래 세션 파일 구조로 동결하고 해시를 남긴다."""

    by_utt = {row.get("utt_id", ""): row for row in rows}
    by_session: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in selected:
        utt_id = str(item["utt_id"])
        by_session[str(item["session_id"])].append(by_utt[utt_id])

    frozen: list[dict[str, object]] = []
    for session, session_rows in sorted(by_session.items()):
        path = run_root / "search_master" / year / f"{session}.csv"
        write_csv_atomic(path, fields, session_rows)
        frozen.append(
            {
                "year": year,
                "session_id": session,
                "relative_path": path.relative_to(run_root).as_posix(),
                "rows": len(session_rows),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return frozen


def validate_frozen_search_sessions(
    run_root: Path,
    metadata: dict[str, object],
) -> bool:
    """재사용 전에 동결 세션 CSV 목록과 실제 내용을 다시 해시한다."""

    hashes_path = run_root / "search_master" / "_session_hashes.json"
    if not hashes_path.is_file():
        return False
    try:
        payload = json.loads(hashes_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    files = payload.get("files")
    metadata_files = metadata.get("frozen_search_sessions")
    if (
        payload.get("schema_version")
        != "pilot_search_master_session_hashes.v1"
        or payload.get("status") != "success"
        or payload.get("token_map_version") != TOKEN_MAP_VERSION
        or not isinstance(files, list)
        or files != metadata_files
        or payload.get("file_count") != len(files)
    ):
        return False

    canonical = json.dumps(
        files,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if payload.get("aggregate_sha256") != hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest():
        return False

    root = run_root.resolve()
    actual_rows = 0
    for record in files:
        if not isinstance(record, dict):
            return False
        relative_path = record.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            return False
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return False
        try:
            _fields, rows = read_csv(path)
            actual_bytes = path.stat().st_size
            actual_sha = sha256_file(path)
        except (OSError, UnicodeError, csv.Error):
            return False
        if (
            record.get("rows") != len(rows)
            or record.get("bytes") != actual_bytes
            or record.get("sha256") != actual_sha
        ):
            return False
        actual_rows += len(rows)
    return payload.get("row_count") == actual_rows


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
        metadata.get("schema_version") != 3
        or metadata.get("status") != "selection_complete"
        or metadata.get("utterances_per_year") != utterances
        or metadata.get("speakers_per_year") != speakers
        or metadata.get("selection_seed") != seed
        or not set(years).issubset(set(metadata.get("years", [])))
    ):
        return False
    if not validate_frozen_search_sessions(run_root, metadata):
        return False
    try:
        _, rows = read_csv(manifest_path)
    except (OSError, UnicodeError, csv.Error):
        return False
    if metadata.get("rows") != len(rows):
        return False
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
            if not wav.is_file() or wav.stat().st_size <= 44:
                return False
            if not lab.is_file():
                return False
            try:
                lab_text = lab.read_text(encoding="utf-8").strip()
                mapping = json.loads(row.get("eojeol_map_json", ""))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return False
            reference_form = row.get("pron_reference_form", "")
            if (
                row.get("lab_source_field") != "pron_reference_form"
                or lab_text != row.get("lab_text")
                or lab_text != form_to_lab(reference_form)
                or mapping != form_to_lab_mapping(reference_form)
            ):
                return False
            session_csv = (
                run_root / "search_master" / year
                / f"{row['session_id']}.csv"
            )
            if not session_csv.is_file():
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
        # r2 안전 러너는 표본 생성 전에 모델·설치 검증 보고서와 lock을
        # 생성한다. 그 러너 전용 제어 항목만 있으면 표본 산출물과 충돌하지
        # 않으므로 허용하되, corpus/csv/manifest 등 부분 표본은 계속 차단한다.
        allowed_control_entries = {
            ".pilot.lock",
            "state",
            "logs",
            "contracts",
            "phone_inventory",
            "temp",
        }
        existing = {path.name for path in run_root.iterdir()}
        unexpected = existing - allowed_control_entries
        if unexpected:
            raise RuntimeError(
                "완료 manifest 없는 부분 표본 run root는 덮어쓰지 않음: "
                f"{run_root}; 예상 밖 항목={sorted(unexpected)}. "
                "새 --run-root를 사용하거나 수동 점검 필요"
            )
    run_root.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    source_fingerprints: list[dict] = []
    frozen_search_sessions: list[dict[str, object]] = []
    for year in years:
        raw_dir = args.raw_root / YEAR_DIRS[year]
        selected = select_year(
            year=year,
            raw_dir=raw_dir,
            wav_year=args.wav_root / year,
            morph_year=args.morph_root / year,
            search_year=args.search_root / year,
            utterances=args.utterances_per_year,
            speakers=args.speakers_per_year,
            seed=args.seed,
        )
        search_fields, search_rows = read_selected_search_rows(
            year, selected, args.search_root
        )
        for item, search_row in zip(selected, search_rows, strict=True):
            reference_form = (
                search_row.get("pron_reference_form") or ""
            ).strip()
            lab_text = form_to_lab(reference_form)
            if not lab_text:
                raise RuntimeError(
                    f"{year} {item['utt_id']} pron_reference_form에서 "
                    "유효한 MFA 어절을 만들 수 없음"
                )
            item["pron_reference_form"] = reference_form
            item["pron_reference_source"] = search_row.get(
                "pron_reference_source", ""
            )
            item["pron_reference_status"] = search_row.get(
                "pron_reference_status", ""
            )
            item["lab_text"] = lab_text
            item["lab_source_field"] = "pron_reference_form"
            item["eojeol_map_json"] = json.dumps(
                form_to_lab_mapping(reference_form),
                ensure_ascii=False,
                separators=(",", ":"),
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
            session = str(item["session_id"])
            utt_id = str(item["utt_id"])
            wav_rel = Path("corpus") / year / session / f"{utt_id}.wav"
            lab_rel = Path("corpus") / year / session / f"{utt_id}.lab"
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
        frozen_search_sessions.extend(
            freeze_selected_search_sessions(
                run_root=run_root,
                year=year,
                fields=search_fields,
                selected=selected,
                rows=search_rows,
            )
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
        "schema_version": 3,
        "created_at": now_iso(),
        "purpose": (
            "연도별 실제 화자 층화 MFA r2 인프라 수용 파일럿; "
            "음운 실현 판정은 수행하지 않음"
        ),
        "years": years,
        "utterances_per_year": args.utterances_per_year,
        "speakers_per_year": args.speakers_per_year,
        "utterances_per_speaker": (
            args.utterances_per_year // args.speakers_per_year
        ),
        "distinct_sessions_per_year": args.speakers_per_year,
        "selection_seed": args.seed,
        "selection_policy": {
            "actual_speaker_id": True,
            "distinct_sessions": True,
            "session_wav_csv_duration_match_min_pct": 98.0,
            "utterance_duration_residual_tolerance_seconds": 0.025,
            "session_padding_allowed_seconds": [-0.025, 0.5],
        },
        "lab_contract": {
            "source_field": "pron_reference_form",
            "token_map_version": TOKEN_MAP_VERSION,
            "non_hangul_policy": (
                "exclude from MFA lab but preserve source-to-MFA mapping"
            ),
        },
        "run_root": str(run_root),
        "source_roots": {
            "bareun": str(args.raw_root.resolve()),
            "search_master": str(args.search_root.resolve()),
            "wav": str(args.wav_root.resolve()),
            "morpheme_textgrid": str(args.morph_root.resolve()),
        },
        "source_bareun_csv_fingerprints": source_fingerprints,
        "frozen_search_sessions": frozen_search_sessions,
        "runtime": runtime_snapshot(PROJECT_ROOT),
        "rows": len(all_rows),
        "status": "selection_complete",
    }
    atomic_write_json(run_root / "selection_manifest.json", payload)
    session_hash_payload = {
        "schema_version": "pilot_search_master_session_hashes.v1",
        "status": "success",
        "created_at": now_iso(),
        "token_map_version": TOKEN_MAP_VERSION,
        "files": frozen_search_sessions,
        "file_count": len(frozen_search_sessions),
        "row_count": sum(
            int(item["rows"]) for item in frozen_search_sessions
        ),
    }
    canonical = json.dumps(
        frozen_search_sessions,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    session_hash_payload["aggregate_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    atomic_write_json(
        run_root / "search_master" / "_session_hashes.json",
        session_hash_payload,
    )
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
