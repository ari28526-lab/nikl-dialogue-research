#!/usr/bin/env python3
"""Audit Stage 2 Gate 1 NI contract candidates without scanning the full corpus."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


sys.stdout.reconfigure(encoding="utf-8")


QUERY_SHA = "744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6"
JOIN_SHA = "12d811632a9c440e33fd76f814620c65e47113bdfda4ea058581b5e476c44050"
EXPECTED_INPUTS = {
    "config/target_queries/n_insertion_production_v1_20260818.json": QUERY_SHA,
    "config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json": JOIN_SHA,
    "config/phenomena_registry.v1.json": "4f652d6422d2e61c3263263224eeb29e9a90c14f4fd8ba2ba66a46e27a98705e",
    "config/stage2_environment_class_enum.v1.json": "871193eda6b1b69f7c2b5c16edbe63904759f4bda769a4629ed2f3f3ce358062",
    "config/stage2_inclusion_exclusion_confound_contract_template.v1.json": "61f78353e521e8a3dbd2181841e98f03580fc3b62d35fd41d1174c156591d7ac",
    "phenomena/34_n_insertion/definition.md": "aa23b940d1e556df98cee5f332e8757f886ab098f468620fe084b93e90983513",
    "docs/decisions/DECISION_stage2_gate0_common_contracts_adoption_20260823.md": "2f5d2c570d5782f750562e55193132c102180462e30cd3758b41ac6c059e9b17",
    "docs/decisions/PLAN_stage2_gate1_NI_reference_implementation_20260823.md": "8e55bab353d65c063c579c0538dbe26aae820a6ebcf25d23e407236ebe5dce66",
    "work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl": "e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680",
    "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl": "1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a",
}

SOURCE_REGISTRY_PATH = "config/candidate_sources/n_insertion_g1_g4_source_registry_v1_20260823.json"
CONTRACT_PATH = "config/phenomenon_contracts/n_insertion_contract_candidate_v1_20260823.json"
ENVIRONMENT_PATH = "config/environment_types/n_insertion_environment_types_candidate_v1_20260823.jsonl"
DEFINITION_PATH = "phenomena/34_n_insertion/definition_stage2_candidate_v1_20260823.md"
YO_NOTE_PATH = "docs/decisions/NOTE_n_insertion_yo_exploratory_query_candidate_20260823.md"
AUDITOR_PATH = "scripts/python/audit_stage2_gate1_n_insertion_contracts.py"
TEST_PATH = "tests/test_audit_stage2_gate1_n_insertion_contracts.py"

ARTIFACT_PATHS = [
    SOURCE_REGISTRY_PATH,
    CONTRACT_PATH,
    ENVIRONMENT_PATH,
    DEFINITION_PATH,
    YO_NOTE_PATH,
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

EXPECTED_HUMAN_CHECK = {
    "CLM-0008",
    "CLM-0015",
    "CLM-0026",
    "CLM-0145",
    "CLM-0151",
}

PRE_IMPLEMENTATION_STATUS = {
    " M docs/decisions/_INDEX.md",
    " M scripts/SCRIPTS_INDEX.md",
    "?? config/phenomena_registry.v1.json",
    "?? config/stage2_additional_information_sidecar_schema.v1.json",
    "?? config/stage2_environment_class_enum.v1.json",
    "?? config/stage2_inclusion_exclusion_confound_contract_template.v1.json",
    "?? config/stage2_zero_drop_status_dictionary.v1.json",
    "?? docs/decisions/DECISION_stage2_gate0_common_contracts_adoption_20260823.md",
    "?? docs/decisions/DECISION_stage2_seven_phenomena_workflow_user_decisions_20260823.md",
    "?? docs/decisions/HANDOFF_stage2_gate0_implementation_prompt_20260823.md",
    "?? docs/decisions/HANDOFF_stage2_gate0_implementation_prompt_v2_20260823.md",
    "?? docs/decisions/PLAN_stage2_gate1_NI_reference_implementation_20260823.html",
    "?? docs/decisions/PLAN_stage2_gate1_NI_reference_implementation_20260823.md",
    "?? docs/decisions/SCHEMA_stage2_gate0_common_contracts_20260823.md",
    "?? docs/reviews/incoming/EXTERNAL_REVIEW_stage2_gate0_common_contracts_claude_code_20260823.html",
    "?? docs/reviews/incoming/EXTERNAL_REVIEW_stage2_gate0_common_contracts_claude_code_20260823.md",
    "?? docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.html",
    "?? docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md",
    "?? docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.html",
    "?? docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json",
    "?? docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.md",
    "?? docs/reviews/incoming/_to_delete/",
    "?? logs/stage2_gate0_common_contracts_20260823/",
    "?? outputs/pilots/stage2_gate0_common_contracts_20260823/",
    "?? phenomena/_draft/",
    "?? phenomena/_templates/",
    "?? scripts/python/audit_stage2_gate0_common_contracts.py",
    "?? tests/test_audit_stage2_gate0_common_contracts.py",
}

GATE1_STATUS = {
    "?? config/candidate_sources/",
    "?? config/environment_types/",
    "?? config/phenomenon_contracts/",
    f"?? {YO_NOTE_PATH}",
    f"?? {DEFINITION_PATH}",
    "?? logs/stage2_gate1_n_insertion_contracts_20260823/",
    "?? outputs/pilots/stage2_gate1_n_insertion_contracts_20260823/",
    f"?? {AUDITOR_PATH}",
    f"?? {TEST_PATH}",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        assert isinstance(value, dict), f"row {number} is not an object: {path}"
        rows.append(value)
    return rows


def normalized_header(path: Path, *, gzipped: bool = False) -> tuple[list[str], str]:
    opener = gzip.open if gzipped else Path.open
    if gzipped:
        with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))
    else:
        with opener(path, "r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))
    digest = hashlib.sha256(",".join(header).encode("utf-8")).hexdigest()
    return header, digest


def validate_expected_inputs(repo_root: Path) -> dict[str, str]:
    measured: dict[str, str] = {}
    for relative, expected in EXPECTED_INPUTS.items():
        path = path_from_repo(repo_root, relative)
        assert path.is_file(), f"missing protected input: {relative}"
        actual = sha256_file(path)
        assert actual == expected, f"protected input SHA mismatch: {relative}"
        measured[relative] = actual
    return measured


def validate_literature(repo_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    inventory_path = path_from_repo(
        repo_root,
        "work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl",
    )
    claims_path = path_from_repo(
        repo_root,
        "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl",
    )
    inventory_rows = read_jsonl(inventory_path)
    claim_rows = read_jsonl(claims_path)
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
            binding_errors.append(f"{row['claim_id']}:missing source")
            continue
        if row["source_file"] != source["relative_path"]:
            binding_errors.append(f"{row['claim_id']}:source_file")
        if row["source_sha256"] != source["sha256"]:
            binding_errors.append(f"{row['claim_id']}:source_sha256")
    assert not binding_errors, binding_errors[:5]
    human = {row["claim_id"] for row in claim_rows if row.get("needs_human_check") is True}
    assert human == EXPECTED_HUMAN_CHECK
    return sources, claims, {
        "inventory_rows": len(inventory_rows),
        "claim_rows": len(claim_rows),
        "source_binding_errors": len(binding_errors),
        "needs_human_check": sorted(human),
    }


def validate_refs(value: Any, sources: dict[str, Any], claims: dict[str, Any]) -> set[str]:
    refs: set[str] = set()

    def walk(node: Any, key: str | None = None) -> None:
        if isinstance(node, dict):
            for child_key, child in node.items():
                walk(child, child_key)
        elif isinstance(node, list):
            if key is not None and key.endswith("evidence_refs"):
                for ref in node:
                    assert isinstance(ref, str), f"non-string evidence ref: {ref!r}"
                    refs.add(ref)
            else:
                for child in node:
                    walk(child, key)

    walk(value)
    for ref in refs:
        if ref.startswith("CLM-"):
            assert ref in claims, f"unknown claim ref: {ref}"
        elif ref.startswith("SRC-"):
            assert ref in sources, f"unknown source ref: {ref}"
        elif ref.startswith("WANT-"):
            continue
        else:
            raise AssertionError(f"invalid evidence ref format: {ref}")
    return refs


def validate_source_registry_dict(registry: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    required = {
        "schema_version",
        "registry_id",
        "status",
        "phenomenon_code",
        "bound_query",
        "bound_join_contract",
        "header_contracts",
        "years",
        "totals",
        "verification_policy",
        "invariants",
    }
    assert required <= registry.keys(), f"source registry missing: {sorted(required - registry.keys())}"
    assert registry["phenomenon_code"] == "NI"
    assert registry["bound_query"]["sha256"] == QUERY_SHA
    assert registry["bound_join_contract"]["sha256"] == JOIN_SHA
    assert [row["year"] for row in registry["years"]] == list(range(2020, 2026))
    header_contracts = registry["header_contracts"]
    total_candidate = 0
    total_joined = 0
    total_intra = 0
    total_inter = 0
    measured_headers: dict[str, set[str]] = {"target": set(), "joined": set()}
    for row in registry["years"]:
        year = row["year"]
        stage = "g3" if year == 2020 else "g4"
        assert row["stage"] == stage
        for key in ("build_manifest", "join_manifest", "audit"):
            item = row[key]
            path = path_from_repo(repo_root, item["path"])
            assert path.is_file(), f"missing {key}: {item['path']}"
            assert sha256_file(path) == item["sha256"], f"{key} SHA mismatch: {year}"
        build = read_json(path_from_repo(repo_root, row["build_manifest"]["path"]))
        join = read_json(path_from_repo(repo_root, row["join_manifest"]["path"]))
        audit = read_json(path_from_repo(repo_root, row["audit"]["path"]))
        assert build["query_set_sha256"] == QUERY_SHA
        assert join["bound_query_set_sha256"] == QUERY_SHA
        assert join["contract_sha256"] == JOIN_SHA
        assert audit["frozen_query_sha256"] == QUERY_SHA
        assert audit["status"] == row["audit"]["status"] == "passed"
        counts = row["counts"]
        assert counts["candidate_rows"] == build["counts"]["candidate_rows"]
        assert counts["candidate_utterances"] == build["counts"]["candidate_utterances"]
        assert counts["intra_eojeol"] == build["query_counts"]["QN1_N_INSERTION_INTRA_EOJEOL_V1"]
        assert counts["inter_eojeol"] == build["query_counts"]["QN2_N_INSERTION_INTER_EOJEOL_V1"]
        assert counts["candidate_rows"] == join["rows_in"] == join["rows_out"]
        assert counts["joined_rows"] == audit["counts"]["joined_rows"] == join["rows_out"]
        assert not audit["failures"]
        assert join["safety"]["rows_dropped"] == 0
        assert join["safety"]["realization_judged"] is False
        assert build["safety"]["realization_judgement_performed"] is False
        target = path_from_repo(repo_root, row["target_candidates"]["path"])
        joined = path_from_repo(repo_root, row["joined_candidates"]["path"])
        source = Path(row["source_morph_boundaries"]["path"])
        assert target.is_file() and target.stat().st_size == row["target_candidates"]["bytes"]
        assert joined.is_file() and joined.stat().st_size == row["joined_candidates"]["bytes"]
        assert source.is_file() and source.stat().st_size == row["source_morph_boundaries"]["bytes"]
        manifest_target = next(item for item in build["files"] if item["path"] == "TARGET_CANDIDATES.csv")
        assert manifest_target["sha256"] == row["target_candidates"]["declared_sha256"]
        assert join["output"]["sha256"] == row["joined_candidates"]["declared_sha256"]
        assert build["sources"][0]["declared_sha256"] == row["source_morph_boundaries"]["declared_sha256"]
        target_header, target_sha = normalized_header(target)
        joined_header, joined_sha = normalized_header(joined)
        assert len(target_header) == header_contracts["target_candidates_all_years"]["columns"]
        assert len(joined_header) == header_contracts["joined_candidates_all_years"]["columns"]
        assert target_sha == header_contracts["target_candidates_all_years"]["normalized_header_sha256"]
        assert joined_sha == header_contracts["joined_candidates_all_years"]["normalized_header_sha256"]
        assert set(header_contracts["required_occurrence_fields"]) <= set(target_header)
        measured_headers["target"].add(target_sha)
        measured_headers["joined"].add(joined_sha)
        total_candidate += counts["candidate_rows"]
        total_joined += counts["joined_rows"]
        total_intra += counts["intra_eojeol"]
        total_inter += counts["inter_eojeol"]
    source_header, source_header_sha = normalized_header(
        Path(registry["years"][0]["source_morph_boundaries"]["path"]), gzipped=True
    )
    assert len(source_header) == header_contracts["source_morph_boundaries_2020"]["columns"]
    assert source_header_sha == header_contracts["source_morph_boundaries_2020"]["normalized_header_sha256"]
    assert len(measured_headers["target"]) == len(measured_headers["joined"]) == 1
    totals = registry["totals"]
    assert total_candidate == total_joined == totals["candidate_rows"] == totals["joined_rows"] == 941903
    assert total_intra == totals["intra_eojeol"] == 353626
    assert total_inter == totals["inter_eojeol"] == 588277
    assert total_intra + total_inter == total_candidate
    assert registry["verification_policy"]["max_occurrences_for_structural_probe"] == 200000
    assert registry["verification_policy"]["realization_judgement"] is False
    return {
        "years": 6,
        "candidate_rows": total_candidate,
        "joined_rows": total_joined,
        "intra_eojeol": total_intra,
        "inter_eojeol": total_inter,
        "target_columns": 34,
        "joined_columns": 73,
        "source_columns": 35,
        "full_csv_rehash_or_scan": False,
    }


def validate_contract_dict(
    contract: dict[str, Any], query: dict[str, Any], sources: dict[str, Any], claims: dict[str, Any]
) -> dict[str, Any]:
    required = {
        "schema_version",
        "contract_id",
        "phenomenon_code",
        "contract_version",
        "contract_status",
        "status",
        "query_reference",
        "query_contract",
        "include_conditions",
        "exclude_conditions",
        "confound_phenomena",
        "membership_rules",
        "unresolved_items",
        "safety",
    }
    assert required <= contract.keys(), f"contract missing: {sorted(required - contract.keys())}"
    assert contract["phenomenon_code"] == "NI"
    assert contract["contract_status"] == "draft"
    assert contract["query_reference"]["sha256"] == QUERY_SHA
    assert contract["researcher"] is None and contract["confirmed_at"] is None
    query_by_id = {row["query_id"]: row for row in query["queries"]}
    assert set(query_by_id) == set(contract["query_reference"]["query_ids"])
    scopes = contract["query_contract"]["scope_conditions"]
    common = contract["query_contract"]["required_common_conditions"]
    for query_id, row in query_by_id.items():
        assert row["conditions"] == [scopes[query_id], *common], f"contract/query condition mismatch: {query_id}"
    assert contract["query_contract"]["left_pos_filter"] is None
    assert contract["query_contract"]["new_occurrence_filter_added"] is False
    assert len(contract["include_conditions"]) == 4
    assert len(contract["exclude_conditions"]) == 3
    assert len(contract["confound_phenomena"]) == 5
    assert len(contract["membership_rules"]) == 3
    assert len(contract["unresolved_items"]) == 5
    unresolved = {row["item_id"]: row for row in contract["unresolved_items"]}
    assert unresolved["NI_UNR_001"]["evidence_refs"] == ["CLM-0015"]
    assert unresolved["NI_UNR_001"]["status"] == "needs_human_check_before_freeze"
    yo = next(row for row in contract["membership_rules"] if row["rule_id"] == "NI_MEM_03_YO_SEPARATE")
    assert yo["evidence_refs"] == ["CLM-0002"]
    assert contract["safety"] == {
        "query_modified_or_refrozen": False,
        "occurrence_rows_rewritten": False,
        "automatic_realization_judgement": False,
        "formal_ledger_written": False,
        "g5_g6_started": False,
    }
    refs = validate_refs(contract, sources, claims)
    return {
        "contract_status": contract["contract_status"],
        "include_conditions": len(contract["include_conditions"]),
        "exclude_conditions": len(contract["exclude_conditions"]),
        "confounds": len(contract["confound_phenomena"]),
        "membership_rules": len(contract["membership_rules"]),
        "unresolved_items": len(contract["unresolved_items"]),
        "evidence_refs": len(refs),
        "query_condition_mismatches": 0,
    }


def validate_environment_rows(
    rows: list[dict[str, Any]], enum: dict[str, Any], sources: dict[str, Any], claims: dict[str, Any]
) -> dict[str, Any]:
    assert [row["environment_type_id"] for row in rows] == EXPECTED_ENV_IDS
    required = set(enum["required_assignment_fields"])
    allowed_classes = {row["value"] for row in enum["environment_class"]}
    allowed_status = set(enum["class_status"])
    for row in rows:
        assert required <= row.keys(), f"environment row missing fields: {row.get('environment_type_id')}"
        assert row["phenomenon_code"] == "NI"
        assert row["class_status"] in allowed_status
        if row["environment_class"] is None:
            assert row["class_status"] == "pending"
        else:
            assert row["environment_class"] in allowed_classes
        assert row["occurrence_assignment_status"] == "not_started"
        if not row["class_evidence_refs"]:
            assert row["class_status"] == "pending"
    validate_refs(rows, sources, claims)
    by_id = {row["environment_type_id"]: row for row in rows}
    assert by_id["NI_ENV_CORE_C_J"]["environment_class"] == "general_direct"
    assert by_id["NI_ENV_CORE_C_J"]["priority_band"] == "core"
    assert by_id["NI_ENV_YO_JX"]["environment_class"] == "theoretical_underreported"
    assert by_id["NI_ENV_YO_JX"]["decision_status"] == "treatment_decided_query_not_created"
    assert by_id["NI_ENV_INTER_EOJEOL"]["environment_class"] is None
    assert by_id["NI_ENV_INTER_EOJEOL"]["class_status"] == "pending"
    for env_id in ("NI_ENV_SINO_RESONANT_J", "NI_ENV_SINO_OBSTRUENT_J"):
        assert by_id[env_id]["class_status"] == "pending"
        assert "CLM-0015" in by_id[env_id]["class_evidence_refs"]
    assert not any(row["class_status"] == "researcher_confirmed" for row in rows)
    return {
        "rows": len(rows),
        "occurrence_assignment_rows": 0,
        "seeded": sum(row["class_status"] == "seeded" for row in rows),
        "pending": sum(row["class_status"] == "pending" for row in rows),
        "researcher_confirmed": 0,
        "inter_eojeol_review": "deferred",
        "yo_treatment": "decided_query_not_created",
    }


def validate_documents(repo_root: Path) -> dict[str, Any]:
    definition = path_from_repo(repo_root, DEFINITION_PATH).read_text(encoding="utf-8")
    yo_note = path_from_repo(repo_root, YO_NOTE_PATH).read_text(encoding="utf-8")
    for marker in (
        "candidate_pending_researcher_confirmation",
        "CLM-0001~CLM-0026",
        "941,903",
        "어절 간",
        "G5/G6",
    ):
        assert marker in definition, f"definition marker missing: {marker}"
    for marker in (
        "treatment_decided_query_not_created",
        "CLM-0002",
        "query JSON·후보 CSV를 만들지",
        "별도 zero-drop",
    ):
        assert marker in yo_note, f"yo note marker missing: {marker}"
    assert "researcher_confirmed`" not in definition.split("## 1. 현상", 1)[0]
    return {"definition_candidate": True, "yo_candidate_document": True, "query_json_created": False}


def validate_artifacts(repo_root: Path) -> dict[str, str]:
    measured: dict[str, str] = {}
    for relative in ARTIFACT_PATHS:
        path = path_from_repo(repo_root, relative)
        assert path.is_file(), f"missing Gate 1 artifact: {relative}"
        partial = path.with_name(path.name + ".partial")
        assert not partial.exists(), f"Gate 1 partial remains: {partial}"
        measured[relative] = sha256_file(path)
    return measured


def validate_worktree(repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    actual = set(result.stdout.splitlines())
    allowed = PRE_IMPLEMENTATION_STATUS | GATE1_STATUS
    unexpected = sorted(actual - allowed)
    missing_baseline = sorted(PRE_IMPLEMENTATION_STATUS - actual)
    assert not unexpected, f"unexpected worktree paths: {unexpected}"
    assert not missing_baseline, f"pre-implementation worktree changed: {missing_baseline}"
    return {
        "status_lines": sorted(actual),
        "unexpected": unexpected,
        "missing_baseline": missing_baseline,
        "tracked_changes": sorted(line for line in actual if not line.startswith("??")),
    }


def audit_repo(repo_root: Path, *, check_git: bool = True) -> dict[str, Any]:
    protected = validate_expected_inputs(repo_root)
    sources, claims, literature = validate_literature(repo_root)
    registry = read_json(path_from_repo(repo_root, SOURCE_REGISTRY_PATH))
    registry_report = validate_source_registry_dict(registry, repo_root)
    query = read_json(path_from_repo(repo_root, registry["bound_query"]["path"]))
    contract = read_json(path_from_repo(repo_root, CONTRACT_PATH))
    contract_report = validate_contract_dict(contract, query, sources, claims)
    enum = read_json(path_from_repo(repo_root, "config/stage2_environment_class_enum.v1.json"))
    environment_rows = read_jsonl(path_from_repo(repo_root, ENVIRONMENT_PATH))
    environment_report = validate_environment_rows(environment_rows, enum, sources, claims)
    documents = validate_documents(repo_root)
    artifacts = validate_artifacts(repo_root)
    worktree = validate_worktree(repo_root) if check_git else {"skipped": True}
    return {
        "schema_version": "stage2_gate1_n_insertion_contracts_audit.v1",
        "status": "passed_candidate_pending_researcher_confirmation",
        "passed": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "gate": 1,
            "phenomenon_code": "NI",
            "source_registry_only_no_occurrence_derivative": True,
            "query_modified_or_refrozen": False,
            "yo_query_json_created": False,
            "g5_g6_started": False,
            "textgrid_modified": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "mfa_koina_wav2vec2_run": False,
        },
        "protected_inputs": protected,
        "literature": literature,
        "source_registry": registry_report,
        "contract": contract_report,
        "environment_types": environment_report,
        "documents": documents,
        "artifact_sha256": artifacts,
        "worktree": worktree,
        "checks": [
            "protected_input_sha_match",
            "literature_ids_bindings_and_human_checks",
            "six_year_manifest_audit_count_bindings",
            "actual_35_34_73_column_headers",
            "query_contract_exact_condition_match",
            "environment_refs_or_pending",
            "yo_decision_complete_query_not_created",
            "zero_drop_941903",
            "no_gate1_partial",
            "git_baseline_plus_allowlist",
        ],
    }


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_manifest_lines(
    repo_root: Path, audit_relative: str, audit_payload: bytes, manifest_relative: str
) -> list[str]:
    assert manifest_relative not in ARTIFACT_PATHS
    lines = [f"{sha256_file(path_from_repo(repo_root, rel))}  {rel}" for rel in sorted(ARTIFACT_PATHS)]
    audit_sha = hashlib.sha256(audit_payload).hexdigest()
    lines.append(f"{audit_sha}  {audit_relative}")
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
    parser = argparse.ArgumentParser(description="Audit Stage 2 Gate 1 NI candidate contracts")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--audit-output",
        default="outputs/pilots/stage2_gate1_n_insertion_contracts_20260823/AUDIT_stage2_gate1_n_insertion_contracts_20260823.json",
    )
    parser.add_argument(
        "--manifest-output",
        default="outputs/pilots/stage2_gate1_n_insertion_contracts_20260823/SHA256SUMS_stage2_gate1_n_insertion_contracts_20260823.txt",
    )
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
