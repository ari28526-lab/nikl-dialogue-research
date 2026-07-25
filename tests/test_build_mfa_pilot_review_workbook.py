import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_mfa_pilot_review_workbook import (  # noqa: E402
    REQUIRED_COLUMNS,
    build_workbook,
    safe_bundle_path,
    validate_bundle_files,
    verify_workbook,
)


class MfaPilotReviewWorkbookTests(unittest.TestCase):
    def make_row(self, utt_id: str, year: str) -> dict[str, str]:
        return {
            "year": year,
            "speaker_id": f"SPK{year}",
            "dialogue_id": f"DOC{year}.1",
            "dialogue_speaker_ids": f"SPK{year} | OTHER{year}",
            "co_speaker_ids": f"OTHER{year}",
            "utt_id": utt_id,
            "form": "정규형",
            "original_form": "원문",
            "pron_reference_hangul": "발음 참조",
            "pron_reference_source": "form_rule_prediction",
            "morph_analysis_align_status": "all_lexical_slots",
            "utterance_info_schema": "[UTT][FORM][ORTH_R][RULE_H][RULE_R]",
            "tier_warning": "",
            "wav_relpath": f"{year}\\{utt_id}.wav",
            "lab_relpath": f"{year}\\{utt_id}.lab",
            "textgrid_relpath": f"{year}\\{utt_id}.TextGrid",
            "csv_relpath": f"{year}\\{utt_id}.csv",
        }

    def test_builds_and_reopens_auditable_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            rows = [
                self.make_row("SDRW2300001955.1.1.164", "2023"),
                self.make_row("SDRW2300000891.1.1.331", "2023"),
            ]
            for row in rows:
                for field in (
                    "wav_relpath",
                    "lab_relpath",
                    "textgrid_relpath",
                    "csv_relpath",
                ):
                    path = safe_bundle_path(bundle, row[field])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"test")
            validate_bundle_files(bundle, rows)

            index = bundle / "INDEX_ALL.csv"
            index.write_text("test", encoding="utf-8")
            output = root / "review.xlsx"
            workbook = build_workbook(
                list(REQUIRED_COLUMNS),
                rows,
                index,
                bundle,
                output_path=output,
            )
            workbook.save(output)
            report = verify_workbook(output, len(rows), bundle)

            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["rows"], 2)
            self.assertEqual(report["hyperlinks"], 8)
            self.assertEqual(report["data_validations"], 4)
            self.assertEqual(report["formula_error_strings"], 0)

    def test_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                safe_bundle_path(Path(tmp), "..\\outside.wav")


if __name__ == "__main__":
    unittest.main()
