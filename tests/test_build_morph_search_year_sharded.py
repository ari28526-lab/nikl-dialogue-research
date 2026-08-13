import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from build_morph_position_tables import sha256_file  # noqa: E402
from build_morph_search_year_sharded import build_year  # noqa: E402


class BuildMorphSearchYearShardedTests(unittest.TestCase):
    FIELDS = [
        "utt_id",
        "year",
        "form",
        "tagged",
        "n_morphs",
        "form_roman",
        "tagged_roman",
        "original_form",
        "pron_reference_form",
        "pron_reference_source",
        "pron_reference_status",
    ]

    def write_session(self, path: Path, row: dict[str, str]) -> None:
        with open(path, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.FIELDS)
            writer.writeheader()
            writer.writerow(row)

    def fixtures(self, root: Path) -> Path:
        source = root / "input" / "2020"
        source.mkdir(parents=True)
        rows = [
            {
                "utt_id": "U1",
                "year": "2020",
                "form": "가",
                "tagged": "가/IC",
                "n_morphs": "1",
                "form_roman": "G A",
                "tagged_roman": "G A/IC",
                "original_form": "합법적인\n인용 필드",
                "pron_reference_form": "가",
                "pron_reference_source": "form_rule_prediction",
                "pron_reference_status": "resolved_form",
            },
            {
                "utt_id": "U2",
                "year": "2020",
                "form": "2사람",
                "tagged": "2/SN+사람/NNG",
                "n_morphs": "2",
                "form_roman": "∅",
                "tagged_roman": "∅/SN + S A _ R A m/NNG",
                "original_form": "",
                "pron_reference_form": "두 사람",
                "pron_reference_source": "original_form_placeholder_resolution",
                "pron_reference_status": "resolved_original_form",
            },
            {
                "utt_id": "U3",
                "year": "2020",
                "form": "나?",
                "tagged": "나/IC+?/SF",
                "n_morphs": "2",
                "form_roman": "N A",
                "tagged_roman": "N A/IC + ?/SF",
                "original_form": "",
                "pron_reference_form": "나?",
                "pron_reference_source": "form_rule_prediction",
                "pron_reference_status": "resolved_form",
            },
            {
                "utt_id": "U4",
                "year": "2020",
                "form": "요즘",
                "tagged": "요즘/NNG",
                "n_morphs": "1",
                "form_roman": "YO _ J EU m",
                "tagged_roman": "YO _ J EU m/NNG",
                "original_form": "",
                "pron_reference_form": "요즘",
                "pron_reference_source": "form_rule_prediction",
                "pron_reference_status": "resolved_form",
            },
        ]
        for index, row in enumerate(rows, 1):
            self.write_session(source / f"S{index:02d}.csv", row)
        return source

    def test_pause_resume_and_annual_deterministic_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.fixtures(root)
            output = root / "output"
            paused = build_year(
                year="2020",
                input_root=source,
                output_root=output,
                files_per_shard=2,
                emit_orth_components=False,
                max_shards=1,
            )
            self.assertEqual(paused["status"], "paused_after_max_shards")
            self.assertTrue(
                (output / "shards" / "shard_00001" / "SHARD_MANIFEST.json").is_file()
            )
            self.assertFalse((output / "annual_tables").exists())

            final = build_year(
                year="2020",
                input_root=source,
                output_root=output,
                files_per_shard=2,
                emit_orth_components=False,
            )
            self.assertEqual(final["status"], "success")
            self.assertEqual(final["tables"]["master"]["rows"], 4)
            self.assertEqual(final["tables"]["symbol_readings"]["rows"], 2)
            symbol_path = (
                output / "annual_tables" / "symbol_readings.csv.gz"
            )
            with gzip.open(
                symbol_path, "rt", encoding="utf-8-sig", newline=""
            ) as stream:
                symbols = list(csv.DictReader(stream))
            with gzip.open(
                output / "annual_tables" / "utterance_master_v2.csv.gz",
                "rt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                master = list(csv.DictReader(stream))
            self.assertEqual(master[0]["original_form"], "합법적인\n인용 필드")
            digit = next(row for row in symbols if row["symbol_surface"] == "2")
            self.assertEqual(digit["reference_reading"], "두")
            first_sha = sha256_file(symbol_path)

            repeated = build_year(
                year="2020",
                input_root=source,
                output_root=output,
                files_per_shard=2,
                emit_orth_components=False,
            )
            self.assertEqual(repeated["status"], "success")
            self.assertEqual(sha256_file(symbol_path), first_sha)

    def test_partial_shard_is_preserved_and_blocks_automatic_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.fixtures(root)
            output = root / "output"
            partial = output / "shards" / "shard_00001" / "raw.partial"
            partial.mkdir(parents=True)
            marker = partial / "evidence.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                build_year(
                    year="2020",
                    input_root=source,
                    output_root=output,
                    files_per_shard=2,
                    emit_orth_components=False,
                )
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            progress = json.loads(
                (output / "YEAR_PROGRESS.json").read_text(encoding="utf-8")
            )
            self.assertEqual(progress["status"], "failed_preserved")


if __name__ == "__main__":
    unittest.main()
