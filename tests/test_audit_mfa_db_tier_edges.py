from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from audit_mfa_db_tier_edges import audit  # noqa: E402


class AuditMfaDbTierEdgesTests(unittest.TestCase):
    def test_counts_equal_and_mismatched_outer_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fixture.db"
            connection = sqlite3.connect(db)
            connection.executescript(
                """
                CREATE TABLE file(id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE sound_file(file_id INTEGER, duration REAL);
                CREATE TABLE utterance(
                    id INTEGER PRIMARY KEY, file_id INTEGER, ignored INTEGER
                );
                CREATE TABLE word(id INTEGER PRIMARY KEY, word TEXT);
                CREATE TABLE phone(
                    id INTEGER PRIMARY KEY, phone TEXT, phone_type TEXT
                );
                CREATE TABLE word_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER,
                    begin REAL, end REAL, word_id INTEGER
                );
                CREATE TABLE phone_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER,
                    begin REAL, end REAL, phone_id INTEGER
                );
                INSERT INTO word VALUES (1, 'word');
                INSERT INTO phone VALUES
                    (1, 'p', 'non_silence'), (2, 'sil', 'silence');
                INSERT INTO file VALUES (1, 'U1'), (2, 'U2');
                INSERT INTO sound_file VALUES (1, 1.0), (2, 1.0);
                INSERT INTO utterance VALUES (1, 1, 0), (2, 2, 0);
                INSERT INTO word_interval VALUES
                    (1, 1, 0.1, 0.9, 1),
                    (2, 2, 0.0, 1.0, 1);
                INSERT INTO phone_interval VALUES
                    (1, 1, 0.1, 0.9, 1),
                    (2, 2, 0.01, 1.0, 1);
                """
            )
            connection.commit()
            connection.close()

            report = audit(db)

            self.assertEqual(report["status"], "success")
            self.assertEqual(report["counts"]["aligned_utterances"], 2)
            self.assertEqual(
                report["counts"]["word_phone_outer_edges_equal"], 1
            )
            self.assertEqual(
                report["counts"]["word_phone_outer_edge_mismatch"], 1
            )
            self.assertEqual(report["counts"]["word_natural_blank_both"], 1)


if __name__ == "__main__":
    unittest.main()
