import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from pipeline_common import sha256_file  # noqa: E402
from validate_mfa_r2_adoption import validate_adoption  # noqa: E402


class MfaR2AdoptionValidationTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        dictionary = root / "common.dict"
        acoustic = root / "acoustic.zip"
        g2p = root / "g2p.zip"
        dictionary.write_text("단어\tt a n\n", encoding="utf-8")
        acoustic.write_bytes(b"acoustic")
        g2p.write_bytes(b"g2p")
        bundle = root / "bundle.json"
        bundle.write_text("{}", encoding="utf-8")

        manifest_path = root / "release.json"
        manifest = {
            "schema_version": "common_pron_mfa_lexicon.v2",
            "status": "success",
            "release_id": "r2",
            "release_contract_id": "contract",
            "phone_inventory_contract": {
                "count": 2,
                "phones": ["a", "t"],
                "sorted_phone_sha256": "phone-contract",
            },
            "outputs": {
                "dictionary": {"sha256": sha256_file(dictionary)}
            },
            "inputs": {
                "acoustic_model": {"sha256": sha256_file(acoustic)},
                "g2p_model": {"sha256": sha256_file(g2p)},
            },
        }
        manifest_path.write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        adoption_path = root / "adoption.json"
        adoption = {
            "schema_version": "common_pron_mfa_adoption.v3",
            "status": "passed",
            "policy": "latest_jamo_common_dictionary_required",
            "common_release": {
                "manifest": {
                    "path": str(manifest_path),
                    "sha256": sha256_file(manifest_path),
                },
                "dictionary": {
                    "path": str(dictionary),
                    "sha256": sha256_file(dictionary),
                },
            },
            "frozen_model_pin": {
                "contract": {
                    "path": str(bundle),
                    "sha256": sha256_file(bundle),
                },
                "models": {
                    "acoustic_model": {
                        "path": str(acoustic),
                        "sha256": sha256_file(acoustic),
                    },
                    "g2p_model": {
                        "path": str(g2p),
                        "sha256": sha256_file(g2p),
                    },
                }
            },
            "gate": {
                "allow_yearly_mfa": True,
                "legacy_inline_g2p_default": False,
                "dictionary_missing": 0,
                "dictionary_spn_words": 0,
                "phone_outside_acoustic_inventory": 0,
            },
        }
        adoption_path.write_text(
            json.dumps(adoption), encoding="utf-8"
        )
        return manifest_path, adoption_path

    def test_passes_exact_r2_contract_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, adoption = self._fixture(Path(tmp))
            report = validate_adoption(manifest, adoption)
            self.assertEqual(report["status"], "passed")
            self.assertFalse(report["inline_g2p_used"])

    def test_rejects_tampered_dictionary(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, adoption = self._fixture(Path(tmp))
            dictionary = Path(
                json.loads(adoption.read_text())["common_release"]
                ["dictionary"]["path"]
            )
            dictionary.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "SHA256"):
                validate_adoption(manifest, adoption)

    def test_project_gate_blocks_known_bad_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, adoption = self._fixture(root)
            gate = root / "gate.json"
            gate.write_text(
                json.dumps(
                    {
                        "schema_version": "mfa_pronunciation_release_gate.v1",
                        "status": "blocked_pending_r3",
                        "blocked_release_ids": ["r2"],
                        "allowed_release_ids": [],
                        "reason": "rule audit failed",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "release를 차단"):
                validate_adoption(manifest, adoption, gate)

    def test_project_gate_requires_explicit_adoption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, adoption = self._fixture(root)
            gate = root / "gate.json"
            gate.write_text(
                json.dumps(
                    {
                        "schema_version": "mfa_pronunciation_release_gate.v1",
                        "status": "adopted",
                        "blocked_release_ids": [],
                        "allowed_release_ids": ["r2"],
                        "reason": "test fixture",
                    }
                ),
                encoding="utf-8",
            )
            report = validate_adoption(manifest, adoption, gate)
            self.assertEqual(
                report["project_pronunciation_release_gate"]["status"],
                "adopted",
            )

    def test_project_r3_contract_requires_six_year_textgrid_materialization(self):
        gate = json.loads(
            (ROOT / "config" / "mfa_pronunciation_release_gate.json")
            .read_text(encoding="utf-8-sig")
        )
        draft = json.loads(
            (ROOT / "config" / "common_pronunciation_resource_contract_v3_draft.json")
            .read_text(encoding="utf-8-sig")
        )
        materialization = draft["textgrid_materialization_gate"]
        self.assertEqual(
            materialization["years"], [2020, 2021, 2022, 2023, 2024, 2025]
        )
        self.assertFalse(materialization["in_place_r2_label_rewrite_allowed"])
        self.assertEqual(
            materialization["source_of_words_and_phones"],
            "either a new MFA database aligned with r3 or an existing r2 interval set proven pronunciation-equivalent for the complete MFA adaptation unit",
        )
        self.assertEqual(
            materialization["required_tiers"],
            [
                "words",
                "phones_mfa",
                "phoneme_r_auto",
                "utterance",
                "utterance_orth_r",
                "morph_analysis_utt",
            ],
        )
        requirements = "\n".join(gate["r3_adoption_requirements"])
        self.assertIn("2020 through 2025", requirements)
        self.assertIn("TextGrid", requirements)
        self.assertIn("dictionary SHA", requirements)
        self.assertTrue(draft["rerun_policy"]["unchanged_r2_reuse_allowed"])
        self.assertEqual(
            draft["rerun_policy"]["changed_unit_scope"],
            "realign the complete MFA speaker/session adaptation unit when any token pronunciation variant changes",
        )


if __name__ == "__main__":
    unittest.main()
