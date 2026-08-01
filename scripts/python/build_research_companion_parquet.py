"""Build a typed Parquet mirror from annual research companion gzip tables.

The gzip CSV files remain the archival/audit source.  Parquet is a disposable
search mirror and must be regenerated from a successful TABLES_MANIFEST plus
the machine-readable v2 schema.  The script deliberately imports PyArrow only
at execution time so MFA itself does not acquire an analytics dependency.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, sha256_file
from research_companion_schema import load_schema, schema_fingerprint

PARQUET_SCHEMA_VERSION = "mfa_research_companion_parquet.v1"


def _arrow_type(pa, type_name: str):
    mapping = {
        "string": pa.string(),
        "int64": pa.int64(),
        "float64": pa.float64(),
        "bool": pa.bool_(),
    }
    try:
        return mapping[type_name]
    except KeyError as exc:
        raise RuntimeError(f"unsupported companion dtype: {type_name}") from exc


def _load_pyarrow():
    try:
        import pyarrow as pa
        import pyarrow.csv as pacsv
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "PyArrow is required only for the Parquet search mirror. "
            "Install it in a separate analytics environment; do not change "
            "the frozen MFA environment."
        ) from exc
    return pa, pacsv, pq


def build_parquet_mirror(
    *,
    table_root: Path,
    output_root: Path,
    schema_path: Path | None = None,
) -> dict[str, object]:
    pa, pacsv, pq = _load_pyarrow()
    table_root = table_root.resolve()
    output_root = output_root.resolve()
    source_manifest_path = table_root / "TABLES_MANIFEST.json"
    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8-sig")
    )
    schema_path, schema = load_schema(schema_path)
    if source_manifest.get("status") != "success":
        raise RuntimeError("source table manifest is not successful")
    if source_manifest.get("schema_version") != schema["schema_version"]:
        raise RuntimeError("source table/schema version mismatch")
    if (
        source_manifest.get("column_schema", {}).get("sha256")
        != sha256_file(schema_path)
    ):
        raise RuntimeError("source table column-schema fingerprint mismatch")
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"Parquet output root must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    built: dict[str, dict[str, object]] = {}
    try:
        for table_name, table_spec in schema["tables"].items():
            source_info = source_manifest.get("tables", {}).get(table_name)
            if not isinstance(source_info, dict):
                raise RuntimeError(f"source manifest table missing: {table_name}")
            source_path = table_root / str(source_info.get("path", ""))
            if (
                not source_path.is_file()
                or sha256_file(source_path) != source_info.get("sha256")
            ):
                raise RuntimeError(f"source table fingerprint mismatch: {table_name}")

            fields = table_spec["fields"]
            column_types = {
                name: _arrow_type(pa, type_name)
                for name, type_name, _nullable in fields
            }
            arrow_schema = pa.schema(
                [
                    pa.field(name, column_types[name], nullable=nullable)
                    for name, _type_name, nullable in fields
                ]
            )
            reader = pacsv.open_csv(
                str(source_path),
                read_options=pacsv.ReadOptions(
                    use_threads=True,
                    block_size=8 * 1024 * 1024,
                    encoding="utf8",
                ),
                parse_options=pacsv.ParseOptions(delimiter=","),
                convert_options=pacsv.ConvertOptions(
                    column_types=column_types,
                    strings_can_be_null=True,
                    null_values=[""],
                    true_values=["true"],
                    false_values=["false"],
                ),
            )
            destination = output_root / f"{table_name}.parquet"
            partial = output_root / f".{destination.name}.{uuid.uuid4().hex}.partial"
            writer = pq.ParquetWriter(
                str(partial),
                arrow_schema,
                compression="zstd",
                use_dictionary=True,
                write_statistics=True,
            )
            row_count = 0
            try:
                for batch in reader:
                    if batch.schema != arrow_schema:
                        batch = batch.cast(arrow_schema)
                    writer.write_batch(batch)
                    row_count += batch.num_rows
            finally:
                writer.close()
            # Windows rejects fsync on a read-only descriptor; rb+ keeps this
            # durability gate portable without modifying the closed file.
            with open(partial, "rb+") as stream:
                os.fsync(stream.fileno())
            metadata = pq.read_metadata(str(partial))
            if metadata.num_rows != row_count:
                raise RuntimeError(f"Parquet row-count mismatch: {table_name}")
            os.replace(partial, destination)
            built[table_name] = {
                **file_fingerprint(destination, with_sha256=True),
                "path": destination.name,
                "rows": row_count,
                "columns": len(fields),
            }
    except BaseException:
        # Completed files are evidence, not a valid mirror, until the final
        # manifest exists.  Leave them in place for diagnosis; never promote a
        # success manifest after any table failure.
        raise

    manifest = {
        "schema_version": PARQUET_SCHEMA_VERSION,
        "status": "success",
        "role": "disposable typed search mirror; gzip CSV remains archival source",
        "input_contract_id": source_manifest.get("input_contract_id"),
        "alignment_contract_id": source_manifest.get("alignment_contract_id"),
        "source_manifest": file_fingerprint(
            source_manifest_path, with_sha256=True
        ),
        "column_schema": schema_fingerprint(schema_path),
        "tables": built,
    }
    atomic_write_json(output_root / "PARQUET_MANIFEST.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path)
    args = parser.parse_args()
    report = build_parquet_mirror(
        table_root=args.table_root,
        output_root=args.output_root,
        schema_path=args.schema,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
