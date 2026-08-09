from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_common_pron_r3_staged_approval import (  # noqa: E402
    EXPECTED_REVIEW,
    REVIEW_FIELDS,
    build_approval,
    read_approved_reviews,
    record_approval_provenance,
    stable_contract_id,
)
from pipeline_common import file_fingerprint  # noqa: E402


class StagedApprovalTests(unittest.TestCase):
    def write_review(self, path: Path) -> None:
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

    @staticmethod
    def write_json(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def make_approval_inputs(self, root: Path) -> dict[str, Path]:
        paths = {
            "review_csv": root / "review.csv",
            "targeted": root / "targeted.json",
            "routing": root / "routing.json",
            "candidate": root / "candidate.json",
            "workflow": root / "workflow.json",
            "output": root / "RESEARCHER_APPROVAL.json",
            "sidecar": root / "RESEARCHER_APPROVAL.provenance.v2.json",
        }
        self.write_review(paths["review_csv"])
        self.write_json(
            paths["targeted"],
            {
                "status": "passed_automatic_checks_pending_researcher_audio_review",
                "checks": {"automatic_pass": 4, "spn_total": 0},
            },
        )
        self.write_json(paths["routing"], {"status": "passed_independent_full_scan"})
        self.write_json(
            paths["candidate"],
            {"status": "passed_full_projection_and_dictionary_equivalence"},
        )
        self.write_json(
            paths["workflow"],
            {
                "schema_version": "mfa_r3_full_realign_workflow.v1",
                "recorded_date": "2026-08-09",
                "researcher_decision": {
                    "approved_by": "ari30",
                    "source": "test",
                    "statement": "approved test scope",
                    "targeted_regression_boundaries_approved": True,
                    "staged_safe_body_adoption_approved": True,
                    "full_r3_realign_safe_body_all_years": True,
                    "reuse_r2_intervals_in_final_r3": False,
                },
                "scope": {
                    "years": [2020, 2021, 2022, 2023, 2024, 2025],
                    "safe_body_utterances": 4_384_992,
                    "followup_utterances": 718_364,
                },
            },
        )
        return paths

    @staticmethod
    def input_records(paths: dict[str, Path]) -> dict[str, dict]:
        return {
            "review_csv": file_fingerprint(paths["review_csv"], with_sha256=True),
            "targeted_regression_audit": file_fingerprint(
                paths["targeted"], with_sha256=True
            ),
            "routing_independent_audit": file_fingerprint(
                paths["routing"], with_sha256=True
            ),
            "candidate_independent_audit": file_fingerprint(
                paths["candidate"], with_sha256=True
            ),
            "workflow_policy": file_fingerprint(
                paths["workflow"], with_sha256=True
            ),
        }

    @staticmethod
    def build(paths: dict[str, Path]) -> tuple[dict, bool]:
        return build_approval(
            review_csv=paths["review_csv"],
            targeted_audit_path=paths["targeted"],
            routing_audit_path=paths["routing"],
            candidate_audit_path=paths["candidate"],
            workflow_policy_path=paths["workflow"],
            output=paths["output"],
        )

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

    def test_approval_is_immutable_and_provenance_sidecar_appends(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.make_approval_inputs(Path(temp))
            approval, wrote = self.build(paths)
            self.assertTrue(wrote)
            original_bytes = paths["output"].read_bytes()
            original_sha = hashlib.sha256(original_bytes).hexdigest()

            sidecar, appended = record_approval_provenance(
                approval_contract_id=approval["approval_contract_id"],
                approval_fingerprint=file_fingerprint(
                    paths["output"], with_sha256=True
                ),
                input_records=self.input_records(paths),
                sidecar=paths["sidecar"],
            )
            self.assertTrue(appended)
            self.assertEqual(len(sidecar["records"]), 1)
            first_record = sidecar["records"][0]

            workflow = json.loads(paths["workflow"].read_text(encoding="utf-8"))
            workflow["implementation_note"] = "non-binding provenance change"
            self.write_json(paths["workflow"], workflow)
            approval_again, wrote_again = self.build(paths)
            self.assertFalse(wrote_again)
            self.assertEqual(
                hashlib.sha256(paths["output"].read_bytes()).hexdigest(),
                original_sha,
            )
            self.assertEqual(approval_again, approval)

            sidecar_again, appended_again = record_approval_provenance(
                approval_contract_id=approval["approval_contract_id"],
                approval_fingerprint=file_fingerprint(
                    paths["output"], with_sha256=True
                ),
                input_records=self.input_records(paths),
                sidecar=paths["sidecar"],
            )
            self.assertTrue(appended_again)
            self.assertEqual(len(sidecar_again["records"]), 2)
            self.assertEqual(sidecar_again["records"][0], first_record)

            before_repeat = paths["sidecar"].read_bytes()
            _, appended_repeat = record_approval_provenance(
                approval_contract_id=approval["approval_contract_id"],
                approval_fingerprint=file_fingerprint(
                    paths["output"], with_sha256=True
                ),
                input_records=self.input_records(paths),
                sidecar=paths["sidecar"],
            )
            self.assertFalse(appended_repeat)
            self.assertEqual(paths["sidecar"].read_bytes(), before_repeat)

    def test_v3_1_contract_matches_approved_staged_scope(self) -> None:
        contract = json.loads(
            (ROOT / "config/common_pronunciation_resource_contract_v3_1.json")
            .read_text(encoding="utf-8-sig")
        )
        table = contract["canonical_type_table"]
        scope = contract["staged_selection_scope"]
        unresolved = scope["not_selected_for_staged_release"]
        self.assertEqual(
            contract["schema_version"],
            "common_pronunciation_resource_contract.v3.1",
        )
        self.assertEqual(table["full_canonical_type_coverage_required"], 881_237)
        self.assertEqual(
            table["selected_phone_coverage_required_before_adoption"],
            795_804,
        )
        self.assertEqual(
            table["selected_phone_coverage_required_before_full_corpus_adoption"],
            881_237,
        )
        self.assertEqual(
            scope["candidate_types_to_promote"] + unresolved["total_types"],
            table["full_canonical_type_coverage_required"],
        )
        self.assertEqual(
            unresolved["zero_fallback_hold_types"]
            + unresolved["explicit_policy_types"],
            unresolved["total_types"],
        )
        self.assertTrue(contract["variant_policy"]["candidate_is_not_selection"])
        self.assertFalse(contract["invariants"]["production_gate_opened_by_this_contract"])
        approval_pin = contract["researcher_approval"]
        approval_path = ROOT / approval_pin["path"]
        self.assertEqual(approval_path.stat().st_size, approval_pin["bytes"])
        self.assertEqual(
            hashlib.sha256(approval_path.read_bytes()).hexdigest(),
            approval_pin["sha256"],
        )
        self.assertTrue(approval_pin["immutable"])


if __name__ == "__main__":
    unittest.main()
