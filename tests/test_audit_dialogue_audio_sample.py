from __future__ import annotations

import csv
import gzip
import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_SCRIPTS = ROOT / "scripts" / "python"
if str(PYTHON_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PYTHON_SCRIPTS))

from audit_dialogue_audio_sample import (  # noqa: E402
    deterministic_sample,
    percentile_ranks,
    read_wav_metrics,
    run_audit,
)


def write_wave(path: Path, *, amplitude: float, seconds: float = 0.2) -> None:
    rate = 16_000
    values = [
        int(amplitude * 32767 * math.sin(2 * math.pi * 220 * index / rate))
        for index in range(int(rate * seconds))
    ]
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(struct.pack(f"<{len(values)}h", *values))


class DialogueAudioSampleTests(unittest.TestCase):
    def test_deterministic_sample_keeps_endpoints(self) -> None:
        files = [Path(f"{number:03d}.wav") for number in range(10)]
        sample = deterministic_sample(files, 4)
        self.assertEqual(sample[0].name, "000.wav")
        self.assertEqual(sample[-1].name, "009.wav")
        self.assertEqual(len(sample), 4)

    def test_percentile_rank_ties_are_stable(self) -> None:
        ranks = percentile_ranks({"a": -60.0, "b": -40.0, "c": -40.0})
        self.assertEqual(ranks["a"], 0.0)
        self.assertEqual(ranks["b"], 75.0)
        self.assertEqual(ranks["c"], 75.0)

    def test_wav_metrics_have_expected_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "tone.wav"
            write_wave(path, amplitude=0.5)
            metrics = read_wav_metrics(path, frame_ms=20.0, edge_ms=50.0)
            self.assertEqual(metrics["sample_rate"], 16_000)
            self.assertEqual(metrics["channels"], 1)
            self.assertAlmostEqual(metrics["duration_sec"], 0.2, places=6)
            self.assertLess(metrics["digital_clip_fraction"], 0.001)

    def test_run_preserves_pending_and_reported_noise_as_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            wav_root = temp / "wav"
            session = "SDRW2200000001"
            session_root = wav_root / session
            session_root.mkdir(parents=True)
            for number, amplitude in enumerate((0.1, 0.2, 0.4), start=1):
                write_wave(
                    session_root / f"{session}.1.1.{number}.wav",
                    amplitude=amplitude,
                )
            structural = temp / "sessions.csv.gz"
            with gzip.open(
                structural, "wt", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=["session_id"])
                writer.writeheader()
                writer.writerow({"session_id": session})
            manifest = run_audit(
                year="2022",
                wav_root=wav_root,
                structural_session_summary=structural,
                output_root=temp / "out",
                samples_per_session=2,
                full_sessions={session},
                researcher_reported_noise_sessions={session},
            )
            self.assertFalse(
                manifest["policy"]["automatic_exclusion_performed"]
            )
            self.assertEqual(manifest["counts"]["sampled_wavs"], 3)
            with gzip.open(
                temp / "out" / "02_SESSION_AUDIO_SUMMARY.csv.gz",
                "rt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["researcher_reported_noise"], "true")
            self.assertEqual(
                rows[0]["review_priority"],
                "researcher_reported_noise_review",
            )
            self.assertEqual(rows[0]["researcher_decision"], "pending")


if __name__ == "__main__":
    unittest.main()
