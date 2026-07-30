import json
import hashlib
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
                "alignment_contract_id": "alignment-2021",
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
        sample = {
            "schema_version": 1,
            "status": "success",
            "year": "2021",
            "input_contract_id": contract_id,
            "db": {"path": str(db)},
            "comparison_counts": {
                "compared": 5,
                "tier_equal": 5,
            },
            "selection_counts": {"selected_sessions": 5},
        }
        researcher = {
            "schema_version": (
                "mfa_r2_infrastructure_researcher_review.v1"
            ),
            "status": "approved",
            "allow_bulk_mfa": True,
            "review_scope": "infrastructure_acceptance_only",
            "realization_judgment_performed": False,
            "counts": {
                "years": {"2021": 10},
                "speakers": 5,
            },
            "year_contracts": {
                "2021": {
                    "alignment_contract_id": "alignment-2021",
                    "lab_input_contract_id": contract_id,
                    "database": str(db),
                }
            },
        }
        paths = {}
        for name, payload in (
            ("audit", audit),
            ("align", align),
            ("merge", merge),
            ("contract", temp_contract),
            ("direct", direct),
            ("sample", sample),
            ("researcher", researcher),
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

    def _run(
        self,
        paths: dict,
        expected_pronunciation_mode: str = "korean_mfa",
    ) -> dict:
        return validate_next_year_gate(
            prior_year="2021",
            next_year="2022",
            audit_report=paths["audit"],
            align_marker=paths["align"],
            merge_marker=paths["merge"],
            temp_contract=paths["contract"],
            sample_equivalence_report=paths["sample"],
            researcher_review_report=paths["researcher"],
            expected_search_master_root=paths["search"],
            expected_final_year_root=paths["final_year"],
            expected_pronunciation_mode=expected_pronunciation_mode,
            report_path=paths["report"],
        )

    def test_matching_qc_markers_report_and_db_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            report = self._run(paths)
            self.assertEqual(report["status"], "passed")
            self.assertEqual(
                report["supported_export_mode"], "direct_db_4tier"
            )
            self.assertEqual(report["failed_checks"], [])
            stored = json.loads(paths["report"].read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "passed")

    def test_r2_pronunciation_mode_passes_when_markers_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            for name in ("align", "merge"):
                payload = json.loads(
                    paths[name].read_text(encoding="utf-8")
                )
                payload["g2p_model"] = (
                    "common_pron_mfa_r2_latest_jamo"
                )
                paths[name].write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            report = self._run(
                paths, "common_pron_mfa_r2_latest_jamo"
            )
            self.assertEqual(report["status"], "passed")

    def test_unknown_pronunciation_mode_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            for name in ("align", "merge"):
                payload = json.loads(
                    paths[name].read_text(encoding="utf-8")
                )
                payload["g2p_model"] = "unknown_mode"
                paths[name].write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            report = self._run(paths, "unknown_mode")
            self.assertEqual(report["status"], "failed")
            self.assertIn(
                "expected_pronunciation_mode_supported",
                report["failed_checks"],
            )

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

    def test_sample_other_db_and_unapproved_review_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            sample = json.loads(
                paths["sample"].read_text(encoding="utf-8")
            )
            sample["db"]["path"] = str(Path(tmp) / "other.db")
            paths["sample"].write_text(
                json.dumps(sample), encoding="utf-8"
            )
            researcher = json.loads(
                paths["researcher"].read_text(encoding="utf-8")
            )
            researcher["status"] = "changes_required"
            researcher["allow_bulk_mfa"] = False
            paths["researcher"].write_text(
                json.dumps(researcher), encoding="utf-8"
            )

            report = self._run(paths)

            self.assertEqual(report["status"], "failed")
            self.assertIn(
                "db_textgrid_sample_equivalence",
                report["failed_checks"],
            )
            self.assertIn(
                "researcher_infrastructure_review",
                report["failed_checks"],
            )

    def test_missing_sample_and_review_reports_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            paths["sample"].unlink()
            paths["researcher"].unlink()

            report = self._run(paths)

            self.assertEqual(report["status"], "failed")
            self.assertIn(
                "sample_equivalence_report_readable",
                report["failed_checks"],
            )
            self.assertIn(
                "researcher_review_report_readable",
                report["failed_checks"],
            )

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

    def test_unaccounted_direct_morph_gap_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            direct = json.loads(
                paths["direct"].read_text(encoding="utf-8")
            )
            direct["counts"]["morpheme_tier_missing"] = 1
            direct["morpheme_tier_missing_inventory"] = ["S1.1"]
            paths["direct"].write_text(
                json.dumps(direct), encoding="utf-8"
            )

            report = self._run(paths)

            self.assertEqual(report["status"], "failed")
            self.assertIn(
                "morphology_classification_evidence",
                report["failed_checks"],
            )
            self.assertIn(
                "direct_morphology_accounted",
                report["failed_checks"],
            )

    def test_classified_exclusion_can_account_for_direct_morph_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            classification = Path(tmp) / "classification.csv"
            classification.write_text(
                "year,utt_id,recommended_action\n"
                "2021,S1.1,exclude_source_audio_unusable\n",
                encoding="utf-8",
            )
            classification_sha = hashlib.sha256(
                classification.read_bytes()
            ).hexdigest()
            audit = json.loads(
                paths["audit"].read_text(encoding="utf-8")
            )
            audit["morphology_classification"] = {
                "source_fingerprint": {
                    "path": str(classification),
                    "sha256": classification_sha,
                },
                "counts_by_action": {
                    "exclude_source_audio_unusable": 1,
                },
                "recovery_candidate_not_valid": 0,
                "unclassified_ids": 0,
                "classification_ids_without_lab": 0,
            }
            paths["audit"].write_text(
                json.dumps(audit), encoding="utf-8"
            )
            direct = json.loads(
                paths["direct"].read_text(encoding="utf-8")
            )
            direct["counts"]["morpheme_tier_missing"] = 1
            direct["morpheme_tier_missing_inventory"] = ["S1.1"]
            paths["direct"].write_text(
                json.dumps(direct), encoding="utf-8"
            )

            report = self._run(paths)

            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["failed_checks"], [])

    def test_same_morph_count_with_wrong_ids_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixtures(Path(tmp))
            classification = Path(tmp) / "classification.csv"
            classification.write_text(
                "year,utt_id,recommended_action\n"
                "2021,S1.1,exclude_source_audio_unusable\n",
                encoding="utf-8",
            )
            classification_sha = hashlib.sha256(
                classification.read_bytes()
            ).hexdigest()
            audit = json.loads(
                paths["audit"].read_text(encoding="utf-8")
            )
            audit["morphology_classification"] = {
                "source_fingerprint": {
                    "path": str(classification),
                    "sha256": classification_sha,
                },
                "counts_by_action": {
                    "exclude_source_audio_unusable": 1,
                },
                "recovery_candidate_not_valid": 0,
                "unclassified_ids": 0,
                "classification_ids_without_lab": 0,
            }
            paths["audit"].write_text(
                json.dumps(audit), encoding="utf-8"
            )
            direct = json.loads(
                paths["direct"].read_text(encoding="utf-8")
            )
            direct["counts"]["morpheme_tier_missing"] = 1
            direct["morpheme_tier_missing_inventory"] = ["OTHER.1"]
            paths["direct"].write_text(
                json.dumps(direct), encoding="utf-8"
            )

            report = self._run(paths)

            self.assertEqual(report["status"], "failed")
            self.assertIn(
                "morphology_classification_evidence",
                report["failed_checks"],
            )
            self.assertIn(
                "direct_morphology_accounted",
                report["failed_checks"],
            )


if __name__ == "__main__":
    unittest.main()
