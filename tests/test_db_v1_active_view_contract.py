from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from materialize_db_v1_active_view_contract import resolve_rows  # noqa: E402


class ActiveViewContractTests(unittest.TestCase):
    def test_curated_pointer_wins_and_non_curated_keeps_base(self):
        statuses = [
            {
                "year": 2020,
                "utt_id": "U1",
                "session_id": "S1",
                "base_primary_status": "post_mfa_technical_exclusion",
                "base_status_family": "technical_exclusion",
                "base_reason_codes_json": "[]",
                "proposed_recovery_status": "curated_manual_word_overlay_pending_phone",
                "proposed_recovery_family": "curated_recovery",
                "proposed_visibility": "curated_annotation_candidate",
                "outcome_source": "D9+D10",
                "evidence_path": "curated.TextGrid",
                "evidence_sha256": "a" * 64,
                "phone_layer_status": "d9_reference_only_not_adopted",
            },
            {
                "year": 2020,
                "utt_id": "U2",
                "session_id": "S2",
                "base_primary_status": "post_mfa_technical_exclusion",
                "base_status_family": "technical_exclusion",
                "base_reason_codes_json": "[]",
                "proposed_recovery_status": "excluded_noise_diagnostic_preserved",
                "proposed_recovery_family": "technical_exclusion",
                "proposed_visibility": "diagnostic_only",
                "outcome_source": "D7",
                "evidence_path": "diagnostic.TextGrid",
                "evidence_sha256": "b" * 64,
                "phone_layer_status": "diagnostic_reference_only",
            },
        ]
        pointers = [
            {
                "year": 2020,
                "utt_id": "U1",
                "active_annotation_source": "curated",
                "active_annotation_revision": "R1",
                "active_textgrid_path": "curated.TextGrid",
                "active_textgrid_sha256": "a" * 64,
                "manual_edit_count": 1,
                "phone_layer_status": "d9_reference_only_not_adopted",
                "phoneme_layer_status": "pending_curated_alignment",
                "morph_enrichment_status": "pending_rebuild_from_curated_transcript",
            }
        ]
        snapshots = [
            {
                "year": 2020,
                "utt_id": "U1",
                "active_textgrid_sha256": "a" * 64,
                "final_transcript": "영화 잘",
                "orth_roman_v2": "YEO ng _ H WA | J A l",
            }
        ]
        rows = resolve_rows(
            status_rows=statuses,
            pointer_rows=pointers,
            snapshot_rows=snapshots,
        )
        by_id = {row["utt_id"]: row for row in rows}
        self.assertEqual(by_id["U1"]["active_annotation_source"], "curated")
        self.assertEqual(by_id["U1"]["active_transcript"], "영화 잘")
        self.assertEqual(by_id["U2"]["active_annotation_source"], "base")
        self.assertEqual(by_id["U2"]["active_textgrid_path"], "")
        self.assertEqual(
            by_id["U2"]["recovery_evidence_path"], "diagnostic.TextGrid"
        )

    def test_pointer_snapshot_set_mismatch_fails(self):
        with self.assertRaisesRegex(RuntimeError, "pointer/snapshot"):
            resolve_rows(
                status_rows=[],
                pointer_rows=[{"year": 2020, "utt_id": "U1"}],
                snapshot_rows=[],
            )


if __name__ == "__main__":
    unittest.main()
