"""MFA SQLite DB에서 연구용 6-tier와 정규화 동반 CSV를 직접 생성한다.

원시 WAV, 동결 search master, MFA DB는 모두 읽기 전용이다. 출력은 연도별
TextGrid와 네 개의 gzip CSV로 구성한다. 510만 발화마다 작은 CSV 파일을
만들지 않고 ``utt_id``와 interval index로 논리적 1:1 대응을 보장한다.

``utterance_alignment.csv.gz``
    TextGrid 1개당 1행. 텍스트·화자·파일·정렬 요약과 계약 ID를 가진다.
``word_intervals_mfa.csv.gz``
    MFA word interval 1개당 1행. MFA에 실제 들어간
    ``pron_reference_form``과 원 형태소 분석의 ``form``을 구분한다.
``phone_intervals_mfa.csv.gz``
    MFA phone interval 1개당 1행. DB ``word_interval_id``로 word에 연결한다.
``excluded_utterances.csv.gz``
    input contract에 묶여 연구자가 승인한 제외를 사유·증거와 함께 전수 기록한다.

MFA phone과 ``phoneme_r_auto``는 실제 음운 실현 판정값이 아니다.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Mapping, Sequence

from build_mfa_alignment_contract import recompute_alignment_contract_id
from mfa_exclusion_contract import load_contract as load_exclusion_contract
from morph_schema import canonicalize_tagged, orth_roman_v2, tagged_roman_v2
from phoneme_roman import (
    ROMAN_SYSTEM_VERSION,
    SCHEMA_VERSION as PHONEME_SCHEMA_VERSION,
    classify_phone,
    load_acoustic_meta,
    model_group_lookup,
)
from pipeline_common import atomic_write_json, file_fingerprint
from realign_eojeol_build_corpus import (
    LAB_INPUT_VERSION,
    MISSING,
    TOKEN_MAP_VERSION,
    form_to_lab_mapping,
)
from research_companion_schema import (
    load_schema as load_companion_schema,
    schema_fingerprint as companion_schema_fingerprint,
    validate_field_order as validate_companion_field_order,
)
from research_textgrid_v2 import (
    BASE_TIERS,
    FLOAT32_BOUNDARY_MARGIN_SECONDS,
    MIN_BOUNDARY_ROUNDOFF_TOLERANCE_SECONDS,
    SCHEMA_VERSION as TEXTGRID_SCHEMA_VERSION,
    SILENCE,
    boundary_roundoff_tolerance,
    normalize_interval_bounds,
    validate_base_textgrid_from_intervals,
    write_base_textgrid_from_intervals,
)

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_VERSION = "mfa_research_6tier_export.v1"
TABLE_SCHEMA_VERSION = "mfa_research_companion_tables.v2"
SILENCE_WORDS = {"", "<eps>", "sil", "<unk>"}
REQUIRED_SEARCH_FIELDS = {
    "utt_id",
    "form",
    "form_roman",
    "tagged",
    "n_eojeol",
    "pron_reference_form",
    "pron_reference_n_eojeol",
}

Interval = tuple[float, float, str]
PhoneMapper = Callable[[str], str]

UTTERANCE_FIELDS = [
    "utt_id",
    "year",
    "session_id",
    "speaker_id",
    "dialogue_id",
    "dialogue_speaker_ids",
    "co_speaker_ids",
    "form",
    "original_form",
    "canonical_tagged",
    "form_roman",
    "form_roman_v2",
    "tagged_roman_v2",
    "pron_reference_form",
    "pron_reference_form_roman",
    "pron_pred_hangul",
    "pron_pred_roman",
    "pron_pred_ipa",
    "pron_reference_hangul",
    "pron_reference_roman",
    "pron_reference_ipa",
    "pron_reference_source",
    "pron_reference_status",
    "source_start_seconds",
    "source_end_seconds",
    "wav_duration_seconds",
    "source_wav_path",
    "source_lab_path",
    "textgrid_relative_path",
    "n_word_intervals",
    "n_phone_intervals",
    "n_source_eojeol",
    "n_reference_eojeol",
    "n_lab_words_expected",
    "n_mfa_words_aligned",
    "lab_word_count_match",
    "word_label_sequence_match",
    "reference_differs_from_form",
    "pron_mfa_ipa",
    "pron_mfa_r_auto",
    "n_spn",
    "alignment_score",
    "align_status",
    "alignment_contract_id",
    "textgrid_schema_version",
    "phoneme_schema_version",
    "roman_system_version",
]

WORD_FIELDS = [
    "utt_id",
    "year",
    "session_id",
    "word_interval_idx",
    "mfa_word_idx",
    "reference_eojeol_idx",
    "reference_eojeol",
    "lab_word_expected",
    "begin_seconds",
    "end_seconds",
    "duration_seconds",
    "word_mfa",
    "is_silence",
    "n_phones",
    "phone_link_status",
    "pron_mfa_ipa",
    "pron_mfa_r_auto",
    "mapping_status",
    "alignment_contract_id",
]

PHONE_FIELDS = [
    "utt_id",
    "year",
    "session_id",
    "phone_interval_idx",
    "phone_idx_in_word",
    "word_interval_idx",
    "mfa_word_idx",
    "reference_eojeol_idx",
    "begin_seconds",
    "end_seconds",
    "duration_seconds",
    "phone_mfa",
    "phoneme_r_auto",
    "is_silence",
    "word_mfa",
    "alignment_contract_id",
]

EXCLUDED_FIELDS = [
    "year",
    "utt_id",
    "input_contract_id",
    "alignment_contract_id",
    "reason_code",
    "exclusion_scope",
    "evidence_path",
    "decision",
    "notes",
    "db_presence",
    "alignment_presence",
    "textgrid_emitted",
]


def placeholders(count: int) -> str:
    if count <= 0:
        raise ValueError("SQL placeholder count는 양수여야 함")
    return ",".join("?" for _ in range(count))


def open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=120
    )


def count_spn_intervals(connection: sqlite3.Connection) -> int:
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


def load_alignment_contract(path: Path, year: str) -> tuple[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    contract_id = str(data.get("alignment_contract_id", "")).strip()
    if data.get("status") != "passed" or str(data.get("year")) != str(year):
        raise RuntimeError(f"alignment contract status/year 불일치: {path}")
    if not contract_id:
        raise RuntimeError(f"alignment_contract_id 누락: {path}")
    return contract_id, data


def load_session_rows(
    search_master_root: Path, year: str, session: str
) -> dict[str, dict[str, str]]:
    path = search_master_root / year / f"{session}.csv"
    if not path.is_file():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_SEARCH_FIELDS - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"{path}: 필수 열 누락 {sorted(missing)}")
        for row in reader:
            utt_id = str(row.get("utt_id", "")).strip()
            if not utt_id:
                raise RuntimeError(f"{path}: 빈 utt_id")
            if utt_id in rows:
                raise RuntimeError(f"{path}: 중복 utt_id {utt_id}")
            rows[utt_id] = row
    return rows


def load_active_lab_ids(lab_root: Path, year: str) -> set[str]:
    year_root = lab_root.resolve() / year
    if not year_root.is_dir():
        raise FileNotFoundError(year_root)
    ids: set[str] = set()
    duplicates: set[str] = set()
    for path in year_root.rglob("*.lab"):
        utt_id = path.stem
        if utt_id in ids:
            duplicates.add(utt_id)
        ids.add(utt_id)
    if duplicates:
        raise RuntimeError(
            f"active lab 중복 utt_id {len(duplicates)}건: "
            f"{sorted(duplicates)[:10]}"
        )
    if not ids:
        raise RuntimeError(f"active lab 0건: {year_root}")
    return ids


def load_search_master_ids(search_master_root: Path, year: str) -> set[str]:
    """Load the frozen pre-MFA source universe for exact ID reconciliation."""

    year_root = search_master_root.resolve() / year
    if not year_root.is_dir():
        raise FileNotFoundError(year_root)
    ids: set[str] = set()
    duplicates: set[str] = set()
    for path in sorted(year_root.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if "utt_id" not in set(reader.fieldnames or ()):
                raise RuntimeError(f"search master utt_id field missing: {path}")
            for row in reader:
                utt_id = str(row.get("utt_id", "") or "").strip()
                if not utt_id:
                    raise RuntimeError(f"search master blank utt_id: {path}")
                if utt_id in ids:
                    duplicates.add(utt_id)
                ids.add(utt_id)
    if duplicates:
        raise RuntimeError(
            "search master duplicate utt_id "
            f"{len(duplicates)}: {sorted(duplicates)[:10]}"
        )
    if not ids:
        raise RuntimeError(f"search master 0 rows: {year_root}")
    return ids


def load_quarantine_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    ids: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if "name" not in set(reader.fieldnames or ()):
            raise RuntimeError(f"quarantine log name 열 누락: {path}")
        for row in reader:
            name = str(row.get("name", "") or "").strip()
            if name:
                ids.add(Path(name).stem)
    return ids


def _db_inventory(
    connection: sqlite3.Connection,
) -> tuple[dict[int, str], dict[int, tuple[str, str]]]:
    words = {int(row[0]): str(row[1]) for row in connection.execute(
        "SELECT id, word FROM word"
    )}
    phones = {
        int(row[0]): (str(row[1]), str(row[2]))
        for row in connection.execute(
            "SELECT id, phone, phone_type FROM phone"
        )
    }
    return words, phones


def _sessions(connection: sqlite3.Connection) -> list[tuple[str, list[tuple]]]:
    grouped: dict[str, list[tuple]] = defaultdict(list)
    for row in connection.execute(
        """
        SELECT u.id, f.name, f.relative_path, sf.duration,
               sf.sound_file_path, u.alignment_score
        FROM utterance u
        JOIN file f ON f.id = u.file_id
        JOIN sound_file sf ON sf.file_id = f.id
        WHERE u.ignored = 0
        ORDER BY f.relative_path, f.name
        """
    ):
        uid, name, relative_path, duration, wav_path, alignment_score = row
        session = str(relative_path or str(name).split(".", 1)[0])
        grouped[session].append(
            (
                int(uid),
                str(name),
                float(duration),
                str(wav_path),
                alignment_score,
            )
        )
    return sorted(grouped.items())


def _session_intervals(
    connection: sqlite3.Connection,
    utterance_ids: Sequence[int],
    word_labels: Mapping[int, str],
    phone_labels: Mapping[int, tuple[str, str]],
) -> tuple[dict[int, list[tuple]], dict[int, list[tuple]]]:
    marks = placeholders(len(utterance_ids))
    words: dict[int, list[tuple]] = defaultdict(list)
    for row in connection.execute(
        "SELECT id, utterance_id, begin, end, word_id "
        f"FROM word_interval WHERE utterance_id IN ({marks}) "
        "ORDER BY utterance_id, begin, end, id",
        list(utterance_ids),
    ):
        interval_id, uid, begin, end, word_id = row
        label = word_labels.get(int(word_id), "")
        if label.strip().lower() in SILENCE_WORDS:
            label = ""
        words[int(uid)].append(
            (int(interval_id), float(begin), float(end), label)
        )
    phones: dict[int, list[tuple]] = defaultdict(list)
    for row in connection.execute(
        "SELECT id, utterance_id, begin, end, phone_id, word_interval_id "
        f"FROM phone_interval WHERE utterance_id IN ({marks}) "
        "ORDER BY utterance_id, begin, end, id",
        list(utterance_ids),
    ):
        interval_id, uid, begin, end, phone_id, word_interval_id = row
        label, phone_type = phone_labels.get(int(phone_id), ("", ""))
        if label.strip().lower() in SILENCE or phone_type == "silence":
            label = ""
        phones[int(uid)].append(
            (
                int(interval_id),
                float(begin),
                float(end),
                label,
                int(word_interval_id) if word_interval_id is not None else None,
            )
        )
    return words, phones


def _normalize_db_interval_rows(
    rows: Sequence[tuple], duration: float
) -> tuple[list[tuple], int, float]:
    """Normalize only DB float32 endpoint drift while preserving row shape."""

    normalized: list[tuple] = []
    adjusted_boundaries = 0
    max_adjustment = 0.0
    for row in rows:
        begin = float(row[1])
        end = float(row[2])
        fixed_begin, fixed_end = normalize_interval_bounds(
            begin, end, duration
        )
        for original, fixed in (
            (begin, fixed_begin),
            (end, fixed_end),
        ):
            difference = abs(original - fixed)
            if difference > 0:
                adjusted_boundaries += 1
                max_adjustment = max(max_adjustment, difference)
        normalized.append((row[0], fixed_begin, fixed_end, *row[3:]))
    return normalized, adjusted_boundaries, max_adjustment


def export_session_textgrids(
    *,
    db_path: Path,
    year: str,
    session: str,
    utterances: list[tuple],
    search_master_root: Path,
    output_root: Path,
    word_labels: Mapping[int, str],
    phone_labels: Mapping[int, tuple[str, str]],
    phone_mapper: PhoneMapper,
    alignment_exclusion_ids: set[str],
) -> dict[str, object]:
    connection = open_readonly(db_path)
    try:
        search_rows = load_session_rows(search_master_root, year, session)
        words_by_utt, phones_by_utt = _session_intervals(
            connection,
            [row[0] for row in utterances],
            word_labels,
            phone_labels,
        )
    finally:
        connection.close()

    counts: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    missing_search: list[str] = []
    missing_alignment: list[str] = []
    approved_excluded: list[str] = []
    roundoff_examples: list[dict[str, object]] = []
    max_boundary_roundoff_seconds = 0.0
    output_dir = output_root / year / session
    output_dir.mkdir(parents=True, exist_ok=True)
    for uid, utt_id, duration, _wav_path, _score in utterances:
        if utt_id in alignment_exclusion_ids:
            counts["approved_excluded"] += 1
            approved_excluded.append(utt_id)
            continue
        row = search_rows.get(utt_id)
        if row is None:
            counts["search_row_missing"] += 1
            missing_search.append(utt_id)
            continue
        word_rows = words_by_utt.get(uid, [])
        phone_rows = phones_by_utt.get(uid, [])
        if not word_rows or not phone_rows:
            counts["alignment_missing"] += 1
            missing_alignment.append(utt_id)
            continue
        destination = output_dir / f"{utt_id}.TextGrid"
        try:
            word_rows, word_adjustments, word_max = (
                _normalize_db_interval_rows(word_rows, duration)
            )
            phone_rows, phone_adjustments, phone_max = (
                _normalize_db_interval_rows(phone_rows, duration)
            )
            words = [
                (begin, end, label)
                for _iid, begin, end, label in word_rows
            ]
            phones = [
                (begin, end, label)
                for _iid, begin, end, label, _wid in phone_rows
            ]
            boundary_adjustments = word_adjustments + phone_adjustments
            utterance_max_adjustment = max(word_max, phone_max)
            if destination.is_file():
                validation = validate_base_textgrid_from_intervals(
                    destination,
                    duration=duration,
                    words=words,
                    phones=phones,
                    row=row,
                    phone_mapper=phone_mapper,
                )
                if validation["valid"]:
                    counts["validated_existing"] += 1
                else:
                    raise RuntimeError(
                        "기존 6-tier 검증 실패: "
                        + "; ".join(validation["reasons"])
                    )
            else:
                validation = write_base_textgrid_from_intervals(
                    destination,
                    duration=duration,
                    words=words,
                    phones=phones,
                    row=row,
                    phone_mapper=phone_mapper,
                )
                counts["created"] += 1
            if validation.get("word_span_fallback"):
                counts["word_span_fallback"] += 1
            if boundary_adjustments:
                counts["float32_boundary_adjustments"] += boundary_adjustments
                counts["utterances_float32_boundary_adjusted"] += 1
                max_boundary_roundoff_seconds = max(
                    max_boundary_roundoff_seconds,
                    utterance_max_adjustment,
                )
                if len(roundoff_examples) < 100:
                    roundoff_examples.append(
                        {
                            "utt_id": utt_id,
                            "adjusted_boundaries": boundary_adjustments,
                            "max_adjustment_seconds": (
                                utterance_max_adjustment
                            ),
                            "allowed_tolerance_seconds": (
                                boundary_roundoff_tolerance(duration)
                            ),
                        }
                    )
        except Exception as exc:
            counts["failed"] += 1
            if len(failures) < 100:
                failures.append(
                    {"utt_id": utt_id, "error": f"{type(exc).__name__}: {exc}"}
                )
    return {
        "counts": dict(counts),
        "failed_examples": failures,
        "search_row_missing_inventory": missing_search,
        "alignment_missing_inventory": missing_alignment,
        "approved_excluded_inventory": approved_excluded,
        "roundoff_examples": roundoff_examples,
        "max_boundary_roundoff_seconds": max_boundary_roundoff_seconds,
    }


def _format_seconds(value: object) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):.6f}"


def _csv_bool(value: object) -> str:
    """동반표 bool의 대소문자·언어 의존성을 없앤다."""

    return "true" if bool(value) else "false"


def _atomic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.{os.getpid()}.partial")
    raw = partial.open("wb")
    compressed = gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=raw,
        compresslevel=3,
        mtime=0,
    )
    stream = io.TextIOWrapper(
        compressed, encoding="utf-8-sig", newline=""
    )
    writer = csv.DictWriter(
        stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    return stream, writer, partial, raw


def _archive_stale_table_partials(
    output_root: Path, year: str, table_root: Path
) -> list[str]:
    """실패한 이전 시도의 table partial을 삭제하지 않고 분리한다."""

    stale = sorted(table_root.glob(".*.partial")) if table_root.is_dir() else []
    if not stale:
        return []
    archive_root = (
        output_root
        / "_failed_table_partials"
        / str(year)
        / f"{time.time_ns()}_{os.getpid()}"
    )
    archive_root.mkdir(parents=True, exist_ok=False)
    archived: list[str] = []
    for path in stale:
        destination = archive_root / path.name
        os.replace(path, destination)
        archived.append(str(destination.relative_to(output_root)))
    return archived


def _reference_form(search: Mapping[str, str]) -> str:
    form = str(search.get("form", "") or "").strip()
    reference = str(search.get("pron_reference_form", "") or "").strip()
    return form if reference in MISSING else reference


def _reference_word_map(search: Mapping[str, str]) -> list[dict[str, object]]:
    """MFA .lab에 쓴 참조 표기와 MFA word 위치를 재생성한다.

    ``form``은 형태소·철자 검색의 원본이고
    ``pron_reference_form``은 숫자 읽기 복원 등을 반영한 MFA 입력이다.
    둘의 어절 위치가 항상 같다고 간주하지 않는다.
    """

    reference = _reference_form(search)
    result: list[dict[str, object]] = []
    for row in form_to_lab_mapping(reference):
        if not row["included_in_mfa"]:
            continue
        result.append(
            {
                "mfa_word_idx": int(row["mfa_word_index"]) + 1,
                "reference_eojeol_idx": int(row["source_eojeol_index"]) + 1,
                "reference_eojeol": str(row["source_token"]),
                "lab_word_expected": str(row["lab_token"]),
            }
        )
    return result


def write_companion_tables(
    *,
    db_path: Path,
    year: str,
    sessions: list[tuple[str, list[tuple]]],
    search_master_root: Path,
    output_root: Path,
    word_labels: Mapping[int, str],
    phone_labels: Mapping[int, tuple[str, str]],
    phone_mapper: PhoneMapper,
    alignment_contract_id: str,
    input_contract_id: str,
    approved_exclusions: Mapping[str, Mapping[str, str]],
    exclusion_contract_fingerprint: Mapping[str, object] | None,
    companion_schema_path: Path,
    companion_schema: Mapping[str, object],
) -> dict[str, object]:
    table_root = output_root / year / "_tables"
    archived_stale_partials = _archive_stale_table_partials(
        output_root, year, table_root
    )
    destinations = {
        "utterances": table_root / "utterance_alignment.csv.gz",
        "words": table_root / "word_intervals_mfa.csv.gz",
        "phones": table_root / "phone_intervals_mfa.csv.gz",
        "excluded": table_root / "excluded_utterances.csv.gz",
    }
    opened = {
        "utterances": _atomic_gzip_writer(destinations["utterances"], UTTERANCE_FIELDS),
        "words": _atomic_gzip_writer(destinations["words"], WORD_FIELDS),
        "phones": _atomic_gzip_writer(destinations["phones"], PHONE_FIELDS),
        "excluded": _atomic_gzip_writer(
            destinations["excluded"], EXCLUDED_FIELDS
        ),
    }
    counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    excluded_written: set[str] = set()
    connection = open_readonly(db_path)
    try:
        for session_index, (session, utterances) in enumerate(sessions, 1):
            search_rows = load_session_rows(search_master_root, year, session)
            words_by_utt, phones_by_utt = _session_intervals(
                connection,
                [row[0] for row in utterances],
                word_labels,
                phone_labels,
            )
            for uid, utt_id, duration, wav_path, score in utterances:
                search = search_rows.get(utt_id)
                if search is None:
                    errors.append({"utt_id": utt_id, "error": "search_row_missing"})
                    continue
                word_rows = words_by_utt.get(uid, [])
                phone_rows = phones_by_utt.get(uid, [])
                exclusion = approved_exclusions.get(utt_id)
                alignment_excluded = bool(
                    exclusion
                    and exclusion.get("exclusion_scope")
                    == "alignment_and_analysis"
                )
                alignment_present = bool(word_rows and phone_rows)
                if alignment_excluded:
                    opened["excluded"][1].writerow(
                        {
                            "year": year,
                            "utt_id": utt_id,
                            "input_contract_id": input_contract_id,
                            "alignment_contract_id": alignment_contract_id,
                            "reason_code": exclusion.get("reason_code", ""),
                            "exclusion_scope": exclusion.get(
                                "exclusion_scope", ""
                            ),
                            "evidence_path": exclusion.get(
                                "evidence_path", ""
                            ),
                            "decision": exclusion.get("decision", ""),
                            "notes": exclusion.get("notes", ""),
                            "db_presence": "true",
                            "alignment_presence": _csv_bool(
                                alignment_present
                            ),
                            "textgrid_emitted": "false",
                        }
                    )
                    excluded_written.add(utt_id)
                    counts["excluded_utterances"] += 1
                    continue
                word_rows, _word_adjustments, _word_max = (
                    _normalize_db_interval_rows(word_rows, duration)
                )
                phone_rows, _phone_adjustments, _phone_max = (
                    _normalize_db_interval_rows(phone_rows, duration)
                )
                phone_by_word: dict[int | None, list[tuple]] = defaultdict(list)
                for phone_row in phone_rows:
                    phone_by_word[phone_row[4]].append(phone_row)

                reference_words = _reference_word_map(search)
                reference_by_mfa_idx = {
                    int(item["mfa_word_idx"]): item for item in reference_words
                }
                word_meta: dict[int, dict[str, object]] = {}
                word_output_rows: list[dict[str, object]] = []
                mfa_word_idx = 0
                observed_word_labels: list[str] = []
                utterance_pron_ipa: list[str] = []
                utterance_pron_r: list[str] = []
                for word_index, (word_id, begin, end, word_label) in enumerate(
                    word_rows, 1
                ):
                    is_silence = not word_label.strip()
                    if not is_silence:
                        mfa_word_idx += 1
                        mfa_word_value: int | str = mfa_word_idx
                        observed_word_labels.append(word_label)
                        reference_meta = reference_by_mfa_idx.get(
                            mfa_word_idx, {}
                        )
                    else:
                        mfa_word_value = ""
                        reference_meta = {}
                    linked = phone_by_word.get(word_id, [])
                    ipa_tokens = [row[3] for row in linked if row[3].strip()]
                    roman_tokens = [phone_mapper(phone) for phone in ipa_tokens]
                    pron_ipa = " ".join(ipa_tokens)
                    pron_r = " ".join(roman_tokens)
                    if not is_silence:
                        utterance_pron_ipa.append(pron_ipa)
                        utterance_pron_r.append(pron_r)
                        if not linked:
                            counts["words_without_linked_phone"] += 1
                    expected_label = str(
                        reference_meta.get("lab_word_expected", "")
                    )
                    if is_silence:
                        mapping_status = "silence"
                    elif not reference_meta:
                        mapping_status = "no_reference_map"
                    elif word_label == expected_label:
                        mapping_status = "matched_reference_lab"
                    else:
                        mapping_status = "label_mismatch"
                    word_meta[word_id] = {
                        "word_interval_idx": word_index,
                        "word_mfa": word_label,
                        "mfa_word_idx": mfa_word_value,
                        "reference_eojeol_idx": reference_meta.get(
                            "reference_eojeol_idx", ""
                        ),
                    }
                    word_output_rows.append(
                        {
                            "utt_id": utt_id,
                            "year": year,
                            "session_id": session,
                            "word_interval_idx": word_index,
                            "mfa_word_idx": mfa_word_value,
                            "reference_eojeol_idx": reference_meta.get(
                                "reference_eojeol_idx", ""
                            ),
                            "reference_eojeol": reference_meta.get(
                                "reference_eojeol", ""
                            ),
                            "lab_word_expected": expected_label,
                            "begin_seconds": _format_seconds(begin),
                            "end_seconds": _format_seconds(end),
                            "duration_seconds": _format_seconds(end - begin),
                            "word_mfa": word_label,
                            "is_silence": _csv_bool(is_silence),
                            "n_phones": len(linked),
                            "phone_link_status": (
                                "linked_by_word_interval_id"
                                if linked else (
                                    "silence_without_phone"
                                    if is_silence else "no_linked_phone"
                                )
                            ),
                            "pron_mfa_ipa": pron_ipa,
                            "pron_mfa_r_auto": pron_r,
                            "mapping_status": mapping_status,
                            "alignment_contract_id": alignment_contract_id,
                        }
                    )
                for row in word_output_rows:
                    opened["words"][1].writerow(row)
                    counts["word_intervals"] += 1

                phone_idx_by_word: Counter[int | None] = Counter()
                for phone_index, (
                    _phone_id,
                    begin,
                    end,
                    phone_label,
                    word_interval_id,
                ) in enumerate(phone_rows, 1):
                    phone_idx_by_word[word_interval_id] += 1
                    linked_meta = word_meta.get(word_interval_id)
                    word_index = (
                        linked_meta["word_interval_idx"] if linked_meta else ""
                    )
                    word_label = linked_meta["word_mfa"] if linked_meta else ""
                    phone_mfa_word_idx = (
                        linked_meta["mfa_word_idx"] if linked_meta else ""
                    )
                    phone_reference_eojeol_idx = (
                        linked_meta["reference_eojeol_idx"]
                        if linked_meta else ""
                    )
                    is_silence = not phone_label.strip()
                    opened["phones"][1].writerow(
                        {
                            "utt_id": utt_id,
                            "year": year,
                            "session_id": session,
                            "phone_interval_idx": phone_index,
                            "phone_idx_in_word": phone_idx_by_word[word_interval_id],
                            "word_interval_idx": word_index,
                            "mfa_word_idx": phone_mfa_word_idx,
                            "reference_eojeol_idx": (
                                phone_reference_eojeol_idx
                            ),
                            "begin_seconds": _format_seconds(begin),
                            "end_seconds": _format_seconds(end),
                            "duration_seconds": _format_seconds(end - begin),
                            "phone_mfa": phone_label,
                            "phoneme_r_auto": (
                                "" if is_silence else phone_mapper(phone_label)
                            ),
                            "is_silence": _csv_bool(is_silence),
                            "word_mfa": word_label,
                            "alignment_contract_id": alignment_contract_id,
                        }
                    )
                    counts["phone_intervals"] += 1
                    if not is_silence and linked_meta is None:
                        counts["unlinked_nonsilence_phones"] += 1

                source_eojeols = str(search.get("n_eojeol", "") or "").strip()
                source_eojeol_count: int | str = (
                    int(source_eojeols) if source_eojeols.isdigit() else ""
                )
                reference_form = _reference_form(search)
                reference_eojeols = str(
                    search.get("pron_reference_n_eojeol", "") or ""
                ).strip()
                reference_eojeol_count: int | str = (
                    int(reference_eojeols)
                    if reference_eojeols.isdigit()
                    else len(reference_form.split())
                )
                expected_lab_labels = [
                    str(item["lab_word_expected"]) for item in reference_words
                ]
                label_sequence_match = observed_word_labels == expected_lab_labels
                utterance_spn = sum(
                    str(phone_row[3]).strip().lower() == "spn"
                    for phone_row in phone_rows
                )
                source_wav = Path(wav_path)
                opened["utterances"][1].writerow(
                    {
                        "utt_id": utt_id,
                        "year": year,
                        "session_id": session,
                        "speaker_id": search.get("speaker_id", ""),
                        "dialogue_id": search.get("dialogue_id", ""),
                        "dialogue_speaker_ids": search.get("dialogue_speaker_ids", ""),
                        "co_speaker_ids": search.get("co_speaker_ids", ""),
                        "form": search.get("form", ""),
                        "original_form": search.get("original_form", ""),
                        "canonical_tagged": canonicalize_tagged(search["tagged"]),
                        "form_roman": search.get("form_roman", ""),
                        "form_roman_v2": orth_roman_v2(
                            str(search.get("form", ""))
                        ),
                        "tagged_roman_v2": tagged_roman_v2(search["tagged"]),
                        "pron_reference_form": search.get("pron_reference_form", ""),
                        "pron_reference_form_roman": search.get(
                            "pron_reference_form_roman", ""
                        ),
                        "pron_pred_hangul": search.get("pron_pred_hangul", ""),
                        "pron_pred_roman": search.get("pron_pred_roman", ""),
                        "pron_pred_ipa": search.get("pron_pred_ipa", ""),
                        "pron_reference_hangul": search.get("pron_reference_hangul", ""),
                        "pron_reference_roman": search.get("pron_reference_roman", ""),
                        "pron_reference_ipa": search.get("pron_reference_ipa", ""),
                        "pron_reference_source": search.get("pron_reference_source", ""),
                        "pron_reference_status": search.get("pron_reference_status", ""),
                        "source_start_seconds": search.get("start", ""),
                        "source_end_seconds": search.get("end", ""),
                        "wav_duration_seconds": _format_seconds(duration),
                        "source_wav_path": str(source_wav),
                        "source_lab_path": str(source_wav.with_suffix(".lab")),
                        "textgrid_relative_path": (
                            Path(year) / session / f"{utt_id}.TextGrid"
                        ).as_posix(),
                        "n_word_intervals": len(word_rows),
                        "n_phone_intervals": len(phone_rows),
                        "n_source_eojeol": source_eojeol_count,
                        "n_reference_eojeol": reference_eojeol_count,
                        "n_lab_words_expected": len(reference_words),
                        "n_mfa_words_aligned": mfa_word_idx,
                        "lab_word_count_match": _csv_bool(
                            mfa_word_idx == len(reference_words)
                        ),
                        "word_label_sequence_match": _csv_bool(
                            label_sequence_match
                        ),
                        "reference_differs_from_form": _csv_bool(
                            reference_form
                            != str(search.get("form", "")).strip()
                        ),
                        "pron_mfa_ipa": " | ".join(utterance_pron_ipa),
                        "pron_mfa_r_auto": " | ".join(utterance_pron_r),
                        "n_spn": utterance_spn,
                        "alignment_score": "" if score is None else score,
                        "align_status": (
                            "aligned_excluded_approved"
                            if exclusion
                            and exclusion.get("exclusion_scope")
                            == "analysis_only"
                            else "aligned"
                        ),
                        "alignment_contract_id": alignment_contract_id,
                        "textgrid_schema_version": TEXTGRID_SCHEMA_VERSION,
                        "phoneme_schema_version": PHONEME_SCHEMA_VERSION,
                        "roman_system_version": ROMAN_SYSTEM_VERSION,
                    }
                )
                counts["utterances"] += 1
                if (
                    exclusion
                    and exclusion.get("exclusion_scope") == "analysis_only"
                ):
                    opened["excluded"][1].writerow(
                        {
                            "year": year,
                            "utt_id": utt_id,
                            "input_contract_id": input_contract_id,
                            "alignment_contract_id": alignment_contract_id,
                            "reason_code": exclusion.get("reason_code", ""),
                            "exclusion_scope": exclusion.get(
                                "exclusion_scope", ""
                            ),
                            "evidence_path": exclusion.get(
                                "evidence_path", ""
                            ),
                            "decision": exclusion.get("decision", ""),
                            "notes": exclusion.get("notes", ""),
                            "db_presence": "true",
                            "alignment_presence": "true",
                            "textgrid_emitted": "true",
                        }
                    )
                    excluded_written.add(utt_id)
                    counts["excluded_utterances"] += 1
                if mfa_word_idx != len(reference_words):
                    counts["lab_word_count_mismatch"] += 1
                    if len(errors) < 100:
                        errors.append(
                            {
                                "utt_id": utt_id,
                                "error": "lab_word_count_mismatch",
                                "expected": str(len(reference_words)),
                                "actual": str(mfa_word_idx),
                            }
                        )
                if not label_sequence_match:
                    counts["word_label_sequence_mismatch"] += 1
                    if len(errors) < 100:
                        errors.append(
                            {
                                "utt_id": utt_id,
                                "error": "word_label_sequence_mismatch",
                                "expected": " | ".join(expected_lab_labels),
                                "actual": " | ".join(observed_word_labels),
                            }
                        )
            if session_index % 100 == 0 or session_index == len(sessions):
                print(
                    f"[{year}] companion tables {session_index:,}/{len(sessions):,} "
                    f"sessions · utterances={counts['utterances']:,}",
                    flush=True,
                )
        for utt_id, exclusion in sorted(approved_exclusions.items()):
            if utt_id in excluded_written:
                continue
            if exclusion.get("exclusion_scope") != "alignment_and_analysis":
                errors.append(
                    {
                        "utt_id": utt_id,
                        "error": "analysis_only_exclusion_not_in_database",
                    }
                )
                continue
            opened["excluded"][1].writerow(
                {
                    "year": year,
                    "utt_id": utt_id,
                    "input_contract_id": input_contract_id,
                    "alignment_contract_id": alignment_contract_id,
                    "reason_code": exclusion.get("reason_code", ""),
                    "exclusion_scope": exclusion.get("exclusion_scope", ""),
                    "evidence_path": exclusion.get("evidence_path", ""),
                    "decision": exclusion.get("decision", ""),
                    "notes": exclusion.get("notes", ""),
                    "db_presence": "false",
                    "alignment_presence": "false",
                    "textgrid_emitted": "false",
                }
            )
            excluded_written.add(utt_id)
            counts["excluded_utterances"] += 1
    finally:
        connection.close()
        for _name, (stream, _writer, _partial, raw) in opened.items():
            if not stream.closed:
                stream.flush()
                stream.close()
            if not raw.closed:
                raw.flush()
                os.fsync(raw.fileno())
                raw.close()

    if errors:
        raise RuntimeError(
            f"동반표 계약 불일치 {len(errors)}건: {errors[:3]}"
        )
    if counts["words_without_linked_phone"]:
        raise RuntimeError(
            "phone이 연결되지 않은 유표 word: "
            f"{counts['words_without_linked_phone']}"
        )
    if counts["unlinked_nonsilence_phones"]:
        raise RuntimeError(
            "word_interval_id 없는 유표 phone: "
            f"{counts['unlinked_nonsilence_phones']}"
        )
    if counts["lab_word_count_mismatch"]:
        raise RuntimeError(
            "MFA 유표 word와 재생성한 lab word 수 불일치: "
            f"{counts['lab_word_count_mismatch']}"
        )
    if counts["word_label_sequence_mismatch"]:
        raise RuntimeError(
            "MFA word label과 재생성한 lab word 순서 불일치: "
            f"{counts['word_label_sequence_mismatch']}"
        )

    # 모든 연결·개수·label gate를 통과한 뒤에만 최종 파일명으로
    # 승격한다. 실패 시 .partial은 조사 근거로 남고, 완성본은 없다.
    for name, (_stream, _writer, partial, _raw) in opened.items():
        os.replace(partial, destinations[name])
    manifest = {
        "schema_version": TABLE_SCHEMA_VERSION,
        "status": "success",
        "year": year,
        "input_contract_id": input_contract_id,
        "alignment_contract_id": alignment_contract_id,
        "textgrid_schema_version": TEXTGRID_SCHEMA_VERSION,
        "phoneme_schema_version": PHONEME_SCHEMA_VERSION,
        "roman_system_version": ROMAN_SYSTEM_VERSION,
        "lab_input_version": LAB_INPUT_VERSION,
        "token_map_version": TOKEN_MAP_VERSION,
        "index_base": 1,
        "position_contract": (
            "source eojeol (form/tagged) and MFA reference eojeol "
            "(pron_reference_form) are separate domains"
        ),
        "archived_stale_partials": archived_stale_partials,
        "logical_sidecar_policy": (
            "annual compressed normalized tables keyed by utt_id; "
            "per-utterance CSV only in selected candidate bundles"
        ),
        "approved_exclusions_contract": exclusion_contract_fingerprint,
        "column_schema": companion_schema_fingerprint(
            companion_schema_path
        ),
        "csv_contract": companion_schema.get("csv"),
        "compression_contract": companion_schema.get("compression"),
        "tables": {
            name: {
                **file_fingerprint(path, with_sha256=True),
                # 연도 폴더가 partial root에서 final staging으로 이동해도
                # manifest가 깨지지 않도록 table-root 상대경로만 기록한다.
                "path": path.name,
            }
            for name, path in destinations.items()
        },
        "counts": dict(sorted(counts.items())),
    }
    atomic_write_json(table_root / "TABLES_MANIFEST.json", manifest)
    return manifest


def _resolved_path_equal(left: object, right: Path) -> bool:
    try:
        return os.path.normcase(str(Path(str(left)).resolve())) == os.path.normcase(
            str(right.resolve())
        )
    except (OSError, TypeError, ValueError):
        return False


def _fingerprint_matches(path: Path, expected: Mapping[str, object]) -> bool:
    if not path.is_file():
        return False
    observed = file_fingerprint(path, with_sha256=True)
    return (
        int(observed["bytes"]) == int(expected.get("bytes", -1))
        and str(observed["sha256"]) == str(expected.get("sha256", ""))
    )


def _alignment_contract_semantically_matches(
    path: Path,
    expected_file: Mapping[str, object],
    *,
    year: str,
    input_contract_id: str,
    alignment_contract_id: str,
) -> bool:
    """Validate the builder's canonical identity, not volatile audit time.

    The alignment contract writer records ``recorded_at`` for provenance.
    That value is intentionally excluded from ``alignment_contract_id`` and
    may change when an otherwise identical checkpoint is reconstructed.
    """

    if not path.is_file() or not _resolved_path_equal(
        expected_file.get("path"), path
    ):
        return False
    try:
        contract = json.loads(path.read_text(encoding="utf-8-sig"))
        return (
            contract.get("schema_version") == "mfa_alignment_contract.v1"
            and contract.get("status") == "passed"
            and str(contract.get("year")) == year
            and str(contract.get("lab_input_contract_id", ""))
            == input_contract_id
            and str(contract.get("alignment_contract_id", ""))
            == alignment_contract_id
            and recompute_alignment_contract_id(contract)
            == alignment_contract_id
        )
    except (OSError, ValueError, TypeError, RuntimeError):
        return False


def load_targeted_repair_resume(
    *,
    failed_report_path: Path,
    repair_manifest_path: Path,
    db_path: Path,
    year: str,
    search_master_root: Path,
    output_root: Path,
    acoustic_model: Path,
    alignment_contract: Path,
    alignment_contract_id: str,
    input_contract_id: str,
    reconciliation: Mapping[str, object],
    source_utterance_count: int,
) -> tuple[Counter[str], list[dict[str, object]], float, dict[str, object]]:
    """Load a failed full-pass checkpoint plus an exact targeted repair.

    This deliberately cannot resume from a truncated or ambiguous failure
    inventory.  The prior pass must have accounted for the full database,
    every failure must have a separately archived and validated repair, and
    all frozen identities must still match the current invocation.
    """

    failed_report_path = failed_report_path.resolve()
    repair_manifest_path = repair_manifest_path.resolve()
    if not failed_report_path.is_file():
        raise FileNotFoundError(failed_report_path)
    if not repair_manifest_path.is_file():
        raise FileNotFoundError(repair_manifest_path)
    previous = json.loads(failed_report_path.read_text(encoding="utf-8-sig"))
    repair = json.loads(repair_manifest_path.read_text(encoding="utf-8-sig"))
    if previous.get("status") != "failed":
        raise RuntimeError("resume source report is not a failed checkpoint")
    if repair.get("status") != "success":
        raise RuntimeError("targeted repair manifest is not successful")
    identity_checks = {
        "year": str(previous.get("year")) == year
        and str(repair.get("year")) == year,
        "db_path": _resolved_path_equal(previous.get("db_path"), db_path)
        and _resolved_path_equal(repair.get("db_path"), db_path),
        "search_master_root": _resolved_path_equal(
            previous.get("search_master_root"), search_master_root
        ),
        "output_root": _resolved_path_equal(
            previous.get("output_root"), output_root
        )
        and _resolved_path_equal(repair.get("output_root"), output_root),
        "alignment_contract_id": str(
            previous.get("alignment_contract_id", "")
        )
        == alignment_contract_id
        and str(repair.get("alignment_contract_id", ""))
        == alignment_contract_id,
        "input_contract_id": str(previous.get("input_contract_id", ""))
        == input_contract_id
        and str(repair.get("input_contract_id", "")) == input_contract_id,
    }
    failed_contract = previous.get("alignment_contract") or {}
    failed_acoustic = previous.get("acoustic_model") or {}
    identity_checks["alignment_contract_semantic_identity"] = (
        _alignment_contract_semantically_matches(
            alignment_contract,
            failed_contract,
            year=year,
            input_contract_id=input_contract_id,
            alignment_contract_id=alignment_contract_id,
        )
    )
    identity_checks["acoustic_model_file"] = _fingerprint_matches(
        acoustic_model, failed_acoustic
    )
    source_fingerprint = repair.get("source_failed_report") or {}
    identity_checks["source_failed_report"] = _fingerprint_matches(
        failed_report_path, source_fingerprint
    )
    if not all(identity_checks.values()):
        failed = sorted(name for name, passed in identity_checks.items() if not passed)
        raise RuntimeError("targeted repair resume identity mismatch: " + ", ".join(failed))

    previous_reconciliation = previous.get("exact_id_reconciliation") or {}
    if (
        previous_reconciliation.get("status") != "passed"
        or not previous_reconciliation.get("full_year_gate")
        or previous_reconciliation.get("counts") != reconciliation.get("counts")
        or previous_reconciliation.get("inventories")
        != reconciliation.get("inventories")
    ):
        raise RuntimeError("prior/current exact ID reconciliation mismatch")

    counts = previous.get("counts") or {}
    failed_count = int(counts.get("failed", 0))
    failed_examples = list(previous.get("failed_examples") or [])
    failed_ids = [str(row.get("utt_id", "")).strip() for row in failed_examples]
    if (
        failed_count <= 0
        or failed_count != len(failed_examples)
        or any(not utt_id for utt_id in failed_ids)
        or len(set(failed_ids)) != failed_count
    ):
        raise RuntimeError("failed checkpoint inventory is incomplete or ambiguous")
    for forbidden in (
        "alignment_missing",
        "search_row_missing",
        "word_span_fallback",
        "spn_intervals",
    ):
        if int(counts.get(forbidden, 0)):
            raise RuntimeError(f"resume checkpoint contains non-repair failure: {forbidden}")
    if (
        int(counts.get("source_utterances", -1)) != source_utterance_count
        or int(previous.get("accounted", -1)) != source_utterance_count
    ):
        raise RuntimeError("resume checkpoint did not account for the full database")

    repaired_ids = [str(value) for value in repair.get("repaired_ids") or []]
    records = list(repair.get("records") or [])
    if (
        int(repair.get("repaired_count", -1)) != failed_count
        or len(records) != failed_count
        or set(repaired_ids) != set(failed_ids)
        or len(repaired_ids) != len(set(repaired_ids))
    ):
        raise RuntimeError("repair manifest does not exactly cover prior failures")
    observed_record_ids: set[str] = set()
    for record in records:
        utt_id = str(record.get("utt_id", "")).strip()
        destination = Path(str(record.get("destination", ""))).resolve()
        try:
            destination.relative_to((output_root / year).resolve())
        except ValueError as exc:
            raise RuntimeError(f"repair destination outside year root: {destination}") from exc
        if (
            not utt_id
            or utt_id in observed_record_ids
            or not bool(record.get("matches_pre_normalization_policy"))
            or not bool(record.get("replacement_validation_passed"))
            or not _fingerprint_matches(
                destination, record.get("destination_after") or {}
            )
            or not _fingerprint_matches(
                Path(str(record.get("archive_path", ""))).resolve(),
                record.get("archive_fingerprint") or {},
            )
        ):
            raise RuntimeError(f"invalid targeted repair evidence: {utt_id or destination}")
        observed_record_ids.add(utt_id)
    if observed_record_ids != set(failed_ids):
        raise RuntimeError("repair record IDs differ from failed checkpoint IDs")

    totals = Counter(
        {
            key: int(value)
            for key, value in counts.items()
            if isinstance(value, (int, float)) and float(value).is_integer()
        }
    )
    prior_validated = int(totals["validated_existing"])
    prior_created = int(totals["created"])
    totals["validated_existing"] += failed_count
    totals["failed"] = 0
    totals["targeted_repaired_existing"] = failed_count
    totals["resume_checkpoint_files_reused"] = prior_validated + prior_created
    float32 = previous.get("float32_boundary_normalization") or {}
    examples = list(float32.get("examples") or [])
    max_adjustment = float(float32.get("max_adjustment_seconds", 0.0))
    resume = {
        "mode": "failed_full_pass_plus_exact_targeted_repair",
        "source_failed_report": file_fingerprint(
            failed_report_path, with_sha256=True
        ),
        "targeted_repair_manifest": file_fingerprint(
            repair_manifest_path, with_sha256=True
        ),
        "prior_validated_existing": prior_validated,
        "prior_created": prior_created,
        "prior_failed": failed_count,
        "repaired_ids": sorted(failed_ids),
        "alignment_contract_validation": {
            "mode": "recomputed_builder_canonical_identity",
            "prior_file_fingerprint": failed_contract,
            "current_file_fingerprint": file_fingerprint(
                alignment_contract, with_sha256=True
            ),
            "recomputed_contract_id": alignment_contract_id,
            "volatile_recorded_at_ignored": True,
        },
        "full_textgrid_revalidation_deferred_to_independent_year_audit": True,
    }
    return totals, examples, max_adjustment, resume


def export_database(
    *,
    db_path: Path,
    year: str,
    search_master_root: Path,
    output_root: Path,
    acoustic_model: Path,
    alignment_contract: Path,
    approved_exclusions_contract: Path | None = None,
    lab_root: Path | None = None,
    quarantine_log: Path | None = None,
    workers: int = 4,
    limit_sessions: int = 0,
) -> dict[str, object]:
    started = time.monotonic()
    db_path = db_path.resolve()
    search_master_root = search_master_root.resolve()
    output_root = output_root.resolve()
    acoustic_model = acoustic_model.resolve()
    alignment_contract = alignment_contract.resolve()
    companion_schema_path, companion_schema = load_companion_schema()
    validate_companion_field_order(
        companion_schema,
        {
            "utterances": UTTERANCE_FIELDS,
            "words": WORD_FIELDS,
            "phones": PHONE_FIELDS,
            "excluded": EXCLUDED_FIELDS,
        },
    )
    contract_id, contract_data = load_alignment_contract(
        alignment_contract, year
    )
    input_contract_id = str(
        contract_data.get("lab_input_contract_id", "") or ""
    ).strip()
    exclusion_contract_data: dict[str, object] | None = None
    approved_exclusions: dict[str, dict[str, str]] = {}
    if approved_exclusions_contract is not None:
        if not input_contract_id:
            raise RuntimeError(
                "approved exclusions 사용에는 lab_input_contract_id가 필요함"
            )
        exclusion_contract_data, approved_exclusions = load_exclusion_contract(
            approved_exclusions_contract,
            year=year,
            input_contract_id=input_contract_id,
        )
    alignment_exclusion_ids = {
        utt_id
        for utt_id, row in approved_exclusions.items()
        if row["exclusion_scope"] == "alignment_and_analysis"
    }
    analysis_only_ids = set(approved_exclusions) - alignment_exclusion_ids
    quarantine_ids = load_quarantine_ids(quarantine_log)
    groups = model_group_lookup(load_acoustic_meta(acoustic_model))

    def phone_mapper(phone: str) -> str:
        return classify_phone(phone, groups).phone_class_r_auto

    connection = open_readonly(db_path)
    try:
        spn_intervals = count_spn_intervals(connection)
        if spn_intervals:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "failed",
                "analysis_ready_status": "blocked_spn_intervals",
                "year": year,
                "counts": {"spn_intervals": spn_intervals},
            }
        word_labels, phone_labels = _db_inventory(connection)
        sessions = _sessions(connection)
        db_ids = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT f.name
                FROM utterance u
                JOIN file f ON f.id=u.file_id
                WHERE u.ignored=0
                """
            )
        }
        aligned_ids = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT f.name
                FROM utterance u
                JOIN file f ON f.id=u.file_id
                WHERE u.ignored=0
                  AND EXISTS(
                    SELECT 1 FROM word_interval wi
                    WHERE wi.utterance_id=u.id
                  )
                  AND EXISTS(
                    SELECT 1 FROM phone_interval pi
                    WHERE pi.utterance_id=u.id
                  )
                """
            )
        }
        used_phones = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT DISTINCT p.phone
                FROM phone_interval pi
                JOIN phone p ON p.id = pi.phone_id
                WHERE trim(p.phone) <> ''
                """
            )
            if str(row[0]).strip().lower() not in SILENCE
        }
    finally:
        connection.close()
    outside = sorted(used_phones - set(groups))
    if outside:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "failed",
            "analysis_ready_status": "blocked_phone_inventory",
            "year": year,
            "phone_outside_acoustic_inventory": outside,
        }
    if limit_sessions and lab_root is not None:
        raise RuntimeError(
            "--limit-sessions와 full-year --lab-root exact gate는 함께 쓸 수 없음"
        )
    if limit_sessions:
        sessions = sessions[:limit_sessions]

    reconciliation: dict[str, object]
    if lab_root is None:
        reconciliation = {
            "status": "unverified_no_lab_root",
            "full_year_gate": False,
        }
    else:
        active_lab_ids = load_active_lab_ids(lab_root, year)
        source_search_ids = load_search_master_ids(search_master_root, year)
        unapproved_quarantine = quarantine_ids - alignment_exclusion_ids
        unknown_active_missing = (
            active_lab_ids - aligned_ids - alignment_exclusion_ids
        )
        # Post-MFA technical exclusions can be present in the retained MFA DB
        # while their LAB files have already been removed from the active
        # corpus.  That is an approved, safer inactive state, not an orphan DB
        # row.  Only DB IDs that are neither active nor explicitly approved
        # are unauthorized.
        approved_inactive_database_exclusions = (
            db_ids - active_lab_ids
        ) & alignment_exclusion_ids
        unexpected_db_ids = (
            db_ids - active_lab_ids - alignment_exclusion_ids
        )
        approved_upstream_exclusions = (
            alignment_exclusion_ids - active_lab_ids
        )
        approved_active_exclusions = alignment_exclusion_ids & active_lab_ids
        unapproved_source_without_active_lab = (
            source_search_ids - active_lab_ids - alignment_exclusion_ids
        )
        active_lab_ids_outside_source = active_lab_ids - source_search_ids
        approved_exclusion_ids_outside_source = (
            alignment_exclusion_ids - source_search_ids
        )
        invalid_analysis_only = analysis_only_ids - aligned_ids
        hard_sets = {
            "unapproved_quarantine_ids": unapproved_quarantine,
            "unknown_active_lab_without_alignment": unknown_active_missing,
            "db_ids_without_active_lab": unexpected_db_ids,
            "unapproved_source_without_active_lab": (
                unapproved_source_without_active_lab
            ),
            "active_lab_ids_outside_source": active_lab_ids_outside_source,
            "approved_exclusion_ids_outside_source": (
                approved_exclusion_ids_outside_source
            ),
            "analysis_only_ids_without_alignment": invalid_analysis_only,
        }
        reconciliation = {
            "status": (
                "passed"
                if all(not values for values in hard_sets.values())
                else "failed"
            ),
            "full_year_gate": True,
            "counts": {
                "source_search_ids": len(source_search_ids),
                "active_lab_ids": len(active_lab_ids),
                "database_utterance_ids": len(db_ids),
                "aligned_database_ids": len(aligned_ids),
                "approved_alignment_exclusions": len(
                    alignment_exclusion_ids
                ),
                "approved_analysis_only_exclusions": len(
                    analysis_only_ids
                ),
                "approved_upstream_alignment_exclusions": len(
                    approved_upstream_exclusions
                ),
                "approved_active_alignment_exclusions": len(
                    approved_active_exclusions
                ),
                "approved_inactive_database_exclusions": len(
                    approved_inactive_database_exclusions
                ),
                "quarantine_ids": len(quarantine_ids),
                **{
                    name: len(values) for name, values in hard_sets.items()
                },
            },
            "inventories": {
                name: sorted(values) for name, values in hard_sets.items()
            },
            "equation": (
                "source_search_ids = active_lab_ids union "
                "approved_upstream_alignment_exclusions; active_lab_ids = "
                "aligned_database_ids union "
                "approved_active_alignment_exclusions; database_utterance_ids "
                "subset active_lab_ids union approved_alignment_exclusions; "
                "quarantine_ids subset approved_alignment_exclusions"
            ),
        }
        if reconciliation["status"] != "passed":
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "failed",
                "analysis_ready_status": "blocked_exact_id_reconciliation",
                "year": year,
                "alignment_contract_id": contract_id,
                "exact_id_reconciliation": reconciliation,
            }

    totals: Counter[str] = Counter(spn_intervals=0)
    failures: list[dict[str, str]] = []
    missing_search: list[str] = []
    missing_alignment: list[str] = []
    roundoff_examples: list[dict[str, object]] = []
    max_boundary_roundoff_seconds = 0.0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                export_session_textgrids,
                db_path=db_path,
                year=year,
                session=session,
                utterances=utterances,
                search_master_root=search_master_root,
                output_root=output_root,
                word_labels=word_labels,
                phone_labels=phone_labels,
                phone_mapper=phone_mapper,
                alignment_exclusion_ids=alignment_exclusion_ids,
            ): (session, len(utterances))
            for session, utterances in sessions
        }
        for index, future in enumerate(as_completed(futures), 1):
            _session, source_count = futures[future]
            result = future.result()
            totals["source_utterances"] += source_count
            totals.update(result["counts"])
            failures.extend(
                result["failed_examples"][: max(0, 100 - len(failures))]
            )
            missing_search.extend(result["search_row_missing_inventory"])
            missing_alignment.extend(result["alignment_missing_inventory"])
            roundoff_examples.extend(
                result["roundoff_examples"][: max(0, 100 - len(roundoff_examples))]
            )
            max_boundary_roundoff_seconds = max(
                max_boundary_roundoff_seconds,
                float(result["max_boundary_roundoff_seconds"]),
            )
            totals["approved_excluded_inventory_rows"] += len(
                result["approved_excluded_inventory"]
            )
            if index % 50 == 0 or index == len(futures):
                print(
                    f"[{year}] research 6-tier {index:,}/{len(futures):,} "
                    f"sessions · created={totals['created']:,}",
                    flush=True,
                )

    accounted = sum(
        totals[key]
        for key in (
            "created",
            "validated_existing",
            "alignment_missing",
            "search_row_missing",
            "failed",
            "approved_excluded",
        )
    )
    hard_failure = any(
        totals[key]
        for key in (
            "alignment_missing",
            "search_row_missing",
            "failed",
            "word_span_fallback",
        )
    ) or accounted != totals["source_utterances"]
    tables_manifest: dict[str, object] | None = None
    if not hard_failure:
        try:
            tables_manifest = write_companion_tables(
                db_path=db_path,
                year=year,
                sessions=sessions,
                search_master_root=search_master_root,
                output_root=output_root,
                word_labels=word_labels,
                phone_labels=phone_labels,
                phone_mapper=phone_mapper,
                alignment_contract_id=contract_id,
                input_contract_id=input_contract_id,
                approved_exclusions=approved_exclusions,
                exclusion_contract_fingerprint=(
                    file_fingerprint(
                        approved_exclusions_contract.resolve(),
                        with_sha256=True,
                    )
                    if approved_exclusions_contract is not None
                    else None
                ),
                companion_schema_path=companion_schema_path,
                companion_schema=companion_schema,
            )
        except Exception as exc:
            hard_failure = True
            failures.append(
                {"utt_id": "", "error": f"companion tables: {type(exc).__name__}: {exc}"}
            )

    status = "failed" if hard_failure else "success"
    elapsed = time.monotonic() - started
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "analysis_ready_status": (
            (
                "ready_with_approved_exclusions"
                if approved_exclusions else "ready"
            )
            if status == "success" else "blocked"
        ),
        "year": year,
        "db_path": str(db_path),
        "search_master_root": str(search_master_root),
        "output_root": str(output_root),
        "tier_names": BASE_TIERS,
        "alignment_contract": file_fingerprint(
            alignment_contract, with_sha256=True
        ),
        "alignment_contract_id": contract_id,
        "input_contract_id": input_contract_id,
        "alignment_models": contract_data.get("models", {}),
        "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        "counts": dict(sorted(totals.items())),
        "accounted": accounted,
        "coverage_pct": (
            round(
                100
                * (totals["created"] + totals["validated_existing"])
                / (
                    totals["source_utterances"]
                    - totals["approved_excluded"]
                ),
                4,
            )
            if (
                totals["source_utterances"]
                - totals["approved_excluded"]
            )
            else 0
        ),
        "coverage_denominator": (
            "database source utterances minus approved "
            "alignment_and_analysis exclusions"
        ),
        "phone_inventory": {
            "used_non_silence": len(used_phones),
            "outside_acoustic": outside,
        },
        "float32_boundary_normalization": {
            "policy": (
                "snap only 0/xmax drift explained by the nearest float32 "
                "representation of the same WAV duration"
            ),
            "minimum_tolerance_seconds": (
                MIN_BOUNDARY_ROUNDOFF_TOLERANCE_SECONDS
            ),
            "comparison_margin_seconds": FLOAT32_BOUNDARY_MARGIN_SECONDS,
            "utterances_adjusted": totals[
                "utterances_float32_boundary_adjusted"
            ],
            "boundaries_adjusted": totals["float32_boundary_adjustments"],
            "max_adjustment_seconds": max_boundary_roundoff_seconds,
            "examples": roundoff_examples[:100],
        },
        "companion_tables": tables_manifest,
        "approved_exclusions_contract": exclusion_contract_data,
        "exact_id_reconciliation": reconciliation,
        "failed_examples": failures[:100],
        "search_row_missing_inventory": sorted(set(missing_search)),
        "alignment_missing_inventory": sorted(set(missing_alignment)),
        "elapsed_seconds": round(elapsed, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument("--approved-exclusions-contract", type=Path)
    parser.add_argument("--lab-root", type=Path)
    parser.add_argument("--quarantine-log", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit-sessions", type=int, default=0)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = export_database(
            db_path=args.db,
            year=args.year,
            search_master_root=args.search_master_root,
            output_root=args.output_root,
            acoustic_model=args.acoustic_model,
            alignment_contract=args.alignment_contract,
            approved_exclusions_contract=args.approved_exclusions_contract,
            lab_root=args.lab_root,
            quarantine_log=args.quarantine_log,
            workers=args.workers,
            limit_sessions=args.limit_sessions,
        )
    except Exception as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed",
            "analysis_ready_status": "blocked_exception",
            "year": args.year,
            "error": f"{type(exc).__name__}: {exc}",
        }
    atomic_write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
