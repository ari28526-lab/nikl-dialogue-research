"""층화 MFA 파일럿의 원출력을 표준 4-tier로 병합하고 전수 QC한다."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import wave
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import atomic_text_writer, atomic_write_json, now_iso  # noqa: E402
from realign_eojeol_merge_output import (  # noqa: E402
    parse_mfa_textgrid,
    validate_4tier,
    write_4tier,
)

QC_FIELDS = [
    "year",
    "speaker_id",
    "session_id",
    "utt_id",
    "status",
    "failure_reason",
    "wav_duration_seconds",
    "textgrid_duration_seconds",
    "duration_difference_seconds",
    "word_intervals",
    "phone_intervals",
    "spn_intervals",
    "spn_interval_pct",
    "spn_duration_seconds",
    "spn_duration_pct",
    "morpheme_intervals",
    "raw_textgrid",
    "final_textgrid",
]
EXPECTED_TIERS = ["words", "phones", "morphemes", "utterance"]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_manifest(run_root: Path) -> list[dict[str, str]]:
    path = run_root / "selection_manifest.csv"
    if not path.is_file():
        raise FileNotFoundError(f"선정 manifest 없음: {path}")
    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=QC_FIELDS, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def find_raw_textgrid(
    run_root: Path, year: str, speaker_id: str, utt_id: str
) -> Path | None:
    expected = (
        run_root / "mfa_raw" / year / speaker_id / f"{utt_id}.TextGrid"
    )
    if expected.is_file():
        return expected
    matches = list((run_root / "mfa_raw" / year).rglob(f"{utt_id}.TextGrid"))
    return matches[0] if len(matches) == 1 else None


def finalize_year(run_root: Path, year: str) -> int:
    manifest = [row for row in read_manifest(run_root) if row["year"] == year]
    if not manifest:
        raise RuntimeError(f"{year} manifest 선택행 0개")
    expected_ids = {row["utt_id"] for row in manifest}
    if len(expected_ids) != len(manifest):
        raise RuntimeError(f"{year} manifest utt_id 중복")
    actual_raw = {
        path.stem for path in (run_root / "mfa_raw" / year).rglob("*.TextGrid")
    }
    extras = sorted(actual_raw - expected_ids)
    missing_raw = sorted(expected_ids - actual_raw)

    qc_rows: list[dict[str, object]] = []
    for row in manifest:
        speaker = row["speaker_id"]
        session = row["session_id"]
        utt_id = row["utt_id"]
        wav_path = run_root / row["corpus_wav_relpath"]
        raw_tg = find_raw_textgrid(run_root, year, speaker, utt_id)
        final_tg = (
            run_root / "textgrid_4tier" / year / speaker / f"{utt_id}.TextGrid"
        )
        qc: dict[str, object] = {
            "year": year,
            "speaker_id": speaker,
            "session_id": session,
            "utt_id": utt_id,
            "status": "failed",
            "failure_reason": "",
            "raw_textgrid": str(raw_tg) if raw_tg else "",
            "final_textgrid": str(final_tg),
        }
        try:
            if raw_tg is None:
                raise RuntimeError("MFA 원 TextGrid 누락 또는 중복 위치")
            duration, tiers = parse_mfa_textgrid(raw_tg)
            words = tiers.get("words", [])
            phones = tiers.get("phones", [])
            if duration is None or duration <= 0 or not words or not phones:
                raise RuntimeError("MFA words/phones/duration 누락")
            morph_source = Path(row["source_morpheme_textgrid"])
            if not morph_source.is_file():
                raise RuntimeError(f"형태소 TextGrid 원본 누락: {morph_source}")
            _, morph_tiers = parse_mfa_textgrid(morph_source)
            morphemes = morph_tiers.get("words", [])
            if not morphemes:
                raise RuntimeError("기존 형태소 TextGrid의 words tier가 비어 있음")

            if final_tg.exists():
                validation = validate_4tier(final_tg, expected_dur=duration)
                if not validation["valid"]:
                    raise RuntimeError(
                        "기존 최종 TextGrid가 손상됨(자동 덮어쓰기 금지): "
                        + "; ".join(validation["reasons"])
                    )
            else:
                write_4tier(
                    final_tg,
                    duration,
                    words,
                    phones,
                    morphemes,
                    row["form"],
                )
            validation = validate_4tier(final_tg, expected_dur=duration)
            if not validation["valid"]:
                raise RuntimeError(
                    "4-tier 검증 실패: " + "; ".join(validation["reasons"])
                )
            final_duration, final_tiers = parse_mfa_textgrid(final_tg)
            tier_names = list(final_tiers)
            if tier_names != EXPECTED_TIERS:
                raise RuntimeError(
                    f"tier 순서 불일치: {tier_names} != {EXPECTED_TIERS}"
                )
            wav_dur = wav_duration(wav_path)
            diff = abs(wav_dur - float(final_duration))
            if diff > 0.02:
                raise RuntimeError(
                    f"WAV/TextGrid 길이 차이 {diff:.6f}s > 0.02s"
                )
            phone_rows = final_tiers["phones"]
            spn_rows = [
                interval for interval in phone_rows
                if interval[2].strip().lower() == "spn"
            ]
            phone_duration = sum(
                end - start for start, end, label in phone_rows if label.strip()
            )
            spn_duration = sum(end - start for start, end, _ in spn_rows)
            labeled_phone_count = sum(1 for _, _, label in phone_rows if label.strip())
            qc.update({
                "status": "passed",
                "wav_duration_seconds": round(wav_dur, 6),
                "textgrid_duration_seconds": round(float(final_duration), 6),
                "duration_difference_seconds": round(diff, 6),
                "word_intervals": len(final_tiers["words"]),
                "phone_intervals": labeled_phone_count,
                "spn_intervals": len(spn_rows),
                "spn_interval_pct": round(
                    100 * len(spn_rows) / labeled_phone_count, 4
                ) if labeled_phone_count else "",
                "spn_duration_seconds": round(spn_duration, 6),
                "spn_duration_pct": round(
                    100 * spn_duration / phone_duration, 4
                ) if phone_duration else "",
                "morpheme_intervals": len(final_tiers["morphemes"]),
            })
        except Exception as exc:  # 발화별 실패를 모두 기록한 뒤 연도 단위 실패
            qc["failure_reason"] = f"{type(exc).__name__}: {exc}"
        qc_rows.append(qc)

    qc_dir = run_root / "qc"
    write_csv(qc_dir / f"{year}_utterance_qc.csv", qc_rows)
    passed = sum(row["status"] == "passed" for row in qc_rows)
    failed = len(qc_rows) - passed
    report = {
        "schema_version": 1,
        "checked_at": now_iso(),
        "year": year,
        "expected_utterances": len(manifest),
        "manifest_speakers": len({row["speaker_id"] for row in manifest}),
        "manifest_sessions": len({row["session_id"] for row in manifest}),
        "raw_textgrids_found": len(actual_raw),
        "raw_missing": missing_raw,
        "raw_extra": extras,
        "passed": passed,
        "failed": failed,
        "spn_intervals": sum(
            int(row.get("spn_intervals") or 0) for row in qc_rows
        ),
        "status": (
            "passed"
            if passed == len(manifest) and not extras and not missing_raw
            else "failed"
        ),
        "qc_csv": str(qc_dir / f"{year}_utterance_qc.csv"),
    }
    atomic_write_json(qc_dir / f"{year}_summary.json", report)
    print(
        f"[{year}] QC {report['status']}: passed={passed}/{len(manifest)}, "
        f"raw_missing={len(missing_raw)}, raw_extra={len(extras)}, "
        f"spn={report['spn_intervals']}",
        flush=True,
    )
    return 0 if report["status"] == "passed" else 1


def summarize(run_root: Path, years: list[str]) -> int:
    reports = []
    for year in years:
        path = run_root / "qc" / f"{year}_summary.json"
        if not path.is_file():
            raise FileNotFoundError(f"연도 QC 요약 없음: {path}")
        reports.append(json.loads(path.read_text(encoding="utf-8-sig")))
    manifest = read_manifest(run_root)
    status = "passed" if all(r["status"] == "passed" for r in reports) else "failed"
    totals = {
        "expected": sum(r["expected_utterances"] for r in reports),
        "passed": sum(r["passed"] for r in reports),
        "failed": sum(r["failed"] for r in reports),
        "spn_intervals": sum(r["spn_intervals"] for r in reports),
    }
    summary = {
        "schema_version": 1,
        "completed_at": now_iso(),
        "run_root": str(run_root),
        "years": years,
        "status": status,
        "totals": totals,
        "year_reports": reports,
    }
    atomic_write_json(run_root / "pilot_summary.json", summary)

    speaker_counts = Counter((row["year"], row["speaker_id"]) for row in manifest)
    lines = [
        "# 연도별 10발화·5화자 MFA 파일럿 결과",
        "",
        f"- 완료 시각: {summary['completed_at']}",
        f"- 실행 폴더: `{run_root}`",
        f"- 전체 판정: **{status.upper()}**",
        f"- 발화: {totals['passed']}/{totals['expected']} QC 통과",
        f"- G2P 정렬 phones의 `spn` interval: {totals['spn_intervals']}",
        "",
        "## 연도별 결과",
        "",
        "| 연도 | 실제 화자 | 원 세션 | 발화 | QC 통과 | spn | 판정 |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for report in reports:
        lines.append(
            f"| {report['year']} | {report['manifest_speakers']} | "
            f"{report['manifest_sessions']} | {report['expected_utterances']} | "
            f"{report['passed']} | {report['spn_intervals']} | "
            f"{report['status']} |"
        )
    lines.extend([
        "",
        "## 표본 균형",
        "",
        "모든 연도에서 CSV `speaker_id` 기준 5명, 화자당 2발화이며 각 화자는 "
        "서로 다른 원 세션에서 선택한다.",
        "",
        "| 연도 | 화자별 발화 수 |",
        "|---:|---|",
    ])
    for year in years:
        counts = sorted(
            (speaker, count)
            for (item_year, speaker), count in speaker_counts.items()
            if item_year == year
        )
        lines.append(
            f"| {year} | "
            + ", ".join(f"{speaker}={count}" for speaker, count in counts)
            + " |"
        )
    lines.extend([
        "",
        "## 해석 주의",
        "",
        "`phones`와 `spn`은 MFA/G2P 정렬 인프라의 운영·분절 지표이며, "
        "음운 현상의 실제 실현 판정값이 아니다. 최종 실현 여부는 연구자가 "
        "WAV와 TextGrid를 직접 검토해 판정한다.",
        "",
        "선택된 관련 CSV는 `csv/{연도}`에, WAV·lab은 `corpus`, MFA 원출력은 "
        "`mfa_raw`, 표준 4-tier는 `textgrid_4tier`, 발화별 검증표는 `qc`에 있다.",
        "",
    ])
    with atomic_text_writer(
        run_root / "RESULTS.md", encoding="utf-8", newline="\n"
    ) as (stream, _):
        stream.write("\n".join(lines))
    print(f"전체 결과: {run_root / 'RESULTS.md'} ({status})", flush=True)
    return 0 if status == "passed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--year")
    group.add_argument("--summarize", action="store_true")
    parser.add_argument(
        "--years",
        nargs="+",
        default=["2020", "2021", "2022", "2023", "2024", "2025"],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_root = args.run_root.resolve()
    if args.summarize:
        return summarize(run_root, args.years)
    return finalize_year(run_root, args.year)


if __name__ == "__main__":
    raise SystemExit(main())
