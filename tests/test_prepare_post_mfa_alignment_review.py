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
    def make_db(self, path: Path) -> None:
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
        connection.executemany(
            "INSERT INTO file VALUES(?, ?, ?)",
            [(1, "U1", "S1"), (2, "U2", "S1")],
        )
        connection.executemany(
            "INSERT INTO utterance VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 0.0, 1.0, 100, "정상", 1, -10.0, 0),
                (2, 2, 0.0, 1.2, 120, "실패", 2, None, 0),
            ],
        )
        connection.execute("INSERT INTO word_interval VALUES(1, 1)")
        connection.execute("INSERT INTO phone_interval VALUES(1, 1)")
        connection.commit()
        connection.close()

    def make_contract(self, root: Path) -> Path:
        review = root / "approved.csv"
        with review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "year": "2020",
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
            year="2020",
            input_contract_id="INPUT1",
            approved_by="researcher",
            approved_at="2026-08-02T12:00:00+09:00",
        )
        return contract

    def make_report(self, path: Path, missing_id: str = "U2") -> None:
        path.write_text(
            json.dumps(
                {
                    "exact_id_reconciliation": {
                        "inventories": {
                            "unknown_active_lab_without_alignment": [missing_id]
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    def make_audio_lab(self, root: Path) -> None:
        session = root / "2020" / "S1"
        session.mkdir(parents=True)
        for utt_id, text in [("U1", "정상"), ("U2", "실패")]:
            (session / f"{utt_id}.wav").write_bytes(b"RIFFfixture")
            (session / f"{utt_id}.lab").write_text(text, encoding="utf-8")

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
            self.assertEqual(decisions[0]["decision"], "pending")
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


if __name__ == "__main__":
    unittest.main()
