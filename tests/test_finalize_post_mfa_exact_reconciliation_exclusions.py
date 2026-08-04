import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from finalize_post_mfa_exact_reconciliation_exclusions import finalize  # noqa: E402
from mfa_exclusion_contract import (  # noqa: E402
    REVIEW_FIELDS,
    build_contract,
    load_contract,
)
from pipeline_common import sha256_file  # noqa: E402
from prepare_post_mfa_alignment_review import prepare_review  # noqa: E402


class FinalizePostMfaExactReconciliationTests(unittest.TestCase):
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
            [(1, "U1", "S1"), (2, "U2", "S1"), (3, "U3", "S2")],
        )
        connection.executemany(
            "INSERT INTO utterance VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 0.0, 1.0, 100, "정상", 1, -10.0, 0),
                (2, 2, 0.0, 1.2, 120, "미정렬", 2, None, 0),
                (3, 3, 0.0, 0.03, None, "초단시간", None, None, 1),
            ],
        )
        connection.execute("INSERT INTO word_interval VALUES(1, 1)")
        connection.execute("INSERT INTO phone_interval VALUES(1, 1)")
        connection.commit()
        connection.close()

    def make_pre_contract(self, root: Path) -> Path:
        review = root / "pre.csv"
        with review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "year": "2021",
                    "input_contract_id": "INPUT1",
                    "utt_id": "OLD1",
                    "reason_code": "audio_pairing_unresolved",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": "fixture",
                    "decision": "approved",
                    "notes": "pre-MFA exclusion",
                }
            )
        contract = root / "pre.json"
        build_contract(
            review_csv=review,
            output=contract,
            year="2021",
            input_contract_id="INPUT1",
            approved_by="researcher",
            approved_at="2026-08-04T11:00:00+09:00",
        )
        return contract

    def make_export_report(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "exact_id_reconciliation": {
                        "inventories": {
                            "unknown_active_lab_without_alignment": [
                                "U2",
                                "U3",
                            ]
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    def make_audio_lab(self, root: Path) -> None:
        for session, utt_id, text in [
            ("S1", "U1", "정상"),
            ("S1", "U2", "미정렬"),
            ("S2", "U3", "초단시간"),
        ]:
            target = root / "2021" / session
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{utt_id}.wav").write_bytes(b"RIFFfixture")
            (target / f"{utt_id}.lab").write_text(text, encoding="utf-8")

    def prepare(self, root: Path) -> tuple[Path, Path, Path, Path, str]:
        db = root / "2021.db"
        export = root / "export.json"
        corpus = root / "corpus"
        review_root = root / "review"
        self.make_db(db)
        self.make_export_report(export)
        pre_contract = self.make_pre_contract(root)
        self.make_audio_lab(corpus)
        summary = prepare_review(
            db_path=db,
            year="2021",
            export_report=export,
            approved_exclusions_contract=pre_contract,
            lab_root=corpus,
            output_root=review_root,
            copy_sample_files=False,
        )
        decisions = review_root / "04_RESEARCHER_APPROVAL.csv"
        with decisions.open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            row["decision"] = "approved"
            row["notes"] += "; researcher approved fixture"
        with decisions.open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return (
            db,
            export,
            pre_contract,
            review_root,
            str(summary["required_approval_token"]),
        )

    def test_combines_explicitly_approved_post_mfa_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, export, pre_contract, review_root, token = self.prepare(root)
            before = sha256_file(db)
            output = root / "combined"

            result = finalize(
                year="2021",
                input_contract_id="INPUT1",
                db_path=db,
                export_report=export,
                pre_approved_contract=pre_contract,
                review_summary=review_root / "SUMMARY.json",
                researcher_decisions=(
                    review_root / "04_RESEARCHER_APPROVAL.csv"
                ),
                output_root=output,
                approved_by="ari30",
                approved_at="2026-08-04T16:00:00+09:00",
                approval_token=token,
                approval_statement="Approve exact post-MFA exclusions.",
            )

            self.assertEqual(sha256_file(db), before)
            self.assertFalse(result["automatic_approval_performed"])
            self.assertFalse(result["full_year_mfa_rerun_required"])
            self.assertTrue(result["resume_from_retained_db"])
            self.assertEqual(result["counts"]["post_mfa_approved"], 2)
            self.assertEqual(
                result["post_mfa_reason_counts"],
                {
                    "mfa_alignment_missing": 1,
                    "mfa_feature_generation_failed": 1,
                },
            )
            _, rows = load_contract(
                output / "approved_exclusions.json",
                year="2021",
                input_contract_id="INPUT1",
            )
            self.assertEqual(set(rows), {"OLD1", "U2", "U3"})

    def test_rejects_wrong_token_without_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, export, pre_contract, review_root, _token = self.prepare(root)
            output = root / "combined"
            with self.assertRaisesRegex(RuntimeError, "token"):
                finalize(
                    year="2021",
                    input_contract_id="INPUT1",
                    db_path=db,
                    export_report=export,
                    pre_approved_contract=pre_contract,
                    review_summary=review_root / "SUMMARY.json",
                    researcher_decisions=(
                        review_root / "04_RESEARCHER_APPROVAL.csv"
                    ),
                    output_root=output,
                    approved_by="ari30",
                    approved_at="2026-08-04T16:00:00+09:00",
                    approval_token="WRONG",
                    approval_statement="Approve exact post-MFA exclusions.",
                )
            self.assertFalse(output.exists())

    def test_preflight_validates_without_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, export, pre_contract, review_root, token = self.prepare(root)
            output = root / "combined"
            result = finalize(
                year="2021",
                input_contract_id="INPUT1",
                db_path=db,
                export_report=export,
                pre_approved_contract=pre_contract,
                review_summary=review_root / "SUMMARY.json",
                researcher_decisions=(
                    review_root / "04_RESEARCHER_APPROVAL.csv"
                ),
                output_root=output,
                approved_by="ari30",
                approved_at="2026-08-04T16:00:00+09:00",
                approval_token=token,
                approval_statement="Approve exact post-MFA exclusions.",
                preflight_only=True,
            )
            self.assertEqual(result["status"], "validated_preflight")
            self.assertFalse(result["output_created"])
            self.assertFalse(output.exists())

            output.mkdir()
            result_existing = finalize(
                year="2021",
                input_contract_id="INPUT1",
                db_path=db,
                export_report=export,
                pre_approved_contract=pre_contract,
                review_summary=review_root / "SUMMARY.json",
                researcher_decisions=(
                    review_root / "04_RESEARCHER_APPROVAL.csv"
                ),
                output_root=output,
                approved_by="ari30",
                approved_at="2026-08-04T16:00:00+09:00",
                approval_token=token,
                approval_statement="Approve exact post-MFA exclusions.",
                preflight_only=True,
            )
            self.assertEqual(
                result_existing["status"], "validated_preflight"
            )
            self.assertEqual(list(output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
