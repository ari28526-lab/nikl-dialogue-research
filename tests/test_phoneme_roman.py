from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_phoneme_roman_pilot as builder  # noqa: E402
import phoneme_roman as roman  # noqa: E402
from merge_textgrid_v2 import interval_tier  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class PhoneRomanTests(unittest.TestCase):
    def test_model_group_lookup_requires_exact_coverage(self):
        meta = {"phones": ["k", "m"], "phone_groups": {"0": ["k"], "1": ["m"]}}
        self.assertEqual(roman.model_group_lookup(meta), {"k": 0, "m": 1})
        meta["phones"].append("n")
        with self.assertRaisesRegex(RuntimeError, "coverage"):
            roman.model_group_lookup(meta)

    def test_phone_classes_preserve_contrast_and_features(self):
        lookup = {
            "ɡ": 0,
            "kʰː": 0,
            "k͈ʷ": 0,
            "k̚": 0,
            "ɸʷ": 11,
            "ɕ͈": 6,
            "dʑ": 8,
            "ɾ": 13,
            "ɭː": 13,
        }
        expected = {
            "ɡ": "G",
            "kʰː": "K",
            "k͈ʷ": "KK",
            "k̚": "k",
            "ɸʷ": "H",
            "ɕ͈": "SS",
            "dʑ": "J",
            "ɾ": "R",
            "ɭː": "l",
        }
        for phone, label in expected.items():
            self.assertEqual(
                roman.classify_phone(phone, lookup).phone_class_r_auto,
                label,
            )
        self.assertTrue(roman.classify_phone("kʰː", lookup).has_length)
        self.assertEqual(
            roman.classify_phone("k͈ʷ", lookup).secondary_articulation,
            "labialized",
        )
        self.assertTrue(roman.classify_phone("k̚", lookup).unreleased)

    def test_pron_compound_vowels_expand_without_losing_source_token(self):
        units = roman.expand_roman_eojeol("H WA n _ G EU l")
        self.assertEqual(
            [unit.display for unit in units],
            ["H", "W", "A", "n", "G", "EU", "l"],
        )
        wa = [unit for unit in units if unit.source_token == "WA"]
        self.assertEqual([unit.display for unit in wa], ["W", "A"])
        self.assertEqual([unit.component_index for unit in wa], [1, 2])

    def test_alignment_accepts_position_only_difference(self):
        lookup = {"ɸʷ": 11, "o": 16, "k": 0, "ɕ͈": 6, "i": 15}
        phones = [
            roman.classify_phone(phone, lookup)
            for phone in ("ɸʷ", "o", "k", "ɕ͈", "i")
        ]
        refs = roman.expand_roman_eojeol("H O k _ SS I")
        ops = roman.align_phone_to_reference(phones, refs)
        self.assertEqual(
            [op.status for op in ops],
            ["exact", "exact", "position_compatible", "exact", "exact"],
        )

    def test_alignment_exposes_reference_only(self):
        lookup = {"o": 16}
        phones = [roman.classify_phone("o", lookup)]
        refs = roman.expand_roman_eojeol("Y O")
        ops = roman.align_phone_to_reference(phones, refs)
        self.assertEqual([op.status for op in ops], ["reference_only", "exact"])

    def test_five_tier_keeps_original_four_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source.TextGrid"
            destination = temp_root / "output.TextGrid"
            duration = 1.0
            tiers = [
                interval_tier("words", [(0, 0.2, ""), (0.2, 0.8, "가"), (0.8, 1, "")], duration),
                interval_tier("phones_mfa", [(0, 0.2, ""), (0.2, 0.5, "k"), (0.5, 0.8, "ɐ"), (0.8, 1, "")], duration),
                interval_tier("utterance", [(0, 0.2, ""), (0.2, 0.8, "가"), (0.8, 1, "")], duration),
                interval_tier("utterance_search", [(0, 0.2, ""), (0.2, 0.8, "[UTT] x"), (0.8, 1, "")], duration),
            ]
            lines = [
                'File type = "ooTextFile"',
                'Object class = "TextGrid"',
                "",
                "xmin = 0",
                "xmax = 1.000000",
                "tiers? <exists>",
                "size = 4",
                "item []:",
            ]
            for index, tier in enumerate(tiers, 1):
                lines.append(f"    item [{index}]:")
                lines.extend(tier)
            source.write_text("\n".join(lines) + "\n", encoding="utf-8")
            labels = {
                builder.interval_key(0.2, 0.5, "k"): "G",
                builder.interval_key(0.5, 0.8, "ɐ"): "A",
            }
            report = builder.write_five_tier(source, destination, labels)
            self.assertTrue(report["original_four_tiers_unchanged"])
            _, parsed = parse_mfa_textgrid(destination)
            self.assertEqual(list(parsed), builder.FIVE_TIERS)
            self.assertEqual(
                [label for _, _, label in parsed["phoneme_r_auto"]],
                ["", "G", "A", ""],
            )


if __name__ == "__main__":
    unittest.main()
