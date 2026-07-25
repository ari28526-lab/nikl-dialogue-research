import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from realign_eojeol_merge_output import validate_4tier, write_4tier  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class FourTierValidationTests(unittest.TestCase):
    def test_writer_produces_valid_four_tier_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.TextGrid"
            write_4tier(
                output,
                1.0,
                [(0.0, 1.0, "것을")],
                [(0.0, 0.5, "k"), (0.5, 1.0, "l")],
                [(0.0, 0.5, "것"), (0.5, 1.0, "을")],
                "것을",
            )
            result = validate_4tier(output, expected_dur=1.0)
            self.assertTrue(result["valid"], result["reasons"])

    def test_wrong_tier_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.TextGrid"
            write_4tier(
                output,
                1.0,
                [(0.0, 1.0, "국물")],
                [(0.0, 1.0, "k")],
                [],
                "국물",
            )
            text = output.read_text(encoding="utf-8")
            output.write_text(
                text.replace('name = "phones"', 'name = "phonez"', 1),
                encoding="utf-8",
            )
            self.assertFalse(validate_4tier(output)["valid"])

    def test_duration_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.TextGrid"
            write_4tier(
                output,
                1.0,
                [(0.0, 1.0, "국물")],
                [(0.0, 1.0, "k")],
                [],
                "국물",
            )
            self.assertFalse(validate_4tier(output, expected_dur=2.0)["valid"])

    def test_writer_adds_outer_empty_intervals_to_utterance(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.TextGrid"
            write_4tier(
                output,
                1.0,
                [(0.2, 0.8, "국물")],
                [(0.2, 0.5, "k"), (0.5, 0.8, "m")],
                [(0.2, 0.8, "국물")],
                "국물",
            )
            duration, tiers = parse_mfa_textgrid(output)
            self.assertEqual(duration, 1.0)
            self.assertEqual(
                tiers["utterance"],
                [(0.0, 0.2, ""), (0.2, 0.8, "국물"), (0.8, 1.0, "")],
            )
            for intervals in tiers.values():
                self.assertEqual(intervals[0][0], 0.0)
                self.assertEqual(intervals[-1][1], 1.0)


if __name__ == "__main__":
    unittest.main()
