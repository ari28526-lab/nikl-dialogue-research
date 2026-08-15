#!/usr/bin/env python3
"""Build a six-year, one-utterance-per-year r3 inspection bundle.

The selected utterance for each year is the first SDRW row in the independent
QC sample whose semantic and byte comparisons both passed.  The script copies
the final WAV and research 6-tier TextGrid and extracts the corresponding full
row from the annual utterance companion table.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import unicodedata
import wave
from pathlib import Path

from praatio import textgrid


EXPECTED_TIERS = [
    "words",
    "phones_mfa",
    "phoneme_r_auto",
    "utterance",
    "utterance_orth_r",
    "morph_analysis_utt",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def choose_qc_sample(qc_csv: Path, year: int) -> dict[str, str]:
    with qc_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        for row in rows:
            if (
                int(row["year"]) == year
                and row["utt_id"].startswith("SDRW")
                and row["status"] == "exact_match"
                and as_bool(row["semantic_equal"])
                and as_bool(row["byte_equal"])
            ):
                return row
    raise RuntimeError(f"{year}: passed SDRW QC sample not found: {qc_csv}")


def find_companion_row(table_path: Path, utt_id: str) -> tuple[list[str], dict[str, str]]:
    with gzip.open(table_path, "rt", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if rows.fieldnames is None:
            raise RuntimeError(f"missing CSV header: {table_path}")
        for row in rows:
            if row["utt_id"] == utt_id:
                return list(rows.fieldnames), row
    raise RuntimeError(f"companion row not found: {utt_id} in {table_path}")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def validate_textgrid(path: Path, expected_form: str, expected_duration: float) -> dict[str, object]:
    grid = textgrid.openTextgrid(str(path), includeEmptyIntervals=True)
    tier_names = list(grid.tierNames)
    if tier_names != EXPECTED_TIERS:
        raise RuntimeError(f"unexpected tiers for {path}: {tier_names}")

    utterance_tier = grid.getTier("utterance")
    labels = [entry.label for entry in utterance_tier.entries if entry.label.strip()]
    if len(labels) != 1:
        raise RuntimeError(f"expected one non-empty utterance interval for {path}: {labels}")
    if nfc(labels[0]) != nfc(expected_form):
        raise RuntimeError(
            f"utterance label mismatch for {path}: {labels[0]!r} != {expected_form!r}"
        )
    if abs(float(grid.maxTimestamp) - expected_duration) > 1e-6:
        raise RuntimeError(
            f"TextGrid/WAV duration mismatch for {path}: "
            f"{grid.maxTimestamp} != {expected_duration}"
        )
    return {
        "tier_names": " | ".join(tier_names),
        "utterance_label": labels[0],
        "textgrid_xmax_seconds": f"{float(grid.maxTimestamp):.9f}",
    }


def write_single_row_csv(
    output_path: Path, fieldnames: list[str], row: dict[str, str]
) -> None:
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def write_manifest(output_path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "year",
        "utt_id",
        "session_id",
        "utterance",
        "wav_duration_seconds",
        "tier_names",
        "qc_status",
        "qc_semantic_equal",
        "qc_byte_equal",
        "wav_file",
        "textgrid_file",
        "csv_file",
        "wav_sha256",
        "textgrid_sha256",
        "csv_sha256",
        "source_wav_path",
        "source_textgrid_path",
        "source_companion_table",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_readme(output_path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2020–2025 MFA r3 연도별 최종 표본",
        "",
        "각 연도 독립 QC에서 TextGrid의 semantic·byte 재생성이 모두 일치한 SDRW 발화",
        "한 건을 골랐다. 각 발화는 WAV 1개, 최종 6-tier TextGrid 1개, 해당 발화의",
        "`utterance_alignment` 전체 1행 CSV 1개로 구성된다.",
        "",
        "CSV에는 원문·형태소·Roman·예측/참조 발음·MFA 발음·화자·세션·경로·정렬",
        "수량·계약 ID가 포함된다. CSV의 MFA/예측 발음은 실제 실현을 자동 판정한 값이",
        "아니며, 실제 실현은 WAV와 TextGrid를 함께 보고 연구자가 판단한다.",
        "",
        "## 표본",
        "",
        "| 연도 | utt_id | 발화 | 길이(초) |",
        "|---:|---|---|---:|",
    ]
    for row in rows:
        utterance = str(row["utterance"]).replace("|", "\\|")
        lines.append(
            f"| {row['year']} | `{row['utt_id']}` | {utterance} | "
            f"{row['wav_duration_seconds']} |"
        )
    lines.extend(
        [
            "",
            "`SAMPLES_MANIFEST.csv`에는 복사본과 원본 경로, SHA-256, QC 상태가 있다.",
            "원본 r3 DB·TextGrid·WAV는 변경하지 않았으며 이 폴더는 검토용 복사본이다.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build(args: argparse.Namespace) -> dict[str, object]:
    release_root = args.release_root.resolve()
    qc_root = args.qc_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"output directory is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    for year in range(2020, 2026):
        qc_csv = qc_root / str(year) / "02_db_sample.csv"
        qc_row = choose_qc_sample(qc_csv, year)
        utt_id = qc_row["utt_id"]
        session_id = qc_row["session"]

        companion_table = (
            release_root
            / "research_6tier"
            / str(year)
            / "_tables"
            / "utterance_alignment.csv.gz"
        )
        fieldnames, companion_row = find_companion_row(companion_table, utt_id)
        if int(companion_row["year"]) != year:
            raise RuntimeError(f"year mismatch for {utt_id}")
        if companion_row["align_status"] != "aligned" or companion_row["n_spn"] != "0":
            raise RuntimeError(f"sample is not cleanly aligned: {utt_id}")

        source_wav = Path(companion_row["source_wav_path"])
        source_textgrid = Path(qc_row["final_path"])
        if not source_wav.is_file() or not source_textgrid.is_file():
            raise RuntimeError(f"missing source asset for {utt_id}")

        duration = wav_duration(source_wav)
        companion_duration = float(companion_row["wav_duration_seconds"])
        if abs(duration - companion_duration) > 1e-6:
            raise RuntimeError(
                f"companion/WAV duration mismatch for {utt_id}: "
                f"{companion_duration} != {duration}"
            )
        grid_info = validate_textgrid(source_textgrid, companion_row["form"], duration)
        source_textgrid_sha = sha256(source_textgrid)
        if source_textgrid_sha != qc_row["final_sha256"]:
            raise RuntimeError(f"QC TextGrid hash mismatch for {utt_id}")

        prefix = f"{year}_{utt_id}"
        copied_wav = output_root / f"{prefix}.wav"
        copied_textgrid = output_root / f"{prefix}.TextGrid"
        copied_csv = output_root / f"{prefix}.csv"
        shutil.copy2(source_wav, copied_wav)
        shutil.copy2(source_textgrid, copied_textgrid)
        write_single_row_csv(copied_csv, fieldnames, companion_row)

        if sha256(copied_wav) != sha256(source_wav):
            raise RuntimeError(f"WAV copy hash mismatch for {utt_id}")
        if sha256(copied_textgrid) != source_textgrid_sha:
            raise RuntimeError(f"TextGrid copy hash mismatch for {utt_id}")

        manifest_rows.append(
            {
                "year": year,
                "utt_id": utt_id,
                "session_id": session_id,
                "utterance": companion_row["form"],
                "wav_duration_seconds": f"{duration:.6f}",
                "tier_names": grid_info["tier_names"],
                "qc_status": qc_row["status"],
                "qc_semantic_equal": qc_row["semantic_equal"],
                "qc_byte_equal": qc_row["byte_equal"],
                "wav_file": copied_wav.name,
                "textgrid_file": copied_textgrid.name,
                "csv_file": copied_csv.name,
                "wav_sha256": sha256(copied_wav),
                "textgrid_sha256": sha256(copied_textgrid),
                "csv_sha256": sha256(copied_csv),
                "source_wav_path": str(source_wav),
                "source_textgrid_path": str(source_textgrid),
                "source_companion_table": str(companion_table),
            }
        )

    manifest_path = output_root / "SAMPLES_MANIFEST.csv"
    readme_path = output_root / "README.md"
    write_manifest(manifest_path, manifest_rows)
    write_readme(readme_path, manifest_rows)
    result = {
        "status": "passed",
        "output_root": str(output_root),
        "years": 6,
        "asset_files": 18,
        "manifest": str(manifest_path),
        "readme": str(readme_path),
        "samples": manifest_rows,
    }
    (output_root / "BUILD_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release-root",
        type=Path,
        default=Path(r"D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809"),
    )
    parser.add_argument(
        "--qc-root",
        type=Path,
        default=Path(
            r"C:\Users\ari30\research\2026_summer_research\outputs\reports"
            r"\mfa_r3_research_qc_common_pron_mfa_r3_20260809"
        ),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
