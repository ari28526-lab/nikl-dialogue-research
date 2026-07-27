"""연도별 MFA 4-tier 운영 TextGrid를 독립적으로 전수 감사한다.

검사 범위:
- lab ↔ TextGrid ID coverage, 중복, 추가 파일, 누락 inventory
- 정확한 4-tier 순서(words/phones/morphemes/utterance)
- 모든 tier의 0–xmax 연속 coverage, 유효 interval, 핵심 label
- TextGrid xmax ↔ 원 WAV header duration
- 운영본을 실패시키지 않는 tier별 가시적 좌우 빈 경계 진단

운영본은 원 WAV 시간을 바꾸지 않는다. 0.05초 가시적 양끝 빈 경계는 패딩된
연구자 점검 사본의 표준이며, 여기서는 진단값으로만 센다.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import wave
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Iterator

from pipeline_common import atomic_text_writer, atomic_write_json
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid

EXPECTED_TIERS = ["words", "phones", "morphemes", "utterance"]


def iter_files(root: Path, suffix: str) -> Iterator[Path]:
    suffix_lower = suffix.lower()
    for directory, subdirs, filenames in os.walk(root):
        subdirs.sort()
        filenames.sort()
        base = Path(directory)
        for filename in filenames:
            if filename.lower().endswith(suffix_lower):
                yield base / filename


def append_progress(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    record = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        **payload,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )
        stream.flush()


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        rate = stream.getframerate()
        if rate <= 0:
            raise ValueError(f"invalid WAV sample rate: {rate}")
        return stream.getnframes() / rate


def inspect_textgrid(
    textgrid_path: Path,
    *,
    wav_path: Path,
    tolerance: float,
    visible_edge_seconds: float,
    check_wav_duration: bool,
) -> dict:
    reasons: list[str] = []
    visible_left: dict[str, bool] = {}
    visible_right: dict[str, bool] = {}
    duration = None
    wav_seconds = None
    try:
        duration, tiers = parse_mfa_textgrid(textgrid_path)
        tier_names = list(tiers)
        if tier_names != EXPECTED_TIERS:
            reasons.append(
                f"tier_schema:expected={EXPECTED_TIERS}:actual={tier_names}"
            )
        if duration is None or duration <= 0:
            reasons.append(f"invalid_duration:{duration}")

        for tier_name in EXPECTED_TIERS:
            intervals = tiers.get(tier_name, [])
            if not intervals:
                reasons.append(f"empty_tier:{tier_name}")
                visible_left[tier_name] = False
                visible_right[tier_name] = False
                continue
            first_start = float(intervals[0][0])
            last_end = float(intervals[-1][1])
            if abs(first_start) > tolerance:
                reasons.append(
                    f"left_boundary:{tier_name}:{first_start}"
                )
            if duration is not None and abs(last_end - duration) > tolerance:
                reasons.append(
                    f"right_boundary:{tier_name}:{last_end}/{duration}"
                )
            previous_end = None
            for index, (start, end, _label) in enumerate(intervals):
                start = float(start)
                end = float(end)
                if start < -tolerance or end < start - tolerance:
                    reasons.append(
                        f"invalid_interval:{tier_name}:{index}:{start}/{end}"
                    )
                    break
                if duration is not None and end > duration + tolerance:
                    reasons.append(
                        f"past_xmax:{tier_name}:{index}:{end}/{duration}"
                    )
                    break
                if (
                    previous_end is not None
                    and abs(start - previous_end) > tolerance
                ):
                    relation = "gap" if start > previous_end else "overlap"
                    reasons.append(
                        f"{relation}:{tier_name}:{index}:"
                        f"{previous_end}/{start}"
                    )
                    break
                previous_end = end

            first = intervals[0]
            last = intervals[-1]
            visible_left[tier_name] = (
                not str(first[2]).strip()
                and float(first[1]) - float(first[0])
                >= visible_edge_seconds - tolerance
            )
            visible_right[tier_name] = (
                not str(last[2]).strip()
                and float(last[1]) - float(last[0])
                >= visible_edge_seconds - tolerance
            )

        for tier_name in ("words", "phones", "morphemes", "utterance"):
            if not any(
                str(label).strip()
                for _start, _end, label in tiers.get(tier_name, [])
            ):
                reasons.append(f"no_labeled_interval:{tier_name}")

        if check_wav_duration:
            if not wav_path.is_file():
                reasons.append("wav_missing")
            else:
                try:
                    wav_seconds = wav_duration(wav_path)
                    if (
                        duration is None
                        or abs(wav_seconds - duration) > tolerance
                    ):
                        reasons.append(
                            f"wav_duration_mismatch:"
                            f"{wav_seconds}/{duration}"
                        )
                except Exception as exc:
                    reasons.append(
                        f"wav_invalid:{type(exc).__name__}:{exc}"
                    )
    except Exception as exc:
        reasons.append(f"parse_error:{type(exc).__name__}:{exc}")

    return {
        "path": str(textgrid_path),
        "utt_id": textgrid_path.stem,
        "valid": not reasons,
        "reasons": reasons,
        "duration": duration,
        "wav_duration": wav_seconds,
        "visible_left": visible_left,
        "visible_right": visible_right,
    }


def write_missing_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "year",
        "session_id",
        "utt_id",
        "reason",
        "lab_path",
        "lab_bytes",
        "wav_path",
        "wav_exists",
    ]
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _temp_path):
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def batched(iterator: Iterator[Path], size: int) -> Iterator[list[Path]]:
    batch: list[Path] = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def audit_year(
    *,
    year: str,
    lab_root: Path,
    textgrid_root: Path,
    report_path: Path,
    missing_csv_path: Path,
    progress_jsonl: Path | None = None,
    input_contract_id: str | None = None,
    workers: int = 4,
    batch_size: int = 2000,
    tolerance: float = 0.001,
    visible_edge_seconds: float = 0.05,
    minimum_coverage_pct: float = 99.0,
    check_wav_duration: bool = True,
) -> dict:
    started_at = datetime.now().astimezone().isoformat()
    started = time.monotonic()
    lab_root = lab_root.resolve()
    textgrid_root = textgrid_root.resolve()
    report_path = report_path.resolve()
    missing_csv_path = missing_csv_path.resolve()

    lab_paths: dict[str, Path] = {}
    duplicate_lab_ids: set[str] = set()
    zero_byte_lab_ids: list[str] = []
    for path in iter_files(lab_root, ".lab"):
        utt_id = path.stem
        if utt_id in lab_paths:
            duplicate_lab_ids.add(utt_id)
        else:
            lab_paths[utt_id] = path
        if path.stat().st_size <= 0:
            zero_byte_lab_ids.append(utt_id)

    append_progress(
        progress_jsonl,
        {
            "event": "audit_started",
            "year": year,
            "input_contract_id": input_contract_id,
            "lab_files": len(lab_paths),
            "workers": workers,
            "check_wav_duration": check_wav_duration,
        },
    )

    textgrid_ids: set[str] = set()
    duplicate_textgrid_ids: set[str] = set()
    extra_textgrid_ids: list[str] = []
    reason_counts: Counter[str] = Counter()
    reason_examples: dict[str, list[str]] = {}
    visible_left = Counter()
    visible_right = Counter()
    inspected = valid = 0

    def inspect(path: Path) -> dict:
        relative = path.relative_to(textgrid_root)
        wav_path = (
            lab_root / relative.parent / f"{path.stem}.wav"
        )
        return inspect_textgrid(
            path,
            wav_path=wav_path,
            tolerance=tolerance,
            visible_edge_seconds=visible_edge_seconds,
            check_wav_duration=check_wav_duration,
        )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        for batch in batched(iter_files(textgrid_root, ".TextGrid"), batch_size):
            for path, result in zip(batch, executor.map(inspect, batch)):
                utt_id = path.stem
                if utt_id in textgrid_ids:
                    duplicate_textgrid_ids.add(utt_id)
                else:
                    textgrid_ids.add(utt_id)
                if utt_id not in lab_paths:
                    extra_textgrid_ids.append(utt_id)
                inspected += 1
                if result["valid"]:
                    valid += 1
                for reason in result["reasons"]:
                    reason_key = reason.split(":", 1)[0]
                    reason_counts[reason_key] += 1
                    examples = reason_examples.setdefault(reason_key, [])
                    if len(examples) < 20:
                        examples.append(f"{utt_id}: {reason}")
                for tier_name, present in result["visible_left"].items():
                    if present:
                        visible_left[tier_name] += 1
                for tier_name, present in result["visible_right"].items():
                    if present:
                        visible_right[tier_name] += 1

            if inspected % 10_000 < len(batch):
                elapsed = max(time.monotonic() - started, 1e-9)
                append_progress(
                    progress_jsonl,
                    {
                        "event": "audit_progress",
                        "year": year,
                        "input_contract_id": input_contract_id,
                        "textgrids_inspected": inspected,
                        "valid_textgrids": valid,
                        "invalid_textgrids": inspected - valid,
                        "files_per_second": round(inspected / elapsed, 1),
                        "elapsed_seconds": round(elapsed, 1),
                    },
                )
                print(
                    f"[{year}] TextGrid {inspected:,} · "
                    f"valid {valid:,} · "
                    f"{inspected / elapsed:,.0f}/s",
                    flush=True,
                )

    missing_ids = sorted(set(lab_paths) - textgrid_ids)
    missing_rows: list[dict] = []
    missing_without_wav = 0
    for utt_id in missing_ids:
        lab_path = lab_paths[utt_id]
        wav_path = lab_path.with_suffix(".wav")
        wav_exists = wav_path.is_file()
        if not wav_exists:
            missing_without_wav += 1
        try:
            session_id = str(lab_path.parent.relative_to(lab_root))
        except ValueError:
            session_id = lab_path.parent.name
        missing_rows.append(
            {
                "year": year,
                "session_id": session_id,
                "utt_id": utt_id,
                "reason": "no_textgrid_after_mfa",
                "lab_path": str(lab_path),
                "lab_bytes": lab_path.stat().st_size,
                "wav_path": str(wav_path),
                "wav_exists": wav_exists,
            }
        )

    write_missing_csv(missing_csv_path, missing_rows)
    lab_count = len(lab_paths)
    coverage_pct = (
        100 * len(textgrid_ids & set(lab_paths)) / lab_count
        if lab_count
        else 0.0
    )
    hard_failure_counts = {
        "duplicate_lab_ids": len(duplicate_lab_ids),
        "zero_byte_labs": len(zero_byte_lab_ids),
        "duplicate_textgrid_ids": len(duplicate_textgrid_ids),
        "textgrid_without_lab": len(extra_textgrid_ids),
        "invalid_textgrids": inspected - valid,
        "missing_without_wav": missing_without_wav,
    }
    status = (
        "success"
        if lab_count > 0
        and coverage_pct >= minimum_coverage_pct
        and all(value == 0 for value in hard_failure_counts.values())
        else "failed"
    )
    elapsed_seconds = round(time.monotonic() - started, 3)
    report = {
        "schema_version": 1,
        "status": status,
        "year": year,
        "input_contract_id": input_contract_id,
        "lab_root": str(lab_root),
        "textgrid_root": str(textgrid_root),
        "missing_csv": str(missing_csv_path),
        "started_at": started_at,
        "finished_at": datetime.now().astimezone().isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "settings": {
            "workers": workers,
            "batch_size": batch_size,
            "tolerance_seconds": tolerance,
            "visible_edge_seconds": visible_edge_seconds,
            "minimum_coverage_pct": minimum_coverage_pct,
            "check_wav_duration": check_wav_duration,
            "expected_tiers": EXPECTED_TIERS,
        },
        "counts": {
            "lab_ids": lab_count,
            "textgrid_files_inspected": inspected,
            "textgrid_ids": len(textgrid_ids),
            "valid_textgrids": valid,
            "invalid_textgrids": inspected - valid,
            "lab_without_textgrid": len(missing_ids),
            "textgrid_without_lab": len(extra_textgrid_ids),
            "missing_with_wav": len(missing_ids) - missing_without_wav,
            "missing_without_wav": missing_without_wav,
            "duplicate_lab_ids": len(duplicate_lab_ids),
            "duplicate_textgrid_ids": len(duplicate_textgrid_ids),
            "zero_byte_labs": len(zero_byte_lab_ids),
        },
        "coverage_pct": round(coverage_pct, 4),
        "hard_failure_counts": hard_failure_counts,
        "reason_counts": dict(sorted(reason_counts.items())),
        "reason_examples": reason_examples,
        "visible_edge_diagnostics": {
            tier_name: {
                "left_blank_at_least_threshold": visible_left[tier_name],
                "right_blank_at_least_threshold": visible_right[tier_name],
                "files_inspected": inspected,
            }
            for tier_name in EXPECTED_TIERS
        },
        "examples": {
            "duplicate_lab_ids": sorted(duplicate_lab_ids)[:20],
            "zero_byte_lab_ids": sorted(zero_byte_lab_ids)[:20],
            "duplicate_textgrid_ids": sorted(duplicate_textgrid_ids)[:20],
            "textgrid_without_lab": sorted(extra_textgrid_ids)[:20],
            "lab_without_textgrid": missing_ids[:20],
        },
    }
    atomic_write_json(report_path, report)
    append_progress(
        progress_jsonl,
        {
            "event": "audit_completed",
            "year": year,
            "input_contract_id": input_contract_id,
            "status": status,
            "coverage_pct": report["coverage_pct"],
            "counts": report["counts"],
            "elapsed_seconds": elapsed_seconds,
            "report": str(report_path),
            "missing_csv": str(missing_csv_path),
        },
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--lab-root", type=Path, required=True)
    parser.add_argument("--textgrid-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--missing-csv", type=Path, required=True)
    parser.add_argument("--progress-jsonl", type=Path)
    parser.add_argument("--input-contract-id")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--tolerance", type=float, default=0.001)
    parser.add_argument("--visible-edge-seconds", type=float, default=0.05)
    parser.add_argument("--minimum-coverage-pct", type=float, default=99.0)
    parser.add_argument("--skip-wav-duration", action="store_true")
    args = parser.parse_args()

    report = audit_year(
        year=args.year,
        lab_root=args.lab_root,
        textgrid_root=args.textgrid_root,
        report_path=args.report,
        missing_csv_path=args.missing_csv,
        progress_jsonl=args.progress_jsonl,
        input_contract_id=args.input_contract_id,
        workers=args.workers,
        batch_size=args.batch_size,
        tolerance=args.tolerance,
        visible_edge_seconds=args.visible_edge_seconds,
        minimum_coverage_pct=args.minimum_coverage_pct,
        check_wav_duration=not args.skip_wav_duration,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
