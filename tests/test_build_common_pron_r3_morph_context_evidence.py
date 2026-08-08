from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_ROOT))

from build_common_pron_r3_morph_context_evidence import split_aligned  # noqa: E402


class MorphContextEvidenceTests(unittest.TestCase):
    def test_split_aligned_preserves_eojeol_boundaries(self) -> None:
        row = {
            "utt_id": "u1",
            "form": "혹시 요즘",
            "tagged": "혹시/MAG 요즘/NNG",
            "n_eojeol": "2",
            "pron_pred_hangul": "혹시 요즘",
            "pron_pred_roman": "H O k _ S I | YO _ J EU m",
        }
        forms, tagged, hangul, roman, tagged_aligned = split_aligned(row)
        self.assertEqual(forms, ["혹시", "요즘"])
        self.assertEqual(tagged, ["혹시/MAG", "요즘/NNG"])
        self.assertEqual(hangul, ["혹시", "요즘"])
        self.assertEqual(roman, ["H O k _ S I", "YO _ J EU m"])
        self.assertTrue(tagged_aligned)

    def test_morph_mismatch_fails_closed(self) -> None:
        row = {
            "utt_id": "u2",
            "form": "혹시 요즘",
            "tagged": "혹시/MAG",
            "n_eojeol": "2",
            "pron_pred_hangul": "혹시 요즘",
            "pron_pred_roman": "H O k _ S I | YO _ J EU m",
        }
        forms, tagged, _, _, tagged_aligned = split_aligned(row)
        self.assertEqual(forms, ["혹시", "요즘"])
        self.assertEqual(tagged, [])
        self.assertFalse(tagged_aligned)

    def test_missing_predictions_are_allowed_but_not_invented(self) -> None:
        row = {
            "utt_id": "u3",
            "form": "혹시",
            "tagged": "혹시/MAG",
            "n_eojeol": "1",
            "pron_pred_hangul": "",
            "pron_pred_roman": "",
        }
        _, _, hangul, roman, tagged_aligned = split_aligned(row)
        self.assertEqual(hangul, [])
        self.assertEqual(roman, [])
        self.assertTrue(tagged_aligned)


if __name__ == "__main__":
    unittest.main()
