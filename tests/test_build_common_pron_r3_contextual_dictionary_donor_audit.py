from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_contextual_dictionary_donor_audit import (  # noqa: E402
    CLASS_CONFLICT,
    CLASS_MULTIPLE,
    CLASS_NONE,
    CLASS_UNANIMOUS,
    Evidence,
    _secondary_cluster,
    aggregate_classes,
    evidence_class,
)
from build_common_pron_r3_g2p_mismatch_diagnostics import EditOperation  # noqa: E402
from phoneme_roman import expand_roman_eojeol  # noqa: E402


def operation(
    *,
    kind: str,
    candidate_index: int | None,
    rule_index: int | None,
    phone: str = "",
    candidate_display: str = "",
    candidate_key: str = "",
    candidate_group: str = "",
    rule_display: str = "",
    rule_key: str = "",
    rule_group: str = "",
) -> EditOperation:
    return EditOperation(
        operation=kind,
        candidate_index=candidate_index,
        rule_index=rule_index,
        candidate_phone=phone,
        candidate_display=candidate_display,
        candidate_key=candidate_key,
        candidate_model_group=candidate_group,
        candidate_has_length=False if phone else None,
        rule_display=rule_display,
        rule_key=rule_key,
        rule_model_group=rule_group,
    )


def evidence(*phones: str) -> Evidence:
    return Evidence(
        level="window2_boundary",
        context=("ctx",),
        phone_counts={phone: 2 for phone in phones},
        token_type_count=2,
    )


class ContextualDictionaryDonorAuditTests(unittest.TestCase):
    def test_palatalized_phone_preserves_onset_glide_cluster(self) -> None:
        rule = tuple(expand_roman_eojeol("P YO"))
        operations = [
            operation(
                kind="rule_only",
                candidate_index=None,
                rule_index=0,
                rule_display="P",
                rule_key="P",
                rule_group="P_GROUP",
            ),
            operation(
                kind="substitution",
                candidate_index=0,
                rule_index=1,
                phone="pʲ",
                candidate_display="B",
                candidate_key="B",
                candidate_group="P_GROUP",
                rule_display="Y",
                rule_key="Y",
                rule_group="Y_GROUP",
            ),
        ]
        result = _secondary_cluster(operations, rule, 0)
        self.assertIsNotNone(result)
        mapping, next_index = result  # type: ignore[misc]
        self.assertEqual(mapping.relation_kind, "secondary_articulation_cluster")
        self.assertEqual(mapping.rule_indices, (0, 1))
        self.assertEqual(mapping.phone, "pʲ")
        self.assertEqual(next_index, 2)

    def test_secondary_cluster_rejects_cross_model_group(self) -> None:
        rule = tuple(expand_roman_eojeol("P YO"))
        operations = [
            operation(
                kind="rule_only",
                candidate_index=None,
                rule_index=0,
                rule_display="P",
                rule_key="P",
                rule_group="P_GROUP",
            ),
            operation(
                kind="substitution",
                candidate_index=0,
                rule_index=1,
                phone="tʲ",
                candidate_display="D",
                candidate_key="D",
                candidate_group="T_GROUP",
                rule_display="Y",
                rule_key="Y",
                rule_group="Y_GROUP",
            ),
        ]
        self.assertIsNone(_secondary_cluster(operations, rule, 0))

    def test_evidence_class_is_fail_closed_and_source_aware(self) -> None:
        self.assertEqual(evidence_class(None, None), CLASS_NONE)
        self.assertEqual(evidence_class(evidence("pʲ"), evidence("pʲ")), CLASS_UNANIMOUS)
        self.assertEqual(
            evidence_class(evidence("pʲ", "pʰ"), evidence("pʲ")),
            CLASS_MULTIPLE,
        )
        self.assertEqual(evidence_class(evidence("pʲ"), evidence("pʰ")), CLASS_CONFLICT)

    def test_token_aggregation_requires_every_issue_and_variant(self) -> None:
        self.assertEqual(aggregate_classes([CLASS_UNANIMOUS]), CLASS_UNANIMOUS)
        self.assertEqual(
            aggregate_classes([CLASS_UNANIMOUS, CLASS_MULTIPLE]), CLASS_MULTIPLE
        )
        self.assertEqual(
            aggregate_classes([CLASS_UNANIMOUS, CLASS_NONE]), CLASS_NONE
        )
        self.assertEqual(
            aggregate_classes([CLASS_NONE, CLASS_CONFLICT]), CLASS_CONFLICT
        )
        self.assertEqual(
            aggregate_classes([CLASS_UNANIMOUS], variant_count=2), CLASS_MULTIPLE
        )


if __name__ == "__main__":
    unittest.main()
