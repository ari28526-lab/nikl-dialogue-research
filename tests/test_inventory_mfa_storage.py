import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPTS))

from inventory_mfa_storage import (  # noqa: E402
    build_inventory,
    classify_temp_file,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False),
        encoding="utf-8",
    )


class MfaStorageInventoryTests(unittest.TestCase):
    def test_classification_is_conservative(self):
        self.assertEqual(
            classify_temp_file(
                year="2021", relative_path="2021.db"
            )[0],
            "retain_critical",
        )
        self.assertEqual(
            classify_temp_file(
                year="2021",
                relative_path="alignment/fsts.korean_mfa.1.ark",
            )[0],
            "cleanup_candidate_after_qc",
        )
        self.assertEqual(
            classify_temp_file(
                year="2021",
                relative_path="alignment/phone_intervals.csv",
            )[0],
            "cleanup_candidate_after_qc",
        )
        self.assertEqual(
            classify_temp_file(
                year="2021",
                relative_path="alignment/log/align.1.log",
            )[0],
            "retain_reproducibility",
        )
        self.assertEqual(
            classify_temp_file(
                year="2021",
                relative_path="alignment/tree",
            )[0],
            "retain_reproducibility",
        )
        self.assertEqual(
            classify_temp_file(
                year="2021", relative_path="mystery.bin"
            )[0],
            "retain_unclassified",
        )

    def test_ready_report_never_authorizes_or_performs_deletion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            temp_year = root / "temp" / "2021"
            temp_year.mkdir(parents=True)
            db = temp_year / "2021.db"
            db.write_bytes(b"SQLite fixture")
            archive = temp_year / "alignment" / "ali.1.ark"
            archive.parent.mkdir()
            archive.write_bytes(b"ark")
            log = temp_year / "alignment" / "align.log"
            log.write_text("log", encoding="utf-8")

            audit = root / "audit.json"
            align = root / "align.json"
            merge = root / "merge.json"
            contract = root / "contract.json"
            direct = root / "direct.json"
            for path in (audit, align, merge, contract, direct):
                write_json(path, {"status": "success"})
            gate = root / "gate.json"
            write_json(
                gate,
                {
                    "status": "passed",
                    "prior_year": "2021",
                    "failed_checks": [],
                    "inputs": {
                        "alignment_db": str(db),
                        "audit_report": str(audit),
                        "align_marker": str(align),
                        "merge_marker": str(merge),
                        "temp_contract": str(contract),
                        "direct_export_report": str(direct),
                    },
                },
            )

            report = build_inventory(
                year="2021",
                temp_year=temp_year,
                qc_gate_report=gate,
                hash_db=True,
            )

            self.assertEqual(report["status"], "ready_for_user_review")
            self.assertFalse(report["deletion_performed"])
            self.assertFalse(report["apply_supported"])
            self.assertTrue(
                report["authorization_required_for_any_cleanup"]
            )
            self.assertEqual(
                report["estimated_reclaim"]["bytes"],
                archive.stat().st_size,
            )
            self.assertEqual(
                report["classification_summary"]["retain_critical"]["files"],
                1,
            )
            self.assertEqual(
                report["classification_summary"][
                    "retain_reproducibility"
                ]["files"],
                1,
            )
            self.assertIn(
                "sha256", report["retained_db_fingerprint"]
            )
            self.assertTrue(archive.exists())
            self.assertTrue(db.exists())

    def test_active_transaction_and_unknown_file_block_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            temp_year = root / "2021"
            temp_year.mkdir()
            db = temp_year / "2021.db"
            db.write_bytes(b"db")
            (temp_year / "2021.db-journal").write_bytes(b"journal")
            (temp_year / "unknown.bin").write_bytes(b"unknown")
            gate = root / "gate.json"
            write_json(
                gate,
                {
                    "status": "passed",
                    "prior_year": "2021",
                    "failed_checks": [],
                    "inputs": {"alignment_db": str(db)},
                },
            )

            report = build_inventory(
                year="2021",
                temp_year=temp_year,
                qc_gate_report=gate,
            )

            self.assertEqual(report["status"], "blocked")
            self.assertIn(
                "active_sqlite_transaction_files_present",
                report["blockers"],
            )
            self.assertIn(
                "unclassified_temp_files_present",
                report["blockers"],
            )
            self.assertFalse(report["deletion_performed"])

    def test_r3_qc_state_is_accepted_and_binds_retained_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            temp_year = root / "temp" / "2023"
            temp_year.mkdir(parents=True)
            db = temp_year / "2023.db"
            db.write_bytes(b"r3 database fixture")
            archive = temp_year / "alignment" / "ali.1.ark"
            archive.parent.mkdir()
            archive.write_bytes(b"ark")
            audit = root / "01_year_audit.json"
            sample_json = root / "02_db_sample.json"
            sample_csv = root / "02_db_sample.csv"
            missing_csv = root / "01_id_inventory.csv"
            write_json(audit, {"status": "success"})
            write_json(sample_json, {"status": "success"})
            sample_csv.write_text("id\n", encoding="utf-8")
            missing_csv.write_text("id\n", encoding="utf-8")

            import hashlib

            expected_sha = hashlib.sha256(db.read_bytes()).hexdigest()
            gate = root / "QC_STATE.json"
            write_json(
                gate,
                {
                    "schema_version": "mfa_r3_research_qc_state.v1",
                    "status": "passed",
                    "year": "2023",
                    "source_mutation_performed": False,
                    "mfa_recomputed": False,
                    "full_export_repeated": False,
                    "counts": {
                        "sample_sessions": 24,
                        "sample_semantic_equal": 24,
                        "sample_byte_equal": 24,
                    },
                    "qc_input": {
                        "source_db_bytes": db.stat().st_size,
                        "source_db_expected_sha256": expected_sha,
                    },
                    "audit_report": {"path": str(audit)},
                    "missing_csv": {"path": str(missing_csv)},
                    "sample_report": {"path": str(sample_json)},
                    "sample_csv": {"path": str(sample_csv)},
                },
            )

            report = build_inventory(
                year="2023",
                temp_year=temp_year,
                qc_gate_report=gate,
                hash_db=True,
            )

            self.assertEqual(report["status"], "ready_for_user_review")
            self.assertEqual(
                report["qc_gate_kind"], "mfa_r3_research_qc_state"
            )
            self.assertEqual(report["estimated_reclaim"]["files"], 1)
            self.assertTrue(db.exists())
            self.assertTrue(archive.exists())

    def test_r3_qc_state_database_mismatch_blocks_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            temp_year = root / "temp" / "2023"
            temp_year.mkdir(parents=True)
            db = temp_year / "2023.db"
            db.write_bytes(b"database")
            gate = root / "QC_STATE.json"
            write_json(
                gate,
                {
                    "schema_version": "mfa_r3_research_qc_state.v1",
                    "status": "passed",
                    "year": "2023",
                    "source_mutation_performed": False,
                    "mfa_recomputed": False,
                    "full_export_repeated": False,
                    "counts": {
                        "sample_sessions": 24,
                        "sample_semantic_equal": 24,
                        "sample_byte_equal": 24,
                    },
                    "qc_input": {
                        "source_db_bytes": db.stat().st_size,
                        "source_db_expected_sha256": "0" * 64,
                    },
                },
            )

            report = build_inventory(
                year="2023",
                temp_year=temp_year,
                qc_gate_report=gate,
                hash_db=True,
            )

            self.assertEqual(report["status"], "blocked")
            self.assertIn(
                "qc_gate_alignment_db_sha256_mismatch",
                report["blockers"],
            )

    def test_missing_or_failed_gate_blocks_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            temp_year = root / "2021"
            temp_year.mkdir()
            (temp_year / "2021.db").write_bytes(b"db")
            gate = root / "gate.json"
            write_json(
                gate,
                {
                    "status": "failed",
                    "prior_year": "2021",
                    "failed_checks": ["audit"],
                    "inputs": {
                        "alignment_db": str(temp_year / "2021.db")
                    },
                },
            )

            report = build_inventory(
                year="2021",
                temp_year=temp_year,
                qc_gate_report=gate,
            )

            self.assertEqual(report["status"], "blocked")
            self.assertIn("qc_gate_not_passed", report["blockers"])
            self.assertIn("qc_gate_has_failed_checks", report["blockers"])


if __name__ == "__main__":
    unittest.main()
