from __future__ import annotations

import csv
import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.python.materialize_mfa_r3_safe_body_corpus import materialize
from scripts.python.pipeline_common import file_fingerprint
from scripts.python.preflight_mfa_r3_year_safe_body import preflight


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_gzip_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class R3RunnerPreflightAndCorpusTests(unittest.TestCase):
    def preflight_fixture(self, root: Path) -> dict[str, Path]:
        release_id = "common_pron_mfa_r3_20260809"
        release_root = root / "r3" / release_id
        model = root / "model.zip"
        dictionary = root / "dictionary.dict"
        g2p = root / "g2p.zip"
        expected = root / "expected.csv.gz"
        followup = root / "followup.csv.gz"
        excluded = root / "excluded.csv.gz"
        for path, content in (
            (model, b"model"),
            (dictionary, b"dictionary"),
            (g2p, b"g2p"),
            (expected, b"expected"),
            (followup, b"followup"),
            (excluded, b"excluded"),
        ):
            path.write_bytes(content)
        contract = root / "alignment.json"
        write_json(
            contract,
            {
                "schema_version": "mfa_r3_alignment_contract.v1",
                "status": "materialized_pending_runner_preflight_and_release_gate",
                "year": "2020",
                "alignment_contract_id": "alignment-test",
                "r3_full_realign": True,
                "scope": {
                    "legacy_marker_reuse_allowed": False,
                    "legacy_db_reuse_allowed": False,
                },
                "identity": {"pronunciation_release_id": release_id},
                "models": {
                    "acoustic": file_fingerprint(model, with_sha256=True),
                    "dictionary": file_fingerprint(dictionary, with_sha256=True),
                    "g2p_provenance": file_fingerprint(g2p, with_sha256=True),
                },
                "year_input": {
                    "expected_mfa_input": 2,
                    "expected_mfa_input_ids": file_fingerprint(
                        expected, with_sha256=True
                    ),
                    "pronunciation_followup_ids": file_fingerprint(
                        followup, with_sha256=True
                    ),
                    "pre_mfa_exclusion_ids": file_fingerprint(
                        excluded, with_sha256=True
                    ),
                },
            },
        )
        audit = root / "alignment_audit.json"
        write_json(
            audit,
            {
                "schema_version": "mfa_r3_alignment_contract_audit.v1",
                "status": "passed_independent_identity_audit_pending_runner_and_release_gate",
                "alignment_contract_id": "alignment-test",
                "verdict": {
                    "identity_recomputed_exact": True,
                    "release_gate_remains_closed": True,
                },
                "inputs": {
                    "alignment_contract": file_fingerprint(
                        contract, with_sha256=True
                    )
                },
            },
        )
        policy = root / "policy.json"
        write_json(
            policy,
            {
                "schema_version": "mfa_r3_runner_policy.v1",
                "status": "approved_runner_implementation_gate_controlled",
                "release_id": release_id,
                "expected_drive_letter": release_root.drive.rstrip(":"),
                "expected_drive_label": "TEST_DRIVE",
                "release_root": str(release_root),
                "capacity_formula": {
                    "temporary_bytes_per_utterance": 1,
                    "database_bytes_per_utterance": 1,
                    "corpus_lab_and_metadata_bytes_per_utterance": 1,
                    "output_and_log_bytes_per_utterance": 1,
                    "fixed_overhead_gib": 1,
                    "safety_multiplier": 1.1,
                },
                "safety": {
                    "automatic_full_clean_retry": False,
                    "delete_temp_on_failure": False,
                    "reuse_legacy_marker": False,
                    "reuse_legacy_database": False,
                },
                "production_gate": {"required_status": "adopted"},
            },
        )
        gate = root / "gate.json"
        write_json(
            gate,
            {"status": "adopted", "allowed_release_ids": [release_id]},
        )
        return {
            "policy": policy,
            "contract": contract,
            "audit": audit,
            "gate": gate,
            "output": root / "preflight.json",
        }

    def test_preflight_go_and_closed_gate_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.preflight_fixture(Path(temp))
            report = preflight(
                year="2020",
                policy_path=paths["policy"],
                alignment_contract_path=paths["contract"],
                alignment_audit_path=paths["audit"],
                release_gate_path=paths["gate"],
                observed_drive_label="TEST_DRIVE",
                observed_free_gib=10,
                lock_problem_count=0,
                powershell_safety_passed=True,
                powershell_runtime_compat_passed=True,
                python_suite_passed=True,
                output_path=paths["output"],
            )
            self.assertTrue(report["go"])
            write_json(paths["gate"], {"status": "blocked_test", "allowed_release_ids": []})
            blocked = preflight(
                year="2020",
                policy_path=paths["policy"],
                alignment_contract_path=paths["contract"],
                alignment_audit_path=paths["audit"],
                release_gate_path=paths["gate"],
                observed_drive_label="TEST_DRIVE",
                observed_free_gib=10,
                lock_problem_count=0,
                powershell_safety_passed=True,
                powershell_runtime_compat_passed=True,
                python_suite_passed=True,
                output_path=paths["output"],
            )
            self.assertFalse(blocked["go"])
            self.assertEqual(blocked["failed_checks"], ["production_release_gate"])

    def test_preflight_capacity_and_lock_are_hard_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.preflight_fixture(Path(temp))
            report = preflight(
                year="2020",
                policy_path=paths["policy"],
                alignment_contract_path=paths["contract"],
                alignment_audit_path=paths["audit"],
                release_gate_path=paths["gate"],
                observed_drive_label="TEST_DRIVE",
                observed_free_gib=0.1,
                lock_problem_count=1,
                powershell_safety_passed=True,
                powershell_runtime_compat_passed=True,
                python_suite_passed=True,
                output_path=paths["output"],
            )
            self.assertFalse(report["go"])
            self.assertIn("lock_state_clear", report["failed_checks"])
            self.assertIn("capacity_formula", report["failed_checks"])

    def test_preflight_repository_test_failure_is_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.preflight_fixture(Path(temp))
            report = preflight(
                year="2020",
                policy_path=paths["policy"],
                alignment_contract_path=paths["contract"],
                alignment_audit_path=paths["audit"],
                release_gate_path=paths["gate"],
                observed_drive_label="TEST_DRIVE",
                observed_free_gib=10,
                lock_problem_count=0,
                powershell_safety_passed=True,
                powershell_runtime_compat_passed=True,
                python_suite_passed=False,
                output_path=paths["output"],
            )
            self.assertFalse(report["go"])
            self.assertEqual(report["failed_checks"], ["python_full_suite"])

    def test_release_scoped_corpus_is_hardlinked_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            year = "2020"
            search_root = root / "search"
            source_csv = search_root / year / "S1.csv"
            source_rows = [
                {
                    "year": year,
                    "utt_id": "U1",
                    "session_id": "S1",
                    "pron_reference_form": "혹시",
                },
                {
                    "year": year,
                    "utt_id": "U2",
                    "session_id": "S1",
                    "pron_reference_form": "요즘",
                },
            ]
            write_csv(
                source_csv,
                ("year", "utt_id", "session_id", "pron_reference_form"),
                source_rows,
            )
            recovered = root / "recovered" / "S1"
            recovered.mkdir(parents=True)
            for utt_id in ("U1", "U2"):
                (recovered / f"{utt_id}.wav").write_bytes(b"RIFF" + utt_id.encode())
            expected = root / "expected.csv.gz"
            write_gzip_csv(
                expected,
                ("year", "utt_id", "session_id", "source_csv"),
                [
                    {
                        "year": year,
                        "utt_id": row["utt_id"],
                        "session_id": "S1",
                        "source_csv": "2020/S1.csv",
                    }
                    for row in source_rows
                ],
            )
            year_contract = root / "year_contract.json"
            write_json(
                year_contract,
                {
                    "year_input_contract_id": "year-test",
                    "accounting": {"expected_mfa_input": 2},
                    "inputs": {
                        "frozen_search_master_inventory": {
                            "root": str(search_root.resolve())
                        }
                    },
                    "outputs": {
                        "expected_mfa_input_ids": file_fingerprint(
                            expected, with_sha256=True
                        )
                    },
                    "corpus_binding": {"recovered_wav_root": str(root / "recovered")},
                },
            )
            alignment = root / "alignment.json"
            write_json(
                alignment,
                {
                    "schema_version": "mfa_r3_alignment_contract.v1",
                    "status": "materialized_pending_runner_preflight_and_release_gate",
                    "year": year,
                    "r3_full_realign": True,
                    "alignment_contract_id": "alignment-test",
                    "identity": {"pronunciation_release_id": "release-test"},
                    "inputs": {
                        "year_input_contract": file_fingerprint(
                            year_contract, with_sha256=True
                        )
                    },
                },
            )
            output = root / "r3" / "corpus" / year
            state = root / "r3" / "contracts"
            first = materialize(
                year=year,
                alignment_contract_path=alignment,
                output_root=output,
                state_root=state,
            )
            self.assertEqual(first["counts"]["physical_wav"], 2)
            self.assertTrue(os.path.samefile(recovered / "U1.wav", output / "S1" / "U1.wav"))
            self.assertTrue((output / "S1" / "U1.lab").read_text(encoding="utf-8"))
            self.assertFalse((recovered / "U1.lab").exists())
            second = materialize(
                year=year,
                alignment_contract_path=alignment,
                output_root=output,
                state_root=state,
            )
            self.assertEqual(second["alignment_contract_id"], "alignment-test")


if __name__ == "__main__":
    unittest.main()
