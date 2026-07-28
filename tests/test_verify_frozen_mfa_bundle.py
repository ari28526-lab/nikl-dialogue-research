import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from verify_frozen_mfa_bundle import verify_frozen_bundle  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FrozenMfaBundleTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, dict, dict]:
        models = {}
        outputs = {}
        for role in ("acoustic_model", "g2p_model", "dictionary"):
            path = root / f"{role}.model"
            path.write_bytes(f"{role}-content".encode())
            models[role] = path
            outputs[role] = {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        expected = {
            "repository": "example/repository",
            "commit": "abc123",
            "acoustic_version": "3.3.0",
            "g2p_version": "3.2.0",
            "unicode_decomposition": True,
            "phone_count": 107,
            "phone_sorted_sha256": "phones-sha",
            "outputs": {
                role: record["sha256"]
                for role, record in outputs.items()
            },
        }
        contract = {
            "schema_version": "hf_korean_mfa_frozen_bundle.v1",
            "status": "success",
            "source": {
                "repository": expected["repository"],
                "commit": expected["commit"],
            },
            "contract": {
                "acoustic_version": expected["acoustic_version"],
                "g2p_version": expected["g2p_version"],
                "unicode_decomposition": True,
                "phone_count": 107,
                "phone_sorted_sha256": "phones-sha",
                "acoustic_g2p_phone_inventory_equal": True,
                "symbol_files_cr_count": 0,
                "dictionary": {"unsupported_phone_count": 0},
            },
            "outputs": outputs,
        }
        contract_path = root / "bundle.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        return contract_path, models, expected

    def test_matching_contract_and_files_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, models, expected = self.fixture(Path(temp))
            report = verify_frozen_bundle(
                contract_path=contract,
                model_paths=models,
                expected_pin=expected,
            )
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["expected"]["commit"], "abc123")

    def test_changed_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, models, expected = self.fixture(Path(temp))
            models["g2p_model"].write_bytes(b"changed")
            with self.assertRaisesRegex(
                RuntimeError, "actual.g2p_model.sha256"
            ):
                verify_frozen_bundle(
                    contract_path=contract,
                    model_paths=models,
                    expected_pin=expected,
                )

    def test_changed_commit_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, models, expected = self.fixture(Path(temp))
            data = json.loads(contract.read_text(encoding="utf-8"))
            data["source"]["commit"] = "wrong"
            contract.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "source.commit"
            ):
                verify_frozen_bundle(
                    contract_path=contract,
                    model_paths=models,
                    expected_pin=expected,
                )


if __name__ == "__main__":
    unittest.main()
