"""Independently audit a pronunciation-reference TextGrid backfill.

The auditor scans every completed session checkpoint and companion row.  It
compares each derived TextGrid with its read-only six-tier source and confirms
that only the seventh ``pron_reference_utt`` tier was added.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402
import research_textgrid_v2 as textgrid_v2  # noqa: E402


SCHEMA_VERSION = "verify_pron_reference_textgrid_backfill.v1"
OUTPUT_SCHEMA_VERSION = "research_textgrid_pron_reference.v1"
TIER_NAME = "pron_reference_utt"


def clean(value: str | None) -> str:
    return (value or "").strip()


def add_error(errors: Counter, key: str, examples: dict[str, list[str]], value: str):
    errors[key] += 1
    if len(examples.setdefault(key, [])) < 10:
        examples[key].append(value)


def verify(args: argparse.Namespace) -> dict:
    started = time.perf_counter()
    year = str(args.year)
    source_root = args.source_textgrid_root.resolve()
    output_root = args.output_root.resolve()
    year_root = output_root / year
    checkpoint_root = year_root / "_checkpoints"
    errors: Counter = Counter()
    counts: Counter = Counter()
    examples: dict[str, list[str]] = {}
    contract_ids: set[str] = set()
    expected_output_paths: set[Path] = set()

    if not checkpoint_root.is_dir():
        raise FileNotFoundError(checkpoint_root)
    checkpoints = sorted(checkpoint_root.glob("*.json"))
    if not checkpoints:
        raise RuntimeError(f"no completed session checkpoints: {checkpoint_root}")
    for checkpoint_path in checkpoints:
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            add_error(errors, "checkpoint_unreadable", examples, f"{checkpoint_path}: {exc}")
            continue
        session_id = clean(checkpoint.get("session_id"))
        contract_ids.add(clean(checkpoint.get("backfill_contract_id")))
        if checkpoint.get("status") != "success" or not session_id:
            add_error(errors, "checkpoint_contract_invalid", examples, str(checkpoint_path))
            continue
        session_root = year_root / session_id
        table_path = session_root / "pron_reference_utterance.csv.gz"
        recorded_table = checkpoint.get("session_table", {})
        if not table_path.is_file():
            add_error(errors, "session_table_missing", examples, str(table_path))
            continue
        table_fp = file_fingerprint(table_path, with_sha256=True)
        if table_fp.get("sha256") != recorded_table.get("sha256"):
            add_error(errors, "session_table_sha_mismatch", examples, str(table_path))
        table_rows = 0
        with gzip.open(table_path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                table_rows += 1
                counts["companion_rows"] += 1
                utt_id = clean(row.get("utt_id"))
                if clean(row.get("year")) != year or clean(row.get("session_id")) != session_id:
                    add_error(errors, "companion_identity_mismatch", examples, utt_id)
                    continue
                source_relative = Path(clean(row.get("source_textgrid_relative_path")))
                output_relative = Path(clean(row.get("output_textgrid_relative_path")))
                if (
                    source_relative.is_absolute()
                    or output_relative.is_absolute()
                    or ".." in source_relative.parts
                    or ".." in output_relative.parts
                ):
                    add_error(errors, "unsafe_relative_path", examples, utt_id)
                    continue
                source_path = source_root / source_relative
                output_path = output_root / output_relative
                expected_output_paths.add(output_path.resolve())
                if not source_path.is_file() or not output_path.is_file():
                    add_error(errors, "textgrid_missing", examples, utt_id)
                    continue
                try:
                    source_duration, source_tiers = parse_mfa_textgrid(source_path)
                    output_duration, output_tiers = parse_mfa_textgrid(output_path)
                    if source_duration is None or output_duration is None:
                        raise ValueError("missing duration")
                    if abs(float(source_duration) - float(output_duration)) > 1e-6:
                        raise ValueError("duration differs")
                    if list(source_tiers) != textgrid_v2.BASE_TIERS:
                        raise ValueError("source six-tier order differs")
                    if list(output_tiers) != textgrid_v2.BASE_TIERS + [TIER_NAME]:
                        raise ValueError("output seven-tier order differs")
                    for tier_name in textgrid_v2.BASE_TIERS:
                        if not textgrid_v2._same_intervals(
                            source_tiers[tier_name], output_tiers[tier_name]
                        ):
                            raise ValueError(f"source tier changed: {tier_name}")
                    if not textgrid_v2._same_edges(
                        output_tiers["utterance"], output_tiers[TIER_NAME]
                    ):
                        raise ValueError("seventh-tier edges differ")
                    if not textgrid_v2._continuous(
                        output_tiers[TIER_NAME], float(output_duration)
                    ):
                        raise ValueError("seventh tier is not continuous")
                    labels = [clean(item[2]) for item in output_tiers[TIER_NAME] if clean(item[2])]
                    if labels != [clean(row.get("pron_reference_utt_label"))]:
                        raise ValueError("seventh-tier label differs")
                except Exception as exc:  # retain all audit failures in one report
                    add_error(errors, "textgrid_semantic_mismatch", examples, f"{utt_id}: {exc}")
                    continue
                counts["textgrids_semantically_verified"] += 1
        expected_session_rows = int(checkpoint.get("counts", {}).get("textgrids", -1))
        observed_session_files = sum(1 for _ in session_root.glob("*.TextGrid"))
        if table_rows != expected_session_rows or observed_session_files != expected_session_rows:
            add_error(
                errors,
                "session_count_mismatch",
                examples,
                f"{session_id}: table={table_rows}, files={observed_session_files}, expected={expected_session_rows}",
            )
        counts["sessions_verified"] += 1

    if len(contract_ids) != 1 or "" in contract_ids:
        add_error(errors, "multiple_or_blank_contract_ids", examples, repr(sorted(contract_ids)))
    actual_output_paths = {
        path.resolve()
        for session_root in year_root.iterdir()
        if session_root.is_dir() and not session_root.name.startswith("_")
        for path in session_root.glob("*.TextGrid")
    }
    extra = actual_output_paths - expected_output_paths
    missing = expected_output_paths - actual_output_paths
    if extra:
        add_error(errors, "untracked_output_textgrid", examples, str(next(iter(extra))))
        errors["untracked_output_textgrid"] += len(extra) - 1
    if missing:
        add_error(errors, "tracked_output_textgrid_missing", examples, str(next(iter(missing))))
        errors["tracked_output_textgrid_missing"] += len(missing) - 1
    staging_root = year_root / "_session_staging"
    partials = sorted(staging_root.glob("*.partial")) if staging_root.is_dir() else []
    if partials:
        errors["partial_session_directories"] = len(partials)
        examples["partial_session_directories"] = [str(path) for path in partials[:10]]

    status = "passed" if not errors else "failed"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "recorded_at": now_iso(),
        "year": year,
        "scope": "all checkpointed sessions under output root",
        "method": (
            "independent checkpoint/session-table scan; exact first-six-tier semantic "
            "comparison; seventh-tier order, boundary, continuity, and label verification"
        ),
        "backfill_contract_ids": sorted(contract_ids),
        "counts": dict(counts),
        "error_counts": dict(errors),
        "error_examples": examples,
        "inputs": {
            "source_textgrid_root": str(source_root),
            "output_root": str(output_root),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    if args.report:
        atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--year", required=True)
    result.add_argument("--source-textgrid-root", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    result.add_argument("--report", type=Path)
    return result


def main() -> int:
    return 0 if verify(parser().parse_args())["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
