#!/usr/bin/env python3
"""Read-only preflight for the first D4 recovery diagnostic shard."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
from pathlib import Path

from pipeline_common import atomic_write_json, now_iso, runtime_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
D_ID = "nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
SHARD_ID = "D4_POST_MFA_DIAGNOSTIC_0001"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(record: dict) -> Path:
    path = Path(record["path"])
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
        raise RuntimeError(f"fingerprint mismatch: {path}")
    return path


def validate_approval(path: Path, first_sha: str) -> dict:
    approval = load_json(path)
    required = {
        "schema_version": "research_db_v1_recovery_shard_approval.v1",
        "status": "approved",
        "shard_id": SHARD_ID,
        "first_shard_sha256": first_sha,
        "authorization": "materialize_and_run_mfa",
    }
    for key, value in required.items():
        if approval.get(key) != value:
            raise RuntimeError(f"approval contract mismatch: {key}")
    if not str(approval.get("approved_by", "")).strip() or not str(approval.get("approved_at", "")).strip():
        raise RuntimeError("approval identity/timestamp missing")
    return approval


def run(args: argparse.Namespace) -> dict:
    project_root = args.project_root.resolve()
    package = args.package.resolve()
    output_manifest = load_json(package / "OUTPUT_MANIFEST.json")
    audit = load_json(package / "INDEPENDENT_AUDIT.json")
    gate = load_json(package / "D4_first_shard" / "PRE_MFA_GATE.json")
    if output_manifest.get("status") != "passed_stopped_before_materialization_and_mfa":
        raise RuntimeError("D0-D4 output manifest not passed")
    if audit.get("status") != "passed_stopped_before_materialization_and_mfa":
        raise RuntimeError("D0-D4 independent audit not passed")
    if gate.get("status") != "hold_before_materialization_and_mfa":
        raise RuntimeError("D4 gate not held")
    manifested = set()
    for record in output_manifest["files"]:
        manifested.add(verify(record).resolve())
    for record in output_manifest.get("implementation", {}).values():
        verify(record)
    actual = {
        path.resolve() for path in package.rglob("*")
        if path.is_file() and path.name != "OUTPUT_MANIFEST.json"
    }
    if actual != manifested:
        raise RuntimeError("D0-D4 output inventory changed")
    first_path = package / "D4_first_shard" / "FIRST_SHARD.csv.gz"
    rows = 0
    missing_materialized_inputs = []
    with gzip.open(first_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            rows += 1
            for field in ("r3_corpus_wav_path", "r3_corpus_lab_path"):
                if not Path(row[field]).is_file():
                    missing_materialized_inputs.append(f"{row['utt_id']}:{field}")
    if rows != 55 or missing_materialized_inputs:
        raise RuntimeError(f"D4 input state failed: rows={rows}, missing={missing_materialized_inputs[:3]}")
    drive = shutil.disk_usage("D:/")
    minimum = int(gate["capacity"]["minimum_D_free_bytes_before_execution"])
    if drive.free < minimum:
        raise RuntimeError(f"D: free space below gate: {drive.free} < {minimum}")
    approval = None
    if args.approval_contract:
        approval = validate_approval(args.approval_contract.resolve(), sha256(first_path))
    status = "passed_gate_closed" if approval is None else "passed_scope_bound_approval_verified"
    report = {
        "schema_version": "research_db_v1_recovery_first_shard_preflight.v1",
        "status": status, "recorded_at": now_iso(), "shard_id": SHARD_ID,
        "rows": rows, "D_free_bytes": drive.free, "minimum_D_free_bytes": minimum,
        "output_manifest_sha256": sha256(package / "OUTPUT_MANIFEST.json"),
        "independent_audit_sha256": sha256(package / "INDEPENDENT_AUDIT.json"),
        "first_shard_sha256": sha256(first_path),
        "approval_verified": approval is not None,
        "files_materialized": False, "mfa_run": False,
        "stop_point": "immediately before recovery corpus materialization and MFA",
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs" / "releases" / D_ID)
    parser.add_argument("--approval-contract", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
