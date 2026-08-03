import importlib.util
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "scripts" / "python"
sys.path.insert(0, str(PYTHON_DIR))
SPEC = importlib.util.spec_from_file_location(
    "plan_wav_duration_recovery",
    PYTHON_DIR / "plan_wav_duration_recovery.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_wav(path: Path, seconds: float) -> None:
    rate = 16_000
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(b"\0\0" * round(seconds * rate))


class PlanWavDurationRecoveryTests(unittest.TestCase):
    def test_direct_identity_survives_unrelated_bad_wav(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wav_dir = Path(temporary)
            # WAV에는 exporter padding 0.01초가 더 있다고 가정한다.
            write_wav(wav_dir / "U.1.wav", 1.01)
            write_wav(wav_dir / "U.2.wav", 2.01)
            write_wav(wav_dir / "U.3.wav", 3.01)
            write_wav(wav_dir / "U.4.wav", 0.10)
            # CSV 순서가 자연 정렬과 달라도 same-ID+duration은 보존돼야 한다.
            csv_rows = [
                {"utt_id": "U.2", "dur": "2.0"},
                {"utt_id": "U.1", "dur": "1.0"},
                {"utt_id": "U.3", "dur": "3.0"},
                {"utt_id": "U.4", "dur": "4.0"},
            ]

            rows = MODULE.plan_session(
                year="2021",
                session="U",
                csv_rows=csv_rows,
                wav_dir=wav_dir,
                affected_target_ids={"U.4"},
            )
            by_target = {
                row["target_utt_id"]: row
                for row in rows
                if row["target_utt_id"]
            }

            for utt_id in ("U.1", "U.2", "U.3"):
                self.assertEqual(
                    by_target[utt_id]["status"], "identity_high_confidence"
                )
                self.assertEqual(by_target[utt_id]["source_utt_id"], utt_id)
            self.assertEqual(by_target["U.4"]["status"], "target_unresolved")


if __name__ == "__main__":
    unittest.main()
