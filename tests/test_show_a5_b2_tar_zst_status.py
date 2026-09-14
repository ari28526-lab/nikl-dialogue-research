from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "show_a5_b2_tar_zst_status.py"


def load_module():
    spec = importlib.util.spec_from_file_location("show_a5_b2_tar_zst_status", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class B2StatusTests(unittest.TestCase):
    def test_waiting_status_before_execute_has_no_anomaly(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.pilot.ROOT) as directory:
            temporary = Path(directory)
            preflight = temporary / "preflight.json"
            preflight.write_text(json.dumps({"status": "passed"}), encoding="utf-8")
            volume = {
                "E": {
                    "label": "VERIFIED_ARCHIVE_2TB",
                    "volume_guid": module.pilot.EXPECTED_VOLUMES["E"]["guid"],
                    "filesystem": "NTFS",
                    "free_bytes": 10**12,
                },
                "H": {
                    "label": "SAMSUNG",
                    "volume_guid": module.pilot.EXPECTED_VOLUMES["H"]["guid"],
                    "filesystem": "NTFS",
                    "free_bytes": 10**12,
                },
            }
            with mock.patch.object(module.pilot, "PREFLIGHT", preflight), mock.patch.object(
                module.pilot, "STATE", temporary / "absent_state.json"
            ), mock.patch.object(module.pilot, "LOCK", temporary / "absent.lock"), mock.patch.object(
                module.pilot, "ARCHIVE_PARTIAL", temporary / "absent.partial"
            ), mock.patch.object(module.pilot, "ARCHIVE_FINAL", temporary / "absent.tar.zst"), mock.patch.object(
                module.pilot, "volume_snapshot", side_effect=lambda letter: volume[letter]
            ):
                status = module.build_status()
        self.assertEqual(status["status"], "awaiting_explicit_execute_approval")
        self.assertEqual(status["preflight_status"], "passed")
        self.assertEqual(status["anomalies"], [])

    def test_running_status_flags_missing_runner_and_child(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.pilot.ROOT) as directory:
            temporary = Path(directory)
            state_path = temporary / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "phase": "create_archive",
                        "pid": 111,
                        "child_pid": 222,
                        "heartbeat": {"elapsed_seconds": 10, "archive_partial_bytes": 1000},
                    }
                ),
                encoding="utf-8",
            )
            lock = temporary / "pilot.lock"
            lock.write_text("lock\n", encoding="utf-8")
            archive = temporary / "pilot.partial"
            archive.write_bytes(b"archive")
            volume = {
                "E": {
                    "label": "VERIFIED_ARCHIVE_2TB",
                    "volume_guid": module.pilot.EXPECTED_VOLUMES["E"]["guid"],
                    "filesystem": "NTFS",
                    "free_bytes": 10**12,
                },
                "H": {
                    "label": "SAMSUNG",
                    "volume_guid": module.pilot.EXPECTED_VOLUMES["H"]["guid"],
                    "filesystem": "NTFS",
                    "free_bytes": 10**12,
                },
            }
            with mock.patch.object(module.pilot, "PREFLIGHT", temporary / "absent_preflight.json"), mock.patch.object(
                module.pilot, "STATE", state_path
            ), mock.patch.object(module.pilot, "LOCK", lock), mock.patch.object(
                module.pilot, "ARCHIVE_PARTIAL", archive
            ), mock.patch.object(module.pilot, "ARCHIVE_FINAL", temporary / "absent.tar.zst"), mock.patch.object(
                module.pilot, "volume_snapshot", side_effect=lambda letter: volume[letter]
            ), mock.patch.object(module.pilot, "process_is_alive", return_value=False):
                status = module.build_status()
        self.assertIn("runner_pid_missing", status["anomalies"])
        self.assertIn("child_pid_missing", status["anomalies"])
        self.assertEqual(status["average_archive_bytes_per_second"], 100.0)


if __name__ == "__main__":
    unittest.main()
