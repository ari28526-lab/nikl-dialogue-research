from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))
import trace_common_pron_special_occurrences as trace  # noqa: E402


class TraceCommonPronSpecialOccurrencesTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path]:
        search = root / "search"
        year_dir = search / "2020"
        year_dir.mkdir(parents=True)
        (search / "_build_meta.json").write_text(
            json.dumps({"status": "success"}), encoding="utf-8"
        )
        fields = sorted(trace.REQUIRED_COLUMNS | {"dialogue_id", "speaker_id"})
        with (year_dir / "SDRW2000000001.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "utt_id": "SDRW2000000001.1.1.1",
                    "year": "2020",
                    "session_id": "SDRW2000000001",
                    "dialogue_id": "SDRW2000000001.1.1",
                    "speaker_id": "SPK1",
                    "form": "외곬을 읽었다",
                    "original_form": "외곬을 읽었다",
                    "start": "0.0",
                    "end": "1.0",
                    "note": "",
                    "pron_reference_form": "외곬을 읽었다",
                    "pron_reference_hangul": "외골쓸 일걷따",
                    "pron_reference_source": "form",
                    "pron_reference_status": "ok",
                }
            )

        dialogue = root / "dialogue"
        raw_dir = dialogue / "NIKL_DIALOGUE_2020"
        raw_dir.mkdir(parents=True)
        (raw_dir / "SDRW2000000001.json").write_text(
            json.dumps(
                {
                    "document": [
                        {
                            "id": "SDRW2000000001.1.1",
                            "utterance": [
                                {
                                    "id": "SDRW2000000001.1.1.1",
                                    "speaker_id": "SPK1",
                                    "form": "외곬을 읽었다",
                                    "original_form": "외곬을 읽었다",
                                    "start": 0.0,
                                    "end": 1.0,
                                    "note": "",
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return search, dialogue

    def test_trace_exact_occurrence_and_raw_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search, dialogue = self.make_fixture(root)
            output = root / "trace.csv"
            manifest = root / "trace.json"
            result = trace.trace_occurrences(
                search_root=search,
                dialogue_json_root=dialogue,
                years=("2020",),
                targets=("외곬을",),
                output_csv=output,
                manifest_path=manifest,
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["counts"]["occurrence_rows"], 1)
            self.assertEqual(
                result["counts"]["target_occurrences"], {"외곬을": 1}
            )
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["target_token"], "외곬을")
            self.assertEqual(rows[0]["token_position_1based"], "1")
            self.assertEqual(rows[0]["raw_json_match_status"], "exact")
            self.assertEqual(rows[0]["raw_json_form"], "외곬을 읽었다")
            self.assertEqual(
                rows[0]["raw_json_original_form"], "외곬을 읽었다"
            )
            self.assertEqual(rows[0]["raw_json_speaker_id"], "SPK1")
            self.assertTrue(rows[0]["raw_json_path"].endswith(".json"))

    def test_missing_target_fails_without_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search, dialogue = self.make_fixture(root)
            output = root / "trace.csv"
            manifest = root / "trace.json"
            with self.assertRaisesRegex(RuntimeError, "target을 찾지 못함"):
                trace.trace_occurrences(
                    search_root=search,
                    dialogue_json_root=dialogue,
                    years=("2020",),
                    targets=("없는표층형",),
                    output_csv=output,
                    manifest_path=manifest,
                )
            self.assertFalse(output.exists())
            self.assertFalse(manifest.exists())

    def test_raw_json_mismatch_is_preserved_as_failed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search, dialogue = self.make_fixture(root)
            raw_path = (
                dialogue
                / "NIKL_DIALOGUE_2020"
                / "SDRW2000000001.json"
            )
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
            payload["document"][0]["utterance"][0]["original_form"] = "다름"
            raw_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            output = root / "trace.csv"
            manifest = root / "trace.json"
            result = trace.trace_occurrences(
                search_root=search,
                dialogue_json_root=dialogue,
                years=("2020",),
                targets=("외곬을",),
                output_csv=output,
                manifest_path=manifest,
            )
            self.assertEqual(result["status"], "failed_source_mismatch")
            self.assertEqual(result["counts"]["source_mismatch_rows"], 1)
            self.assertFalse(
                result["gates"]["search_master_matches_raw_json"]
            )
            self.assertFalse(
                result["gates"]["usable_for_pronunciation_approval"]
            )
            self.assertTrue(output.is_file())
            self.assertTrue(manifest.is_file())
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(
                rows[0]["raw_json_match_status"],
                "original_form_mismatch",
            )

    def test_targets_must_match_one_lab_token(self):
        with self.assertRaisesRegex(ValueError, "단일 동일 어절"):
            trace.normalize_targets(["외곬을 읽었다"])


if __name__ == "__main__":
    unittest.main()
