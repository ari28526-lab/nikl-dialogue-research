from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDITOR_PATH = REPO_ROOT / "scripts/python/audit_stage2_gate1_ni_freeze_contracts.py"
SPEC = importlib.util.spec_from_file_location("gate1_ni_freeze_audit", AUDITOR_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class Gate1NIFreezeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources, cls.claims, _ = AUDIT.validate_literature(REPO_ROOT)
        cls.candidate_contract = AUDIT.read_json(REPO_ROOT / AUDIT.CONTRACT_CANDIDATE_PATH)
        cls.frozen_contract = AUDIT.read_json(REPO_ROOT / AUDIT.FROZEN_CONTRACT_PATH)
        cls.query = AUDIT.read_json(REPO_ROOT / AUDIT.QUERY_PATH)
        cls.candidate_environment = AUDIT.read_jsonl(REPO_ROOT / AUDIT.ENVIRONMENT_CANDIDATE_PATH)
        cls.frozen_environment = AUDIT.read_jsonl(REPO_ROOT / AUDIT.FROZEN_ENVIRONMENT_PATH)

    def test_success_actual_freeze(self) -> None:
        report = AUDIT.audit_repo(REPO_ROOT, check_git=False)
        self.assertTrue(report["passed"])
        self.assertEqual(report["zero_drop"]["candidate_rows"], 941903)
        self.assertEqual(report["environment_types"]["rows"], 7)
        self.assertEqual(report["environment_types"]["occurrence_assignment_rows"], 0)
        self.assertEqual(report["contract"]["clm_0015"], "deferred_by_decision_d_g1_a")

    def test_failure_candidate_sha_mismatch(self) -> None:
        expected = dict(AUDIT.EXPECTED_INPUTS)
        expected[AUDIT.CONTRACT_CANDIDATE_PATH] = "0" * 64
        with self.assertRaises(AssertionError):
            AUDIT.validate_pinned_inputs(REPO_ROOT, expected)

    def test_failure_supersedes_or_adoption_sha_mismatch(self) -> None:
        for key in ("supersedes", "adoption_decision"):
            with self.subTest(key=key):
                broken = copy.deepcopy(self.frozen_contract)
                broken[key]["sha256"] = "0" * 64
                with self.assertRaises(AssertionError):
                    AUDIT.validate_frozen_contract_dict(
                        broken, self.candidate_contract, self.query, self.sources, self.claims
                    )

    def test_failure_unknown_clm_reference(self) -> None:
        frozen = copy.deepcopy(self.frozen_environment)
        candidate = copy.deepcopy(self.candidate_environment)
        frozen[0]["class_evidence_refs"] = ["CLM-9999"]
        candidate[0]["class_evidence_refs"] = ["CLM-9999"]
        with self.assertRaises(AssertionError):
            AUDIT.validate_frozen_environment_rows(frozen, candidate, self.sources, self.claims)

    def test_failure_silent_sino_promotion(self) -> None:
        broken = copy.deepcopy(self.frozen_environment)
        broken[2]["class_status"] = "researcher_confirmed"
        with self.assertRaises(AssertionError):
            AUDIT.validate_frozen_environment_rows(
                broken, self.candidate_environment, self.sources, self.claims
            )

    def test_failure_unresolved_item_removed(self) -> None:
        broken = copy.deepcopy(self.frozen_contract)
        broken["unresolved_items"] = [
            row for row in broken["unresolved_items"] if row["item_id"] != "NI_UNR_001"
        ]
        with self.assertRaises(AssertionError):
            AUDIT.validate_frozen_contract_dict(
                broken, self.candidate_contract, self.query, self.sources, self.claims
            )

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
