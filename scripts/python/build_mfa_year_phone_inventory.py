"""Build a year-level observed-phone report without changing alignment data.

The methodological invariant is the *allowed* acoustic-model inventory and
its SHA.  Observed phone sets may differ by year because the corpora differ;
they are recorded descriptively and are not required to be identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
)


SCHEMA_VERSION = "mfa_year_phone_inventory.v1"
ALIGNMENT_SCHEMA_VERSION = "mfa_alignment_contract.v1"
COMMON_SCHEMA_VERSION = "common_pron_mfa_lexicon.v2"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object 아님: {path}")
    return value


def phone_contract(phones: set[str]) -> dict[str, Any]:
    canonical = "\n".join(sorted(phones)) + "\n"
    return {
        "count": len(phones),
        "sorted_phone_sha256": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
        "phones": sorted(phones),
    }


def _table_columns(
    connection: sqlite3.Connection, table: str
) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table})")
    }


def build_year_phone_inventory(
    *,
    db_path: Path,
    year: str,
    common_manifest_path: Path,
    alignment_contract_path: Path,
) -> dict[str, Any]:
    db_path = db_path.resolve()
    common_manifest_path = common_manifest_path.resolve()
    alignment_contract_path = alignment_contract_path.resolve()
    if year not in {"2020", "2021", "2022", "2023", "2024", "2025"}:
        raise RuntimeError(f"지원하지 않는 연도: {year}")
    if not db_path.is_file():
        raise RuntimeError(f"alignment DB 없음: {db_path}")

    common = _load(common_manifest_path)
    alignment = _load(alignment_contract_path)
    if (
        common.get("schema_version") != COMMON_SCHEMA_VERSION
        or common.get("status") != "success"
    ):
        raise RuntimeError("공통사전 manifest gate 실패")
    if (
        alignment.get("schema_version") != ALIGNMENT_SCHEMA_VERSION
        or alignment.get("status") != "passed"
        or str(alignment.get("year")) != year
        or alignment.get("pronunciation_mode")
        != "common_pronunciation"
    ):
        raise RuntimeError("alignment contract gate 실패")

    common_actual = file_fingerprint(
        common_manifest_path, with_sha256=True
    )
    common_record = alignment.get("common_pron_manifest", {})
    if (
        common_record.get("sha256") != common_actual["sha256"]
        or common_record.get("bytes") != common_actual["bytes"]
    ):
        raise RuntimeError(
            "alignment contract와 공통사전 manifest fingerprint 불일치"
        )

    allowed_record = common.get("phone_inventory_contract", {})
    allowed = {
        str(phone)
        for phone in allowed_record.get("phones", [])
        if str(phone)
    }
    allowed_contract = phone_contract(allowed)
    if (
        not allowed
        or allowed_contract["count"] != allowed_record.get("count")
        or allowed_contract["sorted_phone_sha256"]
        != allowed_record.get("sorted_phone_sha256")
    ):
        raise RuntimeError("공통사전 allowed phone inventory 손상")

    uri = f"file:{db_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not {"phone", "phone_interval"}.issubset(tables):
            raise RuntimeError("DB phone/phone_interval table 누락")
        if not {"id", "phone"}.issubset(
            _table_columns(connection, "phone")
        ):
            raise RuntimeError("DB phone table 필드 계약 불일치")
        if not {"phone_id"}.issubset(
            _table_columns(connection, "phone_interval")
        ):
            raise RuntimeError("DB phone_interval 필드 계약 불일치")
        counts = Counter(
            {
                str(phone): int(count)
                for phone, count in connection.execute(
                    "SELECT p.phone, COUNT(*) "
                    "FROM phone_interval pi "
                    "JOIN phone p ON p.id = pi.phone_id "
                    "GROUP BY p.phone ORDER BY p.phone"
                )
                if str(phone)
            }
        )
    finally:
        connection.close()

    observed = set(counts)
    outside = sorted(observed - allowed)
    spn_intervals = int(counts.get("spn", 0))
    observed_contract = phone_contract(observed)
    status = (
        "success"
        if not outside and spn_intervals == 0 and observed
        else "failed"
    )
    stat = db_path.stat()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "recorded_at": now_iso(),
        "year": year,
        "methodological_interpretation": (
            "The allowed phone inventory and its SHA must be identical "
            "across years. Observed phone sets are corpus-dependent "
            "descriptive results and are not required to be identical."
        ),
        "alignment_contract": file_fingerprint(
            alignment_contract_path, with_sha256=True
        ),
        "alignment_contract_id": alignment.get(
            "alignment_contract_id"
        ),
        "common_pron_manifest": common_actual,
        "alignment_db": {
            "path": str(db_path),
            "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        },
        "allowed_phone_inventory": allowed_contract,
        "observed_phone_inventory": observed_contract,
        "observed_interval_counts": dict(sorted(counts.items())),
        "outside_allowed_inventory": outside,
        "spn_intervals": spn_intervals,
        "gate": {
            "allowed_inventory_contract_verified": True,
            "observed_phone_count_positive": bool(observed),
            "observed_outside_allowed": len(outside),
            "spn_intervals": spn_intervals,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument(
        "--common-pron-manifest", type=Path, required=True
    )
    parser.add_argument(
        "--alignment-contract", type=Path, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_year_phone_inventory(
        db_path=args.db,
        year=args.year,
        common_manifest_path=args.common_pron_manifest,
        alignment_contract_path=args.alignment_contract,
    )
    atomic_write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
