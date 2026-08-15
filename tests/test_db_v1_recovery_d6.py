from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from build_db_v1_recovery_d6_gate import classify_missing  # noqa: E402


def evidence(
    *, ignored: bool = False, frames: int | None = 100,
    words: int = 0, phones: int = 0,
) -> dict[str, object]:
    return {
        "ignored_by_mfa": ignored,
        "num_frames": frames,
        "word_interval_count": words,
        "phone_interval_count": phones,
    }


def test_classify_feature_generation_failure_first() -> None:
    assert classify_missing(evidence(ignored=True, frames=None)) == "feature_generation_failed_in_d5"


def test_classify_missing_features() -> None:
    assert classify_missing(evidence(frames=None)) == "features_missing_after_d5"
    assert classify_missing(evidence(frames=0)) == "features_missing_after_d5"


def test_classify_alignment_not_emitted() -> None:
    assert classify_missing(evidence()) == "alignment_not_emitted_after_fresh_subset"


def test_classify_partial_intervals() -> None:
    assert classify_missing(evidence(words=0, phones=3)) == "word_intervals_missing_after_fresh_subset"
    assert classify_missing(evidence(words=3, phones=0)) == "phone_intervals_missing_after_fresh_subset"


def test_classify_unexpected_export_absence() -> None:
    assert classify_missing(evidence(words=3, phones=4)) == "unexpected_export_absence_requires_manual_db_audit"
