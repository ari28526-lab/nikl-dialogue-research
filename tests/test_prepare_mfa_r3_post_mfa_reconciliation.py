import csv
import gzip
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from pipeline_common import file_fingerprint, sha256_file  # noqa: E402
from prepare_mfa_r3_post_mfa_reconciliation import prepare  # noqa: E402


class PrepareMfaR3PostMfaReconciliationTests(unittest.TestCase):
    year = "2020"

    def make_db(self, path: Path) -> None:
        con = sqlite3.connect(path)
        con.executescript(
            """
            CREATE TABLE file(
                id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT
            );
            CREATE TABLE utterance(
                id INTEGER PRIMARY KEY, file_id INTEGER, begin REAL, end REAL,
                num_frames INTEGER, normalized_text TEXT, job_id INTEGER,
                alignment_log_likelihood REAL, ignored BOOLEAN
            );
            CREATE TABLE word_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER
            );
            CREATE TABLE phone_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER
            );
            INSERT INTO file VALUES(1, 'U1', 'S1');
            INSERT INTO file VALUES(2, 'U2', 'S1');
            INSERT INTO file VALUES(3, 'U3', 'S2');
            INSERT INTO utterance VALUES(1,1,0,1,100,'가',1,-1,0);
            INSERT INTO utterance VALUES(2,2,0,1,100,'나',1,NULL,0);
            INSERT INTO utterance VALUES(3,3,0,1,NULL,'다',2,NULL,1);
            INSERT INTO word_interval VALUES(1,1);
            INSERT INTO phone_interval VALUES(1,1);
            """
        )
        con.commit()
        con.close()

    def make_expected(self, path: Path, ids: list[tuple[str, str]]) -> None:
        with path.open("wb") as raw:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=0
            ) as compressed:
                with io.TextIOWrapper(
                    compressed, encoding="utf-8-sig", newline=""
                ) as text:
                    writer = csv.DictWriter(
                        text,
                        fieldnames=["year", "utt_id", "session_id"],
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    for utt_id, session_id in ids:
                        writer.writerow(
                            {
                                "year": self.year,
                                "utt_id": utt_id,
                                "session_id": session_id,
                            }
                        )

    def make_contracts(
        self, root: Path, db: Path, expected: Path, count: int
    ) -> tuple[Path, Path]:
        expected_record = file_fingerprint(expected, with_sha256=True)
        alignment_id = "a" * 64
        contract = root / "ALIGNMENT_CONTRACT_2020.json"
        contract.write_text(
            json.dumps(
                {
                    "schema_version": "mfa_r3_alignment_contract.v1",
                    "year": self.year,
                    "alignment_contract_id": alignment_id,
                    "identity": {
                        "year_input_contract_id": "input-r3-fixture",
                        "expected_mfa_input_sha256": expected_record["sha256"],
                    },
                    "year_input": {
                        "expected_mfa_input": count,
                        "expected_mfa_input_ids": expected_record,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        marker = root / "ALIGN_DONE_2020.json"
        marker.write_text(
            json.dumps(
                {
                    "schema_version": "mfa_r3_alignment_done.v1",
                    "status": "passed",
                    "year": self.year,
                    "release_id": "common_pron_mfa_r3_fixture",
                    "alignment_contract_id": alignment_id,
                    "source_db": file_fingerprint(db, with_sha256=True),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return marker, contract

    def test_prepares_pending_exact_id_review_without_modifying_db(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "2020.db"
            expected = root / "expected.csv.gz"
            output = root / "review"
            self.make_db(db)
            self.make_expected(expected, [("U1", "S1"), ("U2", "S1"), ("U3", "S2")])
            marker, contract = self.make_contracts(root, db, expected, 3)
            before = sha256_file(db)

            result = prepare(
                db_path=db,
                year=self.year,
                alignment_marker=marker,
                alignment_contract=contract,
                output_root=output,
            )

            self.assertEqual(result["status"], "pending_researcher_approval")
            self.assertEqual(result["counts"]["aligned_utterances"], 1)
            self.assertEqual(result["counts"]["post_mfa_candidates"], 2)
            self.assertEqual(
                result["counts"]["reason_counts"],
                {
                    "mfa_alignment_missing": 1,
                    "mfa_feature_generation_failed": 1,
                },
            )
            with (output / "02_RESEARCHER_DECISIONS.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["utt_id"] for row in rows], ["U2", "U3"])
            self.assertTrue(all(row["decision"] == "pending" for row in rows))
            for record in result["outputs"].values():
                self.assertTrue(Path(record["path"]).is_file())
            self.assertEqual(before, sha256_file(db))

    def test_database_input_mismatch_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "2020.db"
            expected = root / "expected.csv.gz"
            output = root / "review"
            self.make_db(db)
            self.make_expected(expected, [("U1", "S1"), ("U2", "S1")])
            marker, contract = self.make_contracts(root, db, expected, 2)

            with self.assertRaisesRegex(RuntimeError, "exact-ID mismatch"):
                prepare(
                    db_path=db,
                    year=self.year,
                    alignment_marker=marker,
                    alignment_contract=contract,
                    output_root=output,
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
