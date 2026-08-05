import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from mfa_production_year_review import FIELDS, IDENTITY_FIELDS  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402
from stage_mfa_production_review_bundle import stage_bundle  # noqa: E402


class StageMfaProductionReviewBundleTests(unittest.TestCase):
    def test_stages_flat_verified_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            rows = []
            for order in range(1, 6):
                utt = f"S{order}.1"
                wav = source / f"{utt}.wav"
                lab = source / f"{utt}.lab"
                tg = source / f"{utt}.TextGrid"
                wav.write_bytes(b"RIFF" + bytes([order]))
                lab.write_text(f"lab-{order}", encoding="utf-8")
                tg.write_text(f"tg-{order}", encoding="utf-8")
                rows.append(
                    {
                        "review_order": str(order),
                        "year": "2021",
                        "session": f"S{order}",
                        "speaker_id": f"P{order}",
                        "utt_id": utt,
                        "wav_path": str(wav),
                        "lab_path": str(lab),
                        "textgrid_path": str(tg),
                        "decision": "pending",
                        "notes": "",
                    }
                )
            review = root / "03_RESEARCHER_REVIEW.csv"
            with review.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            manifest = root / "03_RESEARCHER_REVIEW_MANIFEST.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "mfa_production_year_review_manifest.v1",
                        "status": "pending_researcher_review",
                        "year": "2021",
                        "input_contract_id": "INPUT",
                        "alignment_contract_id": "ALIGN",
                        "automatic_approval_performed": False,
                        "row_identities": [
                            {key: row[key] for key in IDENTITY_FIELDS}
                            for row in rows
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "bundle"
            result = stage_bundle(
                review_csv=review,
                review_manifest=manifest,
                output_root=output,
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["counts"]["payload_files"], 15)
            self.assertEqual(len(list(output.glob("*.wav"))), 5)
            self.assertEqual(len(list(output.glob("*.lab"))), 5)
            self.assertEqual(len(list(output.glob("*.TextGrid"))), 5)
            self.assertEqual(
                file_fingerprint(review, with_sha256=True)["sha256"],
                file_fingerprint(
                    output / "03_RESEARCHER_REVIEW.csv", with_sha256=True
                )["sha256"],
            )
            copied_manifest = json.loads(
                (output / "BUNDLE_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(copied_manifest["counts"]["sessions"], 5)


if __name__ == "__main__":
    unittest.main()
