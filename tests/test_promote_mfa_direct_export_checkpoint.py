import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_mfa_alignment_contract import recompute_alignment_contract_id  # noqa: E402
from pipeline_common import atomic_write_json, file_fingerprint  # noqa: E402
from promote_mfa_direct_export_checkpoint import promote_checkpoint  # noqa: E402


class PromoteMfaDirectExportCheckpointTests(unittest.TestCase):
    def fixture(self, root: Path):
        project = root / "project"
        search = root / "search"
        search.mkdir()
        partial = root / "staging" / "_partial" / "ALIGN" / "2021"
        final_root = root / "staging"
        final = final_root / "2021"
        tables = partial / "_tables"
        tables.mkdir(parents=True)
        table_records = {}
        exclusions = root / "approved_exclusions.json"
        exclusions.write_text("{}\n", encoding="utf-8")
        for name, filename in {
            "utterances": "utterance_alignment.csv.gz",
            "words": "word_intervals_mfa.csv.gz",
            "phones": "phone_intervals_mfa.csv.gz",
            "excluded": "excluded_utterances.csv.gz",
        }.items():
            path = tables / filename
            path.write_bytes((name + "\n").encode())
            record = file_fingerprint(path, with_sha256=True)
            record["path"] = filename
            table_records[name] = record
        companion = {
            "schema_version": "mfa_research_companion_tables.v2",
            "status": "success",
            "year": "2021",
            "input_contract_id": "INPUT",
            "alignment_contract_id": "ALIGN",
            "approved_exclusions_contract": file_fingerprint(
                exclusions, with_sha256=True
            ),
            "tables": table_records,
            "counts": {
                "utterances": 2,
                "word_intervals": 2,
                "phone_intervals": 2,
                "excluded_utterances": 0,
            },
        }
        atomic_write_json(tables / "TABLES_MANIFEST.json", companion)
        db = root / "2021.db"
        db.write_bytes(b"db")
        alignment = {
            "schema_version": "mfa_alignment_contract.v1",
            "status": "passed",
            "year": "2021",
            "lab_input_contract_id": "INPUT",
            "runtime": {"mfa": "3.3.0"},
            "models": {
                role: {
                    "requested_name": role,
                    "bytes": index,
                    "sha256": role + "-sha",
                }
                for index, role in enumerate(
                    ("acoustic", "dictionary", "g2p"), 1
                )
            },
            "frozen_model_pin": {
                "commit": "commit",
                "contract": {"sha256": "bundle-sha"},
                "models": {"dictionary": {"sha256": "base-dict-sha"}},
            },
            "pronunciation_mode": "common_pron_mfa_r2_latest_jamo",
            "common_pron_adoption_contract": {"sha256": "adoption-sha"},
            "approved_exclusions_contract": {"sha256": "exclusion-sha"},
        }
        alignment["alignment_contract_id"] = recompute_alignment_contract_id(alignment)
        alignment_id = alignment["alignment_contract_id"]
        companion["alignment_contract_id"] = alignment_id
        atomic_write_json(tables / "TABLES_MANIFEST.json", companion)
        base_repair = root / "base_repair.json"
        later_repair = root / "later_repair.json"
        base_repair.write_text('{"status":"success"}\n', encoding="utf-8")
        later_repair.write_text('{"status":"success"}\n', encoding="utf-8")
        report = {
            "schema_version": "mfa_research_6tier_export.v1",
            "status": "success",
            "year": "2021",
            "db_path": str(db),
            "search_master_root": str(search),
            "output_root": str(partial.parent),
            "tier_names": [
                "words", "phones_mfa", "phoneme_r_auto", "utterance",
                "utterance_orth_r", "morph_analysis_utt",
            ],
            "input_contract_id": "INPUT",
            "alignment_contract_id": alignment_id,
            "counts": {
                "created": 0, "validated_existing": 2, "failed": 0,
                "alignment_missing": 0, "search_row_missing": 0,
                "spn_intervals": 0,
            },
            "coverage_pct": 100.0,
            "exact_id_reconciliation": {
                "status": "passed", "full_year_gate": True,
                "counts": {"active_lab_ids": 2},
            },
            "companion_tables": companion,
            "resume_checkpoint": {
                "targeted_repair_manifest": file_fingerprint(
                    base_repair, with_sha256=True
                ),
                "subsequent_targeted_repair_manifest": file_fingerprint(
                    later_repair, with_sha256=True
                ),
            },
        }
        contract = root / "alignment.json"
        ready = root / "ready.json"
        export = root / "export.json"
        integrity = root / "input_integrity.json"
        atomic_write_json(contract, alignment)
        atomic_write_json(export, report)
        atomic_write_json(
            integrity,
            {
                "all_years_pass": True,
                "gate_profile": "execution",
                "search_master_root": str(search),
                "retained_db_checkpoint": {
                    "status": "validated",
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": alignment_id,
                    "alignment_db": str(db),
                },
                "years": [
                    {
                        "year": "2021",
                        "execution_gates_pass": True,
                        "analysis_ready_gates_pass": True,
                        "counts": {},
                    }
                ],
            },
        )
        atomic_write_json(
            ready,
            {
                "year": "2021", "stage": "direct_db_ready",
                "details": {
                    "computation_complete": True,
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": alignment_id,
                    "alignment_db": str(db),
                    "search_master_root": str(search),
                },
            },
        )
        return {
            "project_root": project,
            "year": "2021",
            "export_report_path": export,
            "alignment_contract_path": contract,
            "ready_marker_path": ready,
            "partial_year": partial,
            "final_year": final,
            "align_marker_path": root / "done" / "2021.align_done",
            "merge_marker_path": root / "done" / "2021.merge_done",
            "promotion_report_path": root / "promotion.json",
            "staging_root": final_root,
            "existing_final_root": root / "canonical",
            "input_integrity_report": integrity,
            "approved_exclusions_contract": exclusions,
        }

    def test_promotes_and_is_idempotent_after_move(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.fixture(Path(temp))
            result = promote_checkpoint(**args)
            self.assertEqual(result["status"], "success")
            self.assertFalse(args["partial_year"].exists())
            self.assertTrue(args["final_year"].is_dir())
            self.assertTrue(args["align_marker_path"].is_file())
            self.assertTrue(args["merge_marker_path"].is_file())
            again = promote_checkpoint(**args)
            self.assertEqual(again["status"], "success")
            self.assertEqual(again["source_state"], "already_moved")

    def test_rejects_table_tampering_before_move(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.fixture(Path(temp))
            table = args["partial_year"] / "_tables" / "phone_intervals_mfa.csv.gz"
            table.write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "table size mismatch"):
                promote_checkpoint(**args)
            self.assertTrue(args["partial_year"].is_dir())
            self.assertFalse(args["final_year"].exists())

    def test_rejects_alignment_identity_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.fixture(Path(temp))
            data = json.loads(args["alignment_contract_path"].read_text())
            data["models"]["acoustic"]["sha256"] = "changed"
            atomic_write_json(args["alignment_contract_path"], data)
            with self.assertRaisesRegex(RuntimeError, "recomputation mismatch"):
                promote_checkpoint(**args)

    def test_rejects_export_exclusion_contract_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.fixture(Path(temp))
            args["approved_exclusions_contract"].write_text(
                '{"changed": true}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(
                RuntimeError, "approved export exclusions size mismatch"
            ):
                promote_checkpoint(**args)

    def test_rejects_repair_manifest_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.fixture(Path(temp))
            report = json.loads(
                args["export_report_path"].read_text(encoding="utf-8")
            )
            repair = Path(
                report["resume_checkpoint"][
                    "subsequent_targeted_repair_manifest"
                ]["path"]
            )
            repair.write_text('{"changed":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "repair evidence size mismatch"
            ):
                promote_checkpoint(**args)


if __name__ == "__main__":
    unittest.main()
