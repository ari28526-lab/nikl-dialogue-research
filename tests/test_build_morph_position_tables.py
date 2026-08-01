import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from build_morph_position_tables import build_tables  # noqa: E402


class BuildMorphPositionTablesTests(unittest.TestCase):
    def _write_input(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "utt_id",
                    "year",
                    "form",
                    "tagged",
                    "n_morphs",
                    "tagged_roman",
                    "pron_reference_form",
                    "pron_reference_source",
                    "pron_reference_status",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "utt_id": "U1",
                    "year": "2020",
                    "form": "혹시 요즘",
                    "tagged": "혹시/MAG 요즘/NNG",
                    "n_morphs": "2",
                    "tagged_roman": (
                        "H O k _ S I/MAG | YO _ J EU m/NNG"
                    ),
                }
            )
            writer.writerow(
                {
                    "utt_id": "U2",
                    "year": "2020",
                    "form": "1층",
                    "tagged": "1/SN+층/NNG",
                    "n_morphs": "2",
                    "tagged_roman": "1/SN + CH EU ng/NNG",
                    "pron_reference_form": "일층",
                    "pron_reference_source": (
                        "original_form_placeholder_resolution"
                    ),
                    "pron_reference_status": "resolved_original_form",
                }
            )

    def test_builds_all_pilot_tables_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.csv"
            self._write_input(source)
            output = root / "output"
            manifest = build_tables(
                input_paths=[source],
                output_root=output,
                emit_orth_components=True,
            )
            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["counts"]["utterances"], 2)
            self.assertEqual(manifest["counts"]["morph_tokens"], 4)
            self.assertEqual(manifest["counts"]["morph_boundaries"], 2)
            self.assertEqual(manifest["counts"]["symbol_readings"], 1)
            self.assertTrue((output / "orth_components.csv").is_file())
            self.assertTrue((output / "eojeol_tokens.csv").is_file())
            self.assertTrue((output / "symbol_readings.csv").is_file())
            saved = json.loads(
                (output / "BUILD_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertTrue(saved["gates"]["boundary_count_equal"])
            self.assertTrue(saved["gates"]["orth_symbol_coverage_equal"])
            with open(
                output / "utterance_master_v2.csv",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[1]["tagged_roman_v2"], "⟨1⟩/SN + CH EU ng/NNG")
            self.assertEqual(
                rows[1]["legacy_tagged_roman_equal_v2"], "False"
            )
            with open(
                output / "symbol_readings.csv",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                symbols = list(csv.DictReader(stream))
            self.assertEqual(symbols[0]["symbol_surface"], "1")
            self.assertEqual(symbols[0]["reference_reading"], "일")
            with self.assertRaises(FileExistsError):
                build_tables(input_paths=[source], output_root=output)


if __name__ == "__main__":
    unittest.main()
