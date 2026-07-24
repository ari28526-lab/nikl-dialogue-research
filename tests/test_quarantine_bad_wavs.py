import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from quarantine_bad_wavs import scan_year  # noqa: E402


class QuarantineTests(unittest.TestCase):
    def test_apply_preserves_relative_path_and_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wav_root = root / "wav"
            source_dir = wav_root / "2020" / "SESSION1"
            source_dir.mkdir(parents=True)
            wav = source_dir / "utt.wav"
            lab = source_dir / "utt.lab"
            wav.write_bytes(b"")
            lab.write_text("국물", encoding="utf-8")
            quarantine = root / "quarantine"

            count = scan_year(
                "2020", 44, True,
                wav_root=wav_root, quarantine_root=quarantine,
            )
            self.assertEqual(count, 1)
            self.assertFalse(wav.exists())
            self.assertFalse(lab.exists())
            self.assertTrue(
                (quarantine / "2020" / "SESSION1" / "utt.wav").exists()
            )
            self.assertTrue(
                (quarantine / "2020" / "SESSION1" / "utt.lab").exists()
            )
            transactions = list(
                (quarantine / "2020" / "_transactions").glob("*.json")
            )
            self.assertEqual(len(transactions), 1)
            record = json.loads(transactions[0].read_text(encoding="utf-8-sig"))
            self.assertEqual(record["status"], "complete")

    def test_dry_run_does_not_move_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "wav" / "2020" / "S" / "u.wav"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"")
            count = scan_year(
                "2020", 44, False,
                wav_root=root / "wav", quarantine_root=root / "q",
            )
            self.assertEqual(count, 1)
            self.assertTrue(source.exists())
            self.assertFalse((root / "q").exists())


if __name__ == "__main__":
    unittest.main()
