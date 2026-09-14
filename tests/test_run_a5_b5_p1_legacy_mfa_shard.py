from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "run_a5_b5_p1_legacy_mfa_shard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_a5_b5_p1_legacy_mfa_shard", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class B5P1Tests(unittest.TestCase):
    def test_shard_selection_matches_contract(self):
        module = load_module()
        relative = "corpus/SDRW2000000001.wav"
        expected = hashlib.sha256(relative.encode("utf-8")).digest()[0] & 63
        self.assertEqual(module.shard_for(relative), expected)
        with self.assertRaises(ValueError):
            module.shard_for(relative, 48)

    def test_ledger_is_order_and_size_sensitive(self):
        module = load_module()
        first = hashlib.sha256()
        second = hashlib.sha256()
        module._ledger_update(first, "a.wav", 10)
        module._ledger_update(first, "b.lab", 2)
        module._ledger_update(second, "b.lab", 2)
        module._ledger_update(second, "a.wav", 10)
        self.assertNotEqual(first.hexdigest(), second.hexdigest())

    def test_known_b4_partial_mismatch_is_acceptable_only_after_terminal_stop(self):
        module = load_module()
        state = {
            "status": "failed_safe_to_review",
            "pid": None,
            "errors": [
                {
                    "type": "RuntimeError",
                    "message": "one or more E partial files do not match an H same-path source by size",
                }
            ],
        }
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            absent_lock = Path(directory) / "absent.lock"
            with mock.patch.object(module.b4, "process_is_alive", return_value=False), mock.patch.object(
                module.b4, "LOCK", absent_lock
            ):
                evidence = module.b4_terminal_evidence(state)
        self.assertTrue(evidence["acceptable"])
        self.assertIn("known_e_partial", evidence["reason"])
        self.assertEqual(evidence["source_files"], module.EXPECTED_FILES)

    def test_b4_direct_scan_mismatch_becomes_new_read_only_baseline(self):
        module = load_module()
        state = {
            "status": "failed_safe_to_review",
            "pid": None,
            "errors": [
                {
                    "type": "RuntimeError",
                    "message": (
                        "source direct scan differs from A4 residual: "
                        "files=15000000/14292409 bytes=500000000000/446724241482"
                    ),
                }
            ],
        }
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            absent_lock = Path(directory) / "absent.lock"
            with mock.patch.object(module.b4, "process_is_alive", return_value=False), mock.patch.object(
                module.b4, "LOCK", absent_lock
            ):
                evidence = module.b4_terminal_evidence(state)
        self.assertTrue(evidence["acceptable"])
        self.assertEqual(evidence["source_files"], 15_000_000)
        self.assertEqual(evidence["source_bytes"], 500_000_000_000)
        self.assertIn("supersedes", evidence["reason"])

    def test_execute_requires_exact_approval_token(self):
        module = load_module()
        with mock.patch.object(module, "run_preflight", return_value={"status": "passed"}), mock.patch.object(
            module, "execute"
        ) as execute, mock.patch.object(
            module.sys, "argv", ["b5", "--execute", "--approval-token", "wrong"]
        ):
            exit_code = module.main()
        self.assertEqual(exit_code, 3)
        execute.assert_not_called()

    def test_bsdtar_accepts_nul_manifest_with_unicode_member(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            root = Path(directory)
            source = root / "구형 자료"
            source.mkdir()
            member_file = source / "표본 파일.lab"
            member_file.write_bytes(b"sample")
            manifest = root / "members.nul"
            member = f"{source.name}/{member_file.name}"
            manifest.write_bytes(member.encode("cp949") + b"\0")
            archive = root / "pilot.tar.zst"
            created = subprocess.run(
                [
                    str(module.TAR_EXE),
                    "-c",
                    "--zstd",
                    "-f",
                    str(archive),
                    "-C",
                    str(source.parent),
                    "--null",
                    "-T",
                    str(manifest),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(created.returncode, 0, module.b2.decode_output(created.stderr))
            listed = subprocess.run(
                [str(module.TAR_EXE), "-tf", str(archive)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(listed.returncode, 0, module.b2.decode_output(listed.stderr))
            self.assertIn(member, module.b2.decode_output(listed.stdout).replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
