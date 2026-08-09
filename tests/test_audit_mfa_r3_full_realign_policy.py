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
            "draft": ROOT / "config/common_pronunciation_resource_contract_v3_draft.json",
            "release_gate": ROOT / "config/mfa_pronunciation_release_gate.json",
            "approval": ROOT
            / "outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json",
        }
        return {
            key: json.loads(path.read_text(encoding="utf-8-sig"))
            for key, path in paths.items()
        }

    def test_repository_policy_is_consistent(self):
        self.assertEqual(MODULE.validate_policy(**self._documents()), [])

    def test_rejects_r2_interval_reuse(self):
        documents = self._documents()
        changed = copy.deepcopy(documents)
        changed["draft"]["rerun_policy"]["unchanged_r2_reuse_allowed"] = True
        failures = MODULE.validate_policy(**changed)
        self.assertTrue(any("r2 reuse" in item for item in failures))

    def test_rejects_unbalanced_year(self):
        documents = self._documents()
        changed = copy.deepcopy(documents)
        changed["workflow"]["year_accounting"]["2020"]["safe_body"] -= 1
        failures = MODULE.validate_policy(**changed)
        self.assertTrue(any("2020" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
