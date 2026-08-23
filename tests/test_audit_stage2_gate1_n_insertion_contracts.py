from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDITOR_PATH = REPO_ROOT / "scripts/python/audit_stage2_gate1_n_insertion_contracts.py"
SPEC = importlib.util.spec_from_file_location("gate1_audit", AUDITOR_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class Gate1AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources, cls.claims, _ = AUDIT.validate_literature(REPO_ROOT)
        cls.enum = AUDIT.read_json(REPO_ROOT / "config/stage2_environment_class_enum.v1.json")

    def test_success_actual_contracts(self) -> None:
        report = AUDIT.audit_repo(REPO_ROOT, check_git=False)
        self.assertTrue(report["passed"])
        self.assertEqual(report["source_registry"]["candidate_rows"], 941903)
        self.assertEqual(report["environment_types"]["rows"], 7)
        self.assertEqual(report["environment_types"]["researcher_confirmed"], 0)

    def test_failure_missing_source_registry_field(self) -> None:
        registry = AUDIT.read_json(REPO_ROOT / AUDIT.SOURCE_REGISTRY_PATH)
        broken = copy.deepcopy(registry)
        del broken["totals"]
        with self.assertRaises(AssertionError):
            AUDIT.validate_source_registry_dict(broken, REPO_ROOT)

    def test_failure_wrong_manifest_sha(self) -> None:
        registry = AUDIT.read_json(REPO_ROOT / AUDIT.SOURCE_REGISTRY_PATH)
        broken = copy.deepcopy(registry)
        broken["years"][0]["build_manifest"]["sha256"] = "0" * 64
        with self.assertRaises(AssertionError):
            AUDIT.validate_source_registry_dict(broken, REPO_ROOT)

    def test_failure_unknown_clm_ref(self) -> None:
        rows = AUDIT.read_jsonl(REPO_ROOT / AUDIT.ENVIRONMENT_PATH)
        broken = copy.deepcopy(rows)
        broken[0]["class_evidence_refs"] = ["CLM-9999"]
        with self.assertRaises(AssertionError):
            AUDIT.validate_environment_rows(broken, self.enum, self.sources, self.claims)

    def test_failure_silent_human_check_confirmation(self) -> None:
        rows = AUDIT.read_jsonl(REPO_ROOT / AUDIT.ENVIRONMENT_PATH)
        broken = copy.deepcopy(rows)
        broken[2]["class_status"] = "researcher_confirmed"
        with self.assertRaises(AssertionError):
            AUDIT.validate_environment_rows(broken, self.enum, self.sources, self.claims)

    def test_existing_output_refuses_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.json"
            manifest_path = Path(temp_dir) / "SHA256SUMS.txt"
            audit_path.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                AUDIT.atomic_write_pair(audit_path, b"new", manifest_path, b"manifest")
            self.assertEqual(audit_path.read_text(encoding="utf-8"), "existing")
            self.assertFalse(manifest_path.exists())

    def test_manifest_excludes_itself(self) -> None:
        audit_relative = "outputs/pilots/test/AUDIT.json"
        manifest_relative = "outputs/pilots/test/SHA256SUMS.txt"
        lines = AUDIT.build_manifest_lines(REPO_ROOT, audit_relative, b"{}\n", manifest_relative)
        self.assertEqual(len(lines), len(AUDIT.ARTIFACT_PATHS) + 1)
        self.assertFalse(any(manifest_relative in line for line in lines))
        self.assertTrue(any(audit_relative in line for line in lines))


if __name__ == "__main__":
    unittest.main()
