import csv
import hashlib
import json
import sys
import tempfile
import unittest
import wave
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_stratified_mfa_pilot import (  # noqa: E402
    audit_session_durations,
    freeze_selected_search_sessions,
    select_year,
    validate_frozen_search_sessions,
)


def write_wav(path: Path, seconds: float = 0.1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\0\0" * round(16_000 * seconds))


def make_session(
    raw_dir: Path,
    wav_year: Path,
    morph_year: Path,
    session_id: str,
    speaker_id: str,
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(1, 4):
        utt_id = f"{session_id}.1.1.{index}"
        rows.append({
            "utt_id": utt_id,
            "speaker_id": speaker_id,
            "form": f"화자 발화 {index}",
            "tagged": "화자/NNG 발화/NNG",
            "n_morphs": "2",
        })
        write_wav(wav_year / session_id / f"{utt_id}.wav")
        morph = morph_year / session_id / f"{utt_id}.TextGrid"
        morph.parent.mkdir(parents=True, exist_ok=True)
        morph.write_text("synthetic", encoding="utf-8")
    with open(
        raw_dir / f"{session_id}.csv", "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class StratifiedPilotSelectionTests(unittest.TestCase):
    def test_frozen_search_session_reuse_rehashes_actual_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            selected = [
                {"utt_id": "S1.1", "session_id": "S1"},
                {"utt_id": "S1.2", "session_id": "S1"},
            ]
            rows = [
                {"utt_id": "S1.1", "pron_reference_form": "한 발화"},
                {"utt_id": "S1.2", "pron_reference_form": "두 발화"},
            ]
            frozen = freeze_selected_search_sessions(
                run_root=run_root,
                year="2020",
                fields=["utt_id", "pron_reference_form"],
                selected=selected,
                rows=rows,
            )
            canonical = json.dumps(
                frozen,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            payload = {
                "schema_version": (
                    "pilot_search_master_session_hashes.v1"
                ),
                "status": "success",
                "token_map_version": (
                    "source_eojeol_to_mfa_word.v1"
                ),
                "files": frozen,
                "file_count": 1,
                "row_count": 2,
                "aggregate_sha256": hashlib.sha256(
                    canonical.encode("utf-8")
                ).hexdigest(),
            }
            hashes = (
                run_root / "search_master" / "_session_hashes.json"
            )
            hashes.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            metadata = {"frozen_search_sessions": frozen}
            self.assertTrue(
                validate_frozen_search_sessions(run_root, metadata)
            )

            session_csv = run_root / frozen[0]["relative_path"]
            session_csv.write_text(
                session_csv.read_text(encoding="utf-8-sig")
                + "S1.3,변조\n",
                encoding="utf-8-sig",
            )
            self.assertFalse(
                validate_frozen_search_sessions(run_root, metadata)
            )

    def test_duration_audit_accepts_consistent_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav_year = Path(tmp)
            session = "SESSION"
            rows = []
            search = []
            for index, duration in enumerate((1.0, 1.5, 2.0, 2.5, 3.0), 1):
                utt = f"{session}.1.1.{index}"
                rows.append({"utt_id": utt})
                search.append({"utt_id": utt, "dur": str(duration)})
                write_wav(
                    wav_year / session / f"{utt}.wav", seconds=duration + 0.4
                )
            result = audit_session_durations(
                session_id=session,
                rows=rows,
                search_rows=search,
                wav_year=wav_year,
            )
            self.assertTrue(result["valid"], result["reason"])
            self.assertAlmostEqual(result["padding"], 0.4, places=3)

    def test_duration_audit_rejects_permuted_utterance_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav_year = Path(tmp)
            session = "SESSION"
            rows = []
            search = []
            durations = (1.0, 1.5, 2.0, 2.5, 3.0)
            for index, (csv_dur, wav_dur) in enumerate(
                zip(durations, reversed(durations)), 1
            ):
                utt = f"{session}.1.1.{index}"
                rows.append({"utt_id": utt})
                search.append({"utt_id": utt, "dur": str(csv_dur)})
                write_wav(wav_year / session / f"{utt}.wav", seconds=wav_dur)
            result = audit_session_durations(
                session_id=session,
                rows=rows,
                search_rows=search,
                wav_year=wav_year,
            )
            self.assertFalse(result["valid"])

    def test_selects_five_real_speakers_from_five_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / "raw"
            wav = base / "wav"
            morph = base / "morph"
            for index in range(1, 7):
                make_session(
                    raw,
                    wav,
                    morph,
                    f"SDRW200000{index:04d}",
                    f"SPK{index:02d}",
                )
            selected = select_year(
                year="2020",
                raw_dir=raw,
                wav_year=wav,
                morph_year=morph,
                search_year=None,
                utterances=10,
                speakers=5,
                seed="test-seed",
            )
            self.assertEqual(len(selected), 10)
            self.assertEqual(len({row["speaker_id"] for row in selected}), 5)
            self.assertEqual(len({row["session_id"] for row in selected}), 5)
            self.assertEqual(
                set(Counter(row["speaker_id"] for row in selected).values()),
                {2},
            )

    def test_fails_instead_of_silently_using_too_few_speakers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / "raw"
            wav = base / "wav"
            morph = base / "morph"
            for index in range(1, 5):
                make_session(
                    raw,
                    wav,
                    morph,
                    f"SDRW200000{index:04d}",
                    f"SPK{index:02d}",
                )
            with self.assertRaises(RuntimeError):
                select_year(
                    year="2020",
                    raw_dir=raw,
                    wav_year=wav,
                    morph_year=morph,
                    search_year=None,
                    utterances=10,
                    speakers=5,
                    seed="test-seed",
                )


if __name__ == "__main__":
    unittest.main()
