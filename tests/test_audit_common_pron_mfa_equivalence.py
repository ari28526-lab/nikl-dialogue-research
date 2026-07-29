import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import audit_common_pron_mfa_equivalence as audit  # noqa: E402


def write_textgrid(path: Path, second_phone: str = "a") -> None:
    tier_specs = [
        ("words", [(0.0, 0.5, ""), (0.5, 1.0, "가")]),
        (
            "phones",
            [(0.0, 0.5, ""), (0.5, 0.7, "k"), (0.7, 1.0, second_phone)],
        ),
        ("morphemes", [(0.0, 0.5, ""), (0.5, 1.0, "가")]),
        ("utterance", [(0.0, 0.5, ""), (0.5, 1.0, "가")]),
    ]
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        "xmax = 1",
        "tiers? <exists>",
        "size = 4",
        "item []:",
    ]
    for tier_index, (name, intervals) in enumerate(tier_specs, 1):
        lines.extend(
            [
                f"    item [{tier_index}]:",
                '        class = "IntervalTier"',
                f'        name = "{name}"',
                "        xmin = 0",
                "        xmax = 1",
                f"        intervals: size = {len(intervals)}",
            ]
        )
        for index, (start, end, label) in enumerate(intervals, 1):
            lines.extend(
                [
                    f"        intervals [{index}]:",
                    f"            xmin = {start}",
                    f"            xmax = {end}",
                    f'            text = "{label}"',
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE word (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            word_type TEXT NOT NULL
        );
        CREATE TABLE pronunciation (
            id INTEGER PRIMARY KEY,
            pronunciation TEXT NOT NULL,
            word_id INTEGER NOT NULL
        );
        CREATE TABLE utterance (id INTEGER PRIMARY KEY);
        CREATE TABLE word_interval (id INTEGER PRIMARY KEY);
        CREATE TABLE phone_interval (id INTEGER PRIMARY KEY);
        CREATE TABLE phone (
            id INTEGER PRIMARY KEY,
            phone TEXT NOT NULL
        );
        INSERT INTO word VALUES (1, '가', 'speech');
        INSERT INTO word VALUES (2, '나', 'speech');
        INSERT INTO pronunciation VALUES (1, 'k a', 1);
        INSERT INTO pronunciation VALUES (2, 'n a', 2);
        INSERT INTO utterance VALUES (1);
        INSERT INTO phone VALUES (1, 'k');
        INSERT INTO phone VALUES (2, 'a');
        INSERT INTO phone VALUES (3, 'n');
        """
    )
    connection.commit()
    connection.close()


class CommonPronEquivalenceTests(unittest.TestCase):
    def test_2020_checkpoint_resumes_without_reparsing_completed_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            textgrids = root / "textgrids"
            textgrids.mkdir()
            write_textgrid(textgrids / "u1.TextGrid")
            write_textgrid(textgrids / "u2.TextGrid")
            qc = root / "qc.json"
            qc.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "year": "2020",
                        "textgrid_root": str(textgrids),
                        "counts": {
                            "valid_textgrids": 2,
                            "invalid_textgrids": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            checkpoint = root / "progress.json"
            first, first_mismatches = audit.audit_2020(
                textgrid_root=textgrids,
                qc_report_path=qc,
                common={"가": {("k", "a")}},
                workers=1,
                batch_size=1,
                checkpoint_path=checkpoint,
                common_dictionary_sha256="a" * 64,
            )
            self.assertEqual(first["status"], "passed")
            self.assertEqual(first_mismatches, [])
            saved = json.loads(
                checkpoint.read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "completed")
            self.assertEqual(saved["counts"]["textgrid_files"], 2)

            with mock.patch.object(
                audit,
                "inspect_2020_textgrid",
                side_effect=AssertionError("completed files reparsed"),
            ):
                second, second_mismatches = audit.audit_2020(
                    textgrid_root=textgrids,
                    qc_report_path=qc,
                    common={"가": {("k", "a")}},
                    workers=1,
                    batch_size=1,
                    checkpoint_path=checkpoint,
                    common_dictionary_sha256="a" * 64,
                )
            self.assertEqual(second["status"], "passed")
            self.assertEqual(second["resumed_from_files"], 2)
            self.assertEqual(second_mismatches, [])

            with (textgrids / "u1.TextGrid").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write("\n")
            with self.assertRaisesRegex(RuntimeError, "입력 prefix 변경"):
                audit.audit_2020(
                    textgrid_root=textgrids,
                    qc_report_path=qc,
                    common={"가": {("k", "a")}},
                    workers=1,
                    batch_size=1,
                    checkpoint_path=checkpoint,
                    common_dictionary_sha256="a" * 64,
                )

    def test_2020_checkpoint_resumes_after_interrupted_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            textgrids = root / "textgrids"
            textgrids.mkdir()
            for index in range(1, 4):
                write_textgrid(textgrids / f"u{index}.TextGrid")
            qc = root / "qc.json"
            qc.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "year": "2020",
                        "textgrid_root": str(textgrids),
                        "counts": {
                            "valid_textgrids": 3,
                            "invalid_textgrids": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            checkpoint = root / "progress.json"
            original = audit.inspect_2020_textgrid

            def interrupt_second(path, common):
                if path.stem == "u2":
                    raise RuntimeError("simulated interruption")
                return original(path, common)

            with mock.patch.object(
                audit,
                "inspect_2020_textgrid",
                side_effect=interrupt_second,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "simulated interruption"
                ):
                    audit.audit_2020(
                        textgrid_root=textgrids,
                        qc_report_path=qc,
                        common={"가": {("k", "a")}},
                        workers=1,
                        batch_size=1,
                        checkpoint_path=checkpoint,
                        common_dictionary_sha256="b" * 64,
                        checkpoint_every_batches=1,
                    )
            saved = json.loads(
                checkpoint.read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "in_progress")
            self.assertEqual(saved["counts"]["textgrid_files"], 1)

            reparsed = []

            def record_remaining(path, common):
                reparsed.append(path.stem)
                return original(path, common)

            with mock.patch.object(
                audit,
                "inspect_2020_textgrid",
                side_effect=record_remaining,
            ):
                result, mismatches = audit.audit_2020(
                    textgrid_root=textgrids,
                    qc_report_path=qc,
                    common={"가": {("k", "a")}},
                    workers=1,
                    batch_size=1,
                    checkpoint_path=checkpoint,
                    common_dictionary_sha256="b" * 64,
                    checkpoint_every_batches=1,
                )
            self.assertEqual(reparsed, ["u2", "u3"])
            self.assertEqual(result["resumed_from_files"], 1)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(mismatches, [])

    def test_r2_enriched_g2p_contract_preserves_core_method(self):
        audit.verify_g2p_contract(
            {
                "num_pronunciations": 1,
                "strict_graphemes": True,
                "input_unit": "unique_surface_eojeol",
                "model_contract": {"version": "3.2.0"},
                "deterministic_no_path_policy": {
                    "same_frozen_model_required": True,
                    "researcher_approval_required": True,
                    "existing_model_pronunciations_replaced": 0,
                    "final_spn_allowed": False,
                },
            }
        )

    def test_g2p_contract_rejects_core_or_no_path_drift(self):
        with self.assertRaisesRegex(RuntimeError, "핵심 계약"):
            audit.verify_g2p_contract(
                {
                    "num_pronunciations": 2,
                    "strict_graphemes": True,
                    "input_unit": "unique_surface_eojeol",
                }
            )
        with self.assertRaisesRegex(RuntimeError, "no-path"):
            audit.verify_g2p_contract(
                {
                    "num_pronunciations": 1,
                    "strict_graphemes": True,
                    "input_unit": "unique_surface_eojeol",
                    "deterministic_no_path_policy": {
                        "same_frozen_model_required": True,
                        "researcher_approval_required": True,
                        "existing_model_pronunciations_replaced": 1,
                        "final_spn_allowed": False,
                    },
                }
            )

    def test_difference_classifies_removed_spn_as_fixed_defect(self):
        classification = audit.classify_mismatch(
            {
                "reason": "pronunciation_set_changed",
                "word": "예시",
                "baseline_phones": "spn",
                "common_phones": "j e s i",
            },
            base_dictionary_words=set(),
        )
        self.assertEqual(classification, "spn_defect_fixed")

    def test_difference_classifies_generated_word_separately(self):
        classification = audit.classify_mismatch(
            {
                "reason": "phone_sequence_changed",
                "word": "새말",
                "baseline_phones": "s e",
                "common_phones": "s e m a l",
            },
            base_dictionary_words={"기본말"},
        )
        self.assertEqual(classification, "g2p_generated_difference")

    def test_2020_textgrid_phone_sequence_matches_common_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "u1.TextGrid"
            write_textgrid(path)
            result = audit.inspect_2020_textgrid(
                path, {"가": {("k", "a")}}
            )
            self.assertEqual(result["matches"], 1)
            self.assertEqual(result["mismatches"], [])

    def test_2020_textgrid_detects_phone_change(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "u1.TextGrid"
            write_textgrid(path, second_phone="x")
            result = audit.inspect_2020_textgrid(
                path, {"가": {("k", "a")}}
            )
            self.assertEqual(result["matches"], 0)
            self.assertEqual(
                result["mismatches"][0][0], "phone_sequence_changed"
            )

    def test_2021_db_exact_pronunciation_set_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "2021.db"
            integrity = root / "integrity.json"
            make_database(database)
            integrity.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "year": "2021",
                        "result": "ok",
                        "database": {
                            "path": str(database),
                            "bytes": database.stat().st_size,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result, mismatches = audit.audit_2021(
                database=database,
                integrity_report_path=integrity,
                year_vocabulary={"가": 3, "나": 2},
                common={"가": {("k", "a")}, "나": {("n", "a")}},
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(mismatches, [])

    def test_2020_partial_db_is_exhaustive_only_within_partial_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "2020.db"
            make_database(database)
            result, mismatches = audit.audit_2020_partial_db(
                database=database,
                year_vocabulary={"가": 3, "나": 2, "다": 1},
                common={"가": {("k", "a")}, "나": {("n", "a")}},
            )
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["is_expected_partial_database"])
            self.assertEqual(
                result["counts"]["partial_db_observed_words"], 2
            )
            self.assertEqual(result["table_counts"]["word_interval"], 0)
            self.assertEqual(mismatches, [])

    def test_2020_partial_db_detects_candidate_change(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "2020.db"
            make_database(database)
            result, mismatches = audit.audit_2020_partial_db(
                database=database,
                year_vocabulary={"가": 3, "나": 2},
                common={"가": {("k", "a")}, "나": {("n", "x")}},
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                mismatches[0]["reason"], "pronunciation_set_changed"
            )

    def test_2021_db_detects_candidate_set_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "2021.db"
            integrity = root / "integrity.json"
            make_database(database)
            integrity.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "year": "2021",
                        "result": "ok",
                        "database": {
                            "path": str(database),
                            "bytes": database.stat().st_size,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result, mismatches = audit.audit_2021(
                database=database,
                integrity_report_path=integrity,
                year_vocabulary={"가": 3, "나": 2},
                common={"가": {("k", "a")}, "나": {("n", "x")}},
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                mismatches[0]["reason"], "pronunciation_set_changed"
            )


if __name__ == "__main__":
    unittest.main()
