import sys
import tempfile
import unittest
import wave
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from plan_wav_duration_recovery import plan_session  # noqa: E402


def write_wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(b"\0\0" * round(seconds * 16_000))


class PlanWavDurationRecoveryTests(unittest.TestCase):
    def test_long_shift_is_remap_and_short_match_stays_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav_dir = Path(tmp) / "wav"
            expected = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
            observed = [1.0, 9.0, 4.0, 5.0, 6.0]
            rows = [
                {"utt_id": f"S1.{index}", "dur": str(duration)}
                for index, duration in enumerate(expected, 1)
            ]
            for index, duration in enumerate(observed, 1):
                write_wav(wav_dir / f"S1.{index}.wav", duration + 0.01)

            result = plan_session(
                year="2020",
                session="S1",
                csv_rows=rows,
                wav_dir=wav_dir,
            )
            by_target = {
                row["target_utt_id"]: row
                for row in result
                if row["target_utt_id"]
            }
            self.assertEqual(
                by_target["S1.1"]["status"], "ambiguous_short_match"
            )
            self.assertEqual(
                by_target["S1.4"]["status"], "remap_high_confidence"
            )
            self.assertEqual(by_target["S1.4"]["source_utt_id"], "S1.3")
            self.assertEqual(
                by_target["S1.2"]["status"], "target_unresolved"
            )
            self.assertTrue(
                any(row["status"] == "source_orphan" for row in result)
            )


if __name__ == "__main__":
    unittest.main()
