import csv
import gzip
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from export_mfa_db_research_6tier import export_database  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class ExportMfaDbResearch6TierTests(unittest.TestCase):
    def make_acoustic(self, path: Path):
        meta = {"phones": ["k"], "phone_groups": {"0": ["k"]}}
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("acoustic/meta.json", json.dumps(meta))

    def make_contract(self, path: Path):
        path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "year": "2021",
                    "alignment_contract_id": "ALIGN_TEST",
                    "models": {},
                }
            ),
            encoding="utf-8",
        )

    def make_db(self, path: Path, *, spn=False):
        con = sqlite3.connect(path)
        con.executescript(
            """
            CREATE TABLE file(
                id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT
            );
            CREATE TABLE sound_file(
                file_id INTEGER PRIMARY KEY, duration FLOAT,
                sound_file_path TEXT
            );
            CREATE TABLE utterance(
                id INTEGER PRIMARY KEY, file_id INTEGER, ignored BOOLEAN,
                alignment_score FLOAT
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
                begin FLOAT, end FLOAT, phone_id INTEGER,
                word_interval_id INTEGER
            );
            """
        )
        con.execute("INSERT INTO file VALUES(1, 'S1.1', 'S1')")
        con.execute("INSERT INTO sound_file VALUES(1, 1.0, 'D:/wav/S1.1.wav')")
        con.execute("INSERT INTO utterance VALUES(1, 1, 0, -12.5)")
        con.executemany(
            "INSERT INTO word VALUES(?, ?)", [(1, "가"), (2, "<eps>")]
        )
        phones = [(1, "k", "non_silence"), (2, "sil", "silence")]
        if spn:
            phones.append((3, "spn", "non_silence"))
        con.executemany("INSERT INTO phone VALUES(?, ?, ?)", phones)
        con.executemany(
            "INSERT INTO word_interval VALUES(?, 1, ?, ?, ?)",
            [(1, 0.0, 0.1, 2), (2, 0.1, 0.8, 1), (3, 0.8, 1.0, 2)],
        )
        phone_id = 3 if spn else 1
        con.executemany(
            "INSERT INTO phone_interval VALUES(?, 1, ?, ?, ?, ?)",
            [
                (1, 0.0, 0.1, 2, 1),
                (2, 0.1, 0.8, phone_id, 2),
                (3, 0.8, 1.0, 2, 3),
            ],
        )
        con.commit()
        con.close()

    def make_search(self, root: Path, overrides=None):
        path = root / "2021" / "S1.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "utt_id",
            "year",
            "session_id",
            "speaker_id",
            "form",
            "original_form",
            "form_roman",
            "tagged",
            "n_eojeol",
            "start",
            "end",
            "pron_reference_form",
            "pron_reference_n_eojeol",
            "pron_reference_hangul",
            "pron_reference_roman",
            "pron_reference_ipa",
            "pron_reference_source",
            "pron_reference_status",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            row = {
                    "utt_id": "S1.1",
                    "year": "2021",
                    "session_id": "S1",
                    "speaker_id": "SPK1",
                    "form": "가",
                    "original_form": "가",
                    "form_roman": "G A",
                    "tagged": "가/NNG",
                    "n_eojeol": "1",
                    "start": "2.0",
                    "end": "3.0",
                    "pron_reference_form": "가",
                    "pron_reference_n_eojeol": "1",
                    "pron_reference_hangul": "가",
                    "pron_reference_roman": "G A",
                    "pron_reference_ipa": "ka",
                    "pron_reference_source": "test",
                    "pron_reference_status": "resolved",
                }
            row.update(overrides or {})
            writer.writerow(row)

    def make_two_word_db(self, path: Path):
        self.make_db(path)
        con = sqlite3.connect(path)
        con.execute("UPDATE word SET word='두' WHERE id=1")
        con.execute("INSERT INTO word VALUES(3, '사람이')")
        con.execute(
            "UPDATE word_interval SET end=0.4 WHERE id=2"
        )
        con.execute(
            "INSERT INTO word_interval VALUES(4, 1, 0.4, 0.8, 3)"
        )
        con.execute(
            "UPDATE phone_interval SET end=0.4 WHERE id=2"
        )
        con.execute(
            "INSERT INTO phone_interval VALUES(4, 1, 0.4, 0.8, 1, 4)"
        )
        con.commit()
        con.close()

    def test_exports_six_tier_and_normalized_companion_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            contract = root / "contract.json"
            search = root / "search"
            output = root / "output"
            self.make_db(db)
            self.make_acoustic(acoustic)
            self.make_contract(contract)
            self.make_search(search)
            report = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
                workers=2,
            )
            self.assertEqual(report["status"], "success")
            tg = output / "2021" / "S1" / "S1.1.TextGrid"
            _duration, tiers = parse_mfa_textgrid(tg)
            self.assertEqual(
                list(tiers),
                [
                    "words",
                    "phones_mfa",
                    "phoneme_r_auto",
                    "utterance",
                    "utterance_orth_r",
                    "morph_analysis_utt",
                ],
            )
            table_root = output / "2021" / "_tables"
            with gzip.open(
                table_root / "utterance_alignment.csv.gz",
                "rt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                utterances = list(csv.DictReader(stream))
            self.assertEqual(len(utterances), 1)
            self.assertEqual(utterances[0]["textgrid_relative_path"], "2021\\S1\\S1.1.TextGrid")
            self.assertEqual(utterances[0]["pron_mfa_ipa"], "k")
            self.assertEqual(utterances[0]["pron_mfa_r_auto"], "G")
            with gzip.open(
                table_root / "phone_intervals_mfa.csv.gz",
                "rt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                phones = list(csv.DictReader(stream))
            self.assertEqual(phones[1]["mfa_word_idx"], "1")
            self.assertEqual(phones[1]["reference_eojeol_idx"], "1")
            self.assertEqual(phones[1]["phoneme_r_auto"], "G")
            manifest = json.loads(
                (table_root / "TABLES_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["counts"]["utterances"], 1)

    def test_source_and_alignment_reference_positions_are_not_conflated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            contract = root / "contract.json"
            search = root / "search"
            output = root / "output"
            self.make_two_word_db(db)
            self.make_acoustic(acoustic)
            self.make_contract(contract)
            self.make_search(
                search,
                {
                    "form": "2사람이",
                    "tagged": "2/SN+사람/NNG+이/JKS",
                    "n_eojeol": "1",
                    "pron_reference_form": "두 사람이",
                    "pron_reference_n_eojeol": "2",
                },
            )
            report = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
            )
            self.assertEqual(report["status"], "success")
            table_root = output / "2021" / "_tables"
            with gzip.open(
                table_root / "utterance_alignment.csv.gz",
                "rt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                utterance = next(csv.DictReader(stream))
            self.assertEqual(utterance["n_source_eojeol"], "1")
            self.assertEqual(utterance["n_reference_eojeol"], "2")
            self.assertEqual(utterance["n_lab_words_expected"], "2")
            self.assertEqual(utterance["n_mfa_words_aligned"], "2")
            self.assertEqual(utterance["reference_differs_from_form"], "True")
            with gzip.open(
                table_root / "word_intervals_mfa.csv.gz",
                "rt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                words = [row for row in csv.DictReader(stream) if row["mfa_word_idx"]]
            self.assertEqual(
                [(row["reference_eojeol_idx"], row["reference_eojeol"]) for row in words],
                [("1", "두"), ("2", "사람이")],
            )

    def test_failed_table_gate_does_not_promote_gzip_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            contract = root / "contract.json"
            search = root / "search"
            output = root / "output"
            self.make_db(db)
            self.make_acoustic(acoustic)
            self.make_contract(contract)
            self.make_search(
                search,
                {
                    "pron_reference_form": "가 나",
                    "pron_reference_n_eojeol": "2",
                },
            )
            report = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
            )
            self.assertEqual(report["status"], "failed")
            table_root = output / "2021" / "_tables"
            self.assertFalse((table_root / "utterance_alignment.csv.gz").exists())
            self.assertFalse((table_root / "word_intervals_mfa.csv.gz").exists())
            self.assertFalse((table_root / "phone_intervals_mfa.csv.gz").exists())
            self.make_search(search)
            recovered = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
            )
            self.assertEqual(recovered["status"], "success")
            self.assertEqual(
                len(recovered["companion_tables"]["archived_stale_partials"]),
                3,
            )
            self.assertEqual(list(table_root.glob(".*.partial")), [])

    def test_actual_spn_interval_blocks_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            contract = root / "contract.json"
            search = root / "search"
            self.make_db(db, spn=True)
            self.make_acoustic(acoustic)
            self.make_contract(contract)
            self.make_search(search)
            report = export_database(
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=root / "out",
                acoustic_model=acoustic,
                alignment_contract=contract,
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["counts"]["spn_intervals"], 1)


if __name__ == "__main__":
    unittest.main()
