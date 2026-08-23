from __future__ import annotations

import copy
import importlib.util
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts/python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SCRIPT_PATH = SCRIPT_DIR / "probe_stage2_two_hour_query_candidates.py"
SPEC = importlib.util.spec_from_file_location("probe_stage2_two_hour_query_candidates", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT_PATH}")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class TwoHourQueryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = PROBE.load_json(REPO_ROOT / PROBE.QUERY_CONFIG)

    def test_query_candidate_config_is_complete_and_capped(self) -> None:
        stats = PROBE.validate_query_config(REPO_ROOT, self.config)
        self.assertEqual(set(stats["queries_by_phenomenon"]), set(PROBE.EXPECTED_CODES))
        self.assertEqual(stats["row_cap"], 200000)
        self.assertEqual(stats["candidate_cap"], 50)

    def test_failure_row_cap_increase(self) -> None:
        broken = copy.deepcopy(self.config)
        broken["safety"]["max_rows_scanned_per_table_year"] = 200001
        with self.assertRaises(PROBE.ProbeError):
            PROBE.validate_query_config(REPO_ROOT, broken)

    def test_ni_has_separate_vcp_surface_branch(self) -> None:
        queries = {row["query_id"]: row for row in self.config["queries"]}
        branch = queries["P2H_NI_EXP_VCP_SURFACE_BRANCH_V1"]
        self.assertEqual(branch["population_role"], "surface_branch_probe")
        self.assertIn("표면 이=범위 밖", branch["interpretation"])
        self.assertIn("표면 요+분석 이/VCP+요=요 탐색", branch["interpretation"])

    def test_vcp_candidate_stays_unresolved(self) -> None:
        query = next(row for row in self.config["queries"] if row["query_id"] == "P2H_NI_EXP_VCP_SURFACE_BRANCH_V1")
        row = {
            "candidate_row_id": "C000001",
            "match_evidence_json": '{"left_morph_surface":"편","left_pos":"NNB","right_morph_surface":"이","right_pos":"VCP"}',
            "active_form": "편이에요",
            "inclusion_status": "candidate_ready_for_manual_realization_review",
        }
        output = PROBE.output_candidate(row, query)
        self.assertEqual(output["surface_analysis_status"], "pending_surface_i_vs_yo_roundtrip")
        self.assertEqual(output["selection_status"], "not_selected_pending_two_hour_allocation")

    def test_vcp_selection_uses_surface_form_and_retains_surface_yo(self) -> None:
        evidence = (
            '{"left_morph_surface":"학생","left_pos":"NNG",'
            '"right_morph_surface":"이","right_pos":"VCP","right_eojeol_idx":"1"}'
        )
        base = {
            "query_id": "P2H_NI_EXP_VCP_SURFACE_BRANCH_V1",
            "match_evidence_json": evidence,
        }
        self.assertEqual(
            PROBE.ni_vcp_surface_scope_status({**base, "active_form": "학생요."}),
            "eligible_surface_yo_analyzer_i_yo",
        )
        self.assertEqual(
            PROBE.ni_vcp_surface_scope_status({**base, "active_form": "학생이에요."}),
            "excluded_overt_surface_copular_i",
        )
        self.assertEqual(
            PROBE.ni_vcp_surface_scope_status({**base, "active_form": "표면불일치"}),
            "unresolved_surface_roundtrip",
        )

    def test_synthetic_allocation_is_12_per_phenomenon_two_per_year(self) -> None:
        candidates = []
        sequence = 0
        for code in PROBE.EXPECTED_CODES:
            for year in PROBE.EXPECTED_YEARS:
                for role, count in (("primary", 3), ("peripheral", 1)):
                    for item in range(count):
                        sequence += 1
                        candidates.append(
                            {
                                "candidate_row_id": f"C{sequence:06d}",
                                "phenomenon_code": code,
                                "population_role": role,
                                "priority": "1" if role == "primary" else "2",
                                "environment_scope": "intra_eojeol",
                                "year": str(year),
                                "utt_id": f"{code}{year}.{role}.{item}",
                                "session_id": f"{code}{year}{role}{item}",
                                "speaker_id": "S",
                                "physical_occurrence_ref": f"ref:{code}:{year}:{role}:{item}",
                                "query_id": f"Q_{code}_{role}",
                                "active_form": f"word-{code}-{year}-{role}-{item}",
                                "morpheme_combination": f"morph-{code}-{item}",
                                "word_group": f"word-{code}-{item}",
                                "wav_path": "synthetic.wav",
                                "active_textgrid_path": "synthetic.TextGrid",
                                "surface_analysis_status": "not_yet_manually_verified",
                                "match_evidence_json": "{}",
                                "interpretation_limit": "test only",
                            }
                        )
        original_ready = PROBE.candidate_ready
        original_link = PROBE.link_selected_time
        PROBE.candidate_ready = lambda row: True
        PROBE.link_selected_time = lambda row: {
            **row,
            "timing_status": "linked_single_eojeol_context_span",
            "target_xmin": "0.1",
            "target_xmax": "0.9",
            "target_word_indices_json": "[1]",
            "target_word_labels_json": '["test"]',
        }
        try:
            selected, shortfalls = PROBE.select_samples(candidates, self.config)
        finally:
            PROBE.candidate_ready = original_ready
            PROBE.link_selected_time = original_link
        self.assertEqual(shortfalls, [])
        self.assertEqual(len(selected), 84)
        code_counts = Counter(row["phenomenon_code"] for row in selected)
        self.assertEqual(set(code_counts.values()), {12})
        year_counts = Counter((row["phenomenon_code"], int(row["year"])) for row in selected)
        self.assertEqual(set(year_counts.values()), {2})
        secondary_counts = Counter(row["phenomenon_code"] for row in selected if row["population_role"] != "primary")
        self.assertTrue(all(secondary_counts[code] <= 2 for code in PROBE.EXPECTED_CODES))
        self.assertTrue(all(row["realization_status"] == "not_judged" for row in selected))

    def test_existing_output_stops_before_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "existing"
            output.mkdir()
            with self.assertRaises(PROBE.ProbeError):
                PROBE.build(
                    root=REPO_ROOT,
                    config_path=REPO_ROOT / PROBE.QUERY_CONFIG,
                    morph_root=Path(temp_dir) / "morph",
                    rc0_root=Path(temp_dir) / "rc0",
                    active_view_root=Path(temp_dir) / "active",
                    r3_root=Path(temp_dir) / "r3",
                    output_dir=output,
                )


if __name__ == "__main__":
    unittest.main()
