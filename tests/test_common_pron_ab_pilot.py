from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python"))

import common_pron_ab_pilot as ab  # noqa: E402


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class CommonPronAbPilotTests(unittest.TestCase):
    def test_edit_distance(self) -> None:
        self.assertEqual(ab.edit_distance([], []), 0)
        self.assertEqual(ab.edit_distance(["k", "a"], ["k", "a"]), 0)
        self.assertEqual(ab.edit_distance(["k", "a"], ["k", "n", "a"]), 1)
        self.assertEqual(ab.edit_distance(["k"], ["t"]), 1)

    def test_release_boundary_blocks_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self.assertEqual(
                ab.ensure_release_child(root / "03_registry", root),
                (root / "03_registry").resolve(),
            )
            with self.assertRaises(RuntimeError):
                ab.ensure_release_child(Path(temp) / "elsewhere", root)

    def test_registry_keeps_attested_and_legacy_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            out = root / "03_registry"
            root.mkdir()
            vocab = Path(temp) / "vocab.csv"
            enriched = Path(temp) / "enriched.csv"
            legacy = Path(temp) / "legacy.csv"
            base = Path(temp) / "base.dict"
            write_csv(
                vocab,
                ["token", "total_occurrences", "n_years_present"],
                [
                    {
                        "token": "가",
                        "total_occurrences": 10,
                        "n_years_present": 6,
                    },
                    {
                        "token": "읽다",
                        "total_occurrences": 5,
                        "n_years_present": 2,
                    },
                ],
            )
            write_csv(
                enriched,
                [
                    "word",
                    "pron_1",
                    "pron_2",
                    "urimal_id",
                    "pos_tag",
                    "sense_no",
                    "stdict_target_code",
                ],
                [
                    {
                        "word": "읽다",
                        "pron_1": "익따",
                        "pron_2": "",
                        "urimal_id": "1",
                        "pos_tag": "VV",
                        "sense_no": "001",
                        "stdict_target_code": "x",
                    }
                ],
            )
            write_csv(
                legacy,
                [
                    "word",
                    "pron_g2p",
                    "urimal_id",
                    "pos_tag",
                    "sense_no",
                ],
                [
                    {
                        "word": "읽다",
                        "pron_g2p": "읽따",
                        "urimal_id": "1",
                        "pos_tag": "VV",
                        "sense_no": "001",
                    }
                ],
            )
            base.write_text("가\tk ɐ\n", encoding="utf-8")
            args = argparse.Namespace(
                release_root=root,
                output_dir=out,
                vocabulary=vocab,
                enriched=enriched,
                legacy=legacy,
                base_dictionary=base,
            )
            self.assertEqual(ab.build_registry(args), 0)
            with (out / "pronunciation_registry_seed.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            source_types = {row["pron_source_type"] for row in rows}
            self.assertEqual(
                source_types,
                {
                    "base_mfa_dictionary",
                    "dictionary_attested",
                    "legacy_machine_g2p",
                },
            )
            attested = next(
                row
                for row in rows
                if row["pron_source_type"] == "dictionary_attested"
            )
            legacy_row = next(
                row
                for row in rows
                if row["pron_source_type"] == "legacy_machine_g2p"
            )
            self.assertEqual(attested["selection_status"], "eligible_policy_b_pilot")
            self.assertEqual(legacy_row["selection_status"], "audit_only")

    def test_lexicon_b_adds_variant_without_replacing_a(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            out = root / "04_mfa_lexicons" / "pilot"
            root.mkdir()
            base = Path(temp) / "base.dict"
            acoustic = Path(temp) / "acoustic.zip"
            sample_words = Path(temp) / "sample_words.txt"
            registry_subset = Path(temp) / "registry.csv"
            word_g2p = Path(temp) / "word_g2p.dict"
            pron_g2p = Path(temp) / "pron_g2p.dict"
            base.write_text("가\tk ɐ\n", encoding="utf-8")
            with zipfile.ZipFile(acoustic, "w") as archive:
                archive.writestr(
                    "korean/meta.json",
                    json.dumps(
                        {"phones": ["k", "k̚", "ɐ", "i", "t͈", "tʰ"]}
                    ),
                )
            sample_words.write_text("가\n읽다\n", encoding="utf-8")
            word_g2p.write_text(
                "가\tk ɐ\n읽다\ti k̚ tʰ ɐ\n", encoding="utf-8"
            )
            pron_g2p.write_text("익따\ti k t͈ ɐ\n", encoding="utf-8")
            row = {field: "" for field in ab.REGISTRY_FIELDS}
            row.update(
                {
                    "candidate_id": "candidate",
                    "token": "읽다",
                    "pron_hangul": "익따",
                    "pron_source_type": "dictionary_attested",
                    "pron_source_field": "pron_1",
                    "selection_status": "eligible_policy_b_pilot",
                }
            )
            write_csv(registry_subset, ab.REGISTRY_FIELDS, [row])
            args = argparse.Namespace(
                release_root=root,
                output_dir=out,
                base_dictionary=base,
                acoustic_model=acoustic,
                sample_words=sample_words,
                registry_subset=registry_subset,
                word_g2p=word_g2p,
                pron_g2p=pron_g2p,
            )
            self.assertEqual(ab.build_lexicons(args), 0)
            a_text = (out / "policy_A_baseline_cache.dict").read_text(
                encoding="utf-8"
            )
            b_text = (out / "policy_B_attested_variants.dict").read_text(
                encoding="utf-8"
            )
            self.assertIn("읽다\ti k̚ tʰ ɐ", a_text)
            self.assertIn("읽다\ti k t͈ ɐ", b_text)
            manifest = json.loads(
                (out / "pilot_lexicon_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["counts"]["policy_b_added_variants"], 1)
            self.assertEqual(manifest["status"], "needs_manual_review")

    def test_sample_copies_byte_identical_ab_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            search_root = Path(temp) / "search"
            wav_root = Path(temp) / "wav"
            morph_root = Path(temp) / "morph"
            registry = Path(temp) / "registry.csv"
            root.mkdir()
            row = {field: "" for field in ab.REGISTRY_FIELDS}
            row.update(
                {
                    "candidate_id": "candidate",
                    "token": "같이",
                    "pron_hangul": "가치",
                    "pron_source_type": "dictionary_attested",
                    "pron_source_field": "pron_1",
                    "selection_status": "eligible_policy_b_pilot",
                }
            )
            write_csv(registry, ab.REGISTRY_FIELDS, [row])
            session = "SESSION1"
            search_path = search_root / "2020" / f"{session}.csv"
            search_fields = [
                "utt_id",
                "year",
                "session_id",
                "speaker_id",
                "form",
                "pron_reference_form",
                "pron_reference_status",
                "dur",
            ]
            utterance_rows = [
                {
                    "utt_id": f"{session}.1",
                    "year": "2020",
                    "session_id": session,
                    "speaker_id": "SPK1",
                    "form": "같이 가",
                    "pron_reference_form": "같이 가",
                    "pron_reference_status": "resolved_form",
                    "dur": "0.1",
                },
                {
                    "utt_id": f"{session}.2",
                    "year": "2020",
                    "session_id": session,
                    "speaker_id": "SPK1",
                    "form": "나는 가",
                    "pron_reference_form": "나는 가",
                    "pron_reference_status": "resolved_form",
                    "dur": "0.1",
                },
            ]
            write_csv(search_path, search_fields, utterance_rows)
            for item in utterance_rows:
                utt_id = item["utt_id"]
                wav_path = wav_root / "2020" / session / f"{utt_id}.wav"
                wav_path.parent.mkdir(parents=True, exist_ok=True)
                with wave.open(str(wav_path), "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16_000)
                    wav.writeframes(b"\0\0" * 1_600)
                morph_path = (
                    morph_root / "2020" / session / f"{utt_id}.TextGrid"
                )
                morph_path.parent.mkdir(parents=True, exist_ok=True)
                morph_path.write_text("dummy", encoding="utf-8")
            args = argparse.Namespace(
                release_root=root,
                run_id="sample_test",
                registry=registry,
                search_root=search_root,
                wav_root=wav_root,
                morph_root=morph_root,
                years=["2020"],
                speakers_per_year=1,
                seed="test_seed",
            )
            self.assertEqual(ab.build_sample(args), 0)
            a_root = root / "06_ab_results" / "sample_test" / "A"
            b_root = root / "06_ab_results" / "sample_test" / "B"
            for a_path in (a_root / "corpus").rglob("*"):
                if not a_path.is_file():
                    continue
                rel = a_path.relative_to(a_root)
                b_path = b_root / rel
                self.assertTrue(b_path.is_file())
                self.assertEqual(ab.sha256_file(a_path), ab.sha256_file(b_path))
            manifest = json.loads(
                (
                    root
                    / "05_ab_corpus"
                    / "sample_test"
                    / "sample_manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["counts"]["utterances"], 2)
            self.assertEqual(manifest["counts"]["stress_utterances"], 1)
            self.assertEqual(manifest["counts"]["control_utterances"], 1)


if __name__ == "__main__":
    unittest.main()
