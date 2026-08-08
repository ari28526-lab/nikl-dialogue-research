"""Summarize r3 adoption gates after safe-body and targeted regression audits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_adoption_readiness_audit.v1"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit(
    *, readiness_manifest_path: Path, routing_manifest_path: Path,
    routing_audit_path: Path, decision_audit_path: Path,
    candidate_manifest_path: Path, candidate_audit_path: Path,
    targeted_audit_path: Path, release_gate_path: Path, draft_contract_path: Path,
    output_path: Path,
) -> dict[str, object]:
    readiness = load(readiness_manifest_path)
    routing = load(routing_manifest_path)
    routing_audit = load(routing_audit_path)
    decision = load(decision_audit_path)
    candidate = load(candidate_manifest_path)
    candidate_audit = load(candidate_audit_path)
    targeted = load(targeted_audit_path)
    release_gate = load(release_gate_path)
    draft = load(draft_contract_path)
    expected_statuses = (
        (readiness, "success_planning_not_selected"),
        (routing, "success_read_only_routing_not_adopted"),
        (routing_audit, "passed_independent_full_scan"),
        (decision, "no_reusable_decisions_found"),
        (candidate, "passed_candidate_only_not_adopted"),
        (candidate_audit, "passed_full_projection_and_dictionary_equivalence"),
        (targeted, "passed_automatic_checks_pending_researcher_audio_review"),
        (release_gate, "blocked_pending_r3"),
        (draft, "blocked_pending_targeted_validation"),
    )
    if any(record.get("status") != status for record, status in expected_statuses):
        raise RuntimeError("adoption readiness input status differs")
    readiness_counts = readiness["counts"]
    routing_counts = routing["counts"]
    candidate_counts = candidate["counts"]
    canonical_types = int(readiness_counts["canonical_types"])
    candidate_types = int(readiness_counts["candidate_ready_types"])
    hold_types = int(readiness_counts["zero_fallback_hold_types"])
    policy_types = int(readiness_counts["planning_status_types"]["policy_candidate_multiple_rule_dictionary_conflict"])
    if candidate_types + hold_types + policy_types != canonical_types:
        raise RuntimeError("canonical readiness partition differs")
    gates = [
        {
            "gate": "canonical_type_coverage",
            "passed": canonical_types == 881237,
            "evidence": f"{canonical_types} observed types represented exactly once",
        },
        {
            "gate": "safe_body_routing_independent_audit",
            "passed": True,
            "evidence": f"{routing_counts['safe_utterances']} safe and {routing_counts['blocked_utterances']} deferred utterances; unknown eojeol=0",
        },
        {
            "gate": "candidate_dictionary_phone_and_byte_projection",
            "passed": True,
            "evidence": f"{candidate_counts['candidate_types']} types / {candidate_counts['dictionary_rows']} variant rows; outside inventory=0; spn=0",
        },
        {
            "gate": "full_final_selected_phone_coverage",
            "passed": False,
            "evidence": f"planning candidates={candidate_types}; zero-fallback hold={hold_types}; policy decision={policy_types}; planning rows are not final selection",
        },
        {
            "gate": "explicit_policy_decisions",
            "passed": False,
            "evidence": f"{policy_types} types / 163 occurrences; reusable prior decisions=0",
        },
        {
            "gate": "targeted_regression_automatic",
            "passed": True,
            "evidence": "review IDs 08, 09, 15, 24: candidate phone exact 4/4; boundaries internally consistent 4/4; spn=0",
        },
        {
            "gate": "targeted_regression_researcher_audio_boundary_review",
            "passed": False,
            "evidence": "4/4 pending in Dropbox review bundle",
        },
        {
            "gate": "project_release_gate_open",
            "passed": False,
            "evidence": "mfa_pronunciation_release_gate remains blocked_pending_r3; allowed_release_ids is empty",
        },
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked_as_expected_at_explicit_method_choice_and_manual_targeted_review",
        "recorded_at": now_iso(),
        "verdict": {
            "full_r3_adoption_allowed": False,
            "yearly_production_mfa_allowed": False,
            "textgrid_materialization_allowed": False,
            "safe_body_candidate_materialized_and_audited": True,
            "next_automatic_work_exhausted_without_changing_adoption_policy": True,
        },
        "coverage": {
            "canonical_types": canonical_types,
            "canonical_occurrences": int(readiness_counts["total_occurrences"]),
            "candidate_types": candidate_types,
            "candidate_occurrences": int(readiness_counts["candidate_ready_occurrences"]),
            "zero_fallback_hold_types": hold_types,
            "zero_fallback_hold_occurrences": int(readiness_counts["zero_fallback_hold_occurrences"]),
            "policy_types": policy_types,
            "policy_occurrences": 163,
            "safe_utterances": int(routing_counts["safe_utterances"]),
            "blocked_utterances": int(routing_counts["blocked_utterances"]),
            "safe_utterance_percent": float(routing_counts["safe_utterance_percent"]),
        },
        "gates": gates,
        "decision_required": {
            "decision_1": {
                "question": "Keep the full 881237-type adoption gate, or authorize a staged safe-body adoption contract?",
                "full_coverage_path": "Continue resolving 85398 zero-fallback holds and 35 policy types; no production MFA before all types have final selected phones.",
                "staged_safe_body_path": "After the four-sample manual boundary review, explicitly amend the gate for 4384992 safe utterances only; preserve 718364 utterances as follow-up and do not claim full-corpus completion.",
            },
            "decision_2": {
                "question": "Do the four r3 targeted TextGrids have acceptable audio-aligned word/phone boundaries?",
                "review_bundle": "C:\\Users\\ari30\\Dropbox\\REVIEW_r3_TARGETED_4_20260808",
            },
        },
        "methodological_constraints": {
            "same_policy_all_six_years": True,
            "r2_textgrids_relabelled_in_place": False,
            "candidate_phone_is_actual_realization_truth": False,
            "deferred_utterances_deleted": False,
            "broad_pilot_repeated": False,
        },
        "inputs": {
            "readiness_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "routing_manifest": file_fingerprint(routing_manifest_path, with_sha256=True),
            "routing_audit": file_fingerprint(routing_audit_path, with_sha256=True),
            "policy_decision_audit": file_fingerprint(decision_audit_path, with_sha256=True),
            "candidate_manifest": file_fingerprint(candidate_manifest_path, with_sha256=True),
            "candidate_audit": file_fingerprint(candidate_audit_path, with_sha256=True),
            "targeted_regression_audit": file_fingerprint(targeted_audit_path, with_sha256=True),
            "release_gate": file_fingerprint(release_gate_path, with_sha256=True),
            "draft_contract": file_fingerprint(draft_contract_path, with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness-manifest", type=Path, required=True)
    parser.add_argument("--routing-manifest", type=Path, required=True)
    parser.add_argument("--routing-audit", type=Path, required=True)
    parser.add_argument("--decision-audit", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--candidate-audit", type=Path, required=True)
    parser.add_argument("--targeted-audit", type=Path, required=True)
    parser.add_argument("--release-gate", type=Path, default=PROJECT_ROOT / "config" / "mfa_pronunciation_release_gate.json")
    parser.add_argument("--draft-contract", type=Path, default=PROJECT_ROOT / "config" / "common_pronunciation_resource_contract_v3_draft.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        readiness_manifest_path=args.readiness_manifest.resolve(), routing_manifest_path=args.routing_manifest.resolve(),
        routing_audit_path=args.routing_audit.resolve(), decision_audit_path=args.decision_audit.resolve(),
        candidate_manifest_path=args.candidate_manifest.resolve(), candidate_audit_path=args.candidate_audit.resolve(),
        targeted_audit_path=args.targeted_audit.resolve(), release_gate_path=args.release_gate.resolve(),
        draft_contract_path=args.draft_contract.resolve(), output_path=args.output.resolve(),
    )
    print(json.dumps({"status": report["status"], **report["verdict"], **report["coverage"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
