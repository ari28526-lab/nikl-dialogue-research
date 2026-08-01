import csv
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from audit_mfa_year_readiness import (  # noqa: E402
    audit_session_durations,
    audit_year,
    main,
)


def write_wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16_000)
        wav_file.writeframes(b"\0\0" * round(16_000 * seconds))


class AuditMfaYearReadinessTests(unittest.TestCase):
    def test_detects_missing_tiny_stale_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            year_dir = search / "2021"
            session_dir = wav_root / "2021" / "S1"
            year_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)

            header = [
                "utt_id",
                "form",
                "pron_reference_form",
                "pron_reference_source",
                "pron_reference_status",
                "sex",
                "dur",
            ]
            rows = [
                [
                    "S1.1", "가 나", "가 나", "form",
                    "resolved_form", "여성", "1.0",
                ],
                [
                    "S1.2", "1", "1", "form",
                    "unresolved_symbol", "미상", "1.0",
                ],
                [
                    "S1.3", "다", "다", "form",
                    "resolved_form", "남성", "1.0",
                ],
                [
                    "S1.4", "라", "라", "form",
                    "resolved_form", "여성", "1.0",
                ],
            ]
            with open(year_dir / "S1.csv", "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)

            write_wav(session_dir / "S1.1.wav", 1.0)
            (session_dir / "S1.1.lab").write_text("가 나", encoding="utf-8")
            write_wav(session_dir / "S1.2.wav", 1.0)
            (session_dir / "S1.2.lab").write_text("stale", encoding="utf-8")
            (session_dir / "S1.4.wav").write_bytes(b"x" * 20)
            (session_dir / "S1.4.lab").write_text("wrong", encoding="utf-8")
            (session_dir / "EXTRA.wav").write_bytes(b"x" * 100)
            (session_dir / "EXTRA.lab").write_text("extra", encoding="utf-8")

            result = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                known_pcm=None,
            )
            counts = result["counts"]
            self.assertEqual(counts["search_rows"], 4)
            self.assertEqual(counts["speaker_missing"], 1)
            self.assertEqual(counts["pron_reference_unresolved"], 1)
            self.assertEqual(counts["wav_missing"], 1)
            self.assertEqual(counts["empty_reference_form"], 1)
            self.assertEqual(counts["stale_lab_for_empty_input"], 1)
            self.assertEqual(counts["wav_too_small"], 1)
            self.assertEqual(counts["lab_content_match"], 1)
            self.assertEqual(counts["lab_content_mismatch"], 1)
            self.assertEqual(counts["lab_not_expected_with_wav"], 2)
            self.assertFalse(result["gates"]["all_expected_labs_ready"])
            self.assertFalse(result["gates"]["no_dangerous_unexpected_labs"])
            self.assertFalse(result["gates"]["no_fatal_tiny_wav"])
            self.assertFalse(
                result["gates"]["csv_wav_duration_correspondence"]
            )
            self.assertFalse(result["all_gates_pass"])

    def test_duration_gate_rejects_permuted_utterance_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "S1"
            session_dir.mkdir()
            rows = []
            durations = (1.0, 1.5, 2.0, 2.5, 3.0)
            for index, (csv_duration, wav_duration) in enumerate(
                zip(durations, reversed(durations)), 1
            ):
                utt_id = f"S1.{index}"
                rows.append({"utt_id": utt_id, "dur": str(csv_duration)})
                write_wav(
                    session_dir / f"{utt_id}.wav",
                    wav_duration,
                )
            entries = {
                path.name: path.stat().st_size
                for path in session_dir.iterdir()
            }
            result = audit_session_durations(
                session="S1",
                rows=rows,
                session_dir=session_dir,
                entries=entries,
                executor=None,
            )
            self.assertFalse(result["valid"])
            self.assertGreater(result["counts"]["residual_mismatch"], 0)
            self.assertTrue(
                any(
                    issue["issue"] == "duration_residual_mismatch"
                    for issue in result["issues"]
                )
            )

    def test_year_gate_rejects_even_one_residual_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            year_dir = search / "2021"
            session_dir = wav_root / "2021" / "S1"
            year_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            fields = [
                "utt_id", "form", "pron_reference_form",
                "pron_reference_source", "pron_reference_status", "sex", "dur",
            ]
            rows = []
            for index in range(1, 101):
                utt_id = f"S1.{index}"
                rows.append(
                    {
                        "utt_id": utt_id,
                        "form": "가",
                        "pron_reference_form": "가",
                        "pron_reference_source": "form",
                        "pron_reference_status": "resolved_form",
                        "sex": "여성",
                        "dur": "1.0",
                    }
                )
                write_wav(
                    session_dir / f"{utt_id}.wav",
                    2.0 if index == 50 else 1.0,
                )
                (session_dir / f"{utt_id}.lab").write_text(
                    "가", encoding="utf-8"
                )
            with (year_dir / "S1.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            result = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                known_pcm=None,
            )

            self.assertEqual(
                result["counts"].get("duration_sessions_failed", 0), 0
            )
            self.assertEqual(result["counts"]["duration_residual_mismatch"], 1)
            self.assertFalse(
                result["gates"]["csv_wav_duration_correspondence"]
            )

    def test_rejects_physically_impossible_text_duration_without_logging_text(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            year_dir = search / "2021"
            session_dir = wav_root / "2021" / "S1"
            year_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            fields = [
                "utt_id",
                "form",
                "pron_reference_form",
                "pron_reference_source",
                "pron_reference_status",
                "sex",
                "dur",
            ]
            impossible_text = "가" * 20
            with open(
                year_dir / "S1.csv",
                "w",
                encoding="utf-8",
                newline="",
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "S1.1",
                        "form": impossible_text,
                        "pron_reference_form": impossible_text,
                        "pron_reference_source": "form",
                        "pron_reference_status": "resolved_form",
                        "sex": "여성",
                        "dur": "0.4",
                    }
                )
            write_wav(session_dir / "S1.1.wav", 0.4)
            (session_dir / "S1.1.lab").write_text(
                impossible_text, encoding="utf-8"
            )

            result = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                known_pcm=None,
            )

            self.assertTrue(
                result["gates"]["csv_wav_duration_correspondence"]
            )
            self.assertFalse(
                result["gates"][
                    "source_segment_text_duration_plausible"
                ]
            )
            self.assertEqual(
                result["counts"][
                    "source_segment_text_duration_impossible"
                ],
                1,
            )
            issue = next(
                item
                for item in result["issue_inventory"]
                if item["issue"]
                == "source_segment_text_duration_impossible"
            )
            self.assertEqual(issue["hangul_syllables"], 20)
            self.assertEqual(
                issue["hangul_syllables_per_second"], 50.0
            )
            self.assertNotIn(impossible_text, str(issue))
            self.assertTrue(result["execution_gates_pass"])
            self.assertFalse(result["analysis_ready_gates_pass"])

    def test_approved_alignment_exclusion_is_not_an_active_gate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            year_dir = search / "2021"
            session_dir = wav_root / "2021" / "S1"
            year_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            fields = [
                "utt_id", "form", "pron_reference_form",
                "pron_reference_source", "pron_reference_status", "sex", "dur",
            ]
            with (year_dir / "S1.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "utt_id": "S1.good", "form": "가",
                            "pron_reference_form": "가",
                            "pron_reference_source": "form",
                            "pron_reference_status": "resolved_form",
                            "sex": "여성", "dur": "1.0",
                        },
                        {
                            "utt_id": "S1.bad", "form": "가" * 20,
                            "pron_reference_form": "가" * 20,
                            "pron_reference_source": "form",
                            "pron_reference_status": "resolved_form",
                            "sex": "여성", "dur": "0.4",
                        },
                    ]
                )
            write_wav(session_dir / "S1.good.wav", 1.0)
            (session_dir / "S1.good.lab").write_text("가", encoding="utf-8")
            (session_dir / "S1.bad.wav").write_bytes(b"")
            (session_dir / "S1.bad.lab").write_text("가", encoding="utf-8")

            result = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                known_pcm=None,
                approved_alignment_exclusions={"S1.bad"},
            )
            self.assertEqual(result["counts"]["approved_alignment_excluded"], 1)
            self.assertEqual(result["counts"].get("wav_too_small", 0), 0)
            self.assertEqual(
                result["counts"].get(
                    "source_segment_text_duration_impossible", 0
                ),
                0,
            )
            self.assertEqual(
                result["counts"]["approved_alignment_active_pair"], 1
            )
            self.assertFalse(
                result["gates"]["approved_alignment_inputs_inactive"]
            )
            self.assertFalse(result["analysis_ready_gates_pass"])

    def test_fully_approved_missing_session_is_not_an_active_gate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            year_dir = search / "2021"
            year_dir.mkdir(parents=True)
            fields = [
                "utt_id", "form", "pron_reference_form",
                "pron_reference_source", "pron_reference_status", "sex", "dur",
            ]
            with (year_dir / "S1.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "S1.1",
                        "form": "가",
                        "pron_reference_form": "가",
                        "pron_reference_source": "form",
                        "pron_reference_status": "resolved_form",
                        "sex": "여성",
                        "dur": "1.0",
                    }
                )

            result = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=root / "wav",
                compare_lab_content=True,
                known_pcm=None,
                approved_alignment_exclusions={"S1.1"},
            )

            self.assertEqual(
                result["counts"]["duration_sessions_fully_excluded"], 1
            )
            self.assertTrue(result["gates"]["session_folders_present"])
            self.assertTrue(
                result["gates"]["csv_wav_duration_correspondence"]
            )
            self.assertTrue(
                result["gates"]["approved_alignment_inputs_inactive"]
            )
            self.assertTrue(result["analysis_ready_gates_pass"])

    def test_morph_source_missing_is_preflight_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            morph_root = root / "morph"
            year_dir = search / "2021"
            session_dir = wav_root / "2021" / "S1"
            morph_dir = morph_root / "2021" / "S1"
            year_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            morph_dir.mkdir(parents=True)

            fields = [
                "utt_id",
                "form",
                "pron_reference_form",
                "pron_reference_source",
                "pron_reference_status",
                "sex",
                "dur",
            ]
            rows = []
            for index, duration in enumerate((1.0, 1.5, 2.0), 1):
                utt_id = f"S1.{index}"
                rows.append(
                    {
                        "utt_id": utt_id,
                        "form": "가",
                        "pron_reference_form": "가",
                        "pron_reference_source": "form",
                        "pron_reference_status": "resolved_form",
                        "sex": "여성",
                        "dur": str(duration),
                    }
                )
                write_wav(
                    session_dir / f"{utt_id}.wav",
                    duration + 0.4,
                )
                (session_dir / f"{utt_id}.lab").write_text(
                    "가", encoding="utf-8"
                )
                if index < 3:
                    (morph_dir / f"{utt_id}.TextGrid").write_text(
                        "nonempty", encoding="utf-8"
                    )
            with open(
                year_dir / "S1.csv",
                "w",
                encoding="utf-8",
                newline="",
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            result = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                morph_textgrid_root=morph_root,
                known_pcm=None,
            )
            self.assertTrue(
                result["gates"]["csv_wav_duration_correspondence"]
            )
            self.assertEqual(result["counts"]["morph_source_missing"], 1)
            self.assertFalse(result["gates"]["all_morph_sources_ready"])
            self.assertEqual(
                result["morph_source_issues"][0]["utt_id"], "S1.3"
            )

    def test_main_is_strict_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            output = root / "audit.json"
            year_dir = search / "2021"
            year_dir.mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                '{"status":"success"}', encoding="utf-8"
            )
            fields = [
                "utt_id",
                "form",
                "pron_reference_form",
                "pron_reference_source",
                "pron_reference_status",
                "sex",
                "dur",
            ]
            with open(
                year_dir / "S1.csv",
                "w",
                encoding="utf-8",
                newline="",
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "S1.1",
                        "form": "가",
                        "pron_reference_form": "가",
                        "pron_reference_source": "form",
                        "pron_reference_status": "resolved_form",
                        "sex": "여성",
                        "dur": "1.0",
                    }
                )
            with patch(
                "sys.argv",
                [
                    "audit_mfa_year_readiness.py",
                    "--years",
                    "2021",
                    "--search-master-root",
                    str(search),
                    "--wav-root",
                    str(wav_root),
                    "--skip-morph-source-audit",
                    "--output",
                    str(output),
                ],
            ):
                self.assertEqual(main(), 1)

    def test_known_pcm_evidence_splits_execution_and_analysis_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            wav_root = root / "wav"
            morph_root = root / "morph"
            year_dir = search / "2021"
            session_dir = wav_root / "2021" / "S1"
            (morph_root / "2021").mkdir(parents=True)
            year_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            fields = [
                "utt_id",
                "form",
                "pron_reference_form",
                "pron_reference_source",
                "pron_reference_status",
                "sex",
                "dur",
            ]
            with open(
                year_dir / "S1.csv",
                "w",
                encoding="utf-8",
                newline="",
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "S1.1",
                        "form": "가",
                        "pron_reference_form": "가",
                        "pron_reference_source": "form",
                        "pron_reference_status": "resolved_form",
                        "sex": "여성",
                        "dur": "1.0",
                    }
                )
            write_wav(session_dir / "S1.1.wav", 1.0)
            (session_dir / "S1.1.lab").write_text("가", encoding="utf-8")

            excluded = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                morph_textgrid_root=morph_root,
                known_pcm_records={
                    "S1.1": {
                        "category": "원본짧음",
                        "pcm_sec": "0.1",
                    }
                },
            )
            self.assertFalse(
                excluded["gates"]["all_morph_sources_ready"]
            )
            self.assertTrue(excluded["execution_gates_pass"])
            self.assertTrue(excluded["analysis_ready_gates_pass"])
            self.assertEqual(
                excluded["counts"]["morph_source_excluded_unusable"], 1
            )

            recoverable = audit_year(
                year="2021",
                search_master_root=search,
                wav_root=wav_root,
                compare_lab_content=True,
                morph_textgrid_root=morph_root,
                known_pcm_records={
                    "S1.1": {
                        "category": "원본정상",
                        "pcm_sec": "1.0",
                    }
                },
            )
            self.assertTrue(recoverable["execution_gates_pass"])
            self.assertFalse(recoverable["analysis_ready_gates_pass"])
            self.assertEqual(
                recoverable["counts"][
                    "morph_source_recovery_candidate"
                ],
                1,
            )


if __name__ == "__main__":
    unittest.main()
