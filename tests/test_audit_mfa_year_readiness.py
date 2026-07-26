import csv
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from audit_mfa_year_readiness import audit_year  # noqa: E402


class AuditMfaYearReadinessTests(unittest.TestCase):
    def test_detects_missing_tiny_stale_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            year_dir = search / "2021"
            session_dir = wav_root / "2021" / "S1"
            year_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)

            header = [
                "utt_id",
                "form",
                "pron_reference_form",
                "pron_reference_source",
                "pron_reference_status",
                "sex",
            ]
            rows = [
                ["S1.1", "가 나", "가 나", "form", "resolved_form", "여성"],
                ["S1.2", "1", "1", "form", "unresolved_symbol", "미상"],
                ["S1.3", "다", "다", "form", "resolved_form", "남성"],
                ["S1.4", "라", "라", "form", "resolved_form", "여성"],
            ]
            with open(year_dir / "S1.csv", "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)

            (session_dir / "S1.1.wav").write_bytes(b"x" * 100)
            (session_dir / "S1.1.lab").write_text("가 나", encoding="utf-8")
            (session_dir / "S1.2.wav").write_bytes(b"x" * 100)
            (session_dir / "S1.2.lab").write_text("stale", encoding="utf-8")
            (session_dir / "S1.4.wav").write_bytes(b"x" * 20)
            (session_dir / "S1.4.lab").write_text("wrong", encoding="utf-8")
            (session_dir / "EXTRA.wav").write_bytes(b"x" * 100)
            (session_dir / "EXTRA.lab").write_text("extra", encoding="utf-8")

            result = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                known_pcm=None,
            )
            counts = result["counts"]
            self.assertEqual(counts["search_rows"], 4)
            self.assertEqual(counts["speaker_missing"], 1)
            self.assertEqual(counts["pron_reference_unresolved"], 1)
            self.assertEqual(counts["wav_missing"], 1)
            self.assertEqual(counts["empty_reference_form"], 1)
            self.assertEqual(counts["stale_lab_for_empty_input"], 1)
            self.assertEqual(counts["wav_too_small"], 1)
            self.assertEqual(counts["lab_content_match"], 1)
            self.assertEqual(counts["lab_content_mismatch"], 1)
            self.assertEqual(counts["lab_not_expected_with_wav"], 2)
            self.assertFalse(result["gates"]["all_expected_labs_ready"])
            self.assertFalse(result["gates"]["no_dangerous_unexpected_labs"])
            self.assertFalse(result["gates"]["no_fatal_tiny_wav"])


if __name__ == "__main__":
    unittest.main()
