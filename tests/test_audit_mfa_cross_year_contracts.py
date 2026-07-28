import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import audit_mfa_cross_year_contracts as audit  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


class CrossYearMfaContractTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        contracts = root / "contracts"
        contracts.mkdir()
        model_records = {}
        for role in ("acoustic", "dictionary", "g2p"):
            path = root / f"{role}.model"
            path.write_text(role, encoding="utf-8")
            model_records[role] = {
                **file_fingerprint(path, with_sha256=True),
                "role": role,
            }
        for year in audit.YEARS:
            payload = {
                "schema_version": "mfa_alignment_contract.v1",
                "status": "passed",
                "year": year,
                "alignment_contract_id": f"id-{year}",
                "lab_input_contract_id": f"lab-{year}",
                "pronunciation_mode": "common_pronunciation",
                "runtime": {
                    "python": "3.13.5",
                    "montreal_forced_aligner": "3.4.0",
                    "pynini": "2.1.6.post1",
                },
                "models": model_records,
                "frozen_model_pin": {
                    "commit": "0091ffa1",
                    "contract": {"sha256": "frozen"},
                },
                "common_pron_manifest": {"sha256": "manifest"},
                "common_pron_adoption_contract": {
                    "sha256": "adoption"
                },
            }
            (contracts / f"{year}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
        return contracts

    def test_same_method_with_year_specific_inputs_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            contracts = self.fixture(Path(temp))
            report = audit.audit_cross_year_contracts(
                contracts_directory=contracts
            )
            self.assertEqual(report["status"], "passed")
            self.assertTrue(
                report["gate"]["same_phone_generation_standard"]
            )

    def test_one_year_dictionary_change_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            contracts = self.fixture(Path(temp))
            path = contracts / "2024.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["models"]["dictionary"]["sha256"] = "changed"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "방법 계약 불일치"
            ):
                audit.audit_cross_year_contracts(
                    contracts_directory=contracts
                )


if __name__ == "__main__":
    unittest.main()
