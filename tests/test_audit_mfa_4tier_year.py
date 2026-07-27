import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPTS))

from audit_mfa_4tier_year import audit_year  # noqa: E402
from realign_eojeol_merge_output import write_4tier  # noqa: E402


def make_wav(path: Path, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 16000
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(b"\x00\x00" * int(rate * seconds))


class AuditMfa4TierYearTests(unittest.TestCase):
    def make_utterance(
        self,
        root: Path,
        utt_id: str,
        *,
        make_textgrid: bool = True,
    ) -> tuple[Path, Path]:
        session = utt_id.split(".", 1)[0]
        lab_dir = root / "labs" / session
        grid_dir = root / "grids" / session
        lab_dir.mkdir(parents=True, exist_ok=True)
        grid_dir.mkdir(parents=True, exist_ok=True)
        (lab_dir / f"{utt_id}.lab").write_text("가", encoding="utf-8")
        make_wav(lab_dir / f"{utt_id}.wav")
        grid_path = grid_dir / f"{utt_id}.TextGrid"
        if make_textgrid:
            write_4tier(
                grid_path,
                1.0,
                [(0.0, 0.8, "가")],
                [(0.0, 0.8, "k")],
                [(0.0, 0.8, "가")],
                "가",
            )
        return lab_dir, grid_path

    def test_full_valid_tree_passes_and_reports_visible_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_utterance(root, "S1.1")
            report_path = root / "report.json"
            missing_csv = root / "missing.csv"
            progress = root / "progress.jsonl"
            report = audit_year(
                year="2021",
                lab_root=root / "labs",
                textgrid_root=root / "grids",
                report_path=report_path,
                missing_csv_path=missing_csv,
                progress_jsonl=progress,
                workers=2,
                batch_size=1,
            )
            self.assertEqual(report["status"], "success")
            self.assertEqual(report["coverage_pct"], 100.0)
            self.assertEqual(report["counts"]["valid_textgrids"], 1)
            self.assertEqual(report["counts"]["invalid_textgrids"], 0)
            self.assertEqual(
                report["visible_edge_diagnostics"]["words"][
                    "left_blank_at_least_threshold"
                ],
                0,
            )
            self.assertEqual(
                report["visible_edge_diagnostics"]["words"][
                    "right_blank_at_least_threshold"
                ],
                1,
            )
            events = [
                json.loads(line)["event"]
                for line in progress.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(
                events,
                ["audit_started", "audit_completed"],
            )
            self.assertTrue(report_path.is_file())
            self.assertIn(
                "utt_id",
                missing_csv.read_text(encoding="utf-8-sig"),
            )

    def test_missing_textgrid_is_in_inventory_and_fails_low_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_utterance(root, "S1.1")
            self.make_utterance(
                root, "S1.2", make_textgrid=False
            )
            report = audit_year(
                year="2021",
                lab_root=root / "labs",
                textgrid_root=root / "grids",
                report_path=root / "report.json",
                missing_csv_path=root / "missing.csv",
                workers=1,
                batch_size=1,
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["coverage_pct"], 50.0)
            self.assertEqual(
                report["counts"]["lab_without_textgrid"], 1
            )
            self.assertIn(
                "S1.2",
                (root / "missing.csv").read_text(
                    encoding="utf-8-sig"
                ),
            )

    def test_wav_duration_mismatch_is_hard_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lab_dir, _grid = self.make_utterance(root, "S1.1")
            make_wav(lab_dir / "S1.1.wav", seconds=0.5)
            report = audit_year(
                year="2021",
                lab_root=root / "labs",
                textgrid_root=root / "grids",
                report_path=root / "report.json",
                missing_csv_path=root / "missing.csv",
                workers=1,
                batch_size=1,
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(
                report["reason_counts"]["wav_duration_mismatch"], 1
            )

    def test_interval_gap_is_hard_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _lab_dir, grid = self.make_utterance(root, "S1.1")
            text = grid.read_text(encoding="utf-8")
            changed = text.replace(
                "            xmax = 0.800000",
                "            xmax = 0.700000",
                1,
            )
            self.assertNotEqual(text, changed)
            grid.write_text(changed, encoding="utf-8")
            report = audit_year(
                year="2021",
                lab_root=root / "labs",
                textgrid_root=root / "grids",
                report_path=root / "report.json",
                missing_csv_path=root / "missing.csv",
                workers=1,
                batch_size=1,
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["reason_counts"]["gap"], 1)


if __name__ == "__main__":
    unittest.main()
