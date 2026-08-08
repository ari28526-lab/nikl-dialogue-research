from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import build_common_pron_r3_g2p_agreement_gate as gate  # noqa: E402


class BuildCommonPronR3G2pAgreementGateTests(unittest.TestCase):
    def test_existing_gate_requires_exact_input_key_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "G2P_AGREEMENT_GATE_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "schema_version": gate.SCHEMA_VERSION,
                        "status": "success_candidates_not_selected",
                        "inputs": {},
                        "outputs": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "input contract differs"):
                gate.verify_existing_gate(
                    root,
                    expected_inputs={"target_inventory": root / "missing.csv.gz"},
                )

    def test_target_exact_dictionary_agreement_is_candidate_not_selection(self) -> None:
        self.assertEqual(
            gate.target_gate_class(
                comparison_status="exact_rule_roman",
                statuses={"candidate_replace_rule_dictionary_agree"},
                rewrite_rule="none",
            ),
            "exact_candidate_dictionary_agree_all_sources",
        )

    def test_target_exact_mixed_evidence_is_held(self) -> None:
        self.assertEqual(
            gate.target_gate_class(
                comparison_status="exact_rule_roman",
                statuses={
                    "candidate_replace_rule_dictionary_agree",
                    "review_rule_sensitive_no_attested_agreement",
                },
                rewrite_rule="none",
            ),
            "hold_exact_source_evidence_review",
        )

    def test_rewrite_and_mismatch_never_become_exact_candidates(self) -> None:
        self.assertEqual(
            gate.target_gate_class(
                comparison_status="exact_rule_roman",
                statuses={"candidate_replace_rule_dictionary_agree"},
                rewrite_rule="NFKD repair",
            ),
            "hold_exact_model_input_rewrite",
        )
        self.assertEqual(
            gate.source_gate_class(
                comparison_status="different_rule_roman",
                selection_status="candidate_replace_rule_dictionary_agree",
                rewrite_rule="none",
            ),
            "mismatch_not_eligible",
        )

    def test_source_evidence_routes_stay_distinct(self) -> None:
        expected = {
            "candidate_replace_rule_dictionary_agree": (
                "exact_candidate_dictionary_agree"
            ),
            "review_rule_dictionary_conflict": (
                "hold_exact_dictionary_conflict"
            ),
            "review_rule_sensitive_no_attested_agreement": (
                "hold_exact_no_attested_agreement"
            ),
        }
        for status, route in expected.items():
            with self.subTest(status=status):
                self.assertEqual(
                    gate.source_gate_class(
                        comparison_status="exact_rule_roman",
                        selection_status=status,
                        rewrite_rule="none",
                    ),
                    route,
                )


if __name__ == "__main__":
    unittest.main()
