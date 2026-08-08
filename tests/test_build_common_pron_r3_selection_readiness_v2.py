from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_selection_readiness_v2 import coverage_decision  # noqa: E402


class SelectionReadinessV2Tests(unittest.TestCase):
    def row(self, *, optional: bool = False, frozen: bool = False, ambiguous: bool = False):
        evidence = []
        if optional:
            evidence.append("optional_place_assimilation_not_mandatory_standard")
        if frozen:
            evidence.append("exact_frozen_mfa_dictionary_variant")
        if ambiguous:
            evidence.append("noninjective_phone_to_rule_cooccurrence")
        return {
            "token": "시험",
            "optional_place_assimilation_only": str(optional).lower(),
            "frozen_dictionary_exact_variant": str(frozen).lower(),
            "evidence_labels_json": json.dumps(evidence, ensure_ascii=False),
        }

    def test_all_optional_is_alignment_candidate_not_standard_rule(self) -> None:
        decision = coverage_decision([self.row(optional=True)])
        self.assertTrue(decision["eligible"])
        self.assertEqual(decision["standard_relation"], "optional_variant_not_mandatory_standard")

    def test_all_exact_frozen_is_model_compatible_candidate(self) -> None:
        decision = coverage_decision([self.row(frozen=True)])
        self.assertTrue(decision["eligible"])
        self.assertEqual(decision["planning_status"], "candidate_r2_exact_frozen_dictionary_alignment_variant")

    def test_some_optional_remains_hold(self) -> None:
        decision = coverage_decision([self.row(optional=True), self.row()])
        self.assertFalse(decision["eligible"])
        self.assertEqual(decision["status"], "some_variants_optional_place_assimilation")

    def test_noninjective_phone_alone_never_authorizes_candidate(self) -> None:
        decision = coverage_decision([self.row(ambiguous=True)])
        self.assertFalse(decision["eligible"])
        self.assertEqual(decision["status"], "unresolved_g2p_or_rule_mapping")


if __name__ == "__main__":
    unittest.main()
