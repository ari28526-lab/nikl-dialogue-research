import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from verify_mfa_install import inspect_mfa_source  # noqa: E402


GOOD_ALIGN = """
import os
def a(aligner, output_format):
    aligner.align()
    if not os.environ.get("MFA_PROJECT_SKIP_TEXTGRID_EXPORT"):
        aligner.export_files(output_format=output_format)
def b(aligner, output_format):
    aligner.align()
    if not os.environ.get("MFA_PROJECT_SKIP_TEXTGRID_EXPORT"):
        aligner.export_files(output_format=output_format)
"""
GOOD_MP = """
def run(self):
    output_path = None
    try:
        file_batch = self.for_write_queue.get()
        if file_batch is None:
            return
    finally:
        self.finished_processing.set()
"""
GOOD_BASE = """
def export(export_procs, for_write_queue):
    for _ in export_procs:
        for_write_queue.put(None)
"""
GOOD_TG = """
def construct_textgrid_output():
    _CHUNK = 50_000
    return _construct_textgrid_output_impl()
def _construct_textgrid_output_impl():
    return None
"""


class MfaPatchVerificationTests(unittest.TestCase):
    def make_root(
        self, align=GOOD_ALIGN, mp=GOOD_MP, base=GOOD_BASE, tg=GOOD_TG
    ):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "command_line").mkdir()
        (root / "alignment").mkdir()
        (root / "command_line" / "align.py").write_text(align, encoding="utf-8")
        (root / "alignment" / "multiprocessing.py").write_text(
            mp, encoding="utf-8"
        )
        (root / "alignment" / "base.py").write_text(base, encoding="utf-8")
        (root / "textgrid.py").write_text(tg, encoding="utf-8")
        return temp, root

    def test_accepts_required_patch_structure(self):
        temp, root = self.make_root()
        try:
            result = inspect_mfa_source(root)
            self.assertTrue(result["ok"], result["checks"])
        finally:
            temp.cleanup()

    def test_rejects_analyze_alignments_call(self):
        bad = GOOD_ALIGN.replace(
            "aligner.align()", "aligner.align()\n    aligner.analyze_alignments()", 1
        )
        temp, root = self.make_root(align=bad)
        try:
            result = inspect_mfa_source(root)
            self.assertFalse(result["ok"])
            check = next(
                c for c in result["checks"]
                if c["name"] == "quality_analysis_call_removed"
            )
            self.assertFalse(check["ok"])
        finally:
            temp.cleanup()

    def test_rejects_missing_export_finally(self):
        bad = "def run(self):\n    output_path = None\n"
        temp, root = self.make_root(mp=bad)
        try:
            self.assertFalse(inspect_mfa_source(root)["ok"])
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
