#!/usr/bin/env python3
"""Build the read-only D8 recovery feasibility audit for 19+25 exact IDs.

This stage does not run MFA, create recovery audio, or mutate the frozen r3
body.  It reconciles D6 ledgers with raw JSON, frozen pre-MFA CSV, LAB, the
canonical WAV, the r3 corpus WAV, the historical H: WAV copy, and (for the
25 sub-0.1-second items) the original-distribution PCM on H:.
"""

from __future__ import annotations

import argparse
import array
import csv
import gzip
import json
import math
import os
import shutil
import sqlite3
import sys
import unicodedata
import uuid
import wave
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
D6_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d6_gate_20260815"
D0_D4_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
PRE_MFA_ROOT = Path(r"D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725")
H_WAV_ROOT = Path(r"H:\20_AUDIO\03_wav\individual")
H_PCM_ROOT = Path(r"H:\00_RAW\dialogue_audio\modu_corpus_dialogue_audio")
D8_ID = "nikl_dialogue_research_db_v1_recovery_d8_feasibility_audit_20260817"

JSON_ROOTS = {
    "2020": Path(r"D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2020_v1.4\NIKL_DIALOGUE_2020_v1.4"),
    "2021": Path(r"D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2021_v1.1\NIKL_DIALOGUE_2021_v1.1"),
    "2022": Path(r"D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2022_v1.0_JSON\NIKL_DIALOGUE_2022_v1.0"),
    "2023": Path(r"D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2023_v1.1\NIKL_DIALOGUE_2023_v1.1"),
    "2024": Path(r"D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2024_v1.0\NIKL_DIALOGUE_2024_v1.0"),
    "2025": Path(r"D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2025_v1.0"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_d2(target_ids: set[str]) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for year in range(2020, 2026):
        path = D0_D4_ROOT / f"D2_technical_audit/{year}_technical_recoverability.csv.gz"
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                utt_id = row.get("utt_id", "")
                if utt_id in target_ids:
                    if utt_id in found:
                        raise RuntimeError(f"duplicate D2 exact ID: {utt_id}")
                    found[utt_id] = row
    if set(found) != target_ids:
        raise RuntimeError(f"D2 exact-ID coverage differs: {sorted(target_ids-set(found))[:5]}")
    return found


def clean_text(value: object) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value or "")).split())


def comparison_text(value: object) -> str:
    text = clean_text(value)
    return "".join(ch for ch in text if ch.isalnum() or ("가" <= ch <= "힣"))


def load_json_session(year: str, session_id: str) -> tuple[Path, list[dict[str, object]]]:
    path = JSON_ROOTS[year] / f"{session_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows: list[dict[str, object]] = []
    for document in payload.get("document", []):
        for raw in document.get("utterance", []):
            rows.append(
                {
                    "utt_id": clean_text(raw.get("id")),
                    "speaker_id": clean_text(raw.get("speaker_id")),
                    "start": float(raw.get("start")),
                    "end": float(raw.get("end")),
                    "form": clean_text(raw.get("form")),
                    "original_form": clean_text(raw.get("original_form")),
                    "note": clean_text(raw.get("note")),
                }
            )
    if not rows or len({row["utt_id"] for row in rows}) != len(rows):
        raise RuntimeError(f"invalid JSON utterance inventory: {path}")
    return path, rows


def load_csv_target(year: str, source_csv: str, utt_id: str) -> tuple[Path, dict[str, str]]:
    path = PRE_MFA_ROOT / source_csv.replace("/", os.sep)
    rows = [row for row in read_csv(path) if row.get("utt_id") == utt_id]
    if len(rows) != 1:
        raise RuntimeError(f"frozen CSV exact-ID count differs: {utt_id}: {len(rows)}")
    if rows[0].get("year") != year:
        raise RuntimeError(f"frozen CSV year differs: {utt_id}")
    return path, rows[0]


def wav_metrics(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        sample_width = stream.getsampwidth()
        sample_rate = stream.getframerate()
        frames = stream.getnframes()
        raw = stream.readframes(frames)
    if sample_width != 2:
        raise RuntimeError(f"unsupported WAV sample width: {path}: {sample_width}")
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    mono: list[int]
    if channels == 1:
        mono = list(samples)
    else:
        mono = [max(abs(samples[index + channel]) for channel in range(channels)) for index in range(0, len(samples), channels)]
    absolute = [abs(value) for value in mono]
    peak = max(absolute, default=0)
    rms = math.sqrt(sum(value * value for value in mono) / len(mono)) if mono else 0.0
    threshold = max(200, int(peak * 0.02))
    active = [index for index, value in enumerate(absolute) if value >= threshold]
    if active:
        span = (active[-1] - active[0] + 1) / sample_rate
        leading = active[0] / sample_rate
        trailing = (len(mono) - active[-1] - 1) / sample_rate
    else:
        span = leading = trailing = 0.0
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "payload_sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "frame_count": frames,
        "duration_seconds": round(frames / sample_rate, 9),
        "peak_abs": peak,
        "rms": round(rms, 3),
        "active_span_seconds": round(span, 9),
        "leading_below_threshold_seconds": round(leading, 9),
        "trailing_below_threshold_seconds": round(trailing, 9),
    }


def file_evidence(path: Path, *, audio: bool = False) -> dict[str, object]:
    evidence: dict[str, object] = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        evidence.update(wav_metrics(path) if audio else {"bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return evidence


def raw_pcm_ledger_evidence(source: dict[str, str]) -> dict[str, object]:
    """Preserve the earlier exact-ID direct-stat result without rescanning H:.

    The flat 2021 PCM directory contains a very large number of entries and a
    current directory enumeration is pathologically slow.  D8 therefore uses
    the frozen direct-stat value from source_pcm_check and independently checks
    the structured H: WAV copy of the same distribution payload.
    """
    seconds = source.get("source_pcm_seconds", "").strip()
    expected = H_PCM_ROOT / f"{source['year']}_pcm" / f"{source['utt_id']}.pcm"
    return {
        "expected_path": str(expected),
        "current_binary_enumeration_performed": False,
        "historical_direct_stat_category": source.get("source_pcm_category", ""),
        "historical_direct_stat_seconds": float(seconds) if seconds else None,
        "historical_source_pcm_check_path": source.get("source_pcm_check_path", ""),
        "historical_source_pcm_check_sha256": sha256_file(Path(source["source_pcm_check_path"])),
        "independent_current_evidence": "H_backup_wav_payload_and_duration",
    }


def overlap_evidence(target: dict[str, object], rows: list[dict[str, object]]) -> dict[str, object]:
    overlaps: list[dict[str, object]] = []
    for other in rows:
        if other["utt_id"] == target["utt_id"]:
            continue
        amount = min(float(target["end"]), float(other["end"])) - max(float(target["start"]), float(other["start"]))
        if amount > 0.001:
            overlaps.append({"utt_id": other["utt_id"], "speaker_id": other["speaker_id"], "overlap_seconds": round(amount, 6)})
    same_form = [
        row["utt_id"]
        for row in rows
        if row["utt_id"] != target["utt_id"]
        and row["speaker_id"] == target["speaker_id"]
        and comparison_text(row["form"]) == comparison_text(target["form"])
    ]
    return {
        "json_note": target["note"],
        "source_note_overlap": "발화겹침" in str(target["note"]),
        "time_overlap": bool(overlaps),
        "overlap_members": overlaps,
        "same_speaker_same_form_other_ids": same_form,
    }


def classify_alignment_missing(*, identity_verified: bool, audio: dict[str, object]) -> tuple[str, bool]:
    if not identity_verified:
        return "hold_identity_conflict_not_d9", False
    if float(audio["duration_seconds"]) < 0.3 or float(audio["active_span_seconds"]) < 0.08:
        return "hold_audio_content_insufficient_not_d9", False
    return "d9_controlled_parameter_retry_candidate", True


def classify_no_run(*, source_seconds: float, observed_seconds: float, independent_seconds: float | None) -> tuple[str, bool]:
    del source_seconds  # timing metadata is recorded but cannot manufacture missing audio
    longest_audio = max(observed_seconds, independent_seconds or 0.0)
    if longest_audio < 0.1:
        return "final_technical_exclusion_source_fragment_too_short", False
    if longest_audio < 0.3:
        return "hold_sub_0_3_audio_not_d9", False
    return "d9_reconstructed_audio_candidate", True


def build_sqlite(path: Path, decisions: list[dict[str, object]], metadata: dict[str, str]) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute(
            """
            CREATE TABLE recovery_feasibility (
                year INTEGER NOT NULL,
                utt_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                branch TEXT NOT NULL,
                recovery_disposition TEXT NOT NULL,
                d9_candidate INTEGER NOT NULL CHECK(d9_candidate IN (0,1)),
                identity_verified INTEGER NOT NULL CHECK(identity_verified IN (0,1)),
                source_overlap INTEGER NOT NULL CHECK(source_overlap IN (0,1)),
                source_duration_seconds REAL NOT NULL,
                observed_wav_duration_seconds REAL NOT NULL,
                evidence_json TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO recovery_feasibility VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    int(row["year"]), row["utt_id"], row["session_id"], row["branch"],
                    row["recovery_disposition"], int(bool(row["d9_candidate"])),
                    int(bool(row["identity_verified"])), int(bool(row["source_overlap"])),
                    float(row["source_duration_seconds"]), float(row["observed_wav_duration_seconds"]),
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                )
                for row in decisions
            ],
        )
        connection.execute("CREATE INDEX idx_d8_branch ON recovery_feasibility(branch)")
        connection.execute("CREATE INDEX idx_d8_disposition ON recovery_feasibility(recovery_disposition)")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany("INSERT INTO metadata VALUES (?,?)", sorted(metadata.items()))
        connection.commit()
    finally:
        connection.close()


def relative_record(path: Path, root: Path) -> dict[str, object]:
    return {"relative_path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def build(args: argparse.Namespace) -> dict[str, object]:
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"D8 output exists: {output_root}")
    partial = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    partial.mkdir(parents=True)
    try:
        missing_rows = read_csv(D6_ROOT / "D6_MISSING_19_TECHNICAL_LEDGER.csv")
        no_run_rows = read_csv(D6_ROOT / "D6_NO_RUN_25_AUDIO_RECOVERY.csv")
        if len(missing_rows) != 19 or len(no_run_rows) != 25:
            raise RuntimeError("D6 19+25 partition count differs")
        target_ids = {row["utt_id"] for row in missing_rows + no_run_rows}
        if len(target_ids) != 44:
            raise RuntimeError("D6 19+25 exact-ID uniqueness differs")
        d2 = read_d2(target_ids)
        json_cache: dict[tuple[str, str], tuple[Path, list[dict[str, object]]]] = {}
        decisions: list[dict[str, object]] = []
        for branch, rows in (("alignment_missing_19", missing_rows), ("sub_0_1_no_run_25", no_run_rows)):
            for source in rows:
                year, utt_id, session_id = source["year"], source["utt_id"], source["session_id"]
                key = (year, session_id)
                if key not in json_cache:
                    json_cache[key] = load_json_session(year, session_id)
                json_path, json_rows = json_cache[key]
                json_matches = [row for row in json_rows if row["utt_id"] == utt_id]
                if len(json_matches) != 1:
                    raise RuntimeError(f"JSON exact-ID count differs: {utt_id}: {len(json_matches)}")
                json_row = json_matches[0]
                csv_path, csv_row = load_csv_target(year, source["source_csv"], utt_id)
                lab_path = Path(source.get("source_lab_path") or source.get("r3_corpus_lab_path") or d2[utt_id]["r3_corpus_lab_path"])
                lab_text = clean_text(lab_path.read_text(encoding="utf-8-sig"))
                canonical_path = Path(d2[utt_id]["canonical_wav_path"])
                r3_path = Path(source.get("source_wav_path") or source.get("r3_corpus_wav_path") or d2[utt_id]["r3_corpus_wav_path"])
                h_path = H_WAV_ROOT / year / session_id / f"{utt_id}.wav"
                canonical = file_evidence(canonical_path, audio=True)
                r3 = file_evidence(r3_path, audio=True)
                h_backup = file_evidence(h_path, audio=True)
                if not canonical["exists"] or not r3["exists"]:
                    raise RuntimeError(f"canonical/r3 WAV missing: {utt_id}")
                if sha256_file(r3_path) != source["source_wav_sha256"]:
                    raise RuntimeError(f"D6 r3 WAV hash differs: {utt_id}")
                if sha256_file(lab_path) != source["source_lab_sha256"]:
                    raise RuntimeError(f"D6 LAB hash differs: {utt_id}")
                start = float(csv_row["start"])
                end = float(csv_row["end"])
                expected_lab_text = clean_text(source.get("normalized_text") or lab_text)
                identity_checks = {
                    "json_csv_form_equal": clean_text(json_row["form"]) == clean_text(csv_row["form"]),
                    "json_csv_original_form_equal": clean_text(json_row["original_form"]) == clean_text(csv_row["original_form"]),
                    "json_csv_start_equal": abs(float(json_row["start"]) - start) <= 1e-6,
                    "json_csv_end_equal": abs(float(json_row["end"]) - end) <= 1e-6,
                    "lab_form_normalized_equal": comparison_text(lab_text) == comparison_text(csv_row["form"]),
                    "lab_d6_normalized_equal": comparison_text(lab_text) == comparison_text(expected_lab_text),
                    "canonical_r3_payload_equal": canonical["payload_sha256"] == r3["payload_sha256"],
                    "h_backup_r3_payload_equal": bool(h_backup["exists"]) and h_backup["payload_sha256"] == r3["payload_sha256"],
                }
                required = [
                    "json_csv_form_equal", "json_csv_original_form_equal", "json_csv_start_equal",
                    "json_csv_end_equal", "lab_d6_normalized_equal", "canonical_r3_payload_equal",
                ]
                identity_verified = all(bool(identity_checks[name]) for name in required)
                overlap = overlap_evidence(json_row, json_rows)
                source_overlap = bool(overlap["source_note_overlap"] or overlap["time_overlap"])
                source_duration = end - start
                raw_pcm = raw_pcm_ledger_evidence(source) if branch == "sub_0_1_no_run_25" else {}
                if branch == "alignment_missing_19":
                    disposition, d9_candidate = classify_alignment_missing(identity_verified=identity_verified, audio=r3)
                else:
                    independent_seconds = None
                    if h_backup["exists"]:
                        independent_seconds = float(h_backup["duration_seconds"])
                    elif raw_pcm.get("historical_direct_stat_seconds") is not None:
                        independent_seconds = float(raw_pcm["historical_direct_stat_seconds"])
                    disposition, d9_candidate = classify_no_run(
                        source_seconds=source_duration,
                        observed_seconds=float(r3["duration_seconds"]),
                        independent_seconds=independent_seconds,
                    )
                decisions.append(
                    {
                        "year": int(year), "utt_id": utt_id, "session_id": session_id,
                        "branch": branch, "form": csv_row["form"], "original_form": csv_row["original_form"],
                        "tagged": csv_row["tagged"], "speaker_id": json_row["speaker_id"],
                        "source_start_seconds": start, "source_end_seconds": end,
                        "source_duration_seconds": round(source_duration, 9),
                        "observed_wav_duration_seconds": r3["duration_seconds"],
                        "lab_text": lab_text, "identity_checks": identity_checks,
                        "identity_verified": identity_verified, "source_overlap": source_overlap,
                        "overlap_evidence": overlap, "json_path": str(json_path),
                        "json_sha256": sha256_file(json_path), "frozen_csv_path": str(csv_path),
                        "frozen_csv_sha256": sha256_file(csv_path), "lab_path": str(lab_path),
                        "lab_sha256": sha256_file(lab_path), "canonical_wav": canonical,
                        "r3_corpus_wav": r3, "h_backup_wav": h_backup,
                        "raw_distribution_pcm": raw_pcm,
                        "prior_source_pcm_category": source.get("source_pcm_category", ""),
                        "prior_source_pcm_seconds": source.get("source_pcm_seconds", ""),
                        "recovery_disposition": disposition, "d9_candidate": d9_candidate,
                        "same_input_blind_rerun_allowed": False,
                        "requires_new_d9_exact_id_contract": bool(d9_candidate),
                        "main_body_mutation_allowed": False, "automatic_merge_allowed": False,
                        "research_scope_after_possible_recovery": (
                            "alignment_infrastructure_only_exclude_single_speaker_acoustic_analysis"
                            if source_overlap else "pending_post_alignment_researcher_review"
                        ),
                    }
                )

        decisions.sort(key=lambda row: (int(row["year"]), row["branch"], row["utt_id"]))
        counts = Counter(row["recovery_disposition"] for row in decisions)
        document = {
            "schema_version": "research_db_v1_recovery_d8_feasibility.v1",
            "status": "read_only_feasibility_audit_complete_gate_closed",
            "recorded_at": now_iso(),
            "counts": {
                "total": 44,
                "alignment_missing": 19,
                "sub_0_1_no_run": 25,
                "d9_candidates": sum(bool(row["d9_candidate"]) for row in decisions),
                "not_d9_candidates": sum(not bool(row["d9_candidate"]) for row in decisions),
                "by_disposition": dict(sorted(counts.items())),
            },
            "method": {
                "mfa_run": False, "audio_materialized": False, "source_mutated": False,
                "full_year_rerun": False, "same_input_blind_rerun": False,
                "evidence": ["raw_json", "frozen_pre_mfa_csv", "lab", "canonical_wav", "r3_corpus_wav", "H_backup_wav", "H_distribution_pcm_for_no_run"],
            },
            "decisions": decisions,
        }
        decision_path = partial / "D8_EXACT_ID_FEASIBILITY.json"
        decision_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        metadata = {
            "schema_version": "research_db_v1_recovery_d8_sqlite.v1",
            "status": document["status"], "recorded_at": document["recorded_at"],
            "decision_sha256": sha256_file(decision_path), "mfa_run": "false",
            "r3_body_mutation_allowed": "false", "automatic_merge_allowed": "false",
        }
        build_sqlite(partial / "D8_RECOVERY_FEASIBILITY.sqlite", decisions, metadata)
        gate = {
            "schema_version": "research_db_v1_recovery_d8_gate.v1",
            "status": "closed_pending_d9_exact_id_approval",
            "recorded_at": now_iso(), "counts": document["counts"],
            "safety": {
                "mfa_run": False, "recovery_audio_created": False, "r3_body_mutated": False,
                "research_6tier_mutated": False, "db_v1_mutated": False,
                "automatic_merge_performed": False, "source_files_deleted": False,
            },
            "next_gate": "approve at most one D9 controlled exact-ID run for d9_candidate=true rows",
        }
        (partial / "D8_GATE.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (partial / "README.md").write_text(
            "# DB v1 recovery D8 read-only feasibility audit\n\n"
            "D6의 미정렬 19건과 0.1초 미만 no-run 25건을 원 JSON, 동결 CSV, LAB, "
            "canonical/r3/H: WAV 및 H: 배포 PCM 증거로 다시 대조했다. 이 단계에서는 "
            "MFA, 새 음원 생성, 본체·6-tier·DB v1 병합, 삭제를 수행하지 않았다. "
            "`d9_candidate=true`인 exact ID만 별도 승인 뒤 한 차례 통제 실행할 수 있다.\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": "research_db_v1_recovery_d8_manifest.v1", "recorded_at": now_iso(),
            "inputs": {
                "d6_missing_19_sha256": sha256_file(D6_ROOT / "D6_MISSING_19_TECHNICAL_LEDGER.csv"),
                "d6_no_run_25_sha256": sha256_file(D6_ROOT / "D6_NO_RUN_25_AUDIO_RECOVERY.csv"),
                "d6_manifest_sha256": sha256_file(D6_ROOT / "OUTPUT_MANIFEST.json"),
            },
            "implementation": {"builder_sha256": sha256_file(Path(__file__).resolve())},
            "files": [relative_record(path, partial) for path in sorted(partial.iterdir()) if path.is_file()],
        }
        (partial / "OUTPUT_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(partial, output_root)
    except Exception:
        shutil.rmtree(partial, ignore_errors=True)
        raise

    report = {
        "schema_version": "research_db_v1_recovery_d8_result.v1",
        "status": "read_only_feasibility_audit_complete_gate_closed", "recorded_at": now_iso(),
        "output_root": str(output_root), "counts": document["counts"], "safety": gate["safety"],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs/releases" / D8_ID)
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "outputs/reports/RESULT_db_v1_recovery_D8_20260817.json")
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
