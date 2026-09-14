from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import audit_a5_b4_legacy_mfa_sharding as b4


def build_status() -> dict[str, Any]:
    state = b4.load_json(b4.STATE) if b4.STATE.is_file() else None
    if state is None:
        return {
            "schema": "a5_b4_legacy_mfa_sharding_status.v1",
            "observed_at": b4.now(),
            "status": "not_started",
            "runner_alive": False,
            "lock_exists": b4.LOCK.exists(),
            "anomalies": [],
        }
    status = state.get("status")
    runner_alive = b4.process_is_alive(state.get("pid"))
    lock_exists = b4.LOCK.exists()
    anomalies: list[str] = []
    if status == "running":
        if not runner_alive:
            anomalies.append("runner_pid_missing")
        if not lock_exists:
            anomalies.append("run_lock_missing")
    elif status == "completed_read_only_design":
        if runner_alive:
            anomalies.append("terminal_state_but_runner_alive")
        if lock_exists:
            anomalies.append("terminal_state_but_live_lock_exists")
    elif status == "failed_safe_to_review":
        if runner_alive:
            anomalies.append("failed_state_but_runner_alive")
    else:
        anomalies.append("unknown_state_status")
    return {
        "schema": "a5_b4_legacy_mfa_sharding_status.v1",
        "observed_at": b4.now(),
        "status": status,
        "phase": state.get("phase"),
        "runner_pid": state.get("pid"),
        "runner_alive": runner_alive,
        "lock_exists": lock_exists,
        "heartbeat": state.get("heartbeat"),
        "source_progress": state.get("source_progress"),
        "errors": state.get("errors", []),
        "external_drive_mutation_performed": state.get("external_drive_mutation_performed"),
        "copy_performed": state.get("copy_performed"),
        "delete_performed": state.get("delete_performed"),
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
