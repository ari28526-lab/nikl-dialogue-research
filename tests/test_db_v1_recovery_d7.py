from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from build_db_v1_recovery_d7_partial_alignment_gate import DECISION_MAP  # noqa: E402


def test_d7_decision_map_exact_counts() -> None:
    counts = Counter(value[0] for value in DECISION_MAP.values())
    assert counts == {
        "noise_hold": 3,
        "transcript_segment_missing": 1,
        "transcript_correction_candidate": 1,
        "partial_alignment_available": 6,
    }


def test_d7_decision_map_has_unique_exact_ids() -> None:
    assert len(DECISION_MAP) == 11
    assert all("." in utt_id for utt_id in DECISION_MAP)


def test_d7_partial_alignment_uses_separate_retention_action() -> None:
    actions = {
        action
        for usability, action in DECISION_MAP.values()
        if usability == "partial_alignment_available"
    }
    assert actions == {"retain_searchable_partial_alignment_separate_from_main_body"}
