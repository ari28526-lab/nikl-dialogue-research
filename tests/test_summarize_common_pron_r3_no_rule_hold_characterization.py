from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from summarize_common_pron_r3_no_rule_hold_characterization import family_hints  # noqa: E402


class NoRuleHoldSummaryTests(unittest.TestCase):
    def test_family_hints_can_be_nonexclusive(self) -> None:
        self.assertEqual(
            family_hints(["SUB:N>NG;RULE_ONLY:W"]),
            {
                "nasal_place_or_boundary_rule_gap",
                "glide_vowel_unitization_or_rule_gap",
                "segment_count_or_deletion_gap",
            },
        )

    def test_laryngeal_and_other_are_not_conflated(self) -> None:
        self.assertEqual(
            family_hints(["SUB:B>P"]),
            {"laryngeal_contrast_or_phone_mapping_gap"},
        )
        self.assertEqual(
            family_hints(["SUB:N>L"]),
            {"other_substitution_or_mixed_gap"},
        )


if __name__ == "__main__":
    unittest.main()
