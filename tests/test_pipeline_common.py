import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from pipeline_common import (  # noqa: E402
    atomic_write_json,
    promote_staged,
    staged_text_writer,
)


class AtomicOutputTests(unittest.TestCase):
    def test_failed_stage_does_not_replace_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "result.txt"
            destination.write_text("old", encoding="utf-8")
            staged = None
            with self.assertRaises(RuntimeError):
                with staged_text_writer(destination) as (stream, staged):
                    stream.write("partial")
                    raise RuntimeError("injected failure")
            self.assertEqual(destination.read_text(encoding="utf-8"), "old")
            self.assertTrue(staged.exists())
            self.assertEqual(staged.read_text(encoding="utf-8"), "partial")

    def test_promote_replaces_only_after_explicit_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "result.txt"
            destination.write_text("old", encoding="utf-8")
            with staged_text_writer(destination) as (stream, staged):
                stream.write("new")
            self.assertEqual(destination.read_text(encoding="utf-8"), "old")
            promote_staged(staged, destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "new")

    def test_atomic_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "run.json"
            atomic_write_json(destination, {"상태": "성공", "n": 2})
            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                {"상태": "성공", "n": 2},
            )


if __name__ == "__main__":
    unittest.main()
