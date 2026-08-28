#!/usr/bin/env python3
"""Independently audit the Bareun WSD CSV pilot and source immutability."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PILOT = Path(
    "D:/10_LAYERS/11_bareun_wsd/bareun_wsd_full_20260828/pilot_p1_20260828"
)
DEFAULT_REPORT = PROJECT_ROOT / "outputs" / "reports" / "AUDIT_bareun_wsd_pilot_p1_20260828.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-root", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    errors: list[str] = []
    manifest_path = args.pilot_root / "PILOT_MANIFEST.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    utterances = read_csv(args.pilot_root / "utterances.csv")
    morphs = read_csv(args.pilot_root / "morphemes.csv")
    senses = read_csv(args.pilot_root / "sense_dictionary.csv")

    if len(utterances) != 240:
        errors.append("utterance_count_not_240")
    if len({row["utt_id"] for row in utterances}) != len(utterances):
        errors.append("duplicate_utt_id")
    year_counts = {
        year: sum(row["year"] == year for row in utterances)
        for year in [str(value) for value in range(2020, 2026)]
    }
    if any(count != 40 for count in year_counts.values()):
        errors.append("year_balance_not_40")
    if any(not row["form"] or int(row["response_morph_count"]) <= 0 for row in utterances):
        errors.append("empty_or_unanalyzed_utterance")
    morph_counts: dict[str, int] = {}
    for row in morphs:
        morph_counts[row["utt_id"]] = morph_counts.get(row["utt_id"], 0) + 1
    for row in utterances:
        if morph_counts.get(row["utt_id"], 0) != int(row["response_morph_count"]):
            errors.append("morph_count_mismatch")
            break
    sense_keys = [row["sense_key"] for row in senses]
    if len(sense_keys) != len(set(sense_keys)):
        errors.append("duplicate_sense_key")
    if not senses:
        errors.append("no_wsd_senses_returned")

    for name, contract in manifest["outputs"].items():
        path = args.pilot_root / name
        if not path.is_file():
            errors.append(f"missing_output:{name}")
            continue
        if path.stat().st_size != contract["bytes"]:
            errors.append(f"output_size_mismatch:{name}")
        if sha256_file(path) != contract["sha256"]:
            errors.append(f"output_sha_mismatch:{name}")
    for source in manifest["source_contracts"]:
        source_path = Path("D:/10_LAYERS/01_bareun_raw") / source["source_file"]
        current_sha = sha256_file(source_path)
        if current_sha != source["sha256_before"] or current_sha != source["sha256_after"]:
            errors.append(f"protected_source_changed:{source['source_file']}")

    counts: dict[str, Any] = {
        "utterances": len(utterances),
        "morphemes": len(morphs),
        "unique_senses": len(senses),
        "year_counts": year_counts,
    }
    report = {
        "schema": "bareun_wsd_csv_pilot_audit.v1",
        "passed": not errors,
        "pilot_root": str(args.pilot_root),
        "counts": counts,
        "estimated_full_uncompressed_gib": manifest["estimated_full_uncompressed_gib"],
        "estimated_full_compressed_gib": manifest["estimated_full_compressed_gib"],
        "protected_csv_unchanged": not any(
            error.startswith("protected_source_changed") for error in errors
        ),
        "textgrid_or_wav_accessed": False,
        "errors": errors,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
