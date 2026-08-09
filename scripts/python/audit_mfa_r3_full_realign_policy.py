from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
R3_RELEASE_ID = "common_pron_mfa_r3_20260809"
R2_RELEASE_ID = "common_pron_mfa_r2_20260728"
R3_EXECUTION_PATHS = (
    "scripts/run_mfa_r3_year_safe_body.ps1",
    "scripts/python/preflight_mfa_r3_year_safe_body.py",
    "scripts/python/materialize_mfa_r3_safe_body_corpus.py",
    "scripts/python/export_mfa_db_research_6tier.py",
    "scripts/python/audit_mfa_research_6tier_year.py",
)
LEGACY_EXECUTION_TOKENS = (
    "common_pron_mfa_r2_",
    "direct_db_research_6tier_v1",
    "mfa_r2_",
    "direct_db_ready",
    "run_eojeol_realign.ps1",
    "d:\\mfa_tmp",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def resolve_record_path(raw: str, project_root: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def verify_record(
    record: dict[str, Any], project_root: Path, label: str
) -> tuple[Path | None, str | None]:
    raw_path = str(record.get("path", "")).strip()
    expected_sha = str(record.get("sha256", "")).strip().lower()
    if not raw_path or len(expected_sha) != 64:
        return None, f"{label} fingerprint record is incomplete"
    path = resolve_record_path(raw_path, project_root)
    if not path.is_file():
        return None, f"{label} file is missing: {path}"
    if "bytes" in record and path.stat().st_size != int(record["bytes"]):
        return None, f"{label} byte count differs"
    if sha256_file(path) != expected_sha:
        return None, f"{label} SHA-256 differs"
    return path, None


def load_routing_summary(path: Path) -> dict[int, dict[str, int]]:
    result: dict[int, dict[str, int]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            year = int(row["year"])
            if year in result:
                raise RuntimeError(f"duplicate routing summary year: {year}")
            result[year] = {
                "source": int(row["utterances"]),
                "safe_body": int(row["safe_utterances"]),
                "followup": int(row["blocked_utterances"]),
            }
    return result


def validate_policy(
    workflow: dict[str, Any],
    contract: dict[str, Any],
    release_gate: dict[str, Any],
    approval: dict[str, Any],
    gate_approval: dict[str, Any],
    checklist: dict[str, Any],
    routing_rows: dict[int, dict[str, int]],
    *,
    expected_gate_state: str = "adopted",
    release_id: str = R3_RELEASE_ID,
) -> list[str]:
    failures: list[str] = []
    scope = workflow.get("scope", {})
    accounting = workflow.get("year_accounting", {})

    if scope.get("years") != YEARS:
        failures.append("workflow scope years differ from 2020-2025")
    if contract.get("scope_years") != YEARS:
        failures.append("v3.1 contract scope years differ from 2020-2025")
    sums = {"source": 0, "safe_body": 0, "followup": 0}
    for year in YEARS:
        row = accounting.get(str(year))
        if not isinstance(row, dict):
            failures.append(f"missing year accounting: {year}")
            continue
        observed = routing_rows.get(year)
        if observed is None:
            failures.append(f"missing Stage 19 routing summary year: {year}")
            continue
        for key in sums:
            value = int(row.get(key, -1))
            sums[key] += value
            if value != observed[key]:
                failures.append(
                    f"workflow {key} differs from Stage 19 summary: {year}"
                )
        if int(row.get("source", -1)) != (
            int(row.get("safe_body", -1)) + int(row.get("followup", -1))
        ):
            failures.append(f"year accounting does not balance: {year}")
    if set(routing_rows) != set(YEARS):
        failures.append("Stage 19 routing summary year set differs")
    for key, scope_key in (
        ("source", "source_utterances"),
        ("safe_body", "safe_body_utterances"),
        ("followup", "followup_utterances"),
    ):
        if sums[key] != int(scope.get(scope_key, -1)):
            failures.append(f"six-year {key} total differs from scope")

    decision = workflow.get("researcher_decision", {})
    if decision.get("full_r3_realign_safe_body_all_years") is not True:
        failures.append("researcher full r3 safe-body realignment is not true")
    if decision.get("reuse_r2_intervals_in_final_r3") is not False:
        failures.append("researcher r2 interval reuse must be false")
    workflow_invariants = workflow.get("annual_completion_invariants", {})
    if workflow_invariants.get(
        "all_alignment_eligible_utterances_within_pronunciation_safe_body_newly_aligned_under_r3"
    ) is not True:
        failures.append("workflow does not require full eligible safe-body realignment")
    if workflow_invariants.get(
        "technically_unalignable_pronunciation_safe_ids_preserved_with_explicit_reason"
    ) is not True:
        failures.append("workflow does not preserve technically unalignable exact IDs")

    invariants = contract.get("invariants", {})
    rerun = contract.get("rerun_policy", {})
    materialization = contract.get("textgrid_materialization_gate", {})
    if invariants.get(
        "all_alignment_eligible_utterances_within_pronunciation_safe_body_newly_aligned_under_r3"
    ) is not True:
        failures.append("v3.1 contract does not require full eligible realignment")
    if invariants.get("pronunciation_safe_is_not_alignment_eligibility") is not True:
        failures.append("v3.1 contract conflates pronunciation and alignment safety")
    if invariants.get("r2_alignment_intervals_used_in_final_r3") is not False:
        failures.append("v3.1 contract permits r2 alignment intervals")
    if rerun.get("unchanged_r2_reuse_allowed") is not False:
        failures.append("v3.1 rerun policy permits unchanged r2 reuse")
    if materialization.get("years") != YEARS:
        failures.append("TextGrid materialization years differ from 2020-2025")
    if "new MFA database" not in materialization.get(
        "source_of_words_and_phones", ""
    ):
        failures.append("TextGrid source is not explicitly a new r3 MFA database")

    approved_scope = release_gate.get("approved_staged_scope", {})
    if int(approved_scope.get("safe_body_utterances", -1)) != sums["safe_body"]:
        failures.append("release gate safe-body count differs")
    if int(approved_scope.get("followup_utterances", -1)) != sums["followup"]:
        failures.append("release gate follow-up count differs")
    if approved_scope.get("r2_intervals_allowed_in_final_r3") is not False:
        failures.append("release gate permits r2 intervals in final r3")
    if R2_RELEASE_ID not in (release_gate.get("blocked_release_ids") or []):
        failures.append("r2 release is not explicitly blocked")

    if expected_gate_state == "adopted":
        if release_gate.get("status") != "adopted":
            failures.append("production release gate is not adopted")
        if release_gate.get("allowed_release_ids") != [release_id]:
            failures.append("production release gate does not allow exactly the r3 release")
    elif expected_gate_state == "closed":
        if release_gate.get("allowed_release_ids") != []:
            failures.append("production release gate is unexpectedly open")
        if not str(release_gate.get("status", "")).startswith("blocked_"):
            failures.append("release gate status is not blocked")
    else:
        failures.append(f"unknown expected gate state: {expected_gate_state}")

    if approval.get("status") != "passed_explicit_researcher_approval":
        failures.append("staged-scope researcher approval is not passed")
    approval_scope = approval.get("scope", {})
    if int(approval_scope.get("safe_body_utterances", -1)) != sums["safe_body"]:
        failures.append("staged approval safe-body count differs")
    if int(approval_scope.get("followup_utterances", -1)) != sums["followup"]:
        failures.append("staged approval follow-up count differs")
    if approval_scope.get("reuse_r2_intervals_in_final_r3") is not False:
        failures.append("staged approval permits r2 interval reuse")

    if gate_approval.get("status") != "passed_explicit_researcher_approval":
        failures.append("production gate researcher approval is not passed")
    researcher = gate_approval.get("researcher", {})
    gate_release = gate_approval.get("release", {})
    preservation = gate_approval.get("preservation_contract", {})
    if researcher.get("approved_by") != "ari30":
        failures.append("production gate approver differs")
    if gate_release.get("release_id") != release_id:
        failures.append("production gate approval release differs")
    if gate_release.get("production_release_gate_opening_approved") is not True:
        failures.append("production gate opening is not explicitly approved")
    if gate_release.get("preflight_years_approved") != [2020]:
        failures.append("production gate approval preflight years differ")
    if int(gate_release.get("preflight_expected_utterances_2020", -1)) != 782715:
        failures.append("production gate approval 2020 count differs")
    if preservation.get("r2_remains_blocked") is not True:
        failures.append("production gate approval does not preserve the r2 block")
    if preservation.get("followup_exact_id_preserved") is not True:
        failures.append("production gate approval does not preserve follow-up IDs")

    if checklist.get("status") != (
        "passed_checklist_1_7_pending_researcher_release_gate"
    ):
        failures.append("checklist 1-7 candidate status differs")
    checks = checklist.get("checks") or []
    if [item.get("item") for item in checks] != list(range(1, 8)):
        failures.append("checklist 1-7 item identity differs")
    if any(item.get("passed") is not True for item in checks):
        failures.append("at least one checklist 1-7 item is not passed")
    return failures


def find_implementation_gaps(project_root: Path) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for relative in R3_EXECUTION_PATHS:
        path = project_root / relative
        if not path.is_file():
            gaps.append({"path": relative, "reason": "r3 execution file missing"})
            continue
        text = path.read_text(encoding="utf-8-sig", errors="strict").casefold()
        hits = [token for token in LEGACY_EXECUTION_TOKENS if token in text]
        if hits:
            gaps.append(
                {
                    "path": relative,
                    "reason": "legacy production identity token in r3 execution path",
                    "matched_tokens": hits,
                }
            )
    return gaps


def verify_embedded_evidence(
    gate: dict[str, Any], gate_approval: dict[str, Any], project_root: Path
) -> list[str]:
    failures: list[str] = []
    for label in ("checklist_1_7_candidate", "production_gate_researcher_approval"):
        record = gate.get("evidence", {}).get(label)
        if not isinstance(record, dict):
            failures.append(f"release gate evidence is missing: {label}")
            continue
        _, failure = verify_record(record, project_root, f"release gate {label}")
        if failure:
            failures.append(failure)
    for label, record in (gate_approval.get("evidence") or {}).items():
        if not isinstance(record, dict) or "path" not in record:
            continue
        _, failure = verify_record(record, project_root, f"gate approval {label}")
        if failure:
            failures.append(failure)
    return failures


def git_commit(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(partial, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected-gate-state", choices=("closed", "adopted"), default="adopted"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "outputs/reports/AUDIT_mfa_r3_full_realign_policy_v2_gate_adopted_20260809.json",
    )
    args = parser.parse_args()
    paths = {
        "workflow": PROJECT_ROOT / "config/mfa_r3_full_realign_workflow_v1.json",
        "contract": PROJECT_ROOT / "config/common_pronunciation_resource_contract_v3_1.json",
        "release_gate": PROJECT_ROOT / "config/mfa_pronunciation_release_gate.json",
        "approval": PROJECT_ROOT
        / "outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json",
        "gate_approval": PROJECT_ROOT
        / "outputs/reviews/common_pron_r3_production_gate_20260809/RESEARCHER_APPROVAL_PRODUCTION_GATE.json",
        "checklist": PROJECT_ROOT
        / "outputs/reports/AUDIT_mfa_r3_checklist_1_7_candidate_20260809.json",
        "routing_manifest": Path(
            "D:/mfa_common_pron/staging/common_pron_mfa_r3_20260807/"
            "19_pre_adoption_routing/PRE_ADOPTION_ROUTING_MANIFEST.json"
        ),
    }
    documents = {
        key: load_json(path)
        for key, path in paths.items()
        if key != "routing_manifest"
    }
    routing_manifest = load_json(paths["routing_manifest"])
    summary_record = routing_manifest.get("outputs", {}).get("year_routing_summary")
    failures: list[str] = []
    if not isinstance(summary_record, dict):
        failures.append("Stage 19 routing manifest lacks year_routing_summary")
        routing_summary_path = paths["routing_manifest"].parent / "year_routing_summary.csv"
    else:
        verified_path, failure = verify_record(
            summary_record, PROJECT_ROOT, "Stage 19 year routing summary"
        )
        if failure:
            failures.append(failure)
        routing_summary_path = verified_path or (
            paths["routing_manifest"].parent / "year_routing_summary.csv"
        )
    routing_rows = load_routing_summary(routing_summary_path)
    failures.extend(
        validate_policy(
            **documents,
            routing_rows=routing_rows,
            expected_gate_state=args.expected_gate_state,
        )
    )
    failures.extend(
        verify_embedded_evidence(
            documents["release_gate"], documents["gate_approval"], PROJECT_ROOT
        )
    )
    gaps = find_implementation_gaps(PROJECT_ROOT)
    passed = not failures and not gaps
    production_allowed = passed and args.expected_gate_state == "adopted"
    report = {
        "schema_version": "mfa_r3_full_realign_policy_audit.v2",
        "status": (
            "passed_policy_consistency_release_gate_adopted"
            if production_allowed
            else (
                "passed_policy_consistency_release_gate_closed"
                if passed
                else "failed_policy_consistency"
            )
        ),
        "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "expected_gate_state": args.expected_gate_state,
        "release_id": R3_RELEASE_ID,
        "policy_failures": failures,
        "r3_execution_legacy_identity_gaps": gaps,
        "production_mfa_allowed_now": production_allowed,
        "stage19_year_routing_summary": fingerprint(routing_summary_path),
        "inputs": {key: fingerprint(path) for key, path in paths.items()},
        "runtime": {"git_commit": git_commit(PROJECT_ROOT)},
    }
    write_json_atomic(args.output.resolve(), report)
    print(
        f"[{report['status']}] failures={len(failures)} gaps={len(gaps)} "
        f"production_allowed={str(production_allowed).lower()}"
    )
    print(args.output.resolve())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
