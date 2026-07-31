import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from build_morph_combined_search_demo import (  # noqa: E402
    build_queries,
    select_review_results,
)


class MorphCombinedSearchDemoTests(unittest.TestCase):
    def fixture(self):
        masters = [
            {"utt_id": "U1", "year": "2020", "form": "색연필", "align_warn": ""},
            {"utt_id": "U2", "year": "2021", "form": "A1층", "align_warn": "mismatch"},
        ]
        morphs = [
            {
                "utt_id": "U1",
                "year": "2020",
                "morph_surface": "이",
                "pos": "JKS",
                "morph_idx_in_eojeol": "2",
                "morph_count_in_eojeol": "2",
            }
        ]
        units = [
            {
                "utt_id": "U1",
                "year": "2020",
                "morph_surface": "없",
                "pos": "VA",
                "unit_type": "hangul",
                "unit_surface": "없",
                "unit_roman": "EO ps",
                "unit_idx_in_morph": "1",
                "unit_count_in_morph": "1",
                "standalone_jamo": "",
                "nucleus_jamo": "ㅓ",
                "nucleus_components_json": '["ㅓ"]',
                "coda_jamo": "ㅄ",
                "coda_components_json": '["ㅂ","ㅅ"]',
            },
            {
                "utt_id": "U2",
                "year": "2021",
                "morph_surface": "A1",
                "pos": "SL",
                "unit_type": "literal",
                "unit_surface": "A1",
                "unit_roman": "⟨A1⟩",
                "unit_idx_in_morph": "1",
                "unit_count_in_morph": "1",
                "standalone_jamo": "",
                "nucleus_jamo": "",
                "nucleus_components_json": "[]",
                "coda_jamo": "",
                "coda_components_json": "[]",
            },
        ]
        boundaries = [
            {
                "utt_id": "U1",
                "year": "2020",
                "boundary_scope": "intra_eojeol",
                "left_morph_surface": "색",
                "left_pos": "NNG",
                "left_coda_jamo": "ㄱ",
                "right_morph_surface": "연필",
                "right_pos": "NNG",
                "right_onset_zero": "True",
                "right_nucleus_jamo": "ㅕ",
            }
        ]
        return masters, morphs, units, boundaries

    def test_query_matrix_finds_combined_conditions(self):
        masters, morphs, units, boundaries = self.fixture()
        catalog, queries = build_queries(
            masters=masters,
            morphs=morphs,
            units=units,
            boundaries=boundaries,
        )
        self.assertEqual(len(catalog), 7)
        self.assertEqual(len(queries["Q1_N_INSERTION_LIKE"]), 1)
        self.assertEqual(len(queries["Q2_MORPH_POS_POSITION"]), 1)
        self.assertEqual(len(queries["Q3_COMPLEX_CODA"]), 1)
        self.assertEqual(len(queries["Q6_LITERAL_ALIGN_WARN"]), 1)

    def test_selection_requires_real_review_bundle_hit(self):
        masters, morphs, units, boundaries = self.fixture()
        catalog, queries = build_queries(
            masters=masters,
            morphs=morphs,
            units=units,
            boundaries=boundaries,
        )
        with self.assertRaises(RuntimeError):
            select_review_results(
                catalog=catalog,
                queries=queries,
                selected_ids={"U1", "U2"},
                masters_by_id={row["utt_id"]: row for row in masters},
            )


if __name__ == "__main__":
    unittest.main()
