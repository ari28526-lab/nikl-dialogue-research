import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from mfa_exclusion_contract import (  # noqa: E402
    REVIEW_FIELDS,
    build_contract,
    load_contract,
)


class MfaExclusionContractTests(unittest.TestCase):
    def write_review(
        self,
        path: Path,
        *,
        decision="approved",
        reason_code="quarantined_wav",
    ):
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "year": "2020",
                    "input_contract_id": "INPUT1",
                    "utt_id": "U1",
                    "reason_code": reason_code,
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": "D:/evidence/U1.wav",
                    "decision": decision,
                    "notes": "bad header",
                }
            )

    def test_build_and_load_sha_bound_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = root / "review.csv"
            contract = root / "contract.json"
            self.write_review(review)
            built = build_contract(
                review_csv=review,
                output=contract,
                year="2020",
                input_contract_id="INPUT1",
                approved_by="researcher",
                approved_at="2026-08-01T12:00:00+09:00",
            )
            self.assertEqual(built["row_count"], 1)
            _data, rows = load_contract(
                contract, year="2020", input_contract_id="INPUT1"
            )
            self.assertEqual(rows["U1"]["reason_code"], "quarantined_wav")
            review.write_text(review.read_text(encoding="utf-8-sig") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "SHA256"):
                load_contract(contract, year="2020", input_contract_id="INPUT1")

    def test_pending_row_cannot_become_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = root / "review.csv"
            self.write_review(review, decision="pending")
            with self.assertRaisesRegex(RuntimeError, "미승인"):
                build_contract(
                    review_csv=review,
                    output=root / "contract.json",
                    year="2020",
                    input_contract_id="INPUT1",
                    approved_by="researcher",
                    approved_at="2026-08-01T12:00:00+09:00",
                )

    def test_empty_reference_unresolved_symbol_can_be_explicitly_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = root / "review.csv"
            contract = root / "contract.json"
            self.write_review(
                review,
                reason_code="empty_reference_unresolved_symbol",
            )
            built = build_contract(
                review_csv=review,
                output=contract,
                year="2020",
                input_contract_id="INPUT1",
                approved_by="researcher",
                approved_at="2026-08-02T12:00:00+09:00",
            )
            self.assertEqual(
                built["counts"][
                    "empty_reference_unresolved_symbol|alignment_and_analysis"
                ],
                1,
            )

    def test_mfa_feature_generation_failure_can_be_explicitly_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = root / "review.csv"
            contract = root / "contract.json"
            self.write_review(
                review,
                reason_code="mfa_feature_generation_failed",
            )
            built = build_contract(
                review_csv=review,
                output=contract,
                year="2020",
                input_contract_id="INPUT1",
                approved_by="researcher",
                approved_at="2026-08-04T15:00:00+09:00",
            )
            self.assertEqual(
                built["counts"][
                    "mfa_feature_generation_failed|alignment_and_analysis"
                ],
                1,
            )


if __name__ == "__main__":
    unittest.main()
