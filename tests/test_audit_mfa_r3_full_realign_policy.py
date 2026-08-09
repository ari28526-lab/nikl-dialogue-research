import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_mfa_r3_full_realign_policy",
    ROOT / "scripts/python/audit_mfa_r3_full_realign_policy.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FullRealignPolicyAuditTests(unittest.TestCase):
    def _documents(self):
        paths = {
            "workflow": ROOT / "config/mfa_r3_full_realign_workflow_v1.json",
            "contract": ROOT
            / "config/common_pronunciation_resource_contract_v3_1.json",
            "release_gate": ROOT / "config/mfa_pronunciation_release_gate.json",
            "approval": ROOT
            / "outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json",
            "gate_approval": ROOT
            / "outputs/reviews/common_pron_r3_production_gate_20260809/RESEARCHER_APPROVAL_PRODUCTION_GATE.json",
            "checklist": ROOT
            / "outputs/reports/AUDIT_mfa_r3_checklist_1_7_candidate_20260809.json",
        }
        return {
            key: json.loads(path.read_text(encoding="utf-8-sig"))
            for key, path in paths.items()
        }

    @staticmethod
    def _routing_rows(workflow):
        return {
            int(year): {
                "source": int(row["source"]),
                "safe_body": int(row["safe_body"]),
                "followup": int(row["followup"]),
            }
            for year, row in workflow["year_accounting"].items()
        }

    def _validate(self, documents):
        return MODULE.validate_policy(
            **documents,
            routing_rows=self._routing_rows(documents["workflow"]),
            expected_gate_state="adopted",
        )

    def test_repository_adopted_policy_is_consistent(self):
        documents = self._documents()
        self.assertEqual(self._validate(documents), [])
        self.assertEqual(MODULE.find_implementation_gaps(ROOT), [])

    def test_rejects_r2_interval_reuse(self):
        changed = copy.deepcopy(self._documents())
        changed["contract"]["rerun_policy"]["unchanged_r2_reuse_allowed"] = True
        failures = self._validate(changed)
        self.assertTrue(any("r2 reuse" in item for item in failures))

    def test_rejects_unbalanced_year(self):
        changed = copy.deepcopy(self._documents())
        changed["workflow"]["year_accounting"]["2020"]["safe_body"] -= 1
        failures = self._validate(changed)
        self.assertTrue(any("2020" in item for item in failures))

    def test_rejects_extra_allowed_release(self):
        changed = copy.deepcopy(self._documents())
        changed["release_gate"]["allowed_release_ids"].append("unexpected")
        failures = self._validate(changed)
        self.assertTrue(any("exactly the r3 release" in item for item in failures))

    def test_rejects_stage19_summary_difference(self):
        documents = self._documents()
        rows = self._routing_rows(documents["workflow"])
        rows[2023]["safe_body"] -= 1
        failures = MODULE.validate_policy(
            **documents,
            routing_rows=rows,
            expected_gate_state="adopted",
        )
        self.assertTrue(any("Stage 19 summary: 2023" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
