from __future__ import annotations

import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from finalize_post_mfa_alignment_exclusions import (  # noqa: E402
    APPROVAL_TOKEN,
    finalize,
)
from mfa_exclusion_contract import (  # noqa: E402
    REVIEW_FIELDS,
    build_contract,
    load_contract,
)
from pipeline_common import file_fingerprint  # noqa: E402


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class FinalizePostMfaAlignmentExclusionsTests(unittest.TestCase):
    def test_combines_pre_and_exact_db_missing_with_audio_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2020.db"
            connection = sqlite3.connect(db)
            connection.executescript(
                """
                CREATE TABLE file(id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE utterance(
                    id INTEGER PRIMARY KEY, file_id INTEGER, ignored INTEGER
                );
                CREATE TABLE word_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER
                );
                CREATE TABLE phone_interval(
                    id INTEGER PRIMARY KEY, utterance_id INTEGER
                );
                INSERT INTO file VALUES
                    (1, 'ALIGNED'), (2, 'AUDIO1'), (3, 'AUDIO2'),
                    (4, 'AUDIO3'), (5, 'MISS_MFA');
                INSERT INTO utterance VALUES
                    (1, 1, 0), (2, 2, 0), (3, 3, 0),
                    (4, 4, 0), (5, 5, 0);
                INSERT INTO word_interval VALUES (1, 1);
                INSERT INTO phone_interval VALUES (1, 1);
                """
            )
            connection.commit()
            connection.close()

            input_id = "INPUT"
            pre_csv = root / "pre.csv"
            write_rows(
                pre_csv,
                [
                    {
                        "year": "2020",
                        "input_contract_id": input_id,
                        "utt_id": "PRE",
                        "reason_code": "audio_pairing_unresolved",
                        "exclusion_scope": "alignment_and_analysis",
                        "evidence_path": "pre",
                        "decision": "approved",
                        "notes": "fixture",
                    }
                ],
            )
            pre_contract = root / "pre.json"
            build_contract(
                review_csv=pre_csv,
                output=pre_contract,
                year="2020",
                input_contract_id=input_id,
                approved_by="ari30",
                approved_at="2026-08-02T00:00:00+09:00",
            )

            post_csv = root / "post.csv"
            write_rows(
                post_csv,
                [
                    {
                        "year": "2020",
                        "input_contract_id": input_id,
                        "utt_id": utt_id,
                        "reason_code": "mfa_alignment_missing",
                        "exclusion_scope": "alignment_and_analysis",
                        "evidence_path": "post",
                        "decision": "pending",
                        "notes": "fixture",
                    }
                    for utt_id in ("AUDIO1", "AUDIO2", "AUDIO3", "MISS_MFA")
                ],
            )
            bundle = root / "bundle"
            bundle.mkdir()
            with (bundle / "00_REVIEW.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream, fieldnames=["utt_id", "decision"]
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "AUDIO1",
                        "decision": "exclude_audio_unusable",
                    }
                )
                for index in range(13):
                    writer.writerow(
                        {"utt_id": f"MATCH{index}", "decision": "match"}
                    )
                writer.writerow(
                    {"utt_id": "AUDIO2", "decision": "exclude_audio_unusable"}
                )
                writer.writerow(
                    {"utt_id": "AUDIO3", "decision": "exclude_audio_unusable"}
                )
            manifest = {
                "schema_version": "simple_post_mfa_review_bundle.v2",
                "status": "success",
                "year": "2020",
                "post_mfa_candidates_csv": file_fingerprint(
                    post_csv, with_sha256=True
                ),
                "approved_audio_unusable_exclusion_count": 3,
                "approved_audio_unusable_utt_ids": [
                    "AUDIO1",
                    "AUDIO2",
                    "AUDIO3",
                ],
                "researcher_review_evidence": {"sha256": "fixture"},
            }
            manifest_path = bundle / "MANIFEST.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            # An incorrect token cannot create an approval contract.
            with self.assertRaises(RuntimeError):
                finalize(
                    year="2020",
                    input_contract_id=input_id,
                    db_path=db,
                    pre_approved_contract=pre_contract,
                    post_decisions=post_csv,
                    review_bundle_manifest=manifest_path,
                    output_root=root / "bad",
                    approved_by="ari30",
                    approved_at=datetime.now().astimezone().isoformat(),
                    approval_token="WRONG",
                    approval_statement="proceed",
                )

            output = root / "final"
            result = finalize(
                year="2020",
                input_contract_id=input_id,
                db_path=db,
                pre_approved_contract=pre_contract,
                post_decisions=post_csv,
                review_bundle_manifest=manifest_path,
                output_root=output,
                approved_by="ari30",
                approved_at="2026-08-03T12:00:00+09:00",
                approval_token=APPROVAL_TOKEN,
                approval_statement="proceed to retained DB export",
            )
            self.assertEqual(result["counts"]["combined_approved"], 5)
            self.assertEqual(result["counts"]["post_mfa_audio_unusable"], 3)
            _contract, rows_by_id = load_contract(
                output / "approved_exclusions.json",
                year="2020",
                input_contract_id=input_id,
            )
            self.assertEqual(rows_by_id["AUDIO1"]["reason_code"], "audio_unusable")
            self.assertEqual(rows_by_id["MISS_MFA"]["reason_code"], "mfa_alignment_missing")


if __name__ == "__main__":
    unittest.main()
