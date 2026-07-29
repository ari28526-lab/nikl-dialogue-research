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

import common_pron_no_path_review as review  # noqa: E402


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_acoustic_model(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "acoustic/meta.json",
            json.dumps({"phones": ["ɨ", "ɭ", "pʰ", "p̚", "k͈", "ʌ"]}),
        )


class CommonPronNoPathReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.mapping = self.root / "mapping.csv"
        self.acoustic = self.root / "acoustic.zip"
        self.g2p_model = self.root / "g2p.zip"
        self.frozen_pin = self.root / "frozen_model_pin.json"
        self.raw = self.root / "raw.dict"
        self.review_path = self.root / "03_review" / "review.csv"
        self.review_manifest = self.root / "00_contract" / "review.json"
        self.input_shard = self.root / "01_g2p" / "input" / "oov.txt"
        self.output_shard = self.root / "01_g2p" / "output" / "oov.dict"
        self.attempt_report = (
            self.root / "_state" / "no_path_repairs" / "oov" / "attempt.json"
        )
        write_csv(
            self.mapping,
            review.MAPPING_FIELDS,
            [
                {
                    "surface": "읊어",
                    "respelled": "을퍼",
                    "rule_id": "rule14",
                    "evidence_source": "official",
                    "evidence_detail": "읊어[을퍼]",
                }
            ],
        )
        write_acoustic_model(self.acoustic)
        self.g2p_model.write_bytes(b"frozen-g2p")
        self.frozen_pin.write_text('{"status":"passed"}\n', encoding="utf-8")
        self.raw.write_text("을퍼\tɨ ɭ pʰ ʌ\n", encoding="utf-8")
        self.input_shard.parent.mkdir(parents=True)
        self.output_shard.parent.mkdir(parents=True)
        self.input_shard.write_text("읊어\n", encoding="utf-8")
        review.build_review(
            mapping_path=self.mapping,
            raw_dictionary=self.raw,
            acoustic_model=self.acoustic,
            g2p_model=self.g2p_model,
            frozen_model_pin=self.frozen_pin,
            review_path=self.review_path,
            manifest_path=self.review_manifest,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def approve(self) -> None:
        rows = review.read_review(self.review_path)
        rows[0]["approved_pron_phones_mfa"] = rows[0][
            "pron_phones_mfa"
        ]
        rows[0]["approved_phone_evidence"] = (
            "same_frozen_jamo_candidate_explicitly_approved"
        )
        rows[0]["decision"] = "approved"
        rows[0]["notes"] = "researcher approved"
        write_csv(self.review_path, review.REVIEW_FIELDS, rows)

    def test_prepare_input_preserves_mapping_order(self) -> None:
        output = self.root / "respelled.txt"
        payload = review.prepare_input(self.mapping, output)
        self.assertEqual(output.read_text(encoding="utf-8"), "을퍼\n")
        self.assertEqual(payload["counts"]["candidates"], 1)

    def test_build_review_preserves_researcher_decision(self) -> None:
        self.approve()
        payload = review.build_review(
            mapping_path=self.mapping,
            raw_dictionary=self.raw,
            acoustic_model=self.acoustic,
            g2p_model=self.g2p_model,
            frozen_model_pin=self.frozen_pin,
            review_path=self.review_path,
            manifest_path=self.review_manifest,
        )
        row = review.read_review(self.review_path)[0]
        self.assertEqual(row["decision"], "approved")
        self.assertEqual(row["notes"], "researcher approved")
        self.assertEqual(payload["status"], "approved")

    def test_record_decision_is_explicit_scoped_and_audited(self) -> None:
        decision_record = self.root / "03_review" / "decisions" / "eulp.json"
        payload = review.record_decision(
            review_path=self.review_path,
            surface="읊어",
            decision="approved",
            approved_pron_phones_mfa="ɨ ɭ pʰ ʌ",
            approved_phone_evidence="same model candidate",
            notes="explicit researcher approval",
            acoustic_model=self.acoustic,
            decision_record=decision_record,
            release_root=self.root,
        )
        row = review.read_review(self.review_path)[0]
        self.assertEqual(row["decision"], "approved")
        self.assertEqual(row["notes"], "explicit researcher approval")
        self.assertEqual(payload["previous_decision"], "pending")
        self.assertEqual(
            payload["approval_scope"],
            "this exact surface and approved phone only",
        )
        recorded = json.loads(decision_record.read_text(encoding="utf-8"))
        self.assertEqual(recorded["surface"], "읊어")
        self.assertEqual(recorded["decision"], "approved")
        before = decision_record.read_bytes()
        second = review.record_decision(
            review_path=self.review_path,
            surface="읊어",
            decision="approved",
            approved_pron_phones_mfa="ɨ ɭ pʰ ʌ",
            approved_phone_evidence="same model candidate",
            notes="explicit researcher approval",
            acoustic_model=self.acoustic,
            decision_record=decision_record,
            release_root=self.root,
        )
        self.assertEqual(second["recorded_at"], payload["recorded_at"])
        self.assertEqual(decision_record.read_bytes(), before)

    def test_record_decision_cannot_reverse_existing_decision(self) -> None:
        decision_record = self.root / "03_review" / "decisions" / "eulp.json"
        review.record_decision(
            review_path=self.review_path,
            surface="읊어",
            decision="approved",
            approved_pron_phones_mfa="ɨ ɭ pʰ ʌ",
            approved_phone_evidence="same model candidate",
            notes="explicit researcher approval",
            acoustic_model=self.acoustic,
            decision_record=decision_record,
            release_root=self.root,
        )
        with self.assertRaisesRegex(RuntimeError, "자동 반전"):
            review.record_decision(
                review_path=self.review_path,
                surface="읊어",
                decision="rejected",
                approved_pron_phones_mfa="",
                approved_phone_evidence="",
                notes="changed",
                acoustic_model=self.acoustic,
                decision_record=self.root / "other.json",
                release_root=self.root,
            )

    def test_pending_candidate_preserves_partial_shard(self) -> None:
        self.output_shard.write_text("기타\tɨ\n", encoding="utf-8")
        self.input_shard.write_text("읊어\n기타\n", encoding="utf-8")
        before = self.output_shard.read_bytes()
        code, payload = review.repair_shard(
            input_shard=self.input_shard,
            output_shard=self.output_shard,
            acoustic_model=self.acoustic,
            review_path=self.review_path,
            release_root=self.root,
            attempt_report=self.attempt_report,
        )
        self.assertEqual(code, review.PENDING_EXIT)
        self.assertEqual(self.output_shard.read_bytes(), before)
        self.assertEqual(payload["not_approved_words"], ["읊어"])
        recorded = json.loads(
            self.attempt_report.read_text(encoding="utf-8")
        )
        self.assertEqual(recorded["status"], "researcher_approval_required")

    def test_approved_candidate_repairs_without_replacing_existing(self) -> None:
        self.approve()
        self.output_shard.write_text("기타\tɨ\n", encoding="utf-8")
        self.input_shard.write_text("읊어\n기타\n", encoding="utf-8")
        code, payload = review.repair_shard(
            input_shard=self.input_shard,
            output_shard=self.output_shard,
            acoustic_model=self.acoustic,
            review_path=self.review_path,
            release_root=self.root,
            attempt_report=self.attempt_report,
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(
            self.output_shard.read_text(encoding="utf-8"),
            "읊어\tɨ ɭ pʰ ʌ\n기타\tɨ\n",
        )
        repair_dir = (
            self.root / "_state" / "no_path_repairs" / self.output_shard.stem
        )
        backups = list(repair_dir.glob("partial_*.dict"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "기타\tɨ\n")
        snapshot = review.read_review(
            repair_dir / "approved_review_snapshot.csv"
        )
        self.assertEqual(snapshot[0]["surface"], "읊어")
        self.assertEqual(snapshot[0]["decision"], "approved")

    def test_unknown_missing_word_is_not_repaired(self) -> None:
        self.output_shard.write_text("기타\tɨ\n", encoding="utf-8")
        self.input_shard.write_text("모름\n기타\n", encoding="utf-8")
        before = self.output_shard.read_bytes()
        code, payload = review.repair_shard(
            input_shard=self.input_shard,
            output_shard=self.output_shard,
            acoustic_model=self.acoustic,
            review_path=self.review_path,
            release_root=self.root,
        )
        self.assertEqual(code, review.UNKNOWN_EXIT)
        self.assertEqual(payload["unknown_words"], ["모름"])
        self.assertEqual(self.output_shard.read_bytes(), before)

    def test_changed_candidate_cannot_overwrite_existing_review(self) -> None:
        self.raw.write_text("을퍼\tɨ ɭ pʰ\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "후보가 달라짐"):
            review.build_review(
                mapping_path=self.mapping,
                raw_dictionary=self.raw,
                acoustic_model=self.acoustic,
                g2p_model=self.g2p_model,
                frozen_model_pin=self.frozen_pin,
                review_path=self.review_path,
                manifest_path=self.review_manifest,
            )

    def test_manual_approved_phone_is_separate_from_model_candidate(self) -> None:
        rows = review.read_review(self.review_path)
        rows[0].update(
            {
                "approved_pron_phones_mfa": "ɨ p̚ k͈ ʌ",
                "approved_phone_evidence": "official_rule_and_probe",
                "decision": "approved",
                "notes": "candidate was linguistically wrong",
            }
        )
        write_csv(self.review_path, review.REVIEW_FIELDS, rows)
        self.output_shard.write_text("기타\tɨ\n", encoding="utf-8")
        self.input_shard.write_text("읊어\n기타\n", encoding="utf-8")
        code, payload = review.repair_shard(
            input_shard=self.input_shard,
            output_shard=self.output_shard,
            acoustic_model=self.acoustic,
            review_path=self.review_path,
            release_root=self.root,
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            self.output_shard.read_text(encoding="utf-8"),
            "읊어\tɨ p̚ k͈ ʌ\n기타\tɨ\n",
        )
        self.assertEqual(payload["counts"]["manual_phone_override_words"], 1)
        self.assertEqual(
            payload["used_candidates"][0]["model_candidate_pron_phones_mfa"],
            "ɨ ɭ pʰ ʌ",
        )
        self.assertEqual(
            payload["used_candidates"][0]["approved_pron_phones_mfa"],
            "ɨ p̚ k͈ ʌ",
        )

    def test_legacy_approved_review_migrates_without_changing_phone(self) -> None:
        legacy = review.read_review(self.review_path)
        legacy[0]["decision"] = "approved"
        legacy[0]["notes"] = "legacy approval"
        write_csv(
            self.review_path,
            review.LEGACY_REVIEW_FIELDS,
            [
                {
                    field: legacy[0][field]
                    for field in review.LEGACY_REVIEW_FIELDS
                }
            ],
        )
        payload = review.build_review(
            mapping_path=self.mapping,
            raw_dictionary=self.raw,
            acoustic_model=self.acoustic,
            g2p_model=self.g2p_model,
            frozen_model_pin=self.frozen_pin,
            review_path=self.review_path,
            manifest_path=self.review_manifest,
        )
        migrated = review.read_review(self.review_path)[0]
        self.assertEqual(
            migrated["approved_pron_phones_mfa"],
            migrated["pron_phones_mfa"],
        )
        self.assertEqual(payload["status"], "approved")


if __name__ == "__main__":
    unittest.main()
