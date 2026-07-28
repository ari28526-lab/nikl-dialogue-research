import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import audit_common_pron_mfa_equivalence as audit  # noqa: E402


def write_textgrid(path: Path, second_phone: str = "a") -> None:
    tier_specs = [
        ("words", [(0.0, 0.5, ""), (0.5, 1.0, "가")]),
        (
            "phones",
            [(0.0, 0.5, ""), (0.5, 0.7, "k"), (0.7, 1.0, second_phone)],
        ),
        ("morphemes", [(0.0, 0.5, ""), (0.5, 1.0, "가")]),
        ("utterance", [(0.0, 0.5, ""), (0.5, 1.0, "가")]),
    ]
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        "xmax = 1",
        "tiers? <exists>",
        "size = 4",
        "item []:",
    ]
    for tier_index, (name, intervals) in enumerate(tier_specs, 1):
        lines.extend(
            [
                f"    item [{tier_index}]:",
                '        class = "IntervalTier"',
                f'        name = "{name}"',
                "        xmin = 0",
                "        xmax = 1",
                f"        intervals: size = {len(intervals)}",
            ]
        )
        for index, (start, end, label) in enumerate(intervals, 1):
            lines.extend(
                [
                    f"        intervals [{index}]:",
                    f"            xmin = {start}",
                    f"            xmax = {end}",
                    f'            text = "{label}"',
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE word (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            word_type TEXT NOT NULL
        );
        CREATE TABLE pronunciation (
            id INTEGER PRIMARY KEY,
            pronunciation TEXT NOT NULL,
            word_id INTEGER NOT NULL
        );
        CREATE TABLE utterance (id INTEGER PRIMARY KEY);
        CREATE TABLE word_interval (id INTEGER PRIMARY KEY);
        CREATE TABLE phone_interval (id INTEGER PRIMARY KEY);
        CREATE TABLE phone (
            id INTEGER PRIMARY KEY,
            phone TEXT NOT NULL
        );
        INSERT INTO word VALUES (1, '가', 'speech');
        INSERT INTO word VALUES (2, '나', 'speech');
        INSERT INTO pronunciation VALUES (1, 'k a', 1);
        INSERT INTO pronunciation VALUES (2, 'n a', 2);
        INSERT INTO utterance VALUES (1);
        INSERT INTO phone VALUES (1, 'k');
        INSERT INTO phone VALUES (2, 'a');
        INSERT INTO phone VALUES (3, 'n');
        """
    )
    connection.commit()
    connection.close()


class CommonPronEquivalenceTests(unittest.TestCase):
    def test_2020_textgrid_phone_sequence_matches_common_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "u1.TextGrid"
            write_textgrid(path)
            result = audit.inspect_2020_textgrid(
                path, {"가": {("k", "a")}}
            )
            self.assertEqual(result["matches"], 1)
            self.assertEqual(result["mismatches"], [])

    def test_2020_textgrid_detects_phone_change(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "u1.TextGrid"
            write_textgrid(path, second_phone="x")
            result = audit.inspect_2020_textgrid(
                path, {"가": {("k", "a")}}
            )
            self.assertEqual(result["matches"], 0)
            self.assertEqual(
                result["mismatches"][0][0], "phone_sequence_changed"
            )

    def test_2021_db_exact_pronunciation_set_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "2021.db"
            integrity = root / "integrity.json"
            make_database(database)
            integrity.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "year": "2021",
                        "result": "ok",
                        "database": {
                            "path": str(database),
                            "bytes": database.stat().st_size,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result, mismatches = audit.audit_2021(
                database=database,
                integrity_report_path=integrity,
                year_vocabulary={"가": 3, "나": 2},
                common={"가": {("k", "a")}, "나": {("n", "a")}},
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(mismatches, [])

    def test_2020_partial_db_is_exhaustive_only_within_partial_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "2020.db"
            make_database(database)
            result, mismatches = audit.audit_2020_partial_db(
                database=database,
                year_vocabulary={"가": 3, "나": 2, "다": 1},
                common={"가": {("k", "a")}, "나": {("n", "a")}},
            )
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["is_expected_partial_database"])
            self.assertEqual(
                result["counts"]["partial_db_observed_words"], 2
            )
            self.assertEqual(result["table_counts"]["word_interval"], 0)
            self.assertEqual(mismatches, [])

    def test_2020_partial_db_detects_candidate_change(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "2020.db"
            make_database(database)
            result, mismatches = audit.audit_2020_partial_db(
                database=database,
                year_vocabulary={"가": 3, "나": 2},
                common={"가": {("k", "a")}, "나": {("n", "x")}},
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                mismatches[0]["reason"], "pronunciation_set_changed"
            )

    def test_2021_db_detects_candidate_set_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "2021.db"
            integrity = root / "integrity.json"
            make_database(database)
            integrity.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "year": "2021",
                        "result": "ok",
                        "database": {
                            "path": str(database),
                            "bytes": database.stat().st_size,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result, mismatches = audit.audit_2021(
                database=database,
                integrity_report_path=integrity,
                year_vocabulary={"가": 3, "나": 2},
                common={"가": {("k", "a")}, "나": {("n", "x")}},
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                mismatches[0]["reason"], "pronunciation_set_changed"
            )


if __name__ == "__main__":
    unittest.main()
