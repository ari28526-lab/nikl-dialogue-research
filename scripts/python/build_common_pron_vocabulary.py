"""2020–2025 전체 동결 코퍼스의 공통 MFA 어휘 인벤토리를 만든다.

발화 표본이 아니라 ``pron_reference_form`` 전수 행을 MFA lab과 같은
``form_to_lab`` 함수로 토큰화한다. 대형 결과는 D:의 release 폴더에 쓰고,
입력 CSV와 기존 MFA 결과는 읽기만 한다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)
from realign_eojeol_build_corpus import form_to_lab  # noqa: E402

DEFAULT_YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
REQUIRED_COLUMNS = {
    "utt_id",
    "year",
    "pron_reference_form",
    "pron_reference_status",
}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_years(value: str) -> tuple[str, ...]:
    years = tuple(part.strip() for part in value.split(",") if part.strip())
    if not years or len(years) != len(set(years)):
        raise argparse.ArgumentTypeError("연도는 중복 없는 쉼표 목록이어야 함")
    if any(year not in DEFAULT_YEARS for year in years):
        raise argparse.ArgumentTypeError("지원 연도는 2020–2025")
    return years


def source_inventory(
    search_root: Path, years: tuple[str, ...]
) -> tuple[list[Path], dict]:
    meta_path = search_root / "_build_meta.json"
    if not meta_path.is_file():
        raise RuntimeError(f"동결 build meta 없음: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if meta.get("status") != "success":
        raise RuntimeError(
            f"동결 search master가 success가 아님: {meta.get('status')}"
        )

    files: list[Path] = []
    year_files: dict[str, int] = {}
    inventory_digest = hashlib.sha256()
    for year in years:
        year_dir = search_root / year
        current = sorted(
            path
            for path in year_dir.glob("*.csv")
            if not path.name.startswith("_")
        )
        if not current:
            raise RuntimeError(f"{year} search CSV 없음: {year_dir}")
        year_files[year] = len(current)
        for path in current:
            stat = path.stat()
            rel = path.relative_to(search_root).as_posix()
            inventory_digest.update(
                f"{rel}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8")
            )
        files.extend(current)
    return files, {
        "search_master_root": str(search_root.resolve()),
        "build_meta": file_fingerprint(meta_path, with_sha256=True),
        "session_files_by_year": year_files,
        "session_files_total": len(files),
        "path_size_mtime_inventory_sha256": inventory_digest.hexdigest(),
    }


def build_vocabulary(
    *,
    search_root: Path,
    years: tuple[str, ...],
    output_csv: Path,
    manifest_path: Path,
    summary_output: Path | None = None,
    progress_every: int = 500,
) -> dict:
    if output_csv.exists() or manifest_path.exists():
        raise FileExistsError(
            "기존 공통 어휘 산출물을 덮어쓰지 않음: "
            f"{output_csv} / {manifest_path}"
        )
    if summary_output is not None and summary_output.exists():
        raise FileExistsError(
            f"기존 요약 보고서를 덮어쓰지 않음: {summary_output}"
        )

    files, source = source_inventory(search_root, years)
    year_index = {year: index for index, year in enumerate(years)}
    token_counts: dict[str, list[int]] = {}
    status_counts = Counter()
    rows_by_year = Counter()
    tokens_by_year = Counter()
    empty_lab_by_year = Counter()
    started = time.perf_counter()

    for file_number, path in enumerate(files, start=1):
        expected_year = path.parent.name
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(
                    f"필수 열 누락 {sorted(missing)}: {path}"
                )
            for row in reader:
                row_year = (row.get("year") or "").strip()
                if row_year != expected_year or row_year not in year_index:
                    raise RuntimeError(
                        f"연도 불일치: file={expected_year}, row={row_year}, "
                        f"utt_id={row.get('utt_id')}"
                    )
                rows_by_year[row_year] += 1
                status = (row.get("pron_reference_status") or "").strip()
                status_counts[f"{row_year}:{status or '<blank>'}"] += 1
                lab_text = form_to_lab(row.get("pron_reference_form") or "")
                if not lab_text:
                    empty_lab_by_year[row_year] += 1
                    continue
                tokens = lab_text.split()
                tokens_by_year[row_year] += len(tokens)
                position = year_index[row_year]
                for token in tokens:
                    counts = token_counts.get(token)
                    if counts is None:
                        counts = [0] * len(years)
                        token_counts[token] = counts
                    counts[position] += 1

        if progress_every and (
            file_number % progress_every == 0 or file_number == len(files)
        ):
            elapsed = time.perf_counter() - started
            print(
                f"[vocab] files={file_number:,}/{len(files):,} "
                f"rows={sum(rows_by_year.values()):,} "
                f"unique={len(token_counts):,} elapsed={elapsed:.1f}s",
                flush=True,
            )

    fields = [
        "token",
        "n_syllables",
        "total_occurrences",
        "n_years_present",
        *[f"count_{year}" for year in years],
    ]
    with atomic_text_writer(
        output_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for token in sorted(token_counts):
            counts = token_counts[token]
            writer.writerow(
                {
                    "token": token,
                    "n_syllables": len(token),
                    "total_occurrences": sum(counts),
                    "n_years_present": sum(value > 0 for value in counts),
                    **{
                        f"count_{year}": counts[index]
                        for index, year in enumerate(years)
                    },
                }
            )

    elapsed = time.perf_counter() - started
    output_sha = sha256_file(output_csv)
    per_year = {}
    for year in years:
        per_year[year] = {
            "session_files": source["session_files_by_year"][year],
            "utterance_rows": rows_by_year[year],
            "lab_tokens": tokens_by_year[year],
            "empty_lab_rows": empty_lab_by_year[year],
            "unique_tokens": sum(
                1
                for counts in token_counts.values()
                if counts[year_index[year]] > 0
            ),
            "unresolved_symbol_rows": status_counts[
                f"{year}:unresolved_symbol"
            ],
        }

    project_root = Path(__file__).resolve().parents[2]
    manifest = {
        "schema_version": 1,
        "kind": "common_pronunciation_full_vocabulary",
        "status": "success",
        "scope": "full_frozen_corpus_vocabulary_2020_2025",
        "recorded_at": now_iso(),
        "years": list(years),
        "tokenizer": {
            "function": "realign_eojeol_build_corpus.form_to_lab",
            "lab_input_version": "eojeol_v3_pron_reference_form",
            "source_field": "pron_reference_form",
            "policy": "whitespace eojjeol; keep Hangul syllables only",
        },
        "source": source,
        "counts": {
            "session_files": len(files),
            "utterance_rows": sum(rows_by_year.values()),
            "lab_tokens": sum(tokens_by_year.values()),
            "unique_tokens": len(token_counts),
            "empty_lab_rows": sum(empty_lab_by_year.values()),
            "unresolved_symbol_rows": sum(
                status_counts[f"{year}:unresolved_symbol"]
                for year in years
            ),
            "per_year": per_year,
        },
        "output": {
            "path": str(output_csv.resolve()),
            "bytes": output_csv.stat().st_size,
            "sha256": output_sha,
            "columns": fields,
        },
        "elapsed_seconds": round(elapsed, 3),
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(manifest_path, manifest)
    if summary_output is not None:
        atomic_write_json(summary_output, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--search-root",
        type=Path,
        default=P("pre_mfa_search_master"),
    )
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument(
        "--years",
        type=parse_years,
        default=DEFAULT_YEARS,
        help="쉼표 구분, 기본 2020–2025 전부",
    )
    parser.add_argument("--progress-every", type=int, default=500)
    args = parser.parse_args()

    try:
        result = build_vocabulary(
            search_root=args.search_root.resolve(),
            years=tuple(args.years),
            output_csv=args.output_csv.resolve(),
            manifest_path=args.manifest.resolve(),
            summary_output=(
                args.summary_output.resolve()
                if args.summary_output is not None
                else None
            ),
            progress_every=max(args.progress_every, 0),
        )
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print(
        "[OK] 2020–2025 전체 공통 vocabulary: "
        f"{result['counts']['utterance_rows']:,}행, "
        f"{result['counts']['unique_tokens']:,}고유 어절"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
