import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from patch_mfa_export_queue import (  # noqa: E402
    NEW_PRODUCER,
    NEW_WORKER,
    OLD_PRODUCER,
    OLD_WORKER,
    inspect_and_patch,
)
from verify_mfa_install import inspect_mfa_source  # noqa: E402


class PatchMfaExportQueueTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        package = root / "montreal_forced_aligner"
        (package / "alignment").mkdir(parents=True)
        (package / "command_line").mkdir()
        (package / "command_line" / "align.py").write_text(
            """
import os
def f(aligner, output_directory, output_format):
    if not os.environ.get("MFA_PROJECT_SKIP_TEXTGRID_EXPORT"):
        aligner.export_files(output_directory, output_format=output_format)
    if not os.environ.get("MFA_PROJECT_SKIP_TEXTGRID_EXPORT"):
        aligner.export_files(output_directory, output_format=output_format)
""",
            encoding="utf-8",
        )
        (package / "alignment" / "multiprocessing.py").write_text(
            "def worker(self):\n"
            + OLD_WORKER
            + "                        pass\n"
            + "    output_path = None\n"
            + "    try:\n"
            + "        pass\n"
            + "    finally:\n"
            + "        self.finished_processing.set()\n",
            encoding="utf-8",
        )
        (package / "alignment" / "base.py").write_text(
            "def producer():\n" + OLD_PRODUCER,
            encoding="utf-8",
        )
        (package / "textgrid.py").write_text(
            """
def construct_textgrid_output():
    _CHUNK = 50000
def _construct_textgrid_output_impl():
    pass
""",
            encoding="utf-8",
        )
        return package

    def test_applies_with_backup_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            backup = root / "backup"
            result = inspect_and_patch(
                package, apply=True, backup_root=backup
            )
            self.assertEqual(result["status"], "patched")
            self.assertTrue((backup / "manifest_before.json").is_file())
            self.assertIn(
                NEW_WORKER,
                (package / "alignment" / "multiprocessing.py").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertIn(
                NEW_PRODUCER,
                (package / "alignment" / "base.py").read_text(
                    encoding="utf-8"
                ),
            )
            second = inspect_and_patch(
                package, apply=True, backup_root=None
            )
            self.assertEqual(second["status"], "already_patched")

    def test_verifier_fails_before_and_passes_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            self.assertFalse(inspect_mfa_source(package)["ok"])
            inspect_and_patch(
                package, apply=True, backup_root=root / "backup"
            )
            self.assertTrue(inspect_mfa_source(package)["ok"])


if __name__ == "__main__":
    unittest.main()
