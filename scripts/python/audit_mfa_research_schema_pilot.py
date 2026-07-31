"""60발화 새 검색 스키마·TextGrid의 전수 교차 검증."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from pipeline_common import atomic_write_json
from research_textgrid import validate_research_textgrid
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def semantically_equal(
    left: list[tuple[float, float, str]],
    right: list[tuple[float, float, str]],
    tolerance: float = 1e-6,
) -> bool:
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if (
            abs(float(a[0]) - float(b[0])) > tolerance
            or abs(float(a[1]) - float(b[1])) > tolerance
            or str(a[2]) != str(b[2])
        ):
            return False
    return True


def load_search_row(
    run_root: Path, year: str, session: str, utt_id: str
) -> dict[str, str]:
    path = run_root / "search_master" / year / f"{session}.csv"
    matches = [
        row for row in read_rows(path) if row.get("utt_id") == utt_id
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{path}: {utt_id} 검색 행 수={len(matches)}"
        )
    return matches[0]


def audit(
    *,
    run_root: Path,
    new_textgrid_root: Path,
    morph_root: Path,
) -> dict[str, object]:
    run_root = run_root.resolve()
    new_textgrid_root = new_textgrid_root.resolve()
    morph_root = morph_root.resolve()
    selection = read_rows(run_root / "selection_manifest.csv")
    morph_master = read_rows(morph_root / "utterance_master_v2.csv")
    master_by_id = {row["utt_id"]: row for row in morph_master}
    counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    year_counts: Counter[str] = Counter()
    seen: set[str] = set()
    for selected in selection:
        year = selected["year"]
        session = selected["session_id"]
        utt_id = selected["utt_id"]
        counts["selected"] += 1
        year_counts[year] += 1
        if utt_id in seen:
            errors.append({"utt_id": utt_id, "error": "selection 중복"})
            continue
        seen.add(utt_id)
        try:
            search_row = load_search_row(
                run_root, year, session, utt_id
            )
            if utt_id not in master_by_id:
                raise RuntimeError("morph master 행 누락")
            new_path = (
                new_textgrid_root / year / session / f"{utt_id}.TextGrid"
            )
            old_path = (
                run_root
                / "textgrid_4tier"
                / year
                / session
                / f"{utt_id}.TextGrid"
            )
            validation = validate_research_textgrid(
                new_path, expected_row=search_row
            )
            if not validation["valid"]:
                raise RuntimeError(
                    "new TextGrid invalid: "
                    + "; ".join(validation["reasons"])
                )
            counts["new_textgrid_valid"] += 1
            counts["left_empty_boundary"] += bool(
                validation["left_empty_boundary"]
            )
            counts["right_empty_boundary"] += bool(
                validation["right_empty_boundary"]
            )
            old_duration, old_tiers = parse_mfa_textgrid(old_path)
            new_duration, new_tiers = parse_mfa_textgrid(new_path)
            if abs(float(old_duration) - float(new_duration)) > 1e-6:
                raise RuntimeError("old/new duration 불일치")
            if not semantically_equal(
                old_tiers["words"], new_tiers["words"]
            ):
                raise RuntimeError("old/new words 불일치")
            if not semantically_equal(
                old_tiers["phones"], new_tiers["phones_mfa"]
            ):
                raise RuntimeError("old/new phones 불일치")
            counts["word_phone_semantic_equal"] += 1
            if (
                master_by_id[utt_id]["tagged_roman_v2"]
                != validation["search_fields"]["MORPH_R"]
            ):
                raise RuntimeError("morph master/TextGrid MORPH_R 불일치")
            if (
                master_by_id[utt_id]["canonical_tagged"]
                != validation["search_fields"]["MORPH"]
            ):
                raise RuntimeError("morph master/TextGrid MORPH 불일치")
            counts["csv_textgrid_label_equal"] += 1
        except Exception as exc:
            errors.append(
                {
                    "year": year,
                    "session": session,
                    "utt_id": utt_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    expected_ids = {row["utt_id"] for row in selection}
    master_ids = set(master_by_id)
    if master_ids != expected_ids:
        errors.append(
            {
                "utt_id": "",
                "error": (
                    "morph master/selection ID 집합 불일치: "
                    f"missing={len(expected_ids - master_ids)} "
                    f"extra={len(master_ids - expected_ids)}"
                ),
            }
        )
    passed = (
        not errors
        and counts["selected"] == 60
        and counts["new_textgrid_valid"] == 60
        and counts["word_phone_semantic_equal"] == 60
        and counts["csv_textgrid_label_equal"] == 60
        and all(year_counts[str(year)] == 10 for year in range(2020, 2026))
    )
    return {
        "schema_version": "mfa_research_schema_pilot_audit.v1",
        "status": "passed" if passed else "failed",
        "run_root": str(run_root),
        "new_textgrid_root": str(new_textgrid_root),
        "morph_root": str(morph_root),
        "counts": dict(sorted(counts.items())),
        "years": dict(sorted(year_counts.items())),
        "errors": errors[:100],
        "gates": {
            "selection_exact_60": counts["selected"] == 60,
            "years_10_each": all(
                year_counts[str(year)] == 10
                for year in range(2020, 2026)
            ),
            "new_textgrid_valid_60": (
                counts["new_textgrid_valid"] == 60
            ),
            "word_phone_semantic_equal_60": (
                counts["word_phone_semantic_equal"] == 60
            ),
            "csv_textgrid_label_equal_60": (
                counts["csv_textgrid_label_equal"] == 60
            ),
            "morph_master_id_set_equal": master_ids == expected_ids,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--new-textgrid-root", type=Path, required=True)
    parser.add_argument("--morph-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        run_root=args.run_root,
        new_textgrid_root=args.new_textgrid_root,
        morph_root=args.morph_root,
    )
    atomic_write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
