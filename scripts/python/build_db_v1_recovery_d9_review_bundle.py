#!/usr/bin/env python3
"""Build and audit a flat review bundle for the 19 D9 TextGrids."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
import wave
from pathlib import Path

from praatio import textgrid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d9_common import D8_ID, D9_ID, D9_OUTPUT_ROOT, D9_ROW_COUNT, PROJECT_ROOT, load_json
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


REVIEW_ID = "db_v1_recovery_d9_review_19_20260817"


def fingerprint(path: Path, root: Path | None = None) -> dict:
    stat = path.stat()
    result = {
        "path": str(path.relative_to(root).as_posix()) if root else str(path.resolve()),
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
    }
    return result


def verify_fingerprint(path: Path, record: dict, *, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    if path.stat().st_size != int(record["bytes"]) or sha256_file(path) != record["sha256"]:
        raise RuntimeError(f"{label} fingerprint differs: {path}")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def inspect_textgrid(path: Path, expected_duration: float) -> dict:
    grid = textgrid.openTextgrid(str(path), includeEmptyIntervals=True)
    names = list(grid.tierNames)
    if names != ["words", "phones"]:
        raise RuntimeError(f"D9 review tier mismatch: {path}: {names}")
    if abs(float(grid.maxTimestamp) - expected_duration) > 1e-6:
        raise RuntimeError(f"D9 review WAV/TextGrid duration mismatch: {path}")
    words = grid.getTier("words")
    phones = grid.getTier("phones")
    return {
        "textgrid_xmax_seconds": round(float(grid.maxTimestamp), 9),
        "tier_names": names,
        "words_nonempty_intervals": sum(bool(entry.label.strip()) for entry in words.entries),
        "phones_nonempty_intervals": sum(bool(entry.label.strip()) for entry in phones.entries),
    }


def copy_verified(source: Path, destination: Path) -> None:
    shutil.copy2(source, destination)
    if source.stat().st_size != destination.stat().st_size or sha256_file(source) != sha256_file(destination):
        raise RuntimeError(f"D9 review copy verification failed: {source}")


def build(args: argparse.Namespace) -> dict:
    package = args.package.resolve()
    d8_root = args.d8_root.resolve()
    d9_root = args.d9_root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"D9 review output already exists: {output}")
    partial = output.with_name(f".{output.name}.{uuid.uuid4().hex}.partial")
    partial.mkdir(parents=True, exist_ok=False)
    try:
        done_path = d9_root / "state/MFA_DONE.json"
        audit_path = d9_root / "state/MFA_AUDIT.json"
        done = load_json(done_path)
        audit = load_json(audit_path)
        if done.get("status") != "completed_controlled_retry_no_merge":
            raise RuntimeError("D9 done state differs")
        if int(done.get("expected", -1)) != D9_ROW_COUNT or int(done.get("textgrid_present", -1)) != D9_ROW_COUNT:
            raise RuntimeError("D9 done coverage differs")
        if audit.get("status") != "completed_controlled_retry_no_merge":
            raise RuntimeError("D9 audit status differs")
        run_rows = load_json(package / "D9_RUN_SHARD.json")["rows"]
        audit_by_id = {row["utt_id"]: row for row in audit["results"]}
        d8_by_id = {
            row["utt_id"]: row
            for row in load_json(d8_root / "D8_EXACT_ID_FEASIBILITY.json")["decisions"]
            if row.get("d9_candidate") is True
        }
        ids = {row["utt_id"] for row in run_rows}
        if len(run_rows) != D9_ROW_COUNT or set(audit_by_id) != ids or set(d8_by_id) != ids:
            raise RuntimeError("D9 review exact-ID inputs differ")

        review_rows: list[dict] = []
        files: list[dict] = []
        for row in run_rows:
            order = int(row["run_order"])
            utt_id = row["utt_id"]
            year = int(row["year"])
            source_wav = Path(row["source_wav"]["path"])
            source_lab = Path(row["source_lab"]["path"])
            source_tg = Path(audit_by_id[utt_id]["textgrid"]["path"])
            verify_fingerprint(source_wav, row["source_wav"], label=f"D9 source WAV {utt_id}")
            verify_fingerprint(source_lab, row["source_lab"], label=f"D9 source LAB {utt_id}")
            verify_fingerprint(source_tg, audit_by_id[utt_id]["textgrid"], label=f"D9 TextGrid {utt_id}")
            base = f"{order:02d}_{year}_{utt_id}"
            target_wav = partial / f"{base}.wav"
            target_lab = partial / f"{base}.lab"
            target_tg = partial / f"{base}.TextGrid"
            copy_verified(source_wav, target_wav)
            copy_verified(source_lab, target_lab)
            copy_verified(source_tg, target_tg)
            duration = wav_duration(target_wav)
            tg_info = inspect_textgrid(target_tg, duration)
            d8 = d8_by_id[utt_id]
            review_rows.append(
                {
                    "review_order": order,
                    "year": year,
                    "utt_id": utt_id,
                    "session_id": row["session_id"],
                    "speaker_id": row["speaker_id"],
                    "form": d8["form"],
                    "original_form": d8["original_form"],
                    "tagged": d8["tagged"],
                    "lab_text": row["lab_text"],
                    "source_start_seconds": d8["source_start_seconds"],
                    "source_end_seconds": d8["source_end_seconds"],
                    "wav_duration_seconds": round(duration, 9),
                    "source_overlap": bool(row["source_overlap"]),
                    **tg_info,
                    "wav": target_wav.name,
                    "lab": target_lab.name,
                    "textgrid": target_tg.name,
                    "decision": "pending",
                    "audio_text_match": "pending",
                    "words_alignment": "pending",
                    "phones_alignment": "pending",
                    "boundary_quality": "pending",
                    "notes": "",
                    "adoption_status": "not_adopted_pending_researcher_review",
                }
            )
            files.extend(
                [fingerprint(target_wav, partial), fingerprint(target_lab, partial), fingerprint(target_tg, partial)]
            )

        review_path = partial / "00_REVIEW_19.json"
        atomic_write_json(
            review_path,
            {
                "schema_version": "research_db_v1_recovery_d9_review.v1",
                "status": "pending_researcher_review",
                "rows": review_rows,
            },
        )
        readme = partial / "00_READ_ME_FIRST.md"
        readme.write_text(
            "# D9 회수 19건 검토\n\n"
            "각 번호는 같은 발화의 WAV, LAB, 2-tier MFA TextGrid 한 세트입니다.\n\n"
            "1. WAV를 재생해 LAB 문장과 같은 발화인지 확인합니다.\n"
            "2. WAV와 TextGrid를 Praat에서 함께 열어 words와 phones 경계를 봅니다.\n"
            "3. 허용 판정은 `approve_recovery_alignment`, `keep_separate_partial`, "
            "`reject_technical`입니다.\n"
            "4. `source_overlap=true` 네 건은 정렬이 좋아도 단일 화자 음향분석 자동 승인이 아닙니다.\n\n"
            "현재 19건은 모두 본체 미채택 상태입니다. 이 폴더의 파일을 고쳐도 r3 본체에는 "
            "자동 반영되지 않습니다. 원문·형태소·시간·검토 입력란은 `00_REVIEW_19.json`에 있습니다.\n",
            encoding="utf-8",
        )
        files.extend([fingerprint(review_path, partial), fingerprint(readme, partial)])
        manifest = {
            "schema_version": "research_db_v1_recovery_d9_review_manifest.v1",
            "status": "passed_flat_review_bundle_no_adoption",
            "recorded_at": now_iso(),
            "counts": {"rows": len(review_rows), "wav": D9_ROW_COUNT, "lab": D9_ROW_COUNT, "textgrid": D9_ROW_COUNT},
            "source_overlap_rows": sum(row["source_overlap"] for row in review_rows),
            "inputs": {
                "D9_done": fingerprint(done_path),
                "D9_audit": fingerprint(audit_path),
                "D9_run_shard": fingerprint(package / "D9_RUN_SHARD.json"),
                "D8_feasibility": fingerprint(d8_root / "D8_EXACT_ID_FEASIBILITY.json"),
            },
            "files": files,
            "automatic_adoption_performed": False,
            "spreadsheet_status": "not_created_official_artifact_dependency_loader_unavailable",
            "runtime": runtime_snapshot(PROJECT_ROOT),
        }
        atomic_write_json(partial / "OUTPUT_MANIFEST.json", manifest)
        output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial, output)
        return manifest
    except BaseException:
        raise


def audit(output: Path) -> dict:
    output = output.resolve()
    manifest = load_json(output / "OUTPUT_MANIFEST.json")
    if manifest.get("status") != "passed_flat_review_bundle_no_adoption":
        raise RuntimeError("D9 review manifest status differs")
    for record in manifest["files"]:
        verify_fingerprint(output / record["path"], record, label="D9 review file")
    review = load_json(output / "00_REVIEW_19.json")
    rows = review["rows"]
    if len(rows) != D9_ROW_COUNT or len({row["utt_id"] for row in rows}) != D9_ROW_COUNT:
        raise RuntimeError("D9 review row count/identity differs")
    for row in rows:
        duration = wav_duration(output / row["wav"])
        info = inspect_textgrid(output / row["textgrid"], duration)
        if info["words_nonempty_intervals"] != row["words_nonempty_intervals"]:
            raise RuntimeError(f"D9 review word count differs: {row['utt_id']}")
        if info["phones_nonempty_intervals"] != row["phones_nonempty_intervals"]:
            raise RuntimeError(f"D9 review phone count differs: {row['utt_id']}")
    report = {
        "schema_version": "research_db_v1_recovery_d9_review_audit.v1",
        "status": "passed_flat_review_bundle_no_adoption",
        "recorded_at": now_iso(),
        "rows": len(rows),
        "source_overlap_rows": sum(row["source_overlap"] for row in rows),
        "file_counts": {
            "wav": len(list(output.glob("*.wav"))),
            "lab": len(list(output.glob("*.lab"))),
            "textgrid": len(list(output.glob("*.TextGrid"))),
        },
        "automatic_adoption_performed": False,
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output / "INDEPENDENT_AUDIT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D9_ID)
    parser.add_argument("--d8-root", type=Path, default=PROJECT_ROOT / "outputs/releases" / D8_ID)
    parser.add_argument("--d9-root", type=Path, default=D9_OUTPUT_ROOT)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "outputs/reviews" / REVIEW_ID)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    result = audit(args.output) if args.audit_only else build(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
