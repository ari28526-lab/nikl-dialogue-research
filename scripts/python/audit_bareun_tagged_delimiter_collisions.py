"""Bareun tagged의 literal ``+``/형태소 구분자 충돌을 연도별 전수 감사한다.

1차 CSV의 ``n_morphs``는 과거에 문자열의 모든 ``+``를 구분자로 세었다.
Bareun 표면형 자체가 ``+``를 포함하면 이 값은 과대계상된다. 원 CSV는 수정하지
않고 POS 종결점 수와 비교해 후보를 찾고, 동결 parser가 무손실 해석하는지 기록한다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from morph_schema import POS_TERMINATOR_RE, parse_tagged, recompose_raw_tagged


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(partial, path)


def scan_year(root: Path, year: str) -> dict[str, object]:
    year_root = root / year
    files = sorted(year_root.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"{year} CSV 0개: {year_root}")
    rows = 0
    candidates = 0
    explained = 0
    errors: list[dict[str, object]] = []
    examples: list[dict[str, object]] = []
    surface_patterns: Counter[str] = Counter()
    difference_counts: Counter[int] = Counter()
    for path in files:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            header = next(reader, [])
            required = {"utt_id", "tagged"}
            missing = required - set(header)
            if missing:
                raise RuntimeError(f"{path}: 필수 열 누락 {sorted(missing)}")
            utt_index = header.index("utt_id")
            tagged_index = header.index("tagged")
            n_morphs_index = (
                header.index("n_morphs") if "n_morphs" in header else -1
            )
            for row_number, values in enumerate(reader, 2):
                rows += 1
                utt_id = values[utt_index] if utt_index < len(values) else ""
                tagged = (
                    values[tagged_index].strip()
                    if tagged_index < len(values)
                    else ""
                )
                source_n_morphs = (
                    values[n_morphs_index]
                    if n_morphs_index >= 0 and n_morphs_index < len(values)
                    else ""
                )
                legacy_count = sum(
                    token.count("+") + 1 for token in tagged.split() if token
                )
                # POS_TERMINATOR_RE is intentionally scoped to one eojeol;
                # applying it to the full utterance would miss POS endings
                # immediately before whitespace.
                terminal_count = sum(
                    len(POS_TERMINATOR_RE.findall(token))
                    for token in tagged.split()
                )
                if legacy_count == terminal_count:
                    continue
                candidates += 1
                try:
                    parsed = parse_tagged(tagged)
                    structured_count = sum(len(group) for group in parsed)
                    literal_surfaces = [
                        morph.surface
                        for group in parsed
                        for morph in group
                        if "+" in morph.surface
                    ]
                    lossless = recompose_raw_tagged(parsed) == tagged
                    difference = legacy_count - structured_count
                    is_explained = (
                        lossless
                        and bool(literal_surfaces)
                        and difference
                        == sum(surface.count("+") for surface in literal_surfaces)
                    )
                    if is_explained:
                        explained += 1
                    else:
                        errors.append(
                            {
                                "file": path.name,
                                "row": row_number,
                                "utt_id": utt_id,
                                "error": "delimiter difference not fully explained",
                            }
                        )
                    difference_counts[difference] += 1
                    surface_patterns.update(literal_surfaces)
                    if len(examples) < 100:
                        examples.append(
                            {
                                "file": path.name,
                                "row": row_number,
                                "utt_id": utt_id,
                                "tagged": tagged,
                                "source_n_morphs": source_n_morphs,
                                "legacy_plus_count": legacy_count,
                                "structured_count": structured_count,
                                "literal_plus_surfaces": literal_surfaces,
                                "lossless": lossless,
                                "explained": is_explained,
                            }
                        )
                except Exception as exc:  # report evidence; do not hide parser failures
                    errors.append(
                        {
                            "file": path.name,
                            "row": row_number,
                            "utt_id": utt_id,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
    return {
        "year": year,
        "input_root": str(year_root.resolve()),
        "file_count": len(files),
        "row_count": rows,
        "delimiter_collision_candidates": candidates,
        "lossless_literal_plus_explained": explained,
        "unexplained_count": len(errors),
        "difference_counts": {
            str(key): value for key, value in sorted(difference_counts.items())
        },
        "literal_plus_surface_patterns": dict(surface_patterns.most_common()),
        "examples": examples,
        "errors": errors[:1000],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--years", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results: list[dict[str, object]] = []
    progress_path = args.output.resolve().with_suffix(".progress.json")
    for year in args.years:
        result = scan_year(args.input_root.resolve(), year)
        results.append(result)
        atomic_json(
            progress_path,
            {
                "schema_version": (
                    "bareun_tagged_delimiter_collision_audit_progress.v1"
                ),
                "status": "running",
                "completed_years": [item["year"] for item in results],
                "years": results,
            },
        )
        print(
            f"[{year}] rows={result['row_count']:,} "
            f"candidates={result['delimiter_collision_candidates']} "
            f"unexplained={result['unexplained_count']}",
            flush=True,
        )
    unexplained = sum(int(item["unexplained_count"]) for item in results)
    payload = {
        "schema_version": "bareun_tagged_delimiter_collision_audit.v1",
        "status": "passed" if unexplained == 0 else "failed",
        "recorded_at": datetime.now().astimezone().isoformat(),
        "years": results,
        "totals": {
            "files": sum(int(item["file_count"]) for item in results),
            "rows": sum(int(item["row_count"]) for item in results),
            "delimiter_collision_candidates": sum(
                int(item["delimiter_collision_candidates"]) for item in results
            ),
            "lossless_literal_plus_explained": sum(
                int(item["lossless_literal_plus_explained"]) for item in results
            ),
            "unexplained": unexplained,
        },
    }
    atomic_json(args.output.resolve(), payload)
    progress_path.unlink(missing_ok=True)
    print(json.dumps(payload["totals"], ensure_ascii=False, indent=2))
    print(args.output.resolve())
    return 0 if unexplained == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
