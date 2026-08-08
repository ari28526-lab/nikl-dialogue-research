from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_global_projection_v2 import (  # noqa: E402
    comparison_class,
    observe_donor_variant,
)
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    CONTEXT_LEVELS,
    DonorObservation,
    context_key,
)
from phoneme_roman import expand_roman_eojeol  # noqa: E402


GROUP_LOOKUP = {
    "k": 1,
    "ɐ": 2,
    "m": 3,
    "dʑ": 4,
    "tɕ": 4,
}


class GlobalProjectionV2Tests(unittest.TestCase):
    def test_comparison_classes_candidate_gain_and_loss(self) -> None:
        previous = {
            "projection_status": "hold_no_unanimous_exact_context_donor",
            "representation_relation": "not_equivalent",
            "projection_candidate_count": "0",
            "projected_pron_phones_json": "[]",
        }
        gained = {
            "projection_status": "candidate_exact_context_projection",
            "representation_relation": "exact_comparison_keys",
            "projection_candidate_count": 1,
            "projected_pron_phones_json": json.dumps(["k ɐ"], ensure_ascii=False),
        }
        self.assertEqual(comparison_class(previous, gained), "candidate_gained")
        self.assertEqual(
            comparison_class(
                {
                    **previous,
                    "projection_status": "candidate_exact_context_projection",
                    "representation_relation": "exact_comparison_keys",
                    "projection_candidate_count": "1",
                    "projected_pron_phones_json": json.dumps(["k ɐ"], ensure_ascii=False),
                },
                {**gained, "projection_candidate_count": 0, "projected_pron_phones_json": "[]"},
            ),
            "candidate_lost",
        )

    def test_comparison_requires_phone_identity_for_unchanged(self) -> None:
        previous = {
            "projection_status": "candidate_exact_context_projection",
            "representation_relation": "exact_comparison_keys",
            "projection_candidate_count": "1",
            "projected_pron_phones_json": json.dumps(["k ɐ"], ensure_ascii=False),
        }
        current = {
            "projection_status": "candidate_exact_context_projection",
            "representation_relation": "exact_comparison_keys",
            "projection_candidate_count": 1,
            "projected_pron_phones_json": json.dumps(["k ɐ"], ensure_ascii=False),
        }
        self.assertEqual(comparison_class(previous, current), "unchanged")
        self.assertEqual(
            comparison_class(previous, {**current, "projected_pron_phones_json": json.dumps(["k tɕ"], ensure_ascii=False)}),
            "candidate_phone_changed",
        )

    def test_multiple_exact_variants_count_one_target_but_test_unanimity(self) -> None:
        rule = tuple(expand_roman_eojeol("G A m _ J A"))
        query_sets = {level: set() for level in CONTEXT_LEVELS}
        for index in range(len(rule)):
            for level in CONTEXT_LEVELS:
                query_sets[level].add(context_key(rule, index, level))
        index: dict[str, dict[tuple[object, ...], DonorObservation]] = {
            level: {} for level in CONTEXT_LEVELS
        }
        seen: set[tuple[str, tuple[object, ...]]] = set()
        for phones in (("k", "ɐ", "m", "dʑ", "ɐ"), ("k", "ɐ", "m", "tɕ", "ɐ")):
            observe_donor_variant(
                index=index,
                query_sets=query_sets,
                target="감자",
                phones=phones,
                rule=rule,
                seen_target_context=seen,
            )
        key = context_key(rule, 3, "window2_boundary")
        observation = index["window2_boundary"][key]
        self.assertEqual(observation.target_type_count, 1)
        self.assertEqual(observation.phone_counts, {"dʑ": 1, "tɕ": 1})


if __name__ == "__main__":
    unittest.main()
