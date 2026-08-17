"""Frozen contracts shared by the D9 exact-ID controlled-beam retry."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline_common import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
D8_ID = "nikl_dialogue_research_db_v1_recovery_d8_feasibility_audit_20260817"
D9_ID = "nikl_dialogue_research_db_v1_recovery_d9_gate_20260817"
D9_SHARD_ID = "D9_CONTROLLED_BEAM_RETRY_0001"
D9_OUTPUT_ROOT = (
    Path(r"D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809") / D9_SHARD_ID
)
D9_BEAM = 100
D9_RETRY_BEAM = 400
D9_ROW_COUNT = 19
APPROVAL_SCHEMA = "research_db_v1_recovery_d9_approval.v1"
AUTHORIZATION = "materialize_19_and_run_one_controlled_beam_retry_no_merge"


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


def validate_config(config: dict) -> None:
    if config != {"beam": D9_BEAM, "retry_beam": D9_RETRY_BEAM}:
        raise RuntimeError("D9 MFA configuration differs from beam=100/retry_beam=400")


def validate_approval(
    approval_path: Path,
    *,
    execution_contract_path: Path,
    run_shard_path: Path,
    config_path: Path,
    output_root: Path = D9_OUTPUT_ROOT,
) -> dict:
    approval = load_json(approval_path)
    required = {
        "schema_version": APPROVAL_SCHEMA,
        "status": "approved",
        "shard_id": D9_SHARD_ID,
        "authorization": AUTHORIZATION,
        "execution_contract_sha256": sha256_file(execution_contract_path),
        "run_shard_sha256": sha256_file(run_shard_path),
        "mfa_config_sha256": sha256_file(config_path),
        "output_root": str(output_root.resolve()),
        "approved_row_count": D9_ROW_COUNT,
        "beam": D9_BEAM,
        "retry_beam": D9_RETRY_BEAM,
    }
    for key, expected in required.items():
        if approval.get(key) != expected:
            raise RuntimeError(f"D9 approval contract mismatch: {key}")
    if not str(approval.get("approved_by", "")).strip():
        raise RuntimeError("D9 approval identity missing")
    if not str(approval.get("approved_at", "")).strip():
        raise RuntimeError("D9 approval timestamp missing")
    if approval.get("one_run_only") is not True:
        raise RuntimeError("D9 approval must bind one_run_only=true")
    if approval.get("source_or_r3_body_mutation_allowed") is not False:
        raise RuntimeError("D9 approval must forbid source/r3 body mutation")
    if approval.get("automatic_merge_allowed") is not False:
        raise RuntimeError("D9 approval must forbid automatic merge")
    return approval
