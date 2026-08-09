from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def validate_policy(
    workflow: dict[str, Any],
    draft: dict[str, Any],
    release_gate: dict[str, Any],
    approval: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    years = [2020, 2021, 2022, 2023, 2024, 2025]
    scope = workflow.get("scope", {})
    accounting = workflow.get("year_accounting", {})

    if scope.get("years") != years:
        failures.append("workflow scope years differ from 2020-2025")
    sums = {"source": 0, "safe_body": 0, "followup": 0}
    for year in years:
        row = accounting.get(str(year))
        if not isinstance(row, dict):
            failures.append(f"missing year accounting: {year}")
            continue
        for key in sums:
            sums[key] += int(row.get(key, -1))
        if int(row.get("source", -1)) != (
            int(row.get("safe_body", -1)) + int(row.get("followup", -1))
        ):
            failures.append(f"year accounting does not balance: {year}")
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
    if (
        workflow_invariants.get(
            "all_alignment_eligible_utterances_within_pronunciation_safe_body_newly_aligned_under_r3"
        )
        is not True
    ):
        failures.append("workflow does not require full eligible pronunciation-safe realignment")
    if (
        workflow_invariants.get(
            "technically_unalignable_pronunciation_safe_ids_preserved_with_explicit_reason"
        )
        is not True
    ):
        failures.append("workflow does not preserve technically unalignable exact IDs")

    invariants = draft.get("invariants", {})
    rerun = draft.get("rerun_policy", {})
    materialization = draft.get("textgrid_materialization_gate", {})
    if (
        invariants.get(
            "all_alignment_eligible_utterances_within_pronunciation_safe_body_newly_aligned_under_r3"
        )
        is not True
    ):
        failures.append("draft does not require every alignment-eligible pronunciation-safe utterance to be newly aligned")
    if invariants.get("pronunciation_safe_is_not_alignment_eligibility") is not True:
        failures.append("draft conflates pronunciation safety with alignment eligibility")
    if invariants.get("r2_alignment_intervals_used_in_final_r3") is not False:
        failures.append("draft permits r2 alignment intervals in final r3")
    if rerun.get("unchanged_r2_reuse_allowed") is not False:
        failures.append("draft rerun policy permits unchanged r2 reuse")
    if materialization.get("years") != years:
        failures.append("TextGrid materialization years differ from 2020-2025")
    if "new MFA database" not in materialization.get("source_of_words_and_phones", ""):
        failures.append("TextGrid source is not explicitly a new r3 MFA database")

    if release_gate.get("allowed_release_ids") != []:
        failures.append("production release gate is unexpectedly open")
    if not str(release_gate.get("status", "")).startswith("blocked_pending_r3"):
        failures.append("release gate status is not blocked_pending_r3")
    approved_scope = release_gate.get("approved_staged_scope", {})
    if int(approved_scope.get("safe_body_utterances", -1)) != sums["safe_body"]:
        failures.append("release gate safe-body count differs")
    if int(approved_scope.get("followup_utterances", -1)) != sums["followup"]:
        failures.append("release gate follow-up count differs")
    if approved_scope.get("r2_intervals_allowed_in_final_r3") is not False:
        failures.append("release gate permits r2 intervals in final r3")

    if approval.get("status") != "passed_explicit_researcher_approval":
        failures.append("explicit researcher approval artifact is not passed")
    approval_scope = approval.get("scope", {})
    if int(approval_scope.get("safe_body_utterances", -1)) != sums["safe_body"]:
        failures.append("approval safe-body count differs")
    if int(approval_scope.get("followup_utterances", -1)) != sums["followup"]:
        failures.append("approval follow-up count differs")
    if approval_scope.get("reuse_r2_intervals_in_final_r3") is not False:
        failures.append("approval permits r2 interval reuse")
    if approval.get("gate", {}).get("allow_production_mfa_now") is not False:
        failures.append("approval artifact unexpectedly permits production MFA")
    return failures


def find_implementation_gaps(project_root: Path) -> list[dict[str, Any]]:
    checks = {
        "scripts/run_eojeol_realign.ps1": ["mfa_r2", "common_pron_mfa_r2"],
        "scripts/python/validate_mfa_r2_adoption.py": ["r2"],
        "scripts/python/build_mfa_alignment_contract.py": ["r2"],
    }
    gaps: list[dict[str, Any]] = []
    for relative, tokens in checks.items():
        path = project_root / relative
        if not path.is_file():
            gaps.append({"path": relative, "reason": "expected runner dependency missing"})
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        hits = [token for token in tokens if token.casefold() in text.casefold()]
        if hits:
            gaps.append(
                {
                    "path": relative,
                    "reason": "legacy r2-specific contract tokens remain",
                    "matched_tokens": hits,
                }
            )
    if not (project_root / "scripts/run_mfa_r3_year_safe_body.ps1").is_file():
        gaps.append(
            {
                "path": "scripts/run_mfa_r3_year_safe_body.ps1",
                "reason": "dedicated r3 annual runner not implemented",
            }
        )
    return gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "outputs/reports/AUDIT_mfa_r3_full_realign_policy_20260809.json",
    )
    args = parser.parse_args()
    paths = {
        "workflow": PROJECT_ROOT / "config/mfa_r3_full_realign_workflow_v1.json",
        "draft": PROJECT_ROOT / "config/common_pronunciation_resource_contract_v3_draft.json",
        "release_gate": PROJECT_ROOT / "config/mfa_pronunciation_release_gate.json",
        "approval": PROJECT_ROOT
        / "outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json",
    }
    documents = {key: load_json(path) for key, path in paths.items()}
    failures = validate_policy(**documents)
    gaps = find_implementation_gaps(PROJECT_ROOT)
    report = {
        "schema_version": "mfa_r3_full_realign_policy_audit.v1",
        "status": (
            "passed_policy_consistency_blocked_as_expected_pending_external_review_and_runner"
            if not failures
            else "failed_policy_consistency"
        ),
        "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "policy_failures": failures,
        "production_mfa_allowed_now": False,
        "implementation_gaps_expected_before_external_review": gaps,
        "inputs": {
            key: {"path": str(path), "sha256": sha256_file(path)}
            for key, path in paths.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[{report['status']}] failures={len(failures)} gaps={len(gaps)}")
    print(args.output)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
