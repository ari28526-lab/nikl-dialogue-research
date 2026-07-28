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

from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid

EXPECTED_TIERS = ["words", "phones", "morphemes", "utterance"]
MORPH_ACTION_EXCLUDE = "exclude_source_audio_unusable"
MORPH_ACTION_RECOVER = "recover_morpheme_alignment_candidate"
MORPH_ACTION_REVIEW = "manual_review_unclassified"
MORPH_ACTIONS = {
    MORPH_ACTION_EXCLUDE,
    MORPH_ACTION_RECOVER,
    MORPH_ACTION_REVIEW,
}


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
    spn_intervals = 0
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
                if (
                    tier_name == "phones"
                    and str(_label).strip().lower() == "spn"
                ):
                    spn_intervals += 1
                    reasons.append(
                        f"spn_interval:phones:{index}:{start}/{end}"
                    )

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
        "spn_intervals": spn_intervals,
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
        "analysis_eligible",
        "morph_disposition",
    ]
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _temp_path):
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_morph_classification(path: Path | None, year: str) -> dict:
    """형태소 원천 결측 분류표를 읽어 분석 분모와 회수 대상을 고정한다."""
    result = {
        "path": None,
        "fingerprint": None,
        "by_utt": {},
        "counts": Counter(),
    }
    if path is None:
        return result
    path = path.resolve()
    required = {"year", "utt_id", "recommended_action"}
    by_utt: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(
                f"{path}: 형태소 분류 필수 열 누락 {sorted(missing)}"
            )
        for row in reader:
            row_year = (row.get("year") or "").strip()
            utt_id = (row.get("utt_id") or "").strip()
            action = (row.get("recommended_action") or "").strip()
            if row_year != year:
                raise RuntimeError(
                    f"{path}: 분류 연도 불일치 {row_year!r} != {year!r}"
                )
            if not utt_id or action not in MORPH_ACTIONS:
                raise RuntimeError(
                    f"{path}: 잘못된 utt/action {utt_id!r}/{action!r}"
                )
            if utt_id in by_utt:
                raise RuntimeError(f"{path}: 중복 utt_id {utt_id}")
            by_utt[utt_id] = row
            result["counts"][action] += 1
    result["path"] = str(path)
    result["fingerprint"] = file_fingerprint(path, with_sha256=True)
    result["by_utt"] = by_utt
    return result


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
    morph_classification_csv: Path | None = None,
) -> dict:
    started_at = datetime.now().astimezone().isoformat()
    started = time.monotonic()
    lab_root = lab_root.resolve()
    textgrid_root = textgrid_root.resolve()
    report_path = report_path.resolve()
    missing_csv_path = missing_csv_path.resolve()
    morph_classification = load_morph_classification(
        morph_classification_csv, year
    )
    morph_by_utt = morph_classification["by_utt"]
    excluded_ids = {
        utt_id
        for utt_id, row in morph_by_utt.items()
        if row["recommended_action"] == MORPH_ACTION_EXCLUDE
    }
    recovery_ids = {
        utt_id
        for utt_id, row in morph_by_utt.items()
        if row["recommended_action"] == MORPH_ACTION_RECOVER
    }
    unclassified_ids = {
        utt_id
        for utt_id, row in morph_by_utt.items()
        if row["recommended_action"] == MORPH_ACTION_REVIEW
    }

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
    lab_ids = set(lab_paths)
    classification_ids_without_lab = set(morph_by_utt) - lab_ids
    eligible_lab_ids = lab_ids - excluded_ids

    append_progress(
        progress_jsonl,
        {
            "event": "audit_started",
            "year": year,
            "input_contract_id": input_contract_id,
            "lab_files": len(lab_paths),
            "analysis_eligible_labs": len(eligible_lab_ids),
            "analysis_exclusions": len(excluded_ids & lab_ids),
            "recovery_candidates": len(recovery_ids & lab_ids),
            "workers": workers,
            "check_wav_duration": check_wav_duration,
        },
    )

    textgrid_ids: set[str] = set()
    duplicate_textgrid_ids: set[str] = set()
    extra_textgrid_ids: list[str] = []
    reason_counts: Counter[str] = Counter()
    excluded_reason_counts: Counter[str] = Counter()
    reason_examples: dict[str, list[str]] = {}
    excluded_reason_examples: dict[str, list[str]] = {}
    visible_left = Counter()
    visible_right = Counter()
    inspected = valid = eligible_inspected = eligible_valid = 0
    spn_intervals = 0
    excluded_inspected = excluded_valid = 0
    valid_textgrid_ids: set[str] = set()

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
                spn_intervals += int(result["spn_intervals"])
                if result["valid"]:
                    valid += 1
                    valid_textgrid_ids.add(utt_id)
                is_excluded = utt_id in excluded_ids
                if is_excluded:
                    excluded_inspected += 1
                    if result["valid"]:
                        excluded_valid += 1
                    target_counts = excluded_reason_counts
                    target_examples = excluded_reason_examples
                else:
                    eligible_inspected += 1
                    if result["valid"]:
                        eligible_valid += 1
                    target_counts = reason_counts
                    target_examples = reason_examples
                for reason in result["reasons"]:
                    reason_key = reason.split(":", 1)[0]
                    target_counts[reason_key] += 1
                    examples = target_examples.setdefault(reason_key, [])
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
                        "analysis_eligible_inspected": eligible_inspected,
                        "analysis_eligible_invalid": (
                            eligible_inspected - eligible_valid
                        ),
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

    missing_ids = sorted(lab_ids - textgrid_ids)
    eligible_missing_ids = sorted(eligible_lab_ids - textgrid_ids)
    missing_rows: list[dict] = []
    missing_without_wav = eligible_missing_without_wav = 0
    for utt_id in missing_ids:
        lab_path = lab_paths[utt_id]
        wav_path = lab_path.with_suffix(".wav")
        wav_exists = wav_path.is_file()
        if not wav_exists:
            missing_without_wav += 1
            if utt_id in eligible_lab_ids:
                eligible_missing_without_wav += 1
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
                "analysis_eligible": utt_id in eligible_lab_ids,
                "morph_disposition": (
                    morph_by_utt.get(utt_id, {}).get(
                        "recommended_action", ""
                    )
                ),
            }
        )

    write_missing_csv(missing_csv_path, missing_rows)
    lab_count = len(lab_paths)
    eligible_lab_count = len(eligible_lab_ids)
    raw_coverage_pct = (
        100 * len(textgrid_ids & lab_ids) / lab_count
        if lab_count
        else 0.0
    )
    coverage_pct = (
        100 * len(textgrid_ids & eligible_lab_ids) / eligible_lab_count
        if eligible_lab_count
        else 0.0
    )
    recovery_candidate_not_valid = (
        recovery_ids & lab_ids
    ) - valid_textgrid_ids
    eligible_zero_byte_lab_ids = (
        set(zero_byte_lab_ids) & eligible_lab_ids
    )
    hard_failure_counts = {
        "duplicate_lab_ids": len(duplicate_lab_ids),
        "zero_byte_analysis_eligible_labs": len(
            eligible_zero_byte_lab_ids
        ),
        "duplicate_textgrid_ids": len(duplicate_textgrid_ids),
        "textgrid_without_lab": len(extra_textgrid_ids),
        "invalid_analysis_eligible_textgrids": (
            eligible_inspected - eligible_valid
        ),
        "missing_analysis_eligible_without_wav": (
            eligible_missing_without_wav
        ),
        "classification_ids_without_lab": len(
            classification_ids_without_lab
        ),
        "morph_source_unclassified": len(unclassified_ids & lab_ids),
        "recovery_candidate_not_valid": len(
            recovery_candidate_not_valid
        ),
        "spn_phone_intervals": spn_intervals,
    }
    status = (
        "success"
        if eligible_lab_count > 0
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
            "coverage_denominator": (
                "lab_ids_minus_exclude_source_audio_unusable"
            ),
        },
        "counts": {
            "lab_ids": lab_count,
            "analysis_eligible_lab_ids": eligible_lab_count,
            "analysis_excluded_lab_ids": len(excluded_ids & lab_ids),
            "textgrid_files_inspected": inspected,
            "textgrid_ids": len(textgrid_ids),
            "valid_textgrids": valid,
            "invalid_textgrids": inspected - valid,
            "analysis_eligible_textgrids_inspected": eligible_inspected,
            "valid_analysis_eligible_textgrids": eligible_valid,
            "invalid_analysis_eligible_textgrids": (
                eligible_inspected - eligible_valid
            ),
            "excluded_textgrids_inspected": excluded_inspected,
            "valid_excluded_textgrids": excluded_valid,
            "lab_without_textgrid": len(missing_ids),
            "analysis_eligible_lab_without_textgrid": len(
                eligible_missing_ids
            ),
            "textgrid_without_lab": len(extra_textgrid_ids),
            "missing_with_wav": len(missing_ids) - missing_without_wav,
            "missing_without_wav": missing_without_wav,
            "duplicate_lab_ids": len(duplicate_lab_ids),
            "duplicate_textgrid_ids": len(duplicate_textgrid_ids),
            "zero_byte_labs": len(zero_byte_lab_ids),
            "zero_byte_analysis_eligible_labs": len(
                eligible_zero_byte_lab_ids
            ),
            "morph_source_recovery_candidates": len(
                recovery_ids & lab_ids
            ),
            "recovery_candidate_not_valid": len(
                recovery_candidate_not_valid
            ),
            "morph_source_unclassified": len(unclassified_ids & lab_ids),
            "classification_ids_without_lab": len(
                classification_ids_without_lab
            ),
            "spn_phone_intervals": spn_intervals,
        },
        "coverage_pct": round(coverage_pct, 4),
        "raw_coverage_pct": round(raw_coverage_pct, 4),
        "hard_failure_counts": hard_failure_counts,
        "reason_counts": dict(sorted(reason_counts.items())),
        "reason_examples": reason_examples,
        "excluded_reason_counts": dict(
            sorted(excluded_reason_counts.items())
        ),
        "excluded_reason_examples": excluded_reason_examples,
        "morphology_classification": {
            "source_csv": morph_classification["path"],
            "source_fingerprint": morph_classification["fingerprint"],
            "counts_by_action": dict(
                sorted(morph_classification["counts"].items())
            ),
            "analysis_exclusion_action": MORPH_ACTION_EXCLUDE,
            "analysis_exclusion_ids": len(excluded_ids & lab_ids),
            "recovery_candidate_ids": len(recovery_ids & lab_ids),
            "recovery_candidate_not_valid": len(
                recovery_candidate_not_valid
            ),
            "unclassified_ids": len(unclassified_ids & lab_ids),
            "classification_ids_without_lab": len(
                classification_ids_without_lab
            ),
        },
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
            "analysis_eligible_lab_without_textgrid": (
                eligible_missing_ids[:20]
            ),
            "recovery_candidate_not_valid": sorted(
                recovery_candidate_not_valid
            )[:20],
            "classification_ids_without_lab": sorted(
                classification_ids_without_lab
            )[:20],
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
    parser.add_argument(
        "--morph-classification-csv",
        type=Path,
        help=(
            "형태소 원천 결측 발화별 recommended_action CSV. "
            "exclude_source_audio_unusable만 분석 분모에서 제외한다."
        ),
    )
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
        morph_classification_csv=args.morph_classification_csv,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
