from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from compare_wav_recovery_plans import compare  # noqa: E402


FIELDS = [
    "year", "session", "target_utt_id", "source_utt_id", "status",
    "block_length", "target_duration_seconds", "source_duration_seconds",
    "duration_residual_seconds", "source_wav",
]


def write_plan(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(target: str, source: str, status: str) -> dict[str, str]:
    return {
        "year": "2023",
        "session": "S",
        "target_utt_id": target,
        "source_utt_id": source,
        "status": status,
        "block_length": "4" if source else "0",
        "target_duration_seconds": "1",
        "source_duration_seconds": "1" if source else "",
        "duration_residual_seconds": "0" if source else "",
        "source_wav": f"{source}.wav" if source else "",
    }


class CompareWavRecoveryPlansTests(unittest.TestCase):
    def test_consensus_partial_and_conflict_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audit = root / "audit.json"
            issue_rows = [
                {
                    "issue": "duration_residual_mismatch",
                    "utt_id": target,
                }
                for target in ("T1", "T2", "T3", "T4")
            ]
            audit.write_text(
                json.dumps({"years": [{"year": "2023", "issue_inventory": issue_rows}]}),
                encoding="utf-8",
            )
            q1 = root / "q1.csv"
            q2 = root / "q2.csv"
            write_plan(
                q1,
                [
                    row("T1", "S1", "remap_high_confidence"),
                    row("T2", "", "target_unresolved"),
                    row("T3", "S3", "remap_high_confidence"),
                    row("T4", "T4", "identity_high_confidence"),
                ],
            )
            write_plan(
                q2,
                [
                    row("T1", "S1", "remap_high_confidence"),
                    row("T2", "S2", "remap_high_confidence"),
                    row("T3", "S9", "remap_high_confidence"),
                    row("T4", "T4", "identity_high_confidence"),
                ],
            )

            rows, report = compare(
                year="2023", audit_path=audit, plans=[("q1", q1), ("q2", q2)]
            )
            by_target = {item["target_utt_id"]: item for item in rows}
            self.assertEqual(by_target["T1"]["classification"], "consensus_remap")
            self.assertEqual(
                by_target["T2"]["classification"], "partial_high_same_source"
            )
            self.assertEqual(
                by_target["T3"]["classification"], "conflicting_high_source"
            )
            self.assertEqual(by_target["T4"]["classification"], "consensus_identity")
            self.assertEqual(report["affected_target_count"], 4)
            self.assertEqual(
                report["high_label_signature_counts"],
                {"q1+q2": 3, "q2": 1},
            )
            self.assertEqual(report["duplicate_high_source_counts_by_plan"], {"q1": 0, "q2": 0})
            self.assertFalse(report["safe_to_auto_apply"])


if __name__ == "__main__":
    unittest.main()
