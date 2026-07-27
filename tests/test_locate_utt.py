import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import locate_utt  # noqa: E402


class LocateUttTests(unittest.TestCase):
    def test_quarantine_prefers_session_layout_and_uses_config_root(self):
        utt_id = "SDRW2000000001.1.1.1"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            roots = {
                "wav": root / "wav",
                "textgrid_eojeol": root / "textgrid_eojeol",
                "textgrid_merged": root / "textgrid_merged",
                "layers": root / "layers",
                "mfa_state": root / "mfa_state",
            }
            quarantine = (
                roots["mfa_state"]
                / "quarantine"
                / "2020"
                / "SDRW2000000001"
                / f"{utt_id}.wav"
            )
            quarantine.parent.mkdir(parents=True)
            quarantine.write_bytes(b"RIFF")

            with patch.object(locate_utt, "P", side_effect=roots.__getitem__):
                result = locate_utt.locate(utt_id)

            self.assertEqual(result["quarantine"], quarantine)

    def test_quarantine_legacy_flat_layout_remains_supported(self):
        utt_id = "SDRW2000000001.1.1.1"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            roots = {
                "wav": root / "wav",
                "textgrid_eojeol": root / "textgrid_eojeol",
                "textgrid_merged": root / "textgrid_merged",
                "layers": root / "layers",
                "mfa_state": root / "mfa_state",
            }
            quarantine = (
                roots["mfa_state"]
                / "quarantine"
                / "2020"
                / f"{utt_id}.wav"
            )
            quarantine.parent.mkdir(parents=True)
            quarantine.write_bytes(b"RIFF")

            with patch.object(locate_utt, "P", side_effect=roots.__getitem__):
                result = locate_utt.locate(utt_id)

            self.assertEqual(result["quarantine"], quarantine)


if __name__ == "__main__":
    unittest.main()
