import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPTS))

from build_mfa_missing_textgrid_inventory import build_inventory  # noqa: E402


class MissingTextgridInventoryTests(unittest.TestCase):
    def test_builds_lab_minus_textgrid_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            labs = root / "labs" / "2020" / "SESSION"
            grids = root / "grids" / "2020" / "SESSION"
            labs.mkdir(parents=True)
            grids.mkdir(parents=True)
            for utt_id in ("U1", "U2", "U3"):
                (labs / f"{utt_id}.lab").write_text("가", encoding="utf-8")
                (labs / f"{utt_id}.wav").write_bytes(b"RIFF")
            for utt_id in ("U1", "U3"):
                (grids / f"{utt_id}.TextGrid").write_text(
                    "TextGrid",
                    encoding="utf-8",
                )

            rows, report = build_inventory(
                year="2020",
                lab_root=root / "labs" / "2020",
                textgrid_root=root / "grids" / "2020",
            )

            self.assertEqual([row["utt_id"] for row in rows], ["U2"])
            self.assertEqual(report["lab_ids"], 3)
            self.assertEqual(report["textgrid_ids"], 2)
            self.assertEqual(report["lab_without_textgrid"], 1)
            self.assertEqual(report["textgrid_without_lab"], 0)
            self.assertEqual(report["missing_with_wav"], 1)
            self.assertEqual(report["status"], "success")


if __name__ == "__main__":
    unittest.main()
