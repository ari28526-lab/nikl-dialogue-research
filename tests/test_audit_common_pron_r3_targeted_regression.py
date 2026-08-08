from __future__ import annotations

import unittest

from scripts.python.audit_common_pron_r3_targeted_regression import labeled


class TargetedRegressionAuditTests(unittest.TestCase):
    def test_labeled_removes_empty_intervals(self) -> None:
        self.assertEqual(labeled([(0, 1, ""), (1, 2, " k ")]), [(1.0, 2.0, "k")])


if __name__ == "__main__":
    unittest.main()
