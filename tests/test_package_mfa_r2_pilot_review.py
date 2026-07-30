import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from package_mfa_r2_pilot_review import (  # noqa: E402
    BUNDLE_SCHEMA_VERSION,
    package_review,
    validate_machine_gates,
)


class FlatPilotReviewBundleTests(unittest.TestCase):
    def test_full_six_year_gate_requires_and_accepts_cross_year_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            rows = []
            for year in (
                "2020", "2021", "2022", "2023", "2024", "2025"
            ):
                rows.append({"year": year})
                database = run / "temp" / year / f"{year}.db"
                database.parent.mkdir(parents=True, exist_ok=True)
                database.write_bytes(b"sqlite")
                sample = run / "logs" / f"{year}.db_tg_sample.json"
                sample.parent.mkdir(parents=True, exist_ok=True)
                sample.write_text(
                    json.dumps(
                        {
                            "status": "success",
                            "year": year,
                            "db": {"path": str(database)},
                            "comparison_counts": {
                                "compared": 5,
                                "tier_equal": 5,
                            },
                            "selection_counts": {
                                "selected_sessions": 5,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                marker = (
                    run / "state" / f"{year}.machine_done.json"
                )
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(
                    json.dumps(
                        {
                            "year": year,
                            "stage": "machine_qc",
                            "status": "passed",
                            "pronunciation_mode": (
                                "common_pron_mfa_r2_latest_jamo"
                            ),
                            "inline_g2p_used": False,
                            "alignment_contract_id": f"align-{year}",
                            "lab_input_contract_id": "lab",
                            "database": str(database),
                            "db_textgrid_sample_report": str(sample),
                            "researcher_review_status": "pending",
                            "realization_judgment_performed": False,
                            "textgrids": 1,
                        }
                    ),
                    encoding="utf-8",
                )
            cross = run / "logs" / "cross_year_method_audit.json"
            cross.write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "mfa_cross_year_method_consistency.v1"
                        ),
                        "status": "passed",
                        "gate": {
                            "years_expected": 6,
                            "years_observed": 6,
                            "cross_year_method_mismatches": 0,
                            "same_phone_generation_standard": True,
                            "same_allowed_phone_inventory": True,
                            "observed_phones_outside_allowed": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            evidence = validate_machine_gates(run, rows)

            self.assertEqual(len(evidence["machine_markers"]), 6)
            self.assertIsNotNone(
                evidence["cross_year_method_audit"]
            )

    def test_packages_one_flat_folder_without_realization_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            output = root / "review"
            utt = "SDRW2000000001.1.1.1"
            session = "SDRW2000000001"
            wav = run / "corpus" / "2020" / session / f"{utt}.wav"
            lab = wav.with_suffix(".lab")
            tg = (
                run / "textgrid_4tier" / "2020" / session
                / f"{utt}.TextGrid"
            )
            search = (
                run / "search_master" / "2020" / f"{session}.csv"
            )
            for path in (wav, lab, tg, search):
                path.parent.mkdir(parents=True, exist_ok=True)
            wav.write_bytes(b"RIFFdata")
            lab.write_text("안녕", encoding="utf-8")
            tg.write_text("File type = \"ooTextFile\"", encoding="utf-8")
            with search.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["utt_id", "form"])
                writer.writeheader()
                writer.writerow({"utt_id": utt, "form": "안녕"})
            manifest_fields = [
                "year", "utt_id", "speaker_id", "session_id",
                "corpus_wav_relpath", "corpus_lab_relpath",
            ]
            with (run / "selection_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as f:
                writer = csv.DictWriter(f, fieldnames=manifest_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "year": "2020",
                        "utt_id": utt,
                        "speaker_id": "SPK1",
                        "session_id": session,
                        "corpus_wav_relpath": wav.relative_to(run).as_posix(),
                        "corpus_lab_relpath": lab.relative_to(run).as_posix(),
                    }
                )
            marker = run / "state" / "2020.machine_done.json"
            marker.parent.mkdir(parents=True)
            database = run / "temp" / "2020" / "2020.db"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"sqlite")
            sample_report = run / "logs" / "2020.db_tg_sample.json"
            sample_report.parent.mkdir(parents=True)
            sample_report.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "year": "2020",
                        "db": {"path": str(database)},
                        "comparison_counts": {
                            "compared": 5,
                            "tier_equal": 5,
                        },
                        "selection_counts": {
                            "selected_sessions": 5,
                        },
                    }
                ),
                encoding="utf-8",
            )
            marker.write_text(
                json.dumps(
                    {
                        "year": "2020",
                        "stage": "machine_qc",
                        "status": "passed",
                        "pronunciation_mode": (
                            "common_pron_mfa_r2_latest_jamo"
                        ),
                        "inline_g2p_used": False,
                        "alignment_contract_id": "align-2020",
                        "lab_input_contract_id": "lab-2020",
                        "database": str(database),
                        "db_textgrid_sample_report": str(sample_report),
                        "researcher_review_status": "pending",
                        "realization_judgment_performed": False,
                        "textgrids": 1,
                    }
                ),
                encoding="utf-8",
            )

            report = package_review(run, output)

            self.assertTrue(report["flat_layout"])
            self.assertEqual(
                report["schema_version"], BUNDLE_SCHEMA_VERSION
            )
            self.assertFalse(report["realization_judgment_performed"])
            self.assertFalse(any(path.is_dir() for path in output.iterdir()))
            self.assertTrue((output / f"2020__{utt}.TextGrid").is_file())
            self.assertTrue((output / "REVIEW.csv").is_file())
            self.assertEqual(
                report["machine_gate_evidence"]["years"], ["2020"]
            )
            for record in report["files"]:
                self.assertIn("relative_path", record)
                self.assertNotIn("path", record)
            for record in report["supporting_files"].values():
                self.assertIn("relative_path", record)
                self.assertNotIn("path", record)

    def test_refuses_packaging_without_machine_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            run.mkdir()
            with (run / "selection_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "year",
                        "utt_id",
                        "speaker_id",
                        "session_id",
                        "corpus_wav_relpath",
                        "corpus_lab_relpath",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "year": "2020",
                        "utt_id": "x",
                        "speaker_id": "s",
                        "session_id": "d",
                        "corpus_wav_relpath": "missing.wav",
                        "corpus_lab_relpath": "missing.lab",
                    }
                )
            with self.assertRaises(FileNotFoundError):
                package_review(run, root / "review")


if __name__ == "__main__":
    unittest.main()
