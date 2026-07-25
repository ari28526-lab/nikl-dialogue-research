import csv
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import stitch_session as stitch  # noqa: E402
from realign_eojeol_merge_output import write_4tier  # noqa: E402


class StitchSessionTests(unittest.TestCase):
    def write_wav(self, path: Path, frames: int = 1600) -> None:
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x01\x00" * frames)

    def test_gap_manifest_and_review_tier_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            identifiers = ["SDRW2000000001.1.1.1", "SDRW2000000001.1.1.2"]
            locations = {}
            rows = []
            for index, uid in enumerate(identifiers, 1):
                wav_path = source / f"{uid}.wav"
                tg_path = source / f"{uid}.TextGrid"
                self.write_wav(wav_path)
                write_4tier(
                    tg_path,
                    0.1,
                    [(0.0, 0.1, f"어절{index}")],
                    [(0.0, 0.1, "p")],
                    [(0.0, 0.1, f"형태소{index}")],
                    f"발화 {index}",
                )
                locations[uid] = {
                    "wav": wav_path,
                    "textgrid_eojeol": tg_path,
                }
                rows.append(
                    {
                        "utt_id": uid,
                        "form": f"발화 {index}",
                        "speaker_id": f"S{index}",
                    }
                )

            old_argv = sys.argv
            old_ordered = stitch.ordered_utts
            old_locate = stitch.locate
            old_parse = stitch.parse_utt
            try:
                stitch.ordered_utts = lambda _session, _year: rows
                stitch.locate = lambda uid: locations[uid]
                stitch.parse_utt = lambda _value: ("2020", "")
                sys.argv = [
                    "stitch_session.py",
                    "--session",
                    "SDRW2000000001",
                    "--out",
                    str(output),
                    "--gap-seconds",
                    "0.05",
                ]
                self.assertEqual(stitch.main(), 0)
            finally:
                sys.argv = old_argv
                stitch.ordered_utts = old_ordered
                stitch.locate = old_locate
                stitch.parse_utt = old_parse

            tag = "SDRW2000000001_stitched"
            with wave.open(str(output / f"{tag}.wav")) as stitched_wav:
                self.assertAlmostEqual(
                    stitched_wav.getnframes() / stitched_wav.getframerate(),
                    0.25,
                    places=6,
                )
            with (output / f"{tag}_manifest.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                manifest = list(csv.DictReader(handle))
            self.assertEqual(len(manifest), 2)
            self.assertEqual(manifest[0]["gap_after_seconds"], "0.050000")
            self.assertEqual(
                manifest[1]["stitched_start_seconds"],
                "0.150000",
            )
            tiers = stitch.parse_tg_tiers(output / f"{tag}.TextGrid")
            self.assertEqual(
                list(tiers),
                [
                    "utterance",
                    "speaker",
                    "words",
                    "phones_mfa",
                    "morphemes_legacy",
                ],
            )
            self.assertIn((0.1, 0.15, ""), tiers["utterance"])


if __name__ == "__main__":
    unittest.main()
