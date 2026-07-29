from __future__ import annotations

import sys
import unittest
from pathlib import Path

from openpyxl import Workbook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_common_pron_researcher_review_xlsx as review  # noqa: E402


class CommonPronResearcherReviewWorkbookTests(unittest.TestCase):
    def test_eulpgo_requires_separate_manual_approved_phone(self) -> None:
        result = review.recommendation_for_no_path(
            {
                "surface": "읊고",
                "respelled": "읍꼬",
                "pron_phones_mfa": "ɨː m k͈ o",
                "rule_id": "standard_pron_rule11_eulpgo_v1",
            }
        )

        self.assertEqual(result["recommended_hangul"], "읍꼬")
        self.assertEqual(result["recommended_phone"], "ɨ p̚ k͈ o")
        self.assertEqual(
            result["recommendation_action"], "manual_phone_override"
        )
        self.assertNotEqual(
            result["recommended_phone"], "ɨː m k͈ o"
        )

    def test_regular_no_path_recommends_frozen_model_candidate(self) -> None:
        candidate = "ɨ m n ɨ n"
        result = review.recommendation_for_no_path(
            {
                "surface": "읊는",
                "respelled": "음는",
                "pron_phones_mfa": candidate,
                "rule_id": "standard_pron_rule18_eulph_nasal_v1",
            }
        )

        self.assertEqual(result["recommended_phone"], candidate)
        self.assertEqual(
            result["recommendation_action"], "accept_model_candidate"
        )
        self.assertIn("제18항", result["reason"])

    def test_jamo_recommendations_keep_source_corrections_explicit(self) -> None:
        expected = {
            "외곬을": (
                "manual_phone_override",
                "legitimate_surface_phonology",
                "w eː ɡ o ɭ s͈ ɨ ɭ",
            ),
            "외곬의": (
                "researcher_audio_choice",
                "legitimate_surface_pronunciation_choice",
                "w eː ɡ o ɭ ɕ͈ i",
            ),
            "외곬수적인": (
                "source_correction_and_audio_choice",
                "source_spelling_correction_required",
                "w eː ɡ o ɭ s͈ u dʑ ʌ ɟ i n",
            ),
            "천구백칤비육": (
                "numeric_placeholder_correction",
                "numeric_placeholder_correction_required",
                (
                    "tɕʰ ʌ ŋ ɡ u b ɛː k̚ tɕʰ i ɭ "
                    "ɕ͈ i m ɲ u k̚"
                ),
            ),
        }

        for token, values in expected.items():
            with self.subTest(token=token):
                result = review.recommendation_for_jamo(token)
                self.assertEqual(result["recommendation_action"], values[0])
                self.assertEqual(result["source_handling"], values[1])
                self.assertEqual(result["recommended_phone"], values[2])

    def test_phone_columns_use_ipa_capable_font(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet["A2"] = "ɨ p̚ k͈ o"

        review.style_phone_columns(
            sheet, columns=("A",), min_row=2, max_row=2
        )

        self.assertEqual(sheet["A2"].font.name, "Noto Sans")
        self.assertEqual(sheet["A2"].value, "ɨ p̚ k͈ o")

    def test_summary_exposes_full_purpose_and_warning_text(self) -> None:
        workbook = Workbook()
        workbook.remove(workbook.active)

        review.populate_summary(workbook, "발음검토")

        sheet = workbook["검토안내"]
        merged = {str(cell_range) for cell_range in sheet.merged_cells.ranges}
        self.assertIn("B3:H3", merged)
        self.assertIn("B4:H4", merged)
        self.assertIn("phone 체계", sheet["B3"].value)
        self.assertIn("자동으로 변경되지 않는다", sheet["B4"].value)


if __name__ == "__main__":
    unittest.main()
