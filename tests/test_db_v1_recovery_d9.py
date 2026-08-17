from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from audit_db_v1_recovery_d9_mfa import tier_names  # noqa: E402
from db_v1_recovery_d9_common import (  # noqa: E402
    APPROVAL_SCHEMA,
    AUTHORIZATION,
    D9_BEAM,
    D9_RETRY_BEAM,
    D9_ROW_COUNT,
    D9_SHARD_ID,
    validate_approval,
    validate_config,
)
from pipeline_common import sha256_file  # noqa: E402


class D9ContractTests(unittest.TestCase):
    def test_configuration_is_exactly_one_wider_beam_step(self) -> None:
        validate_config({"beam": 100, "retry_beam": 400})
        with self.assertRaises(RuntimeError):
            validate_config({"beam": 10, "retry_beam": 40})

    def test_approval_is_bound_to_three_hashes_and_no_merge(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            contract = tmp_path / "contract.json"
            shard = tmp_path / "shard.json"
            config = tmp_path / "config.json"
            for path, payload in (
                (contract, {"x": 1}),
                (shard, {"x": 2}),
                (config, {"beam": D9_BEAM, "retry_beam": D9_RETRY_BEAM}),
            ):
                path.write_text(json.dumps(payload), encoding="utf-8")
            approval = {
                "schema_version": APPROVAL_SCHEMA,
                "status": "approved",
                "shard_id": D9_SHARD_ID,
                "authorization": AUTHORIZATION,
                "execution_contract_sha256": sha256_file(contract),
                "run_shard_sha256": sha256_file(shard),
                "mfa_config_sha256": sha256_file(config),
                "output_root": str((tmp_path / "out").resolve()),
                "approved_row_count": D9_ROW_COUNT,
                "beam": D9_BEAM,
                "retry_beam": D9_RETRY_BEAM,
                "one_run_only": True,
                "source_or_r3_body_mutation_allowed": False,
                "automatic_merge_allowed": False,
                "approved_by": "ari30",
                "approved_at": "2026-08-17T00:00:00+09:00",
            }
            approval_path = tmp_path / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            validate_approval(
                approval_path,
                execution_contract_path=contract,
                run_shard_path=shard,
                config_path=config,
                output_root=tmp_path / "out",
            )
            approval["automatic_merge_allowed"] = True
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                validate_approval(
                    approval_path,
                    execution_contract_path=contract,
                    run_shard_path=shard,
                    config_path=config,
                    output_root=tmp_path / "out",
                )

    def test_textgrid_audit_requires_named_tiers(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "x.TextGrid"
            path.write_text(
                'File type = "ooTextFile"\nname = "words"\nname = "phones"\n',
                encoding="utf-8",
            )
            self.assertEqual(tier_names(path), ["words", "phones"])


if __name__ == "__main__":
    unittest.main()
