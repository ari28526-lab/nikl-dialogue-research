import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_mfa_alignment_contract import (  # noqa: E402
    build_alignment_contract,
)


class MfaAlignmentContractTests(unittest.TestCase):
    def make_contract(
        self,
        root: Path,
        *,
        lab_contract: str = "lab-a",
        suffix: str = "",
    ) -> dict:
        paths = {}
        for role in ("acoustic", "dictionary", "g2p"):
            path = root / f"{role}{suffix}.model"
            path.write_bytes(f"{role}-same-content".encode("utf-8"))
            paths[role] = path
        return build_alignment_contract(
            year="2022",
            lab_input_contract_id=lab_contract,
            acoustic_model_path=paths["acoustic"],
            dictionary_model_path=paths["dictionary"],
            g2p_model_path=paths["g2p"],
            runtime={
                "python": "3.13.14",
                "montreal_forced_aligner": "3.4.0",
                "pynini": "2.1.7",
            },
        )

    def test_same_content_at_different_paths_has_same_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_contract(root, suffix="-a")
            second = self.make_contract(root, suffix="-b")
            self.assertEqual(
                first["alignment_contract_id"],
                second["alignment_contract_id"],
            )

    def test_model_content_change_changes_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_contract(root)
            changed = root / "g2p.model"
            changed.write_bytes(b"changed-g2p")
            second = build_alignment_contract(
                year="2022",
                lab_input_contract_id="lab-a",
                acoustic_model_path=root / "acoustic.model",
                dictionary_model_path=root / "dictionary.model",
                g2p_model_path=changed,
                runtime=first["runtime"],
            )
            self.assertNotEqual(
                first["alignment_contract_id"],
                second["alignment_contract_id"],
            )

    def test_lab_contract_change_changes_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_contract(root, lab_contract="lab-a")
            second = self.make_contract(root, lab_contract="lab-b")
            self.assertNotEqual(
                first["alignment_contract_id"],
                second["alignment_contract_id"],
            )


if __name__ == "__main__":
    unittest.main()
