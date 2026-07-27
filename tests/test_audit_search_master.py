import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

import audit_search_master as audit


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class AuditSearchMasterTests(unittest.TestCase):
    def test_session_finds_json_only_utterance_and_uncomputed_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.csv"
            master = root / "master.csv"
            source_rows = [
                {
                    "utt_id": "S1.1",
                    "speaker_id": "P1",
                    "form": "가",
                    "tagged": "가/VV",
                    "n_morphs": "1",
                }
            ]
            write_csv(
                source,
                source_rows,
                ["utt_id", "speaker_id", "form", "tagged", "n_morphs"],
            )
            master_rows = [
                {
                    "utt_id": "S1.1",
                    "year": "2020",
                    "session_id": "S1",
                    "form": "가",
                    "tagged": "가/VV",
                    "category_norm": "일상대화",
                    "topic": "생활",
                    "has_wav": "",
                    "has_tg_eojeol": "",
                    "quarantined": "",
                }
            ]
            write_csv(
                master,
                master_rows,
                [
                    "utt_id",
                    "year",
                    "session_id",
                    "form",
                    "tagged",
                    "category_norm",
                    "topic",
                    "has_wav",
                    "has_tg_eojeol",
                    "quarantined",
                ],
            )
            json_path = root / "S1.json"
            json_path.write_text(
                json.dumps(
                    {
                        "document": [
                            {
                                "utterance": [
                                    {"id": "S1.1", "form": "가"},
                                    {
                                        "id": "S1.2",
                                        "form": "",
                                        "original_form": "",
                                    },
                                ]
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = audit.audit_session(source, master, json_path)

            self.assertEqual(result["source_rows"], 1)
            self.assertEqual(result["master_rows"], 1)
            self.assertEqual(result["json_rows"], 2)
            self.assertEqual(
                result["json_missing_in_source"],
                [
                    {
                        "utt_id": "S1.2",
                        "form_empty": True,
                        "original_form_empty": True,
                    }
                ],
            )
            self.assertEqual(result["coverage"]["has_wav"], {"": 1})

    def test_lexicon_wiring_requires_builder_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            builder = root / "builder.py"
            predictor = root / "predictor.py"
            builder.write_text("result = predict_pron(form)\n", encoding="utf-8")
            predictor.write_text(
                "def build_lexicon_index(rows): pass\n"
                "def lexicon_pron(word, pos, index): pass\n",
                encoding="utf-8",
            )
            result = audit.audit_lexicon_wiring(
                builder, predictor, ["utt_id", "pron_pred_hangul"]
            )
            self.assertTrue(result["predictor_has_index_helper"])
            self.assertFalse(result["builder_mentions_lexicon_path"])
            self.assertFalse(result["builder_passes_lexicon_to_predictor"])

    def test_compact_existing_report_preserves_counts(self):
        report = {
            "totals": {
                "json_missing_in_source": 2,
                "source_missing_in_json": 0,
            },
            "mismatches": {
                "json_source_content_sessions": [
                    {
                        "year": "2021",
                        "session_id": "S1",
                        "json_rows": 3,
                        "source_rows": 1,
                        "json_missing_in_source": [
                            {
                                "utt_id": "S1.2",
                                "form_empty": True,
                                "original_form_empty": False,
                            },
                            {
                                "utt_id": "S1.3",
                                "form_empty": True,
                                "original_form_empty": True,
                            },
                        ],
                        "source_missing_in_json": [],
                    }
                ],
                "source_master_content_sessions": [],
            },
            "verdicts": {},
        }
        compact = audit.compact_existing_report(report, 10, 1)
        self.assertEqual(compact["totals"]["json_source_mismatch_sessions"], 1)
        self.assertEqual(compact["totals"]["json_excluded_form_empty"], 2)
        self.assertEqual(
            compact["totals"]["json_excluded_original_form_nonempty"], 1
        )
        detail = compact["mismatches"]["json_source_content_sessions"][0]
        self.assertEqual(detail["json_missing_in_source_count"], 2)
        self.assertEqual(len(detail["json_missing_in_source_examples"]), 1)

    def test_integrity_gates_accept_only_documented_empty_form_exclusions(self):
        report = {
            "totals": {
                "missing_json_sessions": 0,
                "json_missing_in_source": 2,
                "json_excluded_form_empty": 2,
                "source_missing_in_json": 0,
                "meta_missing_rows": 0,
            },
            "verdicts": {
                "session_sets_match": True,
                "source_master_rows_match": True,
                "source_master_content_match": True,
            },
        }
        audit.set_integrity_gates(report)
        self.assertTrue(report["all_integrity_gates_pass"])

        report["totals"]["missing_json_sessions"] = 1
        audit.set_integrity_gates(report)
        self.assertFalse(report["all_integrity_gates_pass"])
        self.assertFalse(
            report["integrity_gates"]["all_source_sessions_have_json"]
        )

    def test_main_returns_nonzero_when_integrity_gate_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "audit.json"
            failed_report = {
                "verdicts": {},
                "integrity_gates": {"session_sets_match": False},
                "all_integrity_gates_pass": False,
            }
            with (
                patch.object(audit, "audit_all", return_value=failed_report),
                patch(
                    "sys.argv",
                    [
                        "audit_search_master.py",
                        "--years",
                        "2021",
                        "--output",
                        str(output),
                    ],
                ),
            ):
                self.assertEqual(audit.main(), 1)
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(saved["strict"])


if __name__ == "__main__":
    unittest.main()
