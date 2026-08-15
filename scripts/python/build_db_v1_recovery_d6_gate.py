#!/usr/bin/env python3
"""Build the D6 post-diagnostic review gate without adopting any result.

The builder treats the frozen r3 body and the D5 diagnostic namespace as
read-only inputs.  It creates (1) a flat 11-item WAV/LAB/TextGrid review
bundle, (2) an exact-ID technical ledger for the 19 non-exported items, and
(3) a no-rerun/original-audio-recovery ledger for the 25 sub-0.1-second
feature failures.  No result is merged into r3, the research 6-tier export,
or DB v1.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import shutil
import sqlite3
import sys
import uuid
import wave
from collections import Counter
from pathlib import Path

from praatio import textgrid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d5_common import D5_OUTPUT_ROOT, PROJECT_ROOT, read_gzip_csv
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


D6_ID = "nikl_dialogue_research_db_v1_recovery_d6_gate_20260815"
D6_REVIEW_ID = "db_v1_recovery_d6_20260815"
D5_PACKAGE = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d5_gate_20260815"
D0_D4_PACKAGE = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
D5_RESULTS = PROJECT_ROOT / "outputs/reports/D5_ALIGNMENT_DIAGNOSTIC_0001_RESULTS.csv"
D5_DB = D5_OUTPUT_ROOT / "temp/corpus/corpus.db"
PCM_CHECK = Path(r"D:\10_LAYERS\05_audio_index\source_pcm_check.csv")


SUCCESS_FIELDS = [
    "review_order", "year", "utt_id", "session_id", "form", "original_form",
    "tagged", "source_csv", "source_start_seconds", "source_end_seconds",
    "source_duration_seconds", "lab_text", "lab_token_count",
    "dictionary_oov_count",
    "wav_duration_seconds", "textgrid_xmax_seconds", "tier_names",
    "words_nonempty_intervals", "phones_nonempty_intervals", "review_wav",
    "review_lab", "review_textgrid", "source_wav_path", "source_lab_path",
    "source_textgrid_path", "wav_sha256", "lab_sha256", "textgrid_sha256",
    "decision", "audio_text_match", "words_alignment", "phones_alignment",
    "boundary_quality", "notes",
]

MISSING_FIELDS = [
    "run_order", "year", "utt_id", "session_id", "form", "original_form",
    "tagged", "source_csv", "source_start_seconds", "source_end_seconds",
    "source_duration_seconds", "wav_duration_seconds", "lab_text",
    "lab_token_count", "dictionary_oov_count", "normalized_text",
    "db_duration_seconds", "num_frames", "job_id", "ignored_by_mfa",
    "word_interval_count", "phone_interval_count", "alignment_log_likelihood",
    "technical_reason_code", "per_utterance_log_evidence", "next_action",
    "same_input_blind_rerun_allowed", "automatic_merge_allowed",
    "source_wav_path", "source_lab_path", "source_wav_sha256",
    "source_lab_sha256",
]

NO_RUN_FIELDS = [
    "run_order", "year", "utt_id", "session_id", "form", "original_form",
    "tagged", "source_csv", "source_start_seconds", "source_end_seconds",
    "source_duration_seconds", "observed_wav_duration_seconds",
    "source_pcm_check_path", "source_pcm_category", "source_pcm_seconds",
    "original_pcm_binary_available", "audio_recovery_class",
    "audio_recovery_path", "same_input_mfa_allowed", "next_action",
    "r3_corpus_wav_path", "r3_corpus_lab_path", "source_wav_sha256",
    "source_lab_sha256",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def relative_fingerprint(path: Path, root: Path) -> dict[str, object]:
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def load_d2(target_ids: set[str]) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for year in range(2020, 2026):
        path = D0_D4_PACKAGE / f"D2_technical_audit/{year}_technical_recoverability.csv.gz"
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                utt_id = str(row.get("utt_id") or "")
                if utt_id in target_ids:
                    if utt_id in found:
                        raise RuntimeError(f"duplicate D2 utt_id: {utt_id}")
                    found[utt_id] = row
    if set(found) != target_ids:
        raise RuntimeError(f"D2 exact-ID mismatch: missing={sorted(target_ids-set(found))[:5]}")
    return found


def load_db_rows(target_ids: set[str]) -> dict[str, dict[str, object]]:
    connection = sqlite3.connect(f"file:{D5_DB.resolve().as_posix()}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" for _ in target_ids)
        rows = connection.execute(
            f"""
            SELECT f.name, f.relative_path, u.begin, u.end, u.num_frames,
                   u.normalized_text, u.job_id, u.alignment_log_likelihood,
                   u.ignored,
                   (SELECT COUNT(*) FROM word_interval wi WHERE wi.utterance_id=u.id),
                   (SELECT COUNT(*) FROM phone_interval pi WHERE pi.utterance_id=u.id)
            FROM utterance u JOIN file f ON f.id=u.file_id
            WHERE f.name IN ({placeholders}) ORDER BY f.name
            """,
            tuple(sorted(target_ids)),
        ).fetchall()
    finally:
        connection.close()
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        result[str(row[0])] = {
            "relative_path": str(row[1] or ""),
            "db_duration_seconds": round(float(row[3]) - float(row[2]), 6),
            "num_frames": int(row[4]) if row[4] is not None else None,
            "normalized_text": str(row[5] or ""),
            "job_id": int(row[6]) if row[6] is not None else None,
            "alignment_log_likelihood": row[7],
            "ignored_by_mfa": bool(row[8]),
            "word_interval_count": int(row[9]),
            "phone_interval_count": int(row[10]),
        }
    if set(result) != target_ids:
        raise RuntimeError(f"D5 DB exact-ID mismatch: missing={sorted(target_ids-set(result))[:5]}")
    return result


def classify_missing(row: dict[str, object]) -> str:
    if bool(row["ignored_by_mfa"]):
        return "feature_generation_failed_in_d5"
    if row["num_frames"] is None or int(row["num_frames"]) <= 0:
        return "features_missing_after_d5"
    words = int(row["word_interval_count"])
    phones = int(row["phone_interval_count"])
    if words == 0 and phones == 0:
        return "alignment_not_emitted_after_fresh_subset"
    if words == 0:
        return "word_intervals_missing_after_fresh_subset"
    if phones == 0:
        return "phone_intervals_missing_after_fresh_subset"
    return "unexpected_export_absence_requires_manual_db_audit"


def inspect_textgrid(path: Path) -> dict[str, object]:
    grid = textgrid.openTextgrid(str(path), includeEmptyIntervals=True)
    names = list(grid.tierNames)
    if names != ["words", "phones"]:
        raise RuntimeError(f"unexpected D5 tiers: {path}: {names}")
    words = grid.getTier("words")
    phones = grid.getTier("phones")
    return {
        "textgrid_xmax_seconds": f"{float(grid.maxTimestamp):.9f}",
        "tier_names": " | ".join(names),
        "words_nonempty_intervals": sum(bool(x.label.strip()) for x in words.entries),
        "phones_nonempty_intervals": sum(bool(x.label.strip()) for x in phones.entries),
    }


def load_pcm_check(target_ids: set[str]) -> dict[str, dict[str, str]]:
    _, rows = read_csv(PCM_CHECK)
    found = {row["utt_id"]: row for row in rows if row.get("utt_id") in target_ids}
    if set(found) != target_ids:
        raise RuntimeError(f"source_pcm_check exact-ID mismatch: missing={sorted(target_ids-set(found))[:5]}")
    return found


def ensure_new_directory(path: Path) -> Path:
    if path.exists():
        raise FileExistsError(f"output already exists: {path}")
    partial = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    partial.mkdir(parents=True)
    return partial


def build(args: argparse.Namespace) -> dict[str, object]:
    release_root = args.release_root.resolve()
    review_root = args.review_root.resolve()
    release_partial = ensure_new_directory(release_root)
    review_partial = ensure_new_directory(review_root)

    _, result_rows = read_csv(D5_RESULTS)
    _, run_rows = read_gzip_csv(D5_PACKAGE / "D5_RUN_SHARD.csv.gz")
    _, no_run_rows = read_csv(D5_PACKAGE / "D5_NO_RUN_AUDIO_DURATION_RECOVERY.csv")
    _, input_audit_rows = read_csv(D5_PACKAGE / "D5_INPUT_AUDIT.csv")
    result_by_id = {row["utt_id"]: row for row in result_rows}
    run_by_id = {row["utt_id"]: row for row in run_rows}
    success_ids = {row["utt_id"] for row in result_rows if row["diagnostic_outcome"] == "textgrid_present_unadopted"}
    missing_ids = {row["utt_id"] for row in result_rows if row["diagnostic_outcome"] == "alignment_missing_after_d5"}
    no_run_ids = {row["utt_id"] for row in no_run_rows}
    input_audit_by_id = {row["utt_id"]: row for row in input_audit_rows}
    if len(success_ids) != 11 or len(missing_ids) != 19 or len(no_run_ids) != 25:
        raise RuntimeError("D5 partition count mismatch")
    if success_ids & missing_ids or set(run_by_id) != success_ids | missing_ids:
        raise RuntimeError("D5 run/result identity mismatch")
    if not (success_ids | missing_ids | no_run_ids) <= set(input_audit_by_id):
        raise RuntimeError("D5 input audit does not cover D6 exact IDs")

    all_ids = success_ids | missing_ids | no_run_ids
    d2 = load_d2(all_ids)
    db = load_db_rows(success_ids | missing_ids)
    pcm = load_pcm_check(no_run_ids)

    success_rows: list[dict[str, object]] = []
    for review_order, utt_id in enumerate(
        [row["utt_id"] for row in result_rows if row["utt_id"] in success_ids], 1
    ):
        run = run_by_id[utt_id]
        meta = d2[utt_id]
        source_wav = Path(run["source_wav_path"])
        source_lab = Path(run["source_lab_path"])
        source_tg = Path(result_by_id[utt_id]["diagnostic_textgrid_path"])
        if not (source_wav.is_file() and source_lab.is_file() and source_tg.is_file()):
            raise RuntimeError(f"success source missing: {utt_id}")
        base = f"{review_order:02d}_{run['year']}_{utt_id}"
        out_wav = review_partial / f"{base}.wav"
        out_lab = review_partial / f"{base}.lab"
        out_tg = review_partial / f"{base}.TextGrid"
        shutil.copy2(source_wav, out_wav)
        shutil.copy2(source_lab, out_lab)
        shutil.copy2(source_tg, out_tg)
        lab_text = source_lab.read_text(encoding="utf-8-sig").strip()
        tg_info = inspect_textgrid(source_tg)
        duration = wav_duration(source_wav)
        if abs(float(tg_info["textgrid_xmax_seconds"]) - duration) > 1e-6:
            raise RuntimeError(f"TextGrid/WAV duration mismatch: {utt_id}")
        success_rows.append({
            "review_order": review_order, "year": run["year"], "utt_id": utt_id,
            "session_id": run["session_id"], "form": meta["form"],
            "original_form": meta["original_form"], "tagged": meta["tagged"],
            "source_csv": meta["source_csv"], "source_start_seconds": meta["start"],
            "source_end_seconds": meta["end"], "source_duration_seconds": meta["dur"],
            "lab_text": lab_text, "lab_token_count": run["lab_token_count"],
            "dictionary_oov_count": input_audit_by_id[utt_id]["dictionary_oov_count"],
            "wav_duration_seconds": f"{duration:.9f}", **tg_info,
            "review_wav": out_wav.name, "review_lab": out_lab.name,
            "review_textgrid": out_tg.name, "source_wav_path": str(source_wav.resolve()),
            "source_lab_path": str(source_lab.resolve()), "source_textgrid_path": str(source_tg.resolve()),
            "wav_sha256": sha256_file(source_wav), "lab_sha256": sha256_file(source_lab),
            "textgrid_sha256": sha256_file(source_tg), "decision": "pending",
            "audio_text_match": "pending", "words_alignment": "pending",
            "phones_alignment": "pending", "boundary_quality": "pending", "notes": "",
        })

    write_csv(review_partial / "00_REVIEW_11.csv", SUCCESS_FIELDS, success_rows)
    (review_partial / "00_READ_ME_FIRST.md").write_text(
        "# D6 성공 11건 검토\n\n"
        "각 번호는 같은 이름의 WAV·LAB·2-tier MFA TextGrid 한 세트입니다. "
        "`00_REVIEW_11.csv`에서 음성-전사 일치, words/phones 정렬과 경계를 확인하십시오.\n\n"
        "이 폴더는 D5 진단 결과의 검토용 복사본이며 r3 본체·6-tier·DB v1에는 아직 반영되지 않았습니다.\n",
        encoding="utf-8",
    )

    log_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (D5_OUTPUT_ROOT / "logs").glob("*.log")
    )
    missing_rows: list[dict[str, object]] = []
    for row in result_rows:
        utt_id = row["utt_id"]
        if utt_id not in missing_ids:
            continue
        run = run_by_id[utt_id]
        meta = d2[utt_id]
        evidence = db[utt_id]
        reason = classify_missing(evidence)
        source_lab = Path(run["source_lab_path"])
        missing_rows.append({
            "run_order": row["run_order"], "year": row["year"], "utt_id": utt_id,
            "session_id": row["session_id"], "form": meta["form"],
            "original_form": meta["original_form"], "tagged": meta["tagged"],
            "source_csv": meta["source_csv"], "source_start_seconds": meta["start"],
            "source_end_seconds": meta["end"], "source_duration_seconds": meta["dur"],
            "wav_duration_seconds": run["wav_duration_seconds"],
            "lab_text": source_lab.read_text(encoding="utf-8-sig").strip(),
            "lab_token_count": run["lab_token_count"],
            "dictionary_oov_count": input_audit_by_id[utt_id]["dictionary_oov_count"], **evidence,
            "technical_reason_code": reason,
            "per_utterance_log_evidence": "mentioned_in_log" if utt_id in log_text else "not_emitted",
            "next_action": "manual_wav_lab_identity_check_then_exact_id_resegmentation_or_new_controlled_diagnostic_gate",
            "same_input_blind_rerun_allowed": "false", "automatic_merge_allowed": "false",
            "source_wav_path": run["source_wav_path"], "source_lab_path": run["source_lab_path"],
            "source_wav_sha256": run["source_wav_sha256"], "source_lab_sha256": run["source_lab_sha256"],
        })
    write_csv(release_partial / "D6_MISSING_19_TECHNICAL_LEDGER.csv", MISSING_FIELDS, missing_rows)

    no_run_output: list[dict[str, object]] = []
    for row in no_run_rows:
        utt_id = row["utt_id"]
        meta = d2[utt_id]
        pcm_row = pcm[utt_id]
        category = pcm_row.get("category", "")
        pcm_seconds = pcm_row.get("pcm_sec", "")
        recovery_class = "source_pcm_missing_confirmed" if not pcm_seconds.strip() else "source_pcm_short_confirmed"
        no_run_output.append({
            "run_order": row["run_order"], "year": row["year"], "utt_id": utt_id,
            "session_id": row["session_id"], "form": row["form"],
            "original_form": row["original_form"], "tagged": meta["tagged"],
            "source_csv": meta["source_csv"], "source_start_seconds": meta["start"],
            "source_end_seconds": meta["end"], "source_duration_seconds": meta["dur"],
            "observed_wav_duration_seconds": row["wav_duration_seconds"],
            "source_pcm_check_path": str(PCM_CHECK.resolve()), "source_pcm_category": category,
            "source_pcm_seconds": pcm_seconds, "original_pcm_binary_available": "false",
            "audio_recovery_class": recovery_class,
            "audio_recovery_path": "source_pcm_check + source_csv(start,end,dur) + canonical_session_path",
            "same_input_mfa_allowed": "false",
            "next_action": "recover_or_reconstruct_original_distribution_segment_before_any_mfa",
            "r3_corpus_wav_path": row["r3_corpus_wav_path"], "r3_corpus_lab_path": row["r3_corpus_lab_path"],
            "source_wav_sha256": row["source_wav_sha256"], "source_lab_sha256": row["source_lab_sha256"],
        })
    write_csv(release_partial / "D6_NO_RUN_25_AUDIO_RECOVERY.csv", NO_RUN_FIELDS, no_run_output)
    write_csv(release_partial / "D6_SUCCESS_11_REVIEW.csv", SUCCESS_FIELDS, success_rows)

    gate = {
        "schema_version": "research_db_v1_recovery_d6_gate.v1",
        "status": "hold_pending_researcher_review_and_separate_approval",
        "recorded_at": now_iso(),
        "counts": {"success_review": 11, "technical_missing": 19, "no_same_input_rerun": 25},
        "researcher_actions": [
            "review the 11 WAV/LAB/TextGrid sets and complete the review table",
            "approve or revise the technical routing for the 19 missing exact IDs",
            "retain the 25 no-run records until original-duration audio is recovered",
        ],
        "safety": {
            "r3_body_mutated": False, "research_6tier_mutated": False,
            "db_v1_mutated": False, "automatic_merge_performed": False,
            "same_input_mfa_for_sub_0_1_second_items": False,
        },
        "xlsx_status": "pending_official_workspace_dependency_loader",
    }
    (release_partial / "D6_GATE_PENDING.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (release_partial / "README.md").write_text(
        "# DB v1 recovery D6 gate\n\n"
        "D5 진단을 성공 11건, 미정렬 19건, 동일 입력 재실행 금지 25건으로 분기한 사후 Gate다. "
        "언어학적 실현 판정이나 본체 병합은 수행하지 않았다. 성공 11건은 별도 검토 폴더에서 확인한다.\n\n"
        "공식 XLSX는 번들 의존성 로더 복구 후 이 CSV들을 원본으로 생성한다. CSV가 권위 장부이며 XLSX는 검토 편의 사본이다.\n",
        encoding="utf-8",
    )

    review_manifest = {
        "schema_version": "research_db_v1_recovery_d6_review_manifest.v1",
        "files": [relative_fingerprint(p, review_partial) for p in sorted(review_partial.iterdir()) if p.is_file()],
    }
    (review_partial / "REVIEW_MANIFEST.json").write_text(
        json.dumps(review_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output_manifest = {
        "schema_version": "research_db_v1_recovery_d6_output_manifest.v1",
        "recorded_at": now_iso(),
        "files": [relative_fingerprint(p, release_partial) for p in sorted(release_partial.iterdir()) if p.is_file()],
        "review_manifest_sha256": sha256_file(review_partial / "REVIEW_MANIFEST.json"),
        "input_fingerprints": {
            "d5_results": sha256_file(D5_RESULTS),
            "d5_run_shard": sha256_file(D5_PACKAGE / "D5_RUN_SHARD.csv.gz"),
            "d5_no_run": sha256_file(D5_PACKAGE / "D5_NO_RUN_AUDIO_DURATION_RECOVERY.csv"),
            "d5_input_audit": sha256_file(D5_PACKAGE / "D5_INPUT_AUDIT.csv"),
            "d5_db": sha256_file(D5_DB),
            "source_pcm_check": sha256_file(PCM_CHECK),
        },
    }
    (release_partial / "OUTPUT_MANIFEST.json").write_text(
        json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    os.replace(release_partial, release_root)
    os.replace(review_partial, review_root)
    report = {
        "schema_version": "research_db_v1_recovery_d6_result.v1",
        "status": "built_gate_closed_pending_researcher_review",
        "recorded_at": now_iso(), "release_root": str(release_root),
        "review_root": str(review_root), "counts": gate["counts"],
        "technical_reason_counts": dict(Counter(row["technical_reason_code"] for row in missing_rows)),
        "audio_recovery_counts": dict(Counter(row["audio_recovery_class"] for row in no_run_output)),
        "automatic_merge_performed": False, "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, default=PROJECT_ROOT / "outputs/releases" / D6_ID)
    parser.add_argument("--review-root", type=Path, default=PROJECT_ROOT / "outputs/reviews" / D6_REVIEW_ID)
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "outputs/reports/RESULT_db_v1_recovery_D6_20260815.json")
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
