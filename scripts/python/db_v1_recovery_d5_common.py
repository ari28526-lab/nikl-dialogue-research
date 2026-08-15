"""Shared contracts for the first executable DB-v1 recovery shard.

The D0-D4 package is immutable evidence.  D5 derives a smaller executable
shard from it and never changes the frozen r3 body or source WAV/LAB files.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

from pipeline_common import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
D0_D4_ID = "nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
D5_ID = "nikl_dialogue_research_db_v1_recovery_d5_gate_20260815"
D4_SHARD_ID = "D4_POST_MFA_DIAGNOSTIC_0001"
D5_SHARD_ID = "D5_ALIGNMENT_DIAGNOSTIC_0001"
D5_OUTPUT_ROOT = Path(
    r"D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809"
) / D5_SHARD_ID
APPROVAL_SCHEMA = "research_db_v1_recovery_d5_approval.v1"
AUTHORIZATION = "materialize_30_and_run_diagnostic_mfa"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def verify_fingerprint(record: dict, *, label: str = "file") -> Path:
    path = Path(str(record.get("path", ""))).resolve()
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    if int(record.get("bytes", -1)) != path.stat().st_size:
        raise RuntimeError(f"{label} byte count differs: {path}")
    if str(record.get("sha256", "")).lower() != sha256_file(path).lower():
        raise RuntimeError(f"{label} sha256 differs: {path}")
    return path


def read_gzip_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def validate_approval(
    approval_path: Path,
    *,
    execution_contract_path: Path,
    run_shard_path: Path,
    output_root: Path = D5_OUTPUT_ROOT,
) -> dict:
    approval = load_json(approval_path)
    required = {
        "schema_version": APPROVAL_SCHEMA,
        "status": "approved",
        "shard_id": D5_SHARD_ID,
        "authorization": AUTHORIZATION,
        "execution_contract_sha256": sha256_file(execution_contract_path),
        "run_shard_sha256": sha256_file(run_shard_path),
        "output_root": str(output_root.resolve()),
        "approved_row_count": 30,
    }
    for key, expected in required.items():
        if approval.get(key) != expected:
            raise RuntimeError(f"D5 approval contract mismatch: {key}")
    if not str(approval.get("approved_by", "")).strip():
        raise RuntimeError("D5 approval identity missing")
    if not str(approval.get("approved_at", "")).strip():
        raise RuntimeError("D5 approval timestamp missing")
    if approval.get("source_or_r3_body_mutation_allowed") is not False:
        raise RuntimeError("D5 approval must forbid source/r3 body mutation")
    if approval.get("automatic_merge_allowed") is not False:
        raise RuntimeError("D5 approval must forbid automatic merge")
    return approval
