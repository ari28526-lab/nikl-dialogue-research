"""남은 연도 MFA 입력을 수정 없이 전수 감사한다.

대량 실행기의 lab 생성과 같은 ``pron_reference_form -> Hangul-only lab``
계약을 사용하되, WAV·lab·CSV를 읽기만 한다. 특히 다음을 연도별로 수치화한다.

- 검색 CSV 행/세션, 화자 메타 결측, 미해결 기호 발음
- WAV 누락·44바이트 미만 파일
- CSV dur와 동일 ID WAV header 길이의 세션 단위 대응
- 현재 lab의 존재/0바이트/예상 내용 일치 여부
- 예상 usable lab의 형태소 원천 TextGrid 존재 여부
- 검색 입력에 속하지 않는데 WAV와 함께 남아 MFA가 읽을 수 있는 stale lab
- 과거 residual 조사에서 확인한 원본 PCM 결함

기본 실행은 WAV header 길이와 형태소 원천 존재까지 감사한다. 기존 lab
내용까지 전수 대조하려면
``--compare-lab-content``를 붙인다. 결과는 JSON으로 원자적으로 기록한다.
원자료·WAV·lab·MFA marker는 변경하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import statistics
import time
import wave
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline_common import atomic_write_json
from mfa_exclusion_contract import load_contract as load_exclusion_contract
from paths import P
from realign_eojeol_build_corpus import MISSING, form_to_lab

csv.field_size_limit(10_000_000)

YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
POST_MFA_ACTIVE_REASON_CODES = frozenset(
    {"audio_unusable", "mfa_alignment_missing"}
)
REQUIRED_COLUMNS = {
    "utt_id",
    "form",
    "pron_reference_form",
    "pron_reference_source",
    "pron_reference_status",
    "sex",
    "dur",
}


def validate_retained_db_checkpoint(
    *,
    checkpoint_path: Path,
    year: str,
    input_contract_id: str,
    alignment_contract_id: str,
    exclusion_rows: dict[str, dict[str, str]],
) -> tuple[set[str], dict[str, object]]:
    """보존 DB의 미정렬 ID와 post-MFA 승인 ID를 exact-match한다."""

    try:
        checkpoint = json.loads(
            checkpoint_path.read_text(encoding="utf-8-sig")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"direct_db_ready 읽기 실패: {checkpoint_path}: {exc}"
        ) from exc
    details = checkpoint.get("details")
    if not isinstance(details, dict):
        raise RuntimeError("direct_db_ready details 누락")
    if (
        str(checkpoint.get("year")) != year
        or checkpoint.get("stage") != "direct_db_ready"
        or not bool(details.get("computation_complete"))
        or str(details.get("input_contract_id")) != input_contract_id
        or str(details.get("alignment_contract_id"))
        != alignment_contract_id
    ):
        raise RuntimeError("direct_db_ready 연도/입력/정렬 계약 불일치")
    db_path = Path(str(details.get("alignment_db") or "")).resolve()
    if not db_path.is_file():
        raise RuntimeError(f"보존 alignment DB 없음: {db_path}")

    authorized = {
        utt_id
        for utt_id, row in exclusion_rows.items()
        if row.get("exclusion_scope") == "alignment_and_analysis"
        and row.get("reason_code") in POST_MFA_ACTIVE_REASON_CODES
    }
    if not authorized:
        raise RuntimeError("checkpoint 재개용 post-MFA 승인 ID가 0건")
    connection = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=120
    )
    connection.execute("PRAGMA query_only=ON")
    try:
        db_missing = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT f.name
                FROM utterance u
                JOIN file f ON f.id = u.file_id
                WHERE u.ignored = 0
                  AND (
                    NOT EXISTS (
                        SELECT 1 FROM word_interval wi
                        WHERE wi.utterance_id = u.id
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM phone_interval pi
                        WHERE pi.utterance_id = u.id
                    )
                  )
                """
            )
        }
    finally:
        connection.close()
    if authorized != db_missing:
        raise RuntimeError(
            "post-MFA 승인 ID와 보존 DB 미정렬 ID 불일치: "
            f"approved={len(authorized)} db={len(db_missing)}"
        )
    return authorized, {
        "path": str(checkpoint_path.resolve()),
        "status": "validated",
        "year": year,
        "input_contract_id": input_contract_id,
        "alignment_contract_id": alignment_contract_id,
        "alignment_db": str(db_path),
        "authorized_active_exclusions": len(authorized),
        "allowed_reason_codes": sorted(POST_MFA_ACTIVE_REASON_CODES),
        "db_missing_ids_exact_match": True,
    }

DURATION_RESIDUAL_TOLERANCE_SECONDS = 0.025
SESSION_DURATION_MATCH_MIN_PCT = 98.0
SESSION_DURATION_COVERAGE_MIN_PCT = 98.0
SESSION_PADDING_MIN_SECONDS = -0.025
SESSION_PADDING_MAX_SECONDS = 0.5
IMPOSSIBLE_SPEECH_RATE_MIN_SYLLABLES = 10
IMPOSSIBLE_SPEECH_RATE_PER_SECOND = 40.0


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


def load_known_pcm_records(
    path: Path | None,
) -> dict[str, dict[str, dict[str, str]]]:
    """과거 원음 실측을 연도·utt_id별로 읽어 누락 사유를 분류한다."""
    result: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    if path is None or not path.is_file():
        return result
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"year", "utt_id", "pcm_sec", "category"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(
                f"{path}: source PCM 필수 열 누락 {sorted(missing)}"
            )
        for row in reader:
            year = (row.get("year") or "").strip()
            utt_id = (row.get("utt_id") or "").strip()
            if not year or not utt_id:
                raise RuntimeError(f"{path}: 빈 year/utt_id")
            if utt_id in result[year]:
                raise RuntimeError(f"{path}: 중복 utt_id {utt_id}")
            result[year][utt_id] = row
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


def wav_duration_seconds(path: Path) -> float:
    """WAV payload를 읽지 않고 header의 frame/rate로 길이를 구한다."""
    if path.stat().st_size < 44:
        raise ValueError("WAV가 44바이트보다 작음")
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        if frames <= 0 or rate <= 0 or channels <= 0:
            raise ValueError(
                "잘못된 WAV header: "
                f"frames={frames} rate={rate} channels={channels}"
            )
        return frames / rate


def _duration_probe(
    item: tuple[str, float, Path],
) -> tuple[str, float, float | None, str | None]:
    utt_id, csv_duration, path = item
    try:
        return utt_id, csv_duration, wav_duration_seconds(path), None
    except (OSError, EOFError, wave.Error, ValueError) as exc:
        return (
            utt_id,
            csv_duration,
            None,
            f"{type(exc).__name__}: {exc}",
        )


def audit_session_durations(
    *,
    session: str,
    rows: list[dict[str, str]],
    session_dir: Path,
    entries: dict[str, int],
    executor: ThreadPoolExecutor | None,
    residual_tolerance: float = DURATION_RESIDUAL_TOLERANCE_SECONDS,
    minimum_match_pct: float = SESSION_DURATION_MATCH_MIN_PCT,
    minimum_coverage_pct: float = SESSION_DURATION_COVERAGE_MIN_PCT,
) -> dict:
    """F29형 발화 번호 밀림을 동일 ID CSV–WAV 길이로 검사한다.

    연도별 WAV 생성 과정에서 일관된 앞뒤 padding이 있을 수 있으므로
    ``wav_duration - csv_duration``의 세션 중앙값을 padding으로 추정하고,
    개별 발화는 그 중앙값에서 벗어난 잔차로 판정한다. 비교 불가 파일이
    조용히 제외되지 않도록 전체 CSV 행 대비 header 검사 coverage도 별도
    hard gate로 둔다.
    """
    probes: list[tuple[str, float, Path]] = []
    issues: list[dict[str, object]] = []
    counts: Counter = Counter()
    counts["expected"] = len(rows)

    for row in rows:
        utt_id = (row.get("utt_id") or "").strip()
        raw_duration = (row.get("dur") or "").strip()
        try:
            csv_duration = float(raw_duration)
            if csv_duration <= 0:
                raise ValueError("0 이하")
        except (TypeError, ValueError):
            counts["csv_duration_invalid"] += 1
            issues.append(
                {
                    "year": "",
                    "session": session,
                    "utt_id": utt_id,
                    "issue": "csv_duration_invalid",
                    "detail": raw_duration,
                }
            )
            continue

        wav_name = f"{utt_id}.wav"
        wav_size = entries.get(wav_name)
        if wav_size is None:
            counts["wav_missing"] += 1
            issues.append(
                {
                    "year": "",
                    "session": session,
                    "utt_id": utt_id,
                    "issue": "duration_wav_missing",
                    "detail": "",
                }
            )
            continue
        if wav_size < 44:
            counts["wav_too_small"] += 1
            issues.append(
                {
                    "year": "",
                    "session": session,
                    "utt_id": utt_id,
                    "issue": "duration_wav_too_small",
                    "detail": str(wav_size),
                }
            )
            continue
        probes.append((utt_id, csv_duration, session_dir / wav_name))

    mapper = executor.map if executor is not None else map
    inspected: list[tuple[str, float, float]] = []
    for utt_id, csv_duration, wav_duration, error in mapper(
        _duration_probe, probes
    ):
        if error is not None or wav_duration is None:
            counts["wav_header_unreadable"] += 1
            issues.append(
                {
                    "year": "",
                    "session": session,
                    "utt_id": utt_id,
                    "issue": "wav_header_unreadable",
                    "detail": error or "",
                }
            )
            continue
        inspected.append((utt_id, csv_duration, wav_duration))

    counts["inspected"] = len(inspected)
    expected = counts["expected"]
    coverage_pct = 100.0 * len(inspected) / expected if expected else 0.0

    if inspected:
        deltas = [
            wav_duration - csv_duration
            for _utt_id, csv_duration, wav_duration in inspected
        ]
        padding = statistics.median(deltas)
        matched = 0
        for utt_id, csv_duration, wav_duration in inspected:
            delta = wav_duration - csv_duration
            residual = delta - padding
            if abs(residual) <= residual_tolerance:
                matched += 1
                continue
            issues.append(
                {
                    "year": "",
                    "session": session,
                    "utt_id": utt_id,
                    "issue": "duration_residual_mismatch",
                    "detail": "",
                    "csv_duration_seconds": round(csv_duration, 6),
                    "wav_duration_seconds": round(wav_duration, 6),
                    "session_padding_seconds": round(padding, 6),
                    "residual_seconds": round(residual, 6),
                }
            )
        counts["matched"] = matched
        counts["residual_mismatch"] = len(inspected) - matched
        match_pct = 100.0 * matched / len(inspected)
        padding_plausible = (
            SESSION_PADDING_MIN_SECONDS
            <= padding
            <= SESSION_PADDING_MAX_SECONDS
        )
    else:
        padding = None
        match_pct = 0.0
        padding_plausible = False

    valid = bool(
        expected
        and coverage_pct >= minimum_coverage_pct
        and match_pct >= minimum_match_pct
        and padding_plausible
    )
    if not valid and not issues:
        issues.append(
            {
                "year": "",
                "session": session,
                "utt_id": "",
                "issue": "duration_session_gate_failed",
                "detail": (
                    f"coverage={coverage_pct:.3f}%, "
                    f"match={match_pct:.3f}%, padding={padding}"
                ),
            }
        )
    return {
        "session": session,
        "valid": valid,
        "expected": expected,
        "inspected": len(inspected),
        "matched": counts["matched"],
        "coverage_pct": round(coverage_pct, 6),
        "match_pct": round(match_pct, 6),
        "padding_seconds": (
            None if padding is None else round(padding, 6)
        ),
        "counts": dict(counts),
        "issues": issues,
    }


def _distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": round(min(values), 6),
        "median": round(statistics.median(values), 6),
        "max": round(max(values), 6),
    }


def audit_year(
    *,
    year: str,
    search_master_root: Path,
    wav_root: Path,
    compare_lab_content: bool,
    check_wav_durations: bool = True,
    morph_textgrid_root: Path | None = None,
    known_pcm: Counter | None = None,
    known_pcm_records: dict[str, dict[str, str]] | None = None,
    lab_workers: int = 8,
    approved_alignment_exclusions: set[str] | None = None,
    approved_active_alignment_exclusions: set[str] | None = None,
) -> dict:
    """한 연도를 읽기 전용으로 전수 감사한다."""
    source_dir = search_master_root / year
    approved_alignment_exclusions = approved_alignment_exclusions or set()
    approved_active_alignment_exclusions = (
        approved_active_alignment_exclusions or set()
    )
    if not approved_active_alignment_exclusions <= approved_alignment_exclusions:
        raise ValueError("active 허용 ID는 승인 alignment 제외의 부분집합이어야 함")
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
    issue_inventory: list[dict[str, object]] = []
    duration_sessions: list[dict] = []
    morph_source_issues: list[dict[str, object]] = []
    scanned_sessions: set[str] = set()
    started = time.monotonic()
    morph_year_dir = (
        morph_textgrid_root / year
        if morph_textgrid_root is not None
        else None
    )
    if morph_year_dir is not None and not morph_year_dir.is_dir():
        raise RuntimeError(f"{year} 형태소 TextGrid 폴더 없음: {morph_year_dir}")
    executor = (
        ThreadPoolExecutor(max_workers=max(1, lab_workers))
        if compare_lab_content or check_wav_durations
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
                active_rows = [
                    row for row in rows
                    if (row.get("utt_id") or "").strip()
                    not in approved_alignment_exclusions
                ]
                if session in scanned_sessions:
                    raise RuntimeError(
                        f"{year} 세션이 여러 CSV에 중복됨: {session}"
                    )
                scanned_sessions.add(session)
                counts["search_sessions"] += 1
                if active_rows and not session_dir.is_dir():
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
                    if utt_id in approved_alignment_exclusions:
                        continue
                    if entries.get(f"{utt_id}.wav", 0) < 44:
                        counts["wav_too_small"] += 1
                        risky_sessions[session] += 1
                        _add_example(examples, "wav_too_small", utt_id)

                if check_wav_durations:
                    if not active_rows:
                        counts["duration_sessions_fully_excluded"] += 1
                    else:
                        duration_result = audit_session_durations(
                            session=session,
                            rows=active_rows,
                            session_dir=session_dir,
                            entries=entries,
                            executor=executor,
                        )
                        duration_sessions.append(duration_result)
                        counts["duration_sessions_checked"] += 1
                        counts[
                            "duration_sessions_passed"
                            if duration_result["valid"]
                            else "duration_sessions_failed"
                        ] += 1
                        for key, value in duration_result["counts"].items():
                            counts[f"duration_{key}"] += value
                        for issue in duration_result["issues"]:
                            issue["year"] = year
                            issue_inventory.append(issue)
                            issue_name = str(issue["issue"])
                            utt_id = str(issue.get("utt_id") or session)
                            _add_example(examples, issue_name, utt_id)
                        if not duration_result["valid"]:
                            risky_sessions[session] += 1

                search_ids: set[str] = set()
                expected_lab_ids: set[str] = set()
                lab_checks: list[tuple[Path, str]] = []
                for row in rows:
                    counts["search_rows"] += 1
                    utt_id = row["utt_id"].strip()
                    search_ids.add(utt_id)
                    if utt_id in approved_alignment_exclusions:
                        counts["approved_alignment_excluded"] += 1
                        if utt_id in wav_ids and utt_id in lab_ids:
                            counts["approved_alignment_active_pair"] += 1
                            if utt_id in approved_active_alignment_exclusions:
                                counts[
                                    "approved_alignment_authorized_active_pair"
                                ] += 1
                            else:
                                counts[
                                    "approved_alignment_unauthorized_active_pair"
                                ] += 1
                            risky_sessions[session] += 1
                            _add_example(
                                examples,
                                "approved_alignment_active_pair",
                                utt_id,
                            )
                        # A still-present lab is expected before quarantine;
                        # a moved lab is also valid.  Either way it must not be
                        # misclassified as an unexpected active input.
                        expected_lab_ids.add(utt_id)
                        continue
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
                    try:
                        csv_duration = float((row.get("dur") or "").strip())
                    except (TypeError, ValueError):
                        csv_duration = 0.0
                    hangul_syllables = len(
                        re.findall(r"[가-힣]", expected_text)
                    )
                    if csv_duration > 0:
                        counts["text_duration_rows_checked"] += 1
                        syllables_per_second = (
                            hangul_syllables / csv_duration
                        )
                        if (
                            hangul_syllables
                            >= IMPOSSIBLE_SPEECH_RATE_MIN_SYLLABLES
                            and syllables_per_second
                            >= IMPOSSIBLE_SPEECH_RATE_PER_SECOND
                        ):
                            counts[
                                "source_segment_text_duration_impossible"
                            ] += 1
                            risky_sessions[session] += 1
                            _add_example(
                                examples,
                                "source_segment_text_duration_impossible",
                                utt_id,
                            )
                            issue_inventory.append(
                                {
                                    "year": year,
                                    "session": session,
                                    "utt_id": utt_id,
                                    "issue": (
                                        "source_segment_text_duration_"
                                        "impossible"
                                    ),
                                    "detail": "",
                                    "csv_duration_seconds": round(
                                        csv_duration, 6
                                    ),
                                    "hangul_syllables": hangul_syllables,
                                    "hangul_syllables_per_second": round(
                                        syllables_per_second, 3
                                    ),
                                }
                            )
                    else:
                        counts["text_duration_rows_not_computable"] += 1

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
                    if morph_year_dir is not None:
                        counts["morph_source_checked"] += 1
                        morph_path = (
                            morph_year_dir
                            / session
                            / f"{utt_id}.TextGrid"
                        )
                        try:
                            morph_size = morph_path.stat().st_size
                        except OSError:
                            morph_size = None
                        morph_issue = None
                        if morph_size is None:
                            counts["morph_source_missing"] += 1
                            morph_issue = "morph_source_missing"
                        elif morph_size == 0:
                            counts["morph_source_zero_byte"] += 1
                            morph_issue = "morph_source_zero_byte"
                        else:
                            counts["morph_source_nonzero"] += 1
                        if morph_issue is not None:
                            prior_pcm = (known_pcm_records or {}).get(utt_id)
                            prior_category = (
                                (prior_pcm.get("category") or "").strip()
                                if prior_pcm is not None
                                else ""
                            )
                            if prior_category in {"원본짧음", "PCM없음"}:
                                morph_disposition = (
                                    "exclude_source_audio_unusable"
                                )
                                counts[
                                    "morph_source_excluded_unusable"
                                ] += 1
                            elif prior_category == "원본정상":
                                morph_disposition = (
                                    "recover_morpheme_alignment_candidate"
                                )
                                counts[
                                    "morph_source_recovery_candidate"
                                ] += 1
                            else:
                                morph_disposition = (
                                    "manual_review_unclassified"
                                )
                                counts[
                                    "morph_source_unclassified"
                                ] += 1
                            risky_sessions[session] += 1
                            _add_example(examples, morph_issue, utt_id)
                            issue = {
                                "year": year,
                                "session": session,
                                "utt_id": utt_id,
                                "issue": morph_issue,
                                "detail": "",
                                "path": str(morph_path),
                                "source_pcm_category": prior_category,
                                "source_pcm_seconds": (
                                    (prior_pcm.get("pcm_sec") or "").strip()
                                    if prior_pcm is not None
                                    else ""
                                ),
                                "morph_disposition": morph_disposition,
                            }
                            morph_source_issues.append(issue)
                            issue_inventory.append(issue)

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
    duration_coverages = [
        float(item["coverage_pct"]) for item in duration_sessions
    ]
    duration_matches = [
        float(item["match_pct"]) for item in duration_sessions
    ]
    duration_paddings = [
        float(item["padding_seconds"])
        for item in duration_sessions
        if item["padding_seconds"] is not None
    ]
    authorized_active_pair_count = counts[
        "approved_alignment_authorized_active_pair"
    ]
    unauthorized_active_pair_count = counts[
        "approved_alignment_unauthorized_active_pair"
    ]
    result = {
        "year": year,
        "status": "audited",
        "read_only": True,
        "compare_lab_content": compare_lab_content,
        "wav_duration_audit_enabled": check_wav_durations,
        "morph_source_audit_enabled": morph_year_dir is not None,
        "approved_alignment_exclusion_count": len(
            approved_alignment_exclusions
        ),
        "approved_active_alignment_exclusion_count": len(
            approved_active_alignment_exclusions
        ),
        "approved_active_alignment_exclusion_inactive_count": (
            len(approved_active_alignment_exclusions)
            - authorized_active_pair_count
        ),
        "csv_files": len(csv_files),
        "elapsed_seconds": round(elapsed, 3),
        "counts": dict(sorted(counts.items())),
        "known_source_pcm_risks": dict(sorted((known_pcm or {}).items())),
        "top_risky_sessions": [
            {"session": session, "issue_count": count}
            for session, count in risky_sessions.most_common(30)
        ],
        "examples": examples,
        "duration_audit": {
            "policy": {
                "residual_tolerance_seconds": (
                    DURATION_RESIDUAL_TOLERANCE_SECONDS
                ),
                "session_match_min_pct": SESSION_DURATION_MATCH_MIN_PCT,
                "session_inspection_coverage_min_pct": (
                    SESSION_DURATION_COVERAGE_MIN_PCT
                ),
                "session_padding_allowed_seconds": [
                    SESSION_PADDING_MIN_SECONDS,
                    SESSION_PADDING_MAX_SECONDS,
                ],
            },
            "coverage_pct_distribution": _distribution(
                duration_coverages
            ),
            "match_pct_distribution": _distribution(duration_matches),
            "padding_seconds_distribution": _distribution(
                duration_paddings
            ),
            "failed_sessions": [
                {
                    key: value
                    for key, value in item.items()
                    if key != "issues"
                }
                for item in duration_sessions
                if not item["valid"]
            ],
        },
        "text_duration_audit": {
            "policy": {
                "minimum_hangul_syllables": (
                    IMPOSSIBLE_SPEECH_RATE_MIN_SYLLABLES
                ),
                "impossible_hangul_syllables_per_second": (
                    IMPOSSIBLE_SPEECH_RATE_PER_SECOND
                ),
                "logged_fields": [
                    "utt_id",
                    "csv_duration_seconds",
                    "hangul_syllables",
                    "hangul_syllables_per_second",
                ],
                "raw_transcript_logged": False,
            },
            "impossible_count": counts[
                "source_segment_text_duration_impossible"
            ],
        },
        "morph_source_issues": morph_source_issues,
        "issue_inventory": issue_inventory,
    }
    raw_morph_issue_count = (
        counts["morph_source_missing"]
        + counts["morph_source_zero_byte"]
    )
    classified_morph_issue_count = (
        counts["morph_source_excluded_unusable"]
        + counts["morph_source_recovery_candidate"]
    )
    result["gates"] = {
        "session_folders_present": counts["session_folder_missing"] == 0,
        "csv_wav_duration_correspondence": (
            not check_wav_durations
            or (
                counts["duration_sessions_failed"] == 0
                and counts["duration_residual_mismatch"] == 0
                and counts["duration_wav_missing"] == 0
                and counts["duration_wav_too_small"] == 0
                and counts["duration_wav_header_unreadable"] == 0
                and counts["duration_csv_duration_invalid"] == 0
            )
        ),
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
        "approved_alignment_inputs_inactive": (
            counts["approved_alignment_active_pair"] == 0
        ),
        "approved_alignment_active_pairs_authorized": (
            unauthorized_active_pair_count == 0
            and authorized_active_pair_count
            <= len(approved_active_alignment_exclusions)
        ),
        "source_segment_text_duration_plausible": (
            counts["source_segment_text_duration_impossible"] == 0
        ),
        "all_morph_sources_ready": (
            morph_year_dir is None
            or raw_morph_issue_count == 0
        ),
        "morph_source_inventory_classified": (
            morph_year_dir is None
            or (
                counts["morph_source_unclassified"] == 0
                and raw_morph_issue_count
                == classified_morph_issue_count
            )
        ),
        "analysis_eligible_morphology_ready": (
            morph_year_dir is None
            or (
                counts["morph_source_unclassified"] == 0
                and counts["morph_source_recovery_candidate"] == 0
                and raw_morph_issue_count
                == counts["morph_source_excluded_unusable"]
            )
        ),
    }
    execution_gate_names = (
        "session_folders_present",
        "csv_wav_duration_correspondence",
        "no_dangerous_unexpected_labs",
        "all_expected_labs_ready",
        "no_fatal_tiny_wav",
        "approved_alignment_active_pairs_authorized",
        "morph_source_inventory_classified",
    )
    analysis_gate_names = (
        *execution_gate_names,
        "source_segment_text_duration_plausible",
        "analysis_eligible_morphology_ready",
    )
    result["execution_gates"] = {
        name: result["gates"][name] for name in execution_gate_names
    }
    result["analysis_ready_gates"] = {
        name: result["gates"][name] for name in analysis_gate_names
    }
    result["execution_gates_pass"] = all(
        result["execution_gates"].values()
    )
    result["analysis_ready_gates_pass"] = all(
        result["analysis_ready_gates"].values()
    )
    # 기존 소비자 호환: all_gates_pass는 더 엄격한 analysis-ready 의미다.
    result["all_gates_pass"] = result["analysis_ready_gates_pass"]
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
        default=P("wav") / "individual",
    )
    parser.add_argument(
        "--morph-textgrid-root",
        type=Path,
        default=P("textgrid_merged"),
    )
    parser.add_argument(
        "--source-pcm-check",
        type=Path,
        default=P("layers") / "05_audio_index" / "source_pcm_check.csv",
    )
    parser.add_argument("--compare-lab-content", action="store_true")
    parser.add_argument(
        "--skip-wav-duration-audit",
        action="store_true",
        help="진단용 우회. 정식 preflight에서는 사용하지 않는다.",
    )
    parser.add_argument(
        "--skip-morph-source-audit",
        action="store_true",
        help="진단용 우회. 정식 preflight에서는 사용하지 않는다.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="보고서만 만들고 gate 실패에도 exit 0을 반환한다.",
    )
    parser.add_argument(
        "--gate-profile",
        choices=("analysis", "execution"),
        default="analysis",
        help=(
            "analysis=원음 결함 제외 후 형태소까지 준비, "
            "execution=모든 형태소 누락 사유 분류 후 MFA 실행 허용"
        ),
    )
    parser.add_argument("--lab-workers", type=int, default=8)
    parser.add_argument("--approved-exclusions-contract", type=Path)
    parser.add_argument("--input-contract-id")
    parser.add_argument("--retained-db-checkpoint", type=Path)
    parser.add_argument("--alignment-contract-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if bool(args.approved_exclusions_contract) != bool(args.input_contract_id):
        raise SystemExit(
            "--approved-exclusions-contract와 --input-contract-id는 함께 지정"
        )
    if args.approved_exclusions_contract and len(args.years) != 1:
        raise SystemExit("승인 제외 계약 감사에서는 연도 1개만 지정")
    if bool(args.retained_db_checkpoint) != bool(args.alignment_contract_id):
        raise SystemExit(
            "--retained-db-checkpoint와 --alignment-contract-id는 함께 지정"
        )
    if args.retained_db_checkpoint and (
        args.approved_exclusions_contract is None
        or args.gate_profile != "execution"
        or len(args.years) != 1
    ):
        raise SystemExit(
            "보존 DB active 제외 허용은 단일 연도 execution profile과 "
            "승인 계약에서만 가능"
        )

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
    known_pcm_by_utt = load_known_pcm_records(args.source_pcm_check)
    report = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "read_only": True,
        "search_master_root": str(args.search_master_root.resolve()),
        "search_master_build_status": meta.get("status"),
        "wav_root": str(args.wav_root.resolve()),
        "morph_textgrid_root": (
            None
            if args.skip_morph_source_audit
            else str(args.morph_textgrid_root.resolve())
        ),
        "strict": not args.no_strict,
        "gate_profile": args.gate_profile,
        "approved_exclusions_contract": (
            None
            if args.approved_exclusions_contract is None
            else str(args.approved_exclusions_contract.resolve())
        ),
        "retained_db_checkpoint": None,
        "years": [],
    }
    for year in args.years:
        approved_alignment_exclusions: set[str] = set()
        approved_active_alignment_exclusions: set[str] = set()
        if args.approved_exclusions_contract is not None:
            _contract, exclusion_rows = load_exclusion_contract(
                args.approved_exclusions_contract,
                year=year,
                input_contract_id=args.input_contract_id,
            )
            approved_alignment_exclusions = {
                utt_id
                for utt_id, row in exclusion_rows.items()
                if row["exclusion_scope"] == "alignment_and_analysis"
            }
            if args.retained_db_checkpoint is not None:
                (
                    approved_active_alignment_exclusions,
                    checkpoint_evidence,
                ) = validate_retained_db_checkpoint(
                    checkpoint_path=args.retained_db_checkpoint,
                    year=year,
                    input_contract_id=args.input_contract_id,
                    alignment_contract_id=args.alignment_contract_id,
                    exclusion_rows=exclusion_rows,
                )
                report["retained_db_checkpoint"] = checkpoint_evidence
        report["years"].append(
            audit_year(
                year=year,
                search_master_root=args.search_master_root,
                wav_root=args.wav_root,
                compare_lab_content=args.compare_lab_content,
                check_wav_durations=not args.skip_wav_duration_audit,
                morph_textgrid_root=(
                    None
                    if args.skip_morph_source_audit
                    else args.morph_textgrid_root
                ),
                known_pcm=known_pcm.get(year),
                known_pcm_records=known_pcm_by_utt.get(year),
                lab_workers=args.lab_workers,
                approved_alignment_exclusions=(
                    approved_alignment_exclusions
                ),
                approved_active_alignment_exclusions=(
                    approved_active_alignment_exclusions
                ),
            )
        )
        atomic_write_json(args.output, report)
    selected_key = (
        "execution_gates_pass"
        if args.gate_profile == "execution"
        else "analysis_ready_gates_pass"
    )
    report["selected_gate_result_key"] = selected_key
    report["all_years_pass"] = all(
        item[selected_key] for item in report["years"]
    )
    atomic_write_json(args.output, report)
    print(f"report: {args.output}", flush=True)
    if args.no_strict or report["all_years_pass"]:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
