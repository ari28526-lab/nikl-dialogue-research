from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python"))

import common_pronunciation_contract as contract  # noqa: E402


class CommonPronunciationContractTests(unittest.TestCase):
    def test_parse_tagged_group(self) -> None:
        parsed = contract.parse_tagged_group("있/VV+다/EF")
        self.assertEqual(
            parsed,
            (
                contract.Morph("있", "VV"),
                contract.Morph("다", "EF"),
            ),
        )
        self.assertEqual(contract.morph_signature(parsed), "있/VV+다/EF")

    def test_dictionary_form_predicate_is_occurrence_candidate(self) -> None:
        match = contract.classify_dictionary_candidate(
            token="있다",
            lexicon_pos="VV",
            tagged_group="있/VV+다/EF",
        )
        self.assertEqual(match.match_status, "predicate_dictionary_form_pos")
        self.assertEqual(
            match.occurrence_mfa_status,
            "eligible_occurrence_candidate",
        )

    def test_single_morph_exact_pos_is_occurrence_candidate(self) -> None:
        match = contract.classify_dictionary_candidate(
            token="그것",
            lexicon_pos="NP",
            tagged_group="그것/NP",
        )
        self.assertEqual(match.match_status, "exact_single_morph_pos")

    def test_surface_only_match_does_not_cross_morphology(self) -> None:
        match = contract.classify_dictionary_candidate(
            token="수가",
            lexicon_pos="NNG",
            tagged_group="수/NNB+가/JKS",
        )
        self.assertEqual(
            match.match_status,
            "surface_only_morphologically_composed",
        )
        self.assertEqual(match.occurrence_mfa_status, "reference_only")

    def test_lexical_suga_remains_a_possible_exact_candidate(self) -> None:
        match = contract.classify_dictionary_candidate(
            token="수가",
            lexicon_pos="NNG",
            tagged_group="수가/NNG",
        )
        self.assertEqual(match.match_status, "exact_single_morph_pos")

    def test_global_activation_requires_full_audit(self) -> None:
        status, _ = contract.decide_global_plain_word_activation(
            ["exact_single_morph_pos"],
            full_occurrence_audit_complete=False,
        )
        self.assertEqual(status, "pending_full_occurrence_audit")

    def test_global_activation_blocks_mixed_morphology(self) -> None:
        status, reason = contract.decide_global_plain_word_activation(
            [
                "exact_single_morph_pos",
                "surface_only_morphologically_composed",
            ],
            full_occurrence_audit_complete=True,
        )
        self.assertEqual(
            status,
            "reference_only_mixed_or_unresolved_morphology",
        )
        self.assertIn("surface_only_morphologically_composed:1", reason)

    def test_global_activation_allows_only_fully_compatible_word(self) -> None:
        status, _ = contract.decide_global_plain_word_activation(
            [
                "predicate_dictionary_form_pos",
                "predicate_dictionary_form_pos",
            ],
            full_occurrence_audit_complete=True,
        )
        self.assertEqual(status, "eligible_global_plain_word_candidate")


if __name__ == "__main__":
    unittest.main()
