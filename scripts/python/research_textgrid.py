"""새 연구 계약의 4-tier TextGrid 작성·검증.

시간 정렬 tier는 MFA DB의 word/phone interval을 그대로 사용한다. 형태소 검색
정보는 발화 수준 ``utterance_search`` label에만 복제하며 시간분할 형태소
tier를 만들지 않는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from merge_textgrid_v2 import interval_tier
from pipeline_common import promote_staged, staged_text_writer
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid
from textgrid_labels import (
    TARGET_TIERS,
    parse_search_label,
    utterance_search_label,
)

Interval = tuple[float, float, str]
SILENCE = {"", "<eps>", "sil", "sp", "<unk>"}


def labeled_word_span(
    words: Sequence[Interval], duration: float
) -> tuple[float, float, bool]:
    labeled = [
        (float(begin), float(end), str(label))
        for begin, end, label in words
        if str(label).strip().lower() not in SILENCE
    ]
    if not labeled:
        return 0.0, float(duration), True
    return labeled[0][0], labeled[-1][1], False


def _continuous(
    intervals: Sequence[Interval], duration: float, tolerance: float = 1e-6
) -> bool:
    if not intervals:
        return False
    if abs(float(intervals[0][0])) > tolerance:
        return False
    cursor = 0.0
    for begin, end, _ in intervals:
        if abs(float(begin) - cursor) > tolerance:
            return False
        if float(end) < float(begin) - tolerance:
            return False
        cursor = float(end)
    return abs(cursor - float(duration)) <= max(tolerance, 1e-5)


def _materialize_intervals(
    intervals: Sequence[Interval],
    duration: float,
    *,
    boundaries: Sequence[float] = (),
) -> list[Interval]:
    """0--duration 연속 구간을 만들고 요청한 경계를 모든 tier에 보존한다."""

    fixed: list[Interval] = []
    cursor = 0.0
    for begin, end, label in sorted(
        intervals, key=lambda row: (float(row[0]), float(row[1]))
    ):
        begin = max(0.0, float(begin))
        end = min(float(end), float(duration))
        if end - begin <= 1e-6:
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
        fixed.append((0.0, float(duration), ""))
    elif float(duration) - cursor > 1e-6:
        fixed.append((cursor, float(duration), ""))

    cuts = sorted(
        {
            float(cut)
            for cut in boundaries
            if 1e-6 < float(cut) < float(duration) - 1e-6
        }
    )
    result: list[Interval] = []
    for begin, end, label in fixed:
        points = [begin]
        points.extend(
            cut for cut in cuts if begin + 1e-9 < cut < end - 1e-9
        )
        points.append(end)
        result.extend(
            (piece_begin, piece_end, label)
            for piece_begin, piece_end in zip(points, points[1:])
        )
    return result


def _has_explicit_boundary(
    intervals: Sequence[Interval], cut: float, tolerance: float = 1e-6
) -> bool:
    has_left = any(abs(float(end) - cut) <= tolerance for _, end, _ in intervals)
    has_right = any(
        abs(float(begin) - cut) <= tolerance for begin, _, _ in intervals
    )
    return has_left and has_right


def validate_research_textgrid(
    path: Path,
    *,
    expected_duration: float | None = None,
    expected_row: Mapping[str, object] | None = None,
    expected_edge_padding_seconds: float | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "valid": False,
        "reasons": [],
        "duration": None,
        "tier_names": [],
        "left_empty_boundary": False,
        "right_empty_boundary": False,
        "explicit_left_edge_boundary": False,
        "explicit_right_edge_boundary": False,
    }
    reasons: list[str] = result["reasons"]  # type: ignore[assignment]
    try:
        duration, tiers = parse_mfa_textgrid(path)
        result["duration"] = duration
        result["tier_names"] = list(tiers)
        if duration is None or duration <= 0:
            reasons.append(f"invalid duration: {duration}")
            return result
        if (
            expected_duration is not None
            and abs(float(duration) - float(expected_duration)) > 0.001
        ):
            reasons.append(
                f"duration mismatch: expected={expected_duration} "
                f"actual={duration}"
            )
        if list(tiers) != TARGET_TIERS:
            reasons.append(
                f"tier order mismatch: expected={TARGET_TIERS} "
                f"actual={list(tiers)}"
            )
        for tier_name in TARGET_TIERS:
            intervals = tiers.get(tier_name, [])
            if not _continuous(intervals, float(duration)):
                reasons.append(f"tier not continuous 0-xmax: {tier_name}")
        if expected_edge_padding_seconds is not None:
            left = float(expected_edge_padding_seconds)
            right = float(duration) - left
            if left <= 0 or right <= left:
                reasons.append(
                    "invalid expected edge padding: "
                    f"{expected_edge_padding_seconds}"
                )
            else:
                left_ok = True
                right_ok = True
                for tier_name in TARGET_TIERS:
                    intervals = tiers.get(tier_name, [])
                    tier_left = _has_explicit_boundary(intervals, left)
                    tier_right = _has_explicit_boundary(intervals, right)
                    left_ok = left_ok and tier_left
                    right_ok = right_ok and tier_right
                    if not tier_left:
                        reasons.append(
                            f"explicit left padding boundary missing: {tier_name}"
                        )
                    if not tier_right:
                        reasons.append(
                            f"explicit right padding boundary missing: {tier_name}"
                        )
                    if any(
                        label.strip()
                        for begin, end, label in intervals
                        if end <= left + 1e-6
                    ):
                        reasons.append(
                            f"left padding label not empty: {tier_name}"
                        )
                    if any(
                        label.strip()
                        for begin, end, label in intervals
                        if begin >= right - 1e-6
                    ):
                        reasons.append(
                            f"right padding label not empty: {tier_name}"
                        )
                result["explicit_left_edge_boundary"] = left_ok
                result["explicit_right_edge_boundary"] = right_ok
        if not any(label.strip() for _, _, label in tiers.get("words", [])):
            reasons.append("words 유표 label 0개")
        if not any(
            label.strip() for _, _, label in tiers.get("phones_mfa", [])
        ):
            reasons.append("phones_mfa 유표 label 0개")
        utterance_labels = [
            (begin, end, label)
            for begin, end, label in tiers.get("utterance", [])
            if label.strip()
        ]
        search_labels = [
            (begin, end, label)
            for begin, end, label in tiers.get("utterance_search", [])
            if label.strip()
        ]
        if len(utterance_labels) != 1:
            reasons.append(
                f"utterance 유표 interval 수={len(utterance_labels)}"
            )
        if len(search_labels) != 1:
            reasons.append(
                f"utterance_search 유표 interval 수={len(search_labels)}"
            )
        if len(utterance_labels) == 1 and len(search_labels) == 1:
            if (
                abs(utterance_labels[0][0] - search_labels[0][0]) > 1e-6
                or abs(utterance_labels[0][1] - search_labels[0][1]) > 1e-6
            ):
                reasons.append("utterance/search label span 불일치")
            result["left_empty_boundary"] = utterance_labels[0][0] > 1e-6
            result["right_empty_boundary"] = (
                float(duration) - utterance_labels[0][1] > 1e-6
            )
            parsed_fields = parse_search_label(search_labels[0][2])
            result["search_fields"] = dict(parsed_fields)
            if expected_row is not None:
                expected_label = utterance_search_label(expected_row)
                if search_labels[0][2] != expected_label:
                    reasons.append("utterance_search label byte 불일치")
                if utterance_labels[0][2] != str(expected_row.get("form", "")):
                    reasons.append("utterance form 불일치")
        result["valid"] = not reasons
    except Exception as exc:
        reasons.append(f"{type(exc).__name__}: {exc}")
    return result


def write_research_textgrid(
    path: Path,
    *,
    duration: float,
    words: Sequence[Interval],
    phones: Sequence[Interval],
    search_row: Mapping[str, object],
    edge_padding_seconds: float | None = None,
) -> dict[str, object]:
    if duration <= 0:
        raise ValueError(f"duration은 양수여야 함: {duration}")
    if not words or not phones:
        raise ValueError("words와 phones interval이 모두 필요함")
    boundaries: list[float] = []
    if edge_padding_seconds is not None:
        left = float(edge_padding_seconds)
        right = float(duration) - left
        if left <= 0 or right <= left:
            raise ValueError(
                f"edge padding이 duration에 비해 잘못됨: "
                f"padding={edge_padding_seconds}, duration={duration}"
            )
        boundaries = [left, right]
    word_intervals = _materialize_intervals(
        words, duration, boundaries=boundaries
    )
    phone_intervals = _materialize_intervals(
        phones, duration, boundaries=boundaries
    )
    if edge_padding_seconds is not None:
        left, right = boundaries
        word_intervals = [
            (
                begin,
                end,
                "" if end <= left + 1e-9 or begin >= right - 1e-9 else label,
            )
            for begin, end, label in word_intervals
        ]
        phone_intervals = [
            (
                begin,
                end,
                "" if end <= left + 1e-9 or begin >= right - 1e-9 else label,
            )
            for begin, end, label in phone_intervals
        ]
    speech_start, speech_end, fallback = labeled_word_span(
        word_intervals, duration
    )
    form = str(search_row.get("form", ""))
    if not form.strip():
        raise ValueError("빈 form")
    label = utterance_search_label(search_row)
    utterance_intervals = _materialize_intervals(
        [(speech_start, speech_end, form)],
        duration,
        boundaries=boundaries,
    )
    search_intervals = _materialize_intervals(
        [(speech_start, speech_end, label)],
        duration,
        boundaries=boundaries,
    )
    tiers = [
        interval_tier("words", word_intervals, duration),
        interval_tier("phones_mfa", phone_intervals, duration),
        interval_tier(
            "utterance",
            utterance_intervals,
            duration,
        ),
        interval_tier(
            "utterance_search",
            search_intervals,
            duration,
        ),
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
    validation = validate_research_textgrid(
        staged,
        expected_duration=duration,
        expected_row=search_row,
        expected_edge_padding_seconds=edge_padding_seconds,
    )
    if not validation["valid"]:
        raise RuntimeError(
            f"임시 연구용 TextGrid 검증 실패: "
            + "; ".join(validation["reasons"])  # type: ignore[arg-type]
        )
    promote_staged(staged, path)
    validation["word_span_fallback"] = fallback
    return validation
