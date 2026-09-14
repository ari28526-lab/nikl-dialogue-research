from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "recover_a5_b3_after_power_loss.py"


def load_module():
    spec = importlib.util.spec_from_file_location("recover_a5_b3_after_power_loss", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecoverB3AfterPowerLossTests(unittest.TestCase):
    def test_current_unit_rejects_unknown_year(self):
        module = load_module()
        self.assertIsNone(module._current_unit({"current_year": 2020}))
        self.assertEqual(module._current_unit({"current_year": 2022})["year"], 2022)

    def test_execute_requires_exact_approval_token(self):
        module = load_module()
        with mock.patch.object(module, "run_preflight", return_value={"status": "passed"}), mock.patch.object(
            module, "execute_recovery"
        ) as execute, mock.patch.object(
            module.sys, "argv", ["recover", "--execute", "--approval-token", "wrong"]
        ):
            exit_code = module.main()
        self.assertEqual(exit_code, 3)
        execute.assert_not_called()

    def test_preflight_rejects_any_live_recorded_process(self):
        module = load_module()
        unit = module.b3.UNITS[0]
        state = {
            "status": "running",
            "phase": "create_archive",
            "current_year": unit["year"],
            "pid": 10,
            "child_pid": 11,
            "completed_units": [],
        }
        fake_volumes = {
            "E": {"label": "VERIFIED_ARCHIVE_2TB", "volume_guid": module.b2.EXPECTED_VOLUMES["E"]["guid"], "filesystem": "NTFS", "free_bytes": 10**12},
            "H": {"label": "SAMSUNG", "volume_guid": module.b2.EXPECTED_VOLUMES["H"]["guid"], "filesystem": "NTFS", "free_bytes": 10**12},
        }
        with mock.patch.object(module, "_state", return_value=state), mock.patch.object(
            module.b3, "unit_paths", return_value={
                "partial": mock.Mock(is_file=mock.Mock(return_value=True), stat=mock.Mock(return_value=mock.Mock(st_size=1))),
                "final": mock.Mock(exists=mock.Mock(return_value=False)),
                "receipt": mock.Mock(exists=mock.Mock(return_value=False)),
            }
        ), mock.patch.object(module.b2, "volume_snapshot", side_effect=lambda letter: fake_volumes[letter]), mock.patch.object(
            module.b2, "a5_state_is_safe_for_pilot", return_value=(True, {})
        ), mock.patch.object(module.b2, "process_is_alive", side_effect=lambda pid: pid == 10), mock.patch.object(
            module.b3, "LOCK", mock.Mock(is_file=mock.Mock(return_value=True))
        ), mock.patch.object(module.b2, "write_json_atomic", return_value=None):
            result = module.run_preflight()
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["runner_pid_dead"])


if __name__ == "__main__":
    unittest.main()
