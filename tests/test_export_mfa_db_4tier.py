import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from compare_textgrid_tiers import compare_trees  # noqa: E402
from export_mfa_db_4tier import export_database  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class ExportMfaDb4TierTests(unittest.TestCase):
    def make_db(self, path: Path):
        con = sqlite3.connect(path)
        con.executescript(
            """
            CREATE TABLE file(id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT);
            CREATE TABLE sound_file(id INTEGER PRIMARY KEY, file_id INTEGER, duration FLOAT);
            CREATE TABLE utterance(
                id INTEGER PRIMARY KEY, file_id INTEGER, ignored BOOLEAN
            );
            CREATE TABLE word(
                id INTEGER PRIMARY KEY,
                word TEXT,
                word_type TEXT DEFAULT 'speech'
            );
            CREATE TABLE pronunciation(
                id INTEGER PRIMARY KEY,
                pronunciation TEXT,
                word_id INTEGER
            );
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
            "INSERT INTO word(id, word) VALUES(?, ?)",
            [(1, "가"), (2, "<eps>")],
        )
        con.execute(
            "INSERT INTO pronunciation VALUES(1, 'k', 1)"
        )
        con.executemany(
            "INSERT INTO phone VALUES(?, ?, ?)",
            [(1, "k", "non_silence"), (2, "sil", "silence")],
        )
        con.executemany(
            "INSERT INTO word_interval VALUES(?, 1, ?, ?, ?)",
            [(1, 0.0, 0.8, 1), (2, 0.8, 1.0, 2)],
        )
        con.executemany(
            "INSERT INTO phone_interval VALUES(?, 1, ?, ?, ?)",
            [(1, 0.0, 0.8, 1), (2, 0.8, 1.0, 2)],
        )
        con.commit()
        con.close()

    def test_exports_valid_four_tiers_and_tree_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            self.make_db(db)
            search = root / "search" / "2021"
            search.mkdir(parents=True)
            with open(search / "S1.csv", "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["utt_id", "form"])
                writer.writerow(["S1.1", "가"])
            output = root / "out"
            with patch(
                "export_mfa_db_4tier.morpheme_tier",
                return_value=[(0.0, 0.8, "가")],
            ):
                report = export_database(
                    db_path=db,
                    year="2021",
                    search_master_root=search.parent,
                    output_root=output,
                )
            self.assertEqual(report["status"], "success")
            path = output / "2021" / "S1" / "S1.1.TextGrid"
            duration, tiers = parse_mfa_textgrid(path)
            self.assertEqual(duration, 1.0)
            self.assertEqual(
                list(tiers), ["words", "phones", "morphemes", "utterance"]
            )
            self.assertEqual(tiers["words"][-1], (0.8, 1.0, ""))
            self.assertEqual(tiers["phones"][-1], (0.8, 1.0, ""))
            comparison = compare_trees(output, output)
            self.assertEqual(comparison["status"], "identical")

    def test_spn_pronunciation_blocks_export_before_textgrid_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            self.make_db(db)
            connection = sqlite3.connect(db)
            connection.execute(
                "UPDATE pronunciation SET pronunciation='spn'"
            )
            connection.commit()
            connection.close()
            output = root / "out"
            report = export_database(
                db_path=db,
                year="2021",
                search_master_root=root / "search",
                output_root=output,
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(
                report["counts"]["spn_pronunciations"], 1
            )
            self.assertEqual(
                report["analysis_ready_status"],
                "blocked_spn_pronunciations",
            )
            self.assertFalse(output.exists())

    def test_missing_morpheme_tier_preserves_export_but_blocks_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            self.make_db(db)
            search = root / "search" / "2021"
            search.mkdir(parents=True)
            with open(search / "S1.csv", "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["utt_id", "form"])
                writer.writerow(["S1.1", "가"])
            with patch(
                "export_mfa_db_4tier.morpheme_tier",
                return_value=None,
            ):
                report = export_database(
                    db_path=db,
                    year="2021",
                    search_master_root=search.parent,
                    output_root=root / "out",
                )
            self.assertEqual(report["status"], "success")
            self.assertEqual(
                report["analysis_ready_status"], "blocked_morphology"
            )
            self.assertFalse(report["morphology_complete"])
            self.assertEqual(report["counts"]["morpheme_tier_missing"], 1)
            self.assertEqual(
                report["morpheme_tier_missing_inventory"], ["S1.1"]
            )

            # Partial resume에서도 기존 4-tier의 구조 valid만 보고 누락을
            # 0건으로 오인하지 않는다.
            with patch(
                "export_mfa_db_4tier.morpheme_tier",
                return_value=None,
            ):
                resumed = export_database(
                    db_path=db,
                    year="2021",
                    search_master_root=search.parent,
                    output_root=root / "out",
                )
            self.assertEqual(resumed["counts"]["validated_existing"], 1)
            self.assertEqual(
                resumed["counts"]["morpheme_tier_missing"], 1
            )
            self.assertEqual(
                resumed["analysis_ready_status"], "blocked_morphology"
            )

    def test_failed_export_records_utterance_and_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "corpus.db"
            self.make_db(db)
            search = root / "search" / "2021"
            search.mkdir(parents=True)
            with open(
                search / "S1.csv",
                "w",
                encoding="utf-8",
                newline="",
            ) as stream:
                writer = csv.writer(stream)
                writer.writerow(["utt_id", "form"])
                writer.writerow(["S1.1", "가"])
            with (
                patch(
                    "export_mfa_db_4tier.morpheme_tier",
                    return_value=[(0.0, 0.8, "가")],
                ),
                patch(
                    "export_mfa_db_4tier.write_4tier",
                    side_effect=RuntimeError("synthetic failure"),
                ),
            ):
                report = export_database(
                    db_path=db,
                    year="2021",
                    search_master_root=search.parent,
                    output_root=root / "out",
                )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["counts"]["failed"], 1)
            self.assertEqual(report["failed_examples"][0]["utt_id"], "S1.1")
            self.assertIn(
                "RuntimeError: synthetic failure",
                report["failed_examples"][0]["error"],
            )


if __name__ == "__main__":
    unittest.main()
