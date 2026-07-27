import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPTS))

from preflight_next_year_after_qc import validate_next_year_gate


class NextYearAfterQcPreflightTests(unittest.TestCase):
    def _fixtures(self, root: Path) -> dict:
        search = root / "search"
        final_year = root / "stage" / "2021"
        temp_year = root / "temp" / "2021"
        db = temp_year / "2021.db"
        missing = root / "missing.csv"
        direct_report = root / "direct.json"
        for directory in (search, final_year, temp_year):
            directory.mkdir(parents=True, exist_ok=True)
        db.write_bytes(b"sqlite")
        missing.write_text("utt_id\n", encoding="utf-8")
        contract_id = "contract-2021"

        audit = {
            "status": "success",
            "year": "2021",
            "input_contract_id": contract_id,
            "textgrid_root": str(final_year),
            "missing_csv": str(missing),
            "coverage_pct": 99.5,
            "hard_failure_counts": {
                "duplicate_lab_ids": 0,
                "invalid_textgrids": 0,
                "missing_without_wav": 0,
            },
            "counts": {"lab_ids": 1000, "textgrid_ids": 995},
        }
        align = {
            "year": "2021",
            "stage": "align",
            "g2p_model": "korean_mfa",
            "details": {
                "export_mode": "direct_db_4tier",
                "input_contract_id": contract_id,
                "search_master_root": str(search),
                "alignment_db": str(db),
                "labs": 1000,
                "textgrids": 995,
            },
        }
        merge = {
            "year": "2021",
            "stage": "merge",
            "g2p_model": "korean_mfa",
            "details": {
                "export_mode": "direct_db_4tier",
                "input_contract_id": contract_id,
                "search_master_root": str(search),
                "staging_output_root": str(final_year.parent),
                "direct_export_report": str(direct_report),
                "alignment_db_retained": True,
            },
        }
        temp_contract = {
            "year": "2021",
            "input_contract_id": contract_id,
            "search_master_root": str(search),
            "temp_year": str(temp_year),
            "status": "direct_merge_completed_temp_retained_for_qc",
        }
        direct = {
            "status": "success",
            "year": "2021",
            "db_path": str(db),
            "search_master_root": str(search),
            "counts": {
                "created": 995,
                "validated_existing": 0,
                "form_missing": 0,
                "morpheme_tier_missing": 0,
                "failed": 0,
            },
        }
        paths = {}
        for name, payload in (
            ("audit", audit),
            ("align", align),
            ("merge", merge),
            ("contract", temp_contract),
            ("direct", direct),
        ):
            path = root / f"{name}.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            paths[name] = path
        paths.update(
            search=search,
            final_year=final_year,
            report=root / "gate.json",
        )
        return paths

    def _run(self, paths: dict) -> dict:
        return validate_next_year_gate(
            prior_year="2021",
            next_year="2022",
            audit_report=paths["audit"],
            align_marker=paths["align"],
            merge_marker=paths["merge"],
            temp_contract=paths["contract"],
            expected_search_master_root=paths["search"],
            expected_final_year_root=paths["final_year"],
            report_path=paths["report"],
        )

    def test_matching_qc_markers_report_and_db_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            report = self._run(paths)
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["failed_checks"], [])
            stored = json.loads(paths["report"].read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "passed")

    def test_contract_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            merge = json.loads(paths["merge"].read_text(encoding="utf-8"))
            merge["details"]["input_contract_id"] = "other-contract"
            paths["merge"].write_text(json.dumps(merge), encoding="utf-8")
            report = self._run(paths)
            self.assertEqual(report["status"], "failed")
            self.assertIn("input_contract_match", report["failed_checks"])

    def test_missing_retained_db_and_direct_report_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            align = json.loads(paths["align"].read_text(encoding="utf-8"))
            Path(align["details"]["alignment_db"]).unlink()
            direct = Path(
                json.loads(paths["merge"].read_text(encoding="utf-8"))[
                    "details"
                ]["direct_export_report"]
            )
            direct.unlink()
            report = self._run(paths)
            self.assertEqual(report["status"], "failed")
            self.assertIn("alignment_db_retained", report["failed_checks"])
            self.assertIn("direct_report_readable", report["failed_checks"])

    def test_corrupt_numeric_fields_fail_with_saved_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
            audit["coverage_pct"] = "not-a-number"
            audit["counts"]["lab_ids"] = "broken"
            paths["audit"].write_text(json.dumps(audit), encoding="utf-8")
            direct = json.loads(
                paths["direct"].read_text(encoding="utf-8")
            )
            direct["counts"]["failed"] = "broken"
            paths["direct"].write_text(
                json.dumps(direct), encoding="utf-8"
            )
            report = self._run(paths)
            self.assertEqual(report["status"], "failed")
            self.assertIn("audit_hard_gate", report["failed_checks"])
            self.assertIn("direct_report_gate", report["failed_checks"])
            self.assertIn("artifact_counts_match", report["failed_checks"])
            self.assertTrue(paths["report"].is_file())


if __name__ == "__main__":
    unittest.main()
