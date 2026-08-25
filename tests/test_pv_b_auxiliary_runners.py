from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_SCRIPTS = ROOT / "scripts" / "python"
sys.path.insert(0, str(PYTHON_SCRIPTS))

from pv_b_aux_common import load_input_manifest, sha256_file  # noqa: E402
from run_pv_b_wav2vec2 import collapse_ctc_ids  # noqa: E402


def write_silence_wav(path: Path, frames: int = 1600, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


class PvBAuxiliaryRunnerTests(unittest.TestCase):
    def make_manifest(self, root: Path) -> Path:
        wav_path = root / "sample.wav"
        write_silence_wav(wav_path)
        manifest = root / "input.jsonl"
        row = {
            "schema_version": "stage2_pv_b_input.v1",
            "pv_id": "PVB-NI-001",
            "phenomenon_code": "NI",
            "occurrence_id": "OCC-001",
            "utt_id": "UTT-001",
            "wav_path": str(wav_path),
            "text": "테스트",
            "sex": "U",
            "source_wav_sha256": sha256_file(wav_path),
        }
        manifest.write_text(
            json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return manifest

    def test_manifest_validation_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.make_manifest(Path(tmp))
            rows = load_input_manifest(manifest, limit=1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["_wav_metadata"]["sample_rate"], 16000)
            self.assertEqual(rows[0]["_wav_sha256"], rows[0]["source_wav_sha256"])

    def test_ctc_collapse_preserves_blank_separation(self) -> None:
        spans = collapse_ctc_ids(
            [0, 2, 2, 0, 2, 3, 3],
            [1.0, 0.8, 0.6, 0.9, 0.7, 0.5, 0.9],
            blank_id=0,
            frame_seconds=0.02,
            token_for_id=lambda value: {2: "n", 3: "a"}[value],
        )
        self.assertEqual([row["token"] for row in spans], ["n", "n", "a"])
        self.assertEqual(spans[0]["start_seconds"], 0.02)
        self.assertEqual(spans[0]["end_seconds"], 0.06)
        self.assertAlmostEqual(spans[0]["mean_frame_probability"], 0.7)

    def test_both_preflights_need_no_model_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.make_manifest(root)
            for script_name in ("run_pv_b_koina.py", "run_pv_b_wav2vec2.py"):
                output_dir = root / (script_name + "_out")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(PYTHON_SCRIPTS / script_name),
                        "--input-manifest",
                        str(manifest),
                        "--output-dir",
                        str(output_dir),
                        "--limit",
                        "1",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                report = json.loads(result.stdout)
                self.assertEqual(report["status"], "preflight_passed")
                self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
