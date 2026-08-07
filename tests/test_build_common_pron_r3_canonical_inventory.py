from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_canonical_inventory import (  # noqa: E402
    classify_selection,
)


def row(**overrides: str) -> dict[str, str]:
    value = {
        "token": "가",
        "current_pron_phones_json": json.dumps(["k ɐ"], ensure_ascii=False),
        "current_pron_roman_json": json.dumps(["G A"], ensure_ascii=False),
        "rule_pron_roman": "G A",
        "comparison_status": "matches_surface_rule",
        "rule_matches_dictionary": "true",
        "current_matches_dictionary": "true",
    }
    value.update(overrides)
    return value


class R3CanonicalInventoryTests(unittest.TestCase):
    def test_exact_rule_selects_only_matching_r2_variants(self) -> None:
        decision = classify_selection(
            row(
                current_pron_phones_json=json.dumps(["k ɐ", "k a"]),
                current_pron_roman_json=json.dumps(["G A", "G EO"]),
            )
        )
        self.assertEqual(decision["status"], "provisional_retain_exact_rule")
        self.assertEqual(decision["phones"], ["k ɐ"])
        self.assertFalse(decision["morph"])

    def test_rule_dictionary_agreement_does_not_invent_backend_phone(self) -> None:
        decision = classify_selection(
            row(
                token="있는",
                rule_pron_roman="I n _ N EU n",
                comparison_status="mismatch_rule_sensitive",
                rule_matches_dictionary="true",
                current_matches_dictionary="false",
            )
        )
        self.assertEqual(
            decision["status"], "candidate_replace_rule_dictionary_agree"
        )
        self.assertEqual(decision["phones"], [])
        self.assertTrue(decision["morph"])

    def test_dictionary_exception_is_candidate_not_automatic_truth(self) -> None:
        decision = classify_selection(
            row(
                comparison_status="mismatch_no_surface_rule_change",
                current_matches_dictionary="true",
                rule_matches_dictionary="false",
            )
        )
        self.assertEqual(
            decision["status"], "candidate_dictionary_supported_exception"
        )
        self.assertEqual(decision["phones"], [])


if __name__ == "__main__":
    unittest.main()
