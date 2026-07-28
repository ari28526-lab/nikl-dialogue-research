"""Trace a small set of common-pronunciation tokens back to frozen source rows.

The full search master is scanned once, using exactly the same ``form_to_lab``
tokenization as the common vocabulary builder.  Matching rows are then joined
back to the raw dialogue JSON by year, session, and utterance ID.  Source files
are read only; outputs are new, atomic, and never overwritten.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_common_pron_vocabulary import (  # noqa: E402
    DEFAULT_YEARS,
    source_inventory,
)
from build_search_master import load_utt_extra  # noqa: E402
from paths import P  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)
from realign_eojeol_build_corpus import form_to_lab  # noqa: E402

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


REQUIRED_COLUMNS = {
    "utt_id",
    "year",
    "session_id",
    "form",
    "original_form",
    "pron_reference_form",
    "pron_reference_hangul",
    "pron_reference_source",
    "pron_reference_status",
}

OUTPUT_FIELDS = [
    "target_token",
    "token_position_1based",
    "utt_id",
    "year",
    "session_id",
    "dialogue_id",
    "speaker_id",
    "form",
    "original_form",
    "pron_reference_form",
    "pron_reference_hangul",
    "pron_reference_source",
    "pron_reference_status",
    "source_search_master_csv",
    "raw_json_path",
    "raw_json_original_form",
    "raw_json_dialogue_id",
    "raw_json_match_status",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def parse_years(value: str) -> tuple[str, ...]:
    years = tuple(part.strip() for part in value.split(",") if part.strip())
    if not years or len(years) != len(set(years)):
        raise argparse.ArgumentTypeError("연도는 중복 없는 쉼표 목록이어야 함")
    if any(year not in DEFAULT_YEARS for year in years):
        raise argparse.ArgumentTypeError("지원 연도는 2020–2025")
    return years


def normalize_targets(values: list[str]) -> tuple[str, ...]:
    targets = tuple(sorted({clean(value) for value in values if clean(value)}))
    if not targets:
        raise ValueError("추적할 표층형이 없음")
    invalid = [
        target
        for target in targets
        if form_to_lab(target) != target
        or len(form_to_lab(target).split()) != 1
    ]
    if invalid:
        raise ValueError(
            "target은 form_to_lab에서 단일 동일 어절이어야 함: "
            f"{invalid}"
        )
    return targets


def scan_search_master(
    *,
    search_root: Path,
    years: tuple[str, ...],
    targets: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict]:
    files, source = source_inventory(search_root, years)
    target_set = set(targets)
    matches: list[dict[str, str]] = []
    rows_by_year: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    target_year_counts: Counter[str] = Counter()

    for path in files:
        expected_year = path.parent.name
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(
                    f"search-master 필수 열 누락 {sorted(missing)}: {path}"
                )
            for row in reader:
                year = clean(row.get("year"))
                if year != expected_year:
                    raise RuntimeError(
                        f"search-master 연도 불일치: {path}, "
                        f"utt_id={clean(row.get('utt_id'))}, row_year={year}"
                    )
                rows_by_year[year] += 1
                lab = form_to_lab(row.get("pron_reference_form") or "")
                if not lab:
                    continue
                tokens = lab.split()
                for position, token in enumerate(tokens, start=1):
                    if token not in target_set:
                        continue
                    target_counts[token] += 1
                    target_year_counts[f"{token}:{year}"] += 1
                    matches.append(
                        {
                            "target_token": token,
                            "token_position_1based": str(position),
                            "utt_id": clean(row.get("utt_id")),
                            "year": year,
                            "session_id": clean(row.get("session_id")),
                            "dialogue_id": clean(row.get("dialogue_id")),
                            "speaker_id": clean(row.get("speaker_id")),
                            "form": clean(row.get("form")),
                            "original_form": clean(row.get("original_form")),
                            "pron_reference_form": clean(
                                row.get("pron_reference_form")
                            ),
                            "pron_reference_hangul": clean(
                                row.get("pron_reference_hangul")
                            ),
                            "pron_reference_source": clean(
                                row.get("pron_reference_source")
                            ),
                            "pron_reference_status": clean(
                                row.get("pron_reference_status")
                            ),
                            "source_search_master_csv": str(path.resolve()),
                        }
                    )

    missing_targets = [
        target for target in targets if target_counts[target] == 0
    ]
    if missing_targets:
        raise RuntimeError(
            f"동결 search-master에서 target을 찾지 못함: {missing_targets}"
        )
    if any(not match["utt_id"] or not match["session_id"] for match in matches):
        raise RuntimeError("target occurrence의 utt_id/session_id가 비어 있음")

    return matches, {
        "source": source,
        "search_master_rows_by_year": dict(sorted(rows_by_year.items())),
        "target_occurrences": {
            target: target_counts[target] for target in targets
        },
        "target_occurrences_by_year": {
            key: target_year_counts[key] for key in sorted(target_year_counts)
        },
    }


def locate_raw_json(
    *,
    dialogue_json_root: Path,
    needed_sessions: dict[str, set[str]],
) -> dict[tuple[str, str], Path]:
    resolved: dict[tuple[str, str], Path] = {}
    for year, sessions in sorted(needed_sessions.items()):
        year_dirs = sorted(
            path
            for path in dialogue_json_root.iterdir()
            if path.is_dir() and year in path.name
        )
        if len(year_dirs) != 1:
            raise RuntimeError(
                f"dialogue_json 연도 폴더가 정확히 1개가 아님: "
                f"year={year}, dirs={year_dirs}"
            )
        remaining = set(sessions)
        for path in year_dirs[0].rglob("*.json"):
            if path.stem not in remaining:
                continue
            key = (year, path.stem)
            if key in resolved:
                raise RuntimeError(
                    f"동일 session JSON 중복: {key}, "
                    f"{resolved[key]}, {path}"
                )
            resolved[key] = path.resolve()
            remaining.remove(path.stem)
        if remaining:
            raise RuntimeError(
                f"원본 JSON session 누락: year={year}, "
                f"sessions={sorted(remaining)}"
            )
    return resolved


def join_raw_json(
    *,
    matches: list[dict[str, str]],
    dialogue_json_root: Path,
) -> tuple[list[dict[str, str]], dict]:
    needed: dict[str, set[str]] = defaultdict(set)
    for match in matches:
        needed[match["year"]].add(match["session_id"])
    paths = locate_raw_json(
        dialogue_json_root=dialogue_json_root,
        needed_sessions=needed,
    )

    loaded: dict[Path, dict[str, dict]] = {}
    joined: list[dict[str, str]] = []
    mismatch_counts: Counter[str] = Counter()
    for match in matches:
        path = paths[(match["year"], match["session_id"])]
        if path not in loaded:
            loaded[path] = load_utt_extra(path)
        raw = loaded[path].get(match["utt_id"])
        if raw is None:
            raise RuntimeError(
                f"원본 JSON에서 utt_id 누락: {path}, {match['utt_id']}"
            )
        raw_original = clean(raw.get("original_form"))
        raw_dialogue = clean(raw.get("dialogue_id"))
        statuses: list[str] = []
        if raw_original != match["original_form"]:
            statuses.append("original_form_mismatch")
        if raw_dialogue != match["dialogue_id"]:
            statuses.append("dialogue_id_mismatch")
        status = "|".join(statuses) if statuses else "exact"
        mismatch_counts[status] += 1
        joined.append(
            {
                **match,
                "raw_json_path": str(path),
                "raw_json_original_form": raw_original,
                "raw_json_dialogue_id": raw_dialogue,
                "raw_json_match_status": status,
            }
        )

    non_exact = {
        key: value for key, value in mismatch_counts.items() if key != "exact"
    }
    if non_exact:
        raise RuntimeError(
            f"search-master와 원본 JSON 불일치: {non_exact}"
        )
    joined.sort(
        key=lambda row: (
            row["year"],
            row["utt_id"],
            int(row["token_position_1based"]),
            row["target_token"],
        )
    )
    return joined, {
        "raw_json_sessions": len(paths),
        "raw_json_files_loaded": len(loaded),
        "raw_json_match_status": dict(sorted(mismatch_counts.items())),
    }


def trace_occurrences(
    *,
    search_root: Path,
    dialogue_json_root: Path,
    years: tuple[str, ...],
    targets: tuple[str, ...],
    output_csv: Path,
    manifest_path: Path,
) -> dict:
    if output_csv.exists() or manifest_path.exists():
        raise FileExistsError(
            "기존 추적 산출물을 덮어쓰지 않음: "
            f"{output_csv} / {manifest_path}"
        )
    if not dialogue_json_root.is_dir():
        raise RuntimeError(f"dialogue_json root 없음: {dialogue_json_root}")

    matches, scan = scan_search_master(
        search_root=search_root,
        years=years,
        targets=targets,
    )
    joined, raw = join_raw_json(
        matches=matches,
        dialogue_json_root=dialogue_json_root,
    )

    with atomic_text_writer(
        output_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(joined)

    manifest = {
        "schema_version": 1,
        "kind": "common_pron_special_occurrence_trace",
        "status": "success",
        "recorded_at": now_iso(),
        "years": list(years),
        "targets": list(targets),
        "tokenizer": {
            "function": "realign_eojeol_build_corpus.form_to_lab",
            "same_as_common_vocabulary": True,
        },
        "source": {
            **scan["source"],
            "dialogue_json_root": str(dialogue_json_root.resolve()),
        },
        "counts": {
            "occurrence_rows": len(joined),
            "search_master_rows_by_year": scan[
                "search_master_rows_by_year"
            ],
            "target_occurrences": scan["target_occurrences"],
            "target_occurrences_by_year": scan[
                "target_occurrences_by_year"
            ],
            **raw,
        },
        "output": file_fingerprint(output_csv, with_sha256=True),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "소수 공통발음 특수 표층형을 동결 search-master와 원본 JSON에 "
            "읽기 전용으로 역추적"
        )
    )
    parser.add_argument(
        "--search-root",
        type=Path,
        default=P("pre_mfa_search_master"),
    )
    parser.add_argument(
        "--dialogue-json-root",
        type=Path,
        default=P("dialogue_json"),
    )
    parser.add_argument(
        "--years",
        type=parse_years,
        default=DEFAULT_YEARS,
    )
    parser.add_argument(
        "--target",
        action="append",
        required=True,
        help="정확히 추적할 한 어절; 여러 번 지정 가능",
    )
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = trace_occurrences(
            search_root=args.search_root.resolve(),
            dialogue_json_root=args.dialogue_json_root.resolve(),
            years=tuple(args.years),
            targets=normalize_targets(args.target),
            output_csv=args.output_csv.resolve(),
            manifest_path=args.manifest.resolve(),
        )
    except Exception as exc:
        print(f"[FAIL] 특수 표층형 원본 역추적: {exc}", file=sys.stderr)
        return 1
    print(
        "[OK] 특수 표층형 원본 역추적: "
        f"targets={len(result['targets'])}, "
        f"occurrences={result['counts']['occurrence_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
