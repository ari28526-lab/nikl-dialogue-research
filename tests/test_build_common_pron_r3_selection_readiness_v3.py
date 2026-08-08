from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_contextual_dictionary_donor_audit import (  # noqa: E402
    CLASS_MULTIPLE,
    CLASS_UNANIMOUS,
)
from build_common_pron_r3_selection_readiness_v3 import eligible_secondary  # noqa: E402


def classification(category: str = CLASS_UNANIMOUS, variants: str = "1") -> dict[str, str]:
    return {
        "contextual_support_class": category,
        "audited_variant_count": variants,
    }


def evidence(**changes: str) -> dict[str, str]:
    result = {
        "variant_index": "1",
        "relation_kind": "secondary_articulation_cluster",
        "evidence_class": CLASS_UNANIMOUS,
        "current_candidate_supported": "true",
        "current_candidate_phone": "pʲ",
        "canonical_context_level": "",
        "frozen_context_level": "syllable_signature",
    }
    result.update(changes)
    return result


class SelectionReadinessV3Tests(unittest.TestCase):
    def test_only_unchanged_secondary_context_is_eligible(self) -> None:
        self.assertTrue(eligible_secondary(classification(), [evidence()]))

    def test_direct_unit_and_phone_replacement_remain_hold(self) -> None:
        self.assertFalse(
            eligible_secondary(
                classification(), [evidence(relation_kind="direct_unit")]
            )
        )
        self.assertFalse(
            eligible_secondary(
                classification(), [evidence(current_candidate_supported="false")]
            )
        )

    def test_multiple_variants_or_evidence_remain_hold(self) -> None:
        self.assertFalse(eligible_secondary(classification(variants="2"), [evidence()]))
        self.assertFalse(
            eligible_secondary(
                classification(CLASS_MULTIPLE),
                [evidence(evidence_class=CLASS_MULTIPLE)],
            )
        )

    def test_frozen_context_is_required(self) -> None:
        self.assertFalse(
            eligible_secondary(
                classification(), [evidence(frozen_context_level="")]
            )
        )

    def test_zero_issue_hold_is_not_eligible(self) -> None:
        self.assertFalse(eligible_secondary(classification(), []))


if __name__ == "__main__":
    unittest.main()
