import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from prepare_mfa_exclusion_review import prepare_review  # noqa: E402


class PrepareMfaExclusionReviewTests(unittest.TestCase):
    def test_candidates_are_pending_and_quarantine_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            (search / "2020" / "S1.csv").write_text(
                "utt_id,form,pron_reference_form\nU1,가,가\n",
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2020",
                                "issue_inventory": [
                                    {
                                        "utt_id": "U1",
                                        "issue": "morph_source_missing",
                                        "morph_disposition": (
                                            "exclude_source_audio_unusable"
                                        ),
                                        "path": "old",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            quarantine = root / "quarantine.csv"
            quarantine.write_text(
                "name,quarantine_path\nU1.wav,D:/q/U1.wav\n",
                encoding="utf-8",
            )
            output = root / "review.csv"
            result = prepare_review(
                audit_report=audit,
                year="2020",
                search_master_root=search,
                output_csv=output,
                output_report=root / "report.json",
                quarantine_log=quarantine,
                input_contract_id="INPUT_TEST",
            )
            self.assertEqual(result["candidate_count"], 1)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["decision"], "pending")
            self.assertEqual(row["reason_code"], "quarantined_wav")
            self.assertEqual(row["exclusion_scope"], "alignment_and_analysis")


if __name__ == "__main__":
    unittest.main()
