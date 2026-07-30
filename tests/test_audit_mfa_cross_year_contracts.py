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
        phones = root / "phones"
        phones.mkdir()
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
            observed = (
                ["a", "k"] if year != "2024" else ["a", "k", "n"]
            )
            (phones / f"{year}.json").write_text(
                json.dumps(
                    {
                        "schema_version": (
                            audit.PHONE_SCHEMA_VERSION
                        ),
                        "status": "success",
                        "year": year,
                        "alignment_contract_id": f"id-{year}",
                        "allowed_phone_inventory": {
                            "count": 3,
                            "sorted_phone_sha256": "allowed",
                            "phones": ["a", "k", "n"],
                        },
                        "observed_phone_inventory": {
                            "count": len(observed),
                            "sorted_phone_sha256": f"observed-{year}",
                            "phones": observed,
                        },
                        "outside_allowed_inventory": [],
                        "spn_intervals": 0,
                    }
                ),
                encoding="utf-8",
            )
        return contracts, phones

    def test_same_method_with_year_specific_inputs_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            contracts, phones = self.fixture(Path(temp))
            report = audit.audit_cross_year_contracts(
                contracts_directory=contracts,
                phone_inventory_directory=phones,
            )
            self.assertEqual(report["status"], "passed")
            self.assertTrue(
                report["gate"]["same_phone_generation_standard"]
            )
            self.assertFalse(
                report["gate"][
                    "observed_phone_sets_required_identical"
                ]
            )
            self.assertIn("n", report["observed_phone_summary"]["union"])

    def test_one_year_dictionary_change_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            contracts, phones = self.fixture(Path(temp))
            path = contracts / "2024.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["models"]["dictionary"]["sha256"] = "changed"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "방법 계약 불일치"
            ):
                audit.audit_cross_year_contracts(
                    contracts_directory=contracts,
                    phone_inventory_directory=phones,
                )

    def test_allowed_phone_inventory_change_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            contracts, phones = self.fixture(Path(temp))
            path = phones / "2023.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["allowed_phone_inventory"]["phones"] = ["a", "k"]
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "허용 phone inventory"
            ):
                audit.audit_cross_year_contracts(
                    contracts_directory=contracts,
                    phone_inventory_directory=phones,
                )


if __name__ == "__main__":
    unittest.main()
