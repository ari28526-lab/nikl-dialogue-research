from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "python" / "preflight_bareun_wsd_environment.py"
SPEC = importlib.util.spec_from_file_location("bareun_wsd_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BareunWsdPreflightTest(unittest.TestCase):
    def test_secret_file_is_loaded_but_source_label_has_no_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            secret_path = Path(temporary) / "bareun_api.txt"
            placeholder = "koba-test-only-placeholder"
            secret_path.write_text(placeholder + "\n", encoding="utf-8")
            config = {
                "environment_variable": "BAREUN_WSD_TEST_KEY_NOT_SET",
                "candidate_files": [str(secret_path)],
            }
            old_value = os.environ.pop(config["environment_variable"], None)
            try:
                key, source = MODULE.load_api_key(config)
            finally:
                if old_value is not None:
                    os.environ[config["environment_variable"]] = old_value
            self.assertEqual(key, placeholder)
            self.assertEqual(source, "file:bareun_api.txt")
            self.assertNotIn(placeholder, source)

    def test_inventory_handles_quoted_embedded_newline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "sample.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["utt_id", "speaker_id", "form"],
                )
                writer.writeheader()
                writer.writerow(
                    {"utt_id": "u1", "speaker_id": "s1", "form": "첫 줄\n둘째 줄"}
                )
                writer.writerow(
                    {"utt_id": "u2", "speaker_id": "s2", "form": "세 어절 문장"}
                )
            result = MODULE.inventory_csv(root, full_scan=True)
            self.assertEqual(result["csv_files"], 1)
            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["input_eojeol"], 7)
            self.assertEqual(result["missing_required_columns_files"], 0)

    def test_report_serialization_never_needs_secret_value(self) -> None:
        public_secret_status = {"available": True, "source": "file:bareun_api.txt"}
        serialized = json.dumps(public_secret_status)
        self.assertNotIn("koba-test-only-placeholder", serialized)


if __name__ == "__main__":
    unittest.main()
