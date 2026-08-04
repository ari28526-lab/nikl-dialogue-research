import csv
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from research_textgrid import write_research_textgrid  # noqa: E402
from research_textgrid_v2 import (  # noqa: E402
    BASE_TIERS,
    STITCHED_TIERS,
    boundary_roundoff_tolerance,
    build_base_tier_data_from_intervals,
    normalize_interval_bounds,
    validate_base_textgrid,
    validate_base_textgrid_from_intervals,
    write_base_textgrid,
    write_base_textgrid_from_intervals,
    write_stitched_review,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class ResearchTextGridV2Tests(unittest.TestCase):
    def row(self, uid="U1", form="혹시 요즘", speaker="S1"):
        return {
            "utt_id": uid,
            "session_id": "SESSION1",
            "speaker_id": speaker,
            "form": form,
            "form_roman": "H O k _ S I | YO _ J EU m",
            "tagged": "혹시/MAG 요즘/NNG",
            "align_warn": "",
        }

    def mapper(self, phone):
        return {"h": "H", "m": "M"}[phone]

    def write_source(self, path: Path, row, duration=0.2):
        write_research_textgrid(
            path,
            duration=duration,
            words=[(0.0, 0.05, ""), (0.05, 0.1, "혹시"), (0.1, 0.15, "요즘"), (0.15, 0.2, "")],
            phones=[(0.0, 0.05, ""), (0.05, 0.1, "h"), (0.1, 0.15, "m"), (0.15, 0.2, "")],
            search_row=row,
        )

    def write_wav(self, path: Path, duration=0.2):
        frames = round(16000 * duration)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x01\x00" * frames)

    def test_single_six_tier_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.TextGrid"
            output = root / "output.TextGrid"
            row = self.row()
            self.write_source(source, row)
            result = write_base_textgrid(
                output,
                source_textgrid=source,
                row=row,
                phone_mapper=self.mapper,
            )
            self.assertTrue(result["valid"])
            self.assertTrue(result["words_unchanged"])
            self.assertTrue(result["phones_mfa_unchanged"])
            self.assertTrue(result["phoneme_boundaries_equal_phones_mfa"])
            duration, tiers = parse_mfa_textgrid(output)
            self.assertEqual(duration, 0.2)
            self.assertEqual(list(tiers), BASE_TIERS)
            self.assertEqual(tiers["phoneme_r_auto"][1][2], "H")
            self.assertEqual(tiers["phoneme_r_auto"][2][2], "M")
            self.assertEqual(
                [row[2] for row in tiers["morph_analysis_utt"] if row[2]],
                ["혹시/MAG | 요즘/NNG"],
            )
            checked = validate_base_textgrid(
                output,
                source_textgrid=source,
                row=row,
                phone_mapper=self.mapper,
            )
            self.assertTrue(checked["speech_tier_boundaries_equal"])

    def test_direct_interval_six_tier_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "direct.TextGrid"
            row = self.row()
            words = [
                (0.0, 0.05, ""),
                (0.05, 0.1, "혹시"),
                (0.1, 0.15, "요즘"),
                (0.15, 0.2, ""),
            ]
            phones = [
                (0.0, 0.05, ""),
                (0.05, 0.1, "h"),
                (0.1, 0.15, "m"),
                (0.15, 0.2, ""),
            ]
            result = write_base_textgrid_from_intervals(
                output,
                duration=0.2,
                words=words,
                phones=phones,
                row=row,
                phone_mapper=self.mapper,
            )
            self.assertTrue(result["valid"])
            self.assertFalse(result["word_span_fallback"])
            checked = validate_base_textgrid_from_intervals(
                output,
                duration=0.2,
                words=words,
                phones=phones,
                row=row,
                phone_mapper=self.mapper,
            )
            self.assertTrue(checked["valid"])
            _duration, tiers = parse_mfa_textgrid(output)
            self.assertEqual(list(tiers), BASE_TIERS)
            self.assertEqual(
                [label for _, _, label in tiers["utterance_orth_r"] if label],
                ["H O k _ S I | YO _ J EU m"],
            )

    def test_out_of_range_interval_is_not_silently_clamped(self):
        with self.assertRaisesRegex(ValueError, "0-xmax 범위"):
            build_base_tier_data_from_intervals(
                duration=0.2,
                words=[(0.05, 0.20001, "혹시")],
                phones=[(0.05, 0.2, "h")],
                row=self.row(),
                phone_mapper=self.mapper,
            )

    def test_float32_terminal_roundoff_is_explicitly_normalized(self):
        duration = 153.96
        float32_end = 153.9600067138672
        self.assertLess(
            float32_end - duration,
            boundary_roundoff_tolerance(duration),
        )
        begin, end = normalize_interval_bounds(0.45, float32_end, duration)
        self.assertEqual(begin, 0.45)
        self.assertEqual(end, duration)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "float32_roundoff.TextGrid"
            write_base_textgrid_from_intervals(
                output,
                duration=duration,
                words=[(0.45, float32_end, "혹시")],
                phones=[(0.45, float32_end, "h")],
                row=self.row(form="혹시"),
                phone_mapper=self.mapper,
            )
            parsed_duration, tiers = parse_mfa_textgrid(output)
            self.assertEqual(parsed_duration, duration)
            self.assertEqual(tiers["words"][-1][1], duration)

    def test_mixed_orthography_is_searchable_in_orth_roman_tier(self):
        row = self.row(form="2사람이")
        row["form_roman"] = "∅"
        row["tagged"] = "2/SN+사람/NNG+이/JKS"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "mixed.TextGrid"
            write_base_textgrid_from_intervals(
                output,
                duration=0.2,
                words=[(0.05, 0.15, "두사람이")],
                phones=[(0.05, 0.15, "h")],
                row=row,
                phone_mapper=self.mapper,
            )
            _duration, tiers = parse_mfa_textgrid(output)
            labels = [
                label for _begin, _end, label
                in tiers["utterance_orth_r"] if label
            ]
            self.assertEqual(labels, ["⟨2⟩ _ S A _ R A m _ I"])

    def test_control_character_in_label_is_rejected(self):
        row = self.row(form="혹시\n요즘")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "제어문자"):
                write_base_textgrid_from_intervals(
                    Path(tmp) / "must_not_exist.TextGrid",
                    duration=0.2,
                    words=[(0.05, 0.15, "혹시")],
                    phones=[(0.05, 0.15, "h")],
                    row=row,
                    phone_mapper=self.mapper,
                )

    def test_stitched_review_contract_and_inverse_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = []
            for index in (1, 2):
                uid = f"U{index}"
                row = self.row(uid=uid, form=f"발화 {index}")
                tg = root / f"{uid}.TextGrid"
                wav = root / f"{uid}.wav"
                self.write_source(tg, row)
                self.write_wav(wav)
                sources.append({"wav": wav, "textgrid": tg, "row": row})
            stitched_wav = root / "stitched.wav"
            stitched_tg = root / "stitched.TextGrid"
            manifest = root / "stitched_manifest.csv"
            result = write_stitched_review(
                destination_wav=stitched_wav,
                destination_textgrid=stitched_tg,
                destination_manifest=manifest,
                sources=sources,
                phone_mapper=self.mapper,
                gap_seconds=0.05,
                stitched_id="TEST",
                alignment_contract_id="TEST_CONTRACT",
                selection_query_id="TEST_QUERY",
            )
            self.assertTrue(result["valid"])
            self.assertFalse(result["koina_cross_seam_allowed"])
            self.assertAlmostEqual(result["duration"], 0.45, places=6)
            _duration, tiers = parse_mfa_textgrid(stitched_tg)
            self.assertEqual(list(tiers), STITCHED_TIERS)
            self.assertEqual(
                [label for _, _, label in tiers["source_utt_id"] if label],
                ["U1", "U2"],
            )
            gap = [
                row
                for row in tiers["source_utt_id"]
                if abs(row[0] - 0.2) < 1e-6 and abs(row[1] - 0.25) < 1e-6
            ]
            self.assertEqual(gap, [(0.2, 0.25, "")])
            with manifest.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[1]["source_time_rule"], "source_time=stitched_time-0.250000")
            self.assertEqual(rows[0]["koina_cross_seam_allowed"], "False")


if __name__ == "__main__":
    unittest.main()
