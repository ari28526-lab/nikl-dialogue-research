from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_a5_b2_tar_zst_pilot as pilot


def load_json_retry(path: Path, attempts: int = 5) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    last_error: OSError | json.JSONDecodeError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.1 * attempt)
    raise RuntimeError(f"could not read stable JSON state: {path}") from last_error


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size if path.is_file() else None
    except OSError:
        return None


def build_status() -> dict[str, Any]:
    preflight = load_json_retry(pilot.PREFLIGHT)
    state = load_json_retry(pilot.STATE)
    volumes: dict[str, dict[str, Any]] = {}
    volume_error: str | None = None
    try:
        volumes = {letter: pilot.volume_snapshot(letter) for letter in pilot.EXPECTED_VOLUMES}
    except Exception as exc:
        volume_error = f"{type(exc).__name__}:{exc}"

    if state is None:
        return {
            "schema": "a5_b2_tar_zst_pilot_status.v1",
            "observed_at": pilot.now(),
            "status": "awaiting_explicit_execute_approval",
            "preflight_status": preflight.get("status") if preflight else None,
            "runner_alive": False,
            "child_alive": False,
            "lock_exists": pilot.LOCK.exists(),
            "archive_partial_exists": pilot.ARCHIVE_PARTIAL.exists(),
            "archive_final_exists": pilot.ARCHIVE_FINAL.exists(),
            "volume_identities_match": bool(volumes) and pilot.volumes_are_expected(volumes),
            "volume_error": volume_error,
            "anomalies": [],
        }

    status = state.get("status")
    phase = state.get("phase")
    runner_alive = pilot.process_is_alive(state.get("pid"))
    child_pid = state.get("child_pid")
    child_alive = pilot.process_is_alive(child_pid)
    lock_exists = pilot.LOCK.exists()
    partial_size = _file_size(pilot.ARCHIVE_PARTIAL)
    final_size = _file_size(pilot.ARCHIVE_FINAL)
    heartbeat = state.get("heartbeat") if isinstance(state.get("heartbeat"), dict) else {}
    anomalies: list[str] = []
    volume_identities_match = bool(volumes) and pilot.volumes_are_expected(volumes)
    if not volume_identities_match:
        anomalies.append("volume_identity_or_availability")
    if status == "running":
        if not runner_alive:
            anomalies.append("runner_pid_missing")
        if not lock_exists:
            anomalies.append("run_lock_missing")
        if phase in {"create_archive", "list_archive"} and not child_alive:
            anomalies.append("child_pid_missing")
        if phase == "create_archive" and partial_size is None:
            anomalies.append("archive_partial_missing")
    elif status == "completed_verified":
        if runner_alive or child_alive:
            anomalies.append("terminal_state_but_process_alive")
        if lock_exists:
            anomalies.append("terminal_state_but_lock_exists")
        if final_size is None:
            anomalies.append("verified_final_archive_missing")
    elif status == "failed_safe_to_review":
        if runner_alive or child_alive:
            anomalies.append("failed_state_but_process_alive")
    else:
        anomalies.append("unknown_state_status")

    elapsed = heartbeat.get("elapsed_seconds")
    archive_bytes = heartbeat.get("archive_partial_bytes")
    average_bytes_per_second = None
    if isinstance(elapsed, (int, float)) and elapsed > 0 and isinstance(archive_bytes, int):
        average_bytes_per_second = round(archive_bytes / elapsed, 1)

    return {
        "schema": "a5_b2_tar_zst_pilot_status.v1",
        "observed_at": pilot.now(),
        "status": status,
        "phase": phase,
        "preflight_status": preflight.get("status") if preflight else None,
        "runner_pid": state.get("pid"),
        "runner_alive": runner_alive,
        "child_pid": child_pid,
        "child_alive": child_alive,
        "lock_exists": lock_exists,
        "archive_partial_bytes": partial_size,
        "archive_final_bytes": final_size,
        "heartbeat": heartbeat,
        "average_archive_bytes_per_second": average_bytes_per_second,
        "volume_identities_match": volume_identities_match,
        "volume_error": volume_error,
        "e_free_bytes": volumes.get("E", {}).get("free_bytes"),
        "e_free_floor_bytes": pilot.E_FREE_FLOOR,
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
