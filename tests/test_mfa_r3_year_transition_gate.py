from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.build_mfa_r3_year_transition_gate import build_gate
from scripts.python.pipeline_common import sha256_file


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class MfaR3YearTransitionGateTests(unittest.TestCase):
    def test_passes_only_for_frozen_prior_and_audited_unstarted_next(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "2022.db"
            db.write_bytes(b"retained-db")
            db_sha = sha256_file(db)
            marker = root / "marker.json"
            write_json(
                marker,
                {
                    "schema_version": "mfa_r3_alignment_done.v1",
                    "status": "passed",
                    "year": "2022",
                    "release_id": "r3",
                    "alignment_contract_id": "align-22",
                    "r3_full_realign": True,
                    "source_db": {"path": str(db), "bytes": db.stat().st_size, "sha256": db_sha},
                    "temp_deleted": False,
                    "database_deleted": False,
                },
            )
            qc = root / "qc.json"
            write_json(
                qc,
                {
                    "schema_version": "mfa_r3_research_qc_state.v1",
                    "status": "passed",
                    "year": "2022",
                    "release_id": "r3",
                    "qc_input_checkpoint_id": "qc-22",
                    "qc_input": {"source_db_expected_sha256": db_sha},
                    "counts": {"sample_sessions": 5, "sample_semantic_equal": 5, "sample_byte_equal": 5},
                    "source_mutation_performed": False,
                    "mfa_recomputed": False,
                    "full_export_repeated": False,
                },
            )
            year_input = root / "input.json"
            write_json(year_input, {"year": "2023", "release_id": "r3", "year_input_contract_id": "input-23"})
            input_audit = root / "input_audit.json"
            write_json(
                input_audit,
                {
                    "status": "passed_independent_exact_id_audit_pending_alignment_contract_gate_closed",
                    "year": "2023",
                    "year_input_contract_id": "input-23",
                    "verdict": {"exact_id_partition_passed": True},
                    "checks": {"expected_mfa_input_has_wav": True},
                    "counts": {"expected_mfa_input": 10},
                },
            )
            alignment = root / "alignment.json"
            write_json(
                alignment,
                {
                    "year": "2023",
                    "alignment_contract_id": "align-23",
                    "identity": {
                        "pronunciation_release_id": "r3",
                        "year_input_contract_id": "input-23",
                    },
                },
            )
            alignment_audit = root / "alignment_audit.json"
            write_json(
                alignment_audit,
                {
                    "status": "passed_independent_identity_audit_pending_runner_and_release_gate",
                    "alignment_contract_id": "align-23",
                    "verdict": {"identity_recomputed_exact": True},
                    "checks": {"r3_full_realign": True, "expected_mfa_input": 10},
                },
            )
            research = root / "research.json"
            write_json(
                research,
                {
                    "schema_version": "mfa_r3_pronunciation_occurrence_year_audit.v1",
                    "status": "passed",
                    "year": "2023",
                    "release_id": "r3",
                    "year_input_contract_id": "input-23",
                    "post_mfa_join_key": ["year", "utt_id", "reference_eojeol_idx"],
                    "counts": {"utterances": 10},
                    "verdict": {
                        "all_source_utterances_accounted": True,
                        "unknown_nonempty_lab_tokens": 0,
                        "ready_for_mfa_preflight": True,
                    },
                },
            )
            preflight = root / "preflight.json"
            write_json(
                preflight,
                {
                    "schema_version": "mfa_r3_year_safe_body_preflight.v1",
                    "status": "go",
                    "go": True,
                    "year": "2023",
                    "release_id": "r3",
                    "alignment_contract_id": "align-23",
                    "failed_checks": [],
                    "capacity": {"required_gib": 1},
                },
            )
            report = build_gate(
                prior_year="2022",
                next_year="2023",
                prior_marker_path=marker,
                prior_qc_path=qc,
                next_input_path=year_input,
                next_input_audit_path=input_audit,
                next_alignment_path=alignment,
                next_alignment_audit_path=alignment_audit,
                next_research_audit_path=research,
                next_preflight_path=preflight,
                next_marker_path=root / "next-marker.json",
                next_database_path=root / "2023.db",
                output_path=root / "gate.json",
            )
            self.assertEqual(report["status"], "passed_ready_for_researcher_start")
            self.assertEqual(report["failed_checks"], [])

            (root / "2023.db").write_bytes(b"started")
            failed = build_gate(
                prior_year="2022",
                next_year="2023",
                prior_marker_path=marker,
                prior_qc_path=qc,
                next_input_path=year_input,
                next_input_audit_path=input_audit,
                next_alignment_path=alignment,
                next_alignment_audit_path=alignment_audit,
                next_research_audit_path=research,
                next_preflight_path=preflight,
                next_marker_path=root / "next-marker.json",
                next_database_path=root / "2023.db",
                output_path=root / "failed-gate.json",
            )
            self.assertEqual(failed["status"], "failed")
            self.assertIn("next_year_not_started", failed["failed_checks"])


if __name__ == "__main__":
    unittest.main()
