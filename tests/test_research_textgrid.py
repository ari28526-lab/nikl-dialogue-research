import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from research_textgrid import (  # noqa: E402
    validate_research_textgrid,
    write_research_textgrid,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402
from textgrid_labels import (  # noqa: E402
    parse_search_label,
    utterance_search_label,
)


class ResearchTextGridTests(unittest.TestCase):
    def row(self):
        return {
            "utt_id": "U1",
            "form": "혹시 요즘",
            "form_roman": "H O k _ S I | YO _ J EU m",
            "tagged": "혹시/MAG 요즘/NNG",
            "align_warn": "",
        }

    def test_label_roundtrip_and_reserved_marker_escape(self):
        row = self.row()
        row["form_roman"] += " [MORPH] literal"
        label = utterance_search_label(row)
        parsed = parse_search_label(label)
        self.assertEqual(parsed["ORTH_R"], row["form_roman"])
        self.assertIn("\\[MORPH\\]", label)

    def test_writes_four_tiers_with_visible_edge_intervals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "U1.TextGrid"
            validation = write_research_textgrid(
                path,
                duration=1.2,
                words=[
                    (0.0, 0.1, ""),
                    (0.1, 0.5, "혹시"),
                    (0.5, 1.0, "요즘"),
                    (1.0, 1.2, ""),
                ],
                phones=[
                    (0.0, 0.1, ""),
                    (0.1, 0.3, "h"),
                    (0.3, 1.0, "m"),
                    (1.0, 1.2, ""),
                ],
                search_row=self.row(),
            )
            self.assertTrue(validation["valid"])
            checked = validate_research_textgrid(
                path, expected_duration=1.2, expected_row=self.row()
            )
            self.assertTrue(checked["left_empty_boundary"])
            self.assertTrue(checked["right_empty_boundary"])
            duration, tiers = parse_mfa_textgrid(path)
            self.assertEqual(duration, 1.2)
            self.assertEqual(
                list(tiers),
                ["words", "phones_mfa", "utterance", "utterance_search"],
            )
            self.assertEqual(tiers["utterance"][0], (0.0, 0.1, ""))
            self.assertEqual(tiers["utterance"][-1], (1.0, 1.2, ""))

    def test_review_padding_boundary_is_explicit_on_every_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "U1.TextGrid"
            validation = write_research_textgrid(
                path,
                duration=1.2,
                words=[
                    (0.0, 0.2, ""),
                    (0.2, 0.6, "혹시"),
                    (0.6, 1.0, "요즘"),
                    (1.0, 1.2, ""),
                ],
                phones=[
                    (0.0, 0.2, ""),
                    (0.2, 0.5, "h"),
                    (0.5, 1.0, "m"),
                    (1.0, 1.2, ""),
                ],
                search_row=self.row(),
                edge_padding_seconds=0.05,
            )
            self.assertTrue(validation["valid"])
            self.assertTrue(validation["explicit_left_edge_boundary"])
            self.assertTrue(validation["explicit_right_edge_boundary"])
            _duration, tiers = parse_mfa_textgrid(path)
            for tier_name, intervals in tiers.items():
                endpoints = {begin for begin, _, _ in intervals} | {
                    end for _, end, _ in intervals
                }
                self.assertIn(0.05, endpoints, tier_name)
                self.assertIn(1.15, endpoints, tier_name)
                self.assertEqual(intervals[0], (0.0, 0.05, ""))
                self.assertEqual(intervals[-1], (1.15, 1.2, ""))

    def test_padding_gate_rejects_implicit_empty_span(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "U1.TextGrid"
            write_research_textgrid(
                path,
                duration=1.2,
                words=[(0.0, 0.2, ""), (0.2, 1.0, "혹시")],
                phones=[(0.0, 0.2, ""), (0.2, 1.0, "h")],
                search_row=self.row(),
            )
            checked = validate_research_textgrid(
                path,
                expected_duration=1.2,
                expected_row=self.row(),
                expected_edge_padding_seconds=0.05,
            )
            self.assertFalse(checked["valid"])
            self.assertIn(
                "explicit left padding boundary missing: utterance",
                checked["reasons"],
            )


if __name__ == "__main__":
    unittest.main()
