import sys
import unicodedata
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from morph_schema import (  # noqa: E402
    MorphSchemaError,
    build_utterance_tables,
    canonicalize_tagged,
    tagged_roman_v2,
)


class MorphSchemaTests(unittest.TestCase):
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

    def test_invalid_reserved_separator_is_not_silently_repaired(self):
        with self.assertRaises(MorphSchemaError):
            build_utterance_tables(
                {"utt_id": "U5", "year": "2020", "tagged": "가/NNG++나/NNG"}
            )


if __name__ == "__main__":
    unittest.main()
