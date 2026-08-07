import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from prepare_mfa_exclusion_review import prepare_review  # noqa: E402


class PrepareMfaExclusionReviewTests(unittest.TestCase):
    def test_candidates_are_pending_and_quarantine_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            (search / "2020" / "S1.csv").write_text(
                "utt_id,form,pron_reference_form\nU1,가,가\n",
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2020",
                                "issue_inventory": [
                                    {
                                        "utt_id": "U1",
                                        "issue": "morph_source_missing",
                                        "morph_disposition": (
                                            "exclude_source_audio_unusable"
                                        ),
                                        "path": "old",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            quarantine = root / "quarantine.csv"
            quarantine.write_text(
                "name,quarantine_path\nU1.wav,D:/q/U1.wav\n",
                encoding="utf-8",
            )
            output = root / "review.csv"
            result = prepare_review(
                audit_report=audit,
                year="2020",
                search_master_root=search,
                output_csv=output,
                output_report=root / "report.json",
                quarantine_log=quarantine,
                input_contract_id="INPUT_TEST",
            )
            self.assertEqual(result["candidate_count"], 1)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["decision"], "pending")
            self.assertEqual(row["reason_code"], "quarantined_wav")
            self.assertEqual(row["exclusion_scope"], "alignment_and_analysis")

    def test_unpaired_read_only_bad_wav_is_not_an_mfa_exclusion_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2021").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {"years": [{"year": "2021", "issue_inventory": []}]}
                ),
                encoding="utf-8",
            )
            inventory = root / "bad_wavs.csv"
            inventory.write_text(
                "name,lab_present,quarantine_path\n"
                "NOT_INPUT.wav,false,D:/q/NOT_INPUT.wav\n",
                encoding="utf-8",
            )
            output = root / "review.csv"
            result = prepare_review(
                audit_report=audit,
                year="2021",
                search_master_root=search,
                output_csv=output,
                output_report=root / "report.json",
                quarantine_log=inventory,
                input_contract_id="INPUT_TEST",
            )
            self.assertEqual(result["candidate_count"], 0)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv.DictReader(stream)), [])

    def test_audio_plan_turns_only_unresolved_target_into_pending_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            (search / "2020" / "S1.csv").write_text(
                "utt_id,form,pron_reference_form\nU1,가,가\n",
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2020",
                                "issue_inventory": [
                                    {
                                        "utt_id": "U1",
                                        "issue": "duration_wav_missing",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            plan = root / "plan.csv"
            plan.write_text(
                "year,target_utt_id,status\n"
                "2020,U1,target_unresolved\n",
                encoding="utf-8",
            )
            output = root / "review.csv"
            result = prepare_review(
                audit_report=audit,
                year="2020",
                search_master_root=search,
                output_csv=output,
                output_report=root / "report.json",
                input_contract_id="INPUT_TEST",
                audio_recovery_plan=plan,
            )
            self.assertEqual(result["candidate_count"], 1)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["decision"], "pending")
            self.assertEqual(row["reason_code"], "audio_pairing_unresolved")
            self.assertEqual(row["notes"], "target_unresolved")

    def test_uncovered_audio_issue_blocks_review_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            (search / "2020" / "S1.csv").write_text(
                "utt_id,form,pron_reference_form\nU1,가,가\n",
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2020",
                                "issue_inventory": [
                                    {
                                        "utt_id": "U1",
                                        "issue": "duration_residual_mismatch",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            plan = root / "plan.csv"
            plan.write_text(
                "year,target_utt_id,status\n"
                "2020,U1,remap_high_confidence\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "복구가 완료되지 않음"):
                prepare_review(
                    audit_report=audit,
                    year="2020",
                    search_master_root=search,
                    output_csv=root / "review.csv",
                    output_report=root / "report.json",
                    input_contract_id="INPUT_TEST",
                    audio_recovery_plan=plan,
                )

    def test_zero_csv_duration_becomes_direct_pending_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2021").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2021",
                                "issue_inventory": [
                                    {
                                        "utt_id": "U_ZERO",
                                        "issue": "csv_duration_invalid",
                                        "detail": "0.0",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output = root / "review.csv"
            result = prepare_review(
                audit_report=audit,
                year="2021",
                search_master_root=search,
                output_csv=output,
                output_report=root / "report.json",
                input_contract_id="INPUT_TEST",
            )
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["direct_audio_exclusion_count"], 1)
            self.assertEqual(
                result["uncovered_audio_pairing_issue_count"], 0
            )
            with output.open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["utt_id"], "U_ZERO")
            self.assertEqual(row["reason_code"], "audio_pairing_unresolved")
            self.assertEqual(row["exclusion_scope"], "alignment_and_analysis")
            self.assertEqual(row["decision"], "pending")

    def test_empty_unresolved_lab_is_candidate_but_partial_lab_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            (search / "2020" / "S1.csv").write_text(
                "utt_id,form,pron_reference_form\nU1,가,가\n",
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {"years": [{"year": "2020", "issue_inventory": []}]}
                ),
                encoding="utf-8",
            )
            inventory = root / "unresolved.csv"
            inventory.write_text(
                "year,utt_id,pron_reference_status,lab_text\n"
                "2020,U_EMPTY,unresolved_symbol,\n"
                "2020,U_PARTIAL,unresolved_symbol,가 나\n",
                encoding="utf-8",
            )
            lab_report = root / "lab.json"
            lab_report.write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "year": "2020",
                        "input_contract_id": "INPUT_TEST",
                        "pron_reference_unresolved": 2,
                        "empty_reference_form": 1,
                        "unresolved_symbol_inventory": str(inventory),
                    }
                ),
                encoding="utf-8",
            )
            output = root / "review.csv"
            result = prepare_review(
                audit_report=audit,
                year="2020",
                search_master_root=search,
                output_csv=output,
                output_report=root / "report.json",
                input_contract_id="INPUT_TEST",
                lab_report=lab_report,
            )
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["unresolved_symbol_count"], 2)
            self.assertEqual(
                result["partial_lab_unresolved_symbol_count"], 1
            )
            self.assertEqual(
                result["empty_reference_unresolved_symbol_count"], 1
            )
            with output.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["utt_id"] for row in rows], ["U_EMPTY"])
            self.assertEqual(
                rows[0]["reason_code"],
                "empty_reference_unresolved_symbol",
            )
            self.assertEqual(rows[0]["decision"], "pending")

    def test_lab_report_inventory_count_mismatch_blocks_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success", "run_id": "T"}),
                encoding="utf-8",
            )
            (search / "2020" / "S1.csv").write_text(
                "utt_id,form,pron_reference_form\nU1,가,가\n",
                encoding="utf-8",
            )
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {"years": [{"year": "2020", "issue_inventory": []}]}
                ),
                encoding="utf-8",
            )
            inventory = root / "unresolved.csv"
            inventory.write_text(
                "year,utt_id,pron_reference_status,lab_text\n"
                "2020,U_EMPTY,unresolved_symbol,\n",
                encoding="utf-8",
            )
            lab_report = root / "lab.json"
            lab_report.write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "year": "2020",
                        "input_contract_id": "INPUT_TEST",
                        "pron_reference_unresolved": 2,
                        "empty_reference_form": 1,
                        "unresolved_symbol_inventory": str(inventory),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "unresolved count"):
                prepare_review(
                    audit_report=audit,
                    year="2020",
                    search_master_root=search,
                    output_csv=root / "review.csv",
                    output_report=root / "report.json",
                    input_contract_id="INPUT_TEST",
                    lab_report=lab_report,
                )


if __name__ == "__main__":
    unittest.main()
