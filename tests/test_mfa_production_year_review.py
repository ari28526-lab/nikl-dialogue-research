import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from mfa_production_year_review import approve, prepare, validate  # noqa: E402
from pipeline_common import sha256_file  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
