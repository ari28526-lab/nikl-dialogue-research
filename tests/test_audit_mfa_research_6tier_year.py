import csv
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from audit_mfa_research_6tier_year import audit_year  # noqa: E402
from export_mfa_db_research_6tier import export_database  # noqa: E402
from mfa_exclusion_contract import REVIEW_FIELDS, build_contract  # noqa: E402
from tests.test_export_mfa_db_research_6tier import (  # noqa: E402
    ExportMfaDbResearch6TierTests as _ExportFixture,
)
from verify_mfa_db_research_6tier_sample import verify_sample  # noqa: E402


class AuditMfaResearch6TierYearTests(unittest.TestCase):
    def test_full_contract_audit_and_missing_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = _ExportFixture()
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            alignment = root / "alignment.json"
            search = root / "search"
            labs = root / "labs"
            output = root / "output"
            fixture.make_db(db)
            fixture.make_acoustic(acoustic)
            fixture.make_contract(alignment)
            fixture.make_search(search)
            lab = labs / "2021" / "S1" / "S1.1.lab"
            lab.parent.mkdir(parents=True)
            lab.write_text("가", encoding="utf-8")
            with wave.open(str(lab.with_suffix(".wav")), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(b"\x00\x00" * 16000)
            review = root / "review.csv"
            with review.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
                writer.writeheader()
            exclusions = root / "exclusions.json"
            build_contract(
                review_csv=review,
                output=exclusions,
                year="2021",
                input_contract_id="INPUT_TEST",
                approved_by="researcher",
                approved_at="2026-08-01T12:00:00+09:00",
            )
            exported = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=alignment,
                approved_exclusions_contract=exclusions,
                lab_root=labs,
            )
            self.assertEqual(exported["status"], "success")
            report = audit_year(
                year="2021",
                lab_root=labs,
                textgrid_root=output,
                acoustic_model=acoustic,
                approved_exclusions_contract=exclusions,
                input_contract_id="INPUT_TEST",
                alignment_contract_id="ALIGN_TEST",
                report_path=root / "audit.json",
                missing_csv_path=root / "missing.csv",
            )
            self.assertEqual(report["status"], "success")
            self.assertTrue(all(v == 0 for v in report["hard_failure_counts"].values()))
            wrong_root = audit_year(
                year="2021",
                lab_root=labs / "2021",
                textgrid_root=output,
                acoustic_model=acoustic,
                approved_exclusions_contract=exclusions,
                input_contract_id="INPUT_TEST",
                alignment_contract_id="ALIGN_TEST",
                report_path=root / "audit_wrong_lab_root.json",
                missing_csv_path=root / "missing_wrong_lab_root.csv",
            )
            self.assertEqual(wrong_root["status"], "failed")
            self.assertEqual(wrong_root["configuration_error"], "lab_year_empty")
            self.assertEqual(wrong_root["hard_failure_counts"], {"empty_lab_input": 1})
            self.assertEqual(wrong_root["inventories"]["extra_textgrid_ids"], [])
            sample = verify_sample(
                db_path=db,
                year="2021",
                search_master_root=search,
                final_root=output,
                scratch_root=root / "scratch",
                acoustic_model=acoustic,
                alignment_contract=alignment,
                approved_exclusions_contract=exclusions,
                report_path=root / "sample.json",
                sample_csv_path=root / "sample.csv",
                sample_size=1,
            )
            self.assertEqual(sample["status"], "success")
            self.assertEqual(sample["comparison_counts"]["semantic_equal"], 1)
            (output / "2021" / "S1" / "S1.1.TextGrid").unlink()
            failed = audit_year(
                year="2021",
                lab_root=labs,
                textgrid_root=output,
                acoustic_model=acoustic,
                approved_exclusions_contract=exclusions,
                input_contract_id="INPUT_TEST",
                alignment_contract_id="ALIGN_TEST",
                report_path=root / "audit_failed.json",
                missing_csv_path=root / "missing_failed.csv",
            )
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["inventories"]["missing_textgrid_ids"], ["S1.1"])


if __name__ == "__main__":
    unittest.main()
