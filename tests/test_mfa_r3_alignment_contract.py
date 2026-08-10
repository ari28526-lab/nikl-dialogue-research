from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.audit_mfa_r3_alignment_contract import audit
from scripts.python.build_mfa_r3_alignment_contract import (
    build_alignment_contract,
    recompute_alignment_contract_id,
    write_if_new,
)
from scripts.python.pipeline_common import file_fingerprint


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class R3AlignmentContractTests(unittest.TestCase):
    def fixture(self, root: Path, *, release_note: str = "a") -> dict[str, Path]:
        release_id = "common_pron_mfa_r3_20260809"
        adoption = root / "adoption.json"
        approval = root / "approval.json"
        routing = root / "routing.json"
        acoustic = root / "acoustic.zip"
        g2p = root / "g2p.zip"
        dictionary = root / "release.dict"
        for path, data in (
            (adoption, b"adoption"),
            (approval, b"approval"),
            (routing, b"routing"),
            (acoustic, b"acoustic"),
            (g2p, b"g2p"),
            (dictionary, b"word\tphone\n"),
        ):
            path.write_bytes(data)
        pin = root / "pin.json"
        write_json(
            pin,
            {
                "status": "passed",
                "models": {
                    "acoustic_model": file_fingerprint(acoustic, with_sha256=True),
                    "g2p_model": file_fingerprint(g2p, with_sha256=True),
                },
            },
        )
        release = root / "release.json"
        write_json(
            release,
            {
                "schema_version": "common_pron_mfa_r3_staged_release.v1",
                "status": "materialized_pending_independent_adoption_audit_and_release_gate",
                "release_id": release_id,
                "pronunciation_contract_id": "pron-contract",
                "note": release_note,
                "scope": {
                    "adopted": False,
                    "allow_yearly_mfa": False,
                    "allow_textgrid_materialization": False,
                },
                "inputs": {
                    "v3_1_contract": file_fingerprint(adoption, with_sha256=True),
                    "researcher_approval": file_fingerprint(approval, with_sha256=True),
                    "stage19_routing_manifest": file_fingerprint(routing, with_sha256=True),
                    "frozen_model_pin": file_fingerprint(pin, with_sha256=True),
                },
                "outputs": {
                    "mfa_dictionary": file_fingerprint(dictionary, with_sha256=True)
                },
            },
        )
        release_audit = root / "release_audit.json"
        write_json(
            release_audit,
            {
                "status": "passed_independent_staged_adoption_audit_pending_release_gate",
                "verdict": {
                    "production_mfa_allowed": False,
                    "release_gate_remains_closed": True,
                },
                "inputs": {
                    "release_manifest": file_fingerprint(release, with_sha256=True)
                },
            },
        )
        expected_ids = root / "expected.csv.gz"
        followup_ids = root / "followup.csv.gz"
        exclusion_ids = root / "exclude.csv.gz"
        expected_ids.write_bytes(b"expected")
        followup_ids.write_bytes(b"followup")
        exclusion_ids.write_bytes(b"exclude")
        year_contract = root / "year_contract.json"
        write_json(
            year_contract,
            {
                "schema_version": "mfa_r3_year_input_contract.v1",
                "status": "materialized_pending_independent_year_input_audit_gate_closed",
                "year": "2020",
                "release_id": release_id,
                "year_input_contract_id": "year-contract",
                "scope": {"production_mfa_allowed": False},
                "accounting": {"expected_mfa_input": 2},
                "corpus_binding": {
                    "corpus_contract_id": "corpus-contract",
                    "recovered_wav_root": str(root / "wav"),
                },
                "outputs": {
                    "expected_mfa_input_ids": file_fingerprint(
                        expected_ids, with_sha256=True
                    ),
                    "pronunciation_followup_ids": file_fingerprint(
                        followup_ids, with_sha256=True
                    ),
                    "pre_mfa_exclusion_ids": file_fingerprint(
                        exclusion_ids, with_sha256=True
                    ),
                },
            },
        )
        year_audit = root / "year_audit.json"
        write_json(
            year_audit,
            {
                "status": "passed_independent_exact_id_audit_pending_alignment_contract_gate_closed",
                "year_input_contract_id": "year-contract",
                "verdict": {
                    "exact_id_partition_passed": True,
                    "production_mfa_allowed": False,
                    "release_gate_remains_closed": True,
                },
                "inputs": {
                    "year_input_contract": file_fingerprint(
                        year_contract, with_sha256=True
                    )
                },
            },
        )
        gate = root / "gate.json"
        write_json(gate, {"status": "blocked_test", "allowed_release_ids": []})
        policy = root / "policy.json"
        write_json(
            policy,
            {
                "schema_version": "mfa_r3_alignment_contract_policy.v1",
                "status": "approved_contract_building_only_gate_closed",
                "pronunciation_release_id": release_id,
                "pronunciation_mode": "common_pron_mfa_r3_staged_safe_body",
                "alignment_origin": "fresh_r3_full_realign",
                "r3_full_realign": True,
                "scope": {
                    "years_enabled": ["2020"],
                    "production_mfa_allowed": False,
                    "textgrid_materialization_allowed": False,
                    "legacy_marker_reuse_allowed": False,
                    "legacy_db_reuse_allowed": False,
                },
            },
        )
        return {
            "policy": policy,
            "release": release,
            "release_audit": release_audit,
            "year_contract": year_contract,
            "year_audit": year_audit,
            "gate": gate,
            "output": root / "ALIGNMENT_CONTRACT_2020.json",
        }

    def build(self, paths: dict[str, Path]) -> dict:
        return build_alignment_contract(
            year="2020",
            policy_path=paths["policy"],
            release_manifest_path=paths["release"],
            release_audit_path=paths["release_audit"],
            year_input_contract_path=paths["year_contract"],
            year_input_audit_path=paths["year_audit"],
            release_gate_path=paths["gate"],
            runtime={
                "python": "3.13-test",
                "montreal_forced_aligner": "3.3-test",
                "pynini": "2.1-test",
            },
        )

    def test_identity_pins_release_routing_dictionary_and_year_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            contract = self.build(paths)
            identity = contract["identity"]
            self.assertEqual(
                contract["alignment_contract_id"],
                recompute_alignment_contract_id(contract),
            )
            self.assertEqual(
                identity["pronunciation_release_id"],
                "common_pron_mfa_r3_20260809",
            )
            self.assertTrue(identity["safe_body_routing_contract_id"])
            self.assertTrue(identity["mfa_dictionary_sha256"])
            self.assertEqual(identity["year_input_contract_id"], "year-contract")

    def test_release_manifest_sha_changes_contract_id(self) -> None:
        with tempfile.TemporaryDirectory() as first_temp, tempfile.TemporaryDirectory() as second_temp:
            first = self.build(self.fixture(Path(first_temp), release_note="a"))
            second = self.build(self.fixture(Path(second_temp), release_note="b"))
            self.assertNotEqual(
                first["alignment_contract_id"], second["alignment_contract_id"]
            )

    def test_write_is_immutable_and_independent_audit_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            contract = self.build(paths)
            self.assertTrue(write_if_new(paths["output"], contract))
            self.assertFalse(write_if_new(paths["output"], contract))
            report = audit(paths["output"], Path(temp) / "audit.json")
            self.assertTrue(report["verdict"]["identity_recomputed_exact"])
            self.assertFalse(report["verdict"]["production_mfa_allowed"])
            changed = dict(contract)
            changed["alignment_contract_id"] = "tampered"
            with self.assertRaisesRegex(RuntimeError, "immutable overwrite refused"):
                write_if_new(paths["output"], changed)

    def test_builder_has_no_release_specific_legacy_magic(self) -> None:
        source = Path(
            "scripts/python/build_mfa_r3_alignment_contract.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("common_pron_mfa_r2_", source)
        self.assertNotIn("g2p_jamo_ls_rewrite_words", source)

    def test_adopted_release_gate_builds_next_year_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            policy = json.loads(paths["policy"].read_text(encoding="utf-8"))
            policy["status"] = "approved_contract_building_release_adopted"
            write_json(paths["policy"], policy)
            write_json(
                paths["gate"],
                {
                    "status": "adopted",
                    "allowed_release_ids": ["common_pron_mfa_r3_20260809"],
                },
            )
            contract = self.build(paths)
            write_if_new(paths["output"], contract)
            report = audit(paths["output"], Path(temp) / "adopted_audit.json")
            self.assertTrue(report["verdict"]["release_gate_adopted_for_release"])
            self.assertFalse(report["verdict"]["release_gate_remains_closed"])


if __name__ == "__main__":
    unittest.main()
