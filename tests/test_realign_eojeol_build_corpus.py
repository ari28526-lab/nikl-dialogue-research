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
            try:
                builder.WAV_ROOT = wav_root
                builder.STATE_ROOT = state
                builder.RAW = raw
                result = builder.build_year("2020", search)
                second = builder.build_year("2020", search)
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


if __name__ == "__main__":
    unittest.main()
