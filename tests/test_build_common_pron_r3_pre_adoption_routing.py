from __future__ import annotations

import unittest

from scripts.python.build_common_pron_r3_pre_adoption_routing import (
    readiness_state,
    routing_class,
)


class PreAdoptionRoutingTests(unittest.TestCase):
    def test_readiness_states_are_mutually_exclusive(self) -> None:
        self.assertEqual(
            readiness_state(
                {
                    "token": "가",
                    "planning_status": "candidate_x",
                    "planning_zero_fallback_hold": "false",
                    "planning_requires_policy_decision": "false",
                }
            ),
            "candidate",
        )
        self.assertEqual(
            readiness_state(
                {
                    "token": "나",
                    "planning_status": "hold_x",
                    "planning_zero_fallback_hold": "true",
                    "planning_requires_policy_decision": "false",
                }
            ),
            "hold",
        )
        self.assertEqual(
            readiness_state(
                {
                    "token": "다",
                    "planning_status": "policy_x",
                    "planning_zero_fallback_hold": "false",
                    "planning_requires_policy_decision": "true",
                }
            ),
            "policy",
        )

    def test_any_unready_token_routes_whole_utterance(self) -> None:
        self.assertEqual(routing_class(set(), set(), set()), "safe")
        self.assertEqual(routing_class({"값"}, set(), set()), "hold")
        self.assertEqual(routing_class({"값"}, {"꽃"}, set()), "hold+policy")
        self.assertEqual(routing_class(set(), set(), {"미등록"}), "unknown")

    def test_candidate_cannot_also_be_hold(self) -> None:
        self.assertEqual(
            routing_class(set(), set(), set(), empty_reference=True),
            "empty_reference",
        )

        with self.assertRaises(RuntimeError):
            readiness_state(
                {
                    "token": "가",
                    "planning_status": "candidate_x",
                    "planning_zero_fallback_hold": "true",
                    "planning_requires_policy_decision": "false",
                }
            )


if __name__ == "__main__":
    unittest.main()
