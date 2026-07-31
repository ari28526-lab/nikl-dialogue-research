import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

import predict_pron as pp  # noqa: E402
from morph_schema import (  # noqa: E402
    CODA_COMPONENTS,
    NUCLEUS_COMPONENTS,
    build_utterance_tables,
    tagged_roman_v2,
)


class MorphSchemaPhonologicalMatrixTests(unittest.TestCase):
    def test_all_11172_modern_hangul_syllables_roundtrip(self):
        surface = "".join(chr(code) for code in range(0xAC00, 0xD7A4))
        result = build_utterance_tables(
            {"utt_id": "ALL_HANGUL", "year": "2020", "tagged": f"{surface}/NNG"}
        )
        units = result["morph_units"]
        self.assertEqual(len(units), 11_172)
        self.assertTrue(all(row["unit_type"] == "hangul" for row in units))
        self.assertEqual({row["onset_jamo"] for row in units}, set(pp.CHO))
        self.assertEqual({row["nucleus_jamo"] for row in units}, set(pp.JUNG))
        self.assertEqual({row["coda_jamo"] for row in units}, set(pp.JONG))
        self.assertEqual(sum(bool(row["onset_zero"]) for row in units), 588)
        for row in units:
            self.assertEqual(
                pp.compose(
                    row["onset_jamo"],
                    row["nucleus_jamo"],
                    row["coda_jamo"],
                ),
                row["unit_surface"],
            )

    def test_all_compound_vowels_keep_slot_and_components(self):
        for nucleus, components in NUCLEUS_COMPONENTS.items():
            with self.subTest(nucleus=nucleus):
                syllable = pp.compose("ㄱ", nucleus, "")
                result = build_utterance_tables(
                    {
                        "utt_id": f"VOWEL_{nucleus}",
                        "year": "2020",
                        "tagged": f"{syllable}/NNG",
                    }
                )
                unit = result["morph_units"][0]
                self.assertEqual(unit["nucleus_jamo"], nucleus)
                self.assertEqual(
                    [
                        row["component_jamo"]
                        for row in result["orth_components"]
                        if row["slot"] == "nucleus"
                    ],
                    list(components),
                )

    def test_all_complex_codas_keep_slot_and_components(self):
        for coda, components in CODA_COMPONENTS.items():
            with self.subTest(coda=coda):
                syllable = pp.compose("ㄱ", "ㅏ", coda)
                result = build_utterance_tables(
                    {
                        "utt_id": f"CODA_{coda}",
                        "year": "2020",
                        "tagged": f"{syllable}/NNG",
                    }
                )
                unit = result["morph_units"][0]
                self.assertEqual(unit["coda_jamo"], coda)
                self.assertEqual(
                    [
                        row["component_jamo"]
                        for row in result["orth_components"]
                        if row["slot"] == "coda"
                    ],
                    list(components),
                )

    def test_tense_and_aspirated_onsets_are_atomic_tokens(self):
        surface = "".join(pp.compose(onset, "ㅏ", "") for onset in pp.CHO)
        result = build_utterance_tables(
            {"utt_id": "ONSETS", "year": "2020", "tagged": f"{surface}/NNG"}
        )
        units = result["morph_units"]
        self.assertEqual(
            [row["onset_roman"] for row in units],
            [pp.ONSET_ROMAN[onset] for onset in pp.CHO],
        )
        self.assertEqual(
            sum(bool(row["onset_zero"]) for row in units),
            1,
        )

    def test_standalone_non_coda_tense_jamo_are_not_lost(self):
        result = build_utterance_tables(
            {
                "utt_id": "JAMO",
                "year": "2020",
                "tagged": "ㄴ/NNG+ㄹ/NNG+ㄸ/NNG+ㅃ/NNG+ㅉ/NNG",
            }
        )
        self.assertEqual(
            [row["unit_roman"] for row in result["morph_units"]],
            ["n", "l", "TT", "PP", "JJ"],
        )

    def test_n_insertion_candidate_environment_is_queryable_not_judged(self):
        result = build_utterance_tables(
            {
                "utt_id": "N_INSERTION",
                "year": "2020",
                "tagged": "색/NNG+연필/NNG",
            }
        )
        boundary = result["morph_boundaries"][0]
        self.assertEqual(boundary["boundary_scope"], "intra_eojeol")
        self.assertEqual(boundary["left_coda_jamo"], "ㄱ")
        self.assertTrue(boundary["right_onset_zero"])
        self.assertEqual(boundary["right_nucleus_jamo"], "ㅕ")
        self.assertNotIn("realized", boundary)

    def test_morph_eojeol_hierarchy_and_positions_are_recoverable(self):
        result = build_utterance_tables(
            {
                "utt_id": "HIERARCHY",
                "year": "2020",
                "tagged": "먹/VV+었/EP+다/EF 오늘/NNG",
            }
        )
        morphs = result["morph_tokens"]
        self.assertEqual(
            [
                (
                    row["eojeol_idx"],
                    row["morph_idx_in_eojeol"],
                    row["morph_count_in_eojeol"],
                )
                for row in morphs
            ],
            [(1, 1, 3), (1, 2, 3), (1, 3, 3), (2, 1, 1)],
        )
        self.assertEqual(
            [row["boundary_scope"] for row in result["morph_boundaries"]],
            ["intra_eojeol", "intra_eojeol", "inter_eojeol"],
        )

    def test_hangul_and_latin_are_unambiguous_in_display(self):
        self.assertEqual(
            tagged_roman_v2("아이/NNG AI/SL"),
            "A _ I/NNG | ⟨AI⟩/SL",
        )
        self.assertEqual(
            tagged_roman_v2("가|나/NNG A/B/SL"),
            "G A _ ⟨|⟩ _ N A/NNG | ⟨A/B⟩/SL",
        )


if __name__ == "__main__":
    unittest.main()
