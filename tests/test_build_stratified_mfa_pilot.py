import csv
import sys
import tempfile
import unittest
import wave
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_stratified_mfa_pilot import select_year  # noqa: E402


def write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\0\0" * 1_600)


def make_session(
    raw_dir: Path,
    wav_year: Path,
    morph_year: Path,
    session_id: str,
    speaker_id: str,
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(1, 4):
        utt_id = f"{session_id}.1.1.{index}"
        rows.append({
            "utt_id": utt_id,
            "speaker_id": speaker_id,
            "form": f"화자 발화 {index}",
            "tagged": "화자/NNG 발화/NNG",
            "n_morphs": "2",
        })
        write_wav(wav_year / session_id / f"{utt_id}.wav")
        morph = morph_year / session_id / f"{utt_id}.TextGrid"
        morph.parent.mkdir(parents=True, exist_ok=True)
        morph.write_text("synthetic", encoding="utf-8")
    with open(
        raw_dir / f"{session_id}.csv", "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class StratifiedPilotSelectionTests(unittest.TestCase):
    def test_selects_five_real_speakers_from_five_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / "raw"
            wav = base / "wav"
            morph = base / "morph"
            for index in range(1, 7):
                make_session(
                    raw,
                    wav,
                    morph,
                    f"SDRW200000{index:04d}",
                    f"SPK{index:02d}",
                )
            selected = select_year(
                year="2020",
                raw_dir=raw,
                wav_year=wav,
                morph_year=morph,
                utterances=10,
                speakers=5,
                seed="test-seed",
            )
            self.assertEqual(len(selected), 10)
            self.assertEqual(len({row["speaker_id"] for row in selected}), 5)
            self.assertEqual(len({row["session_id"] for row in selected}), 5)
            self.assertEqual(
                set(Counter(row["speaker_id"] for row in selected).values()),
                {2},
            )

    def test_fails_instead_of_silently_using_too_few_speakers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / "raw"
            wav = base / "wav"
            morph = base / "morph"
            for index in range(1, 5):
                make_session(
                    raw,
                    wav,
                    morph,
                    f"SDRW200000{index:04d}",
                    f"SPK{index:02d}",
                )
            with self.assertRaises(RuntimeError):
                select_year(
                    year="2020",
                    raw_dir=raw,
                    wav_year=wav,
                    morph_year=morph,
                    utterances=10,
                    speakers=5,
                    seed="test-seed",
                )


if __name__ == "__main__":
    unittest.main()
