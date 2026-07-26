import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from patch_mfa_skip_export import (  # noqa: E402
    NEW_EXPORT,
    NEW_IMPORT,
    OLD_EXPORT,
    OLD_IMPORT,
    inspect_and_patch,
)


class PatchMfaSkipExportTests(unittest.TestCase):
    def test_applies_two_guarded_calls_and_preserves_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "montreal_forced_aligner"
            path = package / "command_line" / "align.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                OLD_IMPORT + "\ndef a():\n" + OLD_EXPORT
                + "\ndef b():\n" + OLD_EXPORT,
                encoding="utf-8",
            )
            backup = root / "backup"
            result = inspect_and_patch(
                package, apply=True, backup_root=backup
            )
            self.assertEqual(result["status"], "patched")
            text = path.read_text(encoding="utf-8")
            self.assertIn(NEW_IMPORT, text)
            self.assertEqual(text.count(NEW_EXPORT), 2)
            self.assertTrue(
                (backup / "command_line" / "align.py").is_file()
            )
            second = inspect_and_patch(
                package, apply=True, backup_root=None
            )
            self.assertEqual(second["status"], "already_patched")


if __name__ == "__main__":
    unittest.main()
