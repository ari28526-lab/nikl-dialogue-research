from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "run_a5_b3_legacy_textgrid_yearly.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_a5_b3_legacy_textgrid_yearly", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class B3LegacyTextGridYearlyTests(unittest.TestCase):
    def test_scope_is_exactly_2021_through_2024(self):
        module = load_module()
        self.assertEqual([unit["year"] for unit in module.UNITS], [2021, 2022, 2023, 2024])
        self.assertEqual(sum(unit["expected_files"] for unit in module.UNITS), 3_622_568)
        self.assertEqual(sum(unit["expected_bytes"] for unit in module.UNITS), 21_374_130_960)

    def test_unit_targets_are_separate_and_never_use_b2_2020_name(self):
        module = load_module()
        targets = [module.unit_paths(unit)["final"].name for unit in module.UNITS]
        self.assertEqual(len(targets), len(set(targets)))
        self.assertTrue(all(str(year) in name for year, name in zip(range(2021, 2025), targets, strict=True)))
        self.assertFalse(any("2020" in name for name in targets))

    def test_preflight_requires_all_targets_absent(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            temporary = Path(directory)
            units = (
                {"year": 2021, "name": "legacy_2021", "source": temporary / "source", "expected_files": 1, "expected_bytes": 1},
            )
            units[0]["source"].mkdir()
            destination = temporary / "destination"
            with mock.patch.object(module, "UNITS", units), mock.patch.object(
                module, "DESTINATION_DIR", destination
            ), mock.patch.object(module, "ROOT", temporary):
                checks, _targets = module._target_checks()
                self.assertTrue(all(checks.values()))
                module.unit_paths(units[0])["final"].parent.mkdir(parents=True)
                module.unit_paths(units[0])["final"].write_bytes(b"existing")
                checks, _targets = module._target_checks()
                self.assertFalse(checks["2021_final_absent"])

    def test_execute_requires_exact_approval_token(self):
        module = load_module()
        passed = {"status": "passed"}
        with mock.patch.object(module, "run_preflight", return_value=passed), mock.patch.object(
            module, "execute"
        ) as execute, mock.patch.object(
            module.sys,
            "argv",
            ["b3", "--execute", "--approval-token", "wrong"],
        ):
            exit_code = module.main()
        self.assertEqual(exit_code, 3)
        execute.assert_not_called()

    def test_configure_helpers_uses_current_year_paths(self):
        module = load_module()
        unit = module.UNITS[0]
        paths = module.unit_paths(unit)
        with mock.patch.object(module.b2, "SOURCE", module.b2.SOURCE):
            module.configure_b2_helpers(unit, paths)
            self.assertEqual(module.b2.SOURCE, unit["source"])
            self.assertEqual(module.b2.ARCHIVE_FINAL, paths["final"])
            self.assertEqual(module.b2.STATE, module.STATE)


if __name__ == "__main__":
    unittest.main()
