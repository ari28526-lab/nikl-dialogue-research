from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import build_common_pron_r3_g2p_mismatch_diagnostics as diagnostic  # noqa: E402
from phoneme_roman import PhoneClass, RomanUnit  # noqa: E402


def phone(label: str, *, key: str | None = None, length: bool = False, group: str = "N_GROUP") -> PhoneClass:
    return PhoneClass(
        phone_mfa=f"/{label}/" + ("ː" if length else ""),
        phone_class_r_auto=label,
        comparison_key=key or label,
        model_group_id=2,
        model_group_r=group,
        has_length=length,
        secondary_articulation="",
        unreleased=False,
    )


def rule(label: str, *, key: str | None = None) -> RomanUnit:
    return RomanUnit(
        display=label,
        comparison_key=key or label,
        source_token=label,
        syllable_index=1,
        token_index_in_syllable=1,
        component_index=1,
        component_count=1,
    )


class BuildMismatchDiagnosticsTests(unittest.TestCase):
    def test_length_supported_adjacent_identical_is_candidate_only(self) -> None:
        candidate = [phone("N", length=True), phone("EU", group="EU_GROUP")]
        reference = [rule("n", key="N"), rule("N"), rule("EU")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(diagnostic.operation_edit_distance(operations), 1)
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations),
            (
                "representation_equivalence_candidate",
                "length_supported_adjacent_identical_coalescence",
                True,
            ),
        )

    def test_unmarked_run_length_difference_is_not_equivalent(self) -> None:
        candidate = [phone("N"), phone("EU", group="EU_GROUP")]
        reference = [rule("n", key="N"), rule("N"), rule("EU")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations)[1],
            "run_length_difference_without_complete_length_support",
        )

    def test_explicit_labialization_can_encode_w_glide(self) -> None:
        candidate = [
            phone("G", group="K_GROUP"),
            phone("A", group="A_GROUP"),
        ]
        candidate[0] = PhoneClass(
            **{**candidate[0].__dict__, "phone_mfa": "ɡʷ"}
        )
        reference = [rule("G"), rule("W"), rule("A")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations),
            (
                "representation_equivalence_candidate",
                "secondary_articulation_encodes_glide",
                True,
            ),
        )

    def test_inherent_palatal_phone_can_encode_y_glide(self) -> None:
        candidate = [phone("G", group="K_GROUP"), phone("EO", group="EO_GROUP")]
        candidate[0] = PhoneClass(
            **{**candidate[0].__dict__, "phone_mfa": "ɟ"}
        )
        reference = [rule("G"), rule("Y"), rule("EO")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations)[1],
            "secondary_articulation_encodes_glide",
        )

    def test_unmarked_y_gap_remains_substantive_candidate(self) -> None:
        candidate = [phone("G", group="K_GROUP"), phone("EO", group="EO_GROUP")]
        reference = [rule("G"), rule("Y"), rule("EO")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations)[1],
            "single_rule_unit_missing_from_candidate",
        )

    def test_single_within_group_contrast_stays_review(self) -> None:
        candidate = [phone("JJ", group="C_GROUP")]
        reference = [rule("J")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(diagnostic.edit_signature(operations), "SUB:JJ>J")
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations)[:2],
            (
                "contrast_review_required",
                "single_contrast_within_acoustic_model_group",
            ),
        )

    def test_single_cross_group_substitution_is_substantive_candidate(self) -> None:
        candidate = [phone("JJ", group="C_GROUP")]
        reference = [rule("D")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations)[:2],
            (
                "substantive_difference_candidate",
                "single_cross_group_substitution",
            ),
        )

    def test_gap_direction_is_explicit(self) -> None:
        candidate = [phone("N")]
        reference = [rule("N"), rule("EU")]
        operations = diagnostic.unit_edit_alignment(candidate, reference)
        self.assertEqual(diagnostic.edit_signature(operations), "RULE_ONLY:EU")
        self.assertEqual(
            diagnostic.classify_diagnostic(candidate, reference, operations)[1],
            "single_rule_unit_missing_from_candidate",
        )


if __name__ == "__main__":
    unittest.main()
