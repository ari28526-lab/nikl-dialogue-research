from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_selection_readiness import (  # noqa: E402
    planning_decision,
    projection_source_record,
)


def row(**overrides: str) -> dict[str, str]:
    value = {
        "token": "있는",
        "selection_status": "review_rule_sensitive_no_attested_agreement",
        "selected_pron_phones_json": "[]",
        "selected_pron_roman_json": "[]",
        "candidate_status": "none",
        "candidate_pron_phones_json": "[]",
        "candidate_pron_roman_json": "[]",
        "dictionary_pron_roman_json": "[]",
        "r2_pron_phones_json": json.dumps(["i t̚ n ɨ n"], ensure_ascii=False),
        "r2_pron_roman_json": json.dumps(["I t N EU N"], ensure_ascii=False),
    }
    value.update(overrides)
    return value


def projection(**overrides: str) -> dict[str, str]:
    value = {
        "token": "있는",
        "target_projection_candidate_count": "1",
        "projected_pron_phones_json": json.dumps(["i nː ɨ n"], ensure_ascii=False),
        "projected_pron_roman_json": json.dumps(["I N EU N"], ensure_ascii=False),
        "source_projection_gate_class": "hold_projection_no_independent_dictionary",
        "target_projection_status": "candidate_model_unitization_equivalent_unchanged",
    }
    value.update(overrides)
    return value


class SelectionReadinessTests(unittest.TestCase):
    def test_global_projection_source_precedes_legacy_source(self) -> None:
        global_record = {"path": "global.csv.gz"}
        self.assertIs(
            projection_source_record(
                {
                    "outputs": {
                        "source_projection_candidates": {"path": "legacy.csv.gz"},
                        "source_global_projection": global_record,
                    }
                }
            ),
            global_record,
        )

    def test_projection_source_must_be_explicit(self) -> None:
        with self.assertRaises(RuntimeError):
            projection_source_record({"outputs": {}})

    def test_exact_r2_is_carried_as_candidate_not_selection(self) -> None:
        decision = planning_decision(
            row(
                selection_status="provisional_retain_exact_rule",
                selected_pron_phones_json=json.dumps(["k ɐ"], ensure_ascii=False),
                selected_pron_roman_json=json.dumps(["G A"], ensure_ascii=False),
            ),
            None,
            [],
            [],
        )
        self.assertEqual(decision["status"], "candidate_r2_exact_mandatory_rule")
        self.assertEqual(decision["phones"], ["k ɐ"])
        self.assertFalse(decision["requires_policy"])

    def test_surface_donor_precedes_missing_dictionary(self) -> None:
        decision = planning_decision(
            row(
                candidate_status="surface_donor_exact_rule",
                candidate_pron_phones_json=json.dumps(["k ɐ t̚ k͈ o"], ensure_ascii=False),
                candidate_pron_roman_json=json.dumps(["G A t KK O"], ensure_ascii=False),
            ),
            None,
            [],
            [],
        )
        self.assertEqual(decision["status"], "candidate_surface_donor_exact_mandatory_rule")

    def test_dictionary_exception_keeps_only_attested_r2_variant(self) -> None:
        decision = planning_decision(
            row(
                selection_status="candidate_dictionary_supported_exception",
                dictionary_pron_roman_json=json.dumps(["G A"], ensure_ascii=False),
                r2_pron_phones_json=json.dumps(["k ɐ", "k ʌ"], ensure_ascii=False),
                r2_pron_roman_json=json.dumps(["G A", "G EO"], ensure_ascii=False),
            ),
            None,
            [],
            [],
        )
        self.assertEqual(decision["phones"], ["k ɐ"])
        self.assertEqual(decision["status"], "candidate_r2_dictionary_supported_exception")

    def test_no_rule_technical_relation_can_be_candidate(self) -> None:
        decision = planning_decision(
            row(selection_status="review_no_surface_rule_mismatch"),
            None,
            ["i nː ɨ n"],
            ["I N EU N"],
        )
        self.assertEqual(decision["status"], "candidate_r2_model_unitization_equivalent_no_rule_change")

    def test_no_rule_substantive_mismatch_stays_zero_fallback_hold(self) -> None:
        decision = planning_decision(
            row(selection_status="review_no_surface_rule_mismatch"),
            None,
            [],
            [],
        )
        self.assertEqual(decision["status"], "hold_no_surface_rule_substantive_mismatch")
        self.assertTrue(decision["hold"])

    def test_mandatory_rule_projection_does_not_require_dictionary_listing(self) -> None:
        decision = planning_decision(row(), projection(), [], [])
        self.assertEqual(decision["status"], "candidate_rule_projection_mandatory_rule_no_conflict")
        self.assertEqual(decision["phones"], ["i nː ɨ n"])

    def test_rule_dictionary_conflict_retains_explicit_multiple_variants(self) -> None:
        decision = planning_decision(
            row(
                selection_status="review_rule_dictionary_conflict",
                dictionary_pron_roman_json=json.dumps(["I t N EU N"], ensure_ascii=False),
            ),
            projection(source_projection_gate_class="hold_projection_dictionary_conflict"),
            [],
            [],
        )
        self.assertEqual(decision["status"], "policy_candidate_multiple_rule_dictionary_conflict")
        self.assertEqual(len(decision["phones"]), 2)
        self.assertTrue(decision["requires_policy"])

    def test_unresolved_projection_stays_hold(self) -> None:
        decision = planning_decision(
            row(),
            projection(
                target_projection_candidate_count="0",
                projected_pron_phones_json="[]",
                projected_pron_roman_json="[]",
                source_projection_gate_class="hold_target_projection_unresolved",
            ),
            [],
            [],
        )
        self.assertEqual(decision["status"], "hold_target_projection_unresolved")
        self.assertTrue(decision["hold"])


if __name__ == "__main__":
    unittest.main()
