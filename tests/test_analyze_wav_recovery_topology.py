from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from analyze_wav_recovery_topology import analyze  # noqa: E402


def row(number: int, source_number: int | None, signature: str) -> dict[str, str]:
    return {
        "year": "2023",
        "session": "S",
        "target_utt_id": f"S.1.1.{number}",
        "classification": "test",
        "consensus_source_utt_id": (
            f"S.1.1.{source_number}" if source_number is not None else ""
        ),
        "high_plan_count": "3" if signature == "q1+q2+q5" else "2",
        "high_labels": signature,
    }


class AnalyzeWavRecoveryTopologyTests(unittest.TestCase):
    def test_secondary_candidate_is_bracketed_by_same_offset(self) -> None:
        rows = [
            row(1, 2, "q1+q2+q5"),
            row(2, 3, "q2+q5"),
            row(3, 4, "q1+q2+q5"),
            row(4, None, "none"),
        ]
        enriched, report = analyze(
            rows,
            all_signature="q1+q2+q5",
            secondary_signature="q2+q5",
        )
        by_target = {item["target_utt_id"]: item for item in enriched}
        self.assertEqual(
            by_target["S.1.1.2"]["topology_tier"],
            "B_Q2_Q5_BRACKETED_SAME_OFFSET",
        )
        self.assertEqual(
            report["topology_tier_counts"],
            {
                "A_ALL_SCALE_CONSENSUS": 2,
                "B_Q2_Q5_BRACKETED_SAME_OFFSET": 1,
                "D_NO_HIGH_MAPPING": 1,
            },
        )
        self.assertFalse(report["safe_to_auto_apply"])


if __name__ == "__main__":
    unittest.main()
