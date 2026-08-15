#!/usr/bin/env python3
"""Copy the exact approved D5 corpus into an isolated, resumable namespace."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d5_common import (
    D5_ID,
    D5_OUTPUT_ROOT,
    D5_SHARD_ID,
    PROJECT_ROOT,
    fingerprint,
    load_json,
    read_gzip_csv,
    validate_approval,
    verify_fingerprint,
)
from pipeline_common import atomic_text_writer, atomic_write_json, now_iso, runtime_snapshot, sha256_file


def copy_exact(source: Path, destination: Path, expected_sha: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size != source.stat().st_size or sha256_file(destination) != expected_sha:
            raise RuntimeError(f"existing D5 copied file differs: {destination}")
        return
    partial = destination.with_name(f".{destination.name}.partial")
    if partial.exists():
        if partial.stat().st_size == source.stat().st_size and sha256_file(partial) == expected_sha:
            os.replace(partial, destination)
            return
        raise RuntimeError(f"stale D5 per-file partial differs: {partial}")
    shutil.copyfile(source, partial)
    if partial.stat().st_size != source.stat().st_size or sha256_file(partial) != expected_sha:
        raise RuntimeError(f"D5 copy verification failed: {source}")
    os.replace(partial, destination)


def materialize(*, package: Path, approval_path: Path, output_root: Path) -> dict:
    package = package.resolve()
    output_root = output_root.resolve()
    if output_root != D5_OUTPUT_ROOT.resolve():
        raise RuntimeError("D5 materializer output root differs from frozen root")
    contract_path = package / "D5_EXECUTION_CONTRACT.json"
    run_shard_path = package / "D5_RUN_SHARD.csv.gz"
    validate_approval(
        approval_path.resolve(),
        execution_contract_path=contract_path,
        run_shard_path=run_shard_path,
        output_root=output_root,
    )
    contract = load_json(contract_path)
    _, rows = read_gzip_csv(run_shard_path)
    if len(rows) != 30:
        raise RuntimeError("D5 materializer requires exactly 30 rows")
    final_manifest = output_root / "state" / "MATERIALIZATION_MANIFEST.json"
    if final_manifest.is_file():
        manifest = load_json(final_manifest)
        if manifest.get("status") != "passed_exact_copy_materialization" or manifest.get("shard_id") != D5_SHARD_ID:
            raise RuntimeError("existing D5 materialization manifest differs")
        _, existing_rows = read_gzip_csv(run_shard_path)
        for row in existing_rows:
            relative = Path(row["target_relative_directory"])
            target_dir = output_root / "corpus" / relative
            verify_fingerprint({
                "path": str(target_dir / f"{row['utt_id']}.wav"),
                "bytes": int(row["source_wav_bytes"]),
                "sha256": row["source_wav_sha256"],
            }, label=f"existing D5 WAV {row['utt_id']}")
            verify_fingerprint({
                "path": str(target_dir / f"{row['utt_id']}.lab"),
                "bytes": int(row["source_lab_bytes"]),
                "sha256": row["source_lab_sha256"],
            }, label=f"existing D5 LAB {row['utt_id']}")
        return manifest
    if output_root.exists():
        raise RuntimeError("D5 final root exists without a complete materialization manifest")
    partial_root = output_root.with_name(f".{output_root.name}.partial")
    partial_identity = {
        "schema_version": "research_db_v1_recovery_d5_partial.v1",
        "status": "building_resume_allowed",
        "shard_id": D5_SHARD_ID,
        "execution_contract_sha256": sha256_file(contract_path),
        "run_shard_sha256": sha256_file(run_shard_path),
        "final_output_root": str(output_root),
    }
    if partial_root.exists():
        marker = partial_root / "PARTIAL_CONTRACT.json"
        if not marker.is_file() or load_json(marker) != partial_identity:
            raise RuntimeError("existing D5 partial root contract differs")
    else:
        partial_root.mkdir(parents=True, exist_ok=False)
        atomic_write_json(partial_root / "PARTIAL_CONTRACT.json", partial_identity)

    source_before: list[dict] = []
    copy_rows: list[dict] = []
    for row in rows:
        source_wav = verify_fingerprint({
            "path": row["source_wav_path"], "bytes": int(row["source_wav_bytes"]), "sha256": row["source_wav_sha256"]
        }, label=f"source WAV {row['utt_id']}")
        source_lab = verify_fingerprint({
            "path": row["source_lab_path"], "bytes": int(row["source_lab_bytes"]), "sha256": row["source_lab_sha256"]
        }, label=f"source LAB {row['utt_id']}")
        source_before.extend([fingerprint(source_wav), fingerprint(source_lab)])
        relative = Path(row["target_relative_directory"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe D5 relative directory: {relative}")
        target_dir = partial_root / "corpus" / relative
        target_wav = target_dir / f"{row['utt_id']}.wav"
        target_lab = target_dir / f"{row['utt_id']}.lab"
        copy_exact(source_wav, target_wav, row["source_wav_sha256"])
        copy_exact(source_lab, target_lab, row["source_lab_sha256"])
        copy_rows.append({
            "run_order": row["run_order"], "year": row["year"], "utt_id": row["utt_id"], "session_id": row["session_id"],
            "source_wav_path": str(source_wav), "target_wav_relative": str(target_wav.relative_to(partial_root)), "wav_sha256": row["source_wav_sha256"],
            "source_lab_path": str(source_lab), "target_lab_relative": str(target_lab.relative_to(partial_root)), "lab_sha256": row["source_lab_sha256"],
        })
    for record in source_before:
        verify_fingerprint(record, label="source after D5 copy")
    state = partial_root / "state"
    state.mkdir(parents=True, exist_ok=True)
    corpus_manifest = state / "CORPUS_MANIFEST.csv"
    fields = list(copy_rows[0])
    with atomic_text_writer(corpus_manifest, encoding="utf-8-sig", newline="") as (stream, _):
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(copy_rows)
    manifest = {
        "schema_version": "research_db_v1_recovery_d5_materialization.v1",
        "status": "passed_exact_copy_materialization",
        "recorded_at": now_iso(),
        "shard_id": D5_SHARD_ID,
        "rows": len(rows),
        "output_root": str(output_root),
        "corpus_root": str(output_root / "corpus"),
        "execution_contract": fingerprint(contract_path),
        "run_shard": fingerprint(run_shard_path),
        "approval": fingerprint(approval_path.resolve()),
        "corpus_manifest_relative": "state\\CORPUS_MANIFEST.csv",
        "corpus_manifest_sha256": sha256_file(corpus_manifest),
        "safety": {"copy_not_hardlink": True, "source_modified": False, "r3_body_modified": False, "automatic_merge": False},
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(state / "MATERIALIZATION_MANIFEST.json", manifest)
    (partial_root / "PARTIAL_CONTRACT.json").unlink()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(partial_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D5_ID)
    parser.add_argument("--approval-contract", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=D5_OUTPUT_ROOT)
    args = parser.parse_args()
    result = materialize(package=args.package, approval_path=args.approval_contract, output_root=args.output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
