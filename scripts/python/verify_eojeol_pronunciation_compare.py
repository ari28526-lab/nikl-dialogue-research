"""Independently verify an eojeol pronunciation comparison table."""
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
from build_eojeol_pronunciation_compare import (  # noqa: E402
    OUTPUT_FIELDS,
    compare_roman,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


SCHEMA_VERSION = "verify_eojeol_pronunciation_compare.v1"
JSON_ARRAY_FIELDS = (
    "morph_surfaces_pos_json",
    "morph_candidate_group_ids_json",
    "morph_dict_match_statuses_json",
    "morph_dict_preferred_source_tiers_json",
    "morph_dict_resolution_statuses_json",
    "morph_dict_preferred_pron_hangul_json",
    "morph_dict_preferred_pron_roman_search_json",
)

csv.field_size_limit(20_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def verify(args: argparse.Namespace) -> dict:
    started = time.perf_counter()
    source_path = args.orth_eojeol_tokens.resolve()
    compare_path = args.compare.resolve()
    manifest_path = args.compare_manifest.resolve()
    report_path = args.output_report.resolve()
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    errors: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    rows = 0
    if manifest.get("status") != "success":
        errors["manifest_not_success"] += 1
    if str(manifest.get("year")) != str(args.year):
        errors["manifest_year_mismatch"] += 1
    if manifest.get("coverage_complete") is not True:
        errors["manifest_coverage_not_complete"] += 1

    with gzip.open(
        source_path, "rt", encoding="utf-8-sig", newline=""
    ) as source_stream, gzip.open(
        compare_path, "rt", encoding="utf-8-sig", newline=""
    ) as compare_stream:
        source_reader = csv.DictReader(source_stream)
        compare_reader = csv.DictReader(compare_stream)
        missing = set(OUTPUT_FIELDS) - set(compare_reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"compare output fields missing: {sorted(missing)}")
        for row_number, pair in enumerate(
            zip_longest(source_reader, compare_reader), 1
        ):
            source, compared = pair
            if source is None:
                errors["extra_compare_rows"] += 1
                continue
            if compared is None:
                errors["missing_compare_rows"] += 1
                continue
            rows += 1
            for source_field, compare_field in (
                ("utt_id", "utt_id"),
                ("year", "year"),
                ("orth_eojeol_idx", "eojeol_idx"),
                ("orth_eojeol_count", "eojeol_count"),
                ("orth_eojeol_form", "eojeol_form"),
                ("orth_eojeol_roman_v2", "eojeol_roman_v2"),
                ("linked_morph_eojeol_idx", "linked_morph_eojeol_idx"),
                ("morph_link_status", "morph_link_status"),
            ):
                if clean(source.get(source_field)) != clean(
                    compared.get(compare_field)
                ):
                    errors[f"identity_mismatch_{compare_field}"] += 1

            try:
                arrays = {
                    field: json.loads(compared[field])
                    for field in JSON_ARRAY_FIELDS
                }
            except (json.JSONDecodeError, TypeError):
                errors["invalid_json_array"] += 1
                continue
            if any(not isinstance(value, list) for value in arrays.values()):
                errors["json_value_not_array"] += 1
                continue
            morph_count = int(compared["morph_count_in_eojeol"])
            if any(len(value) != morph_count for value in arrays.values()):
                errors["morph_json_array_length_mismatch"] += 1
            linked = bool(clean(compared["linked_morph_eojeol_idx"]))
            if linked != (morph_count > 0):
                errors["morph_link_count_contract_mismatch"] += 1
            if not linked and clean(compared["dict_layer_status"]) != "morph_coordinate_not_linked":
                errors["unlinked_morph_status_mismatch"] += 1

            recomputed = compare_roman(
                compared["pron_rule_roman"], compared["pron_mfa_r_auto"]
            )
            if recomputed != clean(compared["rule_mfa_roman_compare_status"]):
                errors["rule_mfa_compare_status_mismatch"] += 1
            status = clean(compared["pron_audit_status"])
            statuses[status] += 1
            for issue in clean(compared["pron_audit_issue_codes"]).split("|"):
                if issue.strip():
                    issues[issue.strip()] += 1
            if args.progress_every and row_number % args.progress_every == 0:
                print(
                    f"[{args.year}] independently verified "
                    f"{row_number:,} eojeol rows",
                    flush=True,
                )

    if rows != int(manifest.get("counts", {}).get("eojeol_rows", -1)):
        errors["manifest_row_count_mismatch"] += 1
    manifest_statuses = {
        key.removeprefix("audit_"): int(value)
        for key, value in manifest.get("counts", {}).items()
        if key.startswith("audit_")
    }
    if dict(sorted(statuses.items())) != dict(sorted(manifest_statuses.items())):
        errors["manifest_audit_counts_mismatch"] += 1
    manifest_issues = {
        key.removeprefix("issue_"): int(value)
        for key, value in manifest.get("counts", {}).items()
        if key.startswith("issue_")
    }
    if dict(sorted(issues.items())) != dict(sorted(manifest_issues.items())):
        errors["manifest_issue_counts_mismatch"] += 1

    compare_fp = file_fingerprint(compare_path, with_sha256=True)
    expected_fp = manifest.get("outputs", {}).get("compare", {})
    if int(compare_fp["bytes"]) != int(expected_fp.get("bytes", -1)):
        errors["manifest_bytes_mismatch"] += 1
    if compare_fp["sha256"] != expected_fp.get("sha256"):
        errors["manifest_sha256_mismatch"] += 1
    partials = sorted(
        str(path)
        for path in compare_path.parent.glob("*.partial")
        if path.is_file()
    )
    if partials:
        errors["partial_files_present"] += len(partials)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if not errors else "failed",
        "recorded_at": now_iso(),
        "year": str(args.year),
        "method": (
            "simultaneous full-row scan against orth_eojeol_tokens; exact "
            "coordinate/text identity, structured morph arrays, rule/MFA "
            "comparison recomputation, manifest counts/SHA, and partial checks"
        ),
        "rows_verified": rows,
        "audit_status_counts": dict(sorted(statuses.items())),
        "issue_counts": dict(sorted(issues.items())),
        "error_counts": dict(sorted(errors.items())),
        "partial_files": partials,
        "inputs": {
            "orth_eojeol_tokens": file_fingerprint(
                source_path, with_sha256=True
            ),
            "compare": compare_fp,
            "compare_manifest": file_fingerprint(
                manifest_path, with_sha256=True
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if errors:
        raise RuntimeError(f"eojeol compare verification failed: {dict(errors)}")
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--year", required=True)
    result.add_argument("--orth-eojeol-tokens", type=Path, required=True)
    result.add_argument("--compare", type=Path, required=True)
    result.add_argument("--compare-manifest", type=Path, required=True)
    result.add_argument("--output-report", type=Path, required=True)
    result.add_argument("--progress-every", type=int, default=500_000)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.progress_every < 0:
        raise ValueError("--progress-every must be non-negative")
    verify(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
