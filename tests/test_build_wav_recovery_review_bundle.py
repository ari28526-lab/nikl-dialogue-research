from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_wav_recovery_review_bundle import (  # noqa: E402
    build_contiguous_groups,
    risk_band,
    select_groups,
)


def make_rows(session: str, start: int, size: int, offset: int) -> list[dict[str, str]]:
    return [
        {
            "session": session,
            "target_utt_id": f"{session}.1.1.{start + index}",
            "source_utt_id": f"{session}.1.1.{start + index + offset}",
            "status": "remap_high_confidence",
            "block_length": str(size),
        }
        for index in range(size)
    ]


class ReviewBundleSelectionTests(unittest.TestCase):
    def test_build_contiguous_groups_splits_offset_and_session(self) -> None:
        rows = (
            make_rows("S1", 1, 3, -1)
            + make_rows("S1", 10, 4, 1)
            + make_rows("S2", 10, 5, -2)
        )
        groups = build_contiguous_groups(rows)
        self.assertEqual(
            [(item.session, item.offset, len(item.rows)) for item in groups],
            [("S1", -1, 3), ("S1", 1, 4), ("S2", -2, 5)],
        )

    def test_risk_band_boundaries(self) -> None:
        self.assertEqual(risk_band(3), "SHORT_3_10")
        self.assertEqual(risk_band(10), "SHORT_3_10")
        self.assertEqual(risk_band(11), "MEDIUM_11_80")
        self.assertEqual(risk_band(80), "MEDIUM_11_80")
        self.assertEqual(risk_band(81), "LONG_81_PLUS")

    def test_select_groups_returns_two_per_band(self) -> None:
        rows: list[dict[str, str]] = []
        for session, size in (
            ("S1", 3),
            ("S2", 8),
            ("S3", 20),
            ("S4", 60),
            ("S5", 100),
            ("S6", 200),
        ):
            rows.extend(make_rows(session, 1, size, -1))
        selected = select_groups(build_contiguous_groups(rows), per_band=2)
        self.assertEqual(len(selected), 6)
        self.assertEqual(
            [risk_band(item.block_length) for item in selected],
            [
                "SHORT_3_10",
                "SHORT_3_10",
                "MEDIUM_11_80",
                "MEDIUM_11_80",
                "LONG_81_PLUS",
                "LONG_81_PLUS",
            ],
        )


if __name__ == "__main__":
    unittest.main()
