import csv
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))
import audit_common_pron_sources as audit  # noqa: E402


class AuditCommonPronSourcesTests(unittest.TestCase):
    def write_csv(self, path, fields, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_fallback_is_counted_without_calling_it_attested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            enriched = root / "enriched.csv"
            legacy = root / "legacy.csv"
            output = root / "audit.json"
            base = ["word", "word_stem", "pos_tag", "sense_no", "urimal_id"]
            self.write_csv(
                enriched,
                base + ["pron_1", "pron_2"],
                [
                    {
                        "word": "가",
                        "word_stem": "가",
                        "pos_tag": "NNG",
                        "sense_no": "001",
                        "urimal_id": "1",
                        "pron_1": "",
                        "pron_2": "",
                    },
                    {
                        "word": "나",
                        "word_stem": "나",
                        "pos_tag": "NNG",
                        "sense_no": "001",
                        "urimal_id": "2",
                        "pron_1": "나",
                        "pron_2": "",
                    },
                ],
            )
            self.write_csv(
                legacy,
                base + ["pron_1", "pron_2", "pron_g2p"],
                [
                    {
                        "word": "가",
                        "word_stem": "가",
                        "pos_tag": "NNG",
                        "sense_no": "001",
                        "urimal_id": "1",
                        "pron_1": "",
                        "pron_2": "",
                        "pron_g2p": "가",
                    }
                ],
            )
            result = audit.audit_sources(
                enriched_path=enriched,
                legacy_path=legacy,
                output_path=output,
                progress_every=0,
            )
            self.assertEqual(
                result["fallback_linkage"][
                    "enriched_missing_pron_with_legacy_g2p"
                ],
                1,
            )
            self.assertEqual(
                result["enriched"]["rows_with_any_attested_candidate"], 1
            )
            self.assertIn(
                "기계 생성",
                result["fallback_linkage"]["interpretation"],
            )


if __name__ == "__main__":
    unittest.main()
