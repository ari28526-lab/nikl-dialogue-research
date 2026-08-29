from __future__ import annotations

import csv
import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "python" / "run_bareun_wsd_csv_full.py"
SPEC = importlib.util.spec_from_file_location("bareun_wsd_csv_full", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BareunWsdCsvFullTest(unittest.TestCase):
    def test_line_separator_normalization_is_one_for_one(self) -> None:
        source = "첫 줄\r\n둘째\u2028셋째\x85넷째"
        normalized, replacements = MODULE.normalize_analysis_text(source)
        self.assertEqual(normalized, "첫 줄  둘째 셋째 넷째")
        self.assertEqual(replacements, 4)
        self.assertEqual(len(normalized), len(source))

    def test_read_input_rows_uses_only_identity_speaker_and_form(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            year = root / "NIKL_DIALOGUE_2020_v1.4"
            year.mkdir()
            path = year / "sample.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["utt_id", "speaker_id", "form", "tagged", "n_morphs"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "u1",
                        "speaker_id": "s1",
                        "form": "새 분석",
                        "tagged": "구/NNG+결과/NNG",
                        "n_morphs": "2",
                    }
                )
            rows = MODULE.read_input_rows(path, root)
            self.assertEqual(rows[0]["form"], "새 분석")
            self.assertNotIn("tagged", rows[0])
            self.assertNotIn("n_morphs", rows[0])

    def test_source_output_dir_preserves_relative_identity(self) -> None:
        root = Path("D:/input")
        source = root / "NIKL_DIALOGUE_2024_v1.0" / "ABC.csv"
        output = MODULE.source_output_dir(Path("D:/run"), source, root)
        self.assertEqual(
            output.as_posix(), "D:/run/files/NIKL_DIALOGUE_2024_v1.0/ABC"
        )

    def test_gzip_csv_is_deterministic_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = [{"a": "한글", "b": 1}, {"a": "둘", "b": 2}]
            first = root / "first.csv.gz"
            second = root / "second.csv.gz"
            MODULE.gzip_csv(first, ["a", "b"], rows)
            MODULE.gzip_csv(second, ["a", "b"], rows)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with gzip.open(first, "rt", encoding="utf-8", newline="") as handle:
                read = list(csv.DictReader(handle))
            self.assertEqual(read[0]["a"], "한글")

    def test_output_contract_rejects_project_drive_and_protected_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            with self.assertRaises(RuntimeError):
                MODULE.ensure_output_contract(project, project / "output", [])

    def test_process_source_is_atomic_and_receipt_resumable(self) -> None:
        from bareunpy.bareun.language_service_pb2 import (
            AnalyzeSyntaxResponse,
            Morpheme,
        )

        class Tagged:
            def __init__(self, response):
                self.response = response

            def msg(self):
                return self.response

        class FakeTagger:
            def __init__(self):
                self.calls = 0
                self.kwargs = []
                self.texts = []

            def tags(self, texts, **kwargs):
                self.calls += 1
                self.kwargs.append(kwargs)
                self.texts.append(list(texts))
                response = AnalyzeSyntaxResponse()
                begin = 0
                for text in texts:
                    sentence = response.sentences.add()
                    sentence.text.content = text
                    sentence.text.begin_offset = begin
                    sentence.text.length = len(text)
                    token = sentence.tokens.add()
                    token.text.content = text
                    token.text.begin_offset = begin
                    token.text.length = len(text)
                    morph = token.morphemes.add()
                    morph.text.content = text
                    morph.text.begin_offset = begin
                    morph.text.length = len(text)
                    morph.tag = Morpheme.Tag.NNG
                    morph.probability = 0.9
                    begin += len(text) + 1
                return Tagged(response)

            def tag(self, text, **kwargs):
                raise AssertionError("single fallback should not be used")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_root = root / "input"
            year = input_root / "NIKL_DIALOGUE_2020_v1.4"
            year.mkdir(parents=True)
            source = year / "sample.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["utt_id", "speaker_id", "form"]
                )
                writer.writeheader()
                writer.writerow({"utt_id": "u1", "speaker_id": "s1", "form": "하나"})
                writer.writerow(
                    {"utt_id": "u2", "speaker_id": "s2", "form": "둘\n셋"}
                )
            run_root = root / "run"
            tagger = FakeTagger()
            receipt = MODULE.process_source(
                tagger, source, input_root, run_root, batch_size=40, max_retries=1
            )
            self.assertEqual(receipt["counts"]["utterances"], 2)
            self.assertEqual(tagger.kwargs[0]["with_sense"], True)
            self.assertEqual(
                receipt["api_input_normalization"]["utterances_changed"], 1
            )
            self.assertEqual(
                receipt["api_input_normalization"]["characters_replaced"], 1
            )
            self.assertEqual(tagger.texts[0], ["하나", "둘 셋"])
            final_dir = MODULE.source_output_dir(run_root, source, input_root)
            self.assertTrue((final_dir / "RECEIPT.json").is_file())
            self.assertFalse(final_dir.with_name(final_dir.name + ".building").exists())
            first_calls = tagger.calls
            resumed = MODULE.process_source(
                tagger, source, input_root, run_root, batch_size=40, max_retries=1
            )
            self.assertEqual(resumed["source_sha256"], receipt["source_sha256"])
            self.assertEqual(tagger.calls, first_calls)

            morph_tagger = FakeTagger()
            morph_run_root = root / "morph-run"
            morph_receipt = MODULE.process_source(
                morph_tagger,
                source,
                input_root,
                morph_run_root,
                batch_size=40,
                max_retries=1,
                with_sense=False,
                auto_spacing=False,
                auto_jointing=False,
            )
            morph_dir = MODULE.source_output_dir(morph_run_root, source, input_root)
            self.assertFalse(morph_receipt["with_sense"])
            self.assertEqual(morph_receipt["schema"], "bareun_morph_csv_file_receipt.v1")
            self.assertFalse((morph_dir / "sense_dictionary.csv.gz").exists())
            self.assertFalse(morph_tagger.kwargs[0]["with_sense"])
            self.assertFalse(morph_tagger.kwargs[0]["auto_spacing"])
            self.assertFalse(morph_tagger.kwargs[0]["auto_jointing"])
            with gzip.open(
                morph_dir / "morphemes.csv.gz", "rt", encoding="utf-8", newline=""
            ) as handle:
                self.assertNotIn("sense_no", next(csv.reader(handle)))
            with gzip.open(
                morph_dir / "utterances.csv.gz", "rt", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[1]["form"], "둘\n셋")
            self.assertEqual(rows[1]["response_text"], "둘 셋")


if __name__ == "__main__":
    unittest.main()
