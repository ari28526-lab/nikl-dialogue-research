import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from mfa_exclusion_contract import REVIEW_FIELDS, build_contract  # noqa: E402
from pipeline_common import sha256_file  # noqa: E402
from prepare_post_mfa_alignment_review import prepare_review  # noqa: E402


class PreparePostMfaAlignmentReviewTests(unittest.TestCase):
    def make_db(
        self, path: Path, *, include_feature_failure: bool = False
    ) -> None:
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE file(
                id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT
            );
            CREATE TABLE utterance(
                id INTEGER PRIMARY KEY, file_id INTEGER, begin FLOAT,
                end FLOAT, num_frames INTEGER, normalized_text TEXT,
                job_id INTEGER, alignment_log_likelihood FLOAT,
                ignored BOOLEAN
            );
            CREATE TABLE word_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER
            );
            CREATE TABLE phone_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER
            );
            """
        )
        files = [(1, "U1", "S1"), (2, "U2", "S1")]
        utterances = [
            (1, 1, 0.0, 1.0, 100, "정상", 1, -10.0, 0),
            (2, 2, 0.0, 1.2, 120, "실패", 2, None, 0),
        ]
        if include_feature_failure:
            files.append((3, "U3", "S2"))
            utterances.append(
                (3, 3, 0.0, 0.03, None, "초단시간", None, None, 1)
            )
        connection.executemany("INSERT INTO file VALUES(?, ?, ?)", files)
        connection.executemany(
            "INSERT INTO utterance VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            utterances,
        )
        connection.execute("INSERT INTO word_interval VALUES(1, 1)")
        connection.execute("INSERT INTO phone_interval VALUES(1, 1)")
        connection.commit()
        connection.close()

    def make_contract(self, root: Path, *, year: str = "2020") -> Path:
        review = root / "approved.csv"
        with review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "year": year,
                    "input_contract_id": "INPUT1",
                    "utt_id": "OLD1",
                    "reason_code": "audio_pairing_unresolved",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": "fixture",
                    "decision": "approved",
                    "notes": "existing upstream exclusion",
                }
            )
        contract = root / "approved.json"
        build_contract(
            review_csv=review,
            output=contract,
            year=year,
            input_contract_id="INPUT1",
            approved_by="researcher",
            approved_at="2026-08-02T12:00:00+09:00",
        )
        return contract

    def make_report(
        self, path: Path, missing_id: str | list[str] = "U2"
    ) -> None:
        missing_ids = (
            [missing_id] if isinstance(missing_id, str) else missing_id
        )
        path.write_text(
            json.dumps(
                {
                    "exact_id_reconciliation": {
                        "inventories": {
                            "unknown_active_lab_without_alignment": missing_ids
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    def make_audio_lab(
        self,
        root: Path,
        *,
        year: str = "2020",
        include_feature_failure: bool = False,
    ) -> None:
        session = root / year / "S1"
        session.mkdir(parents=True)
        for utt_id, text in [("U1", "정상"), ("U2", "실패")]:
            (session / f"{utt_id}.wav").write_bytes(b"RIFFfixture")
            (session / f"{utt_id}.lab").write_text(text, encoding="utf-8")
        if include_feature_failure:
            feature_session = root / year / "S2"
            feature_session.mkdir(parents=True)
            (feature_session / "U3.wav").write_bytes(b"RIFFshort")
            (feature_session / "U3.lab").write_text(
                "초단시간", encoding="utf-8"
            )

    def test_creates_pending_review_without_changing_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2020.db"
            report = root / "report.json"
            audio_lab = root / "corpus"
            output = root / "review"
            self.make_db(db)
            self.make_report(report)
            contract = self.make_contract(root)
            self.make_audio_lab(audio_lab)
            before = sha256_file(db)

            summary = prepare_review(
                db_path=db,
                year="2020",
                export_report=report,
                approved_exclusions_contract=contract,
                lab_root=audio_lab,
                output_root=output,
                copy_sample_files=True,
            )

            self.assertEqual(sha256_file(db), before)
            self.assertEqual(summary["candidate_count"], 1)
            self.assertEqual(summary["existing_approved_exclusion_count"], 1)
            self.assertFalse(summary["auto_approval_performed"])
            self.assertFalse(summary["full_year_mfa_rerun_required"])
            with (output / "02_RESEARCHER_DECISIONS.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                decisions = list(csv.DictReader(stream))
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0]["utt_id"], "U2")
            self.assertEqual(
                decisions[0]["reason_code"], "mfa_alignment_missing"
            )
            self.assertEqual(decisions[0]["decision"], "pending")
            with (output / "04_RESEARCHER_APPROVAL.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                approval_rows = list(csv.DictReader(stream))
            self.assertEqual(approval_rows, decisions)
            self.assertTrue((output / "03_AUDIO_LAB_PILOT" / "U1.wav").is_file())
            self.assertTrue((output / "03_AUDIO_LAB_PILOT" / "U2.wav").is_file())

    def test_rejects_report_database_inventory_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2020.db"
            report = root / "report.json"
            self.make_db(db)
            self.make_report(report, missing_id="OTHER")
            contract = self.make_contract(root)
            with self.assertRaisesRegex(RuntimeError, "DB/report"):
                prepare_review(
                    db_path=db,
                    year="2020",
                    export_report=report,
                    approved_exclusions_contract=contract,
                    lab_root=root / "corpus",
                    output_root=root / "review",
                    copy_sample_files=False,
                )
            self.assertFalse((root / "review").exists())

    def test_classifies_ignored_active_lab_as_feature_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2021.db"
            report = root / "report.json"
            audio_lab = root / "corpus"
            output = root / "review"
            self.make_db(db, include_feature_failure=True)
            self.make_report(report, missing_id=["U2", "U3"])
            contract = self.make_contract(root, year="2021")
            self.make_audio_lab(
                audio_lab, year="2021", include_feature_failure=True
            )

            summary = prepare_review(
                db_path=db,
                year="2021",
                export_report=report,
                approved_exclusions_contract=contract,
                lab_root=audio_lab,
                output_root=output,
                copy_sample_files=False,
            )

            self.assertEqual(summary["candidate_count"], 2)
            self.assertEqual(
                summary["reason_counts"],
                {
                    "mfa_alignment_missing": 1,
                    "mfa_feature_generation_failed": 1,
                },
            )
            with (output / "02_RESEARCHER_DECISIONS.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                decisions = {
                    row["utt_id"]: row for row in csv.DictReader(stream)
                }
            self.assertEqual(
                decisions["U2"]["reason_code"], "mfa_alignment_missing"
            )
            self.assertEqual(
                decisions["U3"]["reason_code"],
                "mfa_feature_generation_failed",
            )
            self.assertTrue(
                all(row["decision"] == "pending" for row in decisions.values())
            )
            with (output / "03_AUDIO_LAB_PILOT_REVIEW.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                pilot_rows = list(csv.DictReader(stream))
            self.assertTrue(
                {
                    "mfa_alignment_missing",
                    "mfa_feature_generation_failed",
                }.issubset({row["reason_code"] for row in pilot_rows})
            )


if __name__ == "__main__":
    unittest.main()
