from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_failed_session_quarantine_plan import build_plan  # noqa: E402


def row(target: str, session: str, status: str) -> dict[str, str]:
    return {
        "year": "2023",
        "session": session,
        "target_utt_id": target,
        "source_utt_id": target,
        "status": status,
        "block_length": "3",
        "target_duration_seconds": "1.0",
        "source_duration_seconds": "1.0",
        "duration_residual_seconds": "0.0",
        "source_wav": "x.wav",
    }


class FailedSessionQuarantinePlanTests(unittest.TestCase):
    def test_failed_session_quarantines_even_apparent_identity(self) -> None:
        audit = {
            "duration_audit": {"failed_sessions": [{"session": "s1"}]},
            "issue_inventory": [
                {"utt_id": "u2", "issue": "duration_residual_mismatch"}
            ],
        }
        output, report = build_plan(
            year="2023",
            audit_row=audit,
            plan_rows=[
                row("u1", "s1", "identity_high_confidence"),
                row("u2", "s1", "target_unresolved"),
                row("u3", "s2", "identity_high_confidence"),
            ],
        )
        by_target = {value["target_utt_id"]: value for value in output}
        self.assertEqual(by_target["u1"]["status"], "target_unresolved")
        self.assertEqual(by_target["u1"]["source_wav"], "")
        self.assertEqual(by_target["u3"]["status"], "identity_high_confidence")
        self.assertEqual(report["failed_session_rows"], 2)
        self.assertEqual(report["additional_session_quarantine_count"], 1)
        self.assertEqual(report["final_audio_exclusion_count"], 2)

    def test_source_orphan_without_target_is_preserved(self) -> None:
        orphan = row("", "s1", "source_orphan")
        output, report = build_plan(
            year="2023",
            audit_row={
                "duration_audit": {"failed_sessions": [{"session": "s1"}]},
                "issue_inventory": [],
            },
            plan_rows=[row("u1", "s1", "identity_high_confidence"), orphan],
        )
        self.assertEqual(output[1]["status"], "source_orphan")
        self.assertEqual(output[1]["target_utt_id"], "")
        self.assertEqual(report["failed_session_rows"], 1)


if __name__ == "__main__":
    unittest.main()
