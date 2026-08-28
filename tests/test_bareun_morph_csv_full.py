from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "scripts" / "python" / "run_bareun_wsd_csv_full.py"
CONFIG_PATH = PROJECT_ROOT / "config" / "bareun_morph_reanalysis_v1.json"
WRAPPER_PATH = PROJECT_ROOT / "run_bareun_morph_csv_full.ps1"
STATUS_PATH = PROJECT_ROOT / "show_bareun_morph_csv_status.ps1"

SPEC = importlib.util.spec_from_file_location("bareun_morph_csv_full", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class BareunMorphCsvFullTest(unittest.TestCase):
    def test_config_is_fresh_morphology_without_wsd(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertFalse(config["api"]["with_sense"])
        self.assertEqual(config["api"]["workers"], 1)
        self.assertEqual(config["api"]["batch_size"], 40)
        self.assertFalse(config["api"]["auto_spacing"])
        self.assertFalse(config["api"]["auto_jointing"])
        self.assertEqual(config["input"]["expected_rows"], 5_103_356)
        self.assertEqual(
            set(config["input"]["ignored_analysis_columns"]), {"tagged", "n_morphs"}
        )
        self.assertIn("12_bareun_morph_v3_1", config["output"]["root"])
        self.assertEqual(RUNNER.analysis_mode(config), "morph")
        self.assertEqual(
            RUNNER.schema_name(config, "manifest"),
            "bareun_morph_csv_full_manifest.v1",
        )

    def test_wrapper_is_explicit_and_powershell_5_1_safe(self) -> None:
        wrapper = WRAPPER_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("BAREUN_MORPH_CSV_FULL_20260828", wrapper)
        self.assertIn("--config", wrapper)
        self.assertIn("bareun_morph_reanalysis_v1.json", wrapper)
        self.assertNotIn("0x80000000", wrapper)
        self.assertNotIn("&&", wrapper)
        self.assertIn("SetThreadExecutionState", wrapper)
        self.assertTrue(STATUS_PATH.is_file())


if __name__ == "__main__":
    unittest.main()
