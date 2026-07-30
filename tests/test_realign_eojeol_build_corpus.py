import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import realign_eojeol_build_corpus as builder  # noqa: E402


class EojeolLabInputContractTests(unittest.TestCase):
    def test_non_hangul_drop_keeps_explicit_source_to_mfa_mapping(self):
        mapping = builder.form_to_lab_mapping("1 다음에 뭐야")

        self.assertEqual(builder.form_to_lab("1 다음에 뭐야"), "다음에 뭐야")
        self.assertEqual(
            [row["mfa_word_index"] for row in mapping],
            [None, 0, 1],
        )
        self.assertEqual(
            [row["included_in_mfa"] for row in mapping],
            [False, True, True],
        )
        self.assertEqual(mapping[0]["source_token"], "1")

    def test_unresolved_inventory_is_atomic_and_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unresolved.csv"
            rows = [
                {
                    "year": "2021",
                    "session_id": "SDRW2100000001",
                    "utt_id": "SDRW2100000001.1.1.1",
                    "form": "3시요",
                    "pron_reference_form": "3시요",
                    "pron_reference_source": "form_rule_prediction",
                    "pron_reference_status": "unresolved_symbol",
                    "lab_text": "시요",
                }
            ]

            builder.write_unresolved_inventory(path, rows)

            with path.open(encoding="utf-8-sig", newline="") as stream:
                saved = list(csv.DictReader(stream))
            self.assertEqual(saved, rows)
            self.assertFalse(Path(f"{path}.partial").exists())

    def test_reference_form_rewrites_stale_existing_lab(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            raw = root / "raw"
            wav_root = root / "wav"
            state = root / "state"
            year_dir = search / "2020"
            session = "SDRW2000000001"
            utt_id = f"{session}.1.1.1"
            year_dir.mkdir(parents=True)
            raw_year = raw / builder.YEAR_DIRS["2020"]
            raw_year.mkdir(parents=True)
            (raw_year / f"{session}.csv").write_text(
                "utt_id,form\n",
                encoding="utf-8",
            )
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success"}),
                encoding="utf-8",
            )
            with (year_dir / f"{session}.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "utt_id",
                        "form",
                        "pron_reference_form",
                        "pron_reference_source",
                        "pron_reference_status",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": utt_id,
                        "form": "무조건 1층으로",
                        "pron_reference_form": "무조건 일 층으로",
                        "pron_reference_source": (
                            "original_form_placeholder_resolution"
                        ),
                        "pron_reference_status": "resolved_original_form",
                    }
                )
            wav_dir = wav_root / "2020" / session
            wav_dir.mkdir(parents=True)
            (wav_dir / f"{utt_id}.wav").write_bytes(b"RIFF")
            lab_path = wav_dir / f"{utt_id}.lab"
            lab_path.write_text("무조건 층으로", encoding="utf-8")

            old_wav_root = builder.WAV_ROOT
            old_state_root = builder.STATE_ROOT
            old_raw = builder.RAW
            progress_path = state / "logs" / "lab_progress.jsonl"
            try:
                builder.WAV_ROOT = wav_root
                builder.STATE_ROOT = state
                builder.RAW = raw
                result = builder.build_year(
                    "2020",
                    search,
                    progress_jsonl=progress_path,
                )
                second = builder.build_year(
                    "2020",
                    search,
                    progress_jsonl=progress_path,
                )
            finally:
                builder.WAV_ROOT = old_wav_root
                builder.STATE_ROOT = old_state_root
                builder.RAW = old_raw

            self.assertEqual(
                lab_path.read_text(encoding="utf-8"),
                "무조건 일 층으로",
            )
            self.assertEqual(result["rewritten_mismatch"], 1)
            self.assertEqual(result["reference_form_changed"], 1)
            self.assertEqual(result["pron_reference_unresolved"], 0)
            self.assertEqual(second["input_contract_id"], result["input_contract_id"])
            self.assertTrue(
                (state / "done" / "2020.lab_input_done.json").is_file()
            )
            progress = [
                json.loads(line)
                for line in progress_path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(
                [item["event"] for item in progress],
                [
                    "lab_started",
                    "lab_progress",
                    "lab_completed",
                    "lab_reused",
                ],
            )
            self.assertEqual(progress[1]["rows_seen"], 1)
            self.assertEqual(progress[2]["status"], "passed")
            self.assertEqual(result["rows_seen"], 1)
            self.assertGreaterEqual(result["elapsed_seconds"], 0)

    def test_rejects_unpassed_search_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            search = Path(tmp)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "validation_failed"}),
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                builder.input_contract(search, "2020")

    def test_rejects_partial_session_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            raw = root / "raw"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success"}),
                encoding="utf-8",
            )
            (search / "2020" / "one.csv").write_text(
                "utt_id,form,pron_reference_form,"
                "pron_reference_source,pron_reference_status\n",
                encoding="utf-8",
            )
            raw_year = raw / builder.YEAR_DIRS["2020"]
            raw_year.mkdir(parents=True)
            for name in ("one.csv", "two.csv"):
                (raw_year / name).write_text(
                    "utt_id,form\n",
                    encoding="utf-8",
                )
            old_raw = builder.RAW
            try:
                builder.RAW = raw
                with self.assertRaises(RuntimeError):
                    builder.input_contract(search, "2020")
            finally:
                builder.RAW = old_raw

    def test_zero_usable_does_not_write_passed_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            raw = root / "raw"
            wav_root = root / "wav"
            state = root / "state"
            session = "SDRW2000000001"
            utt_id = f"{session}.1.1.1"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success"}),
                encoding="utf-8",
            )
            with (search / "2020" / f"{session}.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "utt_id",
                        "form",
                        "pron_reference_form",
                        "pron_reference_source",
                        "pron_reference_status",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": utt_id,
                        "form": "1",
                        "pron_reference_form": "1",
                        "pron_reference_source": "form_rule_prediction",
                        "pron_reference_status": "unresolved_symbol",
                    }
                )
            raw_year = raw / builder.YEAR_DIRS["2020"]
            raw_year.mkdir(parents=True)
            (raw_year / f"{session}.csv").write_text(
                "utt_id,form\n",
                encoding="utf-8",
            )
            wav_dir = wav_root / "2020" / session
            wav_dir.mkdir(parents=True)
            (wav_dir / f"{utt_id}.wav").write_bytes(b"RIFF")
            progress_path = state / "logs" / "lab_progress.jsonl"

            old_wav_root = builder.WAV_ROOT
            old_state_root = builder.STATE_ROOT
            old_raw = builder.RAW
            try:
                builder.WAV_ROOT = wav_root
                builder.STATE_ROOT = state
                builder.RAW = raw
                with self.assertRaisesRegex(
                    RuntimeError, "유효 lab 0건"
                ):
                    builder.build_year(
                        "2020",
                        search,
                        progress_jsonl=progress_path,
                    )
            finally:
                builder.WAV_ROOT = old_wav_root
                builder.STATE_ROOT = old_state_root
                builder.RAW = old_raw

            self.assertFalse(
                (state / "done" / "2020.lab_input_done.json").exists()
            )
            self.assertFalse(
                (state / "logs" / "lab_build_2020_latest.json").exists()
            )
            progress = [
                json.loads(line)
                for line in progress_path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(progress[-1]["event"], "lab_failed")
            self.assertEqual(
                progress[-1]["reason"], "usable_lab_zero"
            )

    def test_empty_reference_archives_stale_lab_instead_of_reusing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            raw = root / "raw"
            wav_root = root / "wav"
            state = root / "state"
            session = "SDRW2000000001"
            utt_id = f"{session}.1.1.9"
            (search / "2020").mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success"}),
                encoding="utf-8",
            )
            with (search / "2020" / f"{session}.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "utt_id",
                        "form",
                        "pron_reference_form",
                        "pron_reference_source",
                        "pron_reference_status",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": utt_id,
                        "form": "1",
                        "pron_reference_form": "1",
                        "pron_reference_source": "form_rule_prediction",
                        "pron_reference_status": "unresolved_symbol",
                    }
                )
                writer.writerow(
                    {
                        "utt_id": f"{session}.1.1.10",
                        "form": "정상",
                        "pron_reference_form": "정상",
                        "pron_reference_source": "form_rule_prediction",
                        "pron_reference_status": "resolved_form",
                    }
                )
            raw_year = raw / builder.YEAR_DIRS["2020"]
            raw_year.mkdir(parents=True)
            (raw_year / f"{session}.csv").write_text(
                "utt_id,form\n",
                encoding="utf-8",
            )
            wav_dir = wav_root / "2020" / session
            wav_dir.mkdir(parents=True)
            (wav_dir / f"{utt_id}.wav").write_bytes(b"RIFF")
            (wav_dir / f"{session}.1.1.10.wav").write_bytes(b"RIFF")
            stale_lab = wav_dir / f"{utt_id}.lab"
            stale_lab.write_text("잘못된 재사용", encoding="utf-8")

            old_wav_root = builder.WAV_ROOT
            old_state_root = builder.STATE_ROOT
            old_raw = builder.RAW
            try:
                builder.WAV_ROOT = wav_root
                builder.STATE_ROOT = state
                builder.RAW = raw
                result = builder.build_year("2020", search)
                inventory = Path(result["unresolved_symbol_inventory"])
                inventory.unlink()
                reused = builder.build_year("2020", search)
            finally:
                builder.WAV_ROOT = old_wav_root
                builder.STATE_ROOT = old_state_root
                builder.RAW = old_raw

            self.assertFalse(stale_lab.exists())
            archived = list(
                (state / "archive_stale_labs").rglob(f"{utt_id}.lab")
            )
            self.assertEqual(len(archived), 1)
            self.assertEqual(
                archived[0].read_text(encoding="utf-8"),
                "잘못된 재사용",
            )
            self.assertEqual(result["archived_empty_input_lab"], 1)
            self.assertEqual(reused["pron_reference_unresolved"], 1)
            self.assertTrue(inventory.is_file())
            with inventory.open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                inventory_rows = list(csv.DictReader(stream))
            self.assertEqual(
                [row["utt_id"] for row in inventory_rows], [utt_id]
            )


if __name__ == "__main__":
    unittest.main()
