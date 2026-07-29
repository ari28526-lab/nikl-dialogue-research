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
    search_master.mkdir(exist_ok=True)
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


def write_g2p_model(
    path: Path,
    *,
    graphemes: list[str],
    unicode_decomposition: bool = False,
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "g2p/meta.json",
            json.dumps(
                {
                    "architecture": "phonetisaurus",
                    "version": "test",
                    "unicode_decomposition": unicode_decomposition,
                    "graphemes": graphemes,
                    "phones": ["a", "k", "p"],
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
        decomposed = sorted(
            set(
                "".join(
                    __import__("unicodedata").normalize("NFKD", value)
                    for value in ("가", "나", "다가", "라마")
                )
            )
        )
        write_g2p_model(
            g2p_model,
            graphemes=decomposed,
            unicode_decomposition=True,
        )
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

    def prepare_jamo_ls(self, root: Path):
        values = self.fixture(root)
        vocabulary = values[0]
        with vocabulary.open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        rows[-1]["token"] = "외곬의"
        with vocabulary.open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=list(lexicon.OOV_FIELDS),
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        write_vocabulary_manifest(vocabulary, values[1])
        decomposed = sorted(
            set(
                "".join(
                    __import__("unicodedata").normalize(
                        "NFKD", value
                    )
                    for value in ("가", "나", "다가", "외곬의")
                )
            )
            - {lexicon.JAMO_LS}
            | {lexicon.JAMO_L, lexicon.JAMO_S}
        )
        write_g2p_model(
            values[3],
            graphemes=decomposed,
            unicode_decomposition=True,
        )
        lexicon.prepare(
            vocabulary=values[0],
            vocabulary_manifest=values[1],
            base_dictionary=values[2],
            g2p_model=values[3],
            acoustic_model=values[4],
            release_root=values[5],
            shard_size=100,
        )
        paths = lexicon.prepare_paths(values[5])
        mapping = lexicon.read_special_mapping(
            paths["special_mapping"]
        )
        paths["special_raw_output"].write_text(
            f"{mapping[0]['model_input']}\tr a m a\n",
            encoding="utf-8",
        )
        lexicon.restore_jamo_ls_candidates(
            release_root=values[5],
            acoustic_model=values[4],
        )
        (paths["output_shards"] / "oov_00001.dict").write_text(
            "나\tn a\n다가\tt a k a\n",
            encoding="utf-8",
        )
        return values, paths

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

    def test_prepare_code_transition_requires_byte_equivalent_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, current = self.prepare(root)
            prepared = json.loads(json.dumps(current))
            prepared["code_contract"]["lexicon_builder"][
                "normalized_utf8_sha256"
            ] = "0" * 64
            evidence_path = root / "isolated_prepare_manifest.json"
            evidence_path.write_text(
                json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            evidence_record = file_fingerprint(
                evidence_path, with_sha256=True
            )
            registry_path = root / "transitions.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "common_pron_prepare_code_transition.v1"
                        ),
                        "status": "active",
                        "transitions": [
                            {
                                "transition_id": "test_transition",
                                "status": "byte_equivalent",
                                "release_contract_id": prepared[
                                    "release_contract_id"
                                ],
                                "from_builder_sha256": "0" * 64,
                                "to_builder_sha256": current[
                                    "code_contract"
                                ]["lexicon_builder"][
                                    "normalized_utf8_sha256"
                                ],
                                "evidence_manifest": evidence_record,
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            result = lexicon.verify_prepare_code_transition(
                prepared=prepared,
                actual_code=current["code_contract"]["lexicon_builder"],
                transitions_path=registry_path,
            )
            self.assertEqual(
                result["status"],
                "byte_equivalent_transition_verified",
            )

            changed = json.loads(
                evidence_path.read_text(encoding="utf-8")
            )
            changed["outputs"]["input_shards"][0]["sha256"] = "f" * 64
            evidence_path.write_text(
                json.dumps(changed, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed_record = file_fingerprint(
                evidence_path, with_sha256=True
            )
            registry = json.loads(
                registry_path.read_text(encoding="utf-8")
            )
            registry["transitions"][0][
                "evidence_manifest"
            ] = changed_record
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError, "prepared artifacts differ"
            ):
                lexicon.verify_prepare_code_transition(
                    prepared=prepared,
                    actual_code=current["code_contract"][
                        "lexicon_builder"
                    ],
                    transitions_path=registry_path,
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
                values[5] / "02_mfa_lexicon/common_pron_mfa_r2.dict"
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

    def test_grapheme_audit_finds_words_strict_g2p_would_skip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_directory = root / "input"
            input_directory.mkdir()
            (input_directory / "oov_00001.txt").write_text(
                "가\n갭\n나\n", encoding="utf-8"
            )
            g2p_model = root / "g2p.zip"
            write_g2p_model(
                g2p_model,
                graphemes=["가", "나"],
            )
            report, rows = lexicon.audit_g2p_grapheme_coverage(
                input_directory=input_directory,
                g2p_model=g2p_model,
            )
            self.assertEqual(report["status"], "unsupported_graphemes_found")
            self.assertEqual(report["counts"]["input_words"], 3)
            self.assertEqual(report["counts"]["unsupported_words"], 1)
            self.assertEqual(rows[0]["token"], "갭")
            self.assertEqual(rows[0]["missing_graphemes"], "갭")

    def test_grapheme_audit_supports_explicit_nfkd_jamo_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_directory = root / "input"
            input_directory.mkdir()
            (input_directory / "oov_00001.txt").write_text(
                "가\n갭\n", encoding="utf-8"
            )
            g2p_model = root / "jamo_g2p.zip"
            decomposed = sorted(
                set(
                    "".join(
                        __import__("unicodedata").normalize("NFKD", value)
                        for value in ("가", "갭")
                    )
                )
            )
            write_g2p_model(
                g2p_model,
                graphemes=decomposed,
            )
            report, rows = lexicon.audit_g2p_grapheme_coverage(
                input_directory=input_directory,
                g2p_model=g2p_model,
                input_normalization="NFKD",
            )
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["input_normalization"], "NFKD")
            self.assertEqual(report["counts"]["unsupported_words"], 0)
            self.assertEqual(rows, [])

    def test_jamo_ls_rewrite_uses_same_supported_jamo_inventory(self):
        token = "외곬의"
        model_input = lexicon.rewrite_jamo_ls_for_model(token)
        self.assertNotEqual(model_input, token)
        decomposed = __import__("unicodedata").normalize(
            "NFKD", model_input
        )
        self.assertNotIn(lexicon.JAMO_LS, decomposed)
        self.assertIn(lexicon.JAMO_L, decomposed)
        self.assertIn(lexicon.JAMO_S, decomposed)

    def test_special_review_preserves_ipa_modifier_letters(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.csv"
            path.write_text(
                "token,model_input,pron_phones_mfa,decision,notes\n"
                "외곬의,외골ᆺ의,tɕʰ i pʲ,approved,\n",
                encoding="utf-8-sig",
            )
            row = lexicon.read_special_review(path)[0]
            self.assertEqual(row["pron_phones_mfa"], "tɕʰ i pʲ")
            self.assertNotEqual(row["pron_phones_mfa"], "tɕh i pj")

    def test_restore_jamo_ls_keeps_surface_key_and_requires_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values = self.fixture(root)
            vocabulary = values[0]
            with vocabulary.open(
                "r", encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            rows[-1]["token"] = "외곬의"
            with vocabulary.open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=list(lexicon.OOV_FIELDS),
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(rows)
            write_vocabulary_manifest(
                vocabulary, values[1]
            )
            decomposed = sorted(
                set(
                    "".join(
                        __import__("unicodedata").normalize(
                            "NFKD", value
                        )
                        for value in ("가", "나", "다가", "외곬의")
                    )
                )
                - {lexicon.JAMO_LS}
                | {lexicon.JAMO_L, lexicon.JAMO_S}
            )
            write_g2p_model(
                values[3],
                graphemes=decomposed,
                unicode_decomposition=True,
            )
            prepared = lexicon.prepare(
                vocabulary=values[0],
                vocabulary_manifest=values[1],
                base_dictionary=values[2],
                g2p_model=values[3],
                acoustic_model=values[4],
                release_root=values[5],
                shard_size=100,
            )
            self.assertEqual(
                prepared["counts"]["g2p_jamo_ls_rewrite_words"], 1
            )
            paths = lexicon.prepare_paths(values[5])
            mapping = lexicon.read_special_mapping(
                paths["special_mapping"]
            )
            paths["special_raw_output"].write_text(
                f"{mapping[0]['model_input']}\tr a m a\n",
                encoding="utf-8",
            )
            report = lexicon.restore_jamo_ls_candidates(
                release_root=values[5],
                acoustic_model=values[4],
            )
            self.assertEqual(
                report["status"],
                "candidate_ready_researcher_review_required",
            )
            restored = lexicon.read_generated_dictionary(
                paths["special_restored_output"]
            )
            self.assertEqual(set(restored), {"외곬의"})
            review = lexicon.read_special_review(
                paths["special_review"]
            )
            self.assertEqual(review[0]["decision"], "pending")

    def test_finalize_uses_reviewed_jamo_override_and_keeps_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            values, paths = self.prepare_jamo_ls(Path(temp))
            review = lexicon.read_special_review(
                paths["special_review"]
            )
            review[0].update(
                {
                    "approved_pron_phones_mfa": "r a m i",
                    "decision": "approved",
                    "evidence_source": "official_rule14_test",
                    "notes": "same-inventory manual correction",
                }
            )
            lexicon.write_csv(
                paths["special_review"],
                lexicon.SPECIAL_REVIEW_FIELDS,
                review,
            )
            manifest = lexicon.finalize(release_root=values[5])
            self.assertEqual(
                manifest["counts"]["g2p_jamo_ls_manual_override_words"],
                1,
            )
            self.assertEqual(
                manifest["counts"][
                    "g2p_jamo_ls_model_candidate_accepted_words"
                ],
                0,
            )
            self.assertEqual(
                lexicon.read_generated_dictionary(
                    paths["special_restored_output"]
                )["외곬의"],
                ("r", "a", "m", "a"),
            )
            self.assertEqual(
                lexicon.read_generated_dictionary(
                    paths["special_approved_output"]
                )["외곬의"],
                ("r", "a", "m", "i"),
            )
            final = lexicon.read_generated_dictionary(
                paths["final_dictionary"]
            )
            self.assertEqual(final["외곬의"], ("r", "a", "m", "i"))
            with paths["g2p_cache"].open(
                "r", encoding="utf-8-sig", newline=""
            ) as stream:
                cache = {
                    row["token"]: row for row in csv.DictReader(stream)
                }
            self.assertEqual(
                cache["외곬의"]["pron_source"],
                "researcher_reviewed_jamo_ls_override_"
                "same_acoustic_inventory_v1",
            )

    def test_finalize_rejects_jamo_override_without_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            values, paths = self.prepare_jamo_ls(Path(temp))
            review = lexicon.read_special_review(
                paths["special_review"]
            )
            review[0].update(
                {
                    "approved_pron_phones_mfa": "r a m i",
                    "decision": "approved",
                }
            )
            lexicon.write_csv(
                paths["special_review"],
                lexicon.SPECIAL_REVIEW_FIELDS,
                review,
            )
            with self.assertRaisesRegex(
                RuntimeError, "evidence_source와 notes"
            ):
                lexicon.finalize(release_root=values[5])


if __name__ == "__main__":
    unittest.main()
