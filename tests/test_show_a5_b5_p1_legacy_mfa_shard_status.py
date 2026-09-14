from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "show_a5_b5_p1_legacy_mfa_shard_status.py"


def load_module():
    spec = importlib.util.spec_from_file_location("show_a5_b5_p1_legacy_mfa_shard_status", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class B5P1StatusTests(unittest.TestCase):
    def test_running_requires_pid_and_lock(self):
        module = load_module()
        state = {"status": "running", "phase": "create_archive", "pid": 10, "errors": []}
        with tempfile.TemporaryDirectory(dir=module.b5.ROOT) as directory:
            temporary = Path(directory)
            state_path = temporary / "state.json"
            state_path.write_text("{}\n", encoding="utf-8")
            lock_path = temporary / "run.lock"
            with mock.patch.object(module.b5, "STATE", state_path), mock.patch.object(
                module.b5, "LOCK", lock_path
            ), mock.patch.object(module.b5, "load_json", return_value=state), mock.patch.object(
                module.b5.b4, "process_is_alive", return_value=False
            ):
                status = module.build_status()
        self.assertIn("runner_pid_missing", status["anomalies"])
        self.assertIn("run_lock_missing", status["anomalies"])


if __name__ == "__main__":
    unittest.main()
