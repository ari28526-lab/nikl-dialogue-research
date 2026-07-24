import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_metadata_index import build_metadata  # noqa: E402


def write_source(path: Path, *, top_id: str, internal_id: str):
    payload = {
        "id": top_id,
        "metadata": {"category": "구어 > 사적 대화 > 일상 대화"},
        "document": [{
            "id": f"{internal_id}.1",
            "metadata": {
                "topic": "일상",
                "date": "2023",
                "speaker": [{"id": "spk1"}],
                "setting": {"relation": "친구"},
            },
            "utterance": [{"id": f"{internal_id}.1.1.1", "form": "국물"}],
        }],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class MetadataIndexTests(unittest.TestCase):
    def test_file_stem_wins_over_wrong_top_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "json" / "NIKL_2023"
            source.mkdir(parents=True)
            path = source / "SDRW2300000445.json"
            write_source(
                path,
                top_id="SDRW2300000444",
                internal_id="SDRW2300000445",
            )
            output = root / "out" / "file_meta.csv"
            report = build_metadata(
                root / "json",
                output,
                gold_index=root / "missing_gold.csv",
                run_id="test",
            )
            with open(output, encoding="utf-8-sig") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["file_id"], "SDRW2300000445")
            self.assertEqual(row["source_top_id"], "SDRW2300000444")
            self.assertEqual(len(report["top_id_mismatches"]), 1)

    def test_invalid_internal_id_does_not_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "json" / "NIKL_2023"
            source.mkdir(parents=True)
            write_source(
                source / "SDRW2300000445.json",
                top_id="SDRW2300000444",
                internal_id="WRONG",
            )
            output = root / "out" / "file_meta.csv"
            output.parent.mkdir(parents=True)
            output.write_text("old", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "검증 실패"):
                build_metadata(
                    root / "json",
                    output,
                    gold_index=root / "missing_gold.csv",
                    run_id="test",
                )
            self.assertEqual(output.read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
