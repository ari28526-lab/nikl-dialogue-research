from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "run_a5_b2_tar_zst_pilot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_a5_b2_tar_zst_pilot", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class B2TarPilotTests(unittest.TestCase):
    def test_atomic_json_replace_retries_transient_permission_error(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            target = Path(directory) / "state.json"
            target.write_text("{}\n", encoding="utf-8")
            path_type = type(target)
            original_replace = path_type.replace
            calls = {"count": 0}

            def flaky_replace(self: Path, destination: Path):
                calls["count"] += 1
                if calls["count"] <= 2:
                    raise PermissionError("simulated transient reader lock")
                return original_replace(self, destination)

            with mock.patch.object(path_type, "replace", new=flaky_replace), mock.patch.object(
                module.time, "sleep", return_value=None
            ):
                module.write_json_atomic(target, {"status": "running"})
            self.assertEqual(calls["count"], 3)
            self.assertEqual(module.load_json(target), {"status": "running"})

    def test_volume_identity_rejects_swapped_guid(self):
        module = load_module()
        volumes = {
            "E": {"label": "VERIFIED_ARCHIVE_2TB", "guid": "wrong", "volume_guid": "wrong", "filesystem": "NTFS"},
            "H": {
                "label": "SAMSUNG",
                "volume_guid": module.EXPECTED_VOLUMES["H"]["guid"],
                "filesystem": "NTFS",
            },
        }
        self.assertFalse(module.volumes_are_expected(volumes))

    def test_a5_state_guard_rejects_live_runner(self):
        module = load_module()
        state = {
            "job_id": "h_preservation_a5_20260902",
            "status": "failed_safe_to_resume",
            "completed_units": [{}] * 10,
            "pid": 12345,
            "robocopy_pid": None,
            "exact_check_pid": None,
            "h_delete_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
        }
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            temporary = Path(directory)
            state_path = temporary / "a5_state.json"
            state_path.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(module, "A5_STATE", state_path), mock.patch.object(
                module, "A5_LOCK", temporary / "absent.lock"
            ), mock.patch.object(module, "load_json", return_value=state), mock.patch.object(
                module, "process_is_alive", side_effect=lambda pid: pid == 12345
            ):
                safe, observed = module.a5_state_is_safe_for_pilot()
        self.assertFalse(safe)
        self.assertEqual(observed["pid"], 12345)

    def test_inventory_counts_bytes_and_selects_deterministic_samples(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            source = Path(directory)
            (source / "b").mkdir()
            (source / "a").mkdir()
            files = {
                "a/one.TextGrid": b"one",
                "a/two.TextGrid": b"twotwo",
                "b/three.TextGrid": b"33333",
                "root.TextGrid": b"root",
            }
            for relative, content in files.items():
                (source / relative).write_bytes(content)
            first = module.inventory_source(source, sample_count=3)
            second = module.inventory_source(source, sample_count=3)
        self.assertEqual(first["files"], 4)
        self.assertEqual(first["directories"], 2)
        self.assertEqual(first["bytes"], sum(map(len, files.values())))
        self.assertEqual(first["samples"], second["samples"])
        self.assertEqual(len(first["samples"]), 3)

    def test_create_command_uses_explicit_zstd_and_partial_target(self):
        module = load_module()

        class FinishedProcess:
            pid = 4321
            returncode = 0

            def poll(self):
                return 0

        state = {}
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            temporary = Path(directory)
            archive = temporary / "pilot.tar.zst.partial"
            log_root = temporary / "logs"
            archive.write_bytes(b"archive")
            with mock.patch.object(module, "ARCHIVE_PARTIAL", archive), mock.patch.object(
                module, "LOGS", log_root
            ), mock.patch.object(module.subprocess, "Popen", return_value=FinishedProcess()) as popen, mock.patch.object(
                module, "write_json_atomic", return_value=None
            ):
                result = module.create_archive_monitored(state)
        command = popen.call_args.args[0]
        self.assertIn("--zstd", command)
        self.assertEqual(command[command.index("-f") + 1], str(archive))
        self.assertEqual(result["archive_bytes"], 7)

    def test_execute_requires_exact_approval_token(self):
        module = load_module()
        passed = {"status": "passed"}
        with mock.patch.object(module, "run_preflight", return_value=passed), mock.patch.object(
            module, "execute_pilot"
        ) as execute, mock.patch.object(
            module.sys, "argv", ["pilot", "--execute", "--approval-token", "wrong"]
        ):
            exit_code = module.main()
        self.assertEqual(exit_code, 3)
        execute.assert_not_called()

    def test_end_to_end_local_tar_list_sha_restore_and_promotion(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            temporary = Path(directory)
            source = temporary / "source_textgrids"
            source.mkdir()
            (source / "nested").mkdir()
            contents = {
                "one.TextGrid": b"File type = text\nfirst\n",
                "two space.TextGrid": b"File type = text\nsecond\n",
                "nested/three.TextGrid": b"File type = text\nthird\n",
                "nested/four.TextGrid": b"File type = text\nfourth\n",
            }
            for relative, content in contents.items():
                (source / relative).write_bytes(content)
            destination = temporary / "destination"
            archive_partial = destination / "pilot.tar.zst.partial"
            archive_final = destination / "pilot.tar.zst"
            receipt = destination / "pilot.receipt.json"
            fake_volume = {
                "E": {"free_bytes": 10**12, "label": "VERIFIED_ARCHIVE_2TB", "volume_guid": "e", "filesystem": "NTFS"},
                "H": {"free_bytes": 10**12, "label": "SAMSUNG", "volume_guid": "h", "filesystem": "NTFS"},
            }
            disk_usage = type("Usage", (), {"free": 10**12})()
            with mock.patch.multiple(
                module,
                SOURCE=source,
                EXPECTED_FILES=len(contents),
                EXPECTED_BYTES=sum(map(len, contents.values())),
                DESTINATION_DIR=destination,
                ARCHIVE_PARTIAL=archive_partial,
                ARCHIVE_FINAL=archive_final,
                RECEIPT=receipt,
                RESTORE_ROOT=temporary / "restore",
                STATE=temporary / "state.json",
                RESULT=temporary / "result.json",
                LOCK=temporary / "pilot.lock",
                LOGS=temporary / "logs",
                E_FREE_FLOOR=0,
            ), mock.patch.object(module, "assert_expected_volumes", return_value=fake_volume), mock.patch.object(
                module, "assert_a5_remains_paused", return_value={"status": "failed_safe_to_resume"}
            ), mock.patch.object(
                module.shutil, "disk_usage", return_value=disk_usage
            ), mock.patch.object(module.time, "sleep", return_value=None):
                result = module.execute_pilot({"status": "passed"})
            self.assertEqual(result["status"], "completed_verified")
            self.assertTrue(archive_final.is_file())
            self.assertFalse(archive_partial.exists())
            self.assertTrue(receipt.is_file())
            self.assertTrue(result["archive_listing"]["exact"])
            self.assertTrue(result["restore_samples"]["all_match"])
            self.assertEqual(result["source_inventory"]["files"], len(contents))

    def test_execute_refuses_to_overwrite_existing_lock(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            temporary = Path(directory)
            lock = temporary / "pilot.lock"
            lock.write_text("existing-owner\n", encoding="utf-8")
            with mock.patch.multiple(
                module,
                LOCK=lock,
                ARCHIVE_PARTIAL=temporary / "absent.partial",
                ARCHIVE_FINAL=temporary / "absent.tar.zst",
                RECEIPT=temporary / "absent.receipt.json",
                RESTORE_ROOT=temporary / "absent_restore",
            ), mock.patch.object(module, "assert_a5_remains_paused", return_value={}), mock.patch.object(
                module, "assert_expected_volumes", return_value={}
            ):
                with self.assertRaises(FileExistsError):
                    module.execute_pilot({"status": "passed"})
            self.assertEqual(lock.read_text(encoding="utf-8"), "existing-owner\n")


if __name__ == "__main__":
    unittest.main()
