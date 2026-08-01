import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from preflight_next_year_after_qc import validate_next_year_gate  # noqa: E402


class PreflightNextYearAfterResearchQcTests(unittest.TestCase):
    def write(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_research_six_tier_dispatch_passes_exact_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            final = root / "final" / "2020"
            search.mkdir()
            final.mkdir(parents=True)
            db = root / "2020.db"
            db.write_bytes(b"sqlite fixture")
            direct = root / "direct.json"
            self.write(
                direct,
                {
                    "status": "success",
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": "ALIGN",
                    "exact_id_reconciliation": {
                        "status": "passed",
                        "full_year_gate": True,
                    },
                    "companion_tables": {"status": "success"},
                },
            )
            audit = root / "audit.json"
            self.write(
                audit,
                {
                    "schema_version": "mfa_research_6tier_year_audit.v1",
                    "status": "success",
                    "year": "2020",
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": "ALIGN",
                    "coverage_pct": 100.0,
                    "hard_failure_counts": {"x": 0},
                    "textgrid_root": str(final.parent),
                    "table_manifest": {
                        "status": "success",
                        "input_contract_id": "INPUT",
                        "alignment_contract_id": "ALIGN",
                    },
                },
            )
            align = root / "align.json"
            merge = root / "merge.json"
            common_details = {
                "export_mode": "direct_db_research_6tier_v1",
                "input_contract_id": "INPUT",
                "alignment_contract_id": "ALIGN",
                "search_master_root": str(search),
                "alignment_db": str(db),
            }
            self.write(
                align,
                {
                    "g2p_model": "common_pron_mfa_r2_latest_jamo",
                    "details": common_details,
                },
            )
            self.write(
                merge,
                {
                    "g2p_model": "common_pron_mfa_r2_latest_jamo",
                    "details": {
                        **common_details,
                        "alignment_db_retained": True,
                        "direct_export_report": str(direct),
                    },
                },
            )
            temp = root / "temp.json"
            self.write(
                temp,
                {
                    "status": "direct_merge_completed_temp_retained_for_qc",
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": "ALIGN",
                    "search_master_root": str(search),
                },
            )
            sample = root / "sample.json"
            self.write(
                sample,
                {
                    "schema_version": "mfa_db_research_6tier_sample_equivalence.v1",
                    "status": "success",
                    "year": "2020",
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": "ALIGN",
                    "comparison_counts": {"compared": 5, "semantic_equal": 5},
                    "selection_counts": {"selected_sessions": 5},
                    "db": {"path": str(db)},
                },
            )
            review = root / "review.json"
            self.write(
                review,
                {
                    "schema_version": "mfa_r2_infrastructure_researcher_review.v1",
                    "status": "approved",
                    "allow_bulk_mfa": True,
                    "realization_judgment_performed": False,
                    "counts": {"speakers": 5},
                    "year_contracts": {
                        "2020": {
                            "alignment_contract_id": "ALIGN",
                            "lab_input_contract_id": "INPUT",
                            "database": str(db),
                        }
                    },
                },
            )
            result = validate_next_year_gate(
                prior_year="2020",
                next_year="2021",
                audit_report=audit,
                align_marker=align,
                merge_marker=merge,
                temp_contract=temp,
                sample_equivalence_report=sample,
                researcher_review_report=review,
                expected_search_master_root=search,
                expected_final_year_root=final,
                expected_pronunciation_mode="common_pron_mfa_r2_latest_jamo",
                report_path=root / "gate.json",
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["supported_export_mode"], "direct_db_research_6tier_v1")


if __name__ == "__main__":
    unittest.main()
