from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.python.build_common_pron_r3_attested_full_sequence_projection import (
    ATTESTED_MARKERS,
    LEGACY_MARKER,
    dictionary_evidence_class,
    freeze,
    runtime_snapshot,
)


class AttestedFullSequenceProjectionTests(unittest.TestCase):
    def test_attested_pron_is_distinct_from_legacy_machine_fallback(self) -> None:
        base = {
            "rule_pron_roman": "G A k",
            "dictionary_pron_roman_json": '["G A k"]',
        }
        attested = {
            **base,
            "dictionary_source_refs_json": f'["{sorted(ATTESTED_MARKERS)[0]}"]',
        }
        legacy = {
            **base,
            "dictionary_source_refs_json": f'["{LEGACY_MARKER}"]',
        }
        self.assertEqual(
            dictionary_evidence_class(attested),
            "attested_pron_1_or_2_rule_exact",
        )
        self.assertEqual(
            dictionary_evidence_class(legacy),
            "legacy_machine_only_rule_exact",
        )

    def test_nonexact_dictionary_variant_is_not_promoted(self) -> None:
        row = {
            "rule_pron_roman": "G A k",
            "dictionary_pron_roman_json": '["G EO k"]',
            "dictionary_source_refs_json": '["NIKL_lexicon_full_v2:pron_1"]',
        }
        self.assertEqual(dictionary_evidence_class(row), "no_dictionary_rule_exact")

    def test_nested_context_keys_are_hashable(self) -> None:
        self.assertEqual(freeze(["A", ["B", 1], False]), ("A", ("B", 1), False))

    def test_runtime_snapshot_requires_explicit_project_root(self) -> None:
        with patch("scripts.python.pipeline_common.subprocess.run") as mocked:
            mocked.return_value.stdout = "test-commit\n"
            snapshot = runtime_snapshot(__import__("pathlib").Path("."))
        self.assertIn("python", snapshot)


if __name__ == "__main__":
    unittest.main()
