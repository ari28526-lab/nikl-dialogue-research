from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "python"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from approve_mfa_r3_post_mfa_reconciliation import approve
from mfa_exclusion_contract import REVIEW_FIELDS, load_contract
from pipeline_common import file_fingerprint


class ApproveMfaR3PostMfaReconciliationTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, str]:
        review = root / "review"
        review.mkdir()
        identity_rows = []
        rows = []
        for index in range(2):
            row = {
                "year": "2020",
                "input_contract_id": "input-1",
                "utt_id": f"utt-{index}",
                "reason_code": "mfa_alignment_missing",
                "exclusion_scope": "alignment_and_analysis",
                "evidence_path": "marker.json",
                "decision": "pending",
                "notes": "preserve",
            }
            rows.append(row)
            identity_rows.append(
                "|".join(
                    row[key]
                    for key in (
                        "year",
                        "input_contract_id",
                        "utt_id",
                        "reason_code",
                        "exclusion_scope",
                    )
                )
            )
        pending = review / "02_RESEARCHER_DECISIONS.csv"
        with pending.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        digest = hashlib.sha256("\n".join(identity_rows).encode()).hexdigest()
        summary = {
            "schema_version": "mfa_r3_post_mfa_reconciliation_review.v1",
            "status": "pending_researcher_approval",
            "year": "2020",
            "input_contract_id": "input-1",
            "candidate_identity_sha256": digest,
            "counts": {"post_mfa_candidates": 2},
            "outputs": {
                "researcher_decisions": file_fingerprint(
                    pending, with_sha256=True
                )
            },
            "policy": {"automatic_approval_performed": False},
        }
        (review / "03_REVIEW_SUMMARY.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        return review, digest

    def test_explicit_frozen_identity_approval_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            review, digest = self._fixture(Path(temporary))
            statement = (
                "2020 2 alignment_and_analysis "
                f"{digest[:12]} 승인자 ari30"
            )
            first = approve(
                review_root=review,
                approved_by="ari30",
                approved_at="2026-08-09T22:30:00+09:00",
                approval_statement=statement,
            )
            second = approve(
                review_root=review,
                approved_by="ari30",
                approved_at="ignored-on-idempotent-check",
                approval_statement=statement,
            )
            self.assertEqual(first, second)
            self.assertFalse(first["automatic_approval_performed"])
            contract, rows = load_contract(
                review / "05_APPROVED_EXCLUSIONS.json",
                year="2020",
                input_contract_id="input-1",
            )
            self.assertEqual(contract["row_count"], 2)
            self.assertEqual(set(rows), {"utt-0", "utt-1"})

    def test_statement_must_name_frozen_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            review, _digest = self._fixture(Path(temporary))
            with self.assertRaisesRegex(RuntimeError, "missing frozen identity"):
                approve(
                    review_root=review,
                    approved_by="ari30",
                    approved_at="2026-08-09T22:30:00+09:00",
                    approval_statement="승인한다",
                )
            self.assertFalse((review / "04_RESEARCHER_APPROVED.csv").exists())


if __name__ == "__main__":
    unittest.main()
