#!/usr/bin/env python3
"""Copy the approved D9 exact-ID corpus into an isolated namespace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d9_common import (
    D9_ID,
    D9_OUTPUT_ROOT,
    D9_ROW_COUNT,
    D9_SHARD_ID,
    PROJECT_ROOT,
    fingerprint,
    load_json,
    validate_approval,
    verify_fingerprint,
)
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


def copy_exact(source: Path, destination: Path, expected_sha: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size != source.stat().st_size or sha256_file(destination) != expected_sha:
            raise RuntimeError(f"existing D9 copied file differs: {destination}")
        return
    partial = destination.with_name(f".{destination.name}.partial")
    if partial.exists():
        if partial.stat().st_size == source.stat().st_size and sha256_file(partial) == expected_sha:
            os.replace(partial, destination)
            return
        raise RuntimeError(f"stale D9 per-file partial differs: {partial}")
    shutil.copyfile(source, partial)
    if partial.stat().st_size != source.stat().st_size or sha256_file(partial) != expected_sha:
        raise RuntimeError(f"D9 copy verification failed: {source}")
    os.replace(partial, destination)


def materialize(*, package: Path, approval_path: Path, output_root: Path) -> dict:
    package = package.resolve()
    output_root = output_root.resolve()
    if output_root != D9_OUTPUT_ROOT.resolve():
        raise RuntimeError("D9 materializer output root differs from frozen root")
    contract_path = package / "D9_EXECUTION_CONTRACT.json"
    run_shard_path = package / "D9_RUN_SHARD.json"
    config_path = package / "D9_MFA_CONFIG.json"
    validate_approval(
        approval_path.resolve(),
        execution_contract_path=contract_path,
        run_shard_path=run_shard_path,
        config_path=config_path,
        output_root=output_root,
    )
    rows = load_json(run_shard_path)["rows"]
    if len(rows) != D9_ROW_COUNT:
        raise RuntimeError("D9 materializer row count differs")
    final_manifest = output_root / "state" / "MATERIALIZATION_MANIFEST.json"
    if final_manifest.is_file():
        manifest = load_json(final_manifest)
        if manifest.get("status") != "passed_exact_copy_materialization" or manifest.get("shard_id") != D9_SHARD_ID:
            raise RuntimeError("existing D9 materialization manifest differs")
        for row in rows:
            target = output_root / "corpus" / row["target_relative_directory"]
            verify_fingerprint(
                {**row["source_wav"], "path": str(target / f"{row['utt_id']}.wav")},
                label=f"existing D9 WAV {row['utt_id']}",
            )
            verify_fingerprint(
                {**row["source_lab"], "path": str(target / f"{row['utt_id']}.lab")},
                label=f"existing D9 LAB {row['utt_id']}",
            )
        return manifest
    if output_root.exists():
        raise RuntimeError("D9 final root exists without complete materialization manifest")
    partial_root = output_root.with_name(f".{output_root.name}.partial")
    partial_identity = {
        "schema_version": "research_db_v1_recovery_d9_partial.v1",
        "status": "building_resume_allowed",
        "shard_id": D9_SHARD_ID,
        "execution_contract_sha256": sha256_file(contract_path),
        "run_shard_sha256": sha256_file(run_shard_path),
        "mfa_config_sha256": sha256_file(config_path),
        "final_output_root": str(output_root),
    }
    if partial_root.exists():
        marker = partial_root / "PARTIAL_CONTRACT.json"
        if not marker.is_file() or load_json(marker) != partial_identity:
            raise RuntimeError("existing D9 partial root contract differs")
    else:
        partial_root.mkdir(parents=True, exist_ok=False)
        atomic_write_json(partial_root / "PARTIAL_CONTRACT.json", partial_identity)
    copied: list[dict] = []
    for row in rows:
        source_wav = verify_fingerprint(row["source_wav"], label=f"D9 source WAV {row['utt_id']}")
        source_lab = verify_fingerprint(row["source_lab"], label=f"D9 source LAB {row['utt_id']}")
        relative = Path(row["target_relative_directory"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe D9 relative directory: {relative}")
        target_dir = partial_root / "corpus" / relative
        target_wav = target_dir / f"{row['utt_id']}.wav"
        target_lab = target_dir / f"{row['utt_id']}.lab"
        copy_exact(source_wav, target_wav, row["source_wav"]["sha256"])
        copy_exact(source_lab, target_lab, row["source_lab"]["sha256"])
        copied.append(
            {
                "run_order": row["run_order"],
                "year": row["year"],
                "utt_id": row["utt_id"],
                "session_id": row["session_id"],
                "target_wav_relative": str(target_wav.relative_to(partial_root)),
                "target_lab_relative": str(target_lab.relative_to(partial_root)),
            }
        )
    state = partial_root / "state"
    state.mkdir(parents=True, exist_ok=True)
    atomic_write_json(state / "CORPUS_MANIFEST.json", {"rows": copied})
    manifest = {
        "schema_version": "research_db_v1_recovery_d9_materialization.v1",
        "status": "passed_exact_copy_materialization",
        "recorded_at": now_iso(),
        "shard_id": D9_SHARD_ID,
        "rows": len(rows),
        "output_root": str(output_root),
        "corpus_root": str(output_root / "corpus"),
        "execution_contract": fingerprint(contract_path),
        "run_shard": fingerprint(run_shard_path),
        "mfa_config": fingerprint(config_path),
        "approval": fingerprint(approval_path.resolve()),
        "safety": {
            "copy_not_hardlink": True,
            "source_modified": False,
            "r3_body_modified": False,
            "automatic_merge": False,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(state / "MATERIALIZATION_MANIFEST.json", manifest)
    (partial_root / "PARTIAL_CONTRACT.json").unlink()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(partial_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D9_ID)
    parser.add_argument("--approval-contract", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=D9_OUTPUT_ROOT)
    args = parser.parse_args()
    result = materialize(package=args.package, approval_path=args.approval_contract, output_root=args.output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
