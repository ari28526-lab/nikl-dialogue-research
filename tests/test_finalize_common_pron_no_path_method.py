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

import common_pron_no_path_review as no_path  # noqa: E402
import finalize_common_pron_no_path_method as finalizer  # noqa: E402
from build_common_pron_mfa_lexicon import write_csv  # noqa: E402
from pipeline_common import atomic_write_json, file_fingerprint  # noqa: E402


def write_acoustic(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "acoustic/meta.json",
            json.dumps({"phones": ["ɨ", "ɭ", "pʰ", "ʌ"]}),
        )


def write_review(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=no_path.REVIEW_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerow(
            {
                "surface": "읊어",
                "respelled": "을퍼",
                "rule_id": "rule14",
                "evidence_source": "official",
                "evidence_detail": "읊어[을퍼]",
                "pron_phones_mfa": "ɨ ɭ pʰ ʌ",
                "approved_pron_phones_mfa": "ɨ ɭ pʰ ʌ",
                "approved_phone_evidence": (
                    "same_frozen_jamo_candidate_explicitly_approved"
                ),
                "decision": "approved",
                "notes": "explicit approval",
            }
        )


class FinalizeNoPathMethodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "common_pron_mfa_r2_20990101"
        self.root.mkdir()
        self.input_shard = (
            self.root / "01_g2p" / "input_shards" / "oov_00001.txt"
        )
        self.output_shard = (
            self.root / "01_g2p" / "output_shards" / "oov_00001.dict"
        )
        self.review = (
            self.root / "03_review" / "g2p_no_path_researcher_review.csv"
        )
        self.acoustic = self.root / "models" / "acoustic.zip"
        self.g2p_model = self.root / "models" / "g2p.zip"
        self.frozen_pin = (
            self.root / "00_contract" / "frozen_model_pin.json"
        )
        self.input_shard.parent.mkdir(parents=True)
        self.output_shard.parent.mkdir(parents=True)
        self.acoustic.parent.mkdir(parents=True)
        self.input_shard.write_text("읊어\n기타\n", encoding="utf-8")
        self.output_shard.write_text("기타\tɨ\n", encoding="utf-8")
        write_acoustic(self.acoustic)
        self.g2p_model.write_bytes(b"frozen-jamo-g2p")
        self.frozen_pin.parent.mkdir(parents=True)
        self.frozen_pin.write_text(
            '{"status":"passed"}\n', encoding="utf-8"
        )
        write_review(self.review)
        code, _ = no_path.repair_shard(
            input_shard=self.input_shard,
            output_shard=self.output_shard,
            acoustic_model=self.acoustic,
            review_path=self.review,
            release_root=self.root,
        )
        self.assertEqual(code, 0)

        final_dir = self.root / "02_mfa_lexicon"
        final_dir.mkdir()
        self.dictionary = final_dir / "common_pron_mfa_r2.dict"
        self.dictionary.write_text(
            "읊어\tɨ ɭ pʰ ʌ\n기타\tɨ\n", encoding="utf-8"
        )
        self.cache = final_dir / "g2p_cache.csv"
        write_csv(
            self.cache,
            ("token", "pron_phones_mfa", "pron_source"),
            [
                {
                    "token": "읊어",
                    "pron_phones_mfa": "ɨ ɭ pʰ ʌ",
                    "pron_source": finalizer.DIRECT_SOURCE,
                },
                {
                    "token": "기타",
                    "pron_phones_mfa": "ɨ",
                    "pron_source": finalizer.DIRECT_SOURCE,
                },
            ],
        )
        self.original_cache_record = file_fingerprint(
            self.cache, with_sha256=True
        )
        self.release_path = (
            self.root / "00_contract" / "release_manifest.json"
        )
        mapping = self.root / "candidate_mapping.csv"
        mapping.write_text("surface,respelled\n읊어,을퍼\n", encoding="utf-8")
        raw = self.root / "candidate_raw.dict"
        raw.write_text("을퍼\tɨ ɭ pʰ ʌ\n", encoding="utf-8")
        candidate_contract = {
            "schema_version": no_path.SCHEMA_VERSION,
            "status": "review_pending",
            "kind": (
                "reviewed_standard_pronunciation_no_path_candidates"
            ),
            "inputs": {
                "helper_code": file_fingerprint(
                    Path(no_path.__file__), with_sha256=True
                ),
                "mapping": file_fingerprint(mapping, with_sha256=True),
                "respelled_g2p": file_fingerprint(
                    raw, with_sha256=True
                ),
                "acoustic_model": file_fingerprint(
                    self.acoustic, with_sha256=True
                ),
                "g2p_model": file_fingerprint(
                    self.g2p_model, with_sha256=True
                ),
                "frozen_model_pin": file_fingerprint(
                    self.frozen_pin, with_sha256=True
                ),
            },
            "output": {
                "researcher_review": file_fingerprint(
                    self.review, with_sha256=True
                )
            },
        }
        atomic_write_json(
            self.root
            / "00_contract"
            / "g2p_no_path_review_manifest.json",
            candidate_contract,
        )
        self.prepared_contract_id = "a" * 64
        self.release = {
            "schema_version": finalizer.LEXICON_SCHEMA_VERSION,
            "status": "success",
            "release_id": self.root.name,
            "release_contract_id": self.prepared_contract_id,
            "phone_policy": "direct only",
            "g2p_contract": {"strict_graphemes": True},
            "dictionary_contract": {},
            "counts": {
                "g2p_output_words": 2,
                "g2p_jamo_ls_rewrite_words": 0,
            },
            "inputs": {
                "acoustic_model": file_fingerprint(
                    self.acoustic, with_sha256=True
                ),
                "g2p_model": file_fingerprint(
                    self.g2p_model, with_sha256=True
                ),
            },
            "g2p_output_shards": [
                {
                    **file_fingerprint(
                        self.output_shard, with_sha256=True
                    ),
                    "shard_index": 1,
                    "row_count": 2,
                }
            ],
            "outputs": {
                "dictionary": file_fingerprint(
                    self.dictionary, with_sha256=True
                ),
                "g2p_cache": self.original_cache_record,
            },
            "required_before_mfa": {},
        }
        atomic_write_json(self.release_path, self.release)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cache_rows(self) -> dict[str, dict[str, str]]:
        with self.cache.open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            return {
                row["token"]: row for row in csv.DictReader(stream)
            }

    def test_finalizes_provenance_without_changing_phones(self) -> None:
        before_dictionary = self.dictionary.read_bytes()
        payload = finalizer.finalize_supplement(self.root)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["counts"]["reviewed_no_path_words"], 1)
        self.assertEqual(self.dictionary.read_bytes(), before_dictionary)
        rows = self.cache_rows()
        self.assertEqual(
            rows["읊어"]["pron_source"], finalizer.FALLBACK_SOURCE
        )
        self.assertEqual(
            rows["기타"]["pron_source"], finalizer.DIRECT_SOURCE
        )
        release = json.loads(
            self.release_path.read_text(encoding="utf-8")
        )
        self.assertEqual(
            release["prepared_release_contract_id"],
            self.prepared_contract_id,
        )
        self.assertNotEqual(
            release["release_contract_id"], self.prepared_contract_id
        )
        self.assertEqual(
            release["counts"]["g2p_reviewed_no_path_words"], 1
        )
        self.assertEqual(
            release["counts"][
                "g2p_existing_model_pronunciations_replaced"
            ],
            0,
        )

    def test_second_run_is_byte_idempotent(self) -> None:
        first = finalizer.finalize_supplement(self.root)
        supplement = (
            self.root
            / "00_contract"
            / "g2p_no_path_method_supplement.json"
        )
        before = {
            "release": self.release_path.read_bytes(),
            "supplement": supplement.read_bytes(),
            "cache": self.cache.read_bytes(),
        }
        second = finalizer.finalize_supplement(self.root)
        self.assertEqual(
            second["production_release_contract_id"],
            first["production_release_contract_id"],
        )
        self.assertEqual(self.release_path.read_bytes(), before["release"])
        self.assertEqual(supplement.read_bytes(), before["supplement"])
        self.assertEqual(self.cache.read_bytes(), before["cache"])

    def test_recovers_manifest_patch_after_supplement_exists(self) -> None:
        payload = finalizer.finalize_supplement(self.root)
        crash_state = dict(self.release)
        # Simulate cache+supplement written, release manifest not yet patched.
        atomic_write_json(self.release_path, crash_state)
        finalizer.finalize_supplement(self.root)
        recovered = json.loads(
            self.release_path.read_text(encoding="utf-8")
        )
        self.assertEqual(
            recovered["release_contract_id"],
            payload["production_release_contract_id"],
        )
        self.assertEqual(
            recovered["counts"]["g2p_reviewed_no_path_words"], 1
        )

    def test_tampered_partial_backup_blocks_supplement(self) -> None:
        repair_dir = (
            self.root / "_state" / "no_path_repairs" / "oov_00001"
        )
        backup = next(repair_dir.glob("partial_*.dict"))
        backup.write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "fingerprint 불일치"):
            finalizer.finalize_supplement(self.root)

    def test_manual_override_gets_distinct_cache_provenance(self) -> None:
        repair_dir = (
            self.root / "_state" / "no_path_repairs" / "oov_00001"
        )
        repair_path = repair_dir / "repair_manifest.json"
        repair = json.loads(repair_path.read_text(encoding="utf-8"))
        snapshot_path = Path(
            repair["inputs"]["approved_review_snapshot"]["path"]
        )
        snapshot = no_path.read_review(snapshot_path)
        snapshot[0].update(
            {
                "pron_phones_mfa": "ɨ ɭ pʰ",
                "approved_pron_phones_mfa": "ɨ ɭ pʰ ʌ",
                "approved_phone_evidence": "official_rule_and_probe",
                "notes": "candidate corrected inside inventory",
            }
        )
        write_csv(snapshot_path, no_path.REVIEW_FIELDS, snapshot)
        used = repair["used_candidates"][0]
        used.update(
            {
                "pron_phones_mfa": "ɨ ɭ pʰ ʌ",
                "model_candidate_pron_phones_mfa": "ɨ ɭ pʰ",
                "approved_pron_phones_mfa": "ɨ ɭ pʰ ʌ",
                "approved_phone_evidence": "official_rule_and_probe",
                "notes": "candidate corrected inside inventory",
            }
        )
        repair["counts"]["same_model_candidate_words"] = 0
        repair["counts"]["manual_phone_override_words"] = 1
        repair["manual_phone_override_words"] = ["읊어"]
        repair["inputs"]["approved_review_snapshot"] = file_fingerprint(
            snapshot_path, with_sha256=True
        )
        atomic_write_json(repair_path, repair)

        payload = finalizer.finalize_supplement(self.root)
        self.assertEqual(
            payload["counts"]["manual_phone_override_words"], 1
        )
        self.assertEqual(
            self.cache_rows()["읊어"]["pron_source"],
            finalizer.MANUAL_FALLBACK_SOURCE,
        )
        release = json.loads(
            self.release_path.read_text(encoding="utf-8")
        )
        self.assertEqual(
            release["counts"][
                "g2p_reviewed_no_path_manual_override_words"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
