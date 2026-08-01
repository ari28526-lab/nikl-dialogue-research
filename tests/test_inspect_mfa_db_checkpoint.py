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
                report["analysis_ready_status"],
                "requires_export_and_independent_qc",
            )


if __name__ == "__main__":
    unittest.main()
