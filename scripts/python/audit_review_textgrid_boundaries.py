"""Render and audit review TextGrid tier boundaries and WAV signal levels."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import wave
from array import array
from pathlib import Path
from typing import Sequence

from pipeline_common import sha256_file
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


def wav_signal_stats(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        sample_width = stream.getsampwidth()
        sample_rate = stream.getframerate()
        frame_count = stream.getnframes()
        data = stream.readframes(frame_count)
    if sample_width not in {1, 2, 4}:
        raise RuntimeError(f"지원하지 않는 WAV sample width: {path} ({sample_width})")
    typecode = {1: "B", 2: "h", 4: "i"}[sample_width]
    samples = array(typecode)
    samples.frombytes(data)
    if sys.byteorder != "little" and sample_width > 1:
        samples.byteswap()
    if sample_width == 1:
        values = [int(value) - 128 for value in samples]
        full_scale = 127
    else:
        values = [int(value) for value in samples]
        full_scale = (1 << (8 * sample_width - 1)) - 1
    peak = max((abs(value) for value in values), default=0)
    rms = math.sqrt(
        sum(value * value for value in values) / max(1, len(values))
    )
    dbfs = None if rms == 0 else 20 * math.log10(rms / full_scale)
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frame_count": frame_count,
        "duration_seconds": frame_count / sample_rate,
        "peak": peak,
        "rms": round(rms, 6),
        "rms_dbfs": None if dbfs is None else round(dbfs, 3),
        "digital_silence": peak == 0,
    }


def _boundary_present(intervals: Sequence[tuple], point: float) -> bool:
    endpoints = {
        round(float(value), 6)
        for begin, end, _label in intervals
        for value in (begin, end)
    }
    return round(float(point), 6) in endpoints


def audit_textgrid(
    path: Path, expected_padding_seconds: float | None
) -> dict[str, object]:
    duration, tiers = parse_mfa_textgrid(path)
    if duration is None or duration <= 0:
        raise RuntimeError(f"TextGrid duration 없음: {path}")
    tier_reports: list[dict[str, object]] = []
    left_positions: list[float | None] = []
    right_positions: list[float | None] = []
    for name, intervals in tiers.items():
        first = intervals[0]
        last = intervals[-1]
        left_empty_end = (
            float(first[1]) if not str(first[2]).strip() else None
        )
        right_empty_start = (
            float(last[0]) if not str(last[2]).strip() else None
        )
        left_positions.append(left_empty_end)
        right_positions.append(right_empty_start)
        report = {
            "tier": name,
            "interval_count": len(intervals),
            "left_empty_end": left_empty_end,
            "right_empty_start": right_empty_start,
            "first_label_empty": not str(first[2]).strip(),
            "last_label_empty": not str(last[2]).strip(),
        }
        if expected_padding_seconds is not None:
            left = float(expected_padding_seconds)
            right = float(duration) - left
            report["expected_left_boundary_present"] = _boundary_present(
                intervals, left
            )
            report["expected_right_boundary_present"] = _boundary_present(
                intervals, right
            )
        tier_reports.append(report)
    unique_left = {None if value is None else round(value, 6) for value in left_positions}
    unique_right = {None if value is None else round(value, 6) for value in right_positions}
    expected_ok = None
    if expected_padding_seconds is not None:
        expected_ok = all(
            bool(row["expected_left_boundary_present"])
            and bool(row["expected_right_boundary_present"])
            and bool(row["first_label_empty"])
            and bool(row["last_label_empty"])
            for row in tier_reports
        )
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "duration_seconds": duration,
        "tier_count": len(tiers),
        "tier_names": list(tiers),
        "tiers": tier_reports,
        "left_empty_edge_consistent": len(unique_left) == 1,
        "right_empty_edge_consistent": len(unique_right) == 1,
        "left_empty_edge_positions": sorted(
            unique_left, key=lambda value: (-1 if value is None else value)
        ),
        "right_empty_edge_positions": sorted(
            unique_right, key=lambda value: (-1 if value is None else value)
        ),
        "expected_padding_seconds": expected_padding_seconds,
        "expected_padding_all_tiers_passed": expected_ok,
    }


def render_textgrid(path: Path, destination: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    duration, tiers = parse_mfa_textgrid(path)
    assert duration is not None
    names = list(tiers)
    figure, axis = plt.subplots(figsize=(14, 0.8 * len(names) + 1.8), dpi=160)
    for lane, name in enumerate(reversed(names)):
        y = lane
        for begin, end, label in tiers[name]:
            labeled = bool(str(label).strip())
            rectangle = Rectangle(
                (float(begin), y),
                float(end) - float(begin),
                0.72,
                facecolor="#cfe8ff" if labeled else "#f2f2f2",
                edgecolor="#333333",
                linewidth=0.7,
            )
            axis.add_patch(rectangle)
            if labeled and float(end) - float(begin) >= duration * 0.055:
                text = str(label).replace("\n", " ")
                if len(text) > 28:
                    text = text[:27] + "…"
                axis.text(
                    (float(begin) + float(end)) / 2,
                    y + 0.36,
                    text,
                    ha="center",
                    va="center",
                    fontsize=7,
                    clip_on=True,
                )
        axis.text(
            -duration * 0.012,
            y + 0.36,
            name,
            ha="right",
            va="center",
            fontsize=8,
        )
    axis.set_xlim(-duration * 0.17, duration)
    axis.set_ylim(-0.15, len(names) + 0.2)
    axis.set_xlabel("seconds")
    axis.set_yticks([])
    axis.set_title(path.stem, fontsize=10)
    axis.spines[["left", "right", "top"]].set_visible(False)
    axis.grid(axis="x", color="#dddddd", linewidth=0.5)
    figure.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, bbox_inches="tight")
    plt.close(figure)


def audit_review_root(
    *,
    input_root: Path,
    output_root: Path,
    expected_padding_seconds: float | None,
) -> dict[str, object]:
    input_root = input_root.resolve()
    output_root = output_root.resolve()
    if not input_root.is_dir():
        raise FileNotFoundError(input_root)
    output_root.mkdir(parents=True, exist_ok=True)
    review_path = input_root / "00_REVIEW.csv"
    with review_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    items: list[dict[str, object]] = []
    for row in rows:
        wav_path = input_root / str(row["wav_file"])
        item: dict[str, object] = {
            "review_order": int(row["review_order"]),
            "utt_id": row["utt_id"],
            "wav": wav_signal_stats(wav_path),
            "textgrid": None,
        }
        textgrid_name = str(row.get("current_mfa_textgrid") or "").strip()
        if textgrid_name:
            textgrid_path = input_root / textgrid_name
            textgrid_report = audit_textgrid(
                textgrid_path, expected_padding_seconds
            )
            image_name = f"{int(row['review_order']):02d}__{row['utt_id']}__TIERS.png"
            render_textgrid(textgrid_path, output_root / image_name)
            textgrid_report["image"] = image_name
            item["textgrid"] = textgrid_report
        items.append(item)
    summary = {
        "schema_version": "review_textgrid_boundary_audit.v1",
        "status": "success",
        "input_root": str(input_root),
        "review_count": len(items),
        "textgrid_count": sum(item["textgrid"] is not None for item in items),
        "digital_silence_count": sum(
            bool(item["wav"]["digital_silence"]) for item in items
        ),
        "expected_padding_seconds": expected_padding_seconds,
        "items": items,
    }
    (output_root / "BOUNDARY_AUDIO_AUDIT.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-padding-seconds", type=float)
    args = parser.parse_args()
    report = audit_review_root(
        input_root=args.input_root,
        output_root=args.output_root,
        expected_padding_seconds=args.expected_padding_seconds,
    )
    print(json.dumps({
        "status": report["status"],
        "review_count": report["review_count"],
        "textgrid_count": report["textgrid_count"],
        "digital_silence_count": report["digital_silence_count"],
        "output_root": str(args.output_root.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
