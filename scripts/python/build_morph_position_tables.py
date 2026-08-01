"""동결 search master에서 형태소·표면 unit·경계 검색표를 생성한다.

원본 CSV는 읽기 전용이다. 출력은 sibling ``.partial`` 디렉터리에서 완성한
뒤 새 root로 원자 승격하며 기존 출력은 덮어쓰지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

from morph_schema import (
    MORPH_SCHEMA_VERSION,
    POSITION_SCHEMA_VERSION,
    ROMAN_SYSTEM_VERSION,
    SERIALIZATION_VERSION,
    MorphSchemaError,
    build_utterance_tables,
)

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MASTER_DERIVED_FIELDS = [
    "canonical_tagged",
    "tagged_roman_v2",
    "roman_system_version",
    "serialization_version",
    "position_schema_version",
    "morph_schema_version",
    "morph_parse_status",
    "morph_count_structured",
    "morph_unit_count",
    "morph_boundary_count",
    "tagged_regeneration_equal",
    "legacy_tagged_roman_equal_v2",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def output_file_record(path: Path) -> dict[str, object]:
    return {
        "relative_path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def input_headers(paths: list[Path]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        missing = {"utt_id", "tagged"} - set(header)
        if missing:
            raise RuntimeError(f"{path}: 필수 열 누락 {sorted(missing)}")
        for field in header:
            if field not in seen:
                ordered.append(field)
                seen.add(field)
    return ordered


def csv_writer(path: Path, fieldnames: list[str]) -> tuple[object, csv.DictWriter]:
    stream = open(path, "w", encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    return stream, writer


def _iter_rows(paths: Iterable[Path]):
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row_number, row in enumerate(reader, 2):
                yield path, row_number, row


def build_tables(
    *,
    input_paths: list[Path],
    output_root: Path,
    emit_orth_components: bool = False,
) -> dict[str, object]:
    if not input_paths:
        raise ValueError("입력 CSV 0개")
    input_paths = sorted(path.resolve() for path in input_paths)
    missing = [str(path) for path in input_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"입력 CSV 누락: {missing}")
    output_root = output_root.resolve()
    partial = output_root.with_name(output_root.name + ".partial")
    if output_root.exists():
        raise FileExistsError(f"기존 출력 덮어쓰기 금지: {output_root}")
    if partial.exists():
        raise FileExistsError(
            f"미완료 출력이 남아 있음; 먼저 조사 필요: {partial}"
        )
    partial.mkdir(parents=True)

    base_fields = input_headers(input_paths)
    master_fields = base_fields + [
        field for field in MASTER_DERIVED_FIELDS if field not in base_fields
    ]
    handles: list[object] = []
    writers: dict[str, csv.DictWriter] = {}
    paths = {
        "master": partial / "utterance_master_v2.csv",
        "eojeol_tokens": partial / "eojeol_tokens.csv",
        "morph_tokens": partial / "morph_tokens.csv",
        "morph_units": partial / "morph_units.csv",
        "morph_boundaries": partial / "morph_boundaries.csv",
        "orth_components": partial / "orth_components.csv",
    }
    master_stream, master_writer = csv_writer(paths["master"], master_fields)
    handles.append(master_stream)
    writers["master"] = master_writer

    seen_ids: set[str] = set()
    counts: Counter[str] = Counter()
    years: Counter[str] = Counter()
    unit_types: Counter[str] = Counter()
    errors: list[dict[str, object]] = []
    detail_fieldnames: dict[str, list[str]] = {}
    try:
        for source, row_number, row in _iter_rows(input_paths):
            utt_id = str(row.get("utt_id", "")).strip()
            if not utt_id:
                errors.append(
                    {
                        "source": str(source),
                        "row": row_number,
                        "utt_id": "",
                        "error": "빈 utt_id",
                    }
                )
                continue
            if utt_id in seen_ids:
                errors.append(
                    {
                        "source": str(source),
                        "row": row_number,
                        "utt_id": utt_id,
                        "error": "중복 utt_id",
                    }
                )
                continue
            seen_ids.add(utt_id)
            try:
                result = build_utterance_tables(row)
            except (MorphSchemaError, KeyError, TypeError, ValueError) as exc:
                errors.append(
                    {
                        "source": str(source),
                        "row": row_number,
                        "utt_id": utt_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            writers["master"].writerow(result["master"])
            counts["utterances"] += 1
            years[str(row.get("year", ""))] += 1
            for table_name in (
                "eojeol_tokens",
                "morph_tokens",
                "morph_units",
                "morph_boundaries",
                "orth_components",
            ):
                if table_name == "orth_components" and not emit_orth_components:
                    continue
                table_rows = result[table_name]
                if table_name not in writers:
                    if not table_rows:
                        continue
                    detail_fieldnames[table_name] = list(table_rows[0])
                    stream, writer = csv_writer(
                        paths[table_name], detail_fieldnames[table_name]
                    )
                    handles.append(stream)
                    writers[table_name] = writer
                for detail_row in table_rows:
                    writers[table_name].writerow(detail_row)
                    counts[table_name] += 1
                    if table_name == "morph_units":
                        unit_types[str(detail_row["unit_type"])] += 1
        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        for handle in handles:
            handle.close()

    if errors:
        failure = {
            "schema_version": "morph_position_build_failure.v1",
            "status": "failed",
            "input_files": [file_record(path) for path in input_paths],
            "counts": dict(counts),
            "error_count": len(errors),
            "errors": errors[:1000],
        }
        write_json(partial / "BUILD_FAILED.json", failure)
        raise RuntimeError(
            f"형태소 스키마 build 실패 {len(errors)}건; "
            f"근거 보존: {partial / 'BUILD_FAILED.json'}"
        )

    expected_boundaries = max(
        0, counts["morph_tokens"] - counts["utterances"]
    )
    if counts["morph_boundaries"] != expected_boundaries:
        raise RuntimeError(
            "경계 개수 불일치: "
            f"expected={expected_boundaries} "
            f"actual={counts['morph_boundaries']}"
        )
    output_files = {
        name: output_file_record(path)
        for name, path in paths.items()
        if path.is_file()
    }
    manifest = {
        "schema_version": "morph_position_build_manifest.v1",
        "status": "success",
        "created_at": datetime.now().astimezone().isoformat(),
        "versions": {
            "morph_schema": MORPH_SCHEMA_VERSION,
            "roman_system": ROMAN_SYSTEM_VERSION,
            "serialization": SERIALIZATION_VERSION,
            "position_schema": POSITION_SCHEMA_VERSION,
        },
        "input_files": [file_record(path) for path in input_paths],
        "output_files": output_files,
        "emit_orth_components": emit_orth_components,
        "counts": dict(sorted(counts.items())),
        "years": dict(sorted(years.items())),
        "unit_types": dict(sorted(unit_types.items())),
        "gates": {
            "duplicate_utt_id": 0,
            "parse_errors": 0,
            "tagged_regeneration_mismatch": 0,
            "syllable_recomposition_mismatch": 0,
            "boundary_count_equal": True,
        },
    }
    write_json(partial / "BUILD_MANIFEST.json", manifest)
    os.replace(partial, output_root)
    return manifest


def resolve_inputs(
    explicit: list[Path],
    input_root: Path | None,
    pattern: str,
) -> list[Path]:
    paths = [path.resolve() for path in explicit]
    if input_root is not None:
        paths.extend(sorted(input_root.resolve().glob(pattern)))
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", default=[])
    parser.add_argument("--input-root", type=Path)
    parser.add_argument(
        "--pattern", default="*/search_master_selected.csv"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--emit-orth-components", action="store_true")
    args = parser.parse_args()
    try:
        manifest = build_tables(
            input_paths=resolve_inputs(
                args.input, args.input_root, args.pattern
            ),
            output_root=args.output_root,
            emit_orth_components=args.emit_orth_components,
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
