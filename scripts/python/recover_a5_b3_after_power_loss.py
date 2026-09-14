from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_a5_b2_tar_zst_pilot as b2
import run_a5_b3_legacy_textgrid_yearly as b3


REPORTS = ROOT / "outputs" / "reports"
PREFLIGHT = REPORTS / "PREFLIGHT_B3_power_loss_recovery_20260903.json"
RECEIPT = REPORTS / "APPLY_B3_power_loss_recovery_20260903.json"
APPROVAL_TOKEN = "B3_POWER_LOSS_SAFE_RESUME_APPROVED"


def _state() -> dict[str, Any]:
    return b2.load_json(b3.STATE) if b3.STATE.is_file() else {}


def _current_unit(state: dict[str, Any]) -> dict[str, Any] | None:
    year = state.get("current_year")
    return next((unit for unit in b3.UNITS if unit["year"] == year), None)


def run_preflight() -> dict[str, Any]:
    errors: list[str] = []
    state = _state()
    unit = _current_unit(state)
    paths = b3.unit_paths(unit) if unit else {}
    try:
        volumes = {letter: b2.volume_snapshot(letter) for letter in b2.EXPECTED_VOLUMES}
    except Exception as exc:
        volumes = {}
        errors.append(f"volume_snapshot:{type(exc).__name__}:{exc}")
    try:
        a5_safe, _a5_state = b2.a5_state_is_safe_for_pilot()
    except Exception as exc:
        a5_safe = False
        errors.append(f"a5_state:{type(exc).__name__}:{exc}")
    completed_years = [item.get("year") for item in state.get("completed_units", [])]
    approved_years = [item["year"] for item in b3.UNITS]
    current_year = state.get("current_year")
    expected_completed = approved_years[: approved_years.index(current_year)] if current_year in approved_years else []
    checks = {
        "b3_state_was_running": state.get("status") == "running",
        "b3_phase_was_create_archive": state.get("phase") == "create_archive",
        "known_current_year": unit is not None,
        "completed_years_are_preceding_units": completed_years == expected_completed,
        "runner_pid_dead": not b2.process_is_alive(state.get("pid")),
        "child_pid_dead": not b2.process_is_alive(state.get("child_pid")),
        "stale_lock_present": b3.LOCK.is_file(),
        "current_partial_present": bool(paths) and paths["partial"].is_file(),
        "current_final_absent": bool(paths) and not paths["final"].exists(),
        "current_receipt_absent": bool(paths) and not paths["receipt"].exists(),
        "a5_safe_pause_10_of_12": a5_safe,
        "volume_identities_match": bool(volumes) and b2.volumes_are_expected(volumes),
        "e_capacity_floor_preserved": bool(volumes)
        and int(volumes["E"]["free_bytes"]) >= b3.E_FREE_FLOOR,
    }
    payload = {
        "schema": "a5_b3_power_loss_recovery_preflight.v1",
        "checked_at": b2.now(),
        "status": "passed" if all(checks.values()) and not errors else "failed",
        "approval_required_for_execute": APPROVAL_TOKEN,
        "current_year": current_year,
        "completed_years": completed_years,
        "stale_runner_pid": state.get("pid"),
        "stale_child_pid": state.get("child_pid"),
        "partial_path": str(paths.get("partial", "")),
        "partial_bytes": paths["partial"].stat().st_size if paths and paths["partial"].is_file() else None,
        "checks": checks,
        "volumes": volumes,
        "errors": errors,
        "mutations_performed": False,
    }
    b2.write_json_atomic(PREFLIGHT, payload)
    return payload


def _timestamp_slug() -> str:
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")


def execute_recovery(preflight: dict[str, Any]) -> dict[str, Any]:
    if preflight.get("status") != "passed":
        raise RuntimeError("cannot recover B3 from a failed preflight")
    state = _state()
    unit = _current_unit(state)
    if unit is None:
        raise RuntimeError("current B3 year is not in the approved unit list")
    paths = b3.unit_paths(unit)
    b2.assert_a5_remains_paused()
    b2.assert_expected_volumes()
    if b2.process_is_alive(state.get("pid")) or b2.process_is_alive(state.get("child_pid")):
        raise RuntimeError("a recorded B3 process became live; refusing recovery")
    if not b3.LOCK.is_file() or not paths["partial"].is_file():
        raise RuntimeError("stale lock or interrupted partial disappeared after preflight")
    if paths["final"].exists() or paths["receipt"].exists():
        raise RuntimeError("current final archive or receipt appeared after preflight")

    slug = _timestamp_slug()
    interrupted_partial = paths["partial"].with_name(f"{paths['partial'].name}.interrupted_{slug}")
    interrupted_lock = b3.LOCK.with_name(f"{b3.LOCK.name}.interrupted_{slug}")
    if interrupted_partial.exists() or interrupted_lock.exists():
        raise RuntimeError("interrupted evidence target already exists")

    paths["partial"].rename(interrupted_partial)
    b3.LOCK.rename(interrupted_lock)
    interrupted_state = {
        **state,
        "schema": "a5_b3_power_loss_interruption.v1",
        "status": "failed_safe_to_resume_after_power_loss",
        "phase": "power_loss_recovered_for_restart",
        "pid": None,
        "child_pid": None,
        "updated_at": b2.now(),
        "interrupted_partial_preserved": str(interrupted_partial),
        "interrupted_partial_bytes": interrupted_partial.stat().st_size,
        "interrupted_lock_preserved": str(interrupted_lock),
        "h_mutation_performed": False,
        "e_existing_partial_deletion_performed": False,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
    }
    interrupted_state.setdefault("errors", []).append(
        {
            "at": b2.now(),
            "type": "PowerLossInterruption",
            "message": "recorded runner and child were dead after host shutdown; partial preserved before restart",
        }
    )
    recovery_receipt = {
        "schema": "a5_b3_power_loss_recovery_apply.v1",
        "status": "interrupted_evidence_preserved_restart_pending",
        "recovered_at": b2.now(),
        "current_year": unit["year"],
        "interrupted_partial": str(interrupted_partial),
        "interrupted_partial_bytes": interrupted_partial.stat().st_size,
        "interrupted_lock": str(interrupted_lock),
        "h_mutation_performed": False,
        "e_existing_partial_deletion_performed": False,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "errors": [],
    }
    b2.write_json_atomic(b3.STATE, interrupted_state)
    b2.write_json_atomic(RECEIPT, recovery_receipt)

    restart_log_dir = b3.LOGS / f"resume_{slug}"
    b3.LOGS = restart_log_dir
    recovery_receipt["restart_log_dir"] = str(restart_log_dir)
    restart_preflight = b3.run_preflight()
    if restart_preflight.get("status") != "passed":
        recovery_receipt["status"] = "interrupted_evidence_preserved_restart_preflight_failed"
        recovery_receipt["restart_preflight"] = restart_preflight
        b2.write_json_atomic(RECEIPT, recovery_receipt)
        raise RuntimeError("B3 restart preflight failed after interruption evidence was preserved")
    recovery_receipt["status"] = "restart_started"
    recovery_receipt["restart_preflight"] = restart_preflight
    b2.write_json_atomic(RECEIPT, recovery_receipt)
    result = b3.execute(restart_preflight)
    recovery_receipt["status"] = "restart_completed_verified"
    recovery_receipt["completed_at"] = b2.now()
    recovery_receipt["completed_years"] = [item["year"] for item in result["completed_units"]]
    b2.write_json_atomic(RECEIPT, recovery_receipt)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    args = parser.parse_args()
    if int(args.preflight_only) + int(args.execute) != 1:
        parser.error("choose exactly one of --preflight-only or --execute")
    preflight = run_preflight()
    if preflight["status"] != "passed":
        print(json.dumps(preflight, ensure_ascii=True), flush=True)
        return 2
    print("status=power_loss_recovery_preflight_passed", flush=True)
    if args.preflight_only:
        return 0
    if args.approval_token != APPROVAL_TOKEN:
        print("status=approval_token_required", file=sys.stderr, flush=True)
        return 3
    try:
        result = execute_recovery(preflight)
    except BaseException as exc:
        print(f"status=failed_safe_to_review error={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
        return 1
    print(f"status=completed_verified completed_years={len(result['completed_units'])}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
