from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from build_common_pron_r3_g2p_mismatch_diagnostics import (  # noqa: E402
    edit_signature,
    unit_edit_alignment,
)
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    CONTEXT_LEVELS,
    DonorObservation,
    choose_projection_evidence,
    context_key,
    project_mismatch,
    representation_relation,
    source_projection_route,
    supported_representation_rule_only_indices,
)
from phoneme_roman import classify_phone, expand_roman_eojeol  # noqa: E402


GROUP_LOOKUP = {
    "i": 15,
    "iː": 15,
    "n": 2,
    "nː": 2,
    "ɨ": 20,
    "tɕ͈": 8,
    "tɕ͈ː": 8,
    "t̚": 7,
    "j": 9,
    "ɟ": 0,
    "ʌ": 21,
}


def empty_donor_index():
    return {level: {} for level in CONTEXT_LEVELS}


class R3ProjectionCandidateTests(unittest.TestCase):
    def test_context_key_preserves_syllable_and_word_boundaries(self) -> None:
        rule = tuple(expand_roman_eojeol("I t _ JJ I"))
        key = context_key(rule, 1, "window1_boundary")
        self.assertEqual(key[:3], ("I", "t", "JJ"))
        self.assertEqual(key[3:], (False, True, False, False))

    def test_length_unitization_is_technical_relation_only(self) -> None:
        rule = tuple(expand_roman_eojeol("I n _ N EU n"))
        relation, _ = representation_relation(("i", "nː", "ɨ", "n"), rule, GROUP_LOOKUP)
        self.assertEqual(relation, "equivalent_length_unitization")

    def test_inherent_palatal_phone_absorbs_y_only_in_relation(self) -> None:
        rule = tuple(expand_roman_eojeol("G YEO"))
        relation, _ = representation_relation(("ɟ", "ʌ"), rule, GROUP_LOOKUP)
        self.assertEqual(relation, "equivalent_glide_unitization")

    def test_mixed_row_marks_only_supported_rule_only_edit(self) -> None:
        rule = tuple(expand_roman_eojeol("G YEO _ D A"))
        phones = tuple(classify_phone(phone, GROUP_LOOKUP) for phone in ("ɟ", "ʌ", "tɕ͈", "i"))
        operations = unit_edit_alignment(phones, rule)
        supported = supported_representation_rule_only_indices(operations)
        self.assertIn("secondary_articulation_glide", supported.values())
        self.assertTrue(any(operation.operation == "substitution" for operation in operations))

    def test_donor_requires_unanimous_phone_and_two_target_types(self) -> None:
        rule = tuple(expand_roman_eojeol("I t _ JJ I"))
        index = empty_donor_index()
        key = context_key(rule, 1, "window2_boundary")
        index["window2_boundary"][key] = DonorObservation(
            phone_counts=Counter({"t̚": 3}),
            target_type_count=2,
            unit_count=3,
            examples=["가", "나"],
        )
        evidence = choose_projection_evidence(donor_index=index, rule=rule, rule_index=1)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.phone, "t̚")

        index["window2_boundary"][key].phone_counts["tɕ͈"] = 1
        self.assertIsNone(
            choose_projection_evidence(donor_index=index, rule=rule, rule_index=1)
        )

    def test_substantive_itji_candidate_is_patched_from_exact_context(self) -> None:
        rule_text = "I t _ JJ I"
        rule = tuple(expand_roman_eojeol(rule_text))
        phones = ("iː", "tɕ͈ː", "tɕ͈", "i")
        operations = unit_edit_alignment(
            tuple(classify_phone(phone, GROUP_LOOKUP) for phone in phones), rule
        )
        index = empty_donor_index()
        key = context_key(rule, 1, "window2_boundary")
        index["window2_boundary"][key] = DonorObservation(
            phone_counts=Counter({"t̚": 4}),
            target_type_count=3,
            unit_count=4,
            examples=["닫찌", "맏찌", "읻찌"],
        )
        row = {
            "target_hangul": "읻찌",
            "rule_pron_roman": rule_text,
            "g2p_candidate_phones": " ".join(phones),
            "g2p_candidate_roman": "I JJ JJ I",
            "edit_signature": edit_signature(operations),
            "diagnostic_layer": "substantive_difference_candidate",
        }
        used = {}
        result = project_mismatch(
            row=row,
            donor_index=index,
            group_lookup=GROUP_LOOKUP,
            used_evidence=used,
        )
        self.assertEqual(result["projection_status"], "candidate_exact_context_projection")
        self.assertEqual(json.loads(result["projected_pron_phones_json"]), ["iː t̚ tɕ͈ i"])
        self.assertEqual(result["representation_relation"], "exact_comparison_keys")
        self.assertEqual(len(used), 1)

    def test_candidate_only_edit_stays_held(self) -> None:
        rule_text = "I JJ I"
        rule = tuple(expand_roman_eojeol(rule_text))
        phones = ("i", "n", "tɕ͈", "i")
        operations = unit_edit_alignment(
            tuple(classify_phone(phone, GROUP_LOOKUP) for phone in phones), rule
        )
        row = {
            "target_hangul": "이찌",
            "rule_pron_roman": rule_text,
            "g2p_candidate_phones": " ".join(phones),
            "g2p_candidate_roman": "I N JJ I",
            "edit_signature": edit_signature(operations),
            "diagnostic_layer": "substantive_difference_candidate",
        }
        result = project_mismatch(
            row=row,
            donor_index=empty_donor_index(),
            group_lookup=GROUP_LOOKUP,
            used_evidence={},
        )
        self.assertEqual(
            result["projection_status"], "hold_candidate_only_deletion_requires_policy"
        )
        self.assertEqual(result["projection_candidate_count"], 0)

    def test_source_dictionary_route_is_evidence_not_selection(self) -> None:
        row = {
            "token": "잇고",
            "rule_pron_roman": "I t _ KK O",
            "dictionary_pron_roman_json": json.dumps(["I t _ KK O"]),
            "original_selection_status": "candidate_replace_rule_dictionary_agree",
        }
        route, agreement = source_projection_route(row, target_candidate_count=1)
        self.assertTrue(agreement)
        self.assertEqual(route, "candidate_projection_dictionary_agree")


if __name__ == "__main__":
    unittest.main()
