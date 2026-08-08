from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_g2p_mismatch_diagnostics import unit_edit_alignment  # noqa: E402
from build_common_pron_r3_rule_phone_coverage_audit import (  # noqa: E402
    noninjective_phone_keys,
    optional_place_assimilation_edits,
)
from phoneme_roman import PhoneClass, expand_roman_eojeol  # noqa: E402


def phone(label: str, raw: str | None = None) -> PhoneClass:
    group = {
        "G": "K_GROUP",
        "B": "P_GROUP",
        "CH": "C_GROUP",
        "I": "I_GROUP",
        "O": "O_GROUP",
        "N": "N_GROUP",
        "M": "M_GROUP",
        "NG": "NG_GROUP",
        "H": "H_GROUP",
        "A": "A_GROUP",
        "EO": "EO_GROUP",
        "U": "U_GROUP",
        "J": "C_GROUP",
        "E": "E_GROUP",
        "S": "S_GROUP",
        "P": "P_GROUP",
    }[label]
    return PhoneClass(
        phone_mfa=raw or label,
        phone_class_r_auto=label,
        comparison_key=label,
        model_group_id=0,
        model_group_r=group,
        has_length=False,
        secondary_articulation="",
        unreleased=False,
    )


class RulePhoneCoverageAuditTests(unittest.TestCase):
    def classify(self, labels: list[str], rule_roman: str):
        candidate = tuple(phone(label) for label in labels)
        rule = tuple(expand_roman_eojeol(rule_roman))
        operations = unit_edit_alignment(candidate, rule)
        return optional_place_assimilation_edits(operations, rule)

    def test_chingu_place_assimilation_is_descriptive_only(self) -> None:
        result = self.classify(["CH", "I", "NG", "G", "U"], "CH I n _ G U")
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["interpretation"], "optional_place_assimilation_not_mandatory_standard")

    def test_hanbeon_and_gongbu_place_assimilation(self) -> None:
        self.assertIsNotNone(
            self.classify(["H", "A", "M", "B", "EO", "N"], "H A n _ B EO n")
        )
        self.assertIsNotNone(
            self.classify(["G", "O", "M", "B", "U"], "G O ng _ B U")
        )

    def test_missing_segment_is_not_place_assimilation(self) -> None:
        self.assertIsNone(
            self.classify(["J", "U", "E", "S", "EO"], "J U ng _ E _ S EO")
        )

    def test_laryngeal_substitution_is_not_place_assimilation(self) -> None:
        self.assertIsNone(
            self.classify(["EO", "CH", "A", "B", "I"], "EO _ CH A _ P I")
        )

    def test_noninjective_requires_two_supported_rule_keys(self) -> None:
        pairs = {
            ("pʲ", "B"): {"비", "비가"},
            ("pʲ", "P"): {"피", "피가"},
            ("n", "N"): {"나", "너"},
            ("n", "D"): {"단일예"},
        }
        self.assertEqual(noninjective_phone_keys(pairs), {"pʲ": {"B", "P"}})


if __name__ == "__main__":
    unittest.main()
