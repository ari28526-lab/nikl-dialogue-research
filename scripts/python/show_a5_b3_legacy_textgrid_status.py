from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_a5_b2_tar_zst_pilot as b2
import run_a5_b3_legacy_textgrid_yearly as b3


def build_status() -> dict[str, Any]:
    state = b2.load_json(b3.STATE) if b3.STATE.is_file() else None
    if state is None:
        return {
            "schema": "a5_b3_legacy_textgrid_yearly_status.v1",
            "observed_at": b2.now(),
            "status": "not_started",
            "runner_alive": False,
            "lock_exists": b3.LOCK.exists(),
            "anomalies": [],
        }
    status = state.get("status")
    phase = state.get("phase")
    runner_alive = b2.process_is_alive(state.get("pid"))
    child_alive = b2.process_is_alive(state.get("child_pid"))
    lock_exists = b3.LOCK.exists()
    anomalies: list[str] = []
    if status == "running":
        if not runner_alive:
            anomalies.append("runner_pid_missing")
        if not lock_exists:
            anomalies.append("run_lock_missing")
        if phase in {"create_archive", "list_archive"} and not child_alive:
            anomalies.append("child_pid_missing")
        archive_partial = state.get("archive_partial")
        if phase == "create_archive" and (
            not isinstance(archive_partial, str) or not Path(archive_partial).is_file()
        ):
            anomalies.append("archive_partial_missing")
    elif status == "completed_verified":
        if runner_alive or child_alive:
            anomalies.append("terminal_state_but_process_alive")
        if lock_exists:
            anomalies.append("terminal_state_but_lock_exists")
        if len(state.get("completed_units", [])) != len(b3.UNITS):
            anomalies.append("verified_state_missing_units")
    elif status == "failed_safe_to_review":
        if runner_alive or child_alive:
            anomalies.append("failed_state_but_process_alive")
    else:
        anomalies.append("unknown_state_status")
    return {
        "schema": "a5_b3_legacy_textgrid_yearly_status.v1",
        "observed_at": b2.now(),
        "status": status,
        "phase": phase,
        "runner_pid": state.get("pid"),
        "runner_alive": runner_alive,
        "child_pid": state.get("child_pid"),
        "child_alive": child_alive,
        "lock_exists": lock_exists,
        "current_year": state.get("current_year"),
        "completed_years": [item.get("year") for item in state.get("completed_units", [])],
        "heartbeat": state.get("heartbeat"),
        "errors": state.get("errors", []),
        "h_mutation_performed": state.get("h_mutation_performed"),
        "e_existing_partial_deletion_performed": state.get("e_existing_partial_deletion_performed"),
        "git_commit_performed": state.get("git_commit_performed"),
        "git_push_performed": state.get("git_push_performed"),
        "anomalies": anomalies,
    }


def main() -> int:
    status = build_status()
    print(json.dumps(status, ensure_ascii=True, separators=(",", ":")))
    return 2 if status["anomalies"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
