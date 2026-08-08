from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from summarize_common_pron_r3_readiness_v2_residuals import no_rule_pattern_key  # noqa: E402


class ReadinessV2ResidualSummaryTests(unittest.TestCase):
    def test_multiple_variants_keep_every_signature(self) -> None:
        rows = [
            {
                "r2_pron_source": "frozen",
                "diagnostic_status": "one",
                "edit_signature": "SUB:NG>N",
            },
            {
                "r2_pron_source": "frozen",
                "diagnostic_status": "two",
                "edit_signature": "SUB:NG>N;RULE_ONLY:G",
            },
        ]
        self.assertEqual(
            no_rule_pattern_key(rows),
            (
                "frozen",
                "multiple_variant_diagnostics",
                "SUB:NG>N || SUB:NG>N;RULE_ONLY:G",
            ),
        )

    def test_single_variant_preserves_status(self) -> None:
        rows = [
            {
                "r2_pron_source": "g2p",
                "diagnostic_status": "hold_g2p_or_rule_mapping_unresolved",
                "edit_signature": "RULE_ONLY:NG",
            }
        ]
        self.assertEqual(
            no_rule_pattern_key(rows),
            ("g2p", "hold_g2p_or_rule_mapping_unresolved", "RULE_ONLY:NG"),
        )


if __name__ == "__main__":
    unittest.main()
