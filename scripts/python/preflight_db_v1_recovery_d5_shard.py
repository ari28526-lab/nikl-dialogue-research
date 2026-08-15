#!/usr/bin/env python3
"""Read-only preflight for the 30-record D5 diagnostic alignment shard."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d5_common import (
    D5_ID,
    D5_OUTPUT_ROOT,
    D5_SHARD_ID,
    PROJECT_ROOT,
    load_json,
    read_gzip_csv,
    validate_approval,
    verify_fingerprint,
)
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


def verify_package(package: Path) -> tuple[dict, dict, Path]:
    manifest_path = package / "OUTPUT_MANIFEST.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "passed_gate_closed_before_D_write_and_mfa":
        raise RuntimeError("D5 gate package status differs")
    for record in manifest.get("files", []):
        verify_fingerprint(record, label="D5 package file")
    for record in manifest.get("implementation", []):
        verify_fingerprint(record, label="D5 implementation")
    manifested = {Path(record["path"]).resolve() for record in manifest["files"]}
    actual = {
        path.resolve() for path in package.iterdir()
        if path.is_file() and path.name != "OUTPUT_MANIFEST.json"
    }
    if manifested != actual:
        raise RuntimeError("D5 package inventory changed")
    contract_path = package / "D5_EXECUTION_CONTRACT.json"
    contract = load_json(contract_path)
    if contract.get("status") != "hold_pending_scope_bound_researcher_approval":
        raise RuntimeError("D5 execution contract gate is not held")
    if contract.get("shard_id") != D5_SHARD_ID:
        raise RuntimeError("D5 execution contract shard differs")
    return manifest, contract, contract_path


def run(args: argparse.Namespace) -> dict:
    project_root = args.project_root.resolve()
    package = args.package.resolve()
    manifest, contract, contract_path = verify_package(package)
    run_shard_path = package / "D5_RUN_SHARD.csv.gz"
    fields, rows = read_gzip_csv(run_shard_path)
    if len(rows) != 30 or len({(row["year"], row["utt_id"]) for row in rows}) != 30:
        raise RuntimeError("D5 run shard count/identity differs")
    if any(row["shard_id"] != D5_SHARD_ID for row in rows):
        raise RuntimeError("D5 run shard ID differs")
    if any(row["reason_code"] != "mfa_alignment_missing" for row in rows):
        raise RuntimeError("D5 run shard includes a non-alignment-missing row")
    for row in rows:
        wav = verify_fingerprint({
            "path": row["source_wav_path"],
            "bytes": int(row["source_wav_bytes"]),
            "sha256": row["source_wav_sha256"],
        }, label=f"D5 source WAV {row['utt_id']}")
        verify_fingerprint({
            "path": row["source_lab_path"],
            "bytes": int(row["source_lab_bytes"]),
            "sha256": row["source_lab_sha256"],
        }, label=f"D5 source LAB {row['utt_id']}")
        with wave.open(str(wav), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
        if duration < 0.1:
            raise RuntimeError(f"D5 executable WAV became too short: {row['utt_id']}")
    for record in contract["models"].values():
        verify_fingerprint(record, label="D5 frozen model")
    mfa = Path(contract["mfa"]["executable"]).resolve()
    if not mfa.is_file():
        raise RuntimeError(f"MFA executable missing: {mfa}")
    if Path(contract["output_root"]).resolve() != D5_OUTPUT_ROOT.resolve():
        raise RuntimeError("D5 output root contract differs")
    if D5_OUTPUT_ROOT.exists() and not (
        D5_OUTPUT_ROOT / "state" / "MATERIALIZATION_MANIFEST.json"
    ).is_file():
        raise RuntimeError("D5 output root exists without its materialization manifest")
    partial = D5_OUTPUT_ROOT.with_name(f".{D5_OUTPUT_ROOT.name}.partial")
    if partial.exists() and not (partial / "PARTIAL_CONTRACT.json").is_file():
        raise RuntimeError("D5 partial root exists without its exact contract")
    drive = shutil.disk_usage("D:/")
    minimum = 20 * 1024**3
    if drive.free < minimum:
        raise RuntimeError(f"D: free space below D5 gate: {drive.free} < {minimum}")
    approval = None
    if args.approval_contract:
        approval = validate_approval(
            args.approval_contract.resolve(),
            execution_contract_path=contract_path,
            run_shard_path=run_shard_path,
            output_root=D5_OUTPUT_ROOT,
        )
    report = {
        "schema_version": "research_db_v1_recovery_d5_preflight.v1",
        "status": "passed_ready_to_execute" if approval else "passed_gate_closed",
        "recorded_at": now_iso(),
        "shard_id": D5_SHARD_ID,
        "rows": len(rows),
        "year_counts": {year: sum(row["year"] == year for row in rows) for year in ("2020", "2021", "2022", "2023", "2024", "2025")},
        "approval_verified": approval is not None,
        "D_free_bytes": drive.free,
        "minimum_D_free_bytes": minimum,
        "output_root": str(D5_OUTPUT_ROOT.resolve()),
        "output_root_present": D5_OUTPUT_ROOT.exists(),
        "files_materialized_by_this_preflight": False,
        "mfa_run_by_this_preflight": False,
        "execution_contract_sha256": sha256_file(contract_path),
        "run_shard_sha256": sha256_file(run_shard_path),
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D5_ID)
    parser.add_argument("--approval-contract", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
