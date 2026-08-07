from __future__ import annotations

import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "scripts" / "python"
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

from summarize_dialogue_audio_quality import FIELDS, YEARS, build_summary


class SummarizeDialogueAudioQualityTests(unittest.TestCase):
    def make_year(self, root: Path, year: str) -> None:
        year_root = root / year
        audio_root = year_root / "03_AUDIO_SAMPLE"
        audio_root.mkdir(parents=True)
        (year_root / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "year": year,
                    "counts": {
                        "utterances": 100,
                        "sessions": 2,
                        "confirmed_overlap_union": 4,
                        "source_time_invalid": 1,
                        "boundary_abut_members": 20,
                    },
                }
            ),
            encoding="utf-8",
        )
        (audio_root / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "year": year,
                    "counts": {
                        "wav_files": 100,
                        "sampled_wavs": 2,
                        "readable_wavs": 1,
                        "invalid_wavs": 1,
                        "sessions_without_wav": 0,
                    },
                    "policy": {"automatic_exclusion_performed": False},
                }
            ),
            encoding="utf-8",
        )
        with gzip.open(
            audio_root / "02_SESSION_AUDIO_SUMMARY.csv.gz",
            "wt",
            encoding="utf-8-sig",
            newline="",
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=("session_id", "review_priority"))
            writer.writeheader()
            writer.writerow({"session_id": "S1", "review_priority": "high_noise_proxy_review"})
            writer.writerow({"session_id": "S2", "review_priority": "invalid_wav_review"})
        with open(
            year_root / "05_BAD_WAV_FULL_SCAN.csv",
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=("name", "size_bytes"))
            writer.writeheader()
            writer.writerow({"name": "bad.wav", "size_bytes": "44"})

    def test_build_summary_is_descriptive_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            for year in YEARS:
                self.make_year(root, year)
            output_csv = root / "SUMMARY.csv"
            output_manifest = root / "SUMMARY.json"
            manifest = build_summary(
                audit_root=root,
                output_csv=output_csv,
                output_manifest=output_manifest,
            )
            with open(output_csv, encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(tuple(rows[0]), FIELDS)
            self.assertEqual(len(rows), 6)
            self.assertEqual(rows[0]["confirmed_source_overlap_pct"], "4.000000")
            self.assertEqual(rows[0]["high_noise_proxy_review_sessions"], "1")
            self.assertEqual(rows[0]["invalid_wav_review_sessions"], "1")
            self.assertEqual(rows[0]["full_scan_bad_wavs"], "1")
            self.assertEqual(rows[0]["automatic_exclusion_performed"], "false")
            self.assertEqual(rows[0]["researcher_decision"], "pending")
            self.assertFalse(manifest["policy"]["automatic_exclusion_performed"])

    def test_existing_outputs_are_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            for year in YEARS:
                self.make_year(root, year)
            output_csv = root / "SUMMARY.csv"
            output_manifest = root / "SUMMARY.json"
            output_csv.write_text("protected", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                build_summary(
                    audit_root=root,
                    output_csv=output_csv,
                    output_manifest=output_manifest,
                )


if __name__ == "__main__":
    unittest.main()
