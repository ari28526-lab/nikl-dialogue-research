"""두 TextGrid 트리의 tier 라벨·경계를 전수 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import atomic_write_json
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


def normalized_tiers(path: Path) -> tuple[float, dict]:
    duration, tiers = parse_mfa_textgrid(path)
    normalized = {
        name: [
            (round(float(begin), 6), round(float(end), 6), label)
            for begin, end, label in intervals
        ]
        for name, intervals in tiers.items()
    }
    return round(float(duration), 6), normalized


def compare_trees(left: Path, right: Path) -> dict:
    left_files = {
        path.relative_to(left).as_posix(): path
        for path in left.rglob("*.TextGrid")
    }
    right_files = {
        path.relative_to(right).as_posix(): path
        for path in right.rglob("*.TextGrid")
    }
    missing_right = sorted(set(left_files) - set(right_files))
    missing_left = sorted(set(right_files) - set(left_files))
    mismatches = []
    matched = 0
    for relative in sorted(set(left_files) & set(right_files)):
        try:
            left_value = normalized_tiers(left_files[relative])
            right_value = normalized_tiers(right_files[relative])
        except Exception as exc:
            mismatches.append({
                "file": relative,
                "reason": f"{type(exc).__name__}: {exc}",
            })
            continue
        if left_value != right_value:
            if len(mismatches) < 100:
                mismatches.append({
                    "file": relative,
                    "reason": "duration_or_tiers_differ",
                })
        else:
            matched += 1
    return {
        "left": str(left.resolve()),
        "right": str(right.resolve()),
        "left_files": len(left_files),
        "right_files": len(right_files),
        "matched": matched,
        "mismatch_count": (
            len(set(left_files) & set(right_files)) - matched
        ),
        "missing_right_count": len(missing_right),
        "missing_left_count": len(missing_left),
        "missing_right_examples": missing_right[:100],
        "missing_left_examples": missing_left[:100],
        "mismatch_examples": mismatches[:100],
        "status": (
            "identical"
            if (
                not missing_right
                and not missing_left
                and matched == len(left_files) == len(right_files)
            )
            else "different"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = compare_trees(args.left, args.right)
    atomic_write_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "identical" else 1


if __name__ == "__main__":
    raise SystemExit(main())
