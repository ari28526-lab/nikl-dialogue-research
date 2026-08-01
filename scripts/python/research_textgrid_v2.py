"""서울 코퍼스 원칙을 참조한 연구용 6-tier와 연결 검토본.

이 모듈은 기존 4-tier, MFA DB, WAV를 수정하지 않는다. 단일 발화의 기본
TextGrid는 ``words/phones_mfa/phoneme_r_auto/utterance/utterance_orth_r/
morph_analysis_utt``로 만들고, 연결 검토본에만 ``source_utt_id/speaker``를
추가한다. 형태소 문자열은 발화 전체 span의 참조값이며 형태소 시간경계가
아니다.
"""

from __future__ import annotations

import csv
import os
import uuid
import wave
from pathlib import Path
from typing import Callable, Mapping, Sequence

from morph_schema import canonicalize_tagged
from pipeline_common import promote_staged, sha256_file, staged_text_writer
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


SCHEMA_VERSION = "research_textgrid.v2"
SOURCE_TIERS = ["words", "phones_mfa", "utterance", "utterance_search"]
BASE_TIERS = [
    "words",
    "phones_mfa",
    "phoneme_r_auto",
    "utterance",
    "utterance_orth_r",
    "morph_analysis_utt",
]
STITCHED_TIERS = BASE_TIERS + ["source_utt_id", "speaker"]
SILENCE = {"", "<eps>", "sil", "sp", "spn", "<unk>"}

Interval = tuple[float, float, str]
PhoneMapper = Callable[[str], str]


def _escape(value: object) -> str:
    return str(value).replace('"', '""')


def _same_intervals(
    left: Sequence[Interval], right: Sequence[Interval], tolerance: float = 1e-6
) -> bool:
    return len(left) == len(right) and all(
        abs(float(a[0]) - float(b[0])) <= tolerance
        and abs(float(a[1]) - float(b[1])) <= tolerance
        and str(a[2]) == str(b[2])
        for a, b in zip(left, right)
    )


def _same_edges(
    left: Sequence[Interval], right: Sequence[Interval], tolerance: float = 1e-6
) -> bool:
    return len(left) == len(right) and all(
        abs(float(a[0]) - float(b[0])) <= tolerance
        and abs(float(a[1]) - float(b[1])) <= tolerance
        for a, b in zip(left, right)
    )


def _continuous(
    intervals: Sequence[Interval], duration: float, tolerance: float = 1e-6
) -> bool:
    if not intervals or abs(float(intervals[0][0])) > tolerance:
        return False
    cursor = 0.0
    for begin, end, _label in intervals:
        if abs(float(begin) - cursor) > tolerance:
            return False
        if float(end) < float(begin) - tolerance:
            return False
        cursor = float(end)
    return abs(cursor - float(duration)) <= max(tolerance, 1e-5)


def _validate_continuous(
    tier_name: str, intervals: Sequence[Interval], duration: float
) -> None:
    if not _continuous(intervals, duration):
        raise ValueError(f"0-xmax 연속 tier가 아님: {tier_name}")


def _materialize_intervals(
    intervals: Sequence[Interval], duration: float
) -> list[Interval]:
    """MFA interval을 0--xmax의 연속 IntervalTier로 만든다.

    입력의 유표 interval 시간과 label은 바꾸지 않고, 실제로 비어 있는 gap과
    양끝에만 빈 interval을 추가한다. overlap은 자료 손상으로 간주해 차단한다.
    """

    fixed: list[Interval] = []
    cursor = 0.0
    for begin, end, label in sorted(
        intervals, key=lambda item: (float(item[0]), float(item[1]))
    ):
        begin = max(0.0, float(begin))
        end = min(float(duration), float(end))
        if end - begin <= 1e-9:
            continue
        if begin < cursor - 1e-6:
            raise ValueError(
                f"interval overlap: begin={begin:.6f} < cursor={cursor:.6f}"
            )
        if begin - cursor > 1e-6:
            fixed.append((cursor, begin, ""))
        fixed.append((begin, end, str(label)))
        cursor = end
    if not fixed:
        return [(0.0, float(duration), "")]
    if float(duration) - cursor > 1e-6:
        fixed.append((cursor, float(duration), ""))
    return fixed


def _labeled_word_span(
    words: Sequence[Interval], duration: float
) -> tuple[float, float, bool]:
    labeled = [
        (float(begin), float(end))
        for begin, end, label in words
        if str(label).strip().lower() not in SILENCE
    ]
    if not labeled:
        return 0.0, float(duration), True
    return labeled[0][0], labeled[-1][1], False


def _mapped_phone_intervals(
    phones: Sequence[Interval], phone_mapper: PhoneMapper
) -> list[Interval]:
    mapped = [
        (
            float(begin),
            float(end),
            "" if str(label).strip().lower() in SILENCE else phone_mapper(str(label)),
        )
        for begin, end, label in phones
    ]
    if any(
        str(phone).strip().lower() not in SILENCE and not str(phoneme).strip()
        for (_begin, _end, phone), (_b2, _e2, phoneme) in zip(phones, mapped)
    ):
        raise ValueError("유표 phone의 빈 phoneme 매핑")
    return mapped


def _interval_tier_exact(
    name: str, intervals: Sequence[Interval], duration: float
) -> list[str]:
    _validate_continuous(name, intervals, duration)
    lines = [
        '        class = "IntervalTier"',
        f'        name = "{_escape(name)}"',
        "        xmin = 0",
        f"        xmax = {float(duration):.6f}",
        f"        intervals: size = {len(intervals)}",
    ]
    for index, (begin, end, label) in enumerate(intervals, 1):
        lines.extend(
            [
                f"        intervals [{index}]:",
                f"            xmin = {float(begin):.6f}",
                f"            xmax = {float(end):.6f}",
                f'            text = "{_escape(label)}"',
            ]
        )
    return lines


def write_textgrid_exact(
    path: Path,
    *,
    duration: float,
    tier_data: Sequence[tuple[str, Sequence[Interval]]],
) -> None:
    if duration <= 0:
        raise ValueError(f"duration은 양수여야 함: {duration}")
    names = [name for name, _ in tier_data]
    if len(names) != len(set(names)):
        raise ValueError(f"중복 tier 이름: {names}")
    tiers = [
        _interval_tier_exact(name, intervals, duration)
        for name, intervals in tier_data
    ]
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {float(duration):.6f}",
        "tiers? <exists>",
        f"size = {len(tiers)}",
        "item []:",
    ]
    for index, tier in enumerate(tiers, 1):
        lines.append(f"    item [{index}]:")
        lines.extend(tier)
    path.parent.mkdir(parents=True, exist_ok=True)
    with staged_text_writer(
        path, encoding="utf-8", newline="\n"
    ) as (stream, staged):
        stream.write("\n".join(lines) + "\n")
    promote_staged(staged, path)


def _one_labeled_interval(intervals: Sequence[Interval], name: str) -> Interval:
    labeled = [row for row in intervals if str(row[2]).strip()]
    if len(labeled) != 1:
        raise ValueError(f"{name} 유표 interval 수={len(labeled)}")
    return labeled[0]


def _relabel_utterance_tier(
    source: Sequence[Interval], label: str, name: str
) -> list[Interval]:
    if not str(label).strip():
        raise ValueError(f"빈 {name} label")
    labeled = _one_labeled_interval(source, "source utterance")
    return [
        (float(begin), float(end), str(label) if row == labeled else "")
        for row in source
        for begin, end, _text in [row]
    ]


def build_base_tier_data(
    source_textgrid: Path,
    row: Mapping[str, object],
    phone_mapper: PhoneMapper,
) -> tuple[float, list[tuple[str, list[Interval]]]]:
    duration, source = parse_mfa_textgrid(source_textgrid)
    if duration is None or list(source) != SOURCE_TIERS:
        raise ValueError(
            f"source 4-tier 계약 불일치: {source_textgrid} tiers={list(source)}"
        )
    form = str(row.get("form", "")).strip()
    form_roman = str(row.get("form_roman", "")).strip()
    tagged = str(row.get("tagged", "")).strip()
    if not form or not form_roman or not tagged:
        raise ValueError("form/form_roman/tagged 필수값 누락")
    morph_label = canonicalize_tagged(tagged)
    phones = list(source["phones_mfa"])
    try:
        phonemes = _mapped_phone_intervals(phones, phone_mapper)
    except ValueError as exc:
        raise ValueError(f"{exc}: {source_textgrid}") from exc
    utterance_source = list(source["utterance"])
    tier_data = [
        ("words", list(source["words"])),
        ("phones_mfa", phones),
        ("phoneme_r_auto", phonemes),
        (
            "utterance",
            _relabel_utterance_tier(utterance_source, form, "utterance"),
        ),
        (
            "utterance_orth_r",
            _relabel_utterance_tier(
                utterance_source, form_roman, "utterance_orth_r"
            ),
        ),
        (
            "morph_analysis_utt",
            _relabel_utterance_tier(
                utterance_source, morph_label, "morph_analysis_utt"
            ),
        ),
    ]
    return float(duration), tier_data


def build_base_tier_data_from_intervals(
    *,
    duration: float,
    words: Sequence[Interval],
    phones: Sequence[Interval],
    row: Mapping[str, object],
    phone_mapper: PhoneMapper,
) -> tuple[list[tuple[str, list[Interval]]], bool]:
    """MFA DB interval에서 승인된 6-tier를 직접 구성한다.

    반환값의 bool은 유표 word가 없어 발화 전체 span을 대신 썼는지를 뜻한다.
    전수 exporter는 이 값을 성공으로 숨기지 않고 hard gate로 센다.
    """

    if duration <= 0:
        raise ValueError(f"duration은 양수여야 함: {duration}")
    if not words or not phones:
        raise ValueError("words와 phones interval이 모두 필요함")
    form = str(row.get("form", "")).strip()
    form_roman = str(row.get("form_roman", "")).strip()
    tagged = str(row.get("tagged", "")).strip()
    if not form or not form_roman or not tagged:
        raise ValueError("form/form_roman/tagged 필수값 누락")

    word_intervals = _materialize_intervals(words, duration)
    phone_intervals = _materialize_intervals(phones, duration)
    phoneme_intervals = _mapped_phone_intervals(phone_intervals, phone_mapper)
    speech_start, speech_end, fallback = _labeled_word_span(
        word_intervals, duration
    )
    speech_source = _materialize_intervals(
        [(speech_start, speech_end, form)], duration
    )
    morph_label = canonicalize_tagged(tagged)
    tier_data = [
        ("words", word_intervals),
        ("phones_mfa", phone_intervals),
        ("phoneme_r_auto", phoneme_intervals),
        (
            "utterance",
            _relabel_utterance_tier(speech_source, form, "utterance"),
        ),
        (
            "utterance_orth_r",
            _relabel_utterance_tier(
                speech_source, form_roman, "utterance_orth_r"
            ),
        ),
        (
            "morph_analysis_utt",
            _relabel_utterance_tier(
                speech_source, morph_label, "morph_analysis_utt"
            ),
        ),
    ]
    return tier_data, fallback


def _validate_against_tier_data(
    path: Path,
    *,
    expected_duration: float,
    expected_data: Sequence[tuple[str, Sequence[Interval]]],
) -> dict[str, object]:
    duration, tiers = parse_mfa_textgrid(path)
    reasons: list[str] = []
    if duration is None or abs(float(duration) - expected_duration) > 1e-6:
        reasons.append("duration 불일치")
    if list(tiers) != BASE_TIERS:
        reasons.append(f"tier 순서 불일치: {list(tiers)}")
    expected = dict(expected_data)
    for name in BASE_TIERS:
        actual = tiers.get(name, [])
        if not _continuous(actual, expected_duration):
            reasons.append(f"0-xmax 비연속: {name}")
        if not _same_intervals(actual, expected.get(name, [])):
            reasons.append(f"예상 interval/label 불일치: {name}")
    if not _same_edges(
        tiers.get("phones_mfa", []), tiers.get("phoneme_r_auto", [])
    ):
        reasons.append("phones_mfa/phoneme_r_auto 경계 불일치")
    speech_tiers = [
        tiers.get("utterance", []),
        tiers.get("utterance_orth_r", []),
        tiers.get("morph_analysis_utt", []),
    ]
    if not all(_same_edges(speech_tiers[0], item) for item in speech_tiers[1:]):
        reasons.append("발화 수준 세 tier 경계 불일치")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "duration": expected_duration,
        "tier_names": list(tiers),
        "words_unchanged": _same_intervals(
            tiers.get("words", []), expected.get("words", [])
        ),
        "phones_mfa_unchanged": _same_intervals(
            tiers.get("phones_mfa", []), expected.get("phones_mfa", [])
        ),
        "phoneme_boundaries_equal_phones_mfa": _same_edges(
            tiers.get("phones_mfa", []), tiers.get("phoneme_r_auto", [])
        ),
        "speech_tier_boundaries_equal": all(
            _same_edges(speech_tiers[0], item) for item in speech_tiers[1:]
        ),
    }


def validate_base_textgrid(
    path: Path,
    *,
    source_textgrid: Path,
    row: Mapping[str, object],
    phone_mapper: PhoneMapper,
) -> dict[str, object]:
    expected_duration, expected_data = build_base_tier_data(
        source_textgrid, row, phone_mapper
    )
    return _validate_against_tier_data(
        path,
        expected_duration=expected_duration,
        expected_data=expected_data,
    )


def validate_base_textgrid_from_intervals(
    path: Path,
    *,
    duration: float,
    words: Sequence[Interval],
    phones: Sequence[Interval],
    row: Mapping[str, object],
    phone_mapper: PhoneMapper,
) -> dict[str, object]:
    expected_data, fallback = build_base_tier_data_from_intervals(
        duration=duration,
        words=words,
        phones=phones,
        row=row,
        phone_mapper=phone_mapper,
    )
    result = _validate_against_tier_data(
        path,
        expected_duration=duration,
        expected_data=expected_data,
    )
    result["word_span_fallback"] = fallback
    return result


def write_base_textgrid(
    destination: Path,
    *,
    source_textgrid: Path,
    row: Mapping[str, object],
    phone_mapper: PhoneMapper,
) -> dict[str, object]:
    if destination.exists():
        raise FileExistsError(f"기존 출력 보호: {destination}")
    duration, tier_data = build_base_tier_data(source_textgrid, row, phone_mapper)
    write_textgrid_exact(destination, duration=duration, tier_data=tier_data)
    result = validate_base_textgrid(
        destination,
        source_textgrid=source_textgrid,
        row=row,
        phone_mapper=phone_mapper,
    )
    if not result["valid"]:
        destination.unlink(missing_ok=True)
        raise RuntimeError("6-tier 검증 실패: " + "; ".join(result["reasons"]))
    return result


def write_base_textgrid_from_intervals(
    destination: Path,
    *,
    duration: float,
    words: Sequence[Interval],
    phones: Sequence[Interval],
    row: Mapping[str, object],
    phone_mapper: PhoneMapper,
) -> dict[str, object]:
    if destination.exists():
        raise FileExistsError(f"기존 출력 보호: {destination}")
    tier_data, fallback = build_base_tier_data_from_intervals(
        duration=duration,
        words=words,
        phones=phones,
        row=row,
        phone_mapper=phone_mapper,
    )
    write_textgrid_exact(destination, duration=duration, tier_data=tier_data)
    result = _validate_against_tier_data(
        destination,
        expected_duration=duration,
        expected_data=tier_data,
    )
    result["word_span_fallback"] = fallback
    if not result["valid"]:
        destination.unlink(missing_ok=True)
        raise RuntimeError("6-tier 검증 실패: " + "; ".join(result["reasons"]))
    return result


def _tile_shifted(
    rows: Sequence[Interval], duration: float
) -> list[Interval]:
    fixed: list[Interval] = []
    cursor = 0.0
    for begin, end, label in sorted(rows, key=lambda item: (item[0], item[1])):
        begin = float(begin)
        end = float(end)
        if begin < cursor - 1e-6:
            raise ValueError(f"연결 tier overlap: {begin:.6f} < {cursor:.6f}")
        if begin - cursor > 1e-6:
            fixed.append((cursor, begin, ""))
        fixed.append((begin, end, str(label)))
        cursor = end
    if not fixed:
        return [(0.0, float(duration), "")]
    if float(duration) - cursor > 1e-6:
        fixed.append((cursor, float(duration), ""))
    return fixed


def _wav_info(path: Path) -> tuple[wave._wave_params, int, bytes]:
    with wave.open(str(path), "rb") as stream:
        params = stream.getparams()
        frames = stream.getnframes()
        data = stream.readframes(frames)
    return params, frames, data


def write_stitched_review(
    *,
    destination_wav: Path,
    destination_textgrid: Path,
    destination_manifest: Path,
    sources: Sequence[Mapping[str, object]],
    phone_mapper: PhoneMapper,
    gap_seconds: float = 0.05,
    stitched_id: str,
    alignment_contract_id: str,
    selection_query_id: str,
) -> dict[str, object]:
    if len(sources) < 2:
        raise ValueError("연결 검토본은 최소 2발화 필요")
    if gap_seconds < 0:
        raise ValueError("gap_seconds는 0 이상")
    for target in (destination_wav, destination_textgrid, destination_manifest):
        if target.exists():
            raise FileExistsError(f"기존 출력 보호: {target}")

    shifted: dict[str, list[Interval]] = {name: [] for name in BASE_TIERS}
    source_ids: list[Interval] = []
    speakers: list[Interval] = []
    clips: list[dict[str, object]] = []
    manifest_rows: list[dict[str, object]] = []
    first_params: wave._wave_params | None = None
    cursor = 0.0
    for order, source in enumerate(sources, 1):
        wav_path = Path(str(source["wav"])).resolve()
        textgrid_path = Path(str(source["textgrid"])).resolve()
        row = source["row"]
        if not isinstance(row, Mapping):
            raise TypeError("source row는 mapping이어야 함")
        params, frame_count, data = _wav_info(wav_path)
        if first_params is None:
            first_params = params
        elif (
            params.nchannels,
            params.sampwidth,
            params.framerate,
            params.comptype,
        ) != (
            first_params.nchannels,
            first_params.sampwidth,
            first_params.framerate,
            first_params.comptype,
        ):
            raise ValueError(f"WAV 형식 불일치: {wav_path}")
        wav_duration = frame_count / params.framerate
        tg_duration, tier_data = build_base_tier_data(
            textgrid_path, row, phone_mapper
        )
        if abs(wav_duration - tg_duration) > 0.001:
            raise ValueError(
                f"WAV/TextGrid 길이 불일치: {wav_path.name} "
                f"{wav_duration:.6f}/{tg_duration:.6f}"
            )
        start = cursor
        end = start + tg_duration
        for name, intervals in tier_data:
            shifted[name].extend(
                (start + begin, start + finish, label)
                for begin, finish, label in intervals
            )
        utt_id = str(row.get("utt_id", "")).strip()
        speaker_id = str(row.get("speaker_id", "")).strip()
        if not utt_id:
            raise ValueError("연결 source utt_id 누락")
        source_ids.append((start, end, utt_id))
        speakers.append((start, end, speaker_id))
        clips.append({"data": data, "frames": frame_count})
        manifest_rows.append(
            {
                "stitched_id": stitched_id,
                "order": order,
                "utt_id": utt_id,
                "session_id": str(row.get("session_id", "")),
                "speaker_id": speaker_id,
                "source_wav": str(wav_path),
                "source_textgrid": str(textgrid_path),
                "source_wav_sha256": sha256_file(wav_path),
                "source_textgrid_sha256": sha256_file(textgrid_path),
                "source_start_seconds": "0.000000",
                "source_end_seconds": f"{tg_duration:.6f}",
                "stitched_start_seconds": f"{start:.6f}",
                "stitched_end_seconds": f"{end:.6f}",
                "gap_before_seconds": (
                    f"{gap_seconds:.6f}" if order > 1 else "0.000000"
                ),
                "gap_after_seconds": (
                    f"{gap_seconds:.6f}"
                    if order < len(sources)
                    else "0.000000"
                ),
                "stitch_mode": "review",
                "seam_contaminated": True,
                "koina_cross_seam_allowed": False,
                "alignment_contract_id": alignment_contract_id,
                "selection_query_id": selection_query_id,
                "source_time_rule": f"source_time=stitched_time-{start:.6f}",
            }
        )
        cursor = end + (gap_seconds if order < len(sources) else 0.0)

    assert first_params is not None
    total_duration = cursor
    destination_wav.parent.mkdir(parents=True, exist_ok=True)
    partial_wav = destination_wav.with_name(
        f".{destination_wav.name}.{uuid.uuid4().hex}.partial"
    )
    try:
        with wave.open(str(partial_wav), "wb") as output:
            output.setparams(first_params)
            gap_frames = round(gap_seconds * first_params.framerate)
            silence = b"\x00" * (
                gap_frames * first_params.nchannels * first_params.sampwidth
            )
            for index, clip in enumerate(clips):
                output.writeframes(clip["data"])
                if index < len(clips) - 1 and silence:
                    output.writeframes(silence)
        os.replace(partial_wav, destination_wav)
    finally:
        partial_wav.unlink(missing_ok=True)

    # 실제 WAV frame 반올림값을 TextGrid xmax의 정본으로 사용한다.
    with wave.open(str(destination_wav), "rb") as output:
        actual_duration = output.getnframes() / output.getframerate()
    if abs(actual_duration - total_duration) > 1 / first_params.framerate + 1e-6:
        raise RuntimeError("연결 WAV 예상 길이 불일치")
    total_duration = actual_duration
    tier_data = [
        (name, _tile_shifted(shifted[name], total_duration))
        for name in BASE_TIERS
    ]
    tier_data.extend(
        [
            ("source_utt_id", _tile_shifted(source_ids, total_duration)),
            ("speaker", _tile_shifted(speakers, total_duration)),
        ]
    )
    write_textgrid_exact(
        destination_textgrid,
        duration=total_duration,
        tier_data=tier_data,
    )
    destination_manifest.parent.mkdir(parents=True, exist_ok=True)
    fields = list(manifest_rows[0])
    partial_manifest = destination_manifest.with_name(
        f".{destination_manifest.name}.{uuid.uuid4().hex}.partial"
    )
    try:
        with open(
            partial_manifest, "x", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(manifest_rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(partial_manifest, destination_manifest)
    finally:
        partial_manifest.unlink(missing_ok=True)

    parsed_duration, parsed = parse_mfa_textgrid(destination_textgrid)
    reasons: list[str] = []
    if parsed_duration is None or abs(parsed_duration - total_duration) > 1e-6:
        reasons.append("연결 TextGrid/WAV duration 불일치")
    if list(parsed) != STITCHED_TIERS:
        reasons.append(f"연결 tier 순서 불일치: {list(parsed)}")
    for name in STITCHED_TIERS:
        if not _continuous(parsed.get(name, []), total_duration):
            reasons.append(f"연결 tier 비연속: {name}")
    actual_ids = [
        label for _begin, _end, label in parsed.get("source_utt_id", []) if label
    ]
    expected_ids = [str(row["utt_id"]) for row in manifest_rows]
    if actual_ids != expected_ids:
        reasons.append(f"source_utt_id 순서 불일치: {actual_ids}")
    if reasons:
        raise RuntimeError("연결 검증 실패: " + "; ".join(reasons))
    return {
        "valid": True,
        "duration": total_duration,
        "tier_names": list(parsed),
        "utterances": len(sources),
        "gap_seconds": gap_seconds,
        "stitch_mode": "review",
        "koina_cross_seam_allowed": False,
        "source_utt_ids": expected_ids,
    }
