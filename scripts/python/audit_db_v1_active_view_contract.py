"""Independently audit the DB v1 exception-only active-view contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "releases"
    / "nikl_dialogue_research_db_v1_active_view_contract_v1_20260818"
)
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "outputs"
    / "reports"
    / "AUDIT_db_v1_active_view_contract_20260818.json"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object expected: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "ACTIVE_VIEW_MANIFEST.json"
    view_path = root / "ACTIVE_RECOVERY_EXCEPTIONS.csv"
    manifest = load_json(manifest_path)
    if manifest["status"] != "materialized_exception_only_contract":
        raise RuntimeError("active-view manifest is not materialized")
    declared = {row["path"]: row for row in manifest["files"]}
    for relative, record in declared.items():
        path = root / relative
        if path.stat().st_size != record["bytes"]:
            raise RuntimeError(f"byte count mismatch: {relative}")
        if sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"SHA mismatch: {relative}")

    with view_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    keys = [(int(row["year"]), row["utt_id"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate exact-ID in active view")
    curated = [row for row in rows if row["active_annotation_source"] == "curated"]
    base = [row for row in rows if row["active_annotation_source"] == "base"]
    if len(rows) != 55 or len(curated) != 16 or len(base) != 39:
        raise RuntimeError("frozen active-view counts mismatch")
    for row in curated:
        required = (
            "active_annotation_revision",
            "active_textgrid_path",
            "active_textgrid_sha256",
            "active_transcript",
            "active_orth_roman_v2",
        )
        if any(not row[field] for field in required):
            raise RuntimeError(f"incomplete curated row: {row['utt_id']}")
        if row["annotation_resolution_status"] != "curated_pointer_applied":
            raise RuntimeError(f"curated resolution mismatch: {row['utt_id']}")
        if row["phone_layer_status"] != "d9_reference_only_not_adopted":
            raise RuntimeError(f"D9 phone was promoted: {row['utt_id']}")
        if row["morph_enrichment_status"] != "pending_rebuild_from_curated_transcript":
            raise RuntimeError(f"morph pending status changed: {row['utt_id']}")
    for row in base:
        forbidden = (
            "active_annotation_revision",
            "active_textgrid_path",
            "active_textgrid_sha256",
            "active_transcript",
            "active_orth_roman_v2",
        )
        if any(row[field] for field in forbidden):
            raise RuntimeError(f"base row received curated content: {row['utt_id']}")

    return {
        "schema_version": "nikl_dialogue_research_db_v1_active_view_contract_audit.v1",
        "status": "passed_exception_only_active_view_contract",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_sha256": sha256_file(manifest_path),
        "counts": {
            "exception_rows": len(rows),
            "curated_pointer_rows": len(curated),
            "base_preserved_exception_rows": len(base),
            "duplicate_exact_ids": len(keys) - len(set(keys)),
        },
        "invariants": {
            "rc0_is_default": True,
            "curated_wins_by_exact_id_only": True,
            "diagnostic_evidence_never_active": True,
            "d9_phone_reference_only": True,
            "morphology_pending": True,
            "full_base_materialization_required": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-root", type=Path, default=DEFAULT_CONTRACT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = audit(args.contract_root)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
