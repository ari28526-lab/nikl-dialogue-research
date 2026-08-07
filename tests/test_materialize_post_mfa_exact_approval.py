import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from finalize_post_mfa_exact_reconciliation_exclusions import (  # noqa: E402
    candidate_identity_sha256,
)
from materialize_post_mfa_exact_approval import materialize  # noqa: E402
from mfa_exclusion_contract import REVIEW_FIELDS  # noqa: E402
from pipeline_common import file_fingerprint, sha256_file  # noqa: E402


class MaterializePostMfaExactApprovalTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[Path, str, str]:
        review = root / "review"
        review.mkdir()
        rows = []
        for utt_id in ("U1", "U2"):
            rows.append(
                {
                    "year": "2022",
                    "input_contract_id": "INPUT1",
                    "utt_id": utt_id,
                    "reason_code": "mfa_alignment_missing",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": "D:/report.json",
                    "decision": "pending",
                    "notes": "no intervals",
                }
            )
        for name in ("02_RESEARCHER_DECISIONS.csv", "04_RESEARCHER_APPROVAL.csv"):
            with (review / name).open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
        token = "APPROVE_2022_POST_MFA_2_ABC"
        summary = {
            "schema_version": "mfa_post_alignment_review.v2",
            "status": "pending_researcher_review",
            "year": "2022",
            "input_contract_id": "INPUT1",
            "auto_approval_performed": False,
            "mfa_database_modified": False,
            "candidate_count": 2,
            "candidate_identity_sha256": candidate_identity_sha256(rows),
            "required_approval_token": token,
            "artifacts": {
                "decisions": file_fingerprint(
                    review / "02_RESEARCHER_DECISIONS.csv", with_sha256=True
                ),
                "approval_working_copy": file_fingerprint(
                    review / "04_RESEARCHER_APPROVAL.csv", with_sha256=True
                ),
            },
        }
        (review / "SUMMARY.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        statement = (
            "2022 post-MFA 2건을 alignment_and_analysis로 제외하고 "
            "원자료를 보존한다. 승인자 ari30."
        )
        return review, token, statement

    def test_archives_pending_and_materializes_exact_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            review, token, statement = self.prepare(Path(tmp))
            immutable_before = sha256_file(
                review / "02_RESEARCHER_DECISIONS.csv"
            )
            pending_before = sha256_file(review / "04_RESEARCHER_APPROVAL.csv")
            result = materialize(
                review_root=review,
                approved_by="ari30",
                approval_statement=statement,
                expected_row_count=2,
                approval_token=token,
            )
            self.assertEqual(result["approved_row_count"], 2)
            self.assertFalse(result["automatic_approval_performed"])
            self.assertEqual(
                sha256_file(review / "02_RESEARCHER_DECISIONS.csv"),
                immutable_before,
            )
            self.assertEqual(
                sha256_file(
                    review
                    / "archive"
                    / "04_RESEARCHER_APPROVAL.pending_original.csv"
                ),
                pending_before,
            )
            with (review / "04_RESEARCHER_APPROVAL.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual({row["decision"] for row in rows}, {"approved"})
            again = materialize(
                review_root=review,
                approved_by="ari30",
                approval_statement=statement,
                expected_row_count=2,
                approval_token=token,
            )
            self.assertEqual(again["approved_row_count"], 2)

    def test_incomplete_statement_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            review, token, _statement = self.prepare(Path(tmp))
            before = sha256_file(review / "04_RESEARCHER_APPROVAL.csv")
            with self.assertRaisesRegex(RuntimeError, "필수 범위"):
                materialize(
                    review_root=review,
                    approved_by="ari30",
                    approval_statement="승인한다.",
                    expected_row_count=2,
                    approval_token=token,
                )
            self.assertEqual(
                sha256_file(review / "04_RESEARCHER_APPROVAL.csv"), before
            )
            self.assertFalse(
                (review / "04_RESEARCHER_APPROVAL_MANIFEST.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
