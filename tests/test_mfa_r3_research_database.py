from __future__ import annotations

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.python import audit_mfa_r3_research_database as auditor
from scripts.python import build_mfa_r3_research_database as builder


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def write_gzip(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class MfaR3ResearchDatabaseTests(unittest.TestCase):
    def test_preflight_rejects_missing_morphology_year(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = root / "release"
            year_root = release / "03_year_input_contracts" / "2023"
            write_json(
                year_root / "YEAR_INPUT_CONTRACT_2023.json",
                {
                    "release_id": "r3-test",
                    "pronunciation_contract_id": "pron-test",
                    "year": "2023",
                    "year_input_contract_id": "year-test",
                },
            )
            policy = {
                "release_id": "r3-test",
                "pronunciation_contract_id": "pron-test",
                "scope_years": ["2023"],
            }
            paths = {
                "year_input_contract_root": release / "03_year_input_contracts",
                "morph_search_root": root / "morph",
            }
            with self.assertRaisesRegex(RuntimeError, "frozen morphology year is incomplete"):
                builder.validate_year_preflight_inputs("2023", policy, paths)

    def test_type_occurrence_and_audit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = root / "release"
            readiness = root / "readiness.csv.gz"
            projection = release / "selected_pronunciation_projection.csv.gz"
            morph = root / "morph"
            year_contract_root = release / "03_year_input_contracts"
            output = release / "05_research_database"
            release.mkdir(parents=True)
            write_json(
                release / "RELEASE_MANIFEST.json",
                {"release_id": "r3-test", "pronunciation_contract_id": "pron-test"},
            )
            gate = root / "gate.json"
            write_json(gate, {"status": "adopted", "allowed_release_ids": ["r3-test"]})

            readiness_fields = [
                "token", "planning_status", "planning_zero_fallback_hold",
                "planning_requires_policy_decision", "planning_reason",
            ]
            write_gzip(
                readiness,
                readiness_fields,
                [
                    {"token": "가", "planning_status": "candidate_test", "planning_zero_fallback_hold": "false", "planning_requires_policy_decision": "false", "planning_reason": "ok"},
                    {"token": "나", "planning_status": "hold_test", "planning_zero_fallback_hold": "true", "planning_requires_policy_decision": "false", "planning_reason": "hold"},
                    {"token": "다", "planning_status": "policy_test", "planning_zero_fallback_hold": "false", "planning_requires_policy_decision": "true", "planning_reason": "policy"},
                ],
            )
            projection_fields = [
                "token", "variant_index", "variant_count",
                "selected_pron_phones_mfa", "selected_pron_roman",
                "source_candidate_status", "source_candidate_source",
                "source_candidate_reason", "selection_status",
                "selection_source", "selection_reason", "final_selection",
            ]
            write_gzip(
                projection,
                projection_fields,
                [{
                    "token": "가", "variant_index": "1", "variant_count": "1",
                    "selected_pron_phones_mfa": "k a", "selected_pron_roman": "G A",
                    "source_candidate_status": "candidate_test", "source_candidate_source": "test",
                    "source_candidate_reason": "test", "selection_status": "selected",
                    "selection_source": "test", "selection_reason": "test", "final_selection": "true",
                }],
            )

            shard = morph / "2020" / "shards" / "shard_00001"
            master_fields = [
                "utt_id", "year", "session_id", "form", "pron_reference_form",
                "pron_reference_n_eojeol", "pron_reference_status",
                "orth_eojeol_count_structured", "morph_eojeol_count_structured",
            ]
            write_gzip(
                shard / "tables" / "utterance_master_v2.csv.gz",
                master_fields,
                [
                    {"utt_id": "U1", "year": "2020", "session_id": "S1", "form": "가", "pron_reference_form": "가", "pron_reference_n_eojeol": "1", "pron_reference_status": "resolved", "orth_eojeol_count_structured": "1", "morph_eojeol_count_structured": "1"},
                    {"utt_id": "U2", "year": "2020", "session_id": "S1", "form": "나", "pron_reference_form": "나", "pron_reference_n_eojeol": "1", "pron_reference_status": "resolved", "orth_eojeol_count_structured": "1", "morph_eojeol_count_structured": "1"},
                    {"utt_id": "U3", "year": "2020", "session_id": "S2", "form": "1 다", "pron_reference_form": "1 다", "pron_reference_n_eojeol": "2", "pron_reference_status": "unresolved_symbol", "orth_eojeol_count_structured": "2", "morph_eojeol_count_structured": "1"},
                ],
            )
            write_json(shard / "SHARD_MANIFEST.json", {"status": "success"})

            year_root = year_contract_root / "2020"
            write_json(
                year_root / "YEAR_INPUT_CONTRACT_2020.json",
                {
                    "release_id": "r3-test", "pronunciation_contract_id": "pron-test",
                    "year": "2020", "year_input_contract_id": "year-test",
                },
            )
            id_fields = ["year", "utt_id", "session_id", "source_csv"]
            write_gzip(year_root / "expected_mfa_input_ids_2020.csv.gz", id_fields, [{"year": "2020", "utt_id": "U1", "session_id": "S1", "source_csv": "S1.csv"}])
            write_gzip(year_root / "pre_mfa_exclusion_ids_2020.csv.gz", id_fields + ["reason_codes_json"], [])
            follow_fields = id_fields + ["routing_class", "hold_tokens_json", "policy_tokens_json", "unknown_tokens_json"]
            write_gzip(
                year_root / "pronunciation_followup_ids_2020.csv.gz",
                follow_fields,
                [
                    {"year": "2020", "utt_id": "U2", "session_id": "S1", "source_csv": "S1.csv", "routing_class": "hold", "hold_tokens_json": '["나"]', "policy_tokens_json": "[]", "unknown_tokens_json": "[]"},
                    {"year": "2020", "utt_id": "U3", "session_id": "S2", "source_csv": "S2.csv", "routing_class": "policy", "hold_tokens_json": "[]", "policy_tokens_json": '["다"]', "unknown_tokens_json": "[]"},
                ],
            )
            write_gzip(year_root / "pronunciation_safe_ids_2020.csv.gz", id_fields, [{"year": "2020", "utt_id": "U1", "session_id": "S1", "source_csv": "S1.csv"}])

            config = root / "config.json"
            policy = {
                "schema_version": "mfa_r3_research_database.v1",
                "status": "approved_fail_closed_before_first_r3_alignment",
                "release_id": "r3-test",
                "pronunciation_contract_id": "pron-test",
                "scope_years": ["2020"],
                "paths": {
                    "release_root": str(release), "readiness_table": str(readiness),
                    "selected_projection": str(projection),
                    "release_manifest": str(release / "RELEASE_MANIFEST.json"),
                    "release_gate": str(gate), "morph_search_root": str(morph),
                    "year_input_contract_root": str(year_contract_root), "output_root": str(output),
                },
                "invariants": {
                    "canonical_types": 3, "selected_types": 1, "selected_variant_rows": 1,
                    "zero_fallback_hold_types": 1, "explicit_policy_hold_types": 1,
                },
            }
            write_json(config, policy)
            loaded = builder.load_policy(config)
            paths = builder.validate_frozen_inputs(loaded)
            catalog = builder.build_catalog(policy=loaded, paths=paths)
            year = builder.build_year(year="2020", policy=loaded, paths=paths, catalog=catalog)
            self.assertEqual(year["counts"]["utterances"], 3)
            self.assertEqual(year["counts"]["occurrences"], 4)
            type_audit, classes = auditor.audit_type_catalog(loaded, paths)
            report = auditor.audit_year(
                year="2020", policy=loaded, paths=paths,
                type_audit=type_audit, classes=classes,
            )
            self.assertEqual(report["status"], "passed")
            self.assertTrue(report["verdict"]["ready_for_mfa_preflight"])


if __name__ == "__main__":
    unittest.main()
