from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from resolve_common_pron_r3_surface_donors import (  # noqa: E402
    matching_donor_variants,
)


class R3SurfaceDonorTests(unittest.TestCase):
    def test_keeps_only_exact_target_roman_variants(self) -> None:
        phones, romans = matching_donor_variants(
            target_roman="G A t _ TT A",
            donor_phones=["k ɐ t̚ t͈ ɐ", "k ɐ t̚ tʰ ɐ"],
            donor_romans=["G A t TT A", "G A t T A"],
        )
        self.assertEqual(phones, ["k ɐ t̚ t͈ ɐ"])
        self.assertEqual(romans, ["G A t TT A"])

    def test_rejects_broadly_different_donor(self) -> None:
        phones, romans = matching_donor_variants(
            target_roman="I n _ N EU n",
            donor_phones=["i s͈ n ɨ n"],
            donor_romans=["I SS N EU N"],
        )
        self.assertEqual(phones, [])
        self.assertEqual(romans, [])


if __name__ == "__main__":
    unittest.main()
