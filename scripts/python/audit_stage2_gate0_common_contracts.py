from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.stdout.reconfigure(encoding="utf-8")


class ContractError(RuntimeError):
    pass


EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
EXPECTED_HUMAN_CHECK = {
    "CLM-0008",
    "CLM-0015",
    "CLM-0026",
    "CLM-0145",
    "CLM-0151",
}
EXPECTED_PROSODY_SOURCE_ONLY = {"SRC-360", "SRC-361", "SRC-362", "SRC-356"}
EXPECTED_ENVIRONMENT_CLASSES = [
    "general_direct",
    "peripheral_reported",
    "theoretical_underreported",
    "unclear_boundary",
]
EXPECTED_AXES = {
    "textgrid_review_need": ["not_needed", "required", "unsure"],
    "textgrid_asset_status": ["available", "unavailable", "blocked"],
    "manual_task_status": ["not_created", "queued", "exported", "returned", "audited"],
}
EXPECTED_INPUTS = {
    "docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json":
        "938353d719e1ddc57c8ba96ca4694310f6570a4b4ca944f684a5a66961bdebae",
    "work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl":
        "e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680",
    "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl":
        "1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a",
    "config/target_queries/n_insertion_production_v1_20260818.json":
        "744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6",
    "phenomena/34_n_insertion/definition.md":
        "aa23b940d1e556df98cee5f332e8757f886ab098f468620fe084b93e90983513",
    "work/literature_evidence_seven_phenomena_20260822/00_admin/CURRENT_STATE.md":
        "a2de36342a29cc143a56e887b525c37acbd27eca028d37c92bac37cb6a76506c",
    "work/literature_evidence_seven_phenomena_20260822/00_admin/DECISION_LOG.jsonl":
        "be2235e5f9cbc20bdff4265be634d23f5ac4a71ca364c792c86451d9f6b90253",
}
DECLARATION_PATHS = [
    "config/phenomena_registry.v1.json",
    "config/stage2_environment_class_enum.v1.json",
    "config/stage2_inclusion_exclusion_confound_contract_template.v1.json",
    "config/stage2_zero_drop_status_dictionary.v1.json",
    "config/stage2_additional_information_sidecar_schema.v1.json",
    "phenomena/_templates/definition.v1.md",
    "phenomena/_draft/PT/definition.md",
    "phenomena/_draft/NAN/definition.md",
    "phenomena/_draft/NAL/definition.md",
    "phenomena/_draft/LLN/definition.md",
    "phenomena/_draft/VH/definition.md",
    "phenomena/_draft/HIA/definition.md",
    "docs/decisions/SCHEMA_stage2_gate0_common_contracts_20260823.md",
    "scripts/python/audit_stage2_gate0_common_contracts.py",
    "tests/test_audit_stage2_gate0_common_contracts.py",
]
PREEXISTING_UNTRACKED = {
    "docs/decisions/DECISION_stage2_seven_phenomena_workflow_user_decisions_20260823.md",
    "docs/decisions/HANDOFF_stage2_gate0_implementation_prompt_20260823.md",
    "docs/decisions/HANDOFF_stage2_gate0_implementation_prompt_v2_20260823.md",
    "docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.html",
    "docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md",
    "docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.html",
    "docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json",
    "docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.md",
    "docs/reviews/incoming/_to_delete/",
}
ALLOWED_NEW_PREFIXES = (
    "config/phenomena_registry.v1.json",
    "config/stage2_",
    "phenomena/_templates/",
    "phenomena/_draft/",
    "docs/decisions/SCHEMA_stage2_gate0_common_contracts_20260823.md",
    "scripts/python/audit_stage2_gate0_common_contracts.py",
    "tests/test_audit_stage2_gate0_common_contracts.py",
    "outputs/pilots/stage2_gate0_common_contracts_20260823/",
    "logs/stage2_gate0_common_contracts_20260823/",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_sha(path: Path, expected: str) -> None:
    require(path.is_file(), f"missing input: {path}")
    actual = sha256_file(path)
    require(actual == expected.lower(), f"SHA mismatch: {path}: {actual} != {expected}")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"JSON top level must be object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            require(line.strip() != "", f"blank JSONL line: {path}:{line_number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL row must be object: {path}:{line_number}")
            rows.append(value)
    return rows


def path_from_repo(repo_root: Path, relative: str) -> Path:
    require(relative != "", "empty relative path")
    candidate = (repo_root / relative).resolve()
    root = repo_root.resolve()
    require(candidate == root or root in candidate.parents, f"path escapes repo: {relative}")
    return candidate


def validate_literature(
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    inv_path = repo_root / "work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl"
    claim_path = repo_root / "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl"
    inv_rows = read_jsonl(inv_path)
    claim_rows = read_jsonl(claim_path)
    require(len(inv_rows) == 362, f"inventory rows: {len(inv_rows)}")
    require(len(claim_rows) == 156, f"claim rows: {len(claim_rows)}")
    require(
        [row.get("source_id") for row in inv_rows]
        == [f"SRC-{number:03d}" for number in range(1, 363)],
        "inventory IDs are not SRC-001..SRC-362",
    )
    require(
        [row.get("claim_id") for row in claim_rows]
        == [f"CLM-{number:04d}" for number in range(1, 157)],
        "claim IDs are not CLM-0001..CLM-0156",
    )
    inventory = {str(row["source_id"]): row for row in inv_rows}
    claims = {str(row["claim_id"]): row for row in claim_rows}
    for claim_id, claim in claims.items():
        source_id = str(claim.get("source_id", ""))
        require(source_id in inventory, f"missing source binding: {claim_id}->{source_id}")
        source = inventory[source_id]
        require(claim.get("source_file") == source.get("relative_path"), f"source path binding: {claim_id}")
        require(claim.get("source_sha256") == source.get("sha256"), f"source SHA binding: {claim_id}")
    human = {claim_id for claim_id, row in claims.items() if row.get("needs_human_check") is True}
    require(human == EXPECTED_HUMAN_CHECK, f"needs_human_check set: {sorted(human)}")
    for source_id in EXPECTED_PROSODY_SOURCE_ONLY:
        require(source_id in inventory, f"missing prosody source: {source_id}")
        require(not any(row.get("source_id") == source_id for row in claim_rows), f"prosody source has CLM: {source_id}")
    return inventory, claims, {
        "inventory_rows": len(inv_rows),
        "claim_rows": len(claim_rows),
        "needs_human_check": sorted(human),
        "source_binding_errors": 0,
    }


def validate_registry(
    repo_root: Path,
    registry: dict[str, Any],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    require(registry.get("schema_version") == "phenomena_registry.v1", "registry schema_version")
    require(registry.get("status") == "candidate_pending_researcher_adoption", "registry status")
    rows = registry.get("phenomena")
    require(isinstance(rows, list), "registry phenomena must be array")
    require([row.get("phenomenon_code") for row in rows] == EXPECTED_CODES, "registry code order/set")
    required_fields = {
        "phenomenon_code", "label_ko", "official_slug", "slug_status",
        "definition_path", "definition_status", "literature_synthesis_path",
        "literature_scaffold_path", "literature_evidence_level",
        "core_extracted_source_count", "core_extracted_claim_count",
        "total_phenomenon_claim_mentions", "a_direct_count", "query_status",
        "frozen_query_sha256", "gate_position", "notes",
    }
    for row in rows:
        code = str(row.get("phenomenon_code", ""))
        require(required_fields <= set(row), f"registry missing fields: {code}: {sorted(required_fields - set(row))}")
        source = handoff["phenomena"][code]
        for field in (
            "label_ko", "literature_evidence_level", "core_extracted_source_count",
            "core_extracted_claim_count", "total_phenomenon_claim_mentions", "a_direct_count",
        ):
            require(row[field] == source[field], f"registry/handoff mismatch: {code}.{field}")
        require(path_from_repo(repo_root, row["definition_path"]).is_file(), f"missing definition: {code}")
        require(path_from_repo(repo_root, row["literature_synthesis_path"]).is_file(), f"missing synthesis: {code}")
        scaffold = row["literature_scaffold_path"]
        if code == "NI":
            require(scaffold is None, "NI literature_scaffold_path must be null")
            require(row["official_slug"] == "34_n_insertion", "NI official_slug")
            require(row["slug_status"] == "assigned_existing", "NI slug_status")
            require(row["definition_path"] == "phenomena/34_n_insertion/definition.md", "NI definition path")
            require(row["definition_status"] == "researcher_confirmed", "NI definition status")
            require(row["query_status"] == "frozen", "NI query_status")
            require(row["frozen_query_sha256"] == EXPECTED_INPUTS["config/target_queries/n_insertion_production_v1_20260818.json"], "NI query SHA")
        else:
            require(isinstance(scaffold, str) and path_from_repo(repo_root, scaffold).is_file(), f"missing scaffold: {code}")
            require(row["official_slug"] is None and row["slug_status"] == "pending_f0", f"pending slug: {code}")
            require(row["query_status"] == "draft_pv_only", f"draft query status: {code}")
            require(row["frozen_query_sha256"] is None, f"unexpected frozen SHA: {code}")
    generated = registry.get("generated_from")
    require(isinstance(generated, dict), "registry generated_from")
    expected_roles = {
        "literature_handoff": "docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json",
        "source_inventory": "work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl",
        "claim_evidence": "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl",
        "n_insertion_frozen_query": "config/target_queries/n_insertion_production_v1_20260818.json",
    }
    for role, relative in expected_roles.items():
        require(generated.get(role, {}).get("path") == relative, f"generated_from path: {role}")
        require(generated[role].get("sha256") == EXPECTED_INPUTS[relative], f"generated_from SHA: {role}")
    return {"phenomena": len(rows), "codes": EXPECTED_CODES, "required_fields_complete": True}


def validate_declarations(repo_root: Path, inventory: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
    environment = read_json(repo_root / "config/stage2_environment_class_enum.v1.json")
    require(environment.get("schema_version") == "stage2_environment_class_enum.v1", "environment schema")
    require([item.get("value") for item in environment.get("environment_class", [])] == EXPECTED_ENVIRONMENT_CLASSES, "environment enum values")
    require(environment.get("assignment_rows") == [], "Gate 0 environment assignments must be empty")

    contract = read_json(repo_root / "config/stage2_inclusion_exclusion_confound_contract_template.v1.json")
    require(contract.get("schema_version") == "stage2_inclusion_exclusion_confound_contract_template.v1", "contract schema")
    template = contract.get("template", {})
    require(template.get("contract_status") == "draft", "contract template status")
    require(template.get("query_reference") is None, "contract query_reference must be null")
    for field in ("include_conditions", "exclude_conditions", "confound_phenomena", "membership_rules", "evidence_refs", "unresolved_items"):
        require(template.get(field) == [], f"Gate 0 contract values must be empty: {field}")

    zero_drop = read_json(repo_root / "config/stage2_zero_drop_status_dictionary.v1.json")
    require(zero_drop.get("schema_version") == "stage2_zero_drop_status_dictionary.v1", "zero-drop schema")
    axes = zero_drop.get("independent_axes", {})
    for axis, values in EXPECTED_AXES.items():
        require(axes.get(axis, {}).get("values") == values, f"zero-drop axis: {axis}")
    require("combined" not in axes, "independent axes must not be merged")

    sidecar = read_json(repo_root / "config/stage2_additional_information_sidecar_schema.v1.json")
    require(sidecar.get("$id") == "stage2_additional_information_sidecar_schema.v1", "sidecar $id")
    required = set(sidecar.get("required", []))
    expected_required = {
        "schema_version", "request_id", "phenomenon_id", "occurrence_id",
        "key_namespace", "information_key", "requested_reason", "value_status",
        "value_text_or_ref", "evidence_source", "evidence_sha256", "reviewer",
        "recorded_at", "supersedes",
    }
    require(required == expected_required, "sidecar required fields")
    require(sidecar.get("x_contract", {}).get("append_only") is True, "sidecar append-only")
    require(sidecar.get("x_contract", {}).get("actual_data_jsonl_created_at_gate0") is False, "sidecar data rows forbidden")

    template_path = repo_root / "phenomena/_templates/definition.v1.md"
    require(template_path.is_file(), "missing definition template")
    for code in [item for item in EXPECTED_CODES if item != "NI"]:
        path = repo_root / f"phenomena/_draft/{code}/definition.md"
        text = path.read_text(encoding="utf-8")
        require(f"# {code} " in text, f"definition code marker: {code}")
        require("literature_seeded_pending_researcher_confirmation" in text, f"definition status: {code}")
        require("실제 4단 환경 분류행: 0" in text, f"no environment rows marker: {code}")
        for claim_id in re.findall(r"CLM-[0-9]{4}", text):
            require(claim_id in claims, f"definition missing CLM: {code}:{claim_id}")
        for source_id in re.findall(r"SRC-[0-9]{3}", text):
            require(source_id in inventory, f"definition missing SRC: {code}:{source_id}")
    return {
        "environment_assignment_rows": 0,
        "contract_value_rows": 0,
        "sidecar_data_rows": 0,
        "definition_template": True,
        "draft_definitions": 6,
    }


def validate_handoff_refs(handoff: dict[str, Any], inventory: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
    seen_sources: set[str] = set()
    seen_claims: set[str] = set()
    for code, phenomenon in handoff["phenomena"].items():
        require(code in EXPECTED_CODES, f"unexpected handoff code: {code}")
        for source in phenomenon["core_extracted_sources"]:
            source_id = source["source_id"]
            seen_sources.add(source_id)
            require(source_id in inventory, f"handoff source missing: {source_id}")
            require(source["path"] == inventory[source_id]["relative_path"], f"handoff source path: {source_id}")
            for claim_id in source["claim_ids_this_phenomenon"]:
                seen_claims.add(claim_id)
                require(claim_id in claims, f"handoff claim missing: {claim_id}")
                require(claims[claim_id]["source_id"] == source_id, f"handoff claim/source: {claim_id}")
        for refs in phenomenon["seed_map"].values():
            for reference in refs:
                ref_id = reference["ref_id"]
                if reference["ref_type"] == "CLM":
                    seen_claims.add(ref_id)
                    require(ref_id in claims, f"seed claim missing: {ref_id}")
                    require(reference["source_id"] == claims[ref_id]["source_id"], f"seed claim/source: {ref_id}")
                elif reference["ref_type"] == "SRC":
                    seen_sources.add(ref_id)
                    require(ref_id in inventory, f"seed source missing: {ref_id}")
                else:
                    raise ContractError(f"unknown ref_type: {reference['ref_type']}")
    require(seen_claims == set(claims), f"handoff does not cover all claims: {len(seen_claims)}")
    require(len(seen_sources) == 28, f"handoff source ref count: {len(seen_sources)}")
    return {"unique_src_refs": len(seen_sources), "unique_clm_refs": len(seen_claims)}


def check_worktree(repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    lines = [line for line in result.stdout.splitlines() if line]
    unexpected: list[str] = []
    tracked_changes: list[str] = []
    for line in lines:
        status = line[:2]
        path = line[3:].replace("\\", "/")
        if status != "??":
            tracked_changes.append(line)
            continue
        if path in PREEXISTING_UNTRACKED:
            continue
        if not any(path.startswith(prefix) for prefix in ALLOWED_NEW_PREFIXES):
            unexpected.append(line)
    require(not tracked_changes, f"tracked file changes detected: {tracked_changes}")
    require(not unexpected, f"unexpected untracked paths: {unexpected}")
    return {"status_lines": lines, "tracked_changes": 0, "unexpected_untracked": 0}


def audit_repo(repo_root: Path, check_git: bool = True) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    checks: list[str] = []
    protected: dict[str, str] = {}
    for relative, expected in EXPECTED_INPUTS.items():
        path = repo_root / relative
        verify_sha(path, expected)
        protected[relative] = expected
    checks.append("protected_input_sha_match")

    inventory, claims, literature_stats = validate_literature(repo_root)
    checks.append("literature_jsonl_ids_and_bindings")
    handoff = read_json(repo_root / "docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json")
    ref_stats = validate_handoff_refs(handoff, inventory, claims)
    checks.append("handoff_src_clm_refs")
    registry = read_json(repo_root / "config/phenomena_registry.v1.json")
    registry_stats = validate_registry(repo_root, registry, handoff)
    checks.append("registry_roundtrip_and_required_fields")
    declaration_stats = validate_declarations(repo_root, inventory, claims)
    checks.append("a1_to_a6_structure_only")
    for relative in DECLARATION_PATHS:
        require((repo_root / relative).is_file(), f"missing declaration artifact: {relative}")
        require(not (repo_root / f"{relative}.partial").exists(), f"partial remains: {relative}.partial")
    checks.append("artifact_presence_and_no_partial")
    worktree_stats = check_worktree(repo_root) if check_git else {"skipped": True}
    if check_git:
        checks.append("git_allowlist_and_no_tracked_changes")

    artifact_hashes = {
        relative: sha256_file(repo_root / relative)
        for relative in DECLARATION_PATHS
    }
    return {
        "schema_version": "stage2_gate0_common_contracts_audit.v1",
        "status": "passed_candidate_pending_researcher_adoption",
        "passed": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "protected_inputs": protected,
        "literature": literature_stats,
        "handoff_refs": ref_stats,
        "registry": registry_stats,
        "declarations": declaration_stats,
        "worktree": worktree_stats,
        "artifact_sha256": artifact_hashes,
        "scope_assertions": {
            "gate": 0,
            "implemented": ["A1", "A2", "A3_enum_only", "A4_template_only", "A5", "A6_schema_only"],
            "gate1_started": False,
            "query_modified_or_created": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "mfa_koina_wav2vec2_run": False,
        },
    }


def ensure_outputs_absent(paths: Iterable[Path]) -> None:
    for path in paths:
        partial = path.with_name(path.name + ".partial")
        if path.exists() or partial.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_manifest_lines(
    repo_root: Path,
    audit_relative: str,
    audit_payload: bytes,
    manifest_relative: str,
) -> list[str]:
    require(manifest_relative not in DECLARATION_PATHS, "manifest must not hash itself")
    entries = {
        relative: sha256_file(repo_root / relative)
        for relative in DECLARATION_PATHS
    }
    entries[audit_relative] = sha256_bytes(audit_payload)
    require(manifest_relative not in entries, "manifest self-hash forbidden")
    return [f"{digest}  {relative}" for relative, digest in sorted(entries.items())]


def atomic_write_pair(
    audit_path: Path,
    audit_payload: bytes,
    manifest_path: Path,
    manifest_payload: bytes,
) -> None:
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
    parser = argparse.ArgumentParser(description="Audit Stage 2 Gate 0 common contracts")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--audit-output",
        default="outputs/pilots/stage2_gate0_common_contracts_20260823/AUDIT_stage2_gate0_common_contracts_20260823.json",
    )
    parser.add_argument(
        "--manifest-output",
        default="outputs/pilots/stage2_gate0_common_contracts_20260823/SHA256SUMS_stage2_gate0_common_contracts_20260823.txt",
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
    manifest_lines = build_manifest_lines(
        repo_root,
        args.audit_output,
        audit_payload,
        args.manifest_output,
    )
    manifest_payload = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    atomic_write_pair(audit_path, audit_payload, manifest_path, manifest_payload)
    print(f"passed=true audit={audit_path} manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
