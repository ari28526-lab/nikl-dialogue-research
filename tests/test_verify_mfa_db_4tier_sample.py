import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from export_mfa_db_4tier import export_database  # noqa: E402
from verify_mfa_db_4tier_sample import verify_sample  # noqa: E402


class VerifyMfaDb4TierSampleTests(unittest.TestCase):
    def make_db(self, path: Path) -> None:
        con = sqlite3.connect(path)
        con.executescript(
            """
            CREATE TABLE file(
                id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT
            );
            CREATE TABLE sound_file(
                id INTEGER PRIMARY KEY, file_id INTEGER, duration FLOAT
            );
            CREATE TABLE utterance(
                id INTEGER PRIMARY KEY, file_id INTEGER, ignored BOOLEAN
            );
            CREATE TABLE word(id INTEGER PRIMARY KEY, word TEXT);
            CREATE TABLE phone(
                id INTEGER PRIMARY KEY, phone TEXT, phone_type TEXT
            );
            CREATE TABLE word_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER,
                begin FLOAT, end FLOAT, word_id INTEGER
            );
            CREATE TABLE phone_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER,
                begin FLOAT, end FLOAT, phone_id INTEGER
            );
            CREATE INDEX wi_utt ON word_interval(utterance_id);
            CREATE INDEX pi_utt ON phone_interval(utterance_id);
            """
        )
        con.executemany(
            "INSERT INTO file VALUES(?, ?, ?)",
            [(1, "S1.1", "S1"), (2, "S2.1", "S2")],
        )
        con.executemany(
            "INSERT INTO sound_file VALUES(?, ?, ?)",
            [(1, 1, 1.0), (2, 2, 1.2)],
        )
        con.executemany(
            "INSERT INTO utterance VALUES(?, ?, 0)",
            [(1, 1), (2, 2)],
        )
        con.execute("INSERT INTO word VALUES(1, '가')")
        con.execute(
            "INSERT INTO phone VALUES(1, 'k', 'non_silence')"
        )
        con.executemany(
            "INSERT INTO word_interval VALUES(?, ?, 0.1, ?, 1)",
            [(1, 1, 0.9), (2, 2, 1.1)],
        )
        con.executemany(
            "INSERT INTO phone_interval VALUES(?, ?, 0.1, ?, 1)",
            [(1, 1, 0.9), (2, 2, 1.1)],
        )
        con.commit()
        con.close()

    def make_search(self, root: Path) -> None:
        year_root = root / "2021"
        year_root.mkdir(parents=True)
        for session in ("S1", "S2"):
            with open(
                year_root / f"{session}.csv",
                "w",
                encoding="utf-8",
                newline="",
            ) as stream:
                writer = csv.writer(stream)
                writer.writerow(["utt_id", "form"])
                writer.writerow([f"{session}.1", "가"])

    def test_reexports_distinct_sessions_and_matches_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            search = root / "search"
            final = root / "final"
            scratch = root / "scratch"
            self.make_db(db)
            self.make_search(search)
            with patch(
                "export_mfa_db_4tier.morpheme_tier",
                return_value=[(0.1, 0.9, "가")],
            ):
                exported = export_database(
                    db_path=db,
                    year="2021",
                    search_master_root=search,
                    output_root=final,
                )
                report = verify_sample(
                    db_path=db,
                    year="2021",
                    search_master_root=search,
                    final_root=final,
                    scratch_root=scratch,
                    report_path=root / "report.json",
                    sample_csv_path=root / "sample.csv",
                    sample_size=2,
                )
            self.assertEqual(exported["status"], "success")
            self.assertEqual(report["status"], "success")
            self.assertEqual(
                report["selection_counts"]["selected_sessions"], 2
            )
            self.assertEqual(
                report["comparison_counts"]["tier_equal"], 2
            )
            self.assertEqual(
                report["comparison_counts"]["byte_equal"], 2
            )

    def test_refuses_stale_scratch_textgrid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            search = root / "search"
            final = root / "final"
            scratch = root / "scratch"
            self.make_db(db)
            self.make_search(search)
            (final / "2021").mkdir(parents=True)
            scratch.mkdir()
            (scratch / "stale.TextGrid").write_text(
                "stale", encoding="utf-8"
            )
            with self.assertRaises(FileExistsError):
                verify_sample(
                    db_path=db,
                    year="2021",
                    search_master_root=search,
                    final_root=final,
                    scratch_root=scratch,
                    report_path=root / "report.json",
                    sample_csv_path=root / "sample.csv",
                    sample_size=2,
                )


if __name__ == "__main__":
    unittest.main()
