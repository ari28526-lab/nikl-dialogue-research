import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from approve_mfa_exclusion_categories import approve_categories  # noqa: E402
from mfa_exclusion_contract import REVIEW_FIELDS, load_contract  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


class ApproveMfaExclusionCategoriesTests(unittest.TestCase):
    def make_candidate(self, root: Path):
        candidate = root / "candidate.csv"
        with candidate.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            for utt_id, reason in (
                ("U1", "audio_pairing_unresolved"),
                ("U2", "empty_reference_unresolved_symbol"),
            ):
                writer.writerow(
                    {
                        "year": "2020",
                        "input_contract_id": "INPUT1",
                        "utt_id": utt_id,
                        "reason_code": reason,
                        "exclusion_scope": "alignment_and_analysis",
                        "evidence_path": "evidence",
                        "decision": "pending",
                        "notes": "fixture",
                    }
                )
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "mfa_exclusion_review_candidates.v1",
                    "status": "pending_researcher_review",
                    "year": "2020",
                    "input_contract_id": "INPUT1",
                    "candidate_count": 2,
                    "automatic_approval_performed": False,
                    "review_csv": file_fingerprint(
                        candidate, with_sha256=True
                    ),
                }
            ),
            encoding="utf-8",
        )
        return candidate, manifest

    def test_explicit_all_category_approval_preserves_pending_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate, manifest = self.make_candidate(root)
            pending_bytes = candidate.read_bytes()
            approved = root / "approved.csv"
            record_path = root / "approval.json"
            contract_path = root / "contract.json"
            record = approve_categories(
                candidate_csv=candidate,
                candidate_manifest=manifest,
                output_approved_csv=approved,
                output_approval_record=record_path,
                output_contract=contract_path,
                approved_reason_codes={
                    "audio_pairing_unresolved",
                    "empty_reference_unresolved_symbol",
                },
                approved_by="researcher",
                approval_statement="approve both categories",
                approved_at="2026-08-02T13:00:00+09:00",
            )
            self.assertEqual(candidate.read_bytes(), pending_bytes)
            self.assertEqual(record["approved_row_count"], 2)
            with approved.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual({row["decision"] for row in rows}, {"approved"})
            _contract, contract_rows = load_contract(
                contract_path, year="2020", input_contract_id="INPUT1"
            )
            self.assertEqual(set(contract_rows), {"U1", "U2"})

    def test_missing_category_does_not_create_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate, manifest = self.make_candidate(root)
            approved = root / "approved.csv"
            record = root / "approval.json"
            contract = root / "contract.json"
            with self.assertRaisesRegex(RuntimeError, "observed categories"):
                approve_categories(
                    candidate_csv=candidate,
                    candidate_manifest=manifest,
                    output_approved_csv=approved,
                    output_approval_record=record,
                    output_contract=contract,
                    approved_reason_codes={"audio_pairing_unresolved"},
                    approved_by="researcher",
                    approval_statement="partial approval",
                )
            self.assertFalse(approved.exists())
            self.assertFalse(record.exists())
            self.assertFalse(contract.exists())

    def test_tampered_pending_candidate_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate, manifest = self.make_candidate(root)
            candidate.write_text(
                candidate.read_text(encoding="utf-8-sig") + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "SHA256"):
                approve_categories(
                    candidate_csv=candidate,
                    candidate_manifest=manifest,
                    output_approved_csv=root / "approved.csv",
                    output_approval_record=root / "approval.json",
                    output_contract=root / "contract.json",
                    approved_reason_codes={
                        "audio_pairing_unresolved",
                        "empty_reference_unresolved_symbol",
                    },
                    approved_by="researcher",
                    approval_statement="approve both",
                )


if __name__ == "__main__":
    unittest.main()
