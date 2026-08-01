"""CSV 발화 순서와 WAV 길이 연속성으로 음원 ID 복구 계획을 만든다.

읽기 전용 도구다. WAV를 복사·이동·이름 변경하지 않는다. 동일 세션 안에서
밀리초 길이 token의 연속 일치 구간만 찾아, 3개 이상 연속 일치는 고신뢰
후보로, 1~2개 일치는 모호 후보로 분리한다. 이 표는 자동 적용 계약이 아니라
후속 복구·연구자 검토의 입력 증거다.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import wave
from collections import Counter
from pathlib import Path

from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint


SCHEMA_VERSION = "wav_duration_recovery_plan.v1"
RELEVANT_ISSUES = {
    "duration_residual_mismatch",
    "duration_wav_missing",
    "duration_wav_too_small",
    "wav_header_unreadable",
}
FIELDS = (
    "year",
    "session",
    "target_utt_id",
    "source_utt_id",
    "status",
    "block_length",
    "target_duration_seconds",
    "source_duration_seconds",
    "duration_residual_seconds",
    "source_wav",
)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def utterance_sort_key(utt_id: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", utt_id)
    return tuple(int(part) if part.isdigit() else part for part in parts)


def duration_token(seconds: float) -> int:
    return round(seconds * 1000)


def plan_session(
    *,
    year: str,
    session: str,
    csv_rows: list[dict[str, str]],
    wav_dir: Path,
    padding_seconds: float = 0.01,
    minimum_high_confidence_run: int = 3,
) -> list[dict[str, object]]:
    targets = []
    for row in csv_rows:
        utt_id = (row.get("utt_id") or "").strip()
        try:
            seconds = float((row.get("dur") or "").strip())
        except ValueError:
            continue
        if utt_id and seconds > 0:
            targets.append((utt_id, seconds))

    sources = []
    if wav_dir.is_dir():
        for path in sorted(wav_dir.glob("*.wav"), key=lambda p: utterance_sort_key(p.stem)):
            try:
                seconds = wav_duration(path)
            except (OSError, EOFError, wave.Error, ZeroDivisionError):
                continue
            sources.append((path.stem, seconds, path))

    target_tokens = [duration_token(seconds) for _utt, seconds in targets]
    source_tokens = [
        duration_token(seconds - padding_seconds)
        for _utt, seconds, _path in sources
    ]
    matcher = difflib.SequenceMatcher(
        a=target_tokens, b=source_tokens, autojunk=False
    )
    mapped_targets: dict[int, tuple[int, int]] = {}
    mapped_sources: set[int] = set()
    for block in matcher.get_matching_blocks():
        if block.size == 0:
            continue
        for offset in range(block.size):
            target_index = block.a + offset
            source_index = block.b + offset
            mapped_targets[target_index] = (source_index, block.size)
            mapped_sources.add(source_index)

    rows: list[dict[str, object]] = []
    for target_index, (target_utt, target_seconds) in enumerate(targets):
        mapping = mapped_targets.get(target_index)
        if mapping is None:
            rows.append(
                {
                    "year": year,
                    "session": session,
                    "target_utt_id": target_utt,
                    "source_utt_id": "",
                    "status": "target_unresolved",
                    "block_length": 0,
                    "target_duration_seconds": round(target_seconds, 6),
                    "source_duration_seconds": "",
                    "duration_residual_seconds": "",
                    "source_wav": "",
                }
            )
            continue
        source_index, block_length = mapping
        source_utt, source_seconds, source_path = sources[source_index]
        if block_length < minimum_high_confidence_run:
            status = "ambiguous_short_match"
        elif source_utt == target_utt:
            status = "identity_high_confidence"
        else:
            status = "remap_high_confidence"
        rows.append(
            {
                "year": year,
                "session": session,
                "target_utt_id": target_utt,
                "source_utt_id": source_utt,
                "status": status,
                "block_length": block_length,
                "target_duration_seconds": round(target_seconds, 6),
                "source_duration_seconds": round(source_seconds, 6),
                "duration_residual_seconds": round(
                    source_seconds - target_seconds - padding_seconds, 6
                ),
                "source_wav": str(source_path.resolve()),
            }
        )

    for source_index, (source_utt, source_seconds, source_path) in enumerate(sources):
        if source_index in mapped_sources:
            continue
        rows.append(
            {
                "year": year,
                "session": session,
                "target_utt_id": "",
                "source_utt_id": source_utt,
                "status": "source_orphan",
                "block_length": 0,
                "target_duration_seconds": "",
                "source_duration_seconds": round(source_seconds, 6),
                "duration_residual_seconds": "",
                "source_wav": str(source_path.resolve()),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--wav-root", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--padding-seconds", type=float, default=0.01)
    parser.add_argument("--minimum-high-confidence-run", type=int, default=3)
    args = parser.parse_args()

    audit = json.loads(args.audit_report.read_text(encoding="utf-8-sig"))
    year_reports = [
        item for item in audit.get("years", [])
        if str(item.get("year")) == str(args.year)
    ]
    if len(year_reports) != 1:
        raise RuntimeError("감사 보고서 연도 결과가 정확히 1개가 아님")
    sessions = sorted(
        {
            str(issue.get("session") or "").strip()
            for issue in year_reports[0].get("issue_inventory", [])
            if str(issue.get("issue") or "") in RELEVANT_ISSUES
            and str(issue.get("session") or "").strip()
        }
    )
    if not sessions:
        raise RuntimeError("복구 계획 대상 세션이 0개임")

    output_rows: list[dict[str, object]] = []
    for index, session in enumerate(sessions, 1):
        csv_path = args.search_master_root / args.year / f"{session}.csv"
        if not csv_path.is_file():
            raise RuntimeError(f"세션 search CSV 누락: {csv_path}")
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        output_rows.extend(
            plan_session(
                year=str(args.year),
                session=session,
                csv_rows=csv_rows,
                wav_dir=args.wav_root / args.year / session,
                padding_seconds=args.padding_seconds,
                minimum_high_confidence_run=args.minimum_high_confidence_run,
            )
        )
        if index % 25 == 0 or index == len(sessions):
            print(f"[{args.year}] recovery plan {index}/{len(sessions)} sessions")

    with atomic_text_writer(
        args.output_csv.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temporary):
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    status_counts = Counter(str(row["status"]) for row in output_rows)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "dry_run_plan_only",
        "year": str(args.year),
        "mutates_wav": False,
        "audit_report": file_fingerprint(
            args.audit_report.resolve(), with_sha256=True
        ),
        "search_master_root": str(args.search_master_root.resolve()),
        "wav_root": str(args.wav_root.resolve()),
        "padding_seconds": args.padding_seconds,
        "minimum_high_confidence_run": args.minimum_high_confidence_run,
        "session_count": len(sessions),
        "row_count": len(output_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "safe_to_auto_apply": False,
        "next_step": (
            "고신뢰 remap도 표본 음성 확인과 원본 archive 계약 뒤 별도 적용"
        ),
    }
    atomic_write_json(args.output_report.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
