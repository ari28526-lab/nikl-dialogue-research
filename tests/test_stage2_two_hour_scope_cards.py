from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_module("audit_stage2_two_hour_scope_cards", "scripts/python/audit_stage2_two_hour_scope_cards.py")
BUILDER = load_module("build_stage2_two_hour_scope_cards_review", "scripts/python/build_stage2_two_hour_scope_cards_review.py")


class TwoHourScopeCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cards = AUDITOR.read_jsonl(REPO_ROOT / AUDITOR.CARDS_PATH)
        cls.sources, cls.claims, _ = AUDITOR.validate_literature(REPO_ROOT)

    def test_success_actual_cards_without_generated_review(self) -> None:
        report = AUDITOR.audit_repo(REPO_ROOT, require_review_outputs=False)
        self.assertTrue(report["passed"])
        self.assertEqual(report["totals"]["phenomena"], 7)
        self.assertEqual(report["totals"]["researcher_minutes"], 840)
        self.assertEqual(report["totals"]["sample_target_total"], 84)

    def test_each_card_is_120_minutes_and_12_samples(self) -> None:
        for card in self.cards:
            stats = AUDITOR.validate_card(REPO_ROOT, card, self.sources, self.claims)
            self.assertEqual(stats["minutes"], 120)
            self.assertEqual(stats["sample_target"], 12)

    def test_failure_schedule_not_120_minutes(self) -> None:
        broken = copy.deepcopy(self.cards[0])
        broken["pilot_schedule"][0]["minutes"] = 19
        with self.assertRaises(AUDITOR.ScopeCardError):
            AUDITOR.validate_card(REPO_ROOT, broken, self.sources, self.claims)

    def test_failure_missing_population_group(self) -> None:
        broken = copy.deepcopy(self.cards[1])
        del broken["population_contract"]["unclear"]
        with self.assertRaises(AUDITOR.ScopeCardError):
            AUDITOR.validate_card(REPO_ROOT, broken, self.sources, self.claims)

    def test_ni_surface_yo_restored_i_is_retained(self) -> None:
        ni = next(card for card in self.cards if card["phenomenon_code"] == "NI")
        stats = AUDITOR.validate_ni_exception(ni)
        self.assertTrue(stats["overt_i_excluded"])
        self.assertTrue(stats["surface_yo_restored_i_retained"])

    def test_builder_roundtrip_contains_every_phenomenon(self) -> None:
        markdown = BUILDER.build_markdown(self.cards)
        html = BUILDER.build_html(self.cards)
        for code in AUDITOR.EXPECTED_CODES:
            self.assertIn(f"## {code} —", markdown)
            self.assertIn(f'data-code="{code}"', html)
        self.assertIn("STAGE2_TWO_HOUR_SCOPE_NOTES.jsonl", html)
        self.assertIn("localStorage", html)

    def test_existing_output_refuses_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "review.html"
            path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                BUILDER.ensure_absent([path])
            self.assertEqual(path.read_text(encoding="utf-8"), "existing\n")

    def test_malformed_jsonl_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cards.jsonl"
            path.write_text(json.dumps({"phenomenon_code": "PT"}) + "\n{broken\n", encoding="utf-8")
            with self.assertRaises((json.JSONDecodeError, ValueError)):
                BUILDER.read_jsonl(path)


if __name__ == "__main__":
    unittest.main()
