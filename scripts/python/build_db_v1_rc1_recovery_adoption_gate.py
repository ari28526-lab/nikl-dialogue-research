#!/usr/bin/env python3
"""Build a closed DB v1 RC1 recovery-adoption gate for the first 55 cases.

The RC0 ledgers and all r3/TextGrid assets are read-only.  The output is a
small append-only overlay candidate; it does not adopt or rewrite anything.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

from praatio import textgrid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from morph_schema import orth_roman_v2
from pipeline_common import atomic_write_json, git_commit, now_iso, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815"
D0_D4_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
D7_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d7_partial_alignment_gate_20260817"
D8_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d8_feasibility_audit_20260817"
D9_REVIEW_ROOT = PROJECT_ROOT / "outputs/reviews/db_v1_recovery_d9_review_19_20260817"
D10_ROOT = Path(r"D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_RESEARCHER_RETURN_0001")
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_rc1_recovery_adoption_gate_20260818"
EXPECTED_D10_COUNTS = {
    "tier_remap_from_proposed": 4,
    "exact_word_sequence": 6,
    "same_characters_different_word_segmentation": 1,
    "researcher_manual_transcription_override": 5,
}


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_record(path: Path, *, relative_to: Path | None = None) -> dict:
    path = path.resolve()
    label = path.relative_to(relative_to.resolve()).as_posix() if relative_to else str(path)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def validate_manifest_file(manifest: dict, path: Path) -> None:
    wanted = str(path.resolve()).lower()
    records = manifest.get("files", [])
    matching = [row for row in records if str(Path(row["path"]).resolve()).lower() == wanted]
    if len(matching) != 1 or matching[0]["sha256"] != sha256_file(path):
        raise RuntimeError(f"manifest fingerprint mismatch: {path}")


def scan_exact_csv_gz(path: Path, ids: set[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if "utt_id" not in (reader.fieldnames or []):
            raise RuntimeError(f"utt_id field missing: {path}")
        for row in reader:
            utt_id = row["utt_id"]
            if utt_id in ids:
                if utt_id in found:
                    raise RuntimeError(f"duplicate exact ID: {utt_id} in {path}")
                found[utt_id] = dict(row)
    return found


def intervals(tier) -> list[dict]:
    return [
        {"xmin": entry.start, "xmax": entry.end, "label": entry.label}
        for entry in tier.entries
    ]


def validate_tier(tier, duration: float, label: str) -> None:
    entries = tuple(tier.entries)
    if not entries or abs(entries[0].start) > 1e-9 or abs(entries[-1].end - duration) > 1e-9:
        raise RuntimeError(f"tier outer boundary mismatch: {label}")
    for left, right in zip(entries, entries[1:]):
        if abs(left.end - right.start) > 1e-9:
            raise RuntimeError(f"tier gap/overlap: {label}")


def d7_mapping(row: dict) -> tuple[str, str, str]:
    usability = row["research_usability"]
    if usability == "noise_hold":
        return "excluded_noise_diagnostic_preserved", "technical_exclusion", "diagnostic_only"
    if usability in {"transcript_segment_missing", "transcript_correction_candidate"}:
        return "excluded_transcript_recovery_candidate", "transcript_recovery", "recovery_candidate"
    if usability == "partial_alignment_available":
        return "excluded_partial_alignment_preserved", "partial_preserved", "recovery_reference"
    raise RuntimeError(f"unknown D7 research usability: {usability}")


def build(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"output already exists; refusing overwrite: {output}")

    base_manifest_path = BASE_ROOT / "BASE_RELEASE_MANIFEST_2020_2025.json"
    d0_manifest_path = D0_D4_ROOT / "OUTPUT_MANIFEST.json"
    d7_path = D7_ROOT / "D7_EXACT_ID_DECISIONS.json"
    d8_path = D8_ROOT / "D8_EXACT_ID_FEASIBILITY.json"
    d9_path = D9_REVIEW_ROOT / "01_RESEARCHER_DECISIONS_WORKING.json"
    d10_queue_path = D10_ROOT / "state/D10_RESEARCHER_RETURN_QUEUE.json"
    d10_audit_path = D10_ROOT / "state/FINAL_AUDIT.json"
    d10_done_path = D10_ROOT / "state/FROZEN_DONE.json"

    base_manifest = load_json(base_manifest_path)
    d0_manifest = load_json(d0_manifest_path)
    d7_doc, d8_doc, d9_doc = load_json(d7_path), load_json(d8_path), load_json(d9_path)
    d10_queue, d10_audit, d10_done = (
        load_json(d10_queue_path), load_json(d10_audit_path), load_json(d10_done_path)
    )
    if base_manifest["status"] != "internal_rc0_ac_complete":
        raise RuntimeError("unexpected DB v1 RC0 status")
    if d0_manifest["status"] != "passed_stopped_before_materialization_and_mfa":
        raise RuntimeError("unexpected D0-D4 status")
    if d9_doc["status"] != "researcher_review_complete_gate_closed_pending_adoption":
        raise RuntimeError("unexpected D9 researcher review status")
    if d10_done["status"] != "frozen_researcher_return_pending_adoption_gate":
        raise RuntimeError("unexpected D10 completion status")
    if d10_done["final_audit_sha256"] != sha256_file(d10_audit_path):
        raise RuntimeError("D10 completion/audit SHA mismatch")
    if d10_queue["classification_counts"] != EXPECTED_D10_COUNTS:
        raise RuntimeError("D10 classification counts differ")
    if d10_queue["source_decisions_sha256"] != sha256_file(d9_path):
        raise RuntimeError("D10 source/D9 decision SHA mismatch")

    d7_rows = d7_doc["decisions"]
    d8_rows = d8_doc["decisions"]
    d9_rows = d9_doc["decisions"]
    d10_rows = d10_queue["rows"]
    if (len(d7_rows), len(d8_rows), len(d9_rows), len(d10_rows)) != (11, 44, 19, 16):
        raise RuntimeError("D7-D10 row counts differ")
    d8_d9 = [row for row in d8_rows if row["d9_candidate"]]
    d8_short = [row for row in d8_rows if not row["d9_candidate"]]
    d9_by_id = {row["utt_id"]: row for row in d9_rows}
    d8_by_id = {row["utt_id"]: row for row in d8_d9}
    d10_by_id = {row["utt_id"]: row for row in d10_rows}
    d7_ids = {row["utt_id"] for row in d7_rows}
    d8_short_ids = {row["utt_id"] for row in d8_short}
    d9_ids = set(d9_by_id)
    if len(d7_ids) != 11 or len(d8_short_ids) != 25 or len(d9_ids) != 19:
        raise RuntimeError("D7/D8/D9 exact-ID uniqueness differs")
    if d7_ids & d8_short_ids or d7_ids & d9_ids or d8_short_ids & d9_ids:
        raise RuntimeError("D7/D8/D9 exact-ID sets overlap")
    if set(d8_by_id) != d9_ids:
        raise RuntimeError("D8 19/D9 19 exact-ID sets differ")
    if set(d10_by_id) != {k for k, v in d9_by_id.items() if v["decision"] == "keep_separate_partial"}:
        raise RuntimeError("D10 16 do not equal D9 manual-overlay decisions")
    all_ids = d7_ids | d8_short_ids | d9_ids

    base_by_id: dict[str, dict] = {}
    route_by_id: dict[str, dict] = {}
    for year in base_manifest["scope"]["years"]:
        year_ids = {utt_id for utt_id in all_ids if int(year) == next(
            int(row["year"]) for row in (d7_rows + d8_rows) if row["utt_id"] == utt_id
        )}
        base_path = BASE_ROOT / f"ledgers/{year}_utterance_status.csv.gz"
        expected_sha = base_manifest["years"][year]["ledger"]["sha256"]
        if sha256_file(base_path) != expected_sha:
            raise RuntimeError(f"base ledger SHA mismatch: {year}")
        d1_path = D0_D4_ROOT / f"D1_recovery_ledger/{year}_recovery_routing.csv.gz"
        validate_manifest_file(d0_manifest, d1_path)
        base_by_id.update(scan_exact_csv_gz(base_path, year_ids))
        route_by_id.update(scan_exact_csv_gz(d1_path, year_ids))
    if set(base_by_id) != all_ids or set(route_by_id) != all_ids:
        raise RuntimeError("55 exact IDs are not complete in base/D1 ledgers")
    for utt_id in all_ids:
        if base_by_id[utt_id]["primary_status"] != "post_mfa_technical_exclusion":
            raise RuntimeError(f"unexpected base status: {utt_id}")
        if route_by_id[utt_id]["primary_status"] != "post_mfa_technical_exclusion":
            raise RuntimeError(f"unexpected D1 status: {utt_id}")

    d10_audit_rows = {row["utt_id"]: row for row in d10_audit["rows"]}
    normalized_files = {
        Path(row["path"]).name: row for row in d10_audit["files"] if row["kind"] == "normalized"
    }
    snapshots = []
    for utt_id, row in sorted(d10_by_id.items(), key=lambda item: int(item[1]["review_order"])):
        audit_row = d10_audit_rows[utt_id]
        name = f"{int(row['review_order']):02d}_{int(row['year'])}_{utt_id}.manual_overlay.TextGrid"
        record = normalized_files.get(name)
        if record is None:
            raise RuntimeError(f"D10 normalized manifest row missing: {utt_id}")
        curated_path = D10_ROOT / record["path"]
        if sha256_file(curated_path) != record["sha256"]:
            raise RuntimeError(f"D10 normalized TextGrid SHA differs: {utt_id}")
        grid = textgrid.openTextgrid(str(curated_path), includeEmptyIntervals=True, reportingMode="error")
        if tuple(grid.tierNames) != (
            "words_d9_reference", "phones_d9_reference", "transcript_proposed", "words_manual_working"
        ):
            raise RuntimeError(f"D10 tier contract differs: {utt_id}")
        for tier_name in grid.tierNames:
            validate_tier(grid.getTier(tier_name), grid.maxTimestamp, f"{utt_id}:{tier_name}")
        manual_words = [e.label.strip() for e in grid.getTier("words_manual_working").entries if e.label.strip()]
        if manual_words != audit_row["final_manual_words"]:
            raise RuntimeError(f"D10 final manual words differ: {utt_id}")
        final_transcript = " ".join(manual_words)
        d9_order = int(d9_by_id[utt_id]["review_order"])
        d9_tg = D9_REVIEW_ROOT / f"{d9_order:02d}_{int(row['year'])}_{utt_id}.TextGrid"
        if not d9_tg.is_file():
            raise RuntimeError(f"D9 reference TextGrid missing: {d9_tg}")
        snapshots.append({
            "edit_id": f"D10-{int(row['review_order']):02d}-{utt_id}",
            "study_id": "nikl_dialogue_research_db_v1",
            "year": int(row["year"]),
            "utt_id": utt_id,
            "base_release_id": base_manifest["release_prep_id"],
            "base_textgrid_path": str(d9_tg.resolve()),
            "base_textgrid_sha256": sha256_file(d9_tg),
            "parent_revision": "db_v1_0_0_rc0",
            "tier_name": "words_manual_working",
            "operation": "replace_tier_snapshot_candidate",
            "base_word_intervals": intervals(grid.getTier("words_d9_reference")),
            "curated_word_intervals": intervals(grid.getTier("words_manual_working")),
            "final_transcript": final_transcript,
            "orth_roman_v2": orth_roman_v2(final_transcript),
            "edit_reason": f"d10_researcher_return:{row['return_classification']}",
            "editor": "ari30",
            "edited_at": d10_queue["recorded_at"],
            "review_status": "reviewed_frozen_pending_adoption",
            "active_annotation_source_candidate": "curated",
            "active_annotation_revision_candidate": "D10_researcher_return_0001",
            "active_textgrid_path_candidate": str(curated_path.resolve()),
            "active_textgrid_sha256_candidate": record["sha256"],
            "manual_edit_count": 1,
            "phone_layer_status": "d9_reference_only_not_adopted",
            "phoneme_layer_status": "pending_curated_alignment",
            "morph_enrichment_status": "pending_rebuild_from_curated_transcript",
        })

    status_rows = []
    def add_status(source: str, source_row: dict, status: str, family: str, visibility: str,
                   annotation: str, phone_status: str, evidence_path: Path) -> None:
        utt_id = source_row["utt_id"]
        base = base_by_id[utt_id]
        route = route_by_id[utt_id]
        status_rows.append({
            "year": int(base["year"]), "utt_id": utt_id, "session_id": base["session_id"],
            "base_primary_status": base["primary_status"], "base_status_family": base["status_family"],
            "base_reason_codes_json": base["reason_codes_json"],
            "d1_recovery_family": route["recovery_family"], "d1_recovery_shard_id": route["recovery_shard_id"],
            "outcome_source": source, "proposed_recovery_status": status,
            "proposed_recovery_family": family, "proposed_visibility": visibility,
            "active_annotation_source_candidate": annotation,
            "active_annotation_revision_candidate": "D10_researcher_return_0001" if annotation == "curated" else None,
            "phone_layer_status": phone_status,
            "evidence_path": str(evidence_path.resolve()), "evidence_sha256": sha256_file(evidence_path),
            "adoption_status": "pending_researcher_approval",
        })

    for row in d7_rows:
        status, family, visibility = d7_mapping(row)
        add_status("D7", row, status, family, visibility, "diagnostic_reference",
                   "diagnostic_reference_only", Path(row["textgrid_path"]))
    for row in d8_short:
        add_status("D8", row, "unresolved_technical_exclusion_source_fragment_too_short",
                   "technical_exclusion", "ledger_only", "none", "not_available",
                   Path(row["canonical_wav"]["path"]))
    for row in d9_rows:
        utt_id = row["utt_id"]
        source_row = d8_by_id[utt_id]
        d9_tg = D9_REVIEW_ROOT / f"{int(row['review_order']):02d}_{int(source_row['year'])}_{utt_id}.TextGrid"
        if row["decision"] == "keep_separate_partial":
            add_status("D9+D10", source_row, "curated_manual_word_overlay_pending_phone",
                       "curated_recovery", "curated_annotation_candidate", "curated",
                       "d9_reference_only_not_adopted", D10_ROOT / next(
                           r["path"] for r in d10_audit["files"]
                           if r["kind"] == "normalized" and utt_id in r["path"]
                       ))
        elif row["decision"] == "reject_technical":
            add_status("D9", source_row, "unresolved_technical_exclusion_audio_or_overlap",
                       "technical_exclusion", "ledger_only", "none", "not_adopted", d9_tg)
        elif row["decision"] == "approve_recovery_alignment":
            add_status("D9", source_row, "recovered_d9_alignment_pending_six_tier_enrichment",
                       "recovered_alignment", "alignment_candidate", "d9_alignment_candidate",
                       "d9_alignment_candidate", d9_tg)
        else:
            raise RuntimeError(f"unknown D9 decision: {row['decision']}")
    status_rows.sort(key=lambda row: (row["year"], row["utt_id"]))
    if len(status_rows) != 55 or len({r["utt_id"] for r in status_rows}) != 55:
        raise RuntimeError("status overlay must contain 55 unique rows")

    partial = output.with_name(f".{output.name}.partial.{os.getpid()}")
    if partial.exists():
        raise RuntimeError(f"partial output already exists: {partial}")
    partial.mkdir(parents=True)
    try:
        status_doc = {
            "schema_version": "research_db_v1_rc1_recovery_status_overlay_candidate.v1",
            "status": "passed_candidate_pending_researcher_adoption",
            "recorded_at": now_iso(), "base_release_id": base_manifest["release_prep_id"],
            "scope": {"rows": 55, "d7": 11, "d8_short": 25, "d9": 19},
            "rows": status_rows, "base_ledger_mutated": False,
        }
        snapshots_doc = {
            "schema_version": "research_db_v1_manual_annotation_snapshot_candidate.v1",
            "status": "passed_candidate_pending_researcher_adoption",
            "recorded_at": now_iso(), "rows": snapshots,
            "constraints": {
                "base_textgrids_modified": False,
                "curated_phone_boundaries_claimed": False,
                "morphology_rebuilt": False,
            },
        }
        atomic_write_json(partial / "RECOVERY_STATUS_OVERLAY_CANDIDATE.json", status_doc)
        atomic_write_json(partial / "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json", snapshots_doc)
        approval = {
            "schema_version": "research_db_v1_rc1_recovery_adoption_approval.v1",
            "status": "pending_researcher_approval",
            "scope": {"status_overlay_rows": 55, "manual_annotation_snapshots": 16},
            "candidate_hashes": {
                "status_overlay_sha256": sha256_file(partial / "RECOVERY_STATUS_OVERLAY_CANDIDATE.json"),
                "manual_snapshots_sha256": sha256_file(partial / "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json"),
            },
            "approval_statement": (
                "DB v1 RC1 recovery Gate의 exact-ID 55건 상태 overlay와 D10 수동 전사·word 경계 "
                "16건을 append-only curated snapshot으로 채택한다. 기존 RC0·r3·6-tier는 덮어쓰지 "
                "않고, D9 phone은 참고 전용으로 유지하며 형태소·phone 재구축은 별도 후속 Gate로 "
                "남긴다. 승인자 ari30."
            ),
            "approved_by": None, "approved_at": None,
            "automatic_approval_performed": False,
        }
        atomic_write_json(partial / "RESEARCHER_APPROVAL_TEMPLATE.json", approval)
        contract = {
            "schema_version": "research_db_v1_rc1_recovery_adoption_gate.v1",
            "status": "gate_closed_pending_researcher_approval",
            "recorded_at": now_iso(),
            "counts": {
                "exact_status_rows": 55, "manual_snapshots": 16,
                "technical_or_noise_exclusions": sum(r["proposed_recovery_family"] == "technical_exclusion" for r in status_rows),
                "transcript_recovery_candidates": sum(r["proposed_recovery_family"] == "transcript_recovery" for r in status_rows),
                "partial_preserved": sum(r["proposed_recovery_family"] == "partial_preserved" for r in status_rows),
                "curated_recovery": 16, "recovered_alignment_pending_enrichment": 1,
            },
            "safety": {
                "base_ledger_modified": False, "r3_main_body_modified": False,
                "research_6tier_modified": False, "textgrid_modified": False,
                "mfa_run": False, "automatic_adoption_performed": False,
            },
            "next_gate": "researcher approval, then append-only RC1 sidecar materialization",
        }
        atomic_write_json(partial / "ADOPTION_CONTRACT_PENDING.json", contract)
        readme = (
            "# DB v1 RC1 recovery adoption Gate\n\n"
            "첫 recovery shard 55건을 RC0를 덮어쓰지 않는 상태 overlay 후보로 묶었다. "
            "D10 16건은 연구자가 확정한 word·전사만 curated snapshot으로 제안하며, "
            "D9 phone은 참고 전용이고 형태소·phone 재구축은 아직 수행하지 않았다.\n\n"
            "현재 Gate는 닫혀 있다. 이 폴더 생성은 DB·r3·6-tier·TextGrid를 수정하지 않는다.\n"
        )
        (partial / "README.md").write_text(readme, encoding="utf-8", newline="\n")
        content_files = [
            "RECOVERY_STATUS_OVERLAY_CANDIDATE.json",
            "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json",
            "RESEARCHER_APPROVAL_TEMPLATE.json",
            "ADOPTION_CONTRACT_PENDING.json",
            "README.md",
        ]
        manifest = {
            "schema_version": "research_db_v1_rc1_recovery_adoption_gate_manifest.v1",
            "status": "gate_closed_pending_researcher_approval",
            "recorded_at": now_iso(),
            "inputs": {
                "base_manifest_sha256": sha256_file(base_manifest_path),
                "d0_d4_manifest_sha256": sha256_file(d0_manifest_path),
                "d7_decisions_sha256": sha256_file(d7_path),
                "d8_feasibility_sha256": sha256_file(d8_path),
                "d9_researcher_decisions_sha256": sha256_file(d9_path),
                "d10_queue_sha256": sha256_file(d10_queue_path),
                "d10_final_audit_sha256": sha256_file(d10_audit_path),
                "d10_done_sha256": sha256_file(d10_done_path),
            },
            "implementation": {"builder_sha256": sha256_file(Path(__file__).resolve()), "git_commit": git_commit(PROJECT_ROOT)},
            "files": [file_record(partial / name, relative_to=partial) for name in content_files],
        }
        atomic_write_json(partial / "MANIFEST.json", manifest)
        os.replace(partial, output)
    except BaseException:
        if partial.exists():
            shutil.rmtree(partial)
        raise
    result = {
        "status": "built_gate_closed_pending_researcher_approval",
        "output": str(output), "status_rows": 55, "manual_snapshots": 16,
        "manifest_sha256": sha256_file(output / "MANIFEST.json"),
        "database_modified": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
