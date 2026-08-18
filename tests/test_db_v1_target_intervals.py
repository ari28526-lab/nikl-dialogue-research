from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from link_db_v1_target_intervals import (  # noqa: E402
    normalize_eojeol,
    resolve_boundary_span,
    validate_word_sequence,
)


class TargetIntervalLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.words = [
            (0.1, 0.4, "여행"),
            (0.4, 0.8, "얘기"),
            (0.8, 1.0, "해요"),
        ]

    def test_terminal_punctuation_is_only_display_normalization(self) -> None:
        self.assertEqual(normalize_eojeol("해요."), "해요")
        self.assertEqual(
            validate_word_sequence("여행 얘기 해요.", self.words), self.words
        )

    def test_intra_eojeol_boundary_maps_one_word(self) -> None:
        result = resolve_boundary_span(
            self.words,
            {"left_eojeol_idx": "2", "right_eojeol_idx": "2", "boundary_scope": "intra_eojeol"},
        )
        self.assertEqual(result["target_xmin"], "0.400000000")
        self.assertEqual(result["target_xmax"], "0.800000000")
        self.assertEqual(result["timing_status"], "linked_single_eojeol_context_span")

    def test_inter_eojeol_boundary_maps_context_span(self) -> None:
        result = resolve_boundary_span(
            self.words,
            {"left_eojeol_idx": "1", "right_eojeol_idx": "2", "boundary_scope": "inter_eojeol"},
        )
        self.assertEqual(result["target_xmin"], "0.100000000")
        self.assertEqual(result["target_xmax"], "0.800000000")
        self.assertEqual(result["target_word_indices_json"], "[1, 2]")

    def test_out_of_range_index_fails(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_boundary_span(
                self.words,
                {"left_eojeol_idx": "3", "right_eojeol_idx": "4"},
            )


if __name__ == "__main__":
    unittest.main()
