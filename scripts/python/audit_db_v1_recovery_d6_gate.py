#!/usr/bin/env python3
"""Independently audit the D6 review gate and its fail-closed boundaries."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import wave
from pathlib import Path

from praatio import textgrid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d5_common import D5_OUTPUT_ROOT, PROJECT_ROOT, read_gzip_csv
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


D6_RELEASE = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d6_gate_20260815"
D6_REVIEW = PROJECT_ROOT / "outputs/reviews/db_v1_recovery_d6_20260815"
D5_PACKAGE = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d5_gate_20260815"
D5_RESULTS = PROJECT_ROOT / "outputs/reports/D5_ALIGNMENT_DIAGNOSTIC_0001_RESULTS.csv"
D5_DB = D5_OUTPUT_ROOT / "temp/corpus/corpus.db"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_manifest(manifest_path: Path, root: Path) -> int:
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    count = 0
    for record in data["files"]:
        path = root / record["relative_path"]
        if not path.is_file():
            raise RuntimeError(f"manifest file missing: {path}")
        if path.stat().st_size != int(record["bytes"]):
            raise RuntimeError(f"manifest byte mismatch: {path}")
        if sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"manifest sha mismatch: {path}")
        count += 1
    return count


def db_interval_counts(ids: set[str]) -> dict[str, tuple[bool, int, int, int | None]]:
    connection = sqlite3.connect(f"file:{D5_DB.resolve().as_posix()}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" for _ in ids)
        rows = connection.execute(
            f"""
            SELECT f.name, u.ignored, u.num_frames,
                   (SELECT COUNT(*) FROM word_interval wi WHERE wi.utterance_id=u.id),
                   (SELECT COUNT(*) FROM phone_interval pi WHERE pi.utterance_id=u.id)
            FROM utterance u JOIN file f ON f.id=u.file_id
            WHERE f.name IN ({placeholders})
            """, tuple(sorted(ids)),
        ).fetchall()
    finally:
        connection.close()
    return {str(r[0]): (bool(r[1]), int(r[3]), int(r[4]), int(r[2]) if r[2] is not None else None) for r in rows}


def audit(args: argparse.Namespace) -> dict[str, object]:
    release = args.release.resolve()
    review = args.review.resolve()
    result_rows = read_csv(D5_RESULTS)
    _, run_rows = read_gzip_csv(D5_PACKAGE / "D5_RUN_SHARD.csv.gz")
    no_run_source = read_csv(D5_PACKAGE / "D5_NO_RUN_AUDIO_DURATION_RECOVERY.csv")
    success = read_csv(release / "D6_SUCCESS_11_REVIEW.csv")
    missing = read_csv(release / "D6_MISSING_19_TECHNICAL_LEDGER.csv")
    no_run = read_csv(release / "D6_NO_RUN_25_AUDIO_RECOVERY.csv")

    expected_success = {r["utt_id"] for r in result_rows if r["diagnostic_outcome"] == "textgrid_present_unadopted"}
    expected_missing = {r["utt_id"] for r in result_rows if r["diagnostic_outcome"] == "alignment_missing_after_d5"}
    expected_no_run = {r["utt_id"] for r in no_run_source}
    observed_success = {r["utt_id"] for r in success}
    observed_missing = {r["utt_id"] for r in missing}
    observed_no_run = {r["utt_id"] for r in no_run}
    if len(success) != 11 or observed_success != expected_success:
        raise RuntimeError("D6 success exact-ID mismatch")
    if len(missing) != 19 or observed_missing != expected_missing:
        raise RuntimeError("D6 missing exact-ID mismatch")
    if len(no_run) != 25 or observed_no_run != expected_no_run:
        raise RuntimeError("D6 no-run exact-ID mismatch")
    if observed_success & observed_missing or observed_no_run & (observed_success | observed_missing):
        raise RuntimeError("D6 partitions overlap")
    if {r["utt_id"] for r in run_rows} != observed_success | observed_missing:
        raise RuntimeError("D5 run partition mismatch")

    review_rows = read_csv(review / "00_REVIEW_11.csv")
    if review_rows != success:
        raise RuntimeError("release/review success table differs")
    for row in review_rows:
        wav_path = review / row["review_wav"]
        lab_path = review / row["review_lab"]
        tg_path = review / row["review_textgrid"]
        for path in (wav_path, lab_path, tg_path):
            if not path.is_file():
                raise RuntimeError(f"review file missing: {path}")
        if sha256_file(wav_path) != row["wav_sha256"] or sha256_file(lab_path) != row["lab_sha256"]:
            raise RuntimeError(f"review WAV/LAB hash mismatch: {row['utt_id']}")
        if sha256_file(tg_path) != row["textgrid_sha256"]:
            raise RuntimeError(f"review TextGrid hash mismatch: {row['utt_id']}")
        with wave.open(str(wav_path), "rb") as stream:
            duration = stream.getnframes() / stream.getframerate()
        grid = textgrid.openTextgrid(str(tg_path), includeEmptyIntervals=True)
        if list(grid.tierNames) != ["words", "phones"]:
            raise RuntimeError(f"review TextGrid tiers differ: {row['utt_id']}")
        if abs(float(grid.maxTimestamp) - duration) > 1e-6:
            raise RuntimeError(f"review TextGrid/WAV duration differs: {row['utt_id']}")
        if not row["lab_text"].strip() or row["decision"] != "pending":
            raise RuntimeError(f"review table initial state invalid: {row['utt_id']}")
        if row["dictionary_oov_count"] != "0":
            raise RuntimeError(f"unexpected D5 dictionary OOV in success row: {row['utt_id']}")

    db_rows = db_interval_counts(observed_missing)
    if set(db_rows) != observed_missing:
        raise RuntimeError("D6 missing IDs absent from preserved DB")
    for row in missing:
        ignored, words, phones, frames = db_rows[row["utt_id"]]
        if ignored or frames is None or frames <= 0 or words != 0 or phones != 0:
            raise RuntimeError(f"unexpected D6 missing technical evidence: {row['utt_id']}")
        if row["technical_reason_code"] != "alignment_not_emitted_after_fresh_subset":
            raise RuntimeError(f"technical classification mismatch: {row['utt_id']}")
        if row["dictionary_oov_count"] != "0":
            raise RuntimeError(f"unexpected D5 dictionary OOV in missing row: {row['utt_id']}")
        if row["same_input_blind_rerun_allowed"] != "false" or row["automatic_merge_allowed"] != "false":
            raise RuntimeError(f"missing gate safety differs: {row['utt_id']}")

    source_no_run = {r["utt_id"]: r for r in no_run_source}
    pcm_present = 0
    pcm_missing = 0
    for row in no_run:
        source = source_no_run[row["utt_id"]]
        if float(source["wav_duration_seconds"]) >= 0.1:
            raise RuntimeError(f"no-run exact duration is not <0.1: {row['utt_id']}")
        if row["same_input_mfa_allowed"] != "false" or row["original_pcm_binary_available"] != "false":
            raise RuntimeError(f"no-run safety differs: {row['utt_id']}")
        if row["source_pcm_seconds"].strip():
            pcm_present += 1
            if row["audio_recovery_class"] != "source_pcm_short_confirmed":
                raise RuntimeError(f"short PCM class differs: {row['utt_id']}")
        else:
            pcm_missing += 1
            if row["audio_recovery_class"] != "source_pcm_missing_confirmed":
                raise RuntimeError(f"missing PCM class differs: {row['utt_id']}")
        if any((D5_OUTPUT_ROOT / "corpus").rglob(f"{row['utt_id']}.*")):
            raise RuntimeError(f"no-run ID unexpectedly materialized in D5 corpus: {row['utt_id']}")
        if any((D5_OUTPUT_ROOT / "mfa_output").rglob(f"{row['utt_id']}.TextGrid")):
            raise RuntimeError(f"no-run ID unexpectedly aligned in D5: {row['utt_id']}")
    if (pcm_present, pcm_missing) != (24, 1):
        raise RuntimeError(f"PCM recovery partition differs: {(pcm_present, pcm_missing)}")

    gate = json.loads((release / "D6_GATE_PENDING.json").read_text(encoding="utf-8-sig"))
    if gate["status"] != "hold_pending_researcher_review_and_separate_approval":
        raise RuntimeError("D6 gate is not closed")
    if any(bool(value) for value in gate["safety"].values()):
        raise RuntimeError("D6 safety flags indicate unauthorized mutation")

    release_manifest_files = verify_manifest(release / "OUTPUT_MANIFEST.json", release)
    review_manifest_files = verify_manifest(review / "REVIEW_MANIFEST.json", review)
    report = {
        "schema_version": "research_db_v1_recovery_d6_independent_audit.v1",
        "status": "passed_gate_closed_pending_researcher_review_and_separate_approval",
        "recorded_at": now_iso(),
        "counts": {"success_review": 11, "technical_missing": 19, "no_same_input_rerun": 25},
        "technical_evidence": {"aligned_features_without_word_or_phone_intervals": 19},
        "audio_recovery_evidence": {"source_pcm_short": 24, "source_pcm_missing": 1},
        "manifest_files_verified": {"release": release_manifest_files, "review": review_manifest_files},
        "safety": {
            "r3_body_mutated": False, "research_6tier_mutated": False,
            "db_v1_mutated": False, "automatic_merge_performed": False,
            "same_input_mfa_for_sub_0_1_second_items": False,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, default=D6_RELEASE)
    parser.add_argument("--review", type=Path, default=D6_REVIEW)
    parser.add_argument("--report", type=Path, default=D6_RELEASE / "INDEPENDENT_AUDIT.json")
    args = parser.parse_args()
    audit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
