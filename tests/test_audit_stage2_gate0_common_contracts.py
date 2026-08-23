from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/python/audit_stage2_gate0_common_contracts.py"
SPEC = importlib.util.spec_from_file_location("audit_stage2_gate0_common_contracts", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT_PATH}")
AUDITOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDITOR)


class Gate0AuditTests(unittest.TestCase):
    def test_success_actual_contracts(self) -> None:
        report = AUDITOR.audit_repo(REPO_ROOT, check_git=False)
        self.assertTrue(report["passed"])
        self.assertEqual(report["registry"]["phenomena"], 7)
        self.assertEqual(report["declarations"]["environment_assignment_rows"], 0)
        self.assertEqual(report["declarations"]["contract_value_rows"], 0)
        self.assertEqual(report["declarations"]["sidecar_data_rows"], 0)

    def test_failure_missing_registry_field(self) -> None:
        registry = json.loads((REPO_ROOT / "config/phenomena_registry.v1.json").read_text(encoding="utf-8"))
        handoff = json.loads((REPO_ROOT / "docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json").read_text(encoding="utf-8"))
        broken = copy.deepcopy(registry)
        del broken["phenomena"][0]["literature_synthesis_path"]
        with self.assertRaises(AUDITOR.ContractError):
            AUDITOR.validate_registry(REPO_ROOT, broken, handoff)

    def test_failure_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.json"
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(AUDITOR.ContractError):
                AUDITOR.verify_sha(path, "0" * 64)

    def test_existing_output_refuses_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.json"
            path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                AUDITOR.ensure_outputs_absent([path])
            self.assertEqual(path.read_text(encoding="utf-8"), "existing\n")

    def test_manifest_excludes_itself(self) -> None:
        audit_relative = "outputs/pilots/stage2_gate0_common_contracts_20260823/AUDIT_stage2_gate0_common_contracts_20260823.json"
        manifest_relative = "outputs/pilots/stage2_gate0_common_contracts_20260823/SHA256SUMS_stage2_gate0_common_contracts_20260823.txt"
        lines = AUDITOR.build_manifest_lines(REPO_ROOT, audit_relative, b"{}\n", manifest_relative)
        self.assertFalse(any(manifest_relative in line for line in lines))
        self.assertTrue(any(audit_relative in line for line in lines))


if __name__ == "__main__":
    unittest.main()
