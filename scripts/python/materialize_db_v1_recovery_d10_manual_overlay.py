"""Materialize the D10 manual-overlay work set without adopting any result.

The D9 alignment is retained as an immutable visual reference.  A separate
``words_manual_working`` tier is created for researcher edits.  Full/manual
recovery candidates start with a blank working tier so that a failed forced
alignment cannot silently become the research annotation.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import wave
from collections import Counter
from pathlib import Path

from praatio import textgrid
from praatio.data_classes.interval_tier import IntervalTier
from praatio.utilities.constants import Interval

from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GATE_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "releases"
    / "nikl_dialogue_research_db_v1_recovery_d10_manual_overlay_gate_20260818"
)
DEFAULT_SOURCE_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "reviews"
    / "db_v1_recovery_d9_review_19_20260817"
)
DEFAULT_TARGET_ROOT = Path(
    r"D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_MANUAL_OVERLAY_0001"
)
EXPECTED_GATE_STATUS = "passed_gate_closed_before_overlay_materialization"
EXPECTED_QUEUE_STATUS = "frozen_candidate_queue_no_materialization"
EXPECTED_REPAIR_COUNTS = {
    "localized_manual_edit": 9,
    "full_manual_realignment": 6,
    "single_word_manual_recovery": 1,
}
EXPECTED_REFERENCE_TIERS = ("words", "phones")
FINAL_TIERS = (
    "words_d9_reference",
    "phones_d9_reference",
    "transcript_proposed",
    "words_manual_working",
)


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def verify_fingerprint(path: Path, record: dict, *, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    actual_bytes = path.stat().st_size
    if actual_bytes != int(record["bytes"]):
        raise RuntimeError(
            f"{label} byte mismatch: {path} expected={record['bytes']} actual={actual_bytes}"
        )
    actual_sha = sha256_file(path)
    if actual_sha != record["sha256"]:
        raise RuntimeError(
            f"{label} SHA-256 mismatch: {path} expected={record['sha256']} actual={actual_sha}"
        )


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        rate = stream.getframerate()
        if rate <= 0:
            raise RuntimeError(f"invalid WAV sample rate: {path}")
        return stream.getnframes() / rate


def row_stem(row: dict) -> str:
    return f"{int(row['review_order']):02d}_{int(row['year'])}_{row['utt_id']}"


def validate_contract(gate_root: Path, source_root: Path) -> dict:
    gate_root = gate_root.resolve()
    source_root = source_root.resolve()
    manifest = load_json(gate_root / "MANIFEST.json")
    for record in manifest.get("files", []):
        verify_fingerprint(
            gate_root / record["path"], record, label=f"D10 Gate {record['path']}"
        )

    gate = load_json(gate_root / "D10_GATE.json")
    queue = load_json(gate_root / "D10_MANUAL_OVERLAY_QUEUE.json")
    decisions_path = source_root / "01_RESEARCHER_DECISIONS_WORKING.json"
    decisions_sha = sha256_file(decisions_path)
    if gate.get("status") != EXPECTED_GATE_STATUS:
        raise RuntimeError(f"unexpected D10 Gate status: {gate.get('status')!r}")
    if queue.get("status") != EXPECTED_QUEUE_STATUS:
        raise RuntimeError(f"unexpected D10 queue status: {queue.get('status')!r}")
    expected_sha = gate.get("source_researcher_decisions_sha256")
    if decisions_sha != expected_sha or queue.get("source_decisions_sha256") != expected_sha:
        raise RuntimeError("D9 researcher-decision SHA-256 no longer matches D10 Gate")

    rows = queue.get("rows", [])
    if len(rows) != 16:
        raise RuntimeError(f"D10 queue count mismatch: expected=16 actual={len(rows)}")
    identities = [(int(row["year"]), row["utt_id"]) for row in rows]
    if len(set(identities)) != len(identities):
        raise RuntimeError("duplicate year/utt_id in D10 queue")
    orders = [int(row["review_order"]) for row in rows]
    if len(set(orders)) != len(orders):
        raise RuntimeError("duplicate review_order in D10 queue")
    repair_counts = Counter(row["repair_class"] for row in rows)
    if dict(repair_counts) != EXPECTED_REPAIR_COUNTS:
        raise RuntimeError(
            f"D10 repair-class mismatch: expected={EXPECTED_REPAIR_COUNTS} "
            f"actual={dict(repair_counts)}"
        )
    for row in rows:
        if not str(row.get("proposed_transcription", "")).strip():
            raise RuntimeError(f"empty proposed transcription: order={row['review_order']}")

    source_manifest_path = source_root / "OUTPUT_MANIFEST.json"
    source_manifest = load_json(source_manifest_path)
    source_records = {record["path"]: record for record in source_manifest["files"]}
    source_audit = []
    for row in rows:
        stem = row_stem(row)
        duration = None
        for suffix in (".wav", ".lab", ".TextGrid"):
            name = f"{stem}{suffix}"
            record = source_records.get(name)
            if record is None:
                raise RuntimeError(f"D9 source manifest record missing: {name}")
            source_path = source_root / name
            verify_fingerprint(source_path, record, label=f"D9 review source {name}")
            if suffix == ".wav":
                duration = wav_duration(source_path)
            elif suffix == ".TextGrid":
                tg = textgrid.openTextgrid(
                    str(source_path), includeEmptyIntervals=True, reportingMode="error"
                )
                if tuple(tg.tierNames) != EXPECTED_REFERENCE_TIERS:
                    raise RuntimeError(
                        f"unexpected D9 tiers: {name} actual={tuple(tg.tierNames)}"
                    )
                if duration is None or abs(tg.maxTimestamp - duration) > 0.001:
                    raise RuntimeError(
                        f"WAV/TextGrid duration mismatch: {name} "
                        f"wav={duration} textgrid={tg.maxTimestamp}"
                    )
        source_audit.append({"review_order": row["review_order"], "duration": duration})

    return {
        "gate_root": gate_root,
        "source_root": source_root,
        "gate": gate,
        "queue": queue,
        "source_manifest_path": source_manifest_path,
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "decisions_path": decisions_path,
        "decisions_sha256": decisions_sha,
        "source_audit": source_audit,
    }


def create_manual_textgrid(source: Path, destination: Path, row: dict) -> None:
    tg = textgrid.openTextgrid(
        str(source), includeEmptyIntervals=True, reportingMode="error"
    )
    duration = tg.maxTimestamp
    source_words = tuple(tg.getTier("words").entries)
    tg.renameTier("words", "words_d9_reference")
    tg.renameTier("phones", "phones_d9_reference")
    proposed = IntervalTier(
        "transcript_proposed",
        [Interval(0.0, duration, row["proposed_transcription"])],
        minT=0.0,
        maxT=duration,
    )
    if row["repair_class"] == "localized_manual_edit":
        working_entries = source_words
    else:
        working_entries = (Interval(0.0, duration, ""),)
    working = IntervalTier(
        "words_manual_working",
        working_entries,
        minT=0.0,
        maxT=duration,
    )
    tg.addTier(proposed)
    tg.addTier(working)
    tg.save(
        str(destination),
        format="long_textgrid",
        includeBlankSpaces=True,
        reportingMode="error",
    )


def build_work_queue(contract: dict) -> dict:
    rows = []
    source_root = contract["source_root"]
    for row in contract["queue"]["rows"]:
        stem = row_stem(row)
        enriched = dict(row)
        enriched["source_files"] = {
            "wav": str((source_root / f"{stem}.wav").resolve()),
            "lab": str((source_root / f"{stem}.lab").resolve()),
            "d9_textgrid": str((source_root / f"{stem}.TextGrid").resolve()),
        }
        enriched["work_files"] = {
            "wav": f"work_flat/{stem}.wav",
            "source_lab": f"work_flat/{stem}.source.lab",
            "proposed_lab": f"work_flat/{stem}.proposed.lab",
            "d9_reference_textgrid": f"work_flat/{stem}.D9_reference.TextGrid",
            "manual_working_textgrid": f"work_flat/{stem}.manual_working.TextGrid",
        }
        enriched["researcher_status"] = "pending_manual_boundary_edit"
        rows.append(enriched)
    return {
        "schema_version": "research_db_v1_recovery_d10_work_queue.v1",
        "status": "materialized_pending_researcher_manual_overlay",
        "recorded_at": now_iso(),
        "source_decisions_sha256": contract["decisions_sha256"],
        "source_manifest_sha256": contract["source_manifest_sha256"],
        "counts": contract["queue"]["counts"],
        "rows": rows,
        "automatic_adoption_performed": False,
    }


def audit_target(target_root: Path, contract: dict, *, require_done: bool = False) -> dict:
    target_root = target_root.resolve()
    work_root = target_root / "work_flat"
    state_root = target_root / "state"
    work_queue_path = state_root / "D10_WORK_QUEUE.json"
    work_queue = load_json(work_queue_path)
    expected_rows = contract["queue"]["rows"]
    if work_queue.get("source_decisions_sha256") != contract["decisions_sha256"]:
        raise RuntimeError("materialized work queue decision hash mismatch")
    if len(work_queue.get("rows", [])) != 16:
        raise RuntimeError("materialized work queue must contain 16 rows")

    counts = Counter()
    files = []
    row_audits = []
    for row in expected_rows:
        stem = row_stem(row)
        source_wav = contract["source_root"] / f"{stem}.wav"
        source_lab = contract["source_root"] / f"{stem}.lab"
        source_tg = contract["source_root"] / f"{stem}.TextGrid"
        targets = {
            "wav": work_root / f"{stem}.wav",
            "source_lab": work_root / f"{stem}.source.lab",
            "proposed_lab": work_root / f"{stem}.proposed.lab",
            "d9_reference_textgrid": work_root / f"{stem}.D9_reference.TextGrid",
            "manual_working_textgrid": work_root / f"{stem}.manual_working.TextGrid",
        }
        for category, path in targets.items():
            if not path.is_file():
                raise RuntimeError(f"D10 target missing: {path}")
            counts[category] += 1
            files.append(
                {
                    "path": str(path.relative_to(target_root)).replace("\\", "/"),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        if sha256_file(targets["wav"]) != sha256_file(source_wav):
            raise RuntimeError(f"copied WAV SHA mismatch: {stem}")
        if sha256_file(targets["source_lab"]) != sha256_file(source_lab):
            raise RuntimeError(f"copied source LAB SHA mismatch: {stem}")
        if sha256_file(targets["d9_reference_textgrid"]) != sha256_file(source_tg):
            raise RuntimeError(f"copied D9 TextGrid SHA mismatch: {stem}")
        proposed_text = targets["proposed_lab"].read_text(encoding="utf-8").strip()
        if proposed_text != row["proposed_transcription"]:
            raise RuntimeError(f"proposed LAB content mismatch: {stem}")

        source_grid = textgrid.openTextgrid(
            str(source_tg), includeEmptyIntervals=True, reportingMode="error"
        )
        manual_grid = textgrid.openTextgrid(
            str(targets["manual_working_textgrid"]),
            includeEmptyIntervals=True,
            reportingMode="error",
        )
        if tuple(manual_grid.tierNames) != FINAL_TIERS:
            raise RuntimeError(
                f"manual TextGrid tier mismatch: {stem} actual={tuple(manual_grid.tierNames)}"
            )
        duration = wav_duration(targets["wav"])
        if abs(manual_grid.maxTimestamp - duration) > 0.001:
            raise RuntimeError(f"manual TextGrid duration mismatch: {stem}")
        if tuple(manual_grid.getTier("words_d9_reference").entries) != tuple(
            source_grid.getTier("words").entries
        ):
            raise RuntimeError(f"D9 word reference changed: {stem}")
        if tuple(manual_grid.getTier("phones_d9_reference").entries) != tuple(
            source_grid.getTier("phones").entries
        ):
            raise RuntimeError(f"D9 phone reference changed: {stem}")
        proposed_entries = manual_grid.getTier("transcript_proposed").entries
        if len(proposed_entries) != 1 or proposed_entries[0].label != row["proposed_transcription"]:
            raise RuntimeError(f"proposed transcript tier mismatch: {stem}")
        working_entries = manual_grid.getTier("words_manual_working").entries
        if row["repair_class"] == "localized_manual_edit":
            if tuple(working_entries) != tuple(source_grid.getTier("words").entries):
                raise RuntimeError(f"localized working tier not initialized from D9: {stem}")
        elif any(entry.label for entry in working_entries):
            raise RuntimeError(f"full/single manual working tier must start blank: {stem}")
        row_audits.append(
            {
                "review_order": row["review_order"],
                "year": row["year"],
                "utt_id": row["utt_id"],
                "repair_class": row["repair_class"],
                "duration_seconds": round(duration, 6),
                "tier_names": list(manual_grid.tierNames),
                "status": "passed_pending_researcher_edit",
            }
        )

    expected_counts = {
        "wav": 16,
        "source_lab": 16,
        "proposed_lab": 16,
        "d9_reference_textgrid": 16,
        "manual_working_textgrid": 16,
    }
    if dict(counts) != expected_counts:
        raise RuntimeError(f"D10 materialized count mismatch: {dict(counts)}")
    if require_done:
        done_path = state_root / "MATERIALIZED_DONE.json"
        audit_path = state_root / "MATERIALIZATION_AUDIT.json"
        done = load_json(done_path)
        if done.get("status") != "materialized_pending_researcher_manual_overlay":
            raise RuntimeError(f"unexpected D10 completion status: {done.get('status')!r}")
        if done.get("source_decisions_sha256") != contract["decisions_sha256"]:
            raise RuntimeError("D10 completion marker decision hash mismatch")
        if not audit_path.is_file():
            raise RuntimeError(f"D10 final materialization audit missing: {audit_path}")
        if done.get("materialization_audit_sha256") != sha256_file(audit_path):
            raise RuntimeError("D10 completion marker/final audit SHA-256 mismatch")
    return {
        "schema_version": "research_db_v1_recovery_d10_materialization_audit.v1",
        "status": "passed_materialization_pending_researcher_manual_overlay",
        "recorded_at": now_iso(),
        "target_root": str(target_root),
        "source_decisions_sha256": contract["decisions_sha256"],
        "source_manifest_sha256": contract["source_manifest_sha256"],
        "counts": expected_counts,
        "repair_counts": EXPECTED_REPAIR_COUNTS,
        "rows": row_audits,
        "files": sorted(files, key=lambda item: item["path"]),
        "safety": {
            "source_files_modified": False,
            "r3_main_body_modified": False,
            "research_6tier_modified": False,
            "db_v1_modified": False,
            "mfa_run": False,
            "automatic_adoption_performed": False,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }


def materialize(target_root: Path, contract: dict) -> dict:
    target_root = target_root.resolve()
    if target_root.exists():
        done_path = target_root / "state" / "MATERIALIZED_DONE.json"
        if done_path.is_file():
            audit = audit_target(target_root, contract, require_done=True)
            audit["idempotent_existing_target"] = True
            return audit
        raise RuntimeError(f"target already exists without completion marker: {target_root}")
    target_root.parent.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(target_root.parent).free
    if free_bytes < 1024**3:
        raise RuntimeError(f"insufficient free space: {free_bytes / 1024**3:.3f} GiB")
    partial_root = target_root.with_name(f".{target_root.name}.partial.{os.getpid()}")
    if partial_root.exists():
        raise RuntimeError(f"partial target already exists: {partial_root}")
    work_root = partial_root / "work_flat"
    state_root = partial_root / "state"
    work_root.mkdir(parents=True)
    state_root.mkdir(parents=True)
    try:
        work_queue = build_work_queue(contract)
        atomic_write_json(state_root / "D10_WORK_QUEUE.json", work_queue)
        for row in contract["queue"]["rows"]:
            stem = row_stem(row)
            source_wav = contract["source_root"] / f"{stem}.wav"
            source_lab = contract["source_root"] / f"{stem}.lab"
            source_tg = contract["source_root"] / f"{stem}.TextGrid"
            shutil.copy2(source_wav, work_root / f"{stem}.wav")
            shutil.copy2(source_lab, work_root / f"{stem}.source.lab")
            (work_root / f"{stem}.proposed.lab").write_text(
                row["proposed_transcription"] + "\n", encoding="utf-8", newline="\n"
            )
            shutil.copy2(source_tg, work_root / f"{stem}.D9_reference.TextGrid")
            create_manual_textgrid(
                source_tg, work_root / f"{stem}.manual_working.TextGrid", row
            )
        readme = (
            "# D10 manual overlay work set\n\n"
            "이 폴더는 D9 실패·부분 정렬 16건의 격리된 수동 보정 작업본이다.\n"
            "r3 본체, 최종 6-tier, DB v1에는 자동 반영되지 않는다.\n\n"
            "- `*.source.lab`: D9 입력 전사(읽기 전용 참고)\n"
            "- `*.proposed.lab`: 연구자 청취 결과를 반영한 전사안\n"
            "- `*.D9_reference.TextGrid`: D9 강제정렬 원본(참고 전용)\n"
            "- `*.manual_working.TextGrid`: 실제 수동 경계 보정 대상\n"
            "- `words_d9_reference`, `phones_d9_reference`: 수정하지 않는 참고 tier\n"
            "- `transcript_proposed`: 확정 전사안\n"
            "- `words_manual_working`: 연구자가 수정할 word tier\n\n"
            "전면 재작업·단일어 회수 건은 잘못된 D9 경계를 채택하지 않도록 "
            "`words_manual_working`을 빈 tier로 시작한다. 국소 수정 건만 D9 word "
            "경계를 초안으로 복사했다. 수동 완료 후에도 별도 검수·adoption Gate가 필요하다.\n"
        )
        (partial_root / "00_READ_ME_FIRST.md").write_text(
            readme, encoding="utf-8", newline="\n"
        )
        # Prove the staging tree before promotion.  The final audit is written
        # only after the directory has its permanent path, so it never records
        # a stale ``.partial`` target as the research work location.
        staging_audit = audit_target(partial_root, contract)
        atomic_write_json(state_root / "MATERIALIZATION_STAGING_AUDIT.json", staging_audit)
        os.replace(partial_root, target_root)
    except BaseException:
        # Preserve partial evidence for diagnosis; never overwrite a future retry.
        raise
    final_audit = audit_target(target_root, contract)
    final_audit["free_gib_after"] = round(
        shutil.disk_usage(target_root.parent).free / 1024**3, 3
    )
    final_state_root = target_root / "state"
    atomic_write_json(final_state_root / "MATERIALIZATION_AUDIT.json", final_audit)
    done = {
        "schema_version": "research_db_v1_recovery_d10_materialized_done.v1",
        "status": "materialized_pending_researcher_manual_overlay",
        "recorded_at": now_iso(),
        "final_target_root": str(target_root),
        "source_decisions_sha256": contract["decisions_sha256"],
        "materialization_audit_sha256": sha256_file(
            final_state_root / "MATERIALIZATION_AUDIT.json"
        ),
        "automatic_adoption_performed": False,
    }
    atomic_write_json(final_state_root / "MATERIALIZED_DONE.json", done)
    return final_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-root", type=Path, default=DEFAULT_GATE_ROOT)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--target-root", type=Path, default=DEFAULT_TARGET_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = validate_contract(args.gate_root, args.source_root)
        if args.preflight_only:
            payload = {
                "status": "preflight_passed_no_materialization",
                "candidates": len(contract["queue"]["rows"]),
                "repair_counts": contract["queue"]["counts"],
                "source_decisions_sha256": contract["decisions_sha256"],
                "target_root": str(args.target_root.resolve()),
            }
        elif args.audit_only:
            payload = audit_target(args.target_root, contract, require_done=True)
        else:
            payload = materialize(args.target_root, contract)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # fail closed with a concise operator message
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
