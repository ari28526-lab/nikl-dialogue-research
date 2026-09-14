from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "show_a5_b3_legacy_textgrid_status.py"


def load_module():
    spec = importlib.util.spec_from_file_location("show_a5_b3_legacy_textgrid_status", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class B3StatusTests(unittest.TestCase):
    def test_running_create_requires_runner_child_lock_and_partial(self):
        module = load_module()
        state = {
            "status": "running",
            "phase": "create_archive",
            "pid": 10,
            "child_pid": 11,
            "archive_partial": "missing.partial",
            "completed_units": [],
            "errors": [],
        }
        with tempfile.TemporaryDirectory(dir=module.b3.ROOT) as directory:
            temporary = Path(directory)
            state_path = temporary / "state.json"
            state_path.write_text("{}\n", encoding="utf-8")
            lock_path = temporary / "run.lock"
            lock_path.write_text("owner\n", encoding="utf-8")
            with mock.patch.object(module.b3, "STATE", state_path), mock.patch.object(
                module.b3, "LOCK", lock_path
            ), mock.patch.object(
                module.b2, "load_json", return_value=state
            ), mock.patch.object(
                module.b2, "process_is_alive", side_effect=lambda pid: pid in {10, 11}
            ):
                status = module.build_status()
        self.assertIn("archive_partial_missing", status["anomalies"])
        self.assertNotIn("runner_pid_missing", status["anomalies"])


if __name__ == "__main__":
    unittest.main()
