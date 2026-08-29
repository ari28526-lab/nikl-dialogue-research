#!/usr/bin/env python3
"""Independently audit the Bareun v3.1 morphology TextGrid pilot."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from pipeline_common import now_iso, sha256_file  # noqa: E402
from research_textgrid_v2 import (  # noqa: E402
    BASE_TIERS,
    normalize_search_label_for_textgrid,
    parse_mfa_textgrid,
)


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_morph_textgrid_pilot_v1.json"
FIRST_FIVE = BASE_TIERS[:5]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def same_intervals(left: Sequence[tuple], right: Sequence[tuple], tolerance: float = 1e-6) -> bool:
    return len(left) == len(right) and all(
        abs(float(a[0]) - float(b[0])) <= tolerance
        and abs(float(a[1]) - float(b[1])) <= tolerance
        and str(a[2]) == str(b[2])
        for a, b in zip(left, right)
    )


def same_edges(left: Sequence[tuple], right: Sequence[tuple], tolerance: float = 1e-6) -> bool:
    return len(left) == len(right) and all(
        abs(float(a[0]) - float(b[0])) <= tolerance
        and abs(float(a[1]) - float(b[1])) <= tolerance
        for a, b in zip(left, right)
    )


def one_label(intervals: Sequence[tuple]) -> str:
    labels = [str(row[2]) for row in intervals if str(row[2])]
    if len(labels) != 1:
        raise ValueError("tier does not have exactly one labeled interval")
    return labels[0]


def read_gzip_rows(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def reconstruct_label(rows: Sequence[Mapping[str, str]], expected_tokens: int) -> str:
    grouped: dict[int, list[tuple[int, str]]] = defaultdict(list)
    morph_indices: list[int] = []
    for row in rows:
        token_index = int(row["token_index"])
        morph_index = int(row["morph_index"])
        grouped[token_index].append(
            (morph_index, f"{row['morph_surface']}/{row['pos']}")
        )
        morph_indices.append(morph_index)
    if sorted(grouped) != list(range(expected_tokens)):
        raise ValueError("token indices mismatch")
    if sorted(morph_indices) != list(range(len(morph_indices))):
        raise ValueError("morph indices mismatch")
    return normalize_search_label_for_textgrid(
        " | ".join(
            " + ".join(value for _, value in sorted(grouped[token]))
            for token in range(expected_tokens)
        )
    )


def audit(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    final_root = resolve_path(config["input"]["bareun_final_root"])
    output_root = resolve_path(config["output"]["root"])
    errors: list[str] = []
    join_path = output_root / "PILOT_JOIN.csv"
    with join_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    inventory = dict(
        line.split("\t", 1)
        for line in (final_root / "RECEIPT_INVENTORY.tsv")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    )
    category_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    source_shas_after: dict[str, str] = {}
    for row in rows:
        utt_id = row["utt_id"]
        year_counts[row["year"]] += 1
        category_counts[row["category"]] += 1
        try:
            source = Path(row["source_textgrid"])
            derived = output_root / row["derived_relative"]
            current_source_sha = sha256_file(source)
            source_shas_after[str(source.resolve())] = current_source_sha
            if current_source_sha != row["source_textgrid_sha256"]:
                errors.append(f"source_textgrid_changed:{utt_id}")
            if sha256_file(derived) != row["derived_textgrid_sha256"]:
                errors.append(f"derived_textgrid_sha_mismatch:{utt_id}")
            source_duration, source_tiers = parse_mfa_textgrid(source)
            derived_duration, derived_tiers = parse_mfa_textgrid(derived)
            if source_duration is None or derived_duration is None:
                errors.append(f"duration_missing:{utt_id}")
            elif abs(float(source_duration) - float(derived_duration)) > 1e-6:
                errors.append(f"duration_changed:{utt_id}")
            if list(source_tiers) != BASE_TIERS or list(derived_tiers) != BASE_TIERS:
                errors.append(f"tier_contract_mismatch:{utt_id}")
            if not all(
                same_intervals(source_tiers[name], derived_tiers[name])
                for name in FIRST_FIVE
            ):
                errors.append(f"protected_first_five_changed:{utt_id}")
            if not same_edges(
                source_tiers["morph_analysis_utt"],
                derived_tiers["morph_analysis_utt"],
            ):
                errors.append(f"morph_boundary_changed:{utt_id}")

            receipt_relative = row["receipt_relative"]
            receipt_path = final_root / receipt_relative
            if inventory.get(receipt_relative) != row["receipt_sha256"]:
                errors.append(f"receipt_inventory_mismatch:{utt_id}")
            if sha256_file(receipt_path) != row["receipt_sha256"]:
                errors.append(f"receipt_sha_mismatch:{utt_id}")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            utterance_path = final_root / row["utterances_relative"]
            morpheme_path = final_root / row["morphemes_relative"]
            for name, path in (
                ("utterances.csv.gz", utterance_path),
                ("morphemes.csv.gz", morpheme_path),
            ):
                contract = receipt["outputs"][name]
                if path.stat().st_size != int(contract["bytes"]):
                    errors.append(f"bareun_output_size_mismatch:{utt_id}:{name}")
                elif sha256_file(path) != contract["sha256"]:
                    errors.append(f"bareun_output_sha_mismatch:{utt_id}:{name}")
            utterance_rows = [
                item for item in read_gzip_rows(utterance_path) if item["utt_id"] == utt_id
            ]
            morph_rows = [
                item for item in read_gzip_rows(morpheme_path) if item["utt_id"] == utt_id
            ]
            if len(utterance_rows) != 1:
                errors.append(f"utterance_cardinality:{utt_id}")
                continue
            expected_tokens = int(utterance_rows[0]["response_token_count"])
            reconstructed = reconstruct_label(morph_rows, expected_tokens)
            derived_label = one_label(derived_tiers["morph_analysis_utt"])
            source_label = one_label(source_tiers["morph_analysis_utt"])
            if derived_label != reconstructed or derived_label != row["new_label"]:
                errors.append(f"new_morph_label_mismatch:{utt_id}")
            actual_category = "changed" if source_label != reconstructed else "unchanged"
            if actual_category != row["category"]:
                errors.append(f"selection_category_mismatch:{utt_id}")
            if hashlib.sha256(source_label.encode("utf-8")).hexdigest() != row["old_label_sha256"]:
                errors.append(f"old_label_hash_mismatch:{utt_id}")
            if hashlib.sha256(reconstructed.encode("utf-8")).hexdigest() != row["new_label_sha256"]:
                errors.append(f"new_label_hash_mismatch:{utt_id}")
            labeled_words = sum(
                1 for _, _, label in source_tiers["words"] if str(label)
            )
            if labeled_words != expected_tokens:
                errors.append(f"word_token_count_mismatch:{utt_id}")
        except Exception as exc:  # fail closed while retaining the exact sample ID
            errors.append(f"exception:{utt_id}:{type(exc).__name__}:{exc}")

    expected_years = [str(value) for value in config["input"]["expected_years"]]
    if len(rows) != 12:
        errors.append("sample_count_mismatch")
    if set(year_counts) != set(expected_years) or any(year_counts[y] != 2 for y in expected_years):
        errors.append("year_balance_mismatch")
    if category_counts != Counter({"changed": 6, "unchanged": 6}):
        errors.append("change_balance_mismatch")

    checksum_path = output_root / "SHA256SUMS.txt"
    checksum_rows = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected_sha, relative = line.split("\t", 1)
        checksum_rows.append(relative)
        path = output_root / relative
        if not path.is_file() or sha256_file(path) != expected_sha:
            errors.append(f"package_checksum_mismatch:{relative}")
    expected_checksum_files = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS.txt"
    }
    if set(checksum_rows) != expected_checksum_files:
        errors.append("package_checksum_inventory_mismatch")

    todo = (output_root / "USER_TODO.md").read_text(encoding="utf-8")
    if todo.count("답변: `") != int(config["selection"]["user_review_cases"]):
        errors.append("user_todo_case_count_mismatch")
    build_receipt = json.loads(
        (output_root / "BUILD_RECEIPT.json").read_text(encoding="utf-8")
    )
    if build_receipt.get("source_textgrid_modified") is not False:
        errors.append("source_textgrid_preservation_contract_missing")
    if build_receipt.get("source_wav_accessed") is not False:
        errors.append("unexpected_wav_access")
    if build_receipt.get("mfa_rerun") is not False:
        errors.append("unexpected_mfa_rerun")

    report = {
        "schema": "bareun_morph_textgrid_pilot_audit.v1",
        "audited_at": now_iso(),
        "passed": not errors,
        "sample_count": len(rows),
        "year_counts": dict(sorted(year_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "source_textgrids_unchanged": not any(
            error.startswith("source_textgrid_changed") for error in errors
        ),
        "first_five_tiers_semantically_unchanged": not any(
            error.startswith("protected_first_five_changed") for error in errors
        ),
        "morph_tier_boundaries_unchanged": not any(
            error.startswith("morph_boundary_changed") for error in errors
        ),
        "new_morph_labels_match_bareun_v3_1": not any(
            error.startswith("new_morph_label_mismatch") for error in errors
        ),
        "source_wav_accessed": False,
        "mfa_rerun": False,
        "user_review_cases": int(config["selection"]["user_review_cases"]),
        "estimated_full_textgrid_gib": build_receipt["estimated_full_textgrid_gib"],
        "free_d_gib_before": build_receipt["free_d_gib_before"],
        "estimated_free_d_gib_after": build_receipt["estimated_free_d_gib_after"],
        "errors": errors,
    }
    report_path = resolve_path(config["output"]["audit_report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    report = audit(args.config.resolve())
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
