"""연도별 lab과 검증된 TextGrid staging의 차집합을 재시도 목록으로 고정한다."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path


def iter_files(root: Path, suffix: str):
    suffix_lower = suffix.lower()
    for directory, _subdirs, filenames in os.walk(root):
        base = Path(directory)
        for filename in filenames:
            if filename.lower().endswith(suffix_lower):
                yield base / filename


def build_inventory(
    *,
    year: str,
    lab_root: Path,
    textgrid_root: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    textgrid_ids: set[str] = set()
    duplicate_textgrid_ids: set[str] = set()
    for path in iter_files(textgrid_root, ".TextGrid"):
        utt_id = path.stem
        if utt_id in textgrid_ids:
            duplicate_textgrid_ids.add(utt_id)
        textgrid_ids.add(utt_id)

    lab_ids: set[str] = set()
    duplicate_lab_ids: set[str] = set()
    missing: list[dict[str, object]] = []
    for lab_path in iter_files(lab_root, ".lab"):
        utt_id = lab_path.stem
        if utt_id in lab_ids:
            duplicate_lab_ids.add(utt_id)
        lab_ids.add(utt_id)
        if utt_id in textgrid_ids:
            continue
        wav_path = lab_path.with_suffix(".wav")
        missing.append(
            {
                "year": year,
                "session_id": lab_path.parent.name,
                "utt_id": utt_id,
                "reason": "no_textgrid_after_beam10_retry40",
                "lab_path": str(lab_path),
                "lab_bytes": lab_path.stat().st_size,
                "wav_path": str(wav_path),
                "wav_exists": wav_path.is_file(),
            }
        )

    missing.sort(key=lambda row: str(row["utt_id"]))
    textgrid_without_lab = sorted(textgrid_ids - lab_ids)
    report = {
        "year": year,
        "lab_root": str(lab_root),
        "textgrid_root": str(textgrid_root),
        "lab_ids": len(lab_ids),
        "textgrid_ids": len(textgrid_ids),
        "lab_without_textgrid": len(missing),
        "textgrid_without_lab": len(textgrid_without_lab),
        "textgrid_without_lab_examples": textgrid_without_lab[:20],
        "duplicate_lab_ids": len(duplicate_lab_ids),
        "duplicate_textgrid_ids": len(duplicate_textgrid_ids),
        "missing_with_wav": sum(bool(row["wav_exists"]) for row in missing),
        "missing_without_wav": sum(not bool(row["wav_exists"]) for row in missing),
        "status": "success"
        if not duplicate_lab_ids
        and not duplicate_textgrid_ids
        and not textgrid_without_lab
        else "review",
    }
    return missing, report


def atomic_write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--lab-root", required=True, type=Path)
    parser.add_argument("--textgrid-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-missing", type=int)
    args = parser.parse_args()

    missing, report = build_inventory(
        year=args.year,
        lab_root=args.lab_root.resolve(),
        textgrid_root=args.textgrid_root.resolve(),
    )
    if (
        args.expected_missing is not None
        and len(missing) != args.expected_missing
    ):
        report["status"] = "failed"
        report["expected_missing"] = args.expected_missing
        report["failure"] = (
            f"missing mismatch: expected={args.expected_missing} "
            f"actual={len(missing)}"
        )

    output = args.output.resolve()
    atomic_write_csv(output, missing)
    report["output_csv"] = str(output)
    report_path = output.with_suffix(".json")
    atomic_write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
