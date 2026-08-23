#!/usr/bin/env python3
"""Independently audit the adopted Stage 2 Gate 1 NI frozen contracts."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


sys.stdout.reconfigure(encoding="utf-8")


ADOPTION_SHA = "637f7b0fa0198241fbca84fbfbfbf2e590adb1dbf4168ee0e59a05cf9031796e"
REVIEW_SHA = "8ed621ccf75f8ba9044799c96506bb00fbe39f881e6b1f8455b3752a4e495bc0"
SOURCE_REGISTRY_SHA = "06d44af2e930429f63019a31777dd472d293411723b92d0d56e409ebe6af6b12"
CONTRACT_CANDIDATE_SHA = "2c5a1f4cf4eb89ac4be57878d41f77906cee9cfa21f6f87c1d751a600de7c9ff"
ENVIRONMENT_CANDIDATE_SHA = "60c3f44d847e0e183d763b5e02dab584a42c8d15ce08cebab4aa3020cec84427"
DEFINITION_CANDIDATE_SHA = "10a5e81f299ba5b2eae65e1f2a14ee323ba4b6f7072ab37767f3a926fba111f3"
YO_NOTE_SHA = "34ba06931c1947cd925d1ce1ec06eacca93c5c8cb3629da437eb4ecbc5d2ce91"
GATE1_AUDIT_SHA = "f08dfe99ad94bc47a66ac3302c3c483a810946e20551441c81291425228ad15e"
GATE1_MANIFEST_SHA = "ea7e160f9cea3be1db6487e87bab33d65dc5c2778906cfacaf59c6101deb25d5"
QUERY_SHA = "744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6"
JOIN_SHA = "12d811632a9c440e33fd76f814620c65e47113bdfda4ea058581b5e476c44050"
LEGACY_DEFINITION_SHA = "aa23b940d1e556df98cee5f332e8757f886ab098f468620fe084b93e90983513"
INVENTORY_SHA = "e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680"
CLAIMS_SHA = "1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a"
BASELINE_STATUS_SHA256 = "12978d379be277024c661c11e0a95d5ec6f7bdc0aedb1f6b3cbdf44f77b854c1"
BASELINE_STATUS_LINES = 61

ADOPTION_PATH = "docs/decisions/DECISION_stage2_gate1_ni_contracts_adoption_20260823.md"
REVIEW_PATH = "docs/reviews/incoming/EXTERNAL_REVIEW_stage2_gate1_n_insertion_contracts_claude_code_20260823.md"
SOURCE_REGISTRY_PATH = "config/candidate_sources/n_insertion_g1_g4_source_registry_v1_20260823.json"
CONTRACT_CANDIDATE_PATH = "config/phenomenon_contracts/n_insertion_contract_candidate_v1_20260823.json"
ENVIRONMENT_CANDIDATE_PATH = "config/environment_types/n_insertion_environment_types_candidate_v1_20260823.jsonl"
DEFINITION_CANDIDATE_PATH = "phenomena/34_n_insertion/definition_stage2_candidate_v1_20260823.md"
YO_NOTE_PATH = "docs/decisions/NOTE_n_insertion_yo_exploratory_query_candidate_20260823.md"
GATE1_AUDIT_PATH = "outputs/pilots/stage2_gate1_n_insertion_contracts_20260823/AUDIT_stage2_gate1_n_insertion_contracts_20260823.json"
GATE1_MANIFEST_PATH = "outputs/pilots/stage2_gate1_n_insertion_contracts_20260823/SHA256SUMS_stage2_gate1_n_insertion_contracts_20260823.txt"
QUERY_PATH = "config/target_queries/n_insertion_production_v1_20260818.json"
JOIN_PATH = "config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json"
LEGACY_DEFINITION_PATH = "phenomena/34_n_insertion/definition.md"
INVENTORY_PATH = "work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl"
CLAIMS_PATH = "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl"

FROZEN_CONTRACT_PATH = "config/phenomenon_contracts/n_insertion_contract_frozen_v1_20260823.json"
FROZEN_ENVIRONMENT_PATH = "config/environment_types/n_insertion_environment_types_frozen_v1_20260823.jsonl"
FROZEN_DEFINITION_PATH = "phenomena/34_n_insertion/definition_stage2_frozen_v1_20260823.md"
AUDITOR_PATH = "scripts/python/audit_stage2_gate1_ni_freeze_contracts.py"
TEST_PATH = "tests/test_audit_stage2_gate1_ni_freeze_contracts.py"
DECISIONS_INDEX_PATH = "docs/decisions/_INDEX.md"
SCRIPTS_INDEX_PATH = "scripts/SCRIPTS_INDEX.md"

DEFAULT_AUDIT_OUTPUT = "outputs/pilots/stage2_gate1_ni_freeze_20260823/AUDIT_stage2_gate1_ni_freeze_20260823.json"
DEFAULT_MANIFEST_OUTPUT = "outputs/pilots/stage2_gate1_ni_freeze_20260823/SHA256SUMS_stage2_gate1_ni_freeze_20260823.txt"

EXPECTED_INPUTS = {
    ADOPTION_PATH: ADOPTION_SHA,
    REVIEW_PATH: REVIEW_SHA,
    SOURCE_REGISTRY_PATH: SOURCE_REGISTRY_SHA,
    CONTRACT_CANDIDATE_PATH: CONTRACT_CANDIDATE_SHA,
    ENVIRONMENT_CANDIDATE_PATH: ENVIRONMENT_CANDIDATE_SHA,
    DEFINITION_CANDIDATE_PATH: DEFINITION_CANDIDATE_SHA,
    YO_NOTE_PATH: YO_NOTE_SHA,
    GATE1_AUDIT_PATH: GATE1_AUDIT_SHA,
    GATE1_MANIFEST_PATH: GATE1_MANIFEST_SHA,
    QUERY_PATH: QUERY_SHA,
    JOIN_PATH: JOIN_SHA,
    LEGACY_DEFINITION_PATH: LEGACY_DEFINITION_SHA,
    INVENTORY_PATH: INVENTORY_SHA,
    CLAIMS_PATH: CLAIMS_SHA,
}

TARGET_QUERY_FILES = {
    "db_v1_target_manifest_pilot_20260818.json": "94c9e6797e0ffd70f5092a009947208969fba4e328f53636a399a8ecaae120a1",
    "n_insertion_production_v1_20260818.json": QUERY_SHA,
    "pv_preview_boundary_20260819.json": "68d0b8cc0bc97019817d779341fa734324eea5467d80d92fa3f90726fa64f736",
}

ARTIFACT_PATHS = [
    FROZEN_CONTRACT_PATH,
    FROZEN_ENVIRONMENT_PATH,
    FROZEN_DEFINITION_PATH,
    AUDITOR_PATH,
    TEST_PATH,
]

EXPECTED_ENV_IDS = [
    "NI_ENV_CORE_C_J",
    "NI_ENV_CORE_C_I",
    "NI_ENV_SINO_RESONANT_J",
    "NI_ENV_SINO_OBSTRUENT_J",
    "NI_ENV_YO_JX",
    "NI_ENV_INTER_EOJEOL",
    "NI_ENV_UNCLEAR_BOUNDARY",
]
CONFIRMED_ENV_IDS = {"NI_ENV_CORE_C_J", "NI_ENV_CORE_C_I", "NI_ENV_YO_JX"}
SINO_PENDING_IDS = {"NI_ENV_SINO_RESONANT_J", "NI_ENV_SINO_OBSTRUENT_J"}
EXPECTED_HUMAN_CHECK = {"CLM-0008", "CLM-0015", "CLM-0026", "CLM-0145", "CLM-0151"}
SAFETY_FALSE = {
    "query_modified_or_refrozen": False,
    "occurrence_rows_rewritten": False,
    "automatic_realization_judgement": False,
    "formal_ledger_written": False,
    "g5_g6_started": False,
}

FREEZE_LOG_PATHS = {
    f"logs/stage2_gate1_ni_freeze_20260823/{name}"
    for name in (
        "00_preflight_gate.log",
        "01_py_compile.log",
        "02_unittest.log",
        "03_check_only.log",
        "04_audit_write.log",
        "05_existing_output_refusal.log",
        "06_final_verification.log",
        "07_post_check_only.log",
    )
}
ALLOWED_NEW_WORKTREE_PATHS = set(ARTIFACT_PATHS) | FREEZE_LOG_PATHS | {
    DEFAULT_AUDIT_OUTPUT,
    DEFAULT_MANIFEST_OUTPUT,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def status_digest(lines: list[str]) -> str:
    payload = ("\n".join(sorted(lines)) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def path_from_repo(repo_root: Path, relative: str) -> Path:
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise AssertionError(f"path escapes repository: {relative}") from exc
    return path


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"expected JSON object: {path}"
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        assert line.strip(), f"blank JSONL row {number}: {path}"
        value = json.loads(line)
        assert isinstance(value, dict), f"JSONL row is not object: {number}"
        rows.append(value)
    return rows


def validate_pinned_inputs(
    repo_root: Path, expected_inputs: dict[str, str] | None = None
) -> dict[str, str]:
    expected_inputs = EXPECTED_INPUTS if expected_inputs is None else expected_inputs
    measured: dict[str, str] = {}
    for relative, expected in expected_inputs.items():
        path = path_from_repo(repo_root, relative)
        assert path.is_file(), f"missing pinned input: {relative}"
        actual = sha256_file(path)
        assert actual == expected, f"pinned input SHA mismatch: {relative}"
        measured[relative] = actual
    return measured


def validate_literature(
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    inventory_rows = read_jsonl(path_from_repo(repo_root, INVENTORY_PATH))
    claim_rows = read_jsonl(path_from_repo(repo_root, CLAIMS_PATH))
    assert len(inventory_rows) == 362
    assert len(claim_rows) == 156
    for index, row in enumerate(inventory_rows, 1):
        assert row["source_id"] == f"SRC-{index:03d}"
    for index, row in enumerate(claim_rows, 1):
        assert row["claim_id"] == f"CLM-{index:04d}"
    sources = {row["source_id"]: row for row in inventory_rows}
    claims = {row["claim_id"]: row for row in claim_rows}
    binding_errors: list[str] = []
    for row in claim_rows:
        source = sources.get(row["source_id"])
        if source is None:
            binding_errors.append(f"{row['claim_id']}:source")
            continue
        if row["source_file"] != source["relative_path"]:
            binding_errors.append(f"{row['claim_id']}:file")
        if row["source_sha256"] != source["sha256"]:
            binding_errors.append(f"{row['claim_id']}:sha")
    assert not binding_errors, binding_errors[:5]
    human = {row["claim_id"] for row in claim_rows if row.get("needs_human_check") is True}
    assert human == EXPECTED_HUMAN_CHECK
    assert claims["CLM-0015"]["needs_human_check"] is True
    return sources, claims, {
        "inventory_rows": 362,
        "claim_rows": 156,
        "binding_errors": 0,
        "needs_human_check": sorted(human),
        "clm_0015_flag_preserved": True,
    }


def collect_and_validate_refs(value: Any, sources: dict[str, Any], claims: dict[str, Any]) -> set[str]:
    refs: set[str] = set()

    def walk(node: Any, key: str | None = None) -> None:
        if isinstance(node, dict):
            for child_key, child in node.items():
                walk(child, child_key)
        elif isinstance(node, list):
            if key is not None and key.endswith("evidence_refs"):
                for ref in node:
                    assert isinstance(ref, str)
                    refs.add(ref)
            else:
                for child in node:
                    walk(child, key)

    walk(value)
    for ref in refs:
        if ref.startswith("CLM-"):
            assert ref in claims, f"unknown CLM reference: {ref}"
        elif ref.startswith("SRC-"):
            assert ref in sources, f"unknown SRC reference: {ref}"
        elif ref.startswith("WANT-"):
            continue
        else:
            raise AssertionError(f"invalid evidence reference: {ref}")
    return refs


def validate_source_registry(repo_root: Path, registry: dict[str, Any]) -> dict[str, Any]:
    assert sha256_file(path_from_repo(repo_root, SOURCE_REGISTRY_PATH)) == SOURCE_REGISTRY_SHA
    assert [row["year"] for row in registry["years"]] == list(range(2020, 2026))
    candidate_total = joined_total = intra_total = inter_total = 0
    per_year: list[dict[str, Any]] = []
    for row in registry["years"]:
        year = row["year"]
        for key in ("build_manifest", "join_manifest", "audit"):
            item = row[key]
            path = path_from_repo(repo_root, item["path"])
            assert path.is_file()
            assert sha256_file(path) == item["sha256"], f"{key} SHA mismatch: {year}"
        build = read_json(path_from_repo(repo_root, row["build_manifest"]["path"]))
        join = read_json(path_from_repo(repo_root, row["join_manifest"]["path"]))
        audit = read_json(path_from_repo(repo_root, row["audit"]["path"]))
        candidate = int(build["counts"]["candidate_rows"])
        intra = int(build["query_counts"]["QN1_N_INSERTION_INTRA_EOJEOL_V1"])
        inter = int(build["query_counts"]["QN2_N_INSERTION_INTER_EOJEOL_V1"])
        joined = int(join["rows_out"])
        assert candidate == int(join["rows_in"]) == joined == int(audit["counts"]["joined_rows"])
        assert row["counts"]["candidate_rows"] == candidate
        assert row["counts"]["joined_rows"] == joined
        assert row["counts"]["intra_eojeol"] == intra
        assert row["counts"]["inter_eojeol"] == inter
        assert intra + inter == candidate
        assert join["safety"]["rows_dropped"] == 0
        assert join["safety"]["realization_judged"] is False
        assert build["safety"]["realization_judgement_performed"] is False
        assert audit["status"] == "passed" and not audit["failures"]
        candidate_total += candidate
        joined_total += joined
        intra_total += intra
        inter_total += inter
        per_year.append({"year": year, "candidate": candidate, "joined": joined})
    assert candidate_total == joined_total == 941903
    assert intra_total == 353626
    assert inter_total == 588277
    assert registry["totals"]["candidate_rows"] == candidate_total
    assert registry["totals"]["joined_rows"] == joined_total
    return {
        "per_year": per_year,
        "candidate_rows": candidate_total,
        "joined_rows": joined_total,
        "intra_eojeol": intra_total,
        "inter_eojeol": inter_total,
        "large_csv_rehash_or_scan": False,
        "new_occurrence_derivative_rows": 0,
    }


def validate_frozen_contract_dict(
    frozen: dict[str, Any], candidate: dict[str, Any], query: dict[str, Any],
    sources: dict[str, Any], claims: dict[str, Any]
) -> dict[str, Any]:
    assert frozen["contract_id"] == "n_insertion_contract_frozen_v1_20260823"
    assert frozen["contract_status"] == "frozen"
    assert frozen["status"] == "frozen_researcher_adopted_20260823"
    assert frozen["researcher"] == "ari30"
    confirmed_at = frozen["confirmed_at"]
    assert isinstance(confirmed_at, str) and confirmed_at.endswith("+09:00")
    assert frozen["supersedes"] == {"path": CONTRACT_CANDIDATE_PATH, "sha256": CONTRACT_CANDIDATE_SHA}
    assert frozen["adoption_decision"] == {"path": ADOPTION_PATH, "sha256": ADOPTION_SHA}
    assert frozen["source_registry_reference"] == {"path": SOURCE_REGISTRY_PATH, "sha256": SOURCE_REGISTRY_SHA}
    for key in (
        "query_contract", "include_conditions", "exclude_conditions", "retention_rules",
        "confound_phenomena", "membership_rules",
    ):
        assert frozen[key] == candidate[key], f"candidate semantic content changed: {key}"
    assert frozen["query_reference"] == candidate["query_reference"]
    assert frozen["join_reference"] == candidate["join_reference"]
    query_by_id = {row["query_id"]: row for row in query["queries"]}
    scopes = frozen["query_contract"]["scope_conditions"]
    common = frozen["query_contract"]["required_common_conditions"]
    assert len(common) == 6
    for query_id in frozen["query_reference"]["query_ids"]:
        assert query_by_id[query_id]["conditions"] == [scopes[query_id], *common]
    assert frozen["query_contract"]["left_pos_filter"] is None
    assert frozen["query_contract"]["new_occurrence_filter_added"] is False
    assert frozen["safety"] == SAFETY_FALSE
    frozen_unresolved = {row["item_id"]: row for row in frozen["unresolved_items"]}
    candidate_unresolved = {row["item_id"]: row for row in candidate["unresolved_items"]}
    assert set(frozen_unresolved) == set(candidate_unresolved)
    assert frozen_unresolved["NI_UNR_001"]["status"] == "deferred_by_decision_d_g1_a"
    assert frozen_unresolved["NI_UNR_001"]["decision_reference"] == {
        "path": ADOPTION_PATH, "sha256": ADOPTION_SHA, "section": "D-G1-A"
    }
    reason = frozen_unresolved["NI_UNR_001"]["defer_reason"]
    assert "Hwang 2007/2008" in reason and "원문 미보유·수배 중" in reason
    assert frozen_unresolved["NI_UNR_005"]["status"] == "resolved_by_adoption_20260823"
    assert frozen_unresolved["NI_UNR_005"]["decision_reference"] == {
        "path": ADOPTION_PATH, "sha256": ADOPTION_SHA, "section": "D-G1-B"
    }
    for item_id in ("NI_UNR_002", "NI_UNR_003", "NI_UNR_004"):
        assert frozen_unresolved[item_id] == candidate_unresolved[item_id]
    for item_id in ("NI_UNR_001", "NI_UNR_005"):
        for field in ("description", "evidence_refs"):
            assert frozen_unresolved[item_id][field] == candidate_unresolved[item_id][field]
    refs = collect_and_validate_refs(frozen, sources, claims)
    assert claims["CLM-0015"]["needs_human_check"] is True
    return {
        "status": frozen["status"],
        "researcher": frozen["researcher"],
        "confirmed_at": confirmed_at,
        "query_conditions": 7,
        "new_occurrence_filters": 0,
        "unresolved_items": len(frozen_unresolved),
        "clm_0015": "deferred_by_decision_d_g1_a",
        "evidence_refs": len(refs),
        "safety_false_items": 5,
    }


def validate_frozen_environment_rows(
    frozen_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]],
    sources: dict[str, Any], claims: dict[str, Any]
) -> dict[str, Any]:
    assert [row["environment_type_id"] for row in frozen_rows] == EXPECTED_ENV_IDS
    assert [row["environment_type_id"] for row in candidate_rows] == EXPECTED_ENV_IDS
    frozen_by_id = {row["environment_type_id"]: row for row in frozen_rows}
    candidate_by_id = {row["environment_type_id"]: row for row in candidate_rows}
    protected_fields = (
        "phenomenon_code", "environment_class", "class_evidence_refs", "priority_band",
        "description_ko", "occurrence_assignment_status",
    )
    for environment_id in EXPECTED_ENV_IDS:
        row = frozen_by_id[environment_id]
        candidate = candidate_by_id[environment_id]
        for field in protected_fields:
            assert row[field] == candidate[field], f"environment meaning changed: {environment_id}:{field}"
        assert row["occurrence_assignment_status"] == "not_started"
        assert row["supersedes"] == {
            "path": ENVIRONMENT_CANDIDATE_PATH,
            "sha256": ENVIRONMENT_CANDIDATE_SHA,
            "environment_type_id": environment_id,
        }
    for environment_id in CONFIRMED_ENV_IDS:
        row = frozen_by_id[environment_id]
        assert row["class_status"] == "researcher_confirmed"
        assert row["classified_by"] == "researcher_adoption_decision_20260823"
        assert row["classified_at"].endswith("+09:00")
    for environment_id in SINO_PENDING_IDS:
        row = frozen_by_id[environment_id]
        assert row["class_status"] == "pending", "silent Sino-Korean promotion"
        assert "CLM-0015 deferred by DECISION_stage2_gate1_ni_contracts_adoption_20260823.md §D-G1-A" in row["pending_reason"]
        assert "Hwang 원전 입수 후 해소" in row["pending_reason"]
    inter = frozen_by_id["NI_ENV_INTER_EOJEOL"]
    assert inter["environment_class"] is None and inter["class_status"] == "pending"
    assert frozen_by_id["NI_ENV_UNCLEAR_BOUNDARY"]["class_status"] == "pending"
    yo = frozen_by_id["NI_ENV_YO_JX"]
    assert yo["decision_status"] == "treatment_decided_query_not_created"
    refs = collect_and_validate_refs(frozen_rows, sources, claims)
    assert "CLM-0015" in refs and claims["CLM-0015"]["needs_human_check"] is True
    return {
        "rows": 7,
        "ids_preserved": True,
        "researcher_confirmed": sorted(CONFIRMED_ENV_IDS),
        "sino_pending": sorted(SINO_PENDING_IDS),
        "inter_eojeol": "null_pending_deferred",
        "unclear_boundary": "pending",
        "occurrence_assignment_rows": 0,
        "yo_treatment": "decided_query_not_created",
        "evidence_refs": len(refs),
    }


def validate_frozen_definition(repo_root: Path) -> dict[str, Any]:
    text = path_from_repo(repo_root, FROZEN_DEFINITION_PATH).read_text(encoding="utf-8")
    markers = (
        "definition_status: `researcher_confirmed`",
        "lifecycle_status: `frozen_v1_adopted_20260823`",
        "CLM-0015",
        "needs_human_check=true",
        "class_status=pending",
        "treatment_decided_query_not_created",
        "environment_class=null",
        "G5/G6",
        "TextGrid 수정",
        "자동 실현 판정",
        "정식 ledger",
    )
    for marker in markers:
        assert marker in text, f"frozen definition marker missing: {marker}"
    assert "definition_status: `researcher_confirmed_frozen" not in text
    return {"definition_status": "researcher_confirmed", "lifecycle_status": "frozen_v1_adopted_20260823"}


def validate_yo_absence(repo_root: Path) -> dict[str, Any]:
    query_root = path_from_repo(repo_root, "config/target_queries")
    actual = {path.name: sha256_file(path) for path in query_root.iterdir() if path.is_file()}
    assert actual == TARGET_QUERY_FILES, "config/target_queries file set or SHA changed"
    candidates_root = path_from_repo(repo_root, "outputs/candidates")
    yo_candidate_files = [
        path for path in candidates_root.rglob("*")
        if path.is_file() and "n_insertion" in str(path).lower()
        and ("yo" in str(path).lower() or "요" in str(path))
    ]
    assert not yo_candidate_files, f"unexpected 요 candidate output: {yo_candidate_files[:3]}"
    return {"target_query_files": 3, "yo_query_json": False, "yo_candidate_csv": False}


def validate_indexes(repo_root: Path) -> dict[str, Any]:
    decisions = path_from_repo(repo_root, DECISIONS_INDEX_PATH).read_text(encoding="utf-8")
    scripts = path_from_repo(repo_root, SCRIPTS_INDEX_PATH).read_text(encoding="utf-8")
    assert "DECISION_stage2_gate1_ni_contracts_adoption_20260823.md" in decisions
    assert "NOTE_n_insertion_yo_exploratory_query_candidate_20260823.md" in decisions
    assert "audit_stage2_gate1_n_insertion_contracts.py" in scripts
    assert "audit_stage2_gate1_ni_freeze_contracts.py" in scripts
    return {"decisions_index": True, "scripts_index": True}


def validate_artifacts(repo_root: Path) -> dict[str, str]:
    measured: dict[str, str] = {}
    for relative in ARTIFACT_PATHS:
        path = path_from_repo(repo_root, relative)
        assert path.is_file(), f"missing frozen artifact: {relative}"
        assert not path.with_name(path.name + ".partial").exists(), f"partial remains: {relative}"
        measured[relative] = sha256_file(path)
    partials = [path for path in repo_root.rglob("*.partial") if "stage2_gate1_ni_freeze" in str(path) or "n_insertion_" in path.name]
    assert not partials, f"freeze partial remains: {partials[:3]}"
    return measured


def validate_worktree(repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    actual = result.stdout.splitlines()
    tracked = sorted(line for line in actual if not line.startswith("??"))
    assert tracked == [" M docs/decisions/_INDEX.md", " M scripts/SCRIPTS_INDEX.md"]
    allowed_status = {f"?? {path}" for path in ALLOWED_NEW_WORKTREE_PATHS}
    baseline = [line for line in actual if line not in allowed_status]
    unexpected_allowed_prefix = [
        line for line in actual
        if ("stage2_gate1_ni_freeze_20260823" in line or "n_insertion_contract_frozen_v1" in line
            or "n_insertion_environment_types_frozen_v1" in line or "definition_stage2_frozen_v1" in line)
        and line not in allowed_status
    ]
    assert not unexpected_allowed_prefix, f"unexpected freeze worktree path: {unexpected_allowed_prefix}"
    assert len(baseline) == BASELINE_STATUS_LINES
    assert status_digest(baseline) == BASELINE_STATUS_SHA256, "worktree changed outside freeze allowlist"
    return {
        "baseline_status_lines": len(baseline),
        "baseline_status_sha256": status_digest(baseline),
        "tracked_changes": tracked,
        "allowed_freeze_status_lines_present": sorted(line for line in actual if line in allowed_status),
        "unexpected": [],
    }


def audit_repo(repo_root: Path, *, check_git: bool = True) -> dict[str, Any]:
    pinned = validate_pinned_inputs(repo_root)
    sources, claims, literature = validate_literature(repo_root)
    registry = read_json(path_from_repo(repo_root, SOURCE_REGISTRY_PATH))
    zero_drop = validate_source_registry(repo_root, registry)
    candidate_contract = read_json(path_from_repo(repo_root, CONTRACT_CANDIDATE_PATH))
    frozen_contract = read_json(path_from_repo(repo_root, FROZEN_CONTRACT_PATH))
    query = read_json(path_from_repo(repo_root, QUERY_PATH))
    contract = validate_frozen_contract_dict(frozen_contract, candidate_contract, query, sources, claims)
    candidate_environment = read_jsonl(path_from_repo(repo_root, ENVIRONMENT_CANDIDATE_PATH))
    frozen_environment = read_jsonl(path_from_repo(repo_root, FROZEN_ENVIRONMENT_PATH))
    environment = validate_frozen_environment_rows(
        frozen_environment, candidate_environment, sources, claims
    )
    definition = validate_frozen_definition(repo_root)
    yo_absence = validate_yo_absence(repo_root)
    indexes = validate_indexes(repo_root)
    artifacts = validate_artifacts(repo_root)
    worktree = validate_worktree(repo_root) if check_git else {"skipped": True}
    return {
        "schema_version": "stage2_gate1_ni_freeze_audit.v1",
        "status": "passed_frozen_v1_researcher_adopted_stopped_before_research",
        "passed": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "phenomenon_code": "NI",
            "frozen_v1_created": True,
            "g5_g6_started": False,
            "yo_query_json_created": False,
            "occurrence_derivative_created": False,
            "automatic_realization_judgement": False,
            "textgrid_modified": False,
            "formal_ledger_written": False,
            "mfa_koina_wav2vec2_run": False,
            "probe_regression_d_g1_c_started": False,
        },
        "pinned_inputs": pinned,
        "literature": literature,
        "zero_drop": zero_drop,
        "contract": contract,
        "environment_types": environment,
        "definition": definition,
        "yo_absence": yo_absence,
        "indexes": indexes,
        "artifact_sha256": artifacts,
        "worktree": worktree,
        "checks": [
            "all_candidate_and_protected_sha_pins",
            "query_contract_exact_seven_conditions",
            "candidate_semantics_preserved",
            "adoption_and_supersedes_sha_bindings",
            "clm_0015_true_and_explicitly_deferred",
            "environment_seven_rows_and_no_silent_promotion",
            "zero_drop_941903_via_manifests_without_csv_scan",
            "yo_query_and_candidate_absent",
            "only_two_tracked_index_changes",
            "baseline_plus_exact_freeze_allowlist",
            "no_partial_and_manifest_self_exclusion",
        ],
    }


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_manifest_lines(
    repo_root: Path, audit_relative: str, audit_payload: bytes, manifest_relative: str
) -> list[str]:
    assert manifest_relative not in ARTIFACT_PATHS
    lines = [f"{sha256_file(path_from_repo(repo_root, relative))}  {relative}" for relative in ARTIFACT_PATHS]
    lines.append(f"{hashlib.sha256(audit_payload).hexdigest()}  {audit_relative}")
    assert all(manifest_relative not in line for line in lines)
    return sorted(lines, key=lambda line: line.split("  ", 1)[1])


def ensure_outputs_absent(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")
        partial = path.with_name(path.name + ".partial")
        if partial.exists():
            raise FileExistsError(f"refusing to overwrite existing partial: {partial}")


def atomic_write_pair(audit_path: Path, audit_payload: bytes, manifest_path: Path, manifest_payload: bytes) -> None:
    ensure_outputs_absent([audit_path, manifest_path])
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    audit_partial = audit_path.with_name(audit_path.name + ".partial")
    manifest_partial = manifest_path.with_name(manifest_path.name + ".partial")
    with audit_partial.open("xb") as handle:
        handle.write(audit_payload)
        handle.flush()
        os.fsync(handle.fileno())
    with manifest_partial.open("xb") as handle:
        handle.write(manifest_payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(audit_partial, audit_path)
    os.replace(manifest_partial, manifest_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the adopted Stage 2 Gate 1 NI frozen contracts")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--audit-output", default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--manifest-output", default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--skip-git-check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report = audit_repo(repo_root, check_git=not args.skip_git_check)
    if args.check_only:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    audit_path = path_from_repo(repo_root, args.audit_output)
    manifest_path = path_from_repo(repo_root, args.manifest_output)
    audit_payload = json_bytes(report)
    manifest_lines = build_manifest_lines(repo_root, args.audit_output, audit_payload, args.manifest_output)
    manifest_payload = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    atomic_write_pair(audit_path, audit_payload, manifest_path, manifest_payload)
    print(f"passed=true audit={audit_path} manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
