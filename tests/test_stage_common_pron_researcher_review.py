from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))
import stage_common_pron_researcher_review as stage  # noqa: E402


FIELDS = (
    "target_token",
    "year",
    "utt_id",
    "session_id",
    "dialogue_id",
    "speaker_id",
    "form",
    "original_form",
    "pron_reference_hangul",
    "pron_reference_source",
    "pron_reference_status",
    "raw_json_match_status",
)


def write_occurrences(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(target: str, utt_id: str, session_id: str) -> dict[str, str]:
    return {
        "target_token": target,
        "year": "2023",
        "utt_id": utt_id,
        "session_id": session_id,
        "dialogue_id": session_id,
        "speaker_id": "SPK1",
        "form": f"{target} 예문",
        "original_form": f"{target} 예문",
        "pron_reference_hangul": f"{target} 예문",
        "pron_reference_source": "form_rule_prediction",
        "pron_reference_status": "resolved_form",
        "raw_json_match_status": "exact",
    }


class StageCommonPronResearcherReviewTests(unittest.TestCase):
    def test_stage_deduplicates_wav_and_preserves_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "release"
            wav_root = root / "wav"
            no_path = root / "no_path.csv"
            jamo = root / "jamo.csv"
            output = release / "03_review" / "bundle"
            utt1 = "SDRW2300000001.1.1.1"
            utt2 = "SDRW2300000002.1.1.2"
            session1 = "SDRW2300000001"
            session2 = "SDRW2300000002"
            for session, utt, byte in (
                (session1, utt1, b"a"),
                (session2, utt2, b"b"),
            ):
                path = wav_root / "2023" / session / f"{utt}.wav"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"RIFF" + byte * 60)
            write_occurrences(
                no_path,
                [row("읊는", utt1, session1), row("읊고", utt1, session1)],
            )
            write_occurrences(
                jamo,
                [row("외곬을", utt2, session2)],
            )

            manifest = stage.stage_bundle(
                no_path_occurrences=no_path,
                jamo_occurrences=jamo,
                wav_root=wav_root,
                release_root=release,
                output_root=output,
            )

            self.assertEqual(
                manifest["counts"],
                {
                    "target_occurrences": 3,
                    "unique_wavs": 2,
                    "source_mismatch_rows": 0,
                    "missing_or_invalid_wavs": 0,
                },
            )
            self.assertTrue(
                manifest["gates"][
                    "all_review_copies_hash_equal_source"
                ]
            )
            with (output / "review_occurrences.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({r["review_wav"] for r in rows}), 2)
            self.assertTrue(all(Path(r["review_wav"]).is_file() for r in rows))
            saved = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "success")

    def test_existing_different_review_wav_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "release"
            wav_root = root / "wav"
            no_path = root / "no_path.csv"
            jamo = root / "jamo.csv"
            output = release / "03_review" / "bundle"
            utt1 = "SDRW2300000001.1.1.1"
            utt2 = "SDRW2300000002.1.1.2"
            session1 = "SDRW2300000001"
            session2 = "SDRW2300000002"
            for session, utt in (
                (session1, utt1),
                (session2, utt2),
            ):
                path = wav_root / "2023" / session / f"{utt}.wav"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"RIFF" + b"a" * 60)
            write_occurrences(no_path, [row("읊고", utt1, session1)])
            write_occurrences(jamo, [row("외곬을", utt2, session2)])
            conflict = (
                output
                / "wav"
                / "2023"
                / session1
                / f"{utt1}.wav"
            )
            conflict.parent.mkdir(parents=True, exist_ok=True)
            conflict.write_bytes(b"RIFF" + b"x" * 60)

            with self.assertRaisesRegex(
                RuntimeError, "differs from source"
            ):
                stage.stage_bundle(
                    no_path_occurrences=no_path,
                    jamo_occurrences=jamo,
                    wav_root=wav_root,
                    release_root=release,
                    output_root=output,
                )


if __name__ == "__main__":
    unittest.main()
