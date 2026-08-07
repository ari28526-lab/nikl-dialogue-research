from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_SCRIPTS = ROOT / "scripts" / "python"
if str(PYTHON_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PYTHON_SCRIPTS))

from audit_dialogue_audio_structure import (  # noqa: E402
    Utterance,
    classify_session,
    parse_json_bytes,
    run_audit,
)


def row(number: int, start: float, end: float, note: str = "") -> Utterance:
    return Utterance(
        year="2022",
        session_id="SDRW2200000001",
        utt_id=f"SDRW2200000001.1.1.{number}",
        speaker_id=f"S{number % 2}",
        start=start,
        end=end,
        note=note,
    )


class DialogueAudioStructureTests(unittest.TestCase):
    def test_classification_separates_overlap_from_abut_review(self) -> None:
        flagged, summary = classify_session(
            [
                row(1, 0.0, 1.0),
                row(2, 1.0, 2.0),
                row(3, 1.8, 2.5, "발화겹침"),
                row(4, 3.0, 4.0),
            ],
            overlap_tolerance=0.001,
            abut_tolerance=0.020,
        )
        by_id = {item["utt_id"]: item for item in flagged}
        self.assertEqual(
            by_id["SDRW2200000001.1.1.1"]["evidence_class"],
            "audio_review_required",
        )
        self.assertEqual(
            by_id["SDRW2200000001.1.1.1"]["reason_codes"],
            "boundary_abut_review",
        )
        self.assertIn(
            "source_time_overlap",
            by_id["SDRW2200000001.1.1.2"]["reason_codes"],
        )
        self.assertEqual(
            by_id["SDRW2200000001.1.1.3"]["evidence_class"],
            "confirmed_source_overlap",
        )
        self.assertIn(
            "source_note_overlap",
            by_id["SDRW2200000001.1.1.3"]["reason_codes"],
        )
        self.assertEqual(summary["confirmed_overlap_union_count"], 2)
        self.assertEqual(summary["boundary_abut_member_count"], 2)
        self.assertTrue(
            all(item["researcher_decision"] == "pending" for item in flagged)
        )

    def test_long_interval_overlap_marks_every_member(self) -> None:
        flagged, summary = classify_session(
            [
                row(1, 0.0, 10.0),
                row(2, 1.0, 2.0),
                row(3, 3.0, 4.0),
                row(4, 11.0, 12.0),
            ],
            overlap_tolerance=0.001,
            abut_tolerance=0.020,
        )
        overlap_ids = {
            item["utt_id"]
            for item in flagged
            if item["time_overlap"] == "true"
        }
        self.assertEqual(
            overlap_ids,
            {
                "SDRW2200000001.1.1.1",
                "SDRW2200000001.1.1.2",
                "SDRW2200000001.1.1.3",
            },
        )
        self.assertEqual(summary["time_overlap_member_count"], 3)

    def test_invalid_source_time_is_preserved_as_pending_exclusion(self) -> None:
        payload = {
            "document": [
                {
                    "utterance": [
                        {
                            "id": "SDRW2200000001.1.1.1",
                            "speaker_id": "S1",
                            "start": 2.0,
                            "end": 1.0,
                            "note": "",
                        }
                    ]
                }
            ]
        }
        rows = parse_json_bytes(
            year="2022",
            source=Path("bad.json"),
            raw=json.dumps(payload).encode("utf-8"),
        )
        flagged, summary = classify_session(
            rows,
            overlap_tolerance=0.001,
            abut_tolerance=0.020,
        )
        self.assertEqual(summary["source_time_invalid_count"], 1)
        self.assertEqual(flagged[0]["reason_codes"], "source_time_invalid")
        self.assertEqual(
            flagged[0]["recommended_scope"],
            "exclude_alignment_and_acoustic_analysis",
        )
        self.assertEqual(flagged[0]["researcher_decision"], "pending")

    def test_run_is_deterministic_and_never_approves(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "source"
            source.mkdir()
            payload = {
                "document": [
                    {
                        "utterance": [
                            {
                                "id": "SDRW2200000001.1.1.1",
                                "speaker_id": "S1",
                                "start": 0.0,
                                "end": 1.0,
                                "note": "",
                            },
                            {
                                "id": "SDRW2200000001.1.1.2",
                                "speaker_id": "S2",
                                "start": 0.8,
                                "end": 1.5,
                                "note": "발화겹침",
                            },
                        ]
                    }
                ]
            }
            (source / "SDRW2200000001.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            first = run_audit(
                year="2022", json_root=source, output_root=temp / "first"
            )
            second = run_audit(
                year="2022", json_root=source, output_root=temp / "second"
            )
            self.assertFalse(first["policy"]["automatic_exclusion_performed"])
            self.assertEqual(first["status"], "pending_researcher_policy_review")
            self.assertEqual(
                first["outputs"]["utterance_flags"]["sha256"],
                second["outputs"]["utterance_flags"]["sha256"],
            )
            with gzip.open(
                temp / "first" / "01_UTTERANCE_STRUCTURAL_FLAGS.csv.gz",
                "rt",
                encoding="utf-8-sig",
            ) as stream:
                text = stream.read()
            self.assertIn("pending", text)
            self.assertNotIn("approved", text)


if __name__ == "__main__":
    unittest.main()
