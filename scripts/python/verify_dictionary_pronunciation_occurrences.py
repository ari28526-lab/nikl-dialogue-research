"""Independently verify annual morphology-to-pronunciation occurrence links."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter
from itertools import zip_longest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


SCHEMA_VERSION = "verify_morph_dictionary_pronunciation_occurrences.v1"
IDENTITY_FIELDS = (
    "utt_id",
    "year",
    "eojeol_idx",
    "morph_idx_in_eojeol",
    "morph_idx_in_utterance",
    "morph_surface",
    "pos",
)
OUTPUT_REQUIRED = set(IDENTITY_FIELDS) | {
    "candidate_group_id",
    "dict_match_status",
    "sense_match_status",
}

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def verify(args: argparse.Namespace) -> dict:
    started = time.perf_counter()
    morph_path = args.morph_tokens.resolve()
    occurrence_path = args.occurrences.resolve()
    manifest_path = args.occurrence_manifest.resolve()
    report_path = args.output_report.resolve()

    manifest = load_json(manifest_path)
    errors: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    rows = 0

    if manifest.get("status") != "success":
        errors["manifest_not_success"] += 1
    if str(manifest.get("year")) != args.year:
        errors["manifest_year_mismatch"] += 1
    if manifest.get("coverage_complete") is not True:
        errors["manifest_coverage_not_complete"] += 1

    with gzip.open(
        morph_path, "rt", encoding="utf-8-sig", newline=""
    ) as morph_stream, gzip.open(
        occurrence_path, "rt", encoding="utf-8-sig", newline=""
    ) as occurrence_stream:
        morph_reader = csv.DictReader(morph_stream)
        occurrence_reader = csv.DictReader(occurrence_stream)
        missing_morph = set(IDENTITY_FIELDS) - set(
            morph_reader.fieldnames or ()
        )
        missing_output = OUTPUT_REQUIRED - set(
            occurrence_reader.fieldnames or ()
        )
        if missing_morph or missing_output:
            raise RuntimeError(
                "required columns missing: "
                f"morph={sorted(missing_morph)}, "
                f"occurrences={sorted(missing_output)}"
            )

        for row_number, pair in enumerate(
            zip_longest(morph_reader, occurrence_reader), 1
        ):
            morph_row, occurrence_row = pair
            if morph_row is None:
                errors["extra_occurrence_rows"] += 1
                continue
            if occurrence_row is None:
                errors["missing_occurrence_rows"] += 1
                continue
            rows += 1
            for field in IDENTITY_FIELDS:
                if clean(morph_row.get(field)) != clean(
                    occurrence_row.get(field)
                ):
                    errors[f"identity_mismatch_{field}"] += 1

            status = clean(occurrence_row.get("dict_match_status"))
            group_id = clean(occurrence_row.get("candidate_group_id"))
            sense_status = clean(occurrence_row.get("sense_match_status"))
            statuses[status] += 1
            matched = status == "matched_exact_surface_pos"
            if matched != bool(group_id):
                errors["group_id_match_contract_mismatch"] += 1
            expected_sense = (
                "corpus_sense_unavailable" if matched else "not_linked"
            )
            if sense_status != expected_sense:
                errors["sense_status_contract_mismatch"] += 1
            if clean(occurrence_row.get("year")) != args.year:
                errors["row_year_mismatch"] += 1

            if args.progress_every and row_number % args.progress_every == 0:
                print(
                    f"[{args.year}] independently verified "
                    f"{row_number:,} rows",
                    flush=True,
                )

    expected_rows = int(manifest.get("counts", {}).get("rows", -1))
    if rows != expected_rows:
        errors["manifest_row_count_mismatch"] += 1
    manifest_statuses = {
        key.removeprefix("status_"): int(value)
        for key, value in manifest.get("counts", {}).items()
        if key.startswith("status_")
    }
    if dict(sorted(statuses.items())) != dict(sorted(manifest_statuses.items())):
        errors["manifest_status_counts_mismatch"] += 1

    occurrence_fp = file_fingerprint(occurrence_path, with_sha256=True)
    expected_fp = manifest.get("outputs", {}).get("occurrences", {})
    if int(occurrence_fp["bytes"]) != int(expected_fp.get("bytes", -1)):
        errors["manifest_bytes_mismatch"] += 1
    if occurrence_fp["sha256"] != expected_fp.get("sha256"):
        errors["manifest_sha256_mismatch"] += 1

    partials = sorted(
        str(path)
        for path in occurrence_path.parent.glob("*.partial")
        if path.is_file()
    )
    if partials:
        errors["partial_files_present"] += len(partials)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if not errors else "failed",
        "recorded_at": now_iso(),
        "year": args.year,
        "method": (
            "independent simultaneous full-row scan of morph input and "
            "occurrence output; identity, link-state, manifest count, byte, "
            "SHA-256, and partial-file checks"
        ),
        "rows_verified": rows,
        "status_counts": dict(sorted(statuses.items())),
        "error_counts": dict(sorted(errors.items())),
        "partial_files": partials,
        "inputs": {
            "morph_tokens": file_fingerprint(morph_path, with_sha256=True),
            "occurrences": occurrence_fp,
            "occurrence_manifest": file_fingerprint(
                manifest_path, with_sha256=True
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if errors:
        raise RuntimeError(f"occurrence verification failed: {dict(errors)}")
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--year", required=True)
    result.add_argument("--morph-tokens", type=Path, required=True)
    result.add_argument("--occurrences", type=Path, required=True)
    result.add_argument("--occurrence-manifest", type=Path, required=True)
    result.add_argument("--output-report", type=Path, required=True)
    result.add_argument("--progress-every", type=int, default=1_000_000)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.progress_every < 0:
        raise ValueError("--progress-every must be non-negative")
    verify(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
