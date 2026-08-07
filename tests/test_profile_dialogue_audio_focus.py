from __future__ import annotations

import csv
import gzip
import json
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "scripts" / "python"
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

from profile_dialogue_audio_focus import build_profile


class ProfileDialogueAudioFocusTests(unittest.TestCase):
    def write_wav(self, path: Path) -> None:
        path.parent.mkdir(parents=True)
        values = [0] * 100 + [12000] * 700 + [0] * 100
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(1000)
            stream.writeframes(struct.pack(f"<{len(values)}h", *values))

    def test_join_is_pending_and_non_automatic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            utt_id = "SDRW2200000001.1.1.1"
            focus = root / "focus.csv"
            with open(focus, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=("utt_id", "reason_code"))
                writer.writeheader()
                writer.writerow({"utt_id": utt_id, "reason_code": "mfa_alignment_missing"})
            structural = root / "structural.csv.gz"
            with gzip.open(structural, "wt", encoding="utf-8-sig", newline="") as stream:
                fields = (
                    "utt_id",
                    "evidence_class",
                    "reason_codes",
                    "max_time_overlap_sec",
                    "boundary_abut_prev",
                    "boundary_abut_next",
                )
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": utt_id,
                        "evidence_class": "confirmed_source_overlap",
                        "reason_codes": "source_time_overlap",
                        "max_time_overlap_sec": "0.1",
                        "boundary_abut_prev": "false",
                        "boundary_abut_next": "false",
                    }
                )
            audio_session = root / "sessions.csv.gz"
            with gzip.open(audio_session, "wt", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=("session_id", "noise_proxy_percentile", "review_priority"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "session_id": "SDRW2200000001",
                        "noise_proxy_percentile": "99.0",
                        "review_priority": "high_noise_proxy_review",
                    }
                )
            wav_root = root / "wav"
            self.write_wav(wav_root / "SDRW2200000001" / f"{utt_id}.wav")
            output_csv = root / "profile.csv"
            output_manifest = root / "profile.json"
            manifest = build_profile(
                year="2022",
                focus_csvs=[focus],
                wav_root=wav_root,
                structural_flags=structural,
                audio_session_summary=audio_session,
                output_csv=output_csv,
                output_manifest=output_manifest,
            )
            with open(output_csv, encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertIn("confirmed_source_overlap", row["review_signals"])
            self.assertIn("high_noise_proxy_review", row["review_signals"])
            self.assertEqual(
                row["scope_if_researcher_approves"],
                "alignment_and_analysis_candidate",
            )
            self.assertEqual(row["researcher_decision"], "pending")
            self.assertFalse(manifest["policy"]["automatic_exclusion_performed"])


if __name__ == "__main__":
    unittest.main()
