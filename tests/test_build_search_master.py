import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import build_search_master as bsm  # noqa: E402
import predict_pron as pp  # noqa: E402


def write_bareun(path):
    rows = [
        {
            "utt_id": "SDRW2000000001.1.1.1",
            "speaker_id": "spk1",
            "form": "국물",
            "tagged": "국물/NNG",
            "n_morphs": "1",
        },
        {
            "utt_id": "SDRW2000000001.1.1.2",
            "speaker_id": "spk1",
            "form": "것을",
            "tagged": "것/NNB+을/JKO",
            "n_morphs": "2",
        },
    ]
    with open(path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_json(path, rows):
    utterances = [
        {
            "id": row["utt_id"],
            "original_form": row["form"],
            "start": str(index),
            "end": str(index + 0.5),
            "note": "",
        }
        for index, row in enumerate(rows)
    ]
    path.write_text(
        json.dumps({"document": [{"utterance": utterances}]}, ensure_ascii=False),
        encoding="utf-8",
    )


class SearchMasterSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bareun = self.root / "SDRW2000000001.csv"
        self.rows = write_bareun(self.bareun)
        self.source_json = self.root / "SDRW2000000001.json"
        write_json(self.source_json, self.rows)
        self.meta = {
            "SDRW2000000001": {
                "category_norm": "사적대화",
                "discourse_mode": "대화",
                "topic": "일상",
                "relation": "친구",
                "date": "2020",
                "in_ml2025_gold": "0",
            }
        }
        self.spk = {
            ("2020", "spk1"): {
                "sex_norm": "여성",
                "age_norm": "20대",
                "occupation_norm": "미상",
                "education_ord": "미상",
                "birthplace_norm": "서울",
                "current_residence_norm": "서울",
            }
        }
        self.json_idx = {"SDRW2000000001": self.source_json}
        self.opts = {
            "tagged_roman": True,
            "coverage": False,
            "overwrite": False,
            "output_root": self.root / "out",
            "archive_root": self.root / "out" / "_archive" / "test_run",
            "run_id": "test_run",
            "allow_missing_json": False,
        }

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        return bsm.build_session(
            self.bareun,
            "2020",
            self.meta,
            self.spk,
            self.json_idx,
            pp.load_ipa_map(),
            self.opts,
        )

    def test_create_then_validate_existing(self):
        first = self.build()
        self.assertEqual(first["status"], "created")
        output = self.root / "out" / "2020" / "SDRW2000000001.csv"
        self.assertTrue(output.exists())

        second = self.build()
        self.assertEqual(second["status"], "validated_existing")
        self.assertEqual(second["n_row"], 2)
        self.assertFalse((self.root / "out" / "_archive").exists())

    def test_partial_existing_is_archived_and_rebuilt(self):
        self.build()
        output = self.root / "out" / "2020" / "SDRW2000000001.csv"
        output.write_text("utt_id,year\nbroken,2020\n", encoding="utf-8")

        rebuilt = self.build()
        self.assertEqual(rebuilt["status"], "created")
        self.assertTrue(rebuilt["archive"])
        self.assertTrue(Path(rebuilt["archive"]).exists())
        expected_ids = [row["utt_id"] for row in self.rows]
        cols = list(bsm.BASE_COLS)
        cols.insert(cols.index("form_roman") + 1, "tagged_roman")
        self.assertTrue(
            bsm.validate_session_csv(output, cols, expected_ids)["valid"]
        )

    def test_overwrite_preserves_valid_previous_file(self):
        self.build()
        self.opts["overwrite"] = True
        rebuilt = self.build()
        self.assertEqual(rebuilt["status"], "created")
        self.assertTrue(Path(rebuilt["archive"]).exists())

    def test_missing_required_bareun_header_fails(self):
        self.bareun.write_text("utt_id,form\nx,국물\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "필수 컬럼 누락"):
            self.build()

    def test_original_form_resolves_numeric_placeholder_with_provenance(self):
        result = pp.predict_pron_reference(
            "무조건 1층으로 된 집",
            "무조건 일 층으로 된 집",
            tagged="무조건/MAG 1/SN+층/NNG+으로/JKB 되/VV+ㄴ/ETM 집/NNG",
        )
        self.assertIn(pp.PLACEHOLDER, result["base"]["pron_pred_hangul"])
        self.assertNotIn(
            pp.PLACEHOLDER, result["reference"]["pron_pred_hangul"]
        )
        self.assertIn("일 층으로", result["reference"]["pron_pred_hangul"])
        self.assertEqual(
            result["reference_source"],
            "original_form_placeholder_resolution",
        )
        self.assertEqual(result["reference_status"], "resolved_original_form")

    def test_unresolved_numeric_is_not_silently_guessed(self):
        result = pp.predict_pron_reference("1층", "")
        self.assertEqual(result["reference_status"], "unresolved_symbol")
        self.assertEqual(result["reference_unresolved_count"], 1)
        self.assertEqual(result["reference_form"], "1층")

    def test_dialogue_participants_and_co_speakers_are_document_scoped(self):
        source = self.root / "dialogue_context.json"
        source.write_text(
            json.dumps(
                {
                    "document": [
                        {
                            "id": "DOC1",
                            "utterance": [
                                {
                                    "id": "U1",
                                    "speaker_id": "SPK_B",
                                    "original_form": "안녕",
                                },
                                {
                                    "id": "U2",
                                    "speaker_id": "SPK_A",
                                    "original_form": "네",
                                },
                                {
                                    "id": "U3",
                                    "speaker_id": "SPK_C",
                                    "original_form": "반가워요",
                                },
                            ],
                        },
                        {
                            "id": "DOC2",
                            "utterance": [
                                {
                                    "id": "U4",
                                    "speaker_id": "SPK_D",
                                    "original_form": "독백",
                                }
                            ],
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        context = bsm.load_utt_extra(source)
        self.assertEqual(
            context["U2"]["dialogue_speaker_ids"],
            "SPK_A | SPK_B | SPK_C",
        )
        self.assertEqual(context["U2"]["co_speaker_ids"], "SPK_B | SPK_C")
        self.assertEqual(context["U2"]["n_dialogue_speakers"], 3)
        self.assertEqual(context["U2"]["n_co_speakers"], 2)
        self.assertEqual(context["U4"]["dialogue_id"], "DOC2")
        self.assertEqual(context["U4"]["co_speaker_ids"], "")


if __name__ == "__main__":
    unittest.main()
