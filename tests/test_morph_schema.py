import sys
import json
import unicodedata
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from morph_schema import (  # noqa: E402
    MorphSchemaError,
    build_utterance_tables,
    canonicalize_tagged,
    orth_roman_v2,
    parse_tagged,
    tagged_roman_v2,
)


class MorphSchemaTests(unittest.TestCase):
    def test_orth_roman_v2_preserves_mixed_eojeol(self):
        self.assertEqual(
            orth_roman_v2("2사람이 A층"),
            "⟨2⟩ _ S A _ R A m _ I | ⟨A⟩ _ CH EU ng",
        )
        self.assertEqual(orth_roman_v2("사람이?"), "S A _ R A m _ I")

    def test_basic_hierarchy_and_onset_zero(self):
        tagged = "혹시/MAG 요즘/NNG"
        self.assertEqual(
            canonicalize_tagged(tagged),
            "혹시/MAG | 요즘/NNG",
        )
        self.assertEqual(
            tagged_roman_v2(tagged),
            "H O k _ S I/MAG | YO _ J EU m/NNG",
        )
        result = build_utterance_tables(
            {"utt_id": "U1", "year": "2020", "tagged": tagged, "n_morphs": "2"}
        )
        units = result["morph_units"]
        yo = next(row for row in units if row["unit_surface"] == "요")
        self.assertTrue(yo["onset_zero"])
        self.assertEqual(yo["onset_jamo"], "ㅇ")
        self.assertEqual(yo["onset_roman"], "")
        self.assertEqual(len(result["morph_boundaries"]), 1)
        self.assertEqual(
            result["morph_boundaries"][0]["boundary_scope"],
            "inter_eojeol",
        )
        self.assertEqual(
            [
                (row["eojeol_idx"], row["eojeol_form"], row["eojeol_roman"])
                for row in result["eojeol_tokens"]
            ],
            [(1, "혹시", "H O k _ S I"), (2, "요즘", "YO _ J EU m")],
        )

    def test_eojeol_tokens_prefer_explicit_form_and_roman(self):
        result = build_utterance_tables(
            {
                "utt_id": "U1B",
                "year": "2020",
                "form": "그걸",
                "form_roman": "G EU _ G EO l",
                "tagged": "그/NP+ㄹ/JKO",
            }
        )
        row = result["eojeol_tokens"][0]
        self.assertEqual(row["eojeol_form"], "그걸")
        self.assertEqual(row["morph_surface_concat"], "그ㄹ")
        self.assertFalse(row["form_matches_morph_surface"])
        self.assertEqual(row["eojeol_form_source"], "form")
        self.assertEqual(row["eojeol_roman_source"], "form_roman")

    def test_form_tagged_count_mismatch_keeps_both_coordinate_spaces(self):
        result = build_utterance_tables(
            {
                "utt_id": "U1C",
                "year": "2020",
                "form": "나는 그걸 할 수 있어",
                "tagged": "나/NP+는/JX 그거/NP+ㄹ/JKO 하/VV+ㄹ/ETM 수/NNB+있/VA+어/EC",
                "align_warn": "eojeol_tag_mismatch(5!=4)",
            }
        )
        self.assertEqual(len(result["orth_eojeol_tokens"]), 5)
        self.assertEqual(len(result["eojeol_tokens"]), 4)
        self.assertFalse(result["master"]["form_tagged_eojeol_count_equal"])
        self.assertTrue(
            all(
                row["morph_link_status"] == "form_tagged_count_mismatch"
                for row in result["orth_eojeol_tokens"]
            )
        )
        self.assertTrue(
            all(
                row["morph_to_form_status"] == "form_tagged_count_mismatch"
                for row in result["eojeol_tokens"]
            )
        )

    def test_complex_coda_keeps_slot_and_components(self):
        result = build_utterance_tables(
            {
                "utt_id": "U2",
                "year": "2020",
                "tagged": "읽/VV+어/EC",
                "n_morphs": "2",
            }
        )
        unit = result["morph_units"][0]
        self.assertEqual(unit["coda_jamo"], "ㄺ")
        self.assertEqual(unit["coda_roman"], "lk")
        self.assertEqual(unit["coda_components_json"], '["ㄹ","ㄱ"]')
        coda = [
            row
            for row in result["orth_components"]
            if row["slot"] == "coda"
        ]
        self.assertEqual(
            [(row["component_jamo"], row["component_roman"]) for row in coda],
            [("ㄹ", "l"), ("ㄱ", "k")],
        )

    def test_standalone_jamo_and_mixed_literal_keep_order(self):
        tagged = "ㄹ거/ETM A1층/NNG"
        result = build_utterance_tables(
            {"utt_id": "U3", "year": "2021", "tagged": tagged}
        )
        self.assertEqual(
            result["master"]["tagged_roman_v2"],
            "l _ G EO/ETM | ⟨A1⟩ _ CH EU ng/NNG",
        )
        second = [
            row
            for row in result["morph_units"]
            if row["morph_surface"] == "A1층"
        ]
        self.assertEqual(
            [
                (
                    row["unit_surface"],
                    row["unit_type"],
                    row["char_start"],
                    row["char_end"],
                )
                for row in second
            ],
            [("A1", "literal", 0, 2), ("층", "hangul", 2, 3)],
        )

    def test_symbol_reading_uses_source_backed_context_not_global_replacement(self):
        result = build_utterance_tables(
            {
                "utt_id": "U3B",
                "year": "2025",
                "form": "2사람이",
                "tagged": "2/SN+사람/NNG+이/JKS",
                "pron_reference_form": "두 사람이",
                "pron_reference_source": (
                    "original_form_placeholder_resolution"
                ),
                "pron_reference_status": "resolved_original_form",
            }
        )
        symbol = result["symbol_readings"][0]
        self.assertEqual(symbol["symbol_surface"], "2")
        self.assertEqual(symbol["symbol_type"], "digit")
        self.assertEqual(symbol["reference_reading"], "두")
        self.assertEqual(symbol["reference_reading_orth_roman"], "D U")
        self.assertEqual(
            symbol["reading_status"], "resolved_reference_transcription"
        )
        self.assertEqual(
            json.loads(symbol["reading_candidates_json"]),
            ["이", "둘", "두"],
        )
        self.assertTrue(symbol["affects_reference_form"])
        self.assertEqual(result["master"]["symbol_count"], 1)
        self.assertEqual(
            result["master"]["symbol_reading_resolved_count"], 1
        )
        self.assertEqual(
            result["eojeol_tokens"][0]["eojeol_roman_v2"],
            "⟨2⟩ _ S A _ R A m _ I",
        )

    def test_symbol_candidate_does_not_become_selected_without_evidence(self):
        result = build_utterance_tables(
            {
                "utt_id": "U3C",
                "year": "2025",
                "form": "2",
                "tagged": "2/SN",
                "pron_reference_form": "2",
                "pron_reference_source": "form_rule_prediction",
                "pron_reference_status": "unresolved_symbol",
            }
        )
        symbol = result["symbol_readings"][0]
        self.assertEqual(symbol["reference_reading"], "")
        self.assertEqual(symbol["reading_status"], "unresolved_same_literal")
        self.assertIn("둘", json.loads(symbol["reading_candidates_json"]))

    def test_nfd_input_is_nfc_canonicalized(self):
        nfd = unicodedata.normalize("NFD", "꽃")
        result = build_utterance_tables(
            {"utt_id": "U4", "year": "2022", "tagged": f"{nfd}/NNG"}
        )
        self.assertEqual(result["morph_units"][0]["unit_surface"], "꽃")
        self.assertEqual(result["master"]["canonical_tagged"], "꽃/NNG")

    def test_punctuation_is_explicit_literal(self):
        self.assertEqual(
            tagged_roman_v2("어/IC+?/SF"),
            "EO/IC + ⟨?⟩/SF",
        )

    def test_literal_plus_in_bareun_symbol_surface_is_lossless(self):
        tagged = "같/VA+아요/EF+.+/SW"
        parsed = parse_tagged(tagged)
        self.assertEqual(
            [(m.surface, m.pos) for m in parsed[0]],
            [("같", "VA"), ("아요", "EF"), (".+", "SW")],
        )
        result = build_utterance_tables(
            {
                "utt_id": "U_PLUS",
                "year": "2024",
                "form": "같아요.+",
                "tagged": tagged,
                # The legacy source counter counted the literal plus as a
                # delimiter.  Preserve that source value but explain it.
                "n_morphs": "4",
            }
        )
        self.assertEqual(result["master"]["morph_count_structured"], 3)
        self.assertEqual(
            result["master"]["morph_parse_status"],
            "ok_legacy_literal_plus_n_morphs_overcount",
        )
        self.assertTrue(result["master"]["tagged_regeneration_equal"])
        self.assertEqual(result["morph_tokens"][-1]["morph_surface"], ".+")
        self.assertEqual(result["morph_tokens"][-1]["pos"], "SW")

    def test_invalid_reserved_separator_is_not_silently_repaired(self):
        with self.assertRaises(MorphSchemaError):
            build_utterance_tables(
                {"utt_id": "U5", "year": "2020", "tagged": "가/NNG++나/NNG"}
            )


if __name__ == "__main__":
    unittest.main()
