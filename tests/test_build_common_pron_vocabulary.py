import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))
import build_common_pron_vocabulary as vocab  # noqa: E402


class BuildCommonPronVocabularyTests(unittest.TestCase):
    def test_full_year_counts_use_mfa_lab_tokenizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_build_meta.json").write_text(
                json.dumps({"status": "success"}), encoding="utf-8"
            )
            fields = [
                "utt_id",
                "year",
                "pron_reference_form",
                "pron_reference_status",
            ]
            rows = {
                "2020": [
                    {
                        "utt_id": "A.1",
                        "year": "2020",
                        "pron_reference_form": "가1 나!",
                        "pron_reference_status": "unresolved_symbol",
                    },
                    {
                        "utt_id": "A.2",
                        "year": "2020",
                        "pron_reference_form": "",
                        "pron_reference_status": "empty",
                    },
                ],
                "2021": [
                    {
                        "utt_id": "B.1",
                        "year": "2021",
                        "pron_reference_form": "가 다",
                        "pron_reference_status": "resolved_form",
                    }
                ],
            }
            for year, current in rows.items():
                year_dir = root / year
                year_dir.mkdir()
                with (year_dir / f"{year}.csv").open(
                    "w", encoding="utf-8", newline=""
                ) as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(current)

            output = root / "vocabulary.csv"
            manifest = root / "manifest.json"
            result = vocab.build_vocabulary(
                search_root=root,
                years=("2020", "2021"),
                output_csv=output,
                manifest_path=manifest,
                progress_every=0,
            )

            self.assertEqual(result["counts"]["utterance_rows"], 3)
            self.assertEqual(result["counts"]["unique_tokens"], 3)
            self.assertEqual(result["counts"]["empty_lab_rows"], 1)
            self.assertEqual(result["counts"]["unresolved_symbol_rows"], 1)
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                by_token = {
                    row["token"]: row for row in csv.DictReader(stream)
                }
            self.assertEqual(by_token["가"]["total_occurrences"], "2")
            self.assertEqual(by_token["가"]["count_2020"], "1")
            self.assertEqual(by_token["가"]["count_2021"], "1")
            self.assertEqual(by_token["나"]["total_occurrences"], "1")
            self.assertEqual(by_token["다"]["total_occurrences"], "1")

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "exists.csv"
            output.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                vocab.build_vocabulary(
                    search_root=root,
                    years=("2020",),
                    output_csv=output,
                    manifest_path=root / "manifest.json",
                    progress_every=0,
                )


if __name__ == "__main__":
    unittest.main()
