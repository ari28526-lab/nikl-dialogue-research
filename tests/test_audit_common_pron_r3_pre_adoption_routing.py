from __future__ import annotations

import unittest

from scripts.python.audit_common_pron_r3_pre_adoption_routing import independent_route


class PreAdoptionRoutingAuditTests(unittest.TestCase):
    def test_route_labels_are_compositional(self) -> None:
        self.assertEqual(independent_route(set(), set(), set(), False), "safe")
        self.assertEqual(independent_route({"h"}, {"p"}, set(), False), "hold+policy")
        self.assertEqual(independent_route(set(), set(), set(), True), "empty_reference")


if __name__ == "__main__":
    unittest.main()
