from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BUILDER_PATH = SCRIPT_DIR / "build_bareun_morph_textgrid_pilot.py"
CONFIG_PATH = PROJECT_ROOT / "config" / "bareun_morph_textgrid_pilot_v1.json"

SPEC = importlib.util.spec_from_file_location("build_bareun_morph_textgrid_pilot", BUILDER_PATH)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

from research_textgrid_v2 import BASE_TIERS, parse_mfa_textgrid, write_textgrid_exact


class BareunMorphTextGridPilotTest(unittest.TestCase):
    def test_config_is_balanced_and_read_only(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["input"]["expected_years"], [str(y) for y in range(2020, 2026)])
        self.assertEqual(config["selection"]["changed_per_year"], 1)
        self.assertEqual(config["selection"]["unchanged_per_year"], 1)
        self.assertTrue(config["contract"]["source_textgrid_read_only"])
        self.assertTrue(config["contract"]["source_wav_read_only"])
        self.assertFalse(config["contract"]["mfa_rerun"])
        self.assertEqual(config["contract"]["tier_order"], BASE_TIERS)

    def test_build_new_morph_label_uses_token_and_global_morph_indices(self) -> None:
        rows = [
            {"token_index": "0", "morph_index": "0", "morph_surface": "가", "pos": "VV"},
            {"token_index": "0", "morph_index": "1", "morph_surface": "아", "pos": "EC"},
            {"token_index": "1", "morph_index": "2", "morph_surface": "집", "pos": "NNG"},
        ]
        label, count = BUILDER.build_new_morph_label(rows, 2)
        self.assertEqual(label, "가/VV + 아/EC | 집/NNG")
        self.assertEqual(count, 3)

    def test_derive_updates_only_morph_label_and_preserves_boundaries(self) -> None:
        tier_data = [
            ("words", [(0.0, 0.1, ""), (0.1, 0.6, "가"), (0.6, 1.0, "")]),
            ("phones_mfa", [(0.0, 0.1, ""), (0.1, 0.6, "k"), (0.6, 1.0, "")]),
            ("phoneme_r_auto", [(0.0, 0.1, ""), (0.1, 0.6, "ㄱ"), (0.6, 1.0, "")]),
            ("utterance", [(0.0, 0.1, ""), (0.1, 0.6, "가"), (0.6, 1.0, "")]),
            ("utterance_orth_r", [(0.0, 0.1, ""), (0.1, 0.6, "ga"), (0.6, 1.0, "")]),
            ("morph_analysis_utt", [(0.0, 0.1, ""), (0.1, 0.6, "가/NNG"), (0.6, 1.0, "")]),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.TextGrid"
            derived = Path(temp_dir) / "derived.TextGrid"
            write_textgrid_exact(source, duration=1.0, tier_data=tier_data)
            source_sha = BUILDER.sha256_file(source)
            result = BUILDER.derive_textgrid(source, derived, "가/VV")
            self.assertEqual(BUILDER.sha256_file(source), source_sha)
            self.assertTrue(result["first_five_unchanged"])
            self.assertTrue(result["morph_boundaries_unchanged"])
            _, source_tiers = parse_mfa_textgrid(source)
            _, derived_tiers = parse_mfa_textgrid(derived)
            for name in BASE_TIERS[:5]:
                self.assertTrue(BUILDER.same_intervals(source_tiers[name], derived_tiers[name]))
            self.assertEqual(BUILDER.one_labeled_interval(derived_tiers["morph_analysis_utt"], "morph")[1], "가/VV")

    def test_noncontiguous_indices_fail_closed(self) -> None:
        rows = [
            {"token_index": "0", "morph_index": "0", "morph_surface": "가", "pos": "VV"},
            {"token_index": "2", "morph_index": "1", "morph_surface": "집", "pos": "NNG"},
        ]
        with self.assertRaises(ValueError):
            BUILDER.build_new_morph_label(rows, 2)


if __name__ == "__main__":
    unittest.main()
