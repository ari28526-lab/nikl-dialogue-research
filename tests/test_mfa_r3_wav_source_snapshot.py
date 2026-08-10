from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.python.build_mfa_r3_wav_source_snapshot import build, contract_id


class WavSourceSnapshotTests(unittest.TestCase):
    def test_snapshot_is_read_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wav_root = root / "2021" / "S1"
            wav_root.mkdir(parents=True)
            first_wav = wav_root / "u1.wav"
            second_wav = wav_root / "u2.wav"
            first_wav.write_bytes(b"RIFFone")
            second_wav.write_bytes(b"RIFFtwo")
            output = root / "snapshot.json"
            first = build(year="2021", wav_root=wav_root.parent, output=output)
            second = build(year="2021", wav_root=wav_root.parent, output=output)
            self.assertEqual(first["corpus_contract_id"], second["corpus_contract_id"])
            self.assertEqual(first["corpus_contract_id"], contract_id(first))
            self.assertEqual(first["wav_files"], 2)
            self.assertEqual(first_wav.read_bytes(), b"RIFFone")
            self.assertEqual(second_wav.read_bytes(), b"RIFFtwo")

    def test_changed_inventory_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wav_root = root / "2021"
            wav_root.mkdir()
            (wav_root / "u1.wav").write_bytes(b"RIFFone")
            output = root / "snapshot.json"
            build(year="2021", wav_root=wav_root, output=output)
            (wav_root / "u2.wav").write_bytes(b"RIFFtwo")
            with self.assertRaisesRegex(RuntimeError, "overwrite refused"):
                build(year="2021", wav_root=wav_root, output=output)


if __name__ == "__main__":
    unittest.main()
