from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_db_v1_target_manifest import row_matches  # noqa: E402


class TargetManifestQueryTests(unittest.TestCase):
    def test_morphophonological_environment_conditions(self):
        row = {
            "left_coda_jamo": "ㄱ",
            "right_onset_zero": "true",
            "right_nucleus_jamo": "ㅣ",
        }
        conditions = [
            {"field": "left_coda_jamo", "op": "nonempty"},
            {"field": "right_onset_zero", "op": "truthy"},
            {"field": "right_nucleus_jamo", "op": "in", "values": ["ㅣ", "ㅑ"]},
        ]
        self.assertTrue(row_matches(row, conditions))
        row["right_nucleus_jamo"] = "ㅏ"
        self.assertFalse(row_matches(row, conditions))

    def test_exact_id_in_condition(self):
        self.assertTrue(
            row_matches(
                {"utt_id": "U1"},
                [{"field": "utt_id", "op": "in", "values": ["U1", "U2"]}],
            )
        )

    def test_absent_field_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "absent"):
            row_matches(
                {"utt_id": "U1"},
                [{"field": "missing", "op": "eq", "value": "x"}],
            )

    def test_truthy_is_not_any_nonempty_string(self):
        conditions = [{"field": "flag", "op": "truthy"}]
        self.assertTrue(row_matches({"flag": "true"}, conditions))
        self.assertFalse(row_matches({"flag": "false"}, conditions))


if __name__ == "__main__":
    unittest.main()
