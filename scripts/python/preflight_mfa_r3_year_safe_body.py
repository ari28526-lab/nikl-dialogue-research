"""Fail-closed preflight for one release-scoped r3 MFA year."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "mfa_r3_year_safe_body_preflight.v1"


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify(record: dict, path: Path) -> bool:
    return bool(
        Path(clean(record.get("path"))).resolve() == path.resolve()
        and path.is_file()
        and int(record.get("bytes", -1)) == path.stat().st_size
        and clean(record.get("sha256")).lower() == sha256_file(path).lower()
    )


def required_capacity_gib(expected_utterances: int, formula: dict) -> dict:
    per_utterance = sum(
        int(formula[key])
        for key in (
            "temporary_bytes_per_utterance",
            "database_bytes_per_utterance",
            "corpus_lab_and_metadata_bytes_per_utterance",
            "output_and_log_bytes_per_utterance",
        )
    )
    variable_bytes = expected_utterances * per_utterance
    fixed_bytes = float(formula["fixed_overhead_gib"]) * (1024**3)
    required_bytes = math.ceil(
        (variable_bytes + fixed_bytes) * float(formula["safety_multiplier"])
    )
    return {
        "expected_utterances": expected_utterances,
        "per_utterance_bytes": per_utterance,
        "variable_gib": round(variable_bytes / (1024**3), 3),
        "fixed_overhead_gib": float(formula["fixed_overhead_gib"]),
        "safety_multiplier": float(formula["safety_multiplier"]),
        "required_gib": round(required_bytes / (1024**3), 3),
    }


def preflight(
    *,
    year: str,
    policy_path: Path,
    alignment_contract_path: Path,
    alignment_audit_path: Path,
    release_gate_path: Path,
    observed_drive_label: str,
    observed_free_gib: float,
    lock_problem_count: int,
    output_path: Path,
) -> dict:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    policy = load_json(policy_path)
    policy_ok = bool(
        policy.get("schema_version") == "mfa_r3_runner_policy.v1"
        and policy.get("status") == "approved_runner_implementation_gate_controlled"
        and policy.get("safety", {}).get("automatic_full_clean_retry") is False
        and policy.get("safety", {}).get("delete_temp_on_failure") is False
        and policy.get("safety", {}).get("reuse_legacy_marker") is False
        and policy.get("safety", {}).get("reuse_legacy_database") is False
    )
    check("runner_policy", policy_ok, policy.get("status"))
    release_id = clean(policy.get("release_id"))
    check(
        "drive_label",
        observed_drive_label == clean(policy.get("expected_drive_label")),
        {"observed": observed_drive_label, "expected": policy.get("expected_drive_label")},
    )
    check(
        "lock_state_clear",
        lock_problem_count == 0,
        {"lock_problem_count": lock_problem_count},
    )

    contract = load_json(alignment_contract_path)
    alignment_audit = load_json(alignment_audit_path)
    identity = contract.get("identity", {})
    contract_ok = bool(
        contract.get("schema_version") == "mfa_r3_alignment_contract.v1"
        and contract.get("status") == "materialized_pending_runner_preflight_and_release_gate"
        and clean(contract.get("year")) == year
        and clean(identity.get("pronunciation_release_id")) == release_id
        and contract.get("r3_full_realign") is True
        and contract.get("scope", {}).get("legacy_marker_reuse_allowed") is False
        and contract.get("scope", {}).get("legacy_db_reuse_allowed") is False
    )
    check("alignment_contract_identity", contract_ok, contract.get("alignment_contract_id"))
    audit_ok = bool(
        alignment_audit.get("schema_version") == "mfa_r3_alignment_contract_audit.v1"
        and alignment_audit.get("status")
        == "passed_independent_identity_audit_pending_runner_and_release_gate"
        and clean(alignment_audit.get("alignment_contract_id"))
        == clean(contract.get("alignment_contract_id"))
        and alignment_audit.get("verdict", {}).get("identity_recomputed_exact") is True
        and alignment_audit.get("verdict", {}).get("release_gate_remains_closed") is True
        and verify(
            alignment_audit["inputs"]["alignment_contract"], alignment_contract_path
        )
    )
    check("alignment_independent_audit", audit_ok, alignment_audit.get("status"))

    fingerprint_checks = {}
    for label, record in contract.get("models", {}).items():
        path = Path(clean(record.get("path"))).resolve()
        fingerprint_checks[f"model_{label}"] = verify(record, path)
    for label in (
        "expected_mfa_input_ids",
        "pronunciation_followup_ids",
        "pre_mfa_exclusion_ids",
    ):
        record = contract.get("year_input", {}).get(label, {})
        path = Path(clean(record.get("path"))).resolve()
        fingerprint_checks[f"year_input_{label}"] = verify(record, path)
    for name, passed in fingerprint_checks.items():
        check(name, passed, "SHA-256/path/bytes")

    expected = int(contract.get("year_input", {}).get("expected_mfa_input", -1))
    capacity = required_capacity_gib(expected, policy["capacity_formula"])
    check(
        "capacity_formula",
        expected > 0 and observed_free_gib >= capacity["required_gib"],
        {**capacity, "observed_free_gib": observed_free_gib},
    )

    release_root = Path(clean(policy["release_root"])).resolve()
    path_scope_ok = bool(
        release_root.drive.upper() == f"{clean(policy['expected_drive_letter']).upper()}:"
        and release_id in release_root.parts
        and "r3" in tuple(part.lower() for part in release_root.parts)
    )
    check("release_scoped_path", path_scope_ok, str(release_root))
    forbidden: list[str] = []
    if release_root.exists():
        for path in release_root.rglob("*"):
            lower = path.name.lower()
            if "r2" in lower or lower in {"align_done", "merge_done"}:
                forbidden.append(str(path))
                if len(forbidden) >= 20:
                    break
    check("legacy_artifacts_absent", not forbidden, forbidden)

    gate = load_json(release_gate_path)
    required_gate_status = clean(policy["production_gate"]["required_status"])
    gate_ok = bool(
        clean(gate.get("status")) == required_gate_status
        and gate.get("allowed_release_ids") == [release_id]
    )
    check(
        "production_release_gate",
        gate_ok,
        {"status": gate.get("status"), "allowed_release_ids": gate.get("allowed_release_ids")},
    )

    failures = [item["name"] for item in checks if not item["passed"]]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "go" if not failures else "no_go",
        "recorded_at": now_iso(),
        "year": year,
        "release_id": release_id,
        "alignment_contract_id": contract.get("alignment_contract_id"),
        "go": not failures,
        "failed_checks": failures,
        "checks": checks,
        "capacity": capacity,
        "paths": {
            "release_root": str(release_root),
            "corpus_year": str(release_root / "corpus" / year),
            "temporary_root": str(release_root / "temp"),
            "mfa_output_year": str(release_root / "mfa_output" / year),
            "logs": str(release_root / "logs"),
            "markers": str(release_root / "markers"),
        },
        "inputs": {
            "runner_policy": file_fingerprint(policy_path, with_sha256=True),
            "alignment_contract": file_fingerprint(
                alignment_contract_path, with_sha256=True
            ),
            "alignment_independent_audit": file_fingerprint(
                alignment_audit_path, with_sha256=True
            ),
            "release_gate": file_fingerprint(release_gate_path, with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument("--alignment-audit", type=Path, required=True)
    parser.add_argument("--release-gate", type=Path, required=True)
    parser.add_argument("--observed-drive-label", required=True)
    parser.add_argument("--observed-free-gib", type=float, required=True)
    parser.add_argument("--lock-problem-count", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = preflight(
        year=args.year,
        policy_path=args.policy.resolve(),
        alignment_contract_path=args.alignment_contract.resolve(),
        alignment_audit_path=args.alignment_audit.resolve(),
        release_gate_path=args.release_gate.resolve(),
        observed_drive_label=args.observed_drive_label,
        observed_free_gib=args.observed_free_gib,
        lock_problem_count=args.lock_problem_count,
        output_path=args.output.resolve(),
    )
    failed = ",".join(report["failed_checks"]) or "none"
    print(
        f"[{report['status'].upper()}] year={report['year']} "
        f"failed={failed} report={args.output.resolve()}"
    )
    return 0 if report["go"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
