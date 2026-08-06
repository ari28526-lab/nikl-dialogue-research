import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from mfa_production_year_review import (  # noqa: E402
    FIELDS,
    IDENTITY_FIELDS,
    approve,
    approve_explicit,
    prepare,
    validate,
)
from pipeline_common import file_fingerprint, sha256_file  # noqa: E402


class ProductionYearReviewTests(unittest.TestCase):
    def write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_prepare_approve_and_validate_exact_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            year = "2020"
            search = root / "search"
            wav_root = root / "wav"
            final = root / "final"
            sample_csv = root / "sample.csv"
            sample_rows = []
            for index in range(5):
                session = f"S{index}"
                utt = f"U{index}"
                (wav_root / year / session).mkdir(parents=True, exist_ok=True)
                (final / year / session).mkdir(parents=True, exist_ok=True)
                (wav_root / year / session / f"{utt}.wav").write_bytes(b"wav")
                (wav_root / year / session / f"{utt}.lab").write_text(
                    "test", encoding="utf-8"
                )
                tg = final / year / session / f"{utt}.TextGrid"
                tg.write_text("File type = text", encoding="utf-8")
                (search / year).mkdir(parents=True, exist_ok=True)
                with (search / year / f"{session}.csv").open(
                    "w", encoding="utf-8-sig", newline=""
                ) as stream:
                    writer = csv.DictWriter(stream, fieldnames=["utt_id", "speaker_id"])
                    writer.writeheader()
                    writer.writerow({"utt_id": utt, "speaker_id": f"SPK{index}"})
                sample_rows.append(
                    {
                        "year": year,
                        "session": session,
                        "utt_id": utt,
                        "status": "exact_match",
                        "semantic_equal": "true",
                        "byte_equal": "true",
                        "final_path": str(tg),
                        "regenerated_path": str(tg),
                        "final_sha256": "x",
                        "regenerated_sha256": "x",
                    }
                )
            with sample_csv.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(sample_rows[0]))
                writer.writeheader()
                writer.writerows(sample_rows)
            sample_report = root / "sample.json"
            self.write_json(
                sample_report,
                {
                    "schema_version": "mfa_db_research_6tier_sample_equivalence.v1",
                    "status": "success",
                    "year": year,
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": "ALIGN",
                    "sample_csv": {"sha256": sha256_file(sample_csv)},
                },
            )
            db = root / "alignment.db"
            db.write_bytes(b"db")
            align_marker = root / "align.json"
            self.write_json(align_marker, {"details": {"alignment_db": str(db)}})
            alignment = root / "alignment.json"
            self.write_json(
                alignment,
                {
                    "status": "passed",
                    "lab_input_contract_id": "INPUT",
                    "alignment_contract_id": "ALIGN",
                },
            )
            review_csv = root / "review" / "REVIEW.csv"
            review_manifest = root / "review" / "MANIFEST.json"
            result = prepare(
                year=year,
                sample_csv=sample_csv,
                sample_report=sample_report,
                align_marker=align_marker,
                alignment_contract=alignment,
                search_master_root=search,
                wav_root=wav_root,
                output_csv=review_csv,
                output_manifest=review_manifest,
            )
            self.assertEqual(result["status"], "pending_researcher_review")
            with review_csv.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
                fields = list(rows[0])
            for row in rows:
                row["decision"] = "approved"
            with review_csv.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            approval = root / "review" / "APPROVAL.json"
            report = approve(
                review_csv=review_csv,
                review_manifest=review_manifest,
                approved_by="researcher",
                output=approval,
            )
            self.assertEqual(report["schema_version"], "mfa_production_year_researcher_review.v1")
            self.assertEqual(validate(report_path=approval, review_csv=review_csv)["status"], "passed")
            rows[0]["utt_id"] = "TAMPERED"
            with review_csv.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(validate(report_path=approval, review_csv=review_csv)["status"], "failed")

    def test_explicit_approval_preserves_pending_csv_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "03_RESEARCHER_REVIEW.csv"
            rows = []
            for index in range(5):
                rows.append(
                    {
                        "review_order": str(index + 1),
                        "year": "2021",
                        "session": f"S{index}",
                        "speaker_id": f"SPK{index}",
                        "utt_id": f"U{index}",
                        "wav_path": str(root / f"U{index}.wav"),
                        "lab_path": str(root / f"U{index}.lab"),
                        "textgrid_path": str(root / f"U{index}.TextGrid"),
                        "decision": "pending",
                        "notes": "",
                    }
                )
            with review_csv.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            original_bytes = review_csv.read_bytes()
            manifest_path = root / "03_RESEARCHER_REVIEW_MANIFEST.json"
            self.write_json(
                manifest_path,
                {
                    "schema_version": "mfa_production_year_review_manifest.v1",
                    "status": "pending_researcher_review",
                    "year": "2021",
                    "input_contract_id": "INPUT",
                    "alignment_contract_id": "ALIGN",
                    "database": str(root / "2021.db"),
                    "review_csv_template": file_fingerprint(
                        review_csv, with_sha256=True
                    ),
                    "row_identities": [
                        {key: row[key] for key in IDENTITY_FIELDS} for row in rows
                    ],
                    "counts": {"rows": 5, "sessions": 5, "speakers_nonempty": 5},
                    "automatic_approval_performed": False,
                },
            )
            pending_archive = root / "03_RESEARCHER_REVIEW_PENDING_ORIGINAL.csv"
            decision_record = root / "03_RESEARCHER_DECISION.json"
            approval = root / "04_RESEARCHER_APPROVAL.json"
            kwargs = {
                "review_csv": review_csv,
                "review_manifest": manifest_path,
                "approved_by": "researcher",
                "approval_statement": "five reviewed samples are approved",
                "expected_row_count": 5,
                "pending_archive": pending_archive,
                "decision_record": decision_record,
                "output": approval,
                "row_note": "explicit infrastructure review; no realization judgment",
            }
            report = approve_explicit(**kwargs)
            self.assertEqual(pending_archive.read_bytes(), original_bytes)
            with review_csv.open("r", encoding="utf-8-sig", newline="") as stream:
                approved_rows = list(csv.DictReader(stream))
            self.assertTrue(all(row["decision"] == "approved" for row in approved_rows))
            self.assertTrue(all(row["notes"] for row in approved_rows))
            decision = json.loads(decision_record.read_text(encoding="utf-8"))
            self.assertFalse(decision["automatic_approval_performed"])
            self.assertTrue(
                decision["materialized_from_explicit_researcher_statement"]
            )
            self.assertEqual(report["status"], "approved")
            self.assertEqual(validate(report_path=approval, review_csv=review_csv)["status"], "passed")
            approved_sha = sha256_file(review_csv)
            second = approve_explicit(**kwargs)
            self.assertEqual(second["status"], "approved")
            self.assertEqual(sha256_file(review_csv), approved_sha)
            with self.assertRaisesRegex(RuntimeError, "row count differs"):
                approve_explicit(**{**kwargs, "expected_row_count": 6})


if __name__ == "__main__":
    unittest.main()
