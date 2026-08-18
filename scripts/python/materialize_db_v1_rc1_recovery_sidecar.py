#!/usr/bin/env python3
"""Materialize the explicitly approved DB v1 RC1 recovery sidecar.

This creates a new, small release package.  RC0 ledgers, r3 databases,
research 6-tier TextGrids, and all source files are read-only inputs.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, git_commit, now_iso, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_rc1_recovery_adoption_gate_20260818"
GATE_AUDIT = PROJECT_ROOT / "outputs/reports/AUDIT_db_v1_rc1_recovery_adoption_gate_20260818.json"
APPROVAL = PROJECT_ROOT / "outputs/approvals/APPROVAL_db_v1_rc1_recovery_adoption_20260818.json"
BASE_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815"
D0_D4_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818"
EXPECTED_STATEMENT = (
    "DB v1 RC1 recovery Gate의 exact-ID 55건 상태 overlay와 D10 수동 전사·word 경계 "
    "16건을 append-only curated snapshot으로 채택한다. 기존 RC0·r3·6-tier는 "
    "덮어쓰지 않고, D9 phone은 참고 전용으로 유지하며 형태소·phone 재구축은 "
    "별도 후속 Gate로 남긴다. 승인자 ari30."
)


def load(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record(path: Path, root: Path) -> dict:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def validate_inputs() -> dict:
    approval = load(APPROVAL)
    gate_manifest = load(GATE_ROOT / "MANIFEST.json")
    gate_contract = load(GATE_ROOT / "ADOPTION_CONTRACT_PENDING.json")
    gate_audit = load(GATE_AUDIT)
    status_candidate = load(GATE_ROOT / "RECOVERY_STATUS_OVERLAY_CANDIDATE.json")
    snapshots_candidate = load(GATE_ROOT / "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json")
    base = load(BASE_ROOT / "BASE_RELEASE_MANIFEST_2020_2025.json")
    d0_manifest = load(D0_D4_ROOT / "OUTPUT_MANIFEST.json")
    expected_hashes = {
        "gate_manifest_sha256": sha256_file(GATE_ROOT / "MANIFEST.json"),
        "status_overlay_sha256": sha256_file(GATE_ROOT / "RECOVERY_STATUS_OVERLAY_CANDIDATE.json"),
        "manual_snapshots_sha256": sha256_file(GATE_ROOT / "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json"),
        "approval_template_sha256": sha256_file(GATE_ROOT / "RESEARCHER_APPROVAL_TEMPLATE.json"),
        "independent_gate_audit_sha256": sha256_file(GATE_AUDIT),
    }
    if approval.get("status") != "explicitly_approved" or approval.get("approved_by") != "ari30":
        raise RuntimeError("RC1 adoption approval is not explicit")
    if approval.get("approval_statement") != EXPECTED_STATEMENT:
        raise RuntimeError("RC1 approval statement differs")
    if approval.get("candidate_hashes") != expected_hashes:
        raise RuntimeError("RC1 approval candidate hashes differ")
    if approval.get("automatic_approval_performed"):
        raise RuntimeError("automatic approval is forbidden")
    if any(bool(value) for key, value in approval["scope"].items() if key.endswith("_allowed")):
        raise RuntimeError("approval scope contains an unsafe permission")
    if gate_manifest["status"] != "gate_closed_pending_researcher_approval":
        raise RuntimeError("candidate gate manifest status differs")
    if gate_contract["status"] != "gate_closed_pending_researcher_approval" or any(gate_contract["safety"].values()):
        raise RuntimeError("candidate gate safety differs")
    if gate_audit["status"] != "passed_gate_closed_pending_researcher_approval":
        raise RuntimeError("independent candidate gate audit did not pass")
    if base["status"] != "internal_rc0_ac_complete":
        raise RuntimeError("base RC0 status differs")
    if d0_manifest["status"] != "passed_stopped_before_materialization_and_mfa":
        raise RuntimeError("D0-D4 status differs")
    rows, snapshots = status_candidate["rows"], snapshots_candidate["rows"]
    if len(rows) != 55 or len({row["utt_id"] for row in rows}) != 55 or len(snapshots) != 16:
        raise RuntimeError("approved candidate scope differs")
    if {row["utt_id"] for row in snapshots} != {
        row["utt_id"] for row in rows if row["proposed_recovery_family"] == "curated_recovery"
    }:
        raise RuntimeError("curated status/snapshot IDs differ")
    return {
        "approval": approval, "gate_manifest": gate_manifest, "gate_audit": gate_audit,
        "status_candidate": status_candidate, "snapshots_candidate": snapshots_candidate,
        "base": base, "d0_manifest": d0_manifest,
    }


def materialize(args: argparse.Namespace) -> dict:
    state = validate_inputs()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"RC1 output already exists; refusing overwrite: {output}")
    adopted_at = now_iso()
    approval_sha = sha256_file(APPROVAL)

    status_doc = copy.deepcopy(state["status_candidate"])
    status_doc["schema_version"] = "research_db_v1_rc1_recovery_status_overlay.v1"
    status_doc["status"] = "adopted_append_only_rc1_sidecar"
    status_doc["recorded_at"] = adopted_at
    status_doc["approval_sha256"] = approval_sha
    for row in status_doc["rows"]:
        row["adoption_status"] = "adopted_append_only_rc1"
        row["adopted_at"] = adopted_at
        row["adoption_approval_sha256"] = approval_sha

    snapshots_doc = copy.deepcopy(state["snapshots_candidate"])
    snapshots_doc["schema_version"] = "research_db_v1_rc1_manual_annotation_snapshots.v1"
    snapshots_doc["status"] = "adopted_append_only_rc1_sidecar"
    snapshots_doc["recorded_at"] = adopted_at
    snapshots_doc["approval_sha256"] = approval_sha
    pointers = []
    for row in snapshots_doc["rows"]:
        row["review_status"] = "adopted_rc1_curated_snapshot"
        row["active_annotation_source"] = "curated"
        row["active_annotation_revision"] = row["active_annotation_revision_candidate"]
        row["active_textgrid_path"] = row["active_textgrid_path_candidate"]
        row["active_textgrid_sha256"] = row["active_textgrid_sha256_candidate"]
        row["adopted_at"] = adopted_at
        row["adoption_approval_sha256"] = approval_sha
        pointers.append({
            "year": row["year"], "utt_id": row["utt_id"],
            "active_annotation_source": "curated",
            "active_annotation_revision": row["active_annotation_revision"],
            "active_textgrid_path": row["active_textgrid_path"],
            "active_textgrid_sha256": row["active_textgrid_sha256"],
            "manual_edit_count": row["manual_edit_count"],
            "phone_layer_status": row["phone_layer_status"],
            "phoneme_layer_status": row["phoneme_layer_status"],
            "morph_enrichment_status": row["morph_enrichment_status"],
        })
    pointers.sort(key=lambda row: (row["year"], row["utt_id"]))
    pointers_doc = {
        "schema_version": "research_db_v1_rc1_active_annotation_pointers.v1",
        "status": "adopted_append_only_rc1_sidecar", "recorded_at": adopted_at,
        "rows": pointers, "base_annotation_replaced": False,
    }

    families = Counter(row["proposed_recovery_family"] for row in status_doc["rows"])
    base_scope = state["base"]["scope"]
    d0_summary = load(D0_D4_ROOT / "BUILD_SUMMARY.json")
    recovery_total = int(d0_summary["counts"]["recovery_total"])
    accounting = {
        "schema_version": "research_db_v1_rc1_recovery_accounting.v1",
        "status": "passed_append_only_no_base_category_delta",
        "recorded_at": adopted_at,
        "base_release_id": state["base"]["release_prep_id"],
        "base_scope": base_scope,
        "base_accounting_equation": state["base"]["accounting_equation"],
        "recovery_inventory_rows": recovery_total,
        "first_shard_adopted_status_rows": 55,
        "remaining_recovery_inventory_rows": recovery_total - 55,
        "first_shard_family_counts": dict(sorted(families.items())),
        "main_body_alignment_delta": 0,
        "base_category_delta": 0,
        "reason": (
            "D9 alignment 1 and D10 curated 16 remain outside aligned 6-tier main body "
            "until separate phone/morphology enrichment gates pass"
        ),
    }
    if recovery_total != 817310 or accounting["remaining_recovery_inventory_rows"] != 817255:
        raise RuntimeError("recovery accounting differs")

    partial = output.with_name(f".{output.name}.partial.{os.getpid()}")
    if partial.exists():
        raise RuntimeError(f"partial output exists: {partial}")
    (partial / "approval").mkdir(parents=True)
    (partial / "overlays").mkdir(parents=True)
    try:
        shutil.copy2(APPROVAL, partial / "approval/RESEARCHER_APPROVAL.json")
        atomic_write_json(partial / "overlays/RECOVERY_STATUS_OVERLAY.json", status_doc)
        atomic_write_json(partial / "overlays/MANUAL_ANNOTATION_SNAPSHOTS.json", snapshots_doc)
        atomic_write_json(partial / "overlays/ACTIVE_ANNOTATION_POINTERS.json", pointers_doc)
        atomic_write_json(partial / "ACCOUNTING.json", accounting)
        readme = (
            "# NIKL dialogue research DB v1.0.0-rc1 — recovery sidecar\n\n"
            "이 release는 RC0를 덮어쓰지 않는 append-only sidecar다. 첫 recovery "
            "shard 55건의 후속 상태와 연구자 수동 word·전사 16건의 active pointer를 "
            "추가한다. r3·6-tier·MFA DB는 변경하지 않았다.\n\n"
            "D9 phone은 참고 전용이며, 수정 전사에 대한 형태소와 phone/phoneme은 "
            "별도 후속 Gate 전까지 pending이다. 따라서 RC1은 16건을 정렬 성공 "
            "본체에 소급 합산하지 않는다.\n"
        )
        (partial / "README.md").write_text(readme, encoding="utf-8", newline="\n")
        names = [
            "approval/RESEARCHER_APPROVAL.json", "overlays/RECOVERY_STATUS_OVERLAY.json",
            "overlays/MANUAL_ANNOTATION_SNAPSHOTS.json", "overlays/ACTIVE_ANNOTATION_POINTERS.json",
            "ACCOUNTING.json", "README.md",
        ]
        manifest = {
            "schema_version": "nikl_dialogue_research_db_v1_rc1_release_manifest.v1",
            "status": "internal_rc1_recovery_sidecar_adopted",
            "recorded_at": adopted_at,
            "release_id": "nikl_dialogue_research_db_v1_0_0_rc1_20260818",
            "base_release_id": state["base"]["release_prep_id"],
            "scope": {"recovery_status_rows": 55, "manual_annotation_snapshots": 16, "active_pointers": 16},
            "inputs": {
                "base_manifest_sha256": sha256_file(BASE_ROOT / "BASE_RELEASE_MANIFEST_2020_2025.json"),
                "d0_d4_manifest_sha256": sha256_file(D0_D4_ROOT / "OUTPUT_MANIFEST.json"),
                "candidate_gate_manifest_sha256": sha256_file(GATE_ROOT / "MANIFEST.json"),
                "candidate_gate_audit_sha256": sha256_file(GATE_AUDIT),
                "researcher_approval_sha256": approval_sha,
            },
            "implementation": {"materializer_sha256": sha256_file(Path(__file__).resolve()), "git_commit": git_commit(PROJECT_ROOT)},
            "files": [record(partial / name, partial) for name in names],
            "safety": {
                "base_rc0_modified": False, "r3_modified": False,
                "research_6tier_modified": False, "textgrid_modified": False,
                "mfa_run": False, "phone_adopted": False, "morphology_rebuilt": False,
            },
        }
        atomic_write_json(partial / "RC1_RELEASE_MANIFEST.json", manifest)
        os.replace(partial, output)
    except BaseException:
        if partial.exists():
            shutil.rmtree(partial)
        raise
    result = {
        "status": "materialized_internal_rc1_recovery_sidecar_adopted",
        "output": str(output), "status_rows": 55, "active_pointers": 16,
        "manifest_sha256": sha256_file(output / "RC1_RELEASE_MANIFEST.json"),
        "base_modified": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    materialize(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
