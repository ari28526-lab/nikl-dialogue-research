from __future__ import annotations

import unittest
import json
from pathlib import Path

from scripts.python.build_common_pron_r3_selection_readiness_v4 import (
    ALLOWED_CHANGED_FIELDS,
    NEW_STATUS,
    apply_candidate,
)


class SelectionReadinessV4Tests(unittest.TestCase):
    def test_policy_total_preserves_existing_policy_decision_occurrences(self) -> None:
        policy = json.loads(
            Path("config/common_pron_r3_selection_readiness_v4.json").read_text(
                encoding="utf-8-sig"
            )
        )
        expected = policy["expected_output"]
        self.assertEqual(expected["total_occurrences"], 27_847_068)
        self.assertEqual(
            expected["candidate_ready_occurrences"]
            + expected["zero_fallback_hold_occurrences"]
            + 163,
            expected["total_occurrences"],
        )

    def test_apply_candidate_changes_only_planning_fields(self) -> None:
        row = {
            "token": "식칼",
            "rule_pron_roman": "S I k _ K A l",
            "planning_zero_fallback_hold": "true",
            "planning_candidate_variant_count": "0",
            "planning_candidate_phones_json": "[]",
            "planning_candidate_roman_json": "[]",
            "planning_status": "hold_target_projection_unresolved",
            "planning_source": "zero_fallback_hold",
            "planning_reason": "hold",
            "planning_requires_policy_decision": "false",
            "planning_is_final_selection": "false",
            "planning_candidate_role": "",
            "planning_standard_relation": "unresolved_hold",
            "planning_actual_realization_status": "not_performed",
        }
        from scripts.python.build_common_pron_r3_selection_readiness_v3 import OUTPUT_FIELDS

        for field in OUTPUT_FIELDS:
            row.setdefault(field, "")
        candidate = {
            "planning_candidate_phones_json": '["ɕʰ i k̚ kʰ ɐ ɭ"]',
            "planning_candidate_roman_json": '["S I k _ K A l"]',
        }
        updated = apply_candidate(row, candidate)
        changed = {field for field in OUTPUT_FIELDS if updated[field] != row[field]}
        self.assertTrue(changed <= ALLOWED_CHANGED_FIELDS)
        self.assertEqual(updated["planning_status"], NEW_STATUS)
        self.assertEqual(updated["planning_zero_fallback_hold"], "false")
        self.assertEqual(updated["planning_is_final_selection"], "false")

    def test_non_hold_cannot_be_repromoted(self) -> None:
        row = {
            "token": "식칼",
            "rule_pron_roman": "S I k _ K A l",
            "planning_zero_fallback_hold": "false",
        }
        candidate = {
            "planning_candidate_phones_json": '["ɕʰ i k̚ kʰ ɐ ɭ"]',
            "planning_candidate_roman_json": '["S I k _ K A l"]',
        }
        with self.assertRaises(RuntimeError):
            apply_candidate(row, candidate)


if __name__ == "__main__":
    unittest.main()
