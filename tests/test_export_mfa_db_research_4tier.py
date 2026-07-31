import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from export_mfa_db_research_4tier import export_database  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class ExportMfaDbResearch4TierTests(unittest.TestCase):
    def make_db(self, path: Path):
        con = sqlite3.connect(path)
        con.executescript(
            """
            CREATE TABLE file(id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT);
            CREATE TABLE sound_file(id INTEGER PRIMARY KEY, file_id INTEGER, duration FLOAT);
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
            """
        )
        con.execute("INSERT INTO file VALUES(1, 'S1.1', 'S1')")
        con.execute("INSERT INTO sound_file VALUES(1, 1, 1.0)")
        con.execute("INSERT INTO utterance VALUES(1, 1, 0)")
        con.executemany(
            "INSERT INTO word VALUES(?, ?)",
            [(1, "가"), (2, "<eps>")],
        )
        con.executemany(
            "INSERT INTO phone VALUES(?, ?, ?)",
            [(1, "k", "non_silence"), (2, "sil", "silence")],
        )
        con.executemany(
            "INSERT INTO word_interval VALUES(?, 1, ?, ?, ?)",
            [(1, 0.1, 0.8, 1), (2, 0.8, 1.0, 2)],
        )
        con.executemany(
            "INSERT INTO phone_interval VALUES(?, 1, ?, ?, ?)",
            [(1, 0.1, 0.8, 1), (2, 0.8, 1.0, 2)],
        )
        con.commit()
        con.close()

    def write_search(self, root: Path, *, include=True):
        path = root / "2021" / "S1.csv"
        path.parent.mkdir(parents=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "utt_id",
                    "form",
                    "form_roman",
                    "tagged",
                    "align_warn",
                ],
            )
            writer.writeheader()
            if include:
                writer.writerow(
                    {
                        "utt_id": "S1.1",
                        "form": "가",
                        "form_roman": "G A",
                        "tagged": "가/NNG",
                        "align_warn": "",
                    }
                )

    def test_exports_new_contract_without_legacy_morpheme_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            self.make_db(db)
            search = root / "search"
            self.write_search(search)
            output = root / "out"
            report = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
            )
            self.assertEqual(report["status"], "success")
            path = output / "2021" / "S1" / "S1.1.TextGrid"
            _duration, tiers = parse_mfa_textgrid(path)
            self.assertEqual(
                list(tiers),
                ["words", "phones_mfa", "utterance", "utterance_search"],
            )
            self.assertEqual(report["counts"]["spn_intervals"], 0)
            self.assertEqual(report["coverage_pct"], 100.0)

    def test_missing_search_row_is_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            self.make_db(db)
            search = root / "search"
            self.write_search(search, include=False)
            report = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=root / "out",
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["counts"]["search_row_missing"], 1)
            self.assertEqual(
                report["search_row_missing_inventory"], ["S1.1"]
            )


if __name__ == "__main__":
    unittest.main()
