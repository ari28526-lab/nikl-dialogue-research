from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.stdout.reconfigure(encoding="utf-8")


class ScopeCardError(RuntimeError):
    pass


EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
EXPECTED_CARD_FIELDS = {
    "schema_version",
    "card_id",
    "phenomenon_code",
    "label_ko",
    "card_status",
    "definition_path",
    "literature_synthesis_path",
    "literature_evidence_level",
    "query_status_at_start",
    "definition_summary",
    "minimum_contrast",
    "boundary_scopes",
    "surface_morph_pos_contract",
    "population_contract",
    "confounds",
    "realization_categories_candidate",
    "not_judgeable_reasons",
    "human_review_items",
    "sidecar_candidates",
    "evidence_refs",
    "evidence_limits",
    "pilot_schedule",
    "sampling_contract",
    "open_questions",
    "readiness",
}
EXPECTED_POPULATIONS = {"primary", "peripheral", "exploratory", "out_of_scope", "unclear"}
EXPECTED_SCHEDULE_MINUTES = [20, 10, 60, 20, 10]
SOURCE_INVENTORY = "work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl"
CLAIM_EVIDENCE = "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl"
SCHEMA_PATH = "config/stage2_two_hour_phenomenon_pilot_schema.v1.json"
CARDS_PATH = "config/phenomenon_scope_cards_candidate_v1_20260823.jsonl"
BUILDER_PATH = "scripts/python/build_stage2_two_hour_scope_cards_review.py"
AUDITOR_PATH = "scripts/python/audit_stage2_two_hour_scope_cards.py"
TEST_PATH = "tests/test_stage2_two_hour_scope_cards.py"
MARKDOWN_PATH = "docs/reviews/incoming/REVIEW_stage2_seven_phenomena_two_hour_scope_cards_20260823.md"
HTML_PATH = "docs/reviews/incoming/REVIEW_stage2_seven_phenomena_two_hour_scope_cards_20260823.html"
DECLARATION_PATHS = [SCHEMA_PATH, CARDS_PATH, BUILDER_PATH, AUDITOR_PATH, TEST_PATH, MARKDOWN_PATH, HTML_PATH]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScopeCardError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"JSON top level must be object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            require(bool(line.strip()), f"blank JSONL line: {path}:{line_number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ScopeCardError(f"invalid JSONL: {path}:{line_number}: {exc}") from exc
            require(isinstance(value, dict), f"JSONL row must be object: {path}:{line_number}")
            rows.append(value)
    return rows


def repo_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    value = (root / relative).resolve()
    require(value == root or root in value.parents, f"path escapes repo: {relative}")
    return value


def validate_schema(schema: dict[str, Any]) -> dict[str, Any]:
    require(schema.get("$id") == "stage2_two_hour_phenomenon_pilot_schema.v1", "schema $id")
    required = set(schema.get("required", []))
    require(required == EXPECTED_CARD_FIELDS, f"schema required fields: {sorted(required)}")
    contract = schema.get("x_contract", {})
    require(contract.get("pilot_minutes_per_phenomenon") == 120, "schema pilot minutes")
    require(contract.get("phenomenon_count") == 7, "schema phenomenon count")
    require(contract.get("total_researcher_minutes") == 840, "schema total minutes")
    require(contract.get("literature_review_included") is True, "literature review must be included")
    require(contract.get("automatic_realization_judgement") is False, "automatic judgement forbidden")
    require(contract.get("query_freeze") is False, "query freeze forbidden")
    require(contract.get("max_rows_scanned_per_source_year") == 200000, "row cap")
    return {"required_fields": len(required), "minutes_each": 120, "minutes_total": 840}


def validate_literature(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    sources = read_jsonl(repo_path(root, SOURCE_INVENTORY))
    claims = read_jsonl(repo_path(root, CLAIM_EVIDENCE))
    require(len(sources) == 362, f"source rows: {len(sources)}")
    require(len(claims) >= 156, f"claim rows below frozen prefix: {len(claims)}")
    expected_claim_ids = [f"CLM-{number:04d}" for number in range(1, len(claims) + 1)]
    require(
        [str(row.get("claim_id", "")) for row in claims] == expected_claim_ids,
        "claim ledger must preserve CLM-0001..CLM-0156 and use contiguous append-only IDs",
    )
    source_map = {str(row.get("source_id")): row for row in sources}
    claim_map = {str(row.get("claim_id")): row for row in claims}
    require(len(source_map) == len(sources), "duplicate source IDs")
    require(len(claim_map) == len(claims), "duplicate claim IDs")
    for claim_id, claim in claim_map.items():
        source_id = str(claim.get("source_id", ""))
        require(source_id in source_map, f"missing claim source: {claim_id}->{source_id}")
        require(claim.get("source_sha256") == source_map[source_id].get("sha256"), f"claim source SHA: {claim_id}")
    return source_map, claim_map, {
        "source_rows": len(sources),
        "claim_rows": len(claims),
        "frozen_claim_prefix_rows": 156,
        "appended_claim_rows": len(claims) - 156,
        "source_sha256": sha256_file(repo_path(root, SOURCE_INVENTORY)),
        "claim_sha256": sha256_file(repo_path(root, CLAIM_EVIDENCE)),
    }


def condition_refs(card: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(str(value) for value in card["evidence_refs"])
    for item in card["boundary_scopes"]:
        values.extend(str(value) for value in item["evidence_refs"])
    for item in card["confounds"]:
        values.extend(str(value) for value in item["evidence_refs"])
    for group in card["population_contract"].values():
        for item in group:
            values.extend(str(value) for value in item["evidence_refs"])
    return values


def validate_card(
    root: Path,
    card: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    claims: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    code = str(card.get("phenomenon_code", ""))
    require(set(card) == EXPECTED_CARD_FIELDS, f"card fields: {code}: {sorted(set(card) ^ EXPECTED_CARD_FIELDS)}")
    require(card["schema_version"] == "stage2_two_hour_phenomenon_pilot_card.v1", f"schema version: {code}")
    require(card["card_id"] == f"P2H-{code}-V1", f"card id: {code}")
    require(card["card_status"] == "candidate_pending_researcher_adoption", f"card status: {code}")
    require(repo_path(root, str(card["definition_path"])).is_file(), f"definition missing: {code}")
    require(repo_path(root, str(card["literature_synthesis_path"])).is_file(), f"synthesis missing: {code}")
    require(len(card["minimum_contrast"]) >= 2, f"minimum contrast: {code}")
    require(card["surface_morph_pos_contract"].get("mismatch_status") == "surface_analysis_mismatch", f"mismatch status: {code}")
    population = card["population_contract"]
    require(set(population) == EXPECTED_POPULATIONS, f"population groups: {code}")
    require(bool(population["primary"]), f"primary population empty: {code}")
    require(bool(population["out_of_scope"]), f"out-of-scope empty: {code}")
    require(bool(population["unclear"]), f"unclear empty: {code}")
    condition_ids: list[str] = []
    for group_name, items in population.items():
        for item in items:
            condition_id = str(item.get("condition_id", ""))
            require(re.fullmatch(r"[A-Z0-9_]+", condition_id) is not None, f"condition id: {code}:{condition_id}")
            condition_ids.append(condition_id)
            expected_priority = {"primary": 1, "peripheral": 2, "exploratory": 3, "out_of_scope": 4, "unclear": 4}[group_name]
            require(item.get("priority") == expected_priority, f"population priority: {code}:{condition_id}")
    require(len(condition_ids) == len(set(condition_ids)), f"duplicate condition IDs: {code}")
    minutes = [int(item.get("minutes", 0)) for item in card["pilot_schedule"]]
    require(minutes == EXPECTED_SCHEDULE_MINUTES, f"schedule minutes: {code}:{minutes}")
    require(sum(minutes) == 120, f"schedule sum: {code}")
    sampling = card["sampling_contract"]
    require(sampling.get("target_total") == 12, f"sample total: {code}")
    require(sampling.get("primary_target") == 10, f"primary target: {code}")
    require(sampling.get("peripheral_or_exploratory_cap") == 2, f"exploratory cap: {code}")
    require(sampling.get("year_target") == "2020-2025_each_up_to_2", f"year target: {code}")
    require(sampling.get("no_silent_drop") is True, f"zero drop: {code}")
    for reference in condition_refs(card):
        if reference.startswith("CLM-"):
            require(reference in claims, f"missing CLM: {code}:{reference}")
        elif reference.startswith("SRC-"):
            require(reference in sources, f"missing SRC: {code}:{reference}")
        else:
            raise ScopeCardError(f"invalid reference: {code}:{reference}")
    require("automatic" not in " ".join(card["realization_categories_candidate"]).lower(), f"automatic category: {code}")
    return {
        "conditions": len(condition_ids),
        "evidence_refs": len(set(condition_refs(card))),
        "minutes": sum(minutes),
        "sample_target": sampling["target_total"],
    }


def validate_ni_exception(card: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(card, ensure_ascii=False)
    require("표면 요" in serialized, "NI surface 요 branch missing")
    require("이/VCP+요" in serialized, "NI restored 이/VCP+요 branch missing")
    require("제외 금지" in serialized or "삭제하지" in serialized, "NI restored form retention missing")
    out_ids = {item["condition_id"] for item in card["population_contract"]["out_of_scope"]}
    exp_ids = {item["condition_id"] for item in card["population_contract"]["exploratory"]}
    require("NI_OUT_OVERT_COPULA_I" in out_ids, "NI overt copula exclusion missing")
    require("NI_EXP_YO" in exp_ids, "NI 요 exploratory population missing")
    return {"overt_i_excluded": True, "surface_yo_restored_i_retained": True}


def validate_review_outputs(root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    markdown_path = repo_path(root, MARKDOWN_PATH)
    html_path = repo_path(root, HTML_PATH)
    require(markdown_path.is_file(), f"missing markdown: {markdown_path}")
    require(html_path.is_file(), f"missing html: {html_path}")
    markdown = markdown_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    for row in rows:
        code = row["phenomenon_code"]
        require(f"## {code} —" in markdown, f"markdown section: {code}")
        require(f'data-code="{code}"' in html_text, f"html tab: {code}")
    require("localStorage" in html_text, "HTML local note persistence missing")
    require("STAGE2_TWO_HOUR_SCOPE_NOTES.jsonl" in html_text, "HTML export missing")
    require("실현 판정이나 연구 완료 기록이 아닙니다" in html_text, "HTML exploration warning missing")
    return {
        "markdown_bytes": markdown_path.stat().st_size,
        "html_bytes": html_path.stat().st_size,
        "one_phenomenon_navigation": True,
        "notes_and_jsonl_export": True,
    }


def audit_repo(root: Path, require_review_outputs: bool = True) -> dict[str, Any]:
    root = root.resolve()
    schema = read_json(repo_path(root, SCHEMA_PATH))
    schema_stats = validate_schema(schema)
    sources, claims, literature_stats = validate_literature(root)
    rows = read_jsonl(repo_path(root, CARDS_PATH))
    require(len(rows) == 7, f"scope card rows: {len(rows)}")
    codes = [row.get("phenomenon_code") for row in rows]
    require(codes == EXPECTED_CODES, f"scope card code order: {codes}")
    card_stats = {
        row["phenomenon_code"]: validate_card(root, row, sources, claims)
        for row in rows
    }
    ni_stats = validate_ni_exception(rows[EXPECTED_CODES.index("NI")])
    review_stats = validate_review_outputs(root, rows) if require_review_outputs else {"skipped": True}
    for relative in [SCHEMA_PATH, CARDS_PATH, BUILDER_PATH, AUDITOR_PATH]:
        require(repo_path(root, relative).is_file(), f"missing artifact: {relative}")
        require(not repo_path(root, relative + ".partial").exists(), f"partial remains: {relative}.partial")
    return {
        "schema_version": "stage2_two_hour_scope_cards_audit.v1",
        "passed": True,
        "status": "passed_candidate_no_query_freeze_no_realization_judgement",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema": schema_stats,
        "literature": literature_stats,
        "cards": card_stats,
        "ni_surface_exception": ni_stats,
        "review_outputs": review_stats,
        "totals": {
            "phenomena": len(rows),
            "minutes_per_phenomenon": 120,
            "researcher_minutes": 840,
            "sample_target_per_phenomenon": 12,
            "sample_target_total": 84,
        },
        "scope_assertions": {
            "query_created_or_frozen": False,
            "occurrences_extracted": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "mfa_koina_wav2vec2_run": False,
            "source_or_frozen_outputs_modified": False,
        },
    }


def ensure_absent(paths: Iterable[Path]) -> None:
    for path in paths:
        partial = path.with_name(path.name + ".partial")
        if path.exists() or partial.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")


def atomic_write_pair(audit_path: Path, audit_payload: bytes, manifest_path: Path, manifest_payload: bytes) -> None:
    ensure_absent([audit_path, manifest_path])
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
    parser = argparse.ArgumentParser(description="Audit Stage 2 two-hour scope cards")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--skip-review-outputs", action="store_true")
    parser.add_argument(
        "--audit-output",
        default="outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/scope_cards/AUDIT_two_hour_scope_cards_20260823.json",
    )
    parser.add_argument(
        "--manifest-output",
        default="outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/scope_cards/SHA256SUMS_two_hour_scope_cards_20260823.txt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    report = audit_repo(root, require_review_outputs=not args.skip_review_outputs)
    if args.check_only:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    audit_path = repo_path(root, args.audit_output)
    manifest_path = repo_path(root, args.manifest_output)
    audit_payload = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    entries = {
        relative: sha256_file(repo_path(root, relative))
        for relative in DECLARATION_PATHS
    }
    entries[args.audit_output] = sha256_bytes(audit_payload)
    require(args.manifest_output not in entries, "manifest cannot hash itself")
    manifest_payload = ("\n".join(f"{digest}  {relative}" for relative, digest in sorted(entries.items())) + "\n").encode("utf-8")
    atomic_write_pair(audit_path, audit_payload, manifest_path, manifest_payload)
    print(f"passed=true audit={audit_path} manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
