from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_no_rule_hold_characterization import (  # noqa: E402
    character_profile,
    evidence_stratum,
)


class NoRuleHoldCharacterizationTests(unittest.TestCase):
    def test_character_profile_keeps_digits_and_symbols_separate(self) -> None:
        self.assertEqual(character_profile("둘")["character_stratum"], "hangul_syllables_only")
        self.assertEqual(character_profile("2개")["character_stratum"], "hangul_with_digits")
        self.assertEqual(
            character_profile("2")["character_stratum"],
            "digits_symbols_or_latin_without_hangul",
        )
        self.assertEqual(
            character_profile("가?")["character_stratum"],
            "hangul_with_punctuation_or_symbol",
        )

    def test_jamo_is_not_plain_hangul_syllable(self) -> None:
        self.assertEqual(character_profile("ㄱㅏ")["character_stratum"], "jamo_present")

    def test_evidence_stratum_does_not_call_dictionary_or_g2p_selection(self) -> None:
        self.assertEqual(
            evidence_stratum(
                character_stratum="hangul_syllables_only",
                dictionary_count=1,
                r2_source="korean_mfa_jamo_g2p_v3.2.0_1best_strict",
                variant_count=1,
            ),
            "hangul_dictionary_present_but_not_phone_supported",
        )
        self.assertEqual(
            evidence_stratum(
                character_stratum="hangul_with_digits",
                dictionary_count=0,
                r2_source="korean_mfa_jamo_g2p_v3.2.0_1best_strict",
                variant_count=1,
            ),
            "non_plain_hangul_requires_form_mapping",
        )


if __name__ == "__main__":
    unittest.main()
