import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from inspect_mfa_db_checkpoint import inspect_database  # noqa: E402


class InspectMfaDbCheckpointTests(unittest.TestCase):
    def test_computation_checkpoint_is_not_analysis_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "2021.db"
            con = sqlite3.connect(db)
            con.executescript(
                """
                CREATE TABLE file(id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE utterance(
                    id INTEGER PRIMARY KEY, file_id INTEGER, ignored BOOLEAN
                );
                CREATE TABLE word_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER
                );
                CREATE TABLE phone(id INTEGER PRIMARY KEY, phone TEXT);
                CREATE TABLE phone_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER,
                    phone_id INTEGER
                );
                INSERT INTO file VALUES(1, 'U1');
                INSERT INTO utterance VALUES(1, 1, 0);
                INSERT INTO word_interval VALUES(1, 1);
                INSERT INTO phone VALUES(1, 'spn');
                INSERT INTO phone_interval VALUES(1, 1, 1);
                """
            )
            con.commit()
            con.close()
            report = inspect_database(db, "2021")
            self.assertEqual(report["status"], "success")
            self.assertEqual(report["counts"]["spn_intervals"], 1)
            self.assertEqual(
                report["counts"]["utterances_with_words_and_phones"], 1
            )
            self.assertEqual(report["counts"]["missing_alignment_utterances"], 0)
            self.assertEqual(
                report["analysis_ready_status"],
                "requires_export_and_independent_qc",
            )

    def test_missing_alignment_count_is_exact_union(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "2020.db"
            con = sqlite3.connect(db)
            con.executescript(
                """
                CREATE TABLE file(id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE utterance(
                    id INTEGER PRIMARY KEY, file_id INTEGER, ignored BOOLEAN
                );
                CREATE TABLE word_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER
                );
                CREATE TABLE phone(id INTEGER PRIMARY KEY, phone TEXT);
                CREATE TABLE phone_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER,
                    phone_id INTEGER
                );
                INSERT INTO file VALUES(1, 'ALIGNED');
                INSERT INTO file VALUES(2, 'WORD_ONLY');
                INSERT INTO file VALUES(3, 'PHONE_ONLY');
                INSERT INTO utterance VALUES(1, 1, 0);
                INSERT INTO utterance VALUES(2, 2, 0);
                INSERT INTO utterance VALUES(3, 3, 0);
                INSERT INTO word_interval VALUES(1, 1);
                INSERT INTO word_interval VALUES(2, 2);
                INSERT INTO phone VALUES(1, 'a');
                INSERT INTO phone_interval VALUES(1, 1, 1);
                INSERT INTO phone_interval VALUES(2, 3, 1);
                """
            )
            con.commit()
            con.close()

            report = inspect_database(db, "2020")
            self.assertEqual(report["counts"]["source_utterances"], 3)
            self.assertEqual(
                report["counts"]["utterances_with_words_and_phones"], 1
            )
            self.assertEqual(report["counts"]["missing_alignment_utterances"], 2)
            self.assertEqual(report["coverage_pct"], 33.3333)
            self.assertEqual(
                report["missing_alignment_examples"],
                ["PHONE_ONLY", "WORD_ONLY"],
            )


if __name__ == "__main__":
    unittest.main()
