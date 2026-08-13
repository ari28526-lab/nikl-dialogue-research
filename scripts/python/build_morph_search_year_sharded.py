"""연도별 형태·표기 조합검색 표를 shard checkpoint로 안전 생성한다.

원 search-master CSV는 읽기 전용이다. 각 shard는 독립 raw build와 결정적
gzip CSV package를 가진다. 중단 뒤에는 성공 shard를 SHA-256으로 다시
검증해 재사용하며, 실패 ``.partial``은 자동 삭제하지 않는다. 모든 shard가
통과한 뒤에만 연도별 gzip 표와 ``YEAR_MANIFEST.json``을 승격한다.

Parquet은 gzip 감사 정본에서 별도 분석 환경으로 재생성한다. 이 스크립트는
동결 MFA 환경에 PyArrow를 추가하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

from build_morph_position_tables import build_tables, sha256_file
from morph_schema import (
    MORPH_SCHEMA_VERSION,
    POSITION_SCHEMA_VERSION,
    ROMAN_SYSTEM_VERSION,
    SERIALIZATION_VERSION,
    SYMBOL_SCHEMA_VERSION,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RUN_SCHEMA_VERSION = "morph_search_year_sharded.v1"
SHARD_SCHEMA_VERSION = "morph_search_shard_package.v1"
YEAR_SCHEMA_VERSION = "morph_search_year_tables.v1"

TABLE_COUNT_KEYS = {
    "utterance_master_v2.csv": "utterances",
    "orth_eojeol_tokens.csv": "orth_eojeol_tokens",
    "eojeol_tokens.csv": "eojeol_tokens",
    "morph_tokens.csv": "morph_tokens",
    "morph_units.csv": "morph_units",
    "morph_boundaries.csv": "morph_boundaries",
    "symbol_readings.csv": "symbol_readings",
    "orth_components.csv": "orth_components",
}


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.{os.getpid()}.partial")
    partial.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with open(partial, "rb+") as stream:
        os.fsync(stream.fileno())
    os.replace(partial, path)


def file_info(path: Path) -> dict[str, object]:
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def inventory_contract(paths: Iterable[Path]) -> tuple[list[dict[str, object]], str]:
    records = [
        {
            "name": path.name,
            "bytes": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns,
        }
        for path in paths
    ]
    canonical = json.dumps(
        records, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return records, hashlib.sha256(canonical).hexdigest()


def chunked(values: list[Path], size: int) -> list[list[Path]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_raw_build(
    raw_root: Path,
    *,
    expected_inputs: list[Path],
    year: str,
) -> dict[str, object]:
    manifest_path = raw_root / "BUILD_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"raw build manifest 없음: {manifest_path}")
    manifest = read_json(manifest_path)
    expected_versions = {
        "morph_schema": MORPH_SCHEMA_VERSION,
        "roman_system": ROMAN_SYSTEM_VERSION,
        "serialization": SERIALIZATION_VERSION,
        "position_schema": POSITION_SCHEMA_VERSION,
        "symbol_schema": SYMBOL_SCHEMA_VERSION,
    }
    if manifest.get("status") != "success":
        raise RuntimeError(f"raw build status 실패: {manifest_path}")
    if manifest.get("versions") != expected_versions:
        raise RuntimeError(f"raw build schema version 불일치: {manifest_path}")
    years = manifest.get("years", {})
    if set(years) != {year}:
        raise RuntimeError(f"raw build year 혼입: expected={year} actual={years}")

    input_records = manifest.get("input_files", [])
    if len(input_records) != len(expected_inputs):
        raise RuntimeError("raw build input file 수 불일치")
    for record, expected in zip(input_records, expected_inputs):
        actual_path = Path(str(record.get("path", ""))).resolve()
        if actual_path != expected.resolve():
            raise RuntimeError(
                f"raw build input 순서/경로 불일치: {actual_path} != {expected}"
            )
        if (
            actual_path.stat().st_size != int(record.get("bytes", -1))
            or sha256_file(actual_path) != record.get("sha256")
        ):
            raise RuntimeError(f"raw build input fingerprint 불일치: {actual_path}")

    output_files = manifest.get("output_files", {})
    required = set(TABLE_COUNT_KEYS) - {"orth_components.csv"}
    observed_names: set[str] = set()
    for record in output_files.values():
        name = str(record.get("relative_path", record.get("path", "")))
        name = Path(name).name
        path = raw_root / name
        if not path.is_file():
            raise RuntimeError(f"raw build output 누락: {path}")
        if (
            path.stat().st_size != int(record.get("bytes", -1))
            or sha256_file(path) != record.get("sha256")
        ):
            raise RuntimeError(f"raw build output fingerprint 불일치: {path}")
        observed_names.add(name)
    if not required.issubset(observed_names):
        raise RuntimeError(
            f"raw build 필수 표 누락: {sorted(required - observed_names)}"
        )
    if not bool(manifest.get("gates", {}).get("orth_symbol_coverage_equal")):
        raise RuntimeError("raw build 원표기 symbol coverage gate 실패")
    return manifest


def write_deterministic_gzip_csv(
    source: Path,
    destination: Path,
    *,
    expected_rows: int,
) -> dict[str, object]:
    partial = destination.with_name(f".{destination.name}.partial")
    if partial.exists():
        raise RuntimeError(f"미완료 gzip이 남아 있음: {partial}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # CSV fields may legally contain quoted newlines.  Counting or copying
    # physical text lines therefore cannot establish the number of records.
    # Validate logical CSV records first, then gzip the source bytes as-is.
    with open(source, encoding="utf-8-sig", newline="") as src:
        reader = csv.reader(src)
        try:
            next(reader)
        except StopIteration:
            raise RuntimeError(f"빈 CSV: {source}")
        row_count = sum(1 for _row in reader)
    if row_count != expected_rows:
        raise RuntimeError(
            f"gzip source CSV 논리행 수 불일치: {source.name} "
            f"expected={expected_rows} actual={row_count}"
        )
    with open(source, "rb") as src:
        with open(partial, "wb") as raw:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=0
            ) as zipped:
                shutil.copyfileobj(src, zipped)
            raw.flush()
            os.fsync(raw.fileno())
    os.replace(partial, destination)
    return {**file_info(destination), "rows": row_count}


def validate_gzip_table(path: Path, *, expected: Mapping[str, object]) -> None:
    if not path.is_file():
        raise RuntimeError(f"gzip table 누락: {path}")
    if (
        path.stat().st_size != int(expected.get("bytes", -1))
        or sha256_file(path) != expected.get("sha256")
    ):
        raise RuntimeError(f"gzip table fingerprint 불일치: {path}")
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        try:
            next(reader)
        except StopIteration:
            raise RuntimeError(f"gzip table header 없음: {path}")
        rows = sum(1 for _row in reader)
    if rows != int(expected.get("rows", -1)):
        raise RuntimeError(f"gzip table row 수 불일치: {path}")


def package_shard(
    shard_root: Path,
    *,
    raw_manifest: Mapping[str, object],
    shard_index: int,
    year: str,
) -> dict[str, object]:
    manifest_path = shard_root / "SHARD_MANIFEST.json"
    tables_root = shard_root / "tables"
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        if (
            manifest.get("status") != "success"
            or manifest.get("year") != year
            or int(manifest.get("shard_index", -1)) != shard_index
            or manifest.get("versions", {}).get("morph_schema")
            != MORPH_SCHEMA_VERSION
        ):
            raise RuntimeError(f"기존 shard package identity 불일치: {shard_root}")
        for info in manifest.get("tables", {}).values():
            validate_gzip_table(
                tables_root / str(info["path"]), expected=info
            )
        return manifest

    partial_root = shard_root / "tables.partial"
    if partial_root.exists():
        raise RuntimeError(
            f"미완료 shard package 보존 중; 자동 삭제 금지: {partial_root}"
        )
    partial_root.mkdir(parents=True)
    counts = raw_manifest.get("counts", {})
    tables: dict[str, dict[str, object]] = {}
    try:
        for name, record in sorted(
            raw_manifest.get("output_files", {}).items()
        ):
            source_name = Path(
                str(record.get("relative_path", record.get("path", "")))
            ).name
            if source_name not in TABLE_COUNT_KEYS:
                continue
            expected_rows = int(counts.get(TABLE_COUNT_KEYS[source_name], 0))
            destination_name = f"{source_name}.gz"
            info = write_deterministic_gzip_csv(
                shard_root / "raw" / source_name,
                partial_root / destination_name,
                expected_rows=expected_rows,
            )
            info["path"] = destination_name
            tables[name] = info
        os.replace(partial_root, tables_root)
    except BaseException:
        raise

    manifest = {
        "schema_version": SHARD_SCHEMA_VERSION,
        "status": "success",
        "created_at": datetime.now().astimezone().isoformat(),
        "year": year,
        "shard_index": shard_index,
        "versions": {
            "morph_schema": MORPH_SCHEMA_VERSION,
            "position_schema": POSITION_SCHEMA_VERSION,
            "symbol_schema": SYMBOL_SCHEMA_VERSION,
        },
        "raw_build_manifest": file_info(
            shard_root / "raw" / "BUILD_MANIFEST.json"
        ),
        "counts": counts,
        "tables": tables,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def merge_annual_tables(
    *,
    output_root: Path,
    shard_manifests: list[dict[str, object]],
    year: str,
    input_inventory_sha256: str,
) -> dict[str, object]:
    final_root = output_root / "annual_tables"
    final_manifest_path = final_root / "YEAR_MANIFEST.json"
    if final_manifest_path.is_file():
        manifest = read_json(final_manifest_path)
        if (
            manifest.get("status") != "success"
            or manifest.get("year") != year
            or manifest.get("input_inventory_sha256")
            != input_inventory_sha256
        ):
            raise RuntimeError("기존 annual manifest identity 불일치")
        for info in manifest.get("tables", {}).values():
            validate_gzip_table(
                final_root / str(info["path"]), expected=info
            )
        return manifest
    if final_root.exists():
        raise RuntimeError(
            f"manifest 없는 annual output 보존 중; 자동 삭제 금지: {final_root}"
        )

    partial_root = output_root / "annual_tables.partial"
    if partial_root.exists():
        raise RuntimeError(
            f"미완료 annual merge 보존 중; 자동 삭제 금지: {partial_root}"
        )
    partial_root.mkdir(parents=True)

    table_keys = set(shard_manifests[0]["tables"])
    for manifest in shard_manifests[1:]:
        if set(manifest["tables"]) != table_keys:
            raise RuntimeError("shard별 table 구성 불일치")

    tables: dict[str, dict[str, object]] = {}
    seen_utt_ids: set[str] = set()
    duplicate_utt_ids = 0
    try:
        for table_key in sorted(table_keys):
            destination_name = str(
                shard_manifests[0]["tables"][table_key]["path"]
            )
            destination = partial_root / destination_name
            expected_rows = sum(
                int(manifest["tables"][table_key]["rows"])
                for manifest in shard_manifests
            )
            written_rows = 0
            expected_header: list[str] | None = None
            with open(destination, "wb") as raw:
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=raw, mtime=0
                ) as zipped:
                    with io.TextIOWrapper(
                        zipped, encoding="utf-8-sig", newline=""
                    ) as dst:
                        writer = csv.writer(dst, lineterminator="\n")
                        for shard_number, manifest in enumerate(
                            shard_manifests, 1
                        ):
                            source = (
                                output_root
                                / "shards"
                                / f"shard_{shard_number:05d}"
                                / "tables"
                                / str(manifest["tables"][table_key]["path"])
                            )
                            with gzip.open(
                                source,
                                "rt",
                                encoding="utf-8-sig",
                                newline="",
                            ) as src:
                                reader = csv.reader(src)
                                try:
                                    header = next(reader)
                                except StopIteration:
                                    raise RuntimeError(
                                        f"annual source header 없음: {source}"
                                    )
                                if expected_header is None:
                                    expected_header = header
                                    writer.writerow(header)
                                elif header != expected_header:
                                    raise RuntimeError(
                                        f"annual header 불일치: {source}"
                                    )
                                utt_id_index = (
                                    header.index("utt_id")
                                    if table_key == "master"
                                    else -1
                                )
                                for row in reader:
                                    if table_key == "master":
                                        utt_id = row[utt_id_index]
                                        if utt_id in seen_utt_ids:
                                            duplicate_utt_ids += 1
                                        else:
                                            seen_utt_ids.add(utt_id)
                                    writer.writerow(row)
                                    written_rows += 1
                raw.flush()
                os.fsync(raw.fileno())
            if written_rows != expected_rows:
                raise RuntimeError(
                    f"annual row 수 불일치: {table_key} "
                    f"expected={expected_rows} actual={written_rows}"
                )
            info = {**file_info(destination), "rows": written_rows}
            info["path"] = destination.name
            tables[table_key] = info
        if duplicate_utt_ids:
            raise RuntimeError(f"annual duplicate utt_id={duplicate_utt_ids}")
        os.replace(partial_root, final_root)
    except BaseException:
        raise

    manifest = {
        "schema_version": YEAR_SCHEMA_VERSION,
        "status": "success",
        "created_at": datetime.now().astimezone().isoformat(),
        "year": year,
        "input_inventory_sha256": input_inventory_sha256,
        "shards": len(shard_manifests),
        "versions": {
            "morph_schema": MORPH_SCHEMA_VERSION,
            "roman_system": ROMAN_SYSTEM_VERSION,
            "serialization": SERIALIZATION_VERSION,
            "position_schema": POSITION_SCHEMA_VERSION,
            "symbol_schema": SYMBOL_SCHEMA_VERSION,
        },
        "tables": tables,
        "gates": {
            "all_shards_success": True,
            "duplicate_utt_id": 0,
            "deterministic_gzip_mtime": 0,
            "orth_symbol_coverage_equal": True,
        },
        "parquet_status": (
            "pending_separate_analytics_environment_from_gzip_source"
        ),
    }
    atomic_write_json(final_root / "YEAR_MANIFEST.json", manifest)
    return manifest


def build_year(
    *,
    year: str,
    input_root: Path,
    output_root: Path,
    files_per_shard: int,
    emit_orth_components: bool,
    max_shards: int = 0,
    input_pattern: str = "*.csv",
) -> dict[str, object]:
    input_root = input_root.resolve()
    output_root = output_root.resolve()
    input_paths = sorted(input_root.glob(input_pattern))
    if not input_paths:
        raise RuntimeError(f"입력 CSV 0개: {input_root}")
    inventory, inventory_sha = inventory_contract(input_paths)
    shards = chunked(input_paths, files_per_shard)
    expected_contract = {
        "schema_version": RUN_SCHEMA_VERSION,
        "year": year,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "files_per_shard": files_per_shard,
        "input_pattern": input_pattern,
        "emit_orth_components": emit_orth_components,
        "input_files": len(input_paths),
        "input_inventory_sha256": inventory_sha,
        "shards": len(shards),
        "versions": {
            "morph_schema": MORPH_SCHEMA_VERSION,
            "position_schema": POSITION_SCHEMA_VERSION,
            "symbol_schema": SYMBOL_SCHEMA_VERSION,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    contract_path = output_root / "RUN_CONTRACT.json"
    if contract_path.is_file():
        existing = read_json(contract_path)
        comparable = {key: existing.get(key) for key in expected_contract}
        if comparable != expected_contract:
            raise RuntimeError("기존 run contract와 입력/옵션 불일치")
    else:
        atomic_write_json(
            contract_path,
            {
                **expected_contract,
                "created_at": datetime.now().astimezone().isoformat(),
                "input_inventory": inventory,
            },
        )

    completed: list[dict[str, object]] = []
    processed_this_run = 0
    try:
        for shard_index, shard_inputs in enumerate(shards, 1):
            shard_root = output_root / "shards" / f"shard_{shard_index:05d}"
            raw_root = shard_root / "raw"
            raw_partial = shard_root / "raw.partial"
            was_complete = (shard_root / "SHARD_MANIFEST.json").is_file()
            if raw_partial.exists():
                raise RuntimeError(
                    f"미완료 raw shard 보존 중; 자동 삭제 금지: {raw_partial}"
                )
            if not raw_root.exists():
                shard_root.mkdir(parents=True, exist_ok=True)
                print(
                    f"[{year}] shard {shard_index}/{len(shards)} build "
                    f"({len(shard_inputs)} files)",
                    flush=True,
                )
                build_tables(
                    input_paths=shard_inputs,
                    output_root=raw_root,
                    emit_orth_components=emit_orth_components,
                )
            raw_manifest = validate_raw_build(
                raw_root, expected_inputs=shard_inputs, year=year
            )
            package = package_shard(
                shard_root,
                raw_manifest=raw_manifest,
                shard_index=shard_index,
                year=year,
            )
            completed.append(package)
            if not was_complete:
                processed_this_run += 1
            atomic_write_json(
                output_root / "YEAR_PROGRESS.json",
                {
                    "schema_version": RUN_SCHEMA_VERSION,
                    "status": (
                        "running"
                        if shard_index < len(shards)
                        else "shards_complete"
                    ),
                    "observed_at": datetime.now().astimezone().isoformat(),
                    "year": year,
                    "completed_shards": shard_index,
                    "total_shards": len(shards),
                    "percent": round(100 * shard_index / len(shards), 3),
                    "last_shard": shard_index,
                },
            )
            if (
                max_shards > 0
                and processed_this_run >= max_shards
                and shard_index < len(shards)
            ):
                report = {
                    "status": "paused_after_max_shards",
                    "year": year,
                    "completed_shards": shard_index,
                    "total_shards": len(shards),
                    "output_root": str(output_root),
                }
                atomic_write_json(output_root / "YEAR_PROGRESS.json", report)
                return report
    except BaseException as exc:
        atomic_write_json(
            output_root / "YEAR_PROGRESS.json",
            {
                "schema_version": RUN_SCHEMA_VERSION,
                "status": "failed_preserved",
                "observed_at": datetime.now().astimezone().isoformat(),
                "year": year,
                "completed_shards": len(completed),
                "total_shards": len(shards),
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise

    annual = merge_annual_tables(
        output_root=output_root,
        shard_manifests=completed,
        year=year,
        input_inventory_sha256=inventory_sha,
    )
    atomic_write_json(
        output_root / "YEAR_PROGRESS.json",
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "success",
            "observed_at": datetime.now().astimezone().isoformat(),
            "year": year,
            "completed_shards": len(shards),
            "total_shards": len(shards),
            "annual_manifest": str(
                output_root / "annual_tables" / "YEAR_MANIFEST.json"
            ),
        },
    )
    return annual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, choices=[str(y) for y in range(2020, 2026)])
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--files-per-shard", type=int, default=100)
    parser.add_argument("--input-pattern", default="*.csv")
    parser.add_argument("--emit-orth-components", action="store_true")
    parser.add_argument("--max-shards", type=int, default=0)
    args = parser.parse_args()
    if args.files_per_shard < 1:
        parser.error("--files-per-shard must be >= 1")
    if args.max_shards < 0:
        parser.error("--max-shards must be >= 0")
    try:
        report = build_year(
            year=args.year,
            input_root=args.input_root,
            output_root=args.output_root,
            files_per_shard=args.files_per_shard,
            emit_orth_components=args.emit_orth_components,
            max_shards=args.max_shards,
            input_pattern=args.input_pattern,
        )
    except BaseException as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
