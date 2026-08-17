#!/usr/bin/env python3
"""Independently audit D8 exact-ID feasibility and closed safety gate."""

from __future__ import annotations

import argparse
import json
import hashlib
import sqlite3
import sys
import wave
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d8_feasibility_audit_20260817"
D6_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d6_gate_20260815"
BUILDER = PROJECT_ROOT / "scripts/python/build_db_v1_recovery_d8_feasibility_audit.py"


def wav_payload_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with wave.open(str(path), "rb") as stream:
        while True:
            block = stream.readframes(65_536)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(root: Path) -> int:
    manifest = json.loads((root / "OUTPUT_MANIFEST.json").read_text(encoding="utf-8-sig"))
    expected_inputs = {
        "d6_missing_19_sha256": sha256_file(D6_ROOT / "D6_MISSING_19_TECHNICAL_LEDGER.csv"),
        "d6_no_run_25_sha256": sha256_file(D6_ROOT / "D6_NO_RUN_25_AUDIO_RECOVERY.csv"),
        "d6_manifest_sha256": sha256_file(D6_ROOT / "OUTPUT_MANIFEST.json"),
    }
    if manifest.get("inputs") != expected_inputs:
        raise RuntimeError("D8 manifest input fingerprints differ")
    if manifest.get("implementation", {}).get("builder_sha256") != sha256_file(BUILDER):
        raise RuntimeError("D8 builder fingerprint differs")
    verified = 0
    for record in manifest["files"]:
        path = root / record["relative_path"]
        if not path.is_file() or path.stat().st_size != int(record["bytes"]):
            raise RuntimeError(f"D8 manifest file/size differs: {path}")
        if sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"D8 manifest hash differs: {path}")
        verified += 1
    return verified


def audit(args: argparse.Namespace) -> dict[str, object]:
    root = args.root.resolve()
    document = json.loads((root / "D8_EXACT_ID_FEASIBILITY.json").read_text(encoding="utf-8-sig"))
    decisions = document["decisions"]
    if len(decisions) != 44 or len({row["utt_id"] for row in decisions}) != 44:
        raise RuntimeError("D8 exact-ID count/uniqueness differs")
    branches = Counter(row["branch"] for row in decisions)
    if branches != {"alignment_missing_19": 19, "sub_0_1_no_run_25": 25}:
        raise RuntimeError(f"D8 branch counts differ: {dict(branches)}")
    for row in decisions:
        if row["same_input_blind_rerun_allowed"] or row["main_body_mutation_allowed"] or row["automatic_merge_allowed"]:
            raise RuntimeError(f"unsafe D8 flag: {row['utt_id']}")
        if row["d9_candidate"] != row["requires_new_d9_exact_id_contract"]:
            raise RuntimeError(f"D9 contract flag differs: {row['utt_id']}")
        for evidence_name in ("canonical_wav", "r3_corpus_wav"):
            evidence = row[evidence_name]
            path = Path(evidence["path"])
            if not path.is_file() or sha256_file(path) != evidence["sha256"]:
                raise RuntimeError(f"D8 audio evidence differs: {row['utt_id']} {evidence_name}")
            if wav_payload_sha256(path) != evidence["payload_sha256"]:
                raise RuntimeError(f"D8 audio payload differs: {row['utt_id']} {evidence_name}")
        h_evidence = row["h_backup_wav"]
        h_path = Path(h_evidence["path"])
        if not h_evidence["exists"] or not h_path.is_file() or sha256_file(h_path) != h_evidence["sha256"]:
            raise RuntimeError(f"D8 H backup audio differs: {row['utt_id']}")
        if wav_payload_sha256(h_path) != h_evidence["payload_sha256"]:
            raise RuntimeError(f"D8 H backup payload differs: {row['utt_id']}")
        for path_field, hash_field in (("json_path", "json_sha256"), ("frozen_csv_path", "frozen_csv_sha256")):
            source_path = Path(row[path_field])
            if not source_path.is_file() or sha256_file(source_path) != row[hash_field]:
                raise RuntimeError(f"D8 metadata evidence differs: {row['utt_id']} {path_field}")
        lab = Path(row["lab_path"])
        if not lab.is_file() or sha256_file(lab) != row["lab_sha256"]:
            raise RuntimeError(f"D8 LAB differs: {row['utt_id']}")
        if row["branch"] == "sub_0_1_no_run_25" and row["d9_candidate"]:
            evidence = row["h_backup_wav"]
            if not evidence["exists"] or float(evidence["duration_seconds"]) < 0.3:
                raise RuntimeError(f"unsafe short-audio D9 candidate: {row['utt_id']}")
        if row["branch"] == "sub_0_1_no_run_25":
            pcm_ledger = row["raw_distribution_pcm"]
            ledger_path = Path(pcm_ledger["historical_source_pcm_check_path"])
            if not ledger_path.is_file() or sha256_file(ledger_path) != pcm_ledger["historical_source_pcm_check_sha256"]:
                raise RuntimeError(f"D8 PCM ledger differs: {row['utt_id']}")
            if float(row["r3_corpus_wav"]["duration_seconds"]) >= 0.1 or float(h_evidence["duration_seconds"]) >= 0.1:
                raise RuntimeError(f"D8 no-run audio is not sub-0.1 second: {row['utt_id']}")
            if row["recovery_disposition"] != "final_technical_exclusion_source_fragment_too_short":
                raise RuntimeError(f"D8 no-run disposition differs: {row['utt_id']}")
        elif not row["identity_verified"] or row["recovery_disposition"] != "d9_controlled_parameter_retry_candidate":
            raise RuntimeError(f"D8 alignment-missing routing differs: {row['utt_id']}")

    database = root / "D8_RECOVERY_FEASIBILITY.sqlite"
    connection = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    try:
        db_rows = connection.execute(
            "SELECT utt_id,branch,recovery_disposition,d9_candidate,identity_verified,source_overlap FROM recovery_feasibility"
        ).fetchall()
        metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    finally:
        connection.close()
    if len(db_rows) != 44:
        raise RuntimeError("D8 SQLite row count differs")
    by_id = {row["utt_id"]: row for row in decisions}
    for db_row in db_rows:
        source = by_id[db_row[0]]
        expected = (
            source["utt_id"], source["branch"], source["recovery_disposition"],
            int(source["d9_candidate"]), int(source["identity_verified"]), int(source["source_overlap"]),
        )
        if db_row != expected:
            raise RuntimeError(f"D8 JSON/SQLite differs: {source['utt_id']}")
    if metadata.get("mfa_run") != "false" or metadata.get("r3_body_mutation_allowed") != "false":
        raise RuntimeError("D8 SQLite safety metadata differs")

    gate = json.loads((root / "D8_GATE.json").read_text(encoding="utf-8-sig"))
    if gate["status"] != "closed_pending_d9_exact_id_approval" or any(bool(value) for value in gate["safety"].values()):
        raise RuntimeError("D8 gate safety differs")
    manifest_files = verify_manifest(root)
    dispositions = Counter(row["recovery_disposition"] for row in decisions)
    report = {
        "schema_version": "research_db_v1_recovery_d8_independent_audit.v1",
        "status": "passed_read_only_feasibility_gate_closed", "recorded_at": now_iso(),
        "counts": {
            "total": 44, "alignment_missing": 19, "sub_0_1_no_run": 25,
            "d9_candidates": sum(bool(row["d9_candidate"]) for row in decisions),
            "by_disposition": dict(sorted(dispositions.items())),
        },
        "sqlite_rows_verified": 44, "manifest_files_verified": manifest_files,
        "safety": gate["safety"], "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_ROOT / "INDEPENDENT_AUDIT.json")
    args = parser.parse_args()
    audit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
