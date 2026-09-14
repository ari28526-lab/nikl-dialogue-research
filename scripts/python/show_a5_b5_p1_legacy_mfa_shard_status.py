from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_a5_b5_p1_legacy_mfa_shard as b5


def build_status() -> dict[str, Any]:
    state = b5.load_json(b5.STATE) if b5.STATE.is_file() else None
    if state is None:
        return {
            "schema": "a5_b5_p1_legacy_mfa_shard_status.v1",
            "observed_at": b5.now(),
            "status": "not_started",
            "runner_alive": False,
            "lock_exists": b5.LOCK.exists(),
            "anomalies": [],
        }
    status = state.get("status")
    alive = b5.b4.process_is_alive(state.get("pid"))
    locked = b5.LOCK.exists()
    anomalies: list[str] = []
    if status == "running":
        if not alive:
            anomalies.append("runner_pid_missing")
        if not locked:
            anomalies.append("run_lock_missing")
    elif status in {"completed_verified", "failed_safe_to_review"}:
        if alive:
            anomalies.append("terminal_state_but_runner_alive")
        if locked:
            anomalies.append("terminal_state_but_live_lock_exists")
    else:
        anomalies.append("unknown_state_status")
    return {
        "schema": "a5_b5_p1_legacy_mfa_shard_status.v1",
        "observed_at": b5.now(),
        "status": status,
        "phase": state.get("phase"),
        "runner_pid": state.get("pid"),
        "runner_alive": alive,
        "lock_exists": locked,
        "heartbeat": state.get("heartbeat"),
        "inventory": state.get("inventory"),
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
