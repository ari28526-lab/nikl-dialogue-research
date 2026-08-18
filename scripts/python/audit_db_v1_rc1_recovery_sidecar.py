#!/usr/bin/env python3
"""Independently audit the adopted DB v1 RC1 recovery sidecar."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

from praatio import textgrid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from morph_schema import orth_roman_v2
from pipeline_common import atomic_write_json, now_iso, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818"
GATE_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_rc1_recovery_adoption_gate_20260818"
BASE_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815"
APPROVAL = PROJECT_ROOT / "outputs/approvals/APPROVAL_db_v1_rc1_recovery_adoption_20260818.json"
MATERIALIZER = PROJECT_ROOT / "scripts/python/materialize_db_v1_rc1_recovery_sidecar.py"
DEFAULT_REPORT = PROJECT_ROOT / "outputs/reports/AUDIT_db_v1_rc1_recovery_sidecar_20260818.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def scan_base(path: Path, wanted: set[str]) -> dict[str, dict]:
    found = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            utt_id = row["utt_id"]
            if utt_id in wanted:
                if utt_id in found:
                    raise RuntimeError(f"duplicate base ID: {utt_id}")
                found[utt_id] = dict(row)
    return found


def audit(args: argparse.Namespace) -> dict:
    root = args.root.resolve()
    manifest = load(root / "RC1_RELEASE_MANIFEST.json")
    if manifest["status"] != "internal_rc1_recovery_sidecar_adopted":
        raise RuntimeError("RC1 manifest status differs")
    if manifest["implementation"]["materializer_sha256"] != sha256_file(MATERIALIZER):
        raise RuntimeError("RC1 materializer fingerprint differs")
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise RuntimeError(f"RC1 package file differs: {path}")
    if sha256_file(root / "approval/RESEARCHER_APPROVAL.json") != sha256_file(APPROVAL):
        raise RuntimeError("RC1 embedded approval differs")

    candidate_status = load(GATE_ROOT / "RECOVERY_STATUS_OVERLAY_CANDIDATE.json")
    candidate_snapshots = load(GATE_ROOT / "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json")
    status = load(root / "overlays/RECOVERY_STATUS_OVERLAY.json")
    snapshots = load(root / "overlays/MANUAL_ANNOTATION_SNAPSHOTS.json")
    pointers = load(root / "overlays/ACTIVE_ANNOTATION_POINTERS.json")
    accounting = load(root / "ACCOUNTING.json")
    if len(status["rows"]) != 55 or len(snapshots["rows"]) != 16 or len(pointers["rows"]) != 16:
        raise RuntimeError("RC1 sidecar counts differ")
    approval_sha = sha256_file(APPROVAL)

    for before, after in zip(candidate_status["rows"], status["rows"]):
        normalized = dict(after)
        if normalized.pop("adopted_at", None) != status["recorded_at"]:
            raise RuntimeError(f"status adopted_at differs: {after['utt_id']}")
        if normalized.pop("adoption_approval_sha256", None) != approval_sha:
            raise RuntimeError(f"status approval differs: {after['utt_id']}")
        normalized["adoption_status"] = "pending_researcher_approval"
        if normalized != before:
            raise RuntimeError(f"candidate/adopted status differs beyond approval: {after['utt_id']}")

    pointer_by_id = {row["utt_id"]: row for row in pointers["rows"]}
    for before, after in zip(candidate_snapshots["rows"], snapshots["rows"]):
        normalized = dict(after)
        for key in (
            "active_annotation_source", "active_annotation_revision", "active_textgrid_path",
            "active_textgrid_sha256", "adopted_at", "adoption_approval_sha256",
        ):
            normalized.pop(key, None)
        normalized["review_status"] = "reviewed_frozen_pending_adoption"
        if normalized != before:
            raise RuntimeError(f"candidate/adopted snapshot differs beyond approval: {after['utt_id']}")
        if after["review_status"] != "adopted_rc1_curated_snapshot":
            raise RuntimeError(f"snapshot adoption status differs: {after['utt_id']}")
        if after["adoption_approval_sha256"] != approval_sha:
            raise RuntimeError(f"snapshot approval differs: {after['utt_id']}")
        pointer = pointer_by_id.get(after["utt_id"])
        expected_pointer = {
            "year": after["year"], "utt_id": after["utt_id"],
            "active_annotation_source": "curated",
            "active_annotation_revision": after["active_annotation_revision"],
            "active_textgrid_path": after["active_textgrid_path"],
            "active_textgrid_sha256": after["active_textgrid_sha256"],
            "manual_edit_count": after["manual_edit_count"],
            "phone_layer_status": after["phone_layer_status"],
            "phoneme_layer_status": after["phoneme_layer_status"],
            "morph_enrichment_status": after["morph_enrichment_status"],
        }
        if pointer != expected_pointer:
            raise RuntimeError(f"active pointer differs: {after['utt_id']}")
        path = Path(after["active_textgrid_path"])
        if not path.is_file() or sha256_file(path) != after["active_textgrid_sha256"]:
            raise RuntimeError(f"active curated TextGrid differs: {after['utt_id']}")
        grid = textgrid.openTextgrid(str(path), includeEmptyIntervals=True, reportingMode="error")
        transcript = " ".join(e.label.strip() for e in grid.getTier("words_manual_working").entries if e.label.strip())
        if transcript != after["final_transcript"] or orth_roman_v2(transcript) != after["orth_roman_v2"]:
            raise RuntimeError(f"active curated transcript differs: {after['utt_id']}")
        if after["phone_layer_status"] != "d9_reference_only_not_adopted":
            raise RuntimeError(f"phone was improperly adopted: {after['utt_id']}")
        if after["morph_enrichment_status"] != "pending_rebuild_from_curated_transcript":
            raise RuntimeError(f"morphology was improperly claimed: {after['utt_id']}")

    ids = {row["utt_id"] for row in status["rows"]}
    base = load(BASE_ROOT / "BASE_RELEASE_MANIFEST_2020_2025.json")
    found = {}
    for year in base["scope"]["years"]:
        path = BASE_ROOT / f"ledgers/{year}_utterance_status.csv.gz"
        if sha256_file(path) != base["years"][year]["ledger"]["sha256"]:
            raise RuntimeError(f"RC0 ledger SHA differs: {year}")
        found.update(scan_base(path, {row["utt_id"] for row in status["rows"] if str(row["year"]) == year}))
    if set(found) != ids or any(row["primary_status"] != "post_mfa_technical_exclusion" for row in found.values()):
        raise RuntimeError("RC0 exact-ID base state differs")

    families = Counter(row["proposed_recovery_family"] for row in status["rows"])
    expected = {
        "technical_exclusion": 30, "transcript_recovery": 2, "partial_preserved": 6,
        "curated_recovery": 16, "recovered_alignment": 1,
    }
    if families != expected:
        raise RuntimeError(f"RC1 family accounting differs: {dict(families)}")
    if accounting["recovery_inventory_rows"] != 817310 or accounting["remaining_recovery_inventory_rows"] != 817255:
        raise RuntimeError("RC1 recovery inventory accounting differs")
    if accounting["main_body_alignment_delta"] != 0 or accounting["base_category_delta"] != 0:
        raise RuntimeError("RC1 base accounting was improperly changed")
    if accounting["base_scope"] != base["scope"]:
        raise RuntimeError("RC1 base scope differs")
    if any(manifest["safety"].values()):
        raise RuntimeError("RC1 safety flags differ")

    report = {
        "schema_version": "nikl_dialogue_research_db_v1_rc1_recovery_sidecar_audit.v1",
        "status": "passed_internal_rc1_append_only_sidecar",
        "recorded_at": now_iso(),
        "counts": {"status_rows": 55, "manual_snapshots": 16, "active_pointers": 16},
        "family_counts": dict(sorted(families.items())),
        "base_source_utterances": base["scope"]["source_utterances"],
        "main_body_alignment_delta": 0,
        "remaining_recovery_inventory_rows": 817255,
        "manifest_sha256": sha256_file(root / "RC1_RELEASE_MANIFEST.json"),
        "approval_sha256": approval_sha,
        "safety": manifest["safety"],
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    audit(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
