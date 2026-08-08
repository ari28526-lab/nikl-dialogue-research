from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_ROOT))

from build_common_pron_r3_unanimous_phone_change_audit import (  # noqa: E402
    edit_mechanism,
    evidence_route,
    primary_route,
    rule_unit_family,
)


class UnanimousPhoneChangeAuditTests(unittest.TestCase):
    def test_insertion_mechanism(self) -> None:
        row = {"relation_kind": "direct_unit", "current_candidate_phone": ""}
        self.assertEqual(edit_mechanism(row), "segment_insertion")

    def test_substitution_mechanisms(self) -> None:
        direct = {"relation_kind": "direct_unit", "current_candidate_phone": "kʰ"}
        secondary = {
            "relation_kind": "secondary_articulation_cluster",
            "current_candidate_phone": "pʲ",
        }
        self.assertEqual(edit_mechanism(direct), "segment_substitution")
        self.assertEqual(
            edit_mechanism(secondary), "secondary_articulation_substitution"
        )

    def test_linguistic_families_are_explicit(self) -> None:
        self.assertEqual(rule_unit_family("direct_unit", ["EU_G"]), "ui_glide_component")
        self.assertEqual(rule_unit_family("direct_unit", ["Y"]), "compound_vowel_glide_component")
        self.assertEqual(rule_unit_family("direct_unit", ["ng"]), "velar_nasal_unit")
        self.assertEqual(rule_unit_family("direct_unit", ["t"]), "coda_or_sonorant_unit")
        self.assertEqual(rule_unit_family("direct_unit", ["KK"]), "onset_laryngeal_or_manner_unit")
        self.assertEqual(rule_unit_family("direct_unit", ["AE"]), "vowel_quality_or_length_unit")
        self.assertEqual(
            rule_unit_family("secondary_articulation_cluster", ["G", "Y"]),
            "secondary_articulation_cluster",
        )

    def test_primary_routes_do_not_imply_candidate(self) -> None:
        self.assertEqual(
            primary_route({"segment_insertion"}, {"ui_glide_component"}),
            "ui_glide_component_insertion",
        )
        self.assertEqual(
            primary_route(
                {"segment_substitution"}, {"onset_laryngeal_or_manner_unit"}
            ),
            "onset_laryngeal_or_manner_substitution",
        )
        self.assertEqual(
            primary_route(
                {"segment_insertion", "segment_substitution"},
                {"coda_or_sonorant_unit", "onset_laryngeal_or_manner_unit"},
            ),
            "multi_operation_mixed_edit",
        )

    def test_evidence_routes_are_scoped(self) -> None:
        self.assertEqual(
            evidence_route("segment_insertion"),
            "audit_rule_parser_and_model_unitization",
        )
        self.assertEqual(
            evidence_route("segment_substitution"),
            "audit_dictionary_rule_and_model_phone_relation",
        )


if __name__ == "__main__":
    unittest.main()
