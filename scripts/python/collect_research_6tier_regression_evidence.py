"""Collect compact, tracked evidence from local post-review regression roots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import atomic_write_json, now_iso, sha256_file
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid

SCHEMA_VERSION = "mfa_research_6tier_post_review_evidence.v1"


def _files(root: Path, pattern: str) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob(pattern))
        if path.is_file()
    }


def collect(
    *,
    legacy_root: Path,
    candidate_root: Path,
    repeat_root: Path,
    parquet_root: Path,
    benchmark_report: Path,
    output: Path,
) -> dict[str, object]:
    roots = [legacy_root, candidate_root, repeat_root, parquet_root]
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError(root)
    reports = [
        json.loads(path.read_text(encoding="utf-8-sig"))
        for path in sorted((candidate_root / "reports").glob("*.json"))
    ]
    if len(reports) != 6 or any(row.get("status") != "success" for row in reports):
        raise RuntimeError("candidate annual reports are not six successful reports")
    legacy_tg = _files(legacy_root, "*.TextGrid")
    candidate_tg = _files(candidate_root, "*.TextGrid")
    tg_missing = sorted(set(legacy_tg) ^ set(candidate_tg))
    orth_label_changes: list[str] = []
    non_orth_mismatches: list[str] = []
    for key in sorted(set(legacy_tg) & set(candidate_tg)):
        old_duration, old_tiers = parse_mfa_textgrid(legacy_tg[key])
        new_duration, new_tiers = parse_mfa_textgrid(candidate_tg[key])
        if old_duration != new_duration or list(old_tiers) != list(new_tiers):
            non_orth_mismatches.append(key)
            continue
        changed = [
            name for name in old_tiers
            if old_tiers[name] != new_tiers[name]
        ]
        if changed == ["utterance_orth_r"]:
            orth_label_changes.append(key)
        elif changed:
            non_orth_mismatches.append(key)
    repeat_tg = _files(repeat_root, "*.TextGrid")
    repeat_tg_mismatch = sorted(
        key for key in set(candidate_tg) | set(repeat_tg)
        if key not in candidate_tg or key not in repeat_tg
        or sha256_file(candidate_tg[key]) != sha256_file(repeat_tg[key])
    )
    first_gzip = _files(candidate_root, "*.csv.gz")
    repeat_gzip = _files(repeat_root, "*.csv.gz")
    gzip_mismatch = sorted(
        key for key in set(first_gzip) | set(repeat_gzip)
        if key not in first_gzip or key not in repeat_gzip
        or sha256_file(first_gzip[key]) != sha256_file(repeat_gzip[key])
    )
    roundtrip_reports = [
        json.loads(path.read_text(encoding="utf-8-sig"))
        for path in sorted((parquet_root / "roundtrip").glob("*.json"))
    ]
    benchmark = json.loads(benchmark_report.read_text(encoding="utf-8-sig"))
    candidate_files = [path for path in candidate_root.rglob("*") if path.is_file()]
    counts = {
        "utterances": sum(int(row["companion_tables"]["counts"]["utterances"]) for row in reports),
        "word_intervals": sum(int(row["companion_tables"]["counts"]["word_intervals"]) for row in reports),
        "phone_intervals": sum(int(row["companion_tables"]["counts"]["phone_intervals"]) for row in reports),
        "spn_intervals": sum(int(row["counts"].get("spn_intervals", 0)) for row in reports),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "success" if (
            not tg_missing and not non_orth_mismatches
            and not repeat_tg_mismatch and not gzip_mismatch
            and len(roundtrip_reports) == 6
            and all(row.get("status") == "success" for row in roundtrip_reports)
            and benchmark.get("status") == "success"
        ) else "failed",
        "collected_at": now_iso(),
        "mfa_executed": False,
        "counts": counts,
        "candidate_output": {
            "files": len(candidate_files),
            "bytes": sum(path.stat().st_size for path in candidate_files),
            "active_partial_files": sum(path.name.endswith(".partial") for path in candidate_files),
        },
        "legacy_textgrid_comparison": {
            "compared": len(legacy_tg),
            "missing_or_extra_count": len(tg_missing),
            "intentional_orth_roman_v2_label_changes": len(orth_label_changes),
            "non_orth_tier_mismatch_count": len(non_orth_mismatches),
            "changed_orth_files": orth_label_changes,
            "non_orth_mismatches": non_orth_mismatches,
        },
        "repeat_textgrid_comparison": {
            "compared": len(candidate_tg),
            "sha256_mismatch_count": len(repeat_tg_mismatch),
            "mismatches": repeat_tg_mismatch,
        },
        "deterministic_gzip_comparison": {
            "compared": len(first_gzip),
            "sha256_mismatch_count": len(gzip_mismatch),
            "mismatches": gzip_mismatch,
        },
        "parquet_roundtrip": {
            "year_reports": len(roundtrip_reports),
            "tables": sum(len(row.get("tables", {})) for row in roundtrip_reports),
            "failed_years": [
                row.get("source_manifest", {}).get("path")
                for row in roundtrip_reports if row.get("status") != "success"
            ],
        },
        "synthetic_10k_benchmark": benchmark,
        "evidence_roots": {
            "legacy": str(legacy_root.resolve()),
            "candidate": str(candidate_root.resolve()),
            "repeat": str(repeat_root.resolve()),
            "parquet": str(parquet_root.resolve()),
            "benchmark": str(benchmark_report.resolve()),
        },
    }
    atomic_write_json(output.resolve(), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--repeat-root", type=Path, required=True)
    parser.add_argument("--parquet-root", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(**vars(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
