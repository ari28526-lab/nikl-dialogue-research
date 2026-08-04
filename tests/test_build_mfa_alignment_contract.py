import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_mfa_alignment_contract import (  # noqa: E402
    build_alignment_contract,
    recompute_alignment_contract_id,
    write_alignment_contract_if_changed,
)
from mfa_exclusion_contract import REVIEW_FIELDS, build_contract  # noqa: E402


class MfaAlignmentContractTests(unittest.TestCase):
    def pin_for(self, root: Path, paths: dict[str, Path]) -> dict:
        return {
            "expected": {"commit": "pinned-commit"},
            "contract": {
                "path": str(root / "bundle.json"),
                "bytes": 1,
                "mtime_ns": 1,
                "sha256": "bundle-sha",
            },
            "models": {
                "acoustic_model": {
                    "sha256": hashlib.sha256(
                        paths["acoustic"].read_bytes()
                    ).hexdigest()
                },
                "g2p_model": {
                    "sha256": hashlib.sha256(
                        paths["g2p"].read_bytes()
                    ).hexdigest()
                },
                "dictionary": {
                    "sha256": hashlib.sha256(
                        paths["dictionary"].read_bytes()
                    ).hexdigest()
                },
            },
        }

    def make_contract(
        self,
        root: Path,
        *,
        lab_contract: str = "lab-a",
        suffix: str = "",
        approved_exclusions: Path | None = None,
    ) -> dict:
        paths = {}
        for role in ("acoustic", "dictionary", "g2p"):
            path = root / f"{role}{suffix}.model"
            path.write_bytes(f"{role}-same-content".encode("utf-8"))
            paths[role] = path
        with patch(
            "build_mfa_alignment_contract.verify_frozen_bundle",
            return_value=self.pin_for(root, paths),
        ):
            return build_alignment_contract(
                year="2022",
                lab_input_contract_id=lab_contract,
                acoustic_model_path=paths["acoustic"],
                dictionary_model_path=paths["dictionary"],
                g2p_model_path=paths["g2p"],
                frozen_bundle_contract_path=root / "bundle.json",
                approved_exclusions_contract_path=approved_exclusions,
                allow_legacy_inline_g2p=True,
                runtime={
                    "python": "3.13.14",
                    "montreal_forced_aligner": "3.4.0",
                    "pynini": "2.1.7",
                },
            )

    def make_approved_exclusions(
        self,
        root: Path,
        *,
        lab_contract: str,
        suffix: str,
        notes: str,
    ) -> Path:
        review = root / f"review-{suffix}.csv"
        with review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "year": "2022",
                    "input_contract_id": lab_contract,
                    "utt_id": f"U-{suffix}",
                    "reason_code": "audio_pairing_unresolved",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": "audit.json",
                    "decision": "approved",
                    "notes": notes,
                }
            )
        output = root / f"approved-{suffix}.json"
        build_contract(
            review_csv=review,
            output=output,
            year="2022",
            input_contract_id=lab_contract,
            approved_by="tester",
            approved_at="2026-08-04T00:00:00+09:00",
        )
        return output

    def test_same_content_at_different_paths_has_same_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_contract(root, suffix="-a")
            second = self.make_contract(root, suffix="-b")
            self.assertEqual(
                first["alignment_contract_id"],
                second["alignment_contract_id"],
            )
            self.assertEqual(
                recompute_alignment_contract_id(first),
                first["alignment_contract_id"],
            )

    def test_identical_semantic_contract_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "alignment.json"
            first = self.make_contract(root, suffix="-stable")
            self.assertTrue(write_alignment_contract_if_changed(output, first))
            before = output.read_bytes()

            second = json.loads(json.dumps(first))
            second["recorded_at"] = "2099-01-01T00:00:00+09:00"
            self.assertFalse(
                write_alignment_contract_if_changed(output, second)
            )
            self.assertEqual(output.read_bytes(), before)

            changed = self.make_contract(
                root, lab_contract="lab-b", suffix="-changed"
            )
            self.assertTrue(
                write_alignment_contract_if_changed(output, changed)
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))[
                    "alignment_contract_id"
                ],
                changed["alignment_contract_id"],
            )

    def test_model_content_change_changes_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_contract(root)
            changed = root / "g2p.model"
            changed.write_bytes(b"changed-g2p")
            paths = {
                "acoustic": root / "acoustic.model",
                "dictionary": root / "dictionary.model",
                "g2p": changed,
            }
            with patch(
                "build_mfa_alignment_contract.verify_frozen_bundle",
                return_value=self.pin_for(root, paths),
            ):
                second = build_alignment_contract(
                    year="2022",
                    lab_input_contract_id="lab-a",
                    acoustic_model_path=paths["acoustic"],
                    dictionary_model_path=paths["dictionary"],
                    g2p_model_path=changed,
                    frozen_bundle_contract_path=root / "bundle.json",
                    allow_legacy_inline_g2p=True,
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

    def test_approved_exclusion_sha_changes_alignment_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_approval = self.make_approved_exclusions(
                root,
                lab_contract="lab-a",
                suffix="a",
                notes="first",
            )
            second_approval = self.make_approved_exclusions(
                root,
                lab_contract="lab-a",
                suffix="b",
                notes="second",
            )
            first = self.make_contract(
                root,
                suffix="-approved-a",
                approved_exclusions=first_approval,
            )
            second = self.make_contract(
                root,
                suffix="-approved-b",
                approved_exclusions=second_approval,
            )
            self.assertNotEqual(
                first["alignment_contract_id"],
                second["alignment_contract_id"],
            )
            self.assertEqual(
                first["approved_exclusions_contract"]["path"],
                str(first_approval.resolve()),
            )

    def test_approved_exclusion_input_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval = self.make_approved_exclusions(
                root,
                lab_contract="other-lab",
                suffix="mismatch",
                notes="wrong input",
            )
            with self.assertRaisesRegex(RuntimeError, "identity/status"):
                self.make_contract(
                    root,
                    lab_contract="lab-a",
                    suffix="-mismatch",
                    approved_exclusions=approval,
                )


if __name__ == "__main__":
    unittest.main()
