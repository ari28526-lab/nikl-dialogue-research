"""연구 동반표 CSV/Parquet 공용 dtype·결측 계약."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from pipeline_common import file_fingerprint

DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "research_companion_tables_schema_v2.json"
)
ALLOWED_TYPES = {"string", "int64", "float64", "bool"}


def load_schema(path: Path | None = None) -> tuple[Path, dict]:
    path = (path or DEFAULT_SCHEMA_PATH).resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("schema_version") != "mfa_research_companion_tables.v2":
        raise RuntimeError("동반표 schema_version 불일치")
    tables = data.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise RuntimeError("동반표 tables schema 누락")
    for table_name, table in tables.items():
        fields = table.get("fields") if isinstance(table, dict) else None
        if not isinstance(fields, list) or not fields:
            raise RuntimeError(f"{table_name}: fields 누락")
        names: list[str] = []
        for item in fields:
            if (
                not isinstance(item, list)
                or len(item) != 3
                or not isinstance(item[0], str)
                or item[1] not in ALLOWED_TYPES
                or not isinstance(item[2], bool)
            ):
                raise RuntimeError(f"{table_name}: 잘못된 field spec {item!r}")
            names.append(item[0])
        if len(names) != len(set(names)):
            raise RuntimeError(f"{table_name}: 중복 field")
        if not set(table.get("primary_key", [])) <= set(names):
            raise RuntimeError(f"{table_name}: primary key가 field 밖")
    return path, data


def validate_field_order(
    schema: Mapping[str, object], expected: Mapping[str, Sequence[str]]
) -> None:
    tables = schema["tables"]
    if set(tables) != set(expected):
        raise RuntimeError(
            f"동반표 table 집합 불일치: {set(tables)} != {set(expected)}"
        )
    for name, fields in expected.items():
        actual = [item[0] for item in tables[name]["fields"]]
        if actual != list(fields):
            raise RuntimeError(f"{name}: schema field order 불일치")


def schema_fingerprint(path: Path | None = None) -> dict:
    resolved, _data = load_schema(path)
    return file_fingerprint(resolved, with_sha256=True)
