from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "python" / "build_stage2_actual_research_guides.py"
AUDITOR_PATH = ROOT / "scripts" / "python" / "audit_stage2_actual_research_guides.py"
SCOPE_CARDS = ROOT / "config" / "phenomenon_scope_cards_candidate_v1_20260823.jsonl"
REVIEWER = ROOT / "outputs" / "pilots" / "pv_seven_phenomena_20260819" / "two_hour_research_pilots_20260823" / "researcher_review_package_v2"
EXPECTED = ("PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("stage2_actual_guide_builder", BUILDER_PATH)
AUDITOR = load_module("stage2_actual_guide_auditor", AUDITOR_PATH)


class Stage2ActualResearchGuideTests(unittest.TestCase):
    def build(self, parent: Path) -> Path:
        output = parent / "guides"
        BUILDER.build_guides(SCOPE_CARDS, REVIEWER, output)
        return output

    def test_builds_common_and_seven_phenomenon_guides(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self.build(Path(tmp))
            self.assertTrue((output / "ACTUAL_RESEARCH_GUIDE.html").is_file())
            self.assertTrue((output / "SESSION_CHECKLIST.html").is_file())
            for code in EXPECTED:
                self.assertTrue((output / "PHENOMENON_GUIDES" / f"{code}.html").is_file())
                self.assertTrue((output / "PHENOMENON_GUIDES" / f"{code}.md").is_file())

    def test_receipt_preserves_candidate_and_84_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self.build(Path(tmp))
            receipt = json.loads((output / "BUILD_RECEIPT.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["candidate_status_preserved"])
            self.assertFalse(receipt["automatic_realization_judgement"])
            self.assertFalse(receipt["raw_corpus_read"])
            self.assertEqual(receipt["total_samples"], 84)
            self.assertEqual(set(receipt["sample_counts"].values()), {12})

    def test_independent_audit_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self.build(Path(tmp))
            audit = AUDITOR.audit_guides(output, SCOPE_CARDS, REVIEWER)
            self.assertTrue(audit["passed"], audit["failures"])
            self.assertEqual(audit["phenomenon_guides_html"], 7)
            self.assertEqual(audit["phenomenon_guides_markdown"], 7)
            self.assertGreater(audit["local_links_checked"], 20)

    def test_refuses_to_overwrite_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "guides"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                BUILDER.build_guides(SCOPE_CARDS, REVIEWER, output)


if __name__ == "__main__":
    unittest.main()
