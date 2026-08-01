"""Verify exact logical equality of a small gzip-CSV/Parquet QC mirror."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file
from research_companion_schema import load_schema

SCHEMA_VERSION = "mfa_research_companion_parquet_roundtrip.v1"


def _load_pyarrow():
    try:
        import pyarrow as pa
        import pyarrow.csv as pacsv
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("PyArrow is required for Parquet roundtrip QC") from exc
    return pa, pacsv, pq


def _type(pa, name: str):
    return {
        "string": pa.string(), "int64": pa.int64(),
        "float64": pa.float64(), "bool": pa.bool_(),
    }[name]


def verify_roundtrip(
    *,
    table_root: Path,
    parquet_root: Path,
    report_path: Path,
    schema_path: Path | None = None,
    max_rows_per_table: int = 1_000_000,
) -> dict[str, object]:
    pa, pacsv, pq = _load_pyarrow()
    table_root = table_root.resolve()
    parquet_root = parquet_root.resolve()
    schema_path, schema = load_schema(schema_path)
    source_manifest_path = table_root / "TABLES_MANIFEST.json"
    parquet_manifest_path = parquet_root / "PARQUET_MANIFEST.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8-sig"))
    parquet_manifest = json.loads(parquet_manifest_path.read_text(encoding="utf-8-sig"))
    if (
        source_manifest.get("status") != "success"
        or parquet_manifest.get("status") != "success"
    ):
        raise RuntimeError("source/parquet manifest not successful")
    if (
        parquet_manifest.get("source_manifest", {}).get("sha256")
        != sha256_file(source_manifest_path)
    ):
        raise RuntimeError("Parquet mirror source-manifest SHA mismatch")

    tables: dict[str, dict[str, object]] = {}
    for name, spec in schema["tables"].items():
        source_info = source_manifest["tables"][name]
        parquet_info = parquet_manifest["tables"][name]
        source = table_root / source_info["path"]
        parquet = parquet_root / parquet_info["path"]
        if sha256_file(source) != source_info["sha256"]:
            raise RuntimeError(f"source SHA mismatch: {name}")
        if sha256_file(parquet) != parquet_info["sha256"]:
            raise RuntimeError(f"Parquet SHA mismatch: {name}")
        if int(parquet_info["rows"]) > max_rows_per_table:
            raise RuntimeError(
                f"roundtrip QC row cap exceeded for {name}: "
                f"{parquet_info['rows']} > {max_rows_per_table}"
            )
        fields = spec["fields"]
        column_types = {field: _type(pa, dtype) for field, dtype, _null in fields}
        arrow_schema = pa.schema(
            [pa.field(field, column_types[field], nullable=nullable)
             for field, _dtype, nullable in fields]
        )
        csv_table = pacsv.read_csv(
            str(source),
            read_options=pacsv.ReadOptions(use_threads=True, encoding="utf8"),
            parse_options=pacsv.ParseOptions(delimiter=","),
            convert_options=pacsv.ConvertOptions(
                column_types=column_types,
                strings_can_be_null=True,
                null_values=[""],
                true_values=["true"],
                false_values=["false"],
            ),
        ).cast(arrow_schema).combine_chunks()
        parquet_table = pq.read_table(str(parquet)).cast(arrow_schema).combine_chunks()
        equal = csv_table.equals(parquet_table, check_metadata=True)
        tables[name] = {
            "rows": csv_table.num_rows,
            "columns": csv_table.num_columns,
            "schema_equal": csv_table.schema.equals(
                parquet_table.schema, check_metadata=True
            ),
            "logical_equal": equal,
        }
    status = "success" if all(row["logical_equal"] for row in tables.values()) else "failed"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "verified_at": now_iso(),
        "scope": "small QC mirror only; not an annual full-table in-memory verifier",
        "source_manifest": file_fingerprint(source_manifest_path, with_sha256=True),
        "parquet_manifest": file_fingerprint(parquet_manifest_path, with_sha256=True),
        "column_schema": file_fingerprint(schema_path, with_sha256=True),
        "tables": tables,
    }
    atomic_write_json(report_path.resolve(), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-root", type=Path, required=True)
    parser.add_argument("--parquet-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--max-rows-per-table", type=int, default=1_000_000)
    args = parser.parse_args()
    report = verify_roundtrip(
        table_root=args.table_root, parquet_root=args.parquet_root,
        report_path=args.report, schema_path=args.schema,
        max_rows_per_table=args.max_rows_per_table,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
