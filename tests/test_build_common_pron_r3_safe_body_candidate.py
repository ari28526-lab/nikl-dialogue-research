from __future__ import annotations

import unittest

from scripts.python.build_common_pron_r3_safe_body_candidate import parse_variants


class SafeBodyCandidateTests(unittest.TestCase):
    def test_parse_variants_preserves_multiple_pronunciations(self) -> None:
        phones, roman = parse_variants(
            {
                "token": "x",
                "planning_candidate_variant_count": "2",
                "planning_candidate_phones_json": '["a b", "a c"]',
                "planning_candidate_roman_json": '["A B", "A C"]',
            }
        )
        self.assertEqual(phones, ["a b", "a c"])
        self.assertEqual(roman, ["A B", "A C"])

    def test_duplicate_phone_variant_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            parse_variants(
                {
                    "token": "x",
                    "planning_candidate_variant_count": "2",
                    "planning_candidate_phones_json": '["a b", "a b"]',
                    "planning_candidate_roman_json": '["A B", "A B"]',
                }
            )


if __name__ == "__main__":
    unittest.main()
