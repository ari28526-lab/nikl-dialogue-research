from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts/python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(name: str, filename: str):
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUGMENT = load_module(
    "augment_stage2_two_hour_pt_nal_shortfalls",
    "augment_stage2_two_hour_pt_nal_shortfalls.py",
)
CORRECT = load_module(
    "derive_stage2_two_hour_ni_scope_correction",
    "derive_stage2_two_hour_ni_scope_correction.py",
)


class TwoHourShortfallAndScopeCorrectionTests(unittest.TestCase):
    def test_pt_internal_rule_accepts_only_noun_sonorant_to_lenis(self) -> None:
        left = {"unit_type": "hangul", "pos": "NNG", "coda_jamo": "ㄴ"}
        right = {"unit_type": "hangul", "pos": "NNG", "onset_jamo": "ㄷ"}
        self.assertTrue(AUGMENT.pt_rule(left, right))
        self.assertFalse(AUGMENT.pt_rule({**left, "pos": "MAG"}, right))
        self.assertFalse(AUGMENT.pt_rule({**left, "coda_jamo": "ㄱ"}, right))
        self.assertFalse(AUGMENT.pt_rule(left, {**right, "onset_jamo": "ㄴ"}))

    def test_annual_selection_never_reuses_same_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wav = Path(temp_dir) / "target.wav"
            textgrid = Path(temp_dir) / "target.TextGrid"
            wav.write_bytes(b"wav")
            textgrid.write_text("TextGrid", encoding="utf-8")
            base = {
                "year": "2020",
                "timing_status": "linked_test",
                "wav_path": str(wav),
                "active_textgrid_path": str(textgrid),
                "morpheme_combination": "A+B",
                "session_id": "S",
            }
            pool = [
                {**base, "physical_occurrence_ref": "same", "candidate_row_id": "C1"},
                {**base, "physical_occurrence_ref": "same", "candidate_row_id": "C2"},
                {**base, "physical_occurrence_ref": "other", "candidate_row_id": "C3"},
            ]
            selected = AUGMENT.choose_two_per_year(
                pool,
                code="NAL",
                seed="test",
                prefer=lambda row: (0,),
            )
        self.assertEqual(len(selected), 2)
        self.assertEqual({row["physical_occurrence_ref"] for row in selected}, {"same", "other"})

    def test_vcp_surface_branch_distinguishes_overt_i_and_surface_yo(self) -> None:
        evidence = {
            "left_morph_surface": "학생",
            "right_morph_surface": "이",
            "right_pos": "VCP",
            "right_eojeol_idx": "1",
        }
        overt = {
            "active_form": "학생이에요.",
            "match_evidence_json": json.dumps(evidence, ensure_ascii=False),
        }
        surface_yo = {
            "active_form": "학생요.",
            "match_evidence_json": json.dumps(evidence, ensure_ascii=False),
        }
        self.assertEqual(
            CORRECT.vcp_surface_class(overt)["status"],
            "excluded_overt_surface_copular_i",
        )
        self.assertEqual(
            CORRECT.vcp_surface_class(surface_yo)["status"],
            "eligible_surface_yo_analyzer_i_yo",
        )

    def test_scope_correction_refuses_existing_output_before_reading_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "existing"
            output.mkdir()
            missing = Path(temp_dir) / "missing"
            with self.assertRaises(CORRECT.ScopeCorrectionError):
                CORRECT.build(
                    final_path=missing,
                    augment_receipt_path=missing,
                    candidate_path=missing,
                    query_receipt_path=missing,
                    output_dir=output,
                )


if __name__ == "__main__":
    unittest.main()
