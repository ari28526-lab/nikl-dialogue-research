from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts/python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(name: str, filename: str):
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_module(
    "build_stage2_two_hour_seven_phenomena_reviewer",
    "build_stage2_two_hour_seven_phenomena_reviewer.py",
)
AUDITOR = load_module(
    "audit_stage2_two_hour_seven_phenomena_reviewer",
    "audit_stage2_two_hour_seven_phenomena_reviewer.py",
)


class SevenPhenomenaReviewerTests(unittest.TestCase):
    def test_c_only_repackage_contract_binds_84_corrected_samples(self) -> None:
        samples_path = REPO_ROOT / BUILDER.DEFAULT_SAMPLES
        rows = BUILDER.read_csv(samples_path)
        report = BUILDER.validate_samples(rows, check_source_assets=False)
        self.assertEqual(report["rows"], 84)
        self.assertEqual(set(report["by_phenomenon"].values()), {12})
        self.assertEqual(BUILDER.sha256_file(samples_path), BUILDER.EXPECTED_SAMPLES_SHA256)

    def test_html_is_one_case_screen_with_required_research_controls(self) -> None:
        sample = {
            "sample_id": "P2H-PT-2020-01",
            "phenomenon_code": "PT",
            "year": "2020",
            "utt_id": "U1",
            "grouped_order": "1",
            "shuffled_order": "1",
            "target_word_indices": [1],
            "target_word_labels": ["시험"],
        }
        literature = {
            "PT": {
                "label_ko": "합성어 경음화",
                "pilot_schedule": [],
                "population_contract": {},
                "confounds": [],
                "evidence_limits": [],
                "open_questions": [],
                "claims": [],
                "source_only_refs": [],
                "realization_categories_candidate": [],
            }
        }
        document = BUILDER.build_html(
            samples=[sample],
            dialogues={"U1": []},
            metadata={"U1": {}},
            literature=literature,
            projections={"P2H-PT-2020-01": {}},
            build_meta={"samples_sha256": "0" * 64, "automatic_realization_judgement": False},
        )
        self.assertEqual(document.count('id="review-form"'), 1)
        self.assertIn('id="order-mode"', document)
        self.assertIn('name="environment_confidence"', document)
        self.assertIn('name="realization_confidence"', document)
        self.assertIn('name="boundary_edit_need"', document)
        self.assertIn('id="dialogue-search"', document)
        self.assertIn("not_formal_realization_ledger", document)
        self.assertIn('id="target-jump"', document)
        self.assertIn("canplay", document)
        self.assertIn('id="phenomenon-summary-save"', document)
        self.assertIn("stage2_two_hour_phenomenon_summary.v1", document)
        self.assertIn("window.history.replaceState", document)
        self.assertNotRegex(document, r"\bconst\s+history\s*=")
        self.assertIn("blindRecheck", document)
        self.assertIn("5 · 단서 명확·재청취 불필요", document)
        self.assertIn("불러오기 실패 — 행 ${lineNumber}", document)
        embedded = AUDITOR.extract_json_script(document, "samples-data")
        self.assertEqual(embedded[0]["sample_id"], "P2H-PT-2020-01")

    def test_start_here_labels_are_scope_card_single_source(self) -> None:
        cards = BUILDER.read_jsonl(REPO_ROOT / BUILDER.DEFAULT_SCOPE_CARDS)
        literature = {
            str(row["phenomenon_code"]): {"label_ko": str(row["label_ko"])}
            for row in cards
        }
        document = BUILDER.build_start_html(literature)
        labels = AUDITOR.extract_start_labels(document)
        self.assertEqual(
            labels,
            {str(row["phenomenon_code"]): str(row["label_ko"]) for row in cards},
        )

    def test_current_claim_ledger_can_refresh_appended_scope_refs(self) -> None:
        refresh = load_module(
            "refresh_stage2_scope_cards_from_appended_claims",
            "refresh_stage2_scope_cards_from_appended_claims.py",
        )
        cards = BUILDER.read_jsonl(REPO_ROOT / BUILDER.DEFAULT_SCOPE_CARDS)
        claims = BUILDER.read_jsonl(REPO_ROOT / BUILDER.DEFAULT_CLAIMS)
        refreshed, additions = refresh.refresh_cards(cards, claims, 156)
        self.assertEqual([row["phenomenon_code"] for row in refreshed], BUILDER.EXPECTED_CODES)
        self.assertEqual(sum(len(value) for value in additions.values()), 18)
        self.assertEqual(len({item for value in additions.values() for item in value}), 17)
        self.assertIn("CLM-0160", additions["PT"])
        self.assertIn("CLM-0160", additions["NAN"])
        self.assertEqual(additions["VH"], [])
        self.assertEqual(additions["HIA"], [])

    def test_phenomenon_summary_omits_sample_id_and_case_latest_filters_it(self) -> None:
        document = BUILDER.REVIEW_HTML
        summary_handler = document.split("byId('phenomenon-summary-save').onclick=", 1)[1].split(";\n", 1)[0]
        self.assertNotIn("sample_id", summary_handler)
        self.assertIn("reviewRows().filter(isSampleRecord)", document)
        self.assertIn("if(isSummaryRecord(row))", document)
        self.assertIn("문헌 메모 자동 저장됨", document)

    def test_praat_wrapper_contract_is_powershell_5_1_compatible(self) -> None:
        text = BUILDER.OPEN_PRAAT_PS1
        self.assertNotIn("&&", text)
        self.assertNotIn("??", text)
        self.assertIn("Start-Process", text)
        self.assertIn("--open", text)
        self.assertIn("praat_work", text)

    def test_audit_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "existing"
            output.mkdir()
            with self.assertRaises(AUDITOR.ReviewerAuditError):
                AUDITOR.write_result(output, {"passed": True})

    def test_embedded_json_roundtrip_escapes_closing_script(self) -> None:
        payload = {"text": "</script>"}
        serialized = BUILDER.json_for_html(payload)
        self.assertNotIn("</script>", serialized)
        self.assertEqual(json.loads(serialized.replace("<\\/", "</")), payload)


if __name__ == "__main__":
    unittest.main()
