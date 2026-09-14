from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python" / "copy_a5_h_preservation_to_e.py"


def load_module():
    spec = importlib.util.spec_from_file_location("copy_a5_h_preservation_to_e", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class A5SafetyTests(unittest.TestCase):
    def test_resume_capacity_projection_does_not_count_partial_tree_twice(self):
        module = load_module()
        units = [
            {"key": "one", "expected_files": 2, "expected_bytes": 100},
            {"key": "two", "expected_files": 3, "expected_bytes": 200},
            {"key": "three", "expected_files": 5, "expected_bytes": 300},
        ]
        state = {
            "schema": "a5_h_preservation_apply.v1",
            "job_id": module.JOB_ID,
            "destination_partial": str(module.PARTIAL_ROOT),
            "expected_bytes": 600,
            "completed_units": [{"key": "one", "files": 2, "bytes": 100}],
            "completed_files": 2,
            "completed_bytes": 100,
            "current_unit": "two",
            "e_free_bytes": 1_000,
            "heartbeat": {
                "current_unit": "two",
                "current_unit_physical_bytes_written_estimate": 40,
            },
        }
        with mock.patch.object(module, "EXPECTED_BYTES", 600):
            result = module.capacity_projection_for_preflight(units, 950, state)

        self.assertTrue(result["resume_state_valid"])
        self.assertEqual(result["capacity_boundary_free_bytes"], 990)
        self.assertEqual(result["remaining_logical_bytes_from_boundary"], 500)
        self.assertEqual(result["projected_e_free_bytes_after_remaining_logical_copy"], 490)

    def test_resume_capacity_projection_rejects_nonprefix_completed_units(self):
        module = load_module()
        units = [
            {"key": "one", "expected_files": 2, "expected_bytes": 100},
            {"key": "two", "expected_files": 3, "expected_bytes": 200},
        ]
        state = {
            "schema": "a5_h_preservation_apply.v1",
            "job_id": module.JOB_ID,
            "destination_partial": str(module.PARTIAL_ROOT),
            "expected_bytes": 300,
            "completed_units": [{"key": "two", "files": 3, "bytes": 200}],
            "completed_files": 3,
            "completed_bytes": 200,
            "current_unit": None,
            "e_free_bytes": 1_000,
        }
        with mock.patch.object(module, "EXPECTED_BYTES", 300):
            result = module.capacity_projection_for_preflight(units, 900, state)

        self.assertFalse(result["resume_state_valid"])
        self.assertEqual(result["mode"], "fresh_full_scope")
        self.assertEqual(result["projected_e_free_bytes_after_remaining_logical_copy"], 600)

    def test_atomic_json_replace_retries_transient_permission_error(self):
        import tempfile

        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
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

    def test_robocopy_child_is_terminated_if_state_write_fails(self):
        import tempfile

        module = load_module()

        class FakeProcess:
            pid = 12345
            returncode = None

            def __init__(self):
                self.terminated = False

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True
                self.returncode = 1

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.terminated = True
                self.returncode = 1

        fake = FakeProcess()
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / "source"
            destination = temp / "destination"
            source.mkdir()
            state = {}
            unit = {"key": "test", "expected_bytes": 1}

            with mock.patch.object(module.subprocess, "Popen", return_value=fake), mock.patch.object(
                module, "write_json_atomic", side_effect=PermissionError("locked")
            ), mock.patch.object(module, "robocopy_executable", return_value="robocopy"), mock.patch.object(
                module,
                "assert_expected_volume_identities",
                return_value={
                    "H": {"free_bytes": 10},
                    "E": {"free_bytes": 10},
                },
            ):
                with self.assertRaisesRegex(PermissionError, "locked"):
                    module.run_robocopy_monitored(source, destination, temp / "copy.log", state, unit)

        self.assertTrue(fake.terminated)

    def test_robocopy_speed_profile_is_explicit_and_opt_in(self):
        import tempfile

        module = load_module()

        class FakeProcess:
            pid = 23456
            returncode = None

            def poll(self):
                return None

            def terminate(self):
                self.returncode = 1

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.returncode = 1

        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / "source"
            destination = temp / "destination"
            source.mkdir()
            state = {}
            unit = {"key": "test", "expected_bytes": 1}

            with mock.patch.object(module.subprocess, "Popen", return_value=FakeProcess()) as popen, mock.patch.object(
                module, "write_json_atomic", side_effect=PermissionError("locked")
            ), mock.patch.object(module, "robocopy_executable", return_value="robocopy"), mock.patch.object(
                module,
                "assert_expected_volume_identities",
                return_value={
                    "H": {"free_bytes": 10},
                    "E": {"free_bytes": 10},
                },
            ):
                with self.assertRaisesRegex(PermissionError, "locked"):
                    module.run_robocopy_monitored(
                        source,
                        destination,
                        temp / "copy.log",
                        state,
                        unit,
                        mt_threads=32,
                        restartable=False,
                    )

            command = popen.call_args.args[0]
            self.assertIn("/MT:32", command)
            self.assertNotIn("/MT:8", command)
            self.assertNotIn("/Z", command)
            self.assertEqual(
                state["copy_profile"],
                {"robocopy_mt_threads": 32, "restartable_mode": False},
            )

    def test_volume_identity_guard_rejects_swapped_destination_guid(self):
        module = load_module()

        def fake_snapshot(letter: str):
            expected = module.EXPECTED_VOLUMES[letter]
            return {
                "drive": letter,
                "label": expected["label"],
                "filesystem": "NTFS",
                "total_bytes": 100,
                "free_bytes": 50,
                "volume_guid": (
                    module.EXPECTED_VOLUMES["H"]["guid"] if letter == "E" else expected["guid"]
                ),
            }

        with mock.patch.object(module, "volume_snapshot", side_effect=fake_snapshot):
            with self.assertRaisesRegex(RuntimeError, "E GUID changed"):
                module.assert_expected_volume_identities()

    def test_exact_tree_summary_rejects_empty_directory_differences(self):
        module = load_module()
        exact = {
            "files": {"total": 2, "copied": 0, "skipped": 2, "mismatch": 0, "failed": 0, "extras": 0},
            "dirs": {"total": 3, "copied": 0, "skipped": 3, "mismatch": 0, "failed": 0, "extras": 0},
        }
        self.assertTrue(module.tree_summary_is_exact(exact))

        extra_directory = {
            "files": dict(exact["files"]),
            "dirs": {**exact["dirs"], "extras": 1},
        }
        self.assertFalse(module.tree_summary_is_exact(extra_directory))

        missing_directory = {
            "files": dict(exact["files"]),
            "dirs": {**exact["dirs"], "copied": 1, "skipped": 2},
        }
        self.assertFalse(module.tree_summary_is_exact(missing_directory))

    def test_exact_tree_check_exposes_and_cleans_live_pid(self):
        import tempfile

        module = load_module()

        class FakeProcess:
            pid = 54321
            returncode = None

            def __init__(self):
                self.poll_count = 0

            def poll(self):
                self.poll_count += 1
                if self.poll_count == 1:
                    return None
                self.returncode = 0
                return 0

            def terminate(self):
                self.returncode = 1

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.returncode = 1

        fake = FakeProcess()
        written_states = []
        exact_zero = {"total": 0, "copied": 0, "skipped": 0, "mismatch": 0, "failed": 0, "extras": 0}
        volumes = {
            "H": {"label": "SAMSUNG", "volume_guid": "h-guid"},
            "E": {"label": "VERIFIED_ARCHIVE_2TB", "volume_guid": "e-guid"},
        }

        with tempfile.TemporaryDirectory(dir=module.ROOT) as directory:
            temp = Path(directory)
            source = temp / "source"
            destination = temp / "destination"
            source.mkdir()
            destination.mkdir()
            state = {"current_unit": "test"}
            unit = {"key": "test"}

            with mock.patch.object(module.subprocess, "Popen", return_value=fake), mock.patch.object(
                module, "write_json_atomic", side_effect=lambda _path, value: written_states.append(dict(value))
            ), mock.patch.object(module.time, "sleep", return_value=None), mock.patch.object(
                module, "assert_expected_volume_identities", return_value=volumes
            ), mock.patch.object(module, "parse_summary", return_value=exact_zero):
                result = module.exact_tree_check(source, destination, state, unit, temp / "exact.log")

        self.assertTrue(result["exact"])
        self.assertTrue(any(item.get("exact_check_pid") == 54321 for item in written_states))
        self.assertTrue(any(item.get("verification_phase") == "exact_tree_check" for item in written_states))
        self.assertNotIn("exact_check_pid", state)
        self.assertNotIn("verification_phase", state)


if __name__ == "__main__":
    unittest.main()
