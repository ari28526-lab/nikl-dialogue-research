from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_mfa_exclusion_category_summary import summarize_year  # noqa: E402
from pipeline_common import sha256_file  # noqa: E402


class MfaExclusionCategorySummaryTests(unittest.TestCase):
    def test_summary_is_bound_to_pending_candidate_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            year_root = root / "2023"
            year_root.mkdir()
            candidate = year_root / "03_RESEARCHER_REVIEW.csv"
            fields = [
                "year", "input_contract_id", "utt_id", "reason_code",
                "exclusion_scope", "evidence_path", "decision", "notes",
            ]
            with candidate.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "year": "2023", "input_contract_id": "abc", "utt_id": "u1",
                            "reason_code": "audio_pairing_unresolved",
                            "exclusion_scope": "alignment_and_analysis", "evidence_path": "a",
                            "decision": "pending", "notes": "",
                        },
                        {
                            "year": "2023", "input_contract_id": "abc", "utt_id": "u2",
                            "reason_code": "empty_reference_unresolved_symbol",
                            "exclusion_scope": "alignment_and_analysis", "evidence_path": "b",
                            "decision": "pending", "notes": "",
                        },
                    ]
                )
            audit = year_root / "01_input_audit_unapproved.json"
            audit.write_text(
                json.dumps(
                    {"years": {"year": "2023", "counts": {"search_rows": 10}}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest = {
                "schema_version": "mfa_exclusion_review_candidates.v1",
                "status": "pending_researcher_review",
                "automatic_approval_performed": False,
                "year": "2023",
                "input_contract_id": "abc",
                "candidate_count": 2,
                "review_csv": {"path": str(candidate.resolve()), "sha256": sha256_file(candidate)},
                "audit_report": {"path": str(audit.resolve()), "sha256": sha256_file(audit)},
            }
            (year_root / "03_RESEARCHER_REVIEW_MANIFEST.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )

            row = summarize_year(root, "2023")
            self.assertEqual(row["search_rows"], 10)
            self.assertEqual(row["safe_body_rows"], 8)
            self.assertEqual(row["candidate_count"], 2)
            self.assertEqual(row["audio_pairing_unresolved"], 1)
            self.assertEqual(row["empty_reference_unresolved_symbol"], 1)
            self.assertEqual(row["decision"], "pending_researcher_category_approval")


if __name__ == "__main__":
    unittest.main()
