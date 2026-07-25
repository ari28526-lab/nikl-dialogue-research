import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_stratified_mfa_review_bundle import (  # noqa: E402
    REVIEW_TIERS,
    intervals_semantically_equal,
    promote_staged_directory,
    verify_padded_wav,
    write_padded_wav,
    write_review_textgrid,
)
from realign_eojeol_merge_output import write_4tier  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class ReviewTextGridTests(unittest.TestCase):
    def test_interval_comparison_allows_textgrid_rounding_only(self):
        self.assertTrue(
            intervals_semantically_equal(
                [(0.0, 0.1, "p")],
                [(0.0, 0.10000000000000002, "p")],
            )
        )
        self.assertFalse(
            intervals_semantically_equal(
                [(0.0, 0.1, "p")],
                [(0.0, 0.11, "p")],
            )
        )

    def test_numeric_internal_slot_receives_original_form_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.TextGrid"
            output = root / "review.TextGrid"
            words = [
                (0.0, 0.1, ""),
                (0.1, 0.4, "무조건"),
                (0.4, 0.5, ""),
                (0.5, 0.9, "층으로"),
                (0.9, 1.0, ""),
            ]
            write_4tier(
                source,
                1.0,
                words,
                [(0.1, 0.9, "p")],
                [
                    (0.1, 0.4, "무조건"),
                    (0.4, 0.5, "1"),
                    (0.5, 0.7, "층"),
                    (0.7, 0.9, "으로"),
                ],
                "무조건 1층으로",
            )
            morph_status, warning = write_review_textgrid(
                source,
                output,
                utt_id="U1",
                form="무조건 1층으로",
                tagged="무조건/MAG 1/SN+층/NNG+으로/JKB",
                original_form="무조건 일 층으로",
                form_roman="M U J O G E O N | I L C E U N G E U R O",
                reference_form="무조건 일 층으로",
                reference_form_roman="M U J O G E O N | I L | C E U N G E U R O",
                pron_reference_hangul="무조건 일 층으로",
                pron_reference_roman="M U J O G E O N | I L | C E U N G E U R O",
                edge_padding_left_seconds=0.05,
                edge_padding_right_seconds=0.05,
            )
            self.assertEqual(morph_status, "labeled_word_slots")
            self.assertEqual(warning, "")

            duration, tiers = parse_mfa_textgrid(output)
            self.assertEqual(duration, 1.1)
            self.assertEqual(list(tiers), REVIEW_TIERS)
            morph_labels = [
                label for _, _, label in tiers["morph_analysis"] if label
            ]
            self.assertEqual(
                morph_labels,
                ["무조건/MAG", "1/SN+층/NNG+으로/JKB"],
            )
            info_labels = [
                label for _, _, label in tiers["utterance_info"] if label
            ]
            self.assertEqual(len(info_labels), 1)
            for marker in (
                "[UTT] U1",
                "[FORM] 무조건 1층으로",
                "[ORTH_R]",
                "[ORIG] 무조건 일 층으로",
                "[REF_FORM] 무조건 일 층으로",
                "[REF_ORTH_R]",
                "[RULE_H] 무조건 일 층으로",
                "[RULE_R]",
            ):
                self.assertIn(marker, info_labels[0])
            for intervals in tiers.values():
                self.assertEqual(intervals[0][0], 0.0)
                self.assertEqual(intervals[-1][1], 1.1)
                self.assertEqual(intervals[0][2], "")
                self.assertEqual(intervals[-1][2], "")

    def test_edge_padding_is_visible_when_alignment_touches_both_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.TextGrid"
            output = root / "review.TextGrid"
            write_4tier(
                source,
                1.0,
                [(0.0, 0.5, "첫"), (0.5, 1.0, "끝")],
                [(0.0, 0.5, "p"), (0.5, 1.0, "t")],
                [(0.0, 0.5, "첫"), (0.5, 1.0, "끝")],
                "첫 끝",
            )
            write_review_textgrid(
                source,
                output,
                utt_id="U2",
                form="첫 끝",
                tagged="첫/MM 끝/NNG",
                original_form="첫 끝",
                form_roman="C E O S | G G E U T",
                reference_form="첫 끝",
                reference_form_roman="C E O S | G G E U T",
                pron_reference_hangul="첟 끋",
                pron_reference_roman="C E T | G G E U T",
                edge_padding_left_seconds=0.05,
                edge_padding_right_seconds=0.05,
            )
            duration, tiers = parse_mfa_textgrid(output)
            self.assertEqual(duration, 1.1)
            for intervals in tiers.values():
                self.assertEqual(intervals[0], (0.0, 0.05, ""))
                self.assertEqual(intervals[-1], (1.05, 1.1, ""))

    def test_padded_wav_preserves_source_frames_between_silence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.wav"
            padded = root / "padded.wav"
            source_frames = b"\x01\x00" * 160
            with wave.open(str(source), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(source_frames)
            info = write_padded_wav(source, padded, 0.05)
            self.assertEqual(info["padding_frames"], 800)
            self.assertEqual(info["padding_seconds"], 0.05)
            self.assertEqual(info["source_duration_seconds"], 0.01)
            self.assertEqual(info["review_duration_seconds"], 0.11)
            verify_padded_wav(source, padded, 0.05)

    def test_verified_copy_fallback_removes_incomplete_only_after_hash_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / ".bundle.staging"
            output = root / "bundle"
            (staging / "2023").mkdir(parents=True)
            (staging / "2023" / "sample.txt").write_text(
                "점검", encoding="utf-8"
            )
            mode = promote_staged_directory(
                staging, output, force_copy_fallback=True
            )
            self.assertEqual(mode, "verified_copy_fallback")
            self.assertFalse(staging.exists())
            self.assertFalse((output / ".INCOMPLETE").exists())
            self.assertEqual(
                (output / "2023" / "sample.txt").read_text(encoding="utf-8"),
                "점검",
            )


if __name__ == "__main__":
    unittest.main()
