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

    def test_coarser_quantum_can_recover_shifted_near_equal_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wav_dir = Path(temporary)
            # U.1은 끼어든 짧은 조각이고 실제 U.1~U.4 음성은 WAV 번호가
            # 하나씩 밀렸다. 길이가 각각 1 ms 달라 1 ms token은 다르지만
            # 5 ms 민감도 분석에서는 하나의 긴 연속열로 일치한다.
            write_wav(wav_dir / "U.1.wav", 0.05)
            for source_index, seconds in enumerate(
                (1.002, 2.002, 3.002, 4.002), start=2
            ):
                write_wav(wav_dir / f"U.{source_index}.wav", seconds)
            csv_rows = [
                {"utt_id": f"U.{index}", "dur": f"{index}.001"}
                for index in range(1, 5)
            ]

            rows = MODULE.plan_session(
                year="2023",
                session="U",
                csv_rows=csv_rows,
                wav_dir=wav_dir,
                padding_seconds=0,
                duration_quantum_ms=5,
                affected_target_ids={row["utt_id"] for row in csv_rows},
            )
            mapped = [
                row for row in rows
                if row["status"] == "remap_high_confidence"
            ]
            self.assertEqual(len(mapped), 4)
            self.assertEqual(
                [row["source_utt_id"] for row in mapped],
                ["U.2", "U.3", "U.4", "U.5"],
            )
            self.assertTrue(all(row["block_length"] == 4 for row in mapped))


if __name__ == "__main__":
    unittest.main()
