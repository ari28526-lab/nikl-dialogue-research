from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from summarize_common_pron_r3_rule_phone_coverage import token_status  # noqa: E402


class RulePhoneCoverageSummaryTests(unittest.TestCase):
    def row(self, *, optional: bool = False, frozen: bool = False) -> dict[str, str]:
        return {
            "optional_place_assimilation_only": str(optional).lower(),
            "frozen_dictionary_exact_variant": str(frozen).lower(),
        }

    def test_noninjective_phone_is_not_a_primary_resolution_status(self) -> None:
        self.assertEqual(token_status([self.row()]), "unresolved_g2p_or_rule_mapping")

    def test_optional_precedes_overlapping_frozen_evidence(self) -> None:
        self.assertEqual(
            token_status([self.row(optional=True, frozen=True)]),
            "all_variants_optional_place_assimilation",
        )

    def test_mixed_optional_remains_explicit(self) -> None:
        self.assertEqual(
            token_status([self.row(optional=True), self.row()]),
            "some_variants_optional_place_assimilation",
        )


if __name__ == "__main__":
    unittest.main()
