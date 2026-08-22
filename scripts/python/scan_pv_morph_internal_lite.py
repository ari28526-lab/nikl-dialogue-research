"""Bounded PV-A scan for adjacent Hangul syllables inside one morpheme.

This is an environment preview only.  It never reads audio, runs MFA, or
decides whether a process was realized.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from pv_preview_common import (
    DEFAULT_CONFIG,
    DEFAULT_MORPH_ROOT,
    PROJECT_ROOT,
    annual_table_contract,
    atomic_write_csv,
    atomic_write_json,
    base_build_receipt,
    load_json,
    physical_occurrence_ref,
    require_under,
    session_from_utt,
    source_receipt,
    validate_config,
    validate_header,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PT_CODAS = {"ㄱ", "ㄲ", "ㅋ", "ㄳ", "ㄺ", "ㄷ", "ㅅ", "ㅆ", "ㅈ", "ㅊ", "ㅌ", "ㅂ", "ㅍ", "ㅄ", "ㄼ", "ㄿ"}
PT_ONSETS = {"ㄱ", "ㄷ", "ㅂ", "ㅅ", "ㅈ"}
OUTPUT_FIELDS = [
    "query_id",
    "query_version",
    "query_role",
    "phenomenon_code",
    "environment_scope",
    "year",
    "utt_id",
    "session_id",
    "matched_table",
    "occurrence_index",
    "physical_occurrence_ref",
    "match_evidence_json",
]


def same_morph(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return (
        left.get("utt_id") == right.get("utt_id")
        and left.get("eojeol_idx") == right.get("eojeol_idx")
        and left.get("morph_idx_in_eojeol") == right.get("morph_idx_in_eojeol")
        and left.get("morph_idx_in_utterance") == right.get("morph_idx_in_utterance")
        and int(right.get("unit_idx_in_morph", "0"))
        == int(left.get("unit_idx_in_morph", "0")) + 1
    )


def rule_matches(rule: str, left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    if left.get("unit_type") != "hangul" or right.get("unit_type") != "hangul":
        return False
    coda = left.get("coda_jamo", "")
    onset = right.get("onset_jamo", "")
    if rule == "pt":
        return coda in PT_CODAS and onset in PT_ONSETS
    if rule == "nan":
        return coda in PT_CODAS and onset == "ㄴ"
    if rule == "nal":
        return coda in PT_CODAS and onset == "ㄹ"
    if rule == "lln":
        return (coda, onset) in {("ㄴ", "ㄹ"), ("ㄹ", "ㄴ")}
    raise RuntimeError(f"unsupported internal rule: {rule}")


def evidence(left: Mapping[str, str], right: Mapping[str, str]) -> dict[str, str]:
    return {
        "boundary_scope": "morph_internal",
        "eojeol_idx": left["eojeol_idx"],
        "left_eojeol_idx": left["eojeol_idx"],
        "right_eojeol_idx": right["eojeol_idx"],
        "morph_idx_in_eojeol": left["morph_idx_in_eojeol"],
        "morph_idx_in_utterance": left["morph_idx_in_utterance"],
        "morph_surface": left["morph_surface"],
        "pos": left["pos"],
        "left_unit_idx_in_morph": left["unit_idx_in_morph"],
        "right_unit_idx_in_morph": right["unit_idx_in_morph"],
        "left_unit_surface": left["unit_surface"],
        "right_unit_surface": right["unit_surface"],
        "left_unit_type": left["unit_type"],
        "right_unit_type": right["unit_type"],
        "left_coda_jamo": left["coda_jamo"],
        "right_onset_jamo": right["onset_jamo"],
        "position_schema_version": left.get("position_schema_version", ""),
    }


def scan_year(
    *,
    morph_root: Path,
    year: int,
    rules: list[dict[str, Any]],
    row_cap: int,
    candidate_cap: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    path, record, annual_manifest = annual_table_contract(
        morph_root, year, "morph_units"
    )
    measured_header = validate_header(path, "morph_units")
    rows: list[dict[str, str]] = []
    counts: dict[str, int] = defaultdict(int)
    rows_scanned = 0
    pair_rows_evaluated = 0
    previous: dict[str, str] | None = None
    stop_reason = "hard_row_cap"
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for current in reader:
            rows_scanned += 1
            if previous is not None and same_morph(previous, current):
                pair_rows_evaluated += 1
                for spec in rules:
                    query_id = str(spec["query_id"])
                    if counts[query_id] >= candidate_cap:
                        continue
                    if not rule_matches(str(spec["rule"]), previous, current):
                        continue
                    session_id = session_from_utt(current["utt_id"])
                    occurrence_index = (
                        f"{current['morph_idx_in_utterance']}:"
                        f"{previous['unit_idx_in_morph']}-"
                        f"{current['unit_idx_in_morph']}"
                    )
                    rows.append(
                        {
                            "query_id": query_id,
                            "query_version": str(spec["query_version"]),
                            "query_role": str(spec["query_role"]),
                            "phenomenon_code": str(spec["phenomenon_code"]),
                            "environment_scope": "morph_internal",
                            "year": str(year),
                            "utt_id": current["utt_id"],
                            "session_id": session_id,
                            "matched_table": "morph_units_pair",
                            "occurrence_index": occurrence_index,
                            "physical_occurrence_ref": physical_occurrence_ref(
                                "morph_units_pair",
                                year,
                                current["utt_id"],
                                occurrence_index,
                            ),
                            "match_evidence_json": json.dumps(
                                evidence(previous, current),
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        }
                    )
                    counts[query_id] += 1
            previous = dict(current)
            if all(counts[str(spec["query_id"])] >= candidate_cap for spec in rules):
                stop_reason = "all_query_candidate_caps_reached"
                break
            if rows_scanned >= row_cap:
                break
    receipt = source_receipt(
        path,
        record,
        annual_manifest,
        rows_scanned=rows_scanned,
        stopped_at_row_cap=rows_scanned >= row_cap,
    )
    receipt.update(
        {
            "year": year,
            "table": "morph_units",
            "measured_header": measured_header,
            "pair_rows_evaluated": pair_rows_evaluated,
            "candidate_counts": dict(sorted(counts.items())),
            "candidate_rows": len([row for row in rows if int(row["year"]) == year]),
            "stop_reason": stop_reason,
        }
    )
    return rows, receipt


def preflight(config_path: Path, morph_root: Path) -> dict[str, Any]:
    config = load_json(config_path)
    validate_config(config)
    measured = []
    for year in config["pilot_allocation"]["years"]:
        path, record, manifest_path = annual_table_contract(
            morph_root, int(year), "morph_units"
        )
        measured.append(
            {
                "year": int(year),
                "path": str(path),
                "bytes": int(record["bytes"]),
                "declared_sha256": record["sha256"],
                "annual_manifest_sha256": source_receipt(
                    path, record, manifest_path
                )["annual_manifest_sha256"],
                "measured_header": validate_header(path, "morph_units"),
            }
        )
    return {
        "status": "preflight_passed_no_scan",
        "config": str(config_path),
        "row_cap": config["safety"]["max_rows_scanned_per_table_year"],
        "sources": measured,
    }


def build(
    *, config_path: Path, morph_root: Path, output_dir: Path
) -> dict[str, Any]:
    require_under(output_dir, PROJECT_ROOT / "outputs" / "pilots")
    config = load_json(config_path)
    validate_config(config)
    output_csv = output_dir / "PV_INTERNAL_CANDIDATES.csv"
    output_json = output_dir / "PV_INTERNAL_SCAN.json"
    for path in (output_csv, output_json):
        if path.exists():
            raise FileExistsError(f"existing output is never overwritten: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    row_cap = int(config["safety"]["max_rows_scanned_per_table_year"])
    candidate_cap = int(
        config["safety"]["max_materialized_candidates_per_query_year"]
    )
    rules = list(config["internal_rules"])
    all_rows: list[dict[str, str]] = []
    receipts = []
    for year in config["pilot_allocation"]["years"]:
        rows, receipt = scan_year(
            morph_root=morph_root,
            year=int(year),
            rules=rules,
            row_cap=row_cap,
            candidate_cap=candidate_cap,
        )
        all_rows.extend(rows)
        receipts.append(receipt)
    atomic_write_csv(output_csv, OUTPUT_FIELDS, all_rows)
    manifest = {
        "schema_version": "pv_morph_internal_lite_scan.v1",
        "status": "completed_preview_candidates_no_realization_judgement",
        **base_build_receipt(config_path),
        "counts": {
            "candidate_rows": len(all_rows),
            "query_year": {
                f"{query_id}|{year}": sum(
                    row["query_id"] == query_id and int(row["year"]) == year
                    for row in all_rows
                )
                for query_id in sorted({row["query_id"] for row in all_rows})
                for year in config["pilot_allocation"]["years"]
            },
        },
        "sources": receipts,
        "output": {
            "path": str(output_csv),
            "bytes": output_csv.stat().st_size,
        },
    }
    atomic_write_json(output_json, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--morph-root", type=Path, default=DEFAULT_MORPH_ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.preflight_only:
            result = preflight(args.config.resolve(), args.morph_root.resolve())
        else:
            if args.output_dir is None:
                parser.error("--output-dir is required unless --preflight-only")
            result = build(
                config_path=args.config.resolve(),
                morph_root=args.morph_root.resolve(),
                output_dir=args.output_dir.resolve(),
            )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
