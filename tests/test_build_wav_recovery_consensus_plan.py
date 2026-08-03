from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_wav_recovery_consensus_plan import build  # noqa: E402


def plan_row(target: str, source: str, status: str) -> dict[str, str]:
    return {
        "year": "2023", "session": "S", "target_utt_id": target,
        "source_utt_id": source, "status": status, "block_length": "5",
        "target_duration_seconds": "1", "source_duration_seconds": "1",
        "duration_residual_seconds": "0", "source_wav": f"{source}.wav",
    }


class BuildWavRecoveryConsensusPlanTests(unittest.TestCase):
    def test_only_a_and_bracketed_b_are_selected(self) -> None:
        topology = [
            {
                "target_utt_id": "T1", "topology_tier": "A_ALL_SCALE_CONSENSUS",
                "consensus_source_utt_id": "S1",
            },
            {
                "target_utt_id": "T2",
                "topology_tier": "B_Q2_Q5_BRACKETED_SAME_OFFSET",
                "consensus_source_utt_id": "S2",
            },
            {
                "target_utt_id": "T3", "topology_tier": "D_NO_HIGH_MAPPING",
                "consensus_source_utt_id": "",
            },
        ]
        q1 = {
            "T1": plan_row("T1", "S1", "remap_high_confidence"),
            "T2": plan_row("T2", "", "target_unresolved"),
            "T3": plan_row("T3", "", "target_unresolved"),
        }
        q2 = {
            "T1": plan_row("T1", "S1", "remap_high_confidence"),
            "T2": plan_row("T2", "S2", "remap_high_confidence"),
            "T3": plan_row("T3", "", "target_unresolved"),
        }
        rows, report = build(
            year="2023", topology_rows=topology, q1_rows=q1, q2_rows=q2
        )
        by_target = {row["target_utt_id"]: row for row in rows}
        self.assertEqual(by_target["T1"]["source_utt_id"], "S1")
        self.assertEqual(by_target["T2"]["source_utt_id"], "S2")
        self.assertEqual(by_target["T3"]["status"], "target_unresolved")
        self.assertEqual(report["duplicate_selected_source_count"], 0)
        self.assertFalse(report["safe_to_auto_apply"])


if __name__ == "__main__":
    unittest.main()
