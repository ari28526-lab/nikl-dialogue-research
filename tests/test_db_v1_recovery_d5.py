import csv
import gzip
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "scripts" / "python"
sys.path.insert(0, str(PYTHON))


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, PYTHON / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


PREPARE = load_module("prepare_db_v1_recovery_d5_execution", "prepare_db_v1_recovery_d5_execution.py")
MATERIALIZE = load_module("materialize_db_v1_recovery_d5_shard", "materialize_db_v1_recovery_d5_shard.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecoveryD5Tests(unittest.TestCase):
    def test_split_does_not_repeat_known_too_short_feature_failures(self):
        self.assertEqual(
            PREPARE.classify_d5("mfa_feature_generation_failed", 0.03, 0)[0],
            "hold_for_audio_duration_recovery_no_same_input_mfa",
        )
        self.assertEqual(
            PREPARE.classify_d5("mfa_alignment_missing", 1.2, 0)[0],
            "approved_candidate_for_fresh_subset_diagnostic",
        )
        self.assertEqual(
            PREPARE.classify_d5("mfa_alignment_missing", 1.2, 1)[0],
            "unexpected_combination_fail_closed",
        )

    def test_materializer_copies_exact_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            package = root / "package"
            target = root / "D5_ALIGNMENT_DIAGNOSTIC_0001"
            source.mkdir()
            package.mkdir()
            wav = source / "U1.wav"
            lab = source / "U1.lab"
            wav.write_bytes(b"RIFF-fake-test-bytes")
            lab.write_text("테스트", encoding="utf-8")
            contract = package / "D5_EXECUTION_CONTRACT.json"
            contract.write_text("{}\n", encoding="utf-8")
            run_shard = package / "D5_RUN_SHARD.csv.gz"
            fields = [
                "run_order", "shard_id", "year", "utt_id", "session_id",
                "reason_code", "source_wav_path", "source_wav_bytes",
                "source_wav_sha256", "source_lab_path", "source_lab_bytes",
                "source_lab_sha256", "lab_token_count", "wav_duration_seconds",
                "target_relative_directory",
            ]
            row = {
                "run_order": "1", "shard_id": MATERIALIZE.D5_SHARD_ID,
                "year": "2022", "utt_id": "U1", "session_id": "S1",
                "reason_code": "mfa_alignment_missing",
                "source_wav_path": str(wav), "source_wav_bytes": str(wav.stat().st_size),
                "source_wav_sha256": sha(wav), "source_lab_path": str(lab),
                "source_lab_bytes": str(lab.stat().st_size), "source_lab_sha256": sha(lab),
                "lab_token_count": "1", "wav_duration_seconds": "1.0",
                "target_relative_directory": str(Path("2022") / "S1"),
            }
            with gzip.open(run_shard, "wt", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for _ in range(30):
                    numbered = dict(row)
                    numbered["run_order"] = str(int(numbered["run_order"]) + _)
                    numbered["utt_id"] = f"U{_ + 1}"
                    w = source / f"U{_ + 1}.wav"
                    l = source / f"U{_ + 1}.lab"
                    w.write_bytes(wav.read_bytes())
                    l.write_bytes(lab.read_bytes())
                    numbered.update({
                        "source_wav_path": str(w), "source_wav_sha256": sha(w),
                        "source_lab_path": str(l), "source_lab_sha256": sha(l),
                    })
                    writer.writerow(numbered)
            approval = root / "approval.json"
            approval.write_text(json.dumps({
                "schema_version": MATERIALIZE.validate_approval.__globals__["APPROVAL_SCHEMA"],
                "status": "approved", "shard_id": MATERIALIZE.D5_SHARD_ID,
                "authorization": MATERIALIZE.validate_approval.__globals__["AUTHORIZATION"],
                "execution_contract_sha256": sha(contract), "run_shard_sha256": sha(run_shard),
                "output_root": str(target.resolve()), "approved_row_count": 30,
                "source_or_r3_body_mutation_allowed": False,
                "automatic_merge_allowed": False, "approved_by": "tester",
                "approved_at": "2026-08-15T00:00:00+09:00",
            }), encoding="utf-8")
            source_hashes = {p.name: sha(p) for p in source.iterdir()}
            with mock.patch.object(MATERIALIZE, "D5_OUTPUT_ROOT", target):
                first = MATERIALIZE.materialize(package=package, approval_path=approval, output_root=target)
                second = MATERIALIZE.materialize(package=package, approval_path=approval, output_root=target)
            self.assertEqual(first["status"], "passed_exact_copy_materialization")
            self.assertEqual(second["rows"], 30)
            self.assertEqual(len(list((target / "corpus").rglob("*.wav"))), 30)
            self.assertEqual(source_hashes, {p.name: sha(p) for p in source.iterdir()})

    def test_approval_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "contract.json"
            shard = root / "shard.csv.gz"
            approval = root / "approval.json"
            contract.write_text("{}", encoding="utf-8")
            shard.write_bytes(b"x")
            approval.write_text(json.dumps({
                "schema_version": "research_db_v1_recovery_d5_approval.v1",
                "status": "approved", "shard_id": "D5_ALIGNMENT_DIAGNOSTIC_0001",
                "authorization": "materialize_30_and_run_diagnostic_mfa",
                "execution_contract_sha256": "wrong", "run_shard_sha256": sha(shard),
                "output_root": str((root / "out").resolve()), "approved_row_count": 30,
                "source_or_r3_body_mutation_allowed": False,
                "automatic_merge_allowed": False, "approved_by": "tester", "approved_at": "now",
            }), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "execution_contract_sha256"):
                MATERIALIZE.validate_approval(
                    approval, execution_contract_path=contract,
                    run_shard_path=shard, output_root=root / "out",
                )


if __name__ == "__main__":
    unittest.main()
