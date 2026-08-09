from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_staged_approval import (  # noqa: E402
    EXPECTED_REVIEW,
    REVIEW_FIELDS,
    read_approved_reviews,
    stable_contract_id,
)


class StagedApprovalTests(unittest.TestCase):
    def test_review_requires_all_four_explicit_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
                writer.writeheader()
                for review_id, (utt_id, target) in EXPECTED_REVIEW.items():
                    writer.writerow(
                        {
                            "review_id": review_id,
                            "utt_id": utt_id,
                            "target_word": target,
                            "automatic_verdict": "pass",
                            "decision": "approved",
                            "notes": "",
                        }
                    )
            rows = read_approved_reviews(path)
            self.assertEqual(len(rows), 4)

    def test_pending_review_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
                writer.writeheader()
                for index, (review_id, (utt_id, target)) in enumerate(
                    EXPECTED_REVIEW.items()
                ):
                    writer.writerow(
                        {
                            "review_id": review_id,
                            "utt_id": utt_id,
                            "target_word": target,
                            "automatic_verdict": "pass",
                            "decision": "pending" if index == 0 else "approved",
                            "notes": "",
                        }
                    )
            with self.assertRaisesRegex(RuntimeError, "not explicitly approved"):
                read_approved_reviews(path)

    def test_contract_id_is_order_independent_for_mapping_keys(self) -> None:
        self.assertEqual(
            stable_contract_id({"a": 1, "b": 2}),
            stable_contract_id({"b": 2, "a": 1}),
        )


if __name__ == "__main__":
    unittest.main()
