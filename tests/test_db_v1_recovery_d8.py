from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from build_db_v1_recovery_d8_feasibility_audit import (  # noqa: E402
    classify_alignment_missing,
    classify_no_run,
)


def test_healthy_alignment_missing_becomes_controlled_candidate() -> None:
    disposition, candidate = classify_alignment_missing(
        identity_verified=True,
        audio={"duration_seconds": 1.0, "active_span_seconds": 0.5},
    )
    assert disposition == "d9_controlled_parameter_retry_candidate"
    assert candidate is True


def test_identity_conflict_never_becomes_d9_candidate() -> None:
    disposition, candidate = classify_alignment_missing(
        identity_verified=False,
        audio={"duration_seconds": 2.0, "active_span_seconds": 1.0},
    )
    assert disposition == "hold_identity_conflict_not_d9"
    assert candidate is False


def test_sub_0_1_source_is_final_technical_exclusion() -> None:
    disposition, candidate = classify_no_run(
        source_seconds=0.04,
        observed_seconds=0.04,
        independent_seconds=0.04,
    )
    assert disposition == "final_technical_exclusion_source_fragment_too_short"
    assert candidate is False


def test_only_recovered_normal_audio_can_be_d9_candidate() -> None:
    disposition, candidate = classify_no_run(
        source_seconds=0.04,
        observed_seconds=0.04,
        independent_seconds=0.8,
    )
    assert disposition == "d9_reconstructed_audio_candidate"
    assert candidate is True


def test_numeral_normalization_is_not_an_identity_failure() -> None:
    # Orthographic numerals can differ from the frozen spoken-form LAB.
    assert "9월" != "구월"
    disposition, candidate = classify_alignment_missing(
        identity_verified=True,
        audio={"duration_seconds": 1.0, "active_span_seconds": 0.4},
    )
    assert disposition == "d9_controlled_parameter_retry_candidate"
    assert candidate is True
