#!/usr/bin/env python3
"""Derive the first executable recovery shard and stop at its approval gate."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import wave
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d5_common import (
    AUTHORIZATION,
    D0_D4_ID,
    D4_SHARD_ID,
    D5_ID,
    D5_OUTPUT_ROOT,
    D5_SHARD_ID,
    PROJECT_ROOT,
    fingerprint,
    load_json,
    read_gzip_csv,
    verify_fingerprint,
)
from pipeline_common import atomic_text_writer, atomic_write_json, now_iso, runtime_snapshot, sha256_file


RUN_FIELDS = (
    "run_order", "shard_id", "year", "utt_id", "session_id",
    "reason_code", "source_wav_path", "source_wav_bytes",
    "source_wav_sha256", "source_lab_path", "source_lab_bytes",
    "source_lab_sha256", "lab_token_count", "wav_duration_seconds",
    "target_relative_directory",
)


def write_csv(path: Path, fields: tuple[str, ...] | list[str], rows: list[dict]) -> None:
    with atomic_text_writer(path, encoding="utf-8-sig", newline="") as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_gzip_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.partial")
    with temp.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            import io
            with io.TextIOWrapper(compressed, encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(
                    stream, fieldnames=fields, extrasaction="ignore",
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(rows)
    os.replace(temp, path)


def load_dictionary_words(path: Path) -> set[str]:
    words: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for line in stream:
            word = line.split("\t", 1)[0].strip()
            if word:
                words.add(word)
    return words


def wav_audit(path: Path) -> dict:
    with wave.open(str(path), "rb") as audio:
        frames = audio.getnframes()
        rate = audio.getframerate()
        return {
            "wav_channels": audio.getnchannels(),
            "wav_sample_width_bytes": audio.getsampwidth(),
            "wav_sample_rate": rate,
            "wav_frames": frames,
            "wav_duration_seconds": frames / rate if rate else 0.0,
        }


def classify_d5(reason: str, duration: float, oov_count: int) -> tuple[str, str]:
    if reason == "mfa_feature_generation_failed" and duration < 0.1:
        return (
            "hold_for_audio_duration_recovery_no_same_input_mfa",
            "observed_feature_failure_and_wav_duration_lt_0_1_seconds",
        )
    if reason == "mfa_alignment_missing" and duration >= 0.1 and oov_count == 0:
        return "approved_candidate_for_fresh_subset_diagnostic", ""
    return "unexpected_combination_fail_closed", "unclassified_D5_input"


def run(args: argparse.Namespace) -> dict:
    project_root = args.project_root.resolve()
    source_package = args.d0_d4_package.resolve()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"D5 output already exists; no overwrite: {output}")

    d0_manifest_path = source_package / "OUTPUT_MANIFEST.json"
    d0_audit_path = source_package / "INDEPENDENT_AUDIT.json"
    d4_gate_path = source_package / "D4_first_shard" / "PRE_MFA_GATE.json"
    d4_shard_path = source_package / "D4_first_shard" / "FIRST_SHARD.csv.gz"
    d0_manifest = load_json(d0_manifest_path)
    d0_audit = load_json(d0_audit_path)
    d4_gate = load_json(d4_gate_path)
    if d0_manifest.get("status") != "passed_stopped_before_materialization_and_mfa":
        raise RuntimeError("D0-D4 package is not passed")
    if d0_audit.get("status") != "passed_stopped_before_materialization_and_mfa":
        raise RuntimeError("D0-D4 independent audit is not passed")
    if d4_gate.get("status") != "hold_before_materialization_and_mfa":
        raise RuntimeError("D4 gate is not held")
    for record in d0_manifest["files"]:
        verify_fingerprint(record, label="D0-D4 package file")

    alignment_path = args.alignment_contract.resolve()
    alignment = load_json(alignment_path)
    if alignment.get("schema_version") != "mfa_r3_alignment_contract.v1":
        raise RuntimeError("frozen alignment contract schema differs")
    models = alignment["models"]
    dictionary_path = verify_fingerprint(models["dictionary"], label="dictionary")
    verify_fingerprint(models["acoustic"], label="acoustic model")
    verify_fingerprint(models["g2p_provenance"], label="G2P provenance")
    dictionary_words = load_dictionary_words(dictionary_path)

    _, source_rows = read_gzip_csv(d4_shard_path)
    if len(source_rows) != 55:
        raise RuntimeError("D4 first shard row count differs")
    seen: set[tuple[str, str]] = set()
    audited: list[dict] = []
    run_rows: list[dict] = []
    no_run: list[dict] = []
    run_tokens: set[str] = set()
    for source in source_rows:
        if source.get("shard_id") != D4_SHARD_ID:
            raise RuntimeError("D4 source shard identity differs")
        key = (source["year"], source["utt_id"])
        if key in seen:
            raise RuntimeError(f"duplicate D4 key: {key}")
        seen.add(key)
        wav_path = Path(source["r3_corpus_wav_path"]).resolve()
        lab_path = Path(source["r3_corpus_lab_path"]).resolve()
        if not wav_path.is_file() or not lab_path.is_file():
            raise RuntimeError(f"D4 source file missing: {key}")
        if wav_path.stat().st_size != int(source["r3_corpus_wav_bytes"]):
            raise RuntimeError(f"D4 source WAV size differs: {key}")
        if lab_path.stat().st_size != int(source["r3_corpus_lab_bytes"]):
            raise RuntimeError(f"D4 source LAB size differs: {key}")
        lab_text = lab_path.read_text(encoding="utf-8-sig").strip()
        if not lab_text:
            raise RuntimeError(f"D4 source LAB empty: {key}")
        tokens = lab_text.split()
        oov = sorted(set(tokens) - dictionary_words)
        audio = wav_audit(wav_path)
        reason = source["reason_code"]
        disposition, no_run_reason = classify_d5(
            reason, audio["wav_duration_seconds"], len(oov)
        )
        record = {
            **source,
            **audio,
            "source_wav_sha256": sha256_file(wav_path),
            "source_lab_sha256": sha256_file(lab_path),
            "lab_utf8_valid": True,
            "lab_has_hangul": any(0xAC00 <= ord(char) <= 0xD7A3 for char in lab_text),
            "lab_token_count": len(tokens),
            "dictionary_oov_count": len(oov),
            "dictionary_oov_json": json.dumps(oov, ensure_ascii=False),
            "d5_disposition": disposition,
            "d5_no_run_reason": no_run_reason,
        }
        audited.append(record)
        if disposition == "approved_candidate_for_fresh_subset_diagnostic":
            run_tokens.update(tokens)
            run_rows.append({
                "run_order": len(run_rows) + 1,
                "shard_id": D5_SHARD_ID,
                "year": source["year"],
                "utt_id": source["utt_id"],
                "session_id": source["session_id"],
                "reason_code": reason,
                "source_wav_path": str(wav_path),
                "source_wav_bytes": wav_path.stat().st_size,
                "source_wav_sha256": record["source_wav_sha256"],
                "source_lab_path": str(lab_path),
                "source_lab_bytes": lab_path.stat().st_size,
                "source_lab_sha256": record["source_lab_sha256"],
                "lab_token_count": len(tokens),
                "wav_duration_seconds": f'{audio["wav_duration_seconds"]:.9f}',
                "target_relative_directory": str(Path(source["year"]) / source["session_id"]),
            })
        elif disposition.startswith("hold_for_audio_duration"):
            no_run.append(record)
        else:
            raise RuntimeError(f"D5 input not safely classified: {key}")
    if len(run_rows) != 30 or len(no_run) != 25:
        raise RuntimeError(f"D5 split differs: run={len(run_rows)}, no_run={len(no_run)}")

    output.mkdir(parents=True, exist_ok=False)
    audit_fields = list(audited[0])
    audit_path = output / "D5_INPUT_AUDIT.csv"
    no_run_path = output / "D5_NO_RUN_AUDIO_DURATION_RECOVERY.csv"
    run_path = output / "D5_RUN_SHARD.csv.gz"
    write_csv(audit_path, audit_fields, audited)
    write_csv(no_run_path, audit_fields, no_run)
    write_gzip_csv(run_path, RUN_FIELDS, run_rows)

    execution = {
        "schema_version": "research_db_v1_recovery_d5_execution_contract.v1",
        "status": "hold_pending_scope_bound_researcher_approval",
        "recorded_at": now_iso(),
        "shard_id": D5_SHARD_ID,
        "counts": {
            "D4_audited": 55,
            "run_mfa": 30,
            "no_same_input_mfa_audio_duration_recovery": 25,
            "run_unique_lab_tokens": len(run_tokens),
        },
        "scientific_scope": {
            "purpose": "fresh subset diagnostic for prior post-MFA alignment-missing records",
            "realization_decisions_automatic": 0,
            "no_run_25_interpretation": "technical recovery routing, not linguistic exclusion",
            "result_merge_requires_separate_gate": True,
        },
        "output_root": str(D5_OUTPUT_ROOT.resolve()),
        "inputs": {
            "D0_D4_output_manifest": fingerprint(d0_manifest_path),
            "D0_D4_independent_audit": fingerprint(d0_audit_path),
            "D4_gate": fingerprint(d4_gate_path),
            "D4_first_shard": fingerprint(d4_shard_path),
            "D5_run_shard": fingerprint(run_path),
            "D5_no_run_inventory": fingerprint(no_run_path),
            "alignment_contract": fingerprint(alignment_path),
        },
        "models": models,
        "mfa": {
            "executable": str(args.mfa_executable.resolve()),
            "num_jobs": 4,
            "arguments": ["align", "<corpus>", "<dictionary>", "<acoustic>", "<output>", "--num_jobs", "4", "--no_tokenization", "--temporary_directory", "<temp>", "--output_format", "long_textgrid", "--clean"],
        },
        "safety": {
            "source_and_r3_body_read_only": True,
            "copy_not_hardlink": True,
            "fresh_namespace": True,
            "automatic_merge": False,
            "failure_artifacts_preserved": True,
            "whole_year_rerun": False,
        },
    }
    execution_path = output / "D5_EXECUTION_CONTRACT.json"
    atomic_write_json(execution_path, execution)
    approval = {
        "schema_version": "research_db_v1_recovery_d5_approval.v1",
        "status": "pending_researcher_approval",
        "shard_id": D5_SHARD_ID,
        "authorization": AUTHORIZATION,
        "execution_contract_sha256": sha256_file(execution_path),
        "run_shard_sha256": sha256_file(run_path),
        "output_root": str(D5_OUTPUT_ROOT.resolve()),
        "approved_row_count": 30,
        "source_or_r3_body_mutation_allowed": False,
        "automatic_merge_allowed": False,
        "approved_by": "",
        "approved_at": "",
        "note": "This is a candidate, not an approval. Copy only after explicit researcher approval.",
    }
    atomic_write_json(output / "RESEARCHER_APPROVAL_PENDING.json", approval)
    readme = f"""# DB v1 recovery D5 execution gate

- D4 55건을 바이트·WAV 헤더·공통사전으로 다시 감사했다.
- 25건은 기존 WAV가 0.1초 미만이며 실제 feature-generation 실패군이므로 동일 입력 MFA를 반복하지 않는다. 원 음원 길이 회수 대상으로 보존한다.
- 나머지 alignment-missing 30건만 `{D5_SHARD_ID}`로 고정했다.
- LAB는 정상 UTF-8 한글이며, 사용 어휘는 고정 공통사전에 모두 존재한다.
- 승인 전에는 `{D5_OUTPUT_ROOT}`를 만들지 않고 MFA도 실행하지 않는다.
- 실행 결과는 진단 자료이며 r3 본체나 DB v1에 자동 병합하지 않는다.
"""
    (output / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    implementation_paths = [
        project_root / "scripts/python/db_v1_recovery_d5_common.py",
        project_root / "scripts/python/prepare_db_v1_recovery_d5_execution.py",
        project_root / "scripts/python/preflight_db_v1_recovery_d5_shard.py",
        project_root / "scripts/python/materialize_db_v1_recovery_d5_shard.py",
        project_root / "scripts/python/audit_db_v1_recovery_d5_mfa.py",
        project_root / "scripts/run_db_v1_recovery_d5_shard.ps1",
    ]
    manifest = {
        "schema_version": "research_db_v1_recovery_d5_gate_manifest.v1",
        "status": "passed_gate_closed_before_D_write_and_mfa",
        "recorded_at": now_iso(),
        "shard_id": D5_SHARD_ID,
        "counts": execution["counts"],
        "files": [fingerprint(path) for path in sorted(output.iterdir()) if path.is_file()],
        "implementation": [fingerprint(path) for path in implementation_paths],
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(output / "OUTPUT_MANIFEST.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--d0-d4-package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D0_D4_ID)
    parser.add_argument("--alignment-contract", type=Path, default=Path(r"D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\04_alignment_contracts\2020\ALIGNMENT_CONTRACT_2020.json"))
    parser.add_argument("--mfa-executable", type=Path, default=Path(r"C:\Users\ari30\miniforge3\envs\mfa\Scripts\mfa.exe"))
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "outputs/releases" / D5_ID)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
