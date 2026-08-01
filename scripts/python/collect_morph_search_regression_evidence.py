"""Collect compact evidence for the 2020–2025 morph-search regression."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from build_morph_position_tables import sha256_file
from build_morph_search_year_sharded import atomic_write_json


def read_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def collect(candidate_root: Path, repeat_root: Path) -> dict[str, object]:
    candidate_root = candidate_root.resolve()
    repeat_root = repeat_root.resolve()
    totals: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    mismatches: list[dict[str, str]] = []
    count_mismatch_utterances = 0
    target_symbol: dict[str, str] | None = None
    years: dict[str, dict[str, object]] = {}

    for year in map(str, range(2020, 2026)):
        left_root = candidate_root / year / "annual_tables"
        right_root = repeat_root / year / "annual_tables"
        left = json.loads(
            (left_root / "YEAR_MANIFEST.json").read_text(encoding="utf-8-sig")
        )
        right = json.loads(
            (right_root / "YEAR_MANIFEST.json").read_text(encoding="utf-8-sig")
        )
        if left.get("status") != "success" or right.get("status") != "success":
            raise RuntimeError(f"{year}: regression manifest not successful")
        if left.get("versions") != right.get("versions"):
            raise RuntimeError(f"{year}: version mismatch between repeats")
        if set(left["tables"]) != set(right["tables"]):
            raise RuntimeError(f"{year}: table inventory mismatch")
        for table_name, info in left["tables"].items():
            other = right["tables"][table_name]
            totals[table_name] += int(info["rows"])
            left_path = left_root / str(info["path"])
            right_path = right_root / str(other["path"])
            left_sha = sha256_file(left_path)
            right_sha = sha256_file(right_path)
            if left_sha != info["sha256"] or right_sha != other["sha256"]:
                raise RuntimeError(f"{year}/{table_name}: manifest SHA mismatch")
            if left_sha != right_sha:
                mismatches.append(
                    {"year": year, "table": table_name, "left": left_sha, "right": right_sha}
                )

        for row in read_rows(left_root / "utterance_master_v2.csv.gz"):
            if str(row["form_tagged_eojeol_count_equal"]).lower() != "true":
                count_mismatch_utterances += 1
        for row in read_rows(left_root / "symbol_readings.csv.gz"):
            status_counts[row["reading_status"]] += 1
            if (
                row["utt_id"] == "SARW2500000414.1.1.2"
                and row["symbol_surface"] == "2"
            ):
                target_symbol = row
        years[year] = {
            "utterances": int(left["tables"]["master"]["rows"]),
            "tables": len(left["tables"]),
            "symbol_rows": int(left["tables"]["symbol_readings"]["rows"]),
            "orth_eojeol_rows": int(left["tables"]["orth_eojeol_tokens"]["rows"]),
            "morph_eojeol_rows": int(left["tables"]["eojeol_tokens"]["rows"]),
        }

    if totals["master"] != 60:
        raise RuntimeError(f"expected 60 utterances, got {totals['master']}")
    if mismatches:
        raise RuntimeError(f"deterministic gzip mismatch: {mismatches}")
    if target_symbol is None:
        raise RuntimeError("target 2사람이 symbol row missing")
    candidates = json.loads(target_symbol["reading_candidates_json"])
    if (
        target_symbol["reference_reading"] != "두"
        or "둘" not in candidates
        or target_symbol["reading_status"]
        != "resolved_reference_transcription"
    ):
        raise RuntimeError("2사람이 symbol reading contract mismatch")

    return {
        "schema_version": "morph_search_v3_regression_evidence.v1",
        "status": "success",
        "collected_at": datetime.now().astimezone().isoformat(),
        "mfa_executed": False,
        "scope": "2020-2025, 10 utterances per year from existing text pilot inputs",
        "versions": json.loads(
            (
                candidate_root / "2020" / "annual_tables" / "YEAR_MANIFEST.json"
            ).read_text(encoding="utf-8-sig")
        )["versions"],
        "years": years,
        "totals": dict(sorted(totals.items())),
        "form_tagged_count_mismatch_utterances": count_mismatch_utterances,
        "symbol_statuses": dict(sorted(status_counts.items())),
        "deterministic_gzip": {
            "compared_tables": 42,
            "sha256_mismatch_count": 0,
        },
        "target_symbol_example": {
            "utt_id": target_symbol["utt_id"],
            "source_eojeol": target_symbol["source_eojeol"],
            "symbol_surface": target_symbol["symbol_surface"],
            "reference_form": target_symbol["reference_form"],
            "selected_reading": target_symbol["reference_reading"],
            "candidate_readings": candidates,
            "reading_source": target_symbol["reading_source"],
            "reading_status": target_symbol["reading_status"],
        },
        "candidate_root": str(candidate_root),
        "repeat_root": str(repeat_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--repeat-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = collect(args.candidate_root, args.repeat_root)
    atomic_write_json(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
