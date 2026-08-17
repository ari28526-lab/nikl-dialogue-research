#!/usr/bin/env python3
"""Freeze the 19-record D9 controlled-beam retry package; do not run MFA."""

from __future__ import annotations

import argparse
import json
import sys
import wave
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d9_common import (
    APPROVAL_SCHEMA,
    AUTHORIZATION,
    D8_ID,
    D9_BEAM,
    D9_ID,
    D9_OUTPUT_ROOT,
    D9_RETRY_BEAM,
    D9_ROW_COUNT,
    D9_SHARD_ID,
    PROJECT_ROOT,
    fingerprint,
    load_json,
    validate_config,
    verify_fingerprint,
)
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


D5_CONTRACT = (
    PROJECT_ROOT
    / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d5_gate_20260815"
    / "D5_EXECUTION_CONTRACT.json"
)


def candidate_from_d8(row: dict) -> dict:
    if row.get("d9_candidate") is not True:
        raise RuntimeError(f"non-D9 candidate reached builder: {row.get('utt_id')}")
    if row.get("recovery_disposition") != "d9_controlled_parameter_retry_candidate":
        raise RuntimeError(f"D9 disposition differs: {row.get('utt_id')}")
    if row.get("identity_verified") is not True:
        raise RuntimeError(f"D9 identity not verified: {row.get('utt_id')}")
    wav_record = dict(row["r3_corpus_wav"])
    wav = verify_fingerprint(wav_record, label=f"D9 r3 WAV {row['utt_id']}")
    lab = Path(row["lab_path"]).resolve()
    if not lab.is_file() or sha256_file(lab) != row["lab_sha256"]:
        raise RuntimeError(f"D9 r3 LAB differs: {row['utt_id']}")
    with wave.open(str(wav), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    if duration < 0.3:
        raise RuntimeError(f"D9 WAV below 0.3 seconds: {row['utt_id']}")
    return {
        "run_order": 0,
        "year": int(row["year"]),
        "utt_id": row["utt_id"],
        "session_id": row["session_id"],
        "speaker_id": row["speaker_id"],
        "form": row["form"],
        "lab_text": row["lab_text"],
        "source_overlap": bool(row["source_overlap"]),
        "research_scope_after_possible_recovery": row["research_scope_after_possible_recovery"],
        "source_wav": fingerprint(wav),
        "source_lab": fingerprint(lab),
        "target_relative_directory": f"{row['year']}\\{row['session_id']}",
    }


def build(*, output: Path, d8_root: Path, d5_contract_path: Path) -> dict:
    output = output.resolve()
    d8_root = d8_root.resolve()
    d5_contract_path = d5_contract_path.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"D9 output package already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    d8_manifest = load_json(d8_root / "OUTPUT_MANIFEST.json")
    if d8_manifest.get("schema_version") != "research_db_v1_recovery_d8_manifest.v1":
        raise RuntimeError("D8 output manifest schema differs")
    for record in d8_manifest.get("files", []):
        path = d8_root / record["relative_path"]
        verify_fingerprint(
            {"path": str(path), "bytes": record["bytes"], "sha256": record["sha256"]},
            label="D8 package file",
        )
    d8_audit = load_json(d8_root / "INDEPENDENT_AUDIT.json")
    if d8_audit.get("status") != "passed_read_only_feasibility_gate_closed":
        raise RuntimeError("D8 independent audit status differs")
    d8_gate = load_json(d8_root / "D8_GATE.json")
    if d8_gate.get("status") != "closed_pending_d9_exact_id_approval":
        raise RuntimeError("D8 gate is not closed for D9")
    d8 = load_json(d8_root / "D8_EXACT_ID_FEASIBILITY.json")
    candidates = [candidate_from_d8(row) for row in d8["decisions"] if row.get("d9_candidate") is True]
    candidates.sort(key=lambda row: (row["year"], row["utt_id"]))
    if len(candidates) != D9_ROW_COUNT or len({row["utt_id"] for row in candidates}) != D9_ROW_COUNT:
        raise RuntimeError(f"D9 candidate coverage differs: {len(candidates)}")
    for index, row in enumerate(candidates, 1):
        row["run_order"] = index

    d5 = load_json(d5_contract_path)
    if d5.get("shard_id") != "D5_ALIGNMENT_DIAGNOSTIC_0001":
        raise RuntimeError("D5 execution contract differs")
    models = d5["models"]
    for record in models.values():
        verify_fingerprint(record, label="D9 frozen model")

    run_shard_path = output / "D9_RUN_SHARD.json"
    config_path = output / "D9_MFA_CONFIG.json"
    atomic_write_json(
        run_shard_path,
        {
            "schema_version": "research_db_v1_recovery_d9_run_shard.v1",
            "status": "frozen_pending_scope_bound_approval",
            "shard_id": D9_SHARD_ID,
            "rows": candidates,
        },
    )
    config = {"beam": D9_BEAM, "retry_beam": D9_RETRY_BEAM}
    validate_config(config)
    atomic_write_json(config_path, config)

    counts = Counter(str(row["year"]) for row in candidates)
    contract_path = output / "D9_EXECUTION_CONTRACT.json"
    contract = {
        "schema_version": "research_db_v1_recovery_d9_execution_contract.v1",
        "status": "hold_pending_scope_bound_researcher_approval",
        "recorded_at": now_iso(),
        "shard_id": D9_SHARD_ID,
        "counts": {
            "run_mfa": len(candidates),
            "by_year": dict(sorted(counts.items())),
            "source_overlap_flagged": sum(bool(row["source_overlap"]) for row in candidates),
        },
        "scientific_scope": {
            "purpose": "one controlled wider-beam retry for D5 alignment-missing exact IDs verified by D8",
            "parameter_change_from_D5": {"beam": "10->100", "retry_beam": "40->400"},
            "same_acoustic_model_dictionary_g2p_and_lab": True,
            "realization_decisions_automatic": 0,
            "source_overlap_flag_is_not_single_speaker_approval": True,
            "result_merge_requires_separate_gate": True,
        },
        "output_root": str(D9_OUTPUT_ROOT.resolve()),
        "inputs": {
            "D8_output_manifest": fingerprint(d8_root / "OUTPUT_MANIFEST.json"),
            "D8_gate": fingerprint(d8_root / "D8_GATE.json"),
            "D8_exact_id_feasibility": fingerprint(d8_root / "D8_EXACT_ID_FEASIBILITY.json"),
            "D5_execution_contract": fingerprint(d5_contract_path),
            "D9_run_shard": fingerprint(run_shard_path),
            "D9_mfa_config": fingerprint(config_path),
        },
        "models": models,
        "mfa": {
            "executable": d5["mfa"]["executable"],
            "num_jobs": 4,
            "beam": D9_BEAM,
            "retry_beam": D9_RETRY_BEAM,
            "arguments": [
                "align", "<corpus>", "<dictionary>", "<acoustic>", "<output>",
                "--config_path", "<D9_MFA_CONFIG.json>", "--beam", str(D9_BEAM),
                "--retry_beam", str(D9_RETRY_BEAM), "--num_jobs", "4",
                "--no_tokenization", "--temporary_directory", "<temp>",
                "--output_format", "long_textgrid", "--clean",
            ],
        },
        "safety": {
            "one_run_only": True,
            "source_and_r3_body_read_only": True,
            "copy_not_hardlink": True,
            "fresh_namespace": True,
            "automatic_merge": False,
            "failure_artifacts_preserved": True,
            "whole_year_rerun": False,
            "sub_0_1_second_items_included": False,
        },
    }
    atomic_write_json(contract_path, contract)

    approval = {
        "schema_version": APPROVAL_SCHEMA,
        "status": "pending_researcher_approval",
        "shard_id": D9_SHARD_ID,
        "authorization": AUTHORIZATION,
        "execution_contract_sha256": sha256_file(contract_path),
        "run_shard_sha256": sha256_file(run_shard_path),
        "mfa_config_sha256": sha256_file(config_path),
        "output_root": str(D9_OUTPUT_ROOT.resolve()),
        "approved_row_count": D9_ROW_COUNT,
        "beam": D9_BEAM,
        "retry_beam": D9_RETRY_BEAM,
        "one_run_only": True,
        "source_or_r3_body_mutation_allowed": False,
        "automatic_merge_allowed": False,
        "approved_by": "",
        "approved_at": "",
        "note": "Candidate only. No approval and no MFA execution are implied.",
    }
    atomic_write_json(output / "RESEARCHER_APPROVAL_PENDING.json", approval)
    atomic_write_json(
        output / "README.json",
        {
            "status": "gate_closed",
            "purpose": contract["scientific_scope"]["purpose"],
            "next": "independent preflight, then explicit scope-bound researcher approval",
            "automatic_merge": False,
        },
    )

    package_files = [
        output / "D9_RUN_SHARD.json",
        output / "D9_MFA_CONFIG.json",
        output / "D9_EXECUTION_CONTRACT.json",
        output / "RESEARCHER_APPROVAL_PENDING.json",
        output / "README.json",
    ]
    manifest = {
        "schema_version": "research_db_v1_recovery_d9_output_manifest.v1",
        "status": "passed_gate_closed_before_D_write_and_mfa",
        "recorded_at": now_iso(),
        "files": [fingerprint(path) for path in package_files],
        "implementation": [
            fingerprint(Path(__file__).resolve()),
            fingerprint(Path(__file__).with_name("db_v1_recovery_d9_common.py")),
            fingerprint(PROJECT_ROOT / "scripts/python/preflight_db_v1_recovery_d9.py"),
            fingerprint(PROJECT_ROOT / "scripts/python/materialize_db_v1_recovery_d9_shard.py"),
            fingerprint(PROJECT_ROOT / "scripts/python/audit_db_v1_recovery_d9_mfa.py"),
            fingerprint(PROJECT_ROOT / "scripts/python/build_db_v1_recovery_d9_approval.py"),
            fingerprint(PROJECT_ROOT / "scripts/run_db_v1_recovery_d9_shard.ps1"),
        ],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output / "OUTPUT_MANIFEST.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "outputs/releases" / D9_ID)
    parser.add_argument("--d8-root", type=Path, default=PROJECT_ROOT / "outputs/releases" / D8_ID)
    parser.add_argument("--d5-contract", type=Path, default=D5_CONTRACT)
    args = parser.parse_args()
    result = build(output=args.output, d8_root=args.d8_root, d5_contract_path=args.d5_contract)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
