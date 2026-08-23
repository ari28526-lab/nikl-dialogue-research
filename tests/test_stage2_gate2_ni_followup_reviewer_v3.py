"""Unit tests for the Stage 2 Gate 2 NI follow-up reviewer v3."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import uuid
import wave
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import audit_stage2_gate2_ni_followup_reviewer_v3 as auditor  # noqa: E402
import build_stage2_gate2_ni_followup_reviewer_v3 as builder  # noqa: E402


class Gate2ReviewerV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document, cls.receipt, cls.assets = builder.prepare(
            source_dir=builder.DEFAULT_SOURCE_DIR,
            pv_root=builder.DEFAULT_PV_ROOT,
            plan_path=builder.DEFAULT_PLAN,
        )

    def test_real_preflight_success(self) -> None:
        self.assertEqual(self.receipt["status"], "preflight_ready")
        self.assertEqual(len(self.assets), 14)
        self.assertEqual(
            self.receipt["asset_projection"]["asset_status_counts"],
            {"available": 14, "unavailable": 0, "blocked": 0},
        )
        self.assertEqual(
            [row["pv_id"] for row in self.assets if row["gate_method_role"] == "ni_method_reference"],
            ["PV0015", "PV0163"],
        )
        self.assertIn("PV_REVIEWER_V3_TEST_API", self.document)
        self.assertNotIn('<label for="priority-filter">우선순위</label>', self.document)

    def test_pinned_sha_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temp_dir:
            path = Path(temp_dir) / "changed.bin"
            path.write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                builder.verify_pinned_file(path, "0" * 64, "test source")

    def test_manifest_sha_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temp_dir:
            path = Path(temp_dir) / "PV_MANIFEST.json"
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                builder.verify_pinned_file(
                    path, builder.EXPECTED_SHA256["pv_manifest"], "PV manifest"
                )

    def test_invalid_textgrid_is_blocked_without_drop(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temp_dir:
            root = Path(temp_dir)
            textgrid = root / "target_source.TextGrid"
            wav = root / "target.wav"
            manifest = root / "PACKAGE_MANIFEST.json"
            textgrid.write_text("not a TextGrid\n", encoding="utf-8")
            with wave.open(str(wav), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(b"\x00\x00" * 1600)
            tg_sha = hashlib.sha256(textgrid.read_bytes()).hexdigest()
            wav_sha = hashlib.sha256(wav.read_bytes()).hexdigest()
            package = {
                "pv_id": "PVTEST",
                "files": [
                    {"path": "target_source.TextGrid", "sha256": tg_sha},
                    {"path": "target.wav", "sha256": wav_sha},
                ],
            }
            manifest.write_text(json.dumps(package), encoding="utf-8")
            sample = {"pv_id": "PVTEST", "phenomenon_code": "NI"}
            sample_row = {
                "target_xmin": "0.01",
                "target_xmax": "0.05",
                "timing_status": "linked_single_eojeol_context_span",
                "active_textgrid_sha256": tg_sha,
            }
            asset = builder.build_asset(
                sample,
                sample_row,
                {"manifest_path": manifest, "manifest": package},
            )
            self.assertEqual(asset["pv_id"], "PVTEST")
            self.assertEqual(asset["textgrid_asset_status"], "blocked")
            self.assertTrue(asset["asset_issue_codes"])

    def test_existing_output_fails_before_write(self) -> None:
        output = (
            PROJECT_ROOT
            / "outputs"
            / "pilots"
            / f"_gate2_existing_output_test_{uuid.uuid4().hex}"
        )
        output.mkdir()
        try:
            with self.assertRaises(FileExistsError):
                builder.build(
                    source_dir=builder.DEFAULT_SOURCE_DIR,
                    pv_root=builder.DEFAULT_PV_ROOT,
                    plan_path=builder.DEFAULT_PLAN,
                    output_dir=output,
                )
        finally:
            output.rmdir()

    def test_manifest_excludes_itself_and_partial(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("a", encoding="utf-8")
            manifest = root / auditor.MANIFEST_NAME
            manifest.write_text("old", encoding="utf-8")
            partial = manifest.with_name(manifest.name + ".partial")
            partial.write_text("partial", encoding="utf-8")
            rows = auditor.manifest_rows(root, manifest)
            names = [row[0] for row in rows]
            self.assertEqual(names, ["a.txt"])

    def test_textgrid_parser_measures_six_tiers(self) -> None:
        path = (
            builder.DEFAULT_PV_ROOT
            / "bundle"
            / "015__NI__2020__SDRW2000000145_1_1_20"
            / "target_source.TextGrid"
        )
        parsed = builder.parse_long_textgrid(path)
        self.assertEqual([row["name"] for row in parsed["tiers"]], builder.EXPECTED_TIERS)
        self.assertGreater(parsed["xmax"], 0)


if __name__ == "__main__":
    unittest.main()
