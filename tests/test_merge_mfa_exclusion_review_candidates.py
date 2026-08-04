import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from merge_mfa_exclusion_review_candidates import merge_snapshots  # noqa: E402
from mfa_exclusion_contract import REVIEW_FIELDS  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


class MergeMfaExclusionReviewCandidatesTests(unittest.TestCase):
    def make_snapshot(
        self, root: Path, name: str, rows: list[dict[str, str]]
    ) -> tuple[Path, Path]:
        csv_path = root / f"{name}.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        manifest = root / f"{name}.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "mfa_exclusion_review_candidates.v1",
                    "status": "pending_researcher_review",
                    "year": "2021",
                    "input_contract_id": "INPUT",
                    "review_csv": file_fingerprint(
                        csv_path, with_sha256=True
                    ),
                    "candidate_count": len(rows),
                    "automatic_approval_performed": False,
                }
            ),
            encoding="utf-8",
        )
        return csv_path, manifest

    @staticmethod
    def row(utt_id: str, reason: str) -> dict[str, str]:
        return {
            "year": "2021",
            "input_contract_id": "INPUT",
            "utt_id": utt_id,
            "reason_code": reason,
            "exclusion_scope": "alignment_and_analysis",
            "evidence_path": "audit.json",
            "decision": "pending",
            "notes": "test",
        }

    def test_keeps_base_and_adds_only_new_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_csv, base_manifest = self.make_snapshot(
                root,
                "base",
                [self.row("U1", "text_duration_impossible")],
            )
            add_csv, add_manifest = self.make_snapshot(
                root,
                "add",
                [
                    self.row("U1", "text_duration_impossible"),
                    self.row("U2", "audio_pairing_unresolved"),
                ],
            )
            output_csv = root / "merged.csv"
            result = merge_snapshots(
                base_csv=base_csv,
                base_manifest=base_manifest,
                addendum_csv=add_csv,
                addendum_manifest=add_manifest,
                output_csv=output_csv,
                output_manifest=root / "merged.json",
            )
            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual(result["duplicate_candidate_count"], 1)
            self.assertEqual(result["new_addendum_candidate_count"], 1)
            with output_csv.open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["utt_id"] for row in rows], ["U1", "U2"])
            self.assertTrue(all(row["decision"] == "pending" for row in rows))

    def test_duplicate_reason_conflict_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_csv, base_manifest = self.make_snapshot(
                root, "base", [self.row("U1", "text_duration_impossible")]
            )
            add_csv, add_manifest = self.make_snapshot(
                root, "add", [self.row("U1", "audio_pairing_unresolved")]
            )
            with self.assertRaisesRegex(RuntimeError, "reason/scope 충돌"):
                merge_snapshots(
                    base_csv=base_csv,
                    base_manifest=base_manifest,
                    addendum_csv=add_csv,
                    addendum_manifest=add_manifest,
                    output_csv=root / "merged.csv",
                    output_manifest=root / "merged.json",
                )


if __name__ == "__main__":
    unittest.main()
