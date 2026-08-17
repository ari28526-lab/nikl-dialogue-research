#!/usr/bin/env python3
"""Read-only preflight for the D9 19-record controlled-beam retry."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d9_common import (
    D9_BEAM,
    D9_ID,
    D9_OUTPUT_ROOT,
    D9_RETRY_BEAM,
    D9_ROW_COUNT,
    D9_SHARD_ID,
    PROJECT_ROOT,
    load_json,
    validate_approval,
    validate_config,
    verify_fingerprint,
)
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


def verify_package(package: Path) -> tuple[dict, dict, Path, Path, Path]:
    manifest_path = package / "OUTPUT_MANIFEST.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "passed_gate_closed_before_D_write_and_mfa":
        raise RuntimeError("D9 package status differs")
    for record in manifest.get("files", []):
        verify_fingerprint(record, label="D9 package file")
    for record in manifest.get("implementation", []):
        verify_fingerprint(record, label="D9 implementation")
    manifested = {Path(record["path"]).resolve() for record in manifest["files"]}
    actual = {
        path.resolve()
        for path in package.iterdir()
        if path.is_file() and path.name != "OUTPUT_MANIFEST.json"
    }
    if manifested != actual:
        raise RuntimeError("D9 package inventory changed")
    contract_path = package / "D9_EXECUTION_CONTRACT.json"
    run_shard_path = package / "D9_RUN_SHARD.json"
    config_path = package / "D9_MFA_CONFIG.json"
    contract = load_json(contract_path)
    if contract.get("status") != "hold_pending_scope_bound_researcher_approval":
        raise RuntimeError("D9 execution contract gate is not held")
    if contract.get("shard_id") != D9_SHARD_ID:
        raise RuntimeError("D9 execution contract shard differs")
    return manifest, contract, contract_path, run_shard_path, config_path


def run(args: argparse.Namespace) -> dict:
    project_root = args.project_root.resolve()
    package = args.package.resolve()
    _, contract, contract_path, run_shard_path, config_path = verify_package(package)
    shard = load_json(run_shard_path)
    rows = shard.get("rows", [])
    if len(rows) != D9_ROW_COUNT or len({row["utt_id"] for row in rows}) != D9_ROW_COUNT:
        raise RuntimeError("D9 run shard identity/count differs")
    if shard.get("status") != "frozen_pending_scope_bound_approval":
        raise RuntimeError("D9 run shard status differs")
    if any(row.get("run_order") != index for index, row in enumerate(rows, 1)):
        raise RuntimeError("D9 run order differs")
    if any(float(row["source_wav"].get("bytes", 0)) <= 44 for row in rows):
        raise RuntimeError("D9 run shard includes empty audio")
    for row in rows:
        wav = verify_fingerprint(row["source_wav"], label=f"D9 source WAV {row['utt_id']}")
        verify_fingerprint(row["source_lab"], label=f"D9 source LAB {row['utt_id']}")
        with wave.open(str(wav), "rb") as audio:
            if audio.getnframes() / audio.getframerate() < 0.3:
                raise RuntimeError(f"D9 source WAV became too short: {row['utt_id']}")
    validate_config(load_json(config_path))
    if contract["mfa"].get("beam") != D9_BEAM or contract["mfa"].get("retry_beam") != D9_RETRY_BEAM:
        raise RuntimeError("D9 contract beam differs")
    for record in contract["models"].values():
        verify_fingerprint(record, label="D9 frozen model")
    mfa = Path(contract["mfa"]["executable"]).resolve()
    if not mfa.is_file():
        raise RuntimeError(f"MFA executable missing: {mfa}")
    if Path(contract["output_root"]).resolve() != D9_OUTPUT_ROOT.resolve():
        raise RuntimeError("D9 output root contract differs")
    if D9_OUTPUT_ROOT.exists() and not (
        D9_OUTPUT_ROOT / "state" / "MATERIALIZATION_MANIFEST.json"
    ).is_file():
        raise RuntimeError("D9 output root exists without materialization manifest")
    partial = D9_OUTPUT_ROOT.with_name(f".{D9_OUTPUT_ROOT.name}.partial")
    if partial.exists() and not (partial / "PARTIAL_CONTRACT.json").is_file():
        raise RuntimeError("D9 partial root exists without exact contract")
    drive = shutil.disk_usage("D:/")
    minimum = 10 * 1024**3
    if drive.free < minimum:
        raise RuntimeError(f"D: free space below D9 gate: {drive.free} < {minimum}")
    approval = None
    if args.approval_contract:
        approval = validate_approval(
            args.approval_contract.resolve(),
            execution_contract_path=contract_path,
            run_shard_path=run_shard_path,
            config_path=config_path,
        )
    report = {
        "schema_version": "research_db_v1_recovery_d9_preflight.v1",
        "status": "passed_ready_to_execute" if approval else "passed_gate_closed",
        "recorded_at": now_iso(),
        "shard_id": D9_SHARD_ID,
        "rows": len(rows),
        "year_counts": {
            year: sum(str(row["year"]) == year for row in rows)
            for year in ("2020", "2021", "2022", "2023", "2024", "2025")
        },
        "beam": D9_BEAM,
        "retry_beam": D9_RETRY_BEAM,
        "approval_verified": approval is not None,
        "D_free_bytes": drive.free,
        "minimum_D_free_bytes": minimum,
        "output_root": str(D9_OUTPUT_ROOT.resolve()),
        "output_root_present": D9_OUTPUT_ROOT.exists(),
        "files_materialized_by_this_preflight": False,
        "mfa_run_by_this_preflight": False,
        "execution_contract_sha256": sha256_file(contract_path),
        "run_shard_sha256": sha256_file(run_shard_path),
        "mfa_config_sha256": sha256_file(config_path),
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D9_ID)
    parser.add_argument("--approval-contract", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
