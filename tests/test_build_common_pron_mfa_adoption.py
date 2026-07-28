import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_common_pron_mfa_adoption as adoption  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


class CommonPronAdoptionTests(unittest.TestCase):
    def fixture(self, root: Path) -> dict[str, Path]:
        dictionary = root / "common.dict"
        dictionary.write_text("가\tk a\n", encoding="utf-8")
        review = root / "jamo_ls_review.csv"
        words = sorted(adoption.REQUIRED_JAMO_LS_WORDS)
        reviewed_pronunciations = {
            word: f"k a {index}"
            for index, word in enumerate(words, 1)
        }
        review.write_text(
            "token,model_input,pron_phones_mfa,decision,notes\n"
            + "".join(
                f"{word},{word},{reviewed_pronunciations[word]},"
                "approved,\n"
                for word in words
            ),
            encoding="utf-8-sig",
        )
        model_shas = {
            role: hashlib.sha256(role.encode()).hexdigest()
            for role in ("acoustic_model", "g2p_model", "dictionary")
        }
        common = root / "release.json"
        common.write_text(
            json.dumps(
                {
                    "schema_version": "common_pron_mfa_lexicon.v2",
                    "status": "success",
                    "release_id": "common_pron_mfa_r2_test",
                    "counts": {
                        "g2p_missing": 0,
                        "g2p_spn_words": 0,
                        "phone_outside_acoustic_inventory": 0,
                        "observed_oov_coverage_missing": 0,
                        "g2p_jamo_ls_rewrite_words": 4,
                    },
                    "inputs": {
                        "acoustic_model": {
                            "sha256": model_shas["acoustic_model"]
                        },
                        "g2p_model": {
                            "sha256": model_shas["g2p_model"]
                        },
                        "base_dictionary": {
                            "sha256": model_shas["dictionary"]
                        },
                    },
                    "outputs": {
                        "dictionary": file_fingerprint(
                            dictionary, with_sha256=True
                        )
                    },
                    "dictionary_contract": {
                        "jamo_ls_surface_key_restoration": True,
                        "jamo_ls_researcher_review": file_fingerprint(
                            review, with_sha256=True
                        ),
                    },
                }
            ),
            encoding="utf-8",
        )
        common_fp = file_fingerprint(common, with_sha256=True)
        difference = root / "difference.json"
        difference.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "common_pron_mfa_difference_inventory.v2"
                    ),
                    "status": "differences_inventoried",
                    "mode": "difference-inventory",
                    "common_release": {"manifest": common_fp},
                    "gate": {
                        "difference_inventory_complete": True,
                        "allow_yearly_mfa": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        difference_fp = file_fingerprint(
            difference, with_sha256=True
        )
        approval = root / "approval.json"
        approval.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "common_pron_mfa_researcher_approval.v1"
                    ),
                    "status": "approved",
                    "approved": True,
                    "common_manifest_sha256": common_fp["sha256"],
                    "difference_inventory_sha256": difference_fp[
                        "sha256"
                    ],
                    "jamo_ls": {
                        "decision": "approved",
                        "phone_inventory_changed": False,
                        "required_words": words,
                        "reviewed_words": words,
                        "reviewed_pronunciations": (
                            reviewed_pronunciations
                        ),
                    },
                }
            ),
            encoding="utf-8",
        )
        bundle = root / "bundle.json"
        bundle.write_text("{}", encoding="utf-8")
        return {
            "common": common,
            "difference": difference,
            "approval": approval,
            "bundle": bundle,
            "model_shas": model_shas,
        }

    def pin(self, paths: dict) -> dict:
        return {
            "expected": {"commit": "0091ffa1"},
            "contract": {
                "path": str(paths["bundle"]),
                "bytes": 2,
                "mtime_ns": 1,
                "sha256": "bundle-sha",
            },
            "models": {
                role: {"sha256": sha}
                for role, sha in paths["model_shas"].items()
            },
        }

    def test_all_gates_issue_adoption_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            with patch(
                "build_common_pron_mfa_adoption.verify_frozen_bundle",
                return_value=self.pin(paths),
            ):
                result = adoption.build_adoption_contract(
                    common_manifest_path=paths["common"],
                    frozen_bundle_contract_path=paths["bundle"],
                    difference_inventory_path=paths["difference"],
                    researcher_approval_path=paths["approval"],
                )
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["allow_yearly_mfa"])

    def test_missing_researcher_review_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            approval = json.loads(
                paths["approval"].read_text(encoding="utf-8")
            )
            approval["jamo_ls"]["reviewed_words"].pop()
            paths["approval"].write_text(
                json.dumps(approval), encoding="utf-8"
            )
            with patch(
                "build_common_pron_mfa_adoption.verify_frozen_bundle",
                return_value=self.pin(paths),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "researcher approval"
                ):
                    adoption.build_adoption_contract(
                        common_manifest_path=paths["common"],
                        frozen_bundle_contract_path=paths["bundle"],
                        difference_inventory_path=paths["difference"],
                        researcher_approval_path=paths["approval"],
                    )


if __name__ == "__main__":
    unittest.main()
