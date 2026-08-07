from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import verify_common_pron_r3_g2p_candidates as verify  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


class VerifyCommonPronR3G2pCandidatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.acoustic = self.root / "acoustic.zip"
        with zipfile.ZipFile(self.acoustic, "w") as archive:
            archive.writestr(
                "korean_mfa/meta.json",
                json.dumps({"phones": ["a", "b"]}),
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_verify_one_best_and_record_small_no_path_set(self) -> None:
        input_path = self.root / "input.txt"
        output_path = self.root / "output.dict"
        report_path = self.root / "report.json"
        input_path.write_text(
            "\n".join(f"word{i:03d}" for i in range(101)) + "\n",
            encoding="utf-8",
        )
        output_path.write_text(
            "\n".join(f"word{i:03d}\ta b" for i in range(100)) + "\n",
            encoding="utf-8",
        )
        result = verify.verify_shard(
            input_shard=input_path,
            output_shard=output_path,
            acoustic_model=self.acoustic,
            report=report_path,
        )
        self.assertEqual(result["status"], "success_candidate_output")
        self.assertEqual(result["counts"]["missing_no_path_words"], 1)
        self.assertEqual(result["missing_no_path_words"], ["word100"])
        self.assertTrue(report_path.is_file())
        verify.verify_existing_report(
            input_shard=input_path,
            output_shard=output_path,
            acoustic_model=self.acoustic,
            report=report_path,
        )
        output_path.write_text("word000\ta\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "fingerprint mismatch"):
            verify.verify_existing_report(
                input_shard=input_path,
                output_shard=output_path,
                acoustic_model=self.acoustic,
                report=report_path,
            )

    def test_reject_large_missing_fraction(self) -> None:
        input_path = self.root / "input.txt"
        output_path = self.root / "output.dict"
        input_path.write_text("one\ntwo\n", encoding="utf-8")
        output_path.write_text("one\ta\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "safety limit"):
            verify.verify_shard(
                input_shard=input_path,
                output_shard=output_path,
                acoustic_model=self.acoustic,
                report=self.root / "report.json",
            )

    def test_reject_duplicate_or_spn(self) -> None:
        input_path = self.root / "input.txt"
        output_path = self.root / "output.dict"
        input_path.write_text("one\n", encoding="utf-8")
        output_path.write_text("one\ta\none\ta\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "duplicate word"):
            verify.verify_shard(
                input_shard=input_path,
                output_shard=output_path,
                acoustic_model=self.acoustic,
                report=self.root / "report.json",
            )
        output_path.write_text("one\tspn\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "spn"):
            verify.verify_shard(
                input_shard=input_path,
                output_shard=output_path,
                acoustic_model=self.acoustic,
                report=self.root / "report.json",
            )

    def test_finalize_binds_all_shards_to_target_manifest(self) -> None:
        output_root = self.root / "phase"
        input_root = self.root / "inputs"
        output_shards = output_root / "output_shards"
        input_root.mkdir()
        output_shards.mkdir(parents=True)
        input_path = input_root / "g2p_target_00001.txt"
        output_path = output_shards / "g2p_target_00001.dict"
        input_path.write_text("one\ntwo\n", encoding="utf-8")
        output_path.write_text("one\ta\ntwo\tb\n", encoding="utf-8")
        target_manifest = self.root / "targets.json"
        target_manifest.write_text(
            json.dumps(
                {
                    "schema_version": verify.TARGET_SCHEMA,
                    "status": "prepared",
                    "counts": {"unique_targets": 2},
                    "outputs": {
                        "input_shards": [
                            {
                                **file_fingerprint(
                                    input_path, with_sha256=True
                                ),
                                "shard_index": 1,
                                "expected_output_name": output_path.name,
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        phase_manifest = output_root / "manifest.json"
        result = verify.finalize_phase(
            target_manifest_path=target_manifest,
            output_root=output_root,
            acoustic_model=self.acoustic,
            phase_manifest_path=phase_manifest,
        )
        self.assertEqual(result["status"], "success_candidates_not_selected")
        self.assertEqual(result["counts"]["output_candidate_words"], 2)
        self.assertTrue(phase_manifest.is_file())
        audit_report = self.root / "audit.json"
        audit = verify.audit_phase(
            target_manifest_path=target_manifest,
            output_root=output_root,
            acoustic_model=self.acoustic,
            phase_manifest_path=phase_manifest,
            audit_report_path=audit_report,
        )
        self.assertEqual(audit["status"], "passed_read_only")
        self.assertEqual(audit["counts"]["output_candidate_words"], 2)
        self.assertTrue(audit_report.is_file())

    def test_read_only_audit_rejects_global_duplicate_input_keys(self) -> None:
        output_root = self.root / "phase"
        input_root = self.root / "inputs"
        output_shards = output_root / "output_shards"
        input_root.mkdir()
        output_shards.mkdir(parents=True)
        shard_records = []
        for index in (1, 2):
            stem = f"g2p_target_{index:05d}"
            input_path = input_root / f"{stem}.txt"
            output_path = output_shards / f"{stem}.dict"
            input_path.write_text("same\n", encoding="utf-8")
            output_path.write_text("same\ta\n", encoding="utf-8")
            shard_records.append(
                {
                    **file_fingerprint(input_path, with_sha256=True),
                    "shard_index": index,
                    "expected_output_name": output_path.name,
                }
            )
        target_manifest = self.root / "targets.json"
        target_manifest.write_text(
            json.dumps(
                {
                    "schema_version": verify.TARGET_SCHEMA,
                    "status": "prepared",
                    "counts": {"unique_targets": 2},
                    "outputs": {"input_shards": shard_records},
                }
            ),
            encoding="utf-8",
        )
        phase_manifest = output_root / "manifest.json"
        verify.finalize_phase(
            target_manifest_path=target_manifest,
            output_root=output_root,
            acoustic_model=self.acoustic,
            phase_manifest_path=phase_manifest,
        )
        with self.assertRaisesRegex(RuntimeError, "repeat across shards"):
            verify.audit_phase(
                target_manifest_path=target_manifest,
                output_root=output_root,
                acoustic_model=self.acoustic,
                phase_manifest_path=phase_manifest,
                audit_report_path=self.root / "audit.json",
            )


if __name__ == "__main__":
    unittest.main()
