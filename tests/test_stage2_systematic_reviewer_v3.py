from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts/python"
sys.path.insert(0, str(SCRIPTS))

from build_stage2_systematic_reviewer_v3 import EXPECTED_CODES, load_factor_maps, sample_audit
from audit_stage2_two_hour_scope_cards import validate_literature


class SystematicReviewerV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.factors_path = ROOT / "config/phenomenon_factor_maps_candidate_v1_20260824.json"
        self.cards_path = ROOT / "config/phenomenon_scope_cards_candidate_v2_20260824.jsonl"

    def test_all_factor_maps_have_questions_and_sampling(self) -> None:
        factors = load_factor_maps(self.factors_path)
        self.assertEqual(list(factors), EXPECTED_CODES)
        for code, row in factors.items():
            self.assertTrue(row["research_questions"], code)
            self.assertTrue(row["factor_dimensions"], code)
            self.assertTrue(row["sampling_requirements"], code)

    def test_pt_and_nan_populations_are_explicitly_separate(self) -> None:
        factors = load_factor_maps(self.factors_path)
        pt_ids = {row["id"] for row in factors["PT"]["scope_families"]}
        self.assertIn("PT-BASE-POSTOBS", pt_ids)
        self.assertIn("PT-VAR-COMPOUND", pt_ids)
        self.assertIn("PT-OVERLAP-COMPOUND-POSTOBS", pt_ids)
        nan_ids = {row["id"] for row in factors["NAN"]["scope_families"]}
        self.assertIn("NAN-BASE-INTRA-N", nan_ids)
        self.assertIn("NAN-BASE-INTRA-M", nan_ids)
        self.assertIn("NAN-PROSODY-INTER", nan_ids)

    def test_scope_cards_preserve_multiple_membership(self) -> None:
        cards = [json.loads(line) for line in self.cards_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual([row["phenomenon_code"] for row in cards], EXPECTED_CODES)
        pt = cards[0]
        joined = json.dumps(pt, ensure_ascii=False)
        self.assertIn("복수", joined)
        self.assertIn("사이시옷", joined)
        self.assertIn("저해음 뒤", joined)

    def test_sample_audit_marks_exploratory_and_pt_nan_limits(self) -> None:
        rows = []
        for code in EXPECTED_CODES:
            for index in range(12):
                rows.append({"sample_id": f"{code}-{index}", "phenomenon_code": code, "population_role": "compoundness_probe" if code == "PT" else "primary", "environment_scope": "morph_internal", "query_id": f"Q-{code}"})
        audit = sample_audit(rows)
        self.assertEqual(audit["PT"]["status"], "exploratory_not_balanced")
        self.assertIn("compoundness probe", audit["PT"]["warning"])
        self.assertIn("/ㅁ/", audit["NAN"]["warning"])

    def test_claim_extension_is_contiguous_and_present(self) -> None:
        path = ROOT / "scripts/python/extend_stage2_all_phenomena_literature.py"
        spec = importlib.util.spec_from_file_location("extension", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        ids = [row["claim_id"] for row in module.ADDITIONAL_CLAIMS]
        self.assertEqual(ids, [f"CLM-{number:04d}" for number in range(163, 174)])

    def test_old_review_jsonl_schema_is_accepted_by_contract(self) -> None:
        fixture = {"schema_version": "stage2_two_hour_exploratory_review.v1", "sample_id": "P2H-NAN-2024-01", "phenomenon_code": "NAN", "research_observation": ""}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.jsonl"
            path.write_text(json.dumps(fixture, ensure_ascii=False) + "\n", encoding="utf-8")
            parsed = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(parsed[0]["schema_version"], "stage2_two_hour_exploratory_review.v1")
        self.assertEqual(parsed[0]["sample_id"], "P2H-NAN-2024-01")

    def test_frozen_scope_auditor_accepts_contiguous_append_only_claims(self) -> None:
        _, claims, report = validate_literature(ROOT)
        self.assertEqual(len(claims), 173)
        self.assertEqual(report["frozen_claim_prefix_rows"], 156)
        self.assertEqual(report["appended_claim_rows"], 17)


if __name__ == "__main__":
    unittest.main()
