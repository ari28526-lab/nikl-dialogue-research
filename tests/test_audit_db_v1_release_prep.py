from __future__ import annotations

import csv
import gzip
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))
MODULE_PATH = ROOT / "scripts" / "python" / "audit_db_v1_release_prep.py"
SPEC = importlib.util.spec_from_file_location("audit_db_v1_release_prep", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DbV1ReleasePrepAuditTests(unittest.TestCase):
    def test_invariant_contract_is_explicit(self) -> None:
        self.assertEqual(
            MODULE.INVARIANTS["aligned_safe_body"],
            ("true", "true", "false", "aligned"),
        )
        self.assertEqual(MODULE.INVARIANTS["pronunciation_followup"][0], "false")
        self.assertEqual(sum(MODULE.EXPECTED.values()), 5_103_356)


if __name__ == "__main__":
    unittest.main()
