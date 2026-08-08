from __future__ import annotations

import unittest

from scripts.python.audit_common_pron_r3_policy_decision_reuse import scalar_strings


class PolicyDecisionReuseAuditTests(unittest.TestCase):
    def test_scalar_strings_walks_nested_ledgers(self) -> None:
        values = set(scalar_strings({"decision": ["approved", {"token": "꽃무늬"}]}))
        self.assertTrue({"decision", "approved", "token", "꽃무늬"}.issubset(values))


if __name__ == "__main__":
    unittest.main()
