import csv
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_common_pron_mfa_lexicon as lexicon  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


def write_vocabulary(path: Path) -> None:
    fields = list(lexicon.OOV_FIELDS)
    rows = [
        {
            "token": "가",
            "total_occurrences": "10",
            "n_years_present": "2",
            "count_2020": "5",
            "count_2021": "5",
            "count_2022": "0",
            "count_2023": "0",
            "count_2024": "0",
            "count_2025": "0",
        },
        {
            "token": "나",
            "total_occurrences": "3",
            "n_years_present": "1",
            "count_2020": "0",
            "count_2021": "0",
            "count_2022": "3",
            "count_2023": "0",
            "count_2024": "0",
            "count_2025": "0",
        },
        {
            "token": "다가",
            "total_occurrences": "8",
            "n_years_present": "2",
            "count_2020": "0",
            "count_2021": "0",
            "count_2022": "4",
            "count_2023": "4",
            "count_2024": "0",
            "count_2025": "0",
        },
        {
            "token": "라마",
            "total_occurrences": "1",
            "n_years_present": "1",
            "count_2020": "0",
            "count_2021": "0",
            "count_2022": "0",
            "count_2023": "0",
            "count_2024": "1",
            "count_2025": "0",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_vocabulary_manifest(vocabulary: Path, manifest: Path) -> None:
    record = file_fingerprint(vocabulary, with_sha256=True)
    search_master = manifest.parent / "search_master"
    search_master.mkdir()
    build_meta_path = search_master / "_build_meta.json"
    build_meta_path.write_text('{"status":"success"}\n', encoding="utf-8")
    build_meta = file_fingerprint(build_meta_path, with_sha256=True)
    manifest.write_text(
        json.dumps(
            {
                "status": "success",
                "counts": {"unique_tokens": 4},
                "source": {
                    "search_master_root": str(search_master),
                    "build_meta": build_meta,
                },
                "output": {
                    "bytes": record["bytes"],
                    "sha256": record["sha256"],
                },
            }
        ),
        encoding="utf-8",
    )


def write_acoustic_model(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "acoustic/meta.json",
            json.dumps(
                {
                    "phones": [
                        "k",
                        "a",
                        "n",
                        "t",
                        "r",
                        "m",
                        "i",
                        "p",
                        "o",
                    ]
                }
            ),
        )


class CommonPronMfaLexiconTests(unittest.TestCase):
    def test_parser_matches_mfa_four_probability_correction_columns(self):
        word, phones, probabilities = lexicon.parse_mfa_dictionary_line(
            "가격 0.99 0.06 1.4 0.93 k ɐ ɟ ʌ k̚",
            path=Path("fixture.dict"),
            line_number=1,
        )
        self.assertEqual(word, "가격")
        self.assertEqual(phones, ("k", "ɐ", "ɟ", "ʌ", "k̚"))
        self.assertEqual(
            probabilities, ("0.99", "0.06", "1.4", "0.93")
        )

    def fixture(self, root: Path):
        vocabulary = root / "vocabulary.csv"
        vocabulary_manifest = root / "vocabulary_manifest.json"
        base_dictionary = root / "base.dict"
        g2p_model = root / "g2p.zip"
        acoustic_model = root / "acoustic.zip"
        release = root / "release"
        write_vocabulary(vocabulary)
        write_vocabulary_manifest(vocabulary, vocabulary_manifest)
        base_dictionary.write_text(
            "가\t0.9 0.8 1.0 1.0 k a\n"
            "기본\tk i p o n\n",
            encoding="utf-8",
        )
        g2p_model.write_bytes(b"g2p-model")
        write_acoustic_model(acoustic_model)
        return (
            vocabulary,
            vocabulary_manifest,
            base_dictionary,
            g2p_model,
            acoustic_model,
            release,
        )

    def prepare(self, root: Path):
        values = self.fixture(root)
        manifest = lexicon.prepare(
            vocabulary=values[0],
            vocabulary_manifest=values[1],
            base_dictionary=values[2],
            g2p_model=values[3],
            acoustic_model=values[4],
            release_root=values[5],
            shard_size=100,
        )
        return values, manifest

    def test_prepare_preserves_surface_scope_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values, first = self.prepare(root)
            self.assertEqual(first["counts"]["vocabulary_words"], 4)
            self.assertEqual(first["counts"]["observed_oov_words"], 3)
            self.assertEqual(first["counts"]["shards"], 1)
            self.assertGreater(
                first["phone_inventory_contract"]["count"], 0
            )
            shard = values[5] / "01_g2p/input_shards/oov_00001.txt"
            self.assertEqual(
                set(shard.read_text(encoding="utf-8").splitlines()),
                {"나", "다가", "라마"},
            )
            second = lexicon.prepare(
                vocabulary=values[0],
                vocabulary_manifest=values[1],
                base_dictionary=values[2],
                g2p_model=values[3],
                acoustic_model=values[4],
                release_root=values[5],
                shard_size=100,
            )
            self.assertEqual(
                first["release_contract_id"], second["release_contract_id"]
            )

    def test_finalize_preserves_base_rows_and_adds_only_g2p(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values, _ = self.prepare(root)
            output = values[5] / "01_g2p/output_shards/oov_00001.dict"
            output.write_text(
                "나\tn a\n"
                "다가\tt a k a\n"
                "라마\tr a m a\n",
                encoding="utf-8",
            )
            manifest = lexicon.finalize(release_root=values[5])
            self.assertEqual(manifest["status"], "success")
            self.assertEqual(
                manifest["dictionary_contract"][
                    "attested_dictionary_variants_added"
                ],
                0,
            )
            self.assertEqual(
                manifest["counts"]["phone_outside_acoustic_inventory"], 0
            )
            dictionary = (
                values[5] / "02_mfa_lexicon/common_pron_mfa_r1.dict"
            ).read_text(encoding="utf-8")
            self.assertTrue(
                dictionary.startswith(
                    "가\t0.9 0.8 1.0 1.0 k a\n기본\tk i p o n\n"
                )
            )
            self.assertIn("다가\tt a k a\n", dictionary)
            self.assertNotIn("pron_1", dictionary)

    def test_finalize_rejects_missing_g2p_word(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values, _ = self.prepare(root)
            output = values[5] / "01_g2p/output_shards/oov_00001.dict"
            output.write_text("나\tn a\n다가\tt a k a\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "coverage 불일치"):
                lexicon.finalize(release_root=values[5])

    def test_finalize_rejects_phone_inventory_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values, _ = self.prepare(root)
            output = values[5] / "01_g2p/output_shards/oov_00001.dict"
            output.write_text(
                "나\tn a\n다가\tt a x\n라마\tr a m a\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "inventory 밖"):
                lexicon.finalize(release_root=values[5])

    def test_prepare_rejects_base_dictionary_phone_inventory_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values = self.fixture(root)
            values[2].write_text("가\tx a\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "기본 사전"):
                lexicon.prepare(
                    vocabulary=values[0],
                    vocabulary_manifest=values[1],
                    base_dictionary=values[2],
                    g2p_model=values[3],
                    acoustic_model=values[4],
                    release_root=values[5],
                    shard_size=100,
                )

    def test_finalize_rejects_spn(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values, _ = self.prepare(root)
            output = values[5] / "01_g2p/output_shards/oov_00001.dict"
            output.write_text(
                "나\tn a\n다가\tspn\n라마\tr a m a\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "spn 포함"):
                lexicon.finalize(release_root=values[5])

    def test_verify_shard_requires_exact_phone_safe_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, _, _, acoustic_model, _ = self.fixture(root)
            input_shard = root / "input.txt"
            output_shard = root / "output.dict"
            input_shard.write_text("나\n다가\n", encoding="utf-8")
            output_shard.write_text(
                "나\tn a\n다가\tt a k a\n", encoding="utf-8"
            )
            report = lexicon.verify_g2p_shard(
                input_shard=input_shard,
                output_shard=output_shard,
                acoustic_model=acoustic_model,
            )
            self.assertEqual(report["counts"]["missing"], 0)
            self.assertEqual(report["counts"]["output_words"], 2)


if __name__ == "__main__":
    unittest.main()
