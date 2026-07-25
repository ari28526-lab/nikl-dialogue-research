import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_stratified_mfa_review_bundle import (  # noqa: E402
    REVIEW_TIERS,
    write_review_textgrid,
)
from realign_eojeol_merge_output import write_4tier  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class ReviewTextGridTests(unittest.TestCase):
    def test_numeric_internal_slot_receives_original_form_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.TextGrid"
            output = root / "review.TextGrid"
            words = [
                (0.0, 0.1, ""),
                (0.1, 0.4, "무조건"),
                (0.4, 0.5, ""),
                (0.5, 0.9, "층으로"),
                (0.9, 1.0, ""),
            ]
            write_4tier(
                source,
                1.0,
                words,
                [(0.1, 0.9, "p")],
                [
                    (0.1, 0.4, "무조건"),
                    (0.4, 0.5, "1"),
                    (0.5, 0.7, "층"),
                    (0.7, 0.9, "으로"),
                ],
                "무조건 1층으로",
            )
            original_status, pron_status, warning = write_review_textgrid(
                source,
                output,
                form="무조건 1층으로",
                original_form="무조건 일 층으로",
                pron_reference="무조건 일 층으로",
            )
            self.assertEqual(original_status, "all_lexical_slots")
            self.assertEqual(pron_status, "all_lexical_slots")
            self.assertEqual(warning, "")

            duration, tiers = parse_mfa_textgrid(output)
            self.assertEqual(duration, 1.0)
            self.assertEqual(list(tiers), REVIEW_TIERS)
            original_labels = [
                label for _, _, label in tiers["original_form"] if label
            ]
            pron_labels = [
                label for _, _, label in tiers["pron_reference"] if label
            ]
            self.assertEqual(original_labels, ["무조건", "일", "층으로"])
            self.assertEqual(pron_labels, ["무조건", "일", "층으로"])
            self.assertEqual(
                [label for _, _, label in tiers["utterance"]],
                ["", "무조건 1층으로", ""],
            )
            for intervals in tiers.values():
                self.assertEqual(intervals[0][0], 0.0)
                self.assertEqual(intervals[-1][1], 1.0)


if __name__ == "__main__":
    unittest.main()
