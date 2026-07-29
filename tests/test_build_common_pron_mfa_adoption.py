import csv
import hashlib
import json
import shutil
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


def write_csv(
    path: Path,
    fields: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


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
            "token,model_input,pron_phones_mfa,"
            "approved_pron_phones_mfa,decision,evidence_source,notes\n"
            + "".join(
                f"{word},{word},k a,"
                f"{reviewed_pronunciations[word]},approved,"
                "official_test,reviewed\n"
                for word in words
            ),
            encoding="utf-8-sig",
        )
        approved_dictionary = root / "jamo_ls_approved.dict"
        approved_dictionary.write_text(
            "".join(
                f"{word}\t{reviewed_pronunciations[word]}\n"
                for word in words
            ),
            encoding="utf-8",
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
                        "g2p_jamo_ls_model_candidate_accepted_words": 2,
                        "g2p_jamo_ls_manual_override_words": 2,
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
                        "jamo_ls_manual_override_policy": (
                            "researcher_approved_same_acoustic_inventory_only"
                        ),
                        "jamo_ls_researcher_review": file_fingerprint(
                            review, with_sha256=True
                        ),
                        "jamo_ls_approved_pronunciations": file_fingerprint(
                            approved_dictionary, with_sha256=True
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
                    "schema_version": adoption.APPROVAL_SCHEMA_VERSION,
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
        paths = {
            "common": common,
            "difference": difference,
            "approval": approval,
            "bundle": bundle,
            "jamo_review": review,
            "approved_dictionary": approved_dictionary,
            "model_shas": model_shas,
        }
        self.attach_decision_application(
            root=root,
            paths=paths,
            reviewed_pronunciations=reviewed_pronunciations,
        )
        return paths

    def attach_decision_application(
        self,
        *,
        root: Path,
        paths: dict,
        reviewed_pronunciations: dict[str, str],
    ) -> None:
        no_path_tokens = [
            f"읊계열{index:02d}" for index in range(1, 24)
        ]
        no_path_rows = [
            {
                "surface": "읊어",
                "respelled": "을퍼",
                "rule_id": "legacy_rule",
                "evidence_source": "fixture",
                "evidence_detail": "fixture",
                "pron_phones_mfa": "k a",
                "approved_pron_phones_mfa": "k a",
                "approved_phone_evidence": "legacy_fixture",
                "decision": "approved",
                "notes": "preserved legacy approval",
            },
            *[
                {
                    "surface": token,
                    "respelled": f"모델입력{index:02d}",
                    "rule_id": "fixture_rule",
                    "evidence_source": "fixture",
                    "evidence_detail": "fixture",
                    "pron_phones_mfa": "k a",
                    "approved_pron_phones_mfa": "k a",
                    "approved_phone_evidence": "fixture",
                    "decision": "approved",
                    "notes": "fixture approval",
                }
                for index, token in enumerate(no_path_tokens, 1)
            ],
        ]
        no_path_review = root / "g2p_no_path_researcher_review.csv"
        write_csv(
            no_path_review, adoption.NO_PATH_FIELDS, no_path_rows
        )
        paths["no_path_review"] = no_path_review

        decisions: list[dict[str, str]] = []
        for index, row in enumerate(no_path_rows[1:], 1):
            decisions.append(
                {
                    "review_order": str(index),
                    "category": "no_path",
                    "token": row["surface"],
                    "model_input": row["respelled"],
                    "model_candidate_phone": row[
                        "pron_phones_mfa"
                    ],
                    "recommendation_action": (
                        "accept_model_candidate"
                    ),
                    "researcher_decision": "approve_recommended",
                    "approved_pron_phones_mfa": row[
                        "approved_pron_phones_mfa"
                    ],
                    "approved_phone_source": "fixture",
                    "approved_phone_provenance": (
                        "researcher_workbook_same_frozen_candidate"
                    ),
                    "researcher_notes": "",
                    "source_handling": "none",
                    "source_url": "",
                    "reason": "fixture",
                    "example_utt_id": f"utt-{index}",
                    "review_wav": "",
                }
            )
        for index, word in enumerate(
            sorted(adoption.REQUIRED_JAMO_LS_WORDS), 24
        ):
            decisions.append(
                {
                    "review_order": str(index),
                    "category": "jamo_ls",
                    "token": word,
                    "model_input": word,
                    "model_candidate_phone": "k a",
                    "recommendation_action": "manual",
                    "researcher_decision": "approve_custom",
                    "approved_pron_phones_mfa": (
                        reviewed_pronunciations[word]
                    ),
                    "approved_phone_source": "fixture",
                    "approved_phone_provenance": (
                        "researcher_workbook_manual_same_inventory"
                    ),
                    "researcher_notes": "fixture",
                    "source_handling": "fixture",
                    "source_url": "",
                    "reason": "fixture",
                    "example_utt_id": f"utt-{index}",
                    "review_wav": "",
                }
            )
        decisions_path = root / "normalized_decisions.csv"
        write_csv(
            decisions_path, adoption.DECISION_FIELDS, decisions
        )
        corrections = []
        for token, spec in adoption.EXPECTED_CORRECTIONS.items():
            decision = next(
                row for row in decisions if row["token"] == token
            )
            corrections.append(
                {
                    "review_order": decision["review_order"],
                    "token": token,
                    **spec,
                    "source_notation": "fixture",
                    "approved_pron_phones_mfa": (
                        reviewed_pronunciations[token]
                    ),
                    "researcher_decision": "approve_custom",
                    "researcher_notes": "fixture",
                    "example_utt_id": "fixture",
                }
            )
        correction_registry = root / "correction_registry.csv"
        write_csv(
            correction_registry,
            adoption.CORRECTION_FIELDS,
            corrections,
        )
        paths["correction_registry"] = correction_registry

        evidence_source = root / "evidence_source"
        evidence_source.mkdir()
        clean_template = evidence_source / "clean.xlsx"
        filled_workbook = evidence_source / "filled.xlsx"
        template_manifest = evidence_source / "template.json"
        model_bundle = evidence_source / "model_bundle.json"
        clean_template.write_bytes(b"clean workbook fixture")
        filled_workbook.write_bytes(b"filled workbook fixture")
        template_manifest.write_text(
            '{"schema_version":"fixture.template.v1"}\n',
            encoding="utf-8",
        )
        model_bundle.write_text(
            '{"schema_version":"fixture.model_bundle.v1"}\n',
            encoding="utf-8",
        )
        validation = root / "validation.json"
        validation.write_text(
            json.dumps(
                {
                    "schema_version": (
                        adoption.VALIDATION_SCHEMA_VERSION
                    ),
                    "status": "ready_for_apply",
                    "kind": (
                        "common_pron_r2_researcher_decision_validation"
                    ),
                    "ready_for_apply": True,
                    "inputs": {
                        "clean_template": file_fingerprint(
                            clean_template, with_sha256=True
                        ),
                        "filled_workbook": file_fingerprint(
                            filled_workbook, with_sha256=True
                        ),
                        "template_manifest": file_fingerprint(
                            template_manifest, with_sha256=True
                        ),
                        "model_bundle": file_fingerprint(
                            model_bundle, with_sha256=True
                        ),
                    },
                    "outputs": {
                        "normalized_decisions": file_fingerprint(
                            decisions_path, with_sha256=True
                        ),
                        "correction_registry": file_fingerprint(
                            correction_registry, with_sha256=True
                        ),
                    },
                    "counts": {
                        "normalized_decisions": 27,
                        "correction_registry_rows": 2,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        transaction = root / "transaction"
        archive = transaction / "archive"
        proposals = transaction / "proposed"
        evidence = transaction / "evidence"
        archive.mkdir(parents=True)
        proposals.mkdir()
        evidence.mkdir()
        original_no_path = archive / "original_no_path.csv"
        original_jamo = archive / "original_jamo.csv"
        original_no_path.write_text("original\n", encoding="utf-8")
        original_jamo.write_text("original\n", encoding="utf-8")
        proposal_no_path = proposals / "no_path.csv"
        proposal_jamo = proposals / "jamo.csv"
        proposal_corrections = proposals / "corrections.csv"
        shutil.copy2(no_path_review, proposal_no_path)
        shutil.copy2(paths["jamo_review"], proposal_jamo)
        shutil.copy2(correction_registry, proposal_corrections)
        evidence_sources = {
            "validation_manifest": validation,
            "template_manifest": template_manifest,
            "clean_template": clean_template,
            "filled_workbook": filled_workbook,
            "model_bundle": model_bundle,
            "normalized_decisions": decisions_path,
            "correction_registry": correction_registry,
        }
        evidence_records = {}
        for label, source in evidence_sources.items():
            destination = evidence / f"{label}__{source.name}"
            shutil.copy2(source, destination)
            evidence_records[label] = file_fingerprint(
                destination, with_sha256=True
            )
        application = root / "application.json"
        application.write_text(
            json.dumps(
                {
                    "schema_version": (
                        adoption.APPLICATION_SCHEMA_VERSION
                    ),
                    "status": "applied",
                    "kind": adoption.APPLICATION_KIND,
                    "transaction_id": "review_fixture",
                    "release_id": "common_pron_mfa_r2_test",
                    "inputs": {
                        "validation_manifest": file_fingerprint(
                            validation, with_sha256=True
                        )
                    },
                    "archives": {
                        "no_path_review": file_fingerprint(
                            original_no_path, with_sha256=True
                        ),
                        "jamo_review": file_fingerprint(
                            original_jamo, with_sha256=True
                        ),
                        "decision_evidence": evidence_records,
                    },
                    "proposals": {
                        "no_path_review": file_fingerprint(
                            proposal_no_path, with_sha256=True
                        ),
                        "jamo_review": file_fingerprint(
                            proposal_jamo, with_sha256=True
                        ),
                        "correction_registry": file_fingerprint(
                            proposal_corrections, with_sha256=True
                        ),
                    },
                    "outputs": {
                        "no_path_review": file_fingerprint(
                            no_path_review, with_sha256=True
                        ),
                        "jamo_review": file_fingerprint(
                            paths["jamo_review"], with_sha256=True
                        ),
                        "correction_registry": file_fingerprint(
                            correction_registry, with_sha256=True
                        ),
                    },
                    "counts": adoption.EXPECTED_APPLICATION_COUNTS,
                    "gates": adoption.EXPECTED_APPLICATION_GATES,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        paths["application"] = application

        snapshot = root / "approved_review_snapshot.csv"
        shutil.copy2(no_path_review, snapshot)
        repair = root / "repair.json"
        repair.write_text(
            json.dumps(
                {
                    "schema_version": "common_pron_g2p_no_path.v2",
                    "status": "success",
                    "kind": "reviewed_no_path_shard_repair",
                    "used_candidates": no_path_rows,
                    "inputs": {
                        "researcher_review": file_fingerprint(
                            no_path_review, with_sha256=True
                        ),
                        "approved_review_snapshot": file_fingerprint(
                            snapshot, with_sha256=True
                        ),
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        cache = root / "cache.csv"
        cache.write_text("token\nfixture\n", encoding="utf-8")
        cache_fp = file_fingerprint(cache, with_sha256=True)
        supplement = root / "supplement.json"
        supplement.write_text(
            json.dumps(
                {
                    "schema_version": adoption.NO_PATH_SCHEMA_VERSION,
                    "status": "success",
                    "kind": (
                        "reviewed_g2p_no_path_method_supplement"
                    ),
                    "production_release_contract_id": "production",
                    "counts": {
                        "reviewed_no_path_words": 24,
                        "manual_phone_override_words": 0,
                    },
                    "policy": {
                        "same_frozen_jamo_g2p_required": True,
                        (
                            "researcher_approved_standard_"
                            "respelling_required"
                        ): True,
                        (
                            "manual_phone_override_same_"
                            "acoustic_inventory_only"
                        ): True,
                        "only_missing_surface_keys_added": True,
                        "existing_model_pronunciations_replaced": 0,
                        "final_spn_words": 0,
                        "phone_inventory_changed": False,
                    },
                    "reviewed_candidates": no_path_rows,
                    "inputs": {
                        "repair_manifests": [
                            file_fingerprint(
                                repair, with_sha256=True
                            )
                        ]
                    },
                    "outputs": {"g2p_cache": cache_fp},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        release = json.loads(
            paths["common"].read_text(encoding="utf-8")
        )
        release["release_contract_id"] = "production"
        release["counts"].update(
            {
                "g2p_reviewed_no_path_words": 24,
                "g2p_reviewed_no_path_manual_override_words": 0,
                "g2p_existing_model_pronunciations_replaced": 0,
            }
        )
        release["outputs"]["g2p_cache"] = cache_fp
        release["method_supplements"] = {
            "reviewed_g2p_no_path": file_fingerprint(
                supplement, with_sha256=True
            )
        }
        paths["common"].write_text(
            json.dumps(release, ensure_ascii=False),
            encoding="utf-8",
        )
        common_fp = file_fingerprint(
            paths["common"], with_sha256=True
        )
        difference = json.loads(
            paths["difference"].read_text(encoding="utf-8")
        )
        difference["common_release"]["manifest"] = common_fp
        paths["difference"].write_text(
            json.dumps(difference, ensure_ascii=False),
            encoding="utf-8",
        )
        difference_fp = file_fingerprint(
            paths["difference"], with_sha256=True
        )
        approval = json.loads(
            paths["approval"].read_text(encoding="utf-8")
        )
        approval.update(
            {
                "schema_version": adoption.APPROVAL_SCHEMA_VERSION,
                "common_manifest_sha256": common_fp["sha256"],
                "difference_inventory_sha256": difference_fp[
                    "sha256"
                ],
                "decision_application_sha256": file_fingerprint(
                    application, with_sha256=True
                )["sha256"],
                "correction_registry_sha256": file_fingerprint(
                    correction_registry, with_sha256=True
                )["sha256"],
            }
        )
        paths["approval"].write_text(
            json.dumps(approval, ensure_ascii=False),
            encoding="utf-8",
        )

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
                    decision_application_path=paths["application"],
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
                        decision_application_path=paths["application"],
                        difference_inventory_path=paths["difference"],
                        researcher_approval_path=paths["approval"],
                    )

    def test_jamo_approved_dictionary_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            paths["approved_dictionary"].write_text(
                "외곬의\twrong phones\n", encoding="utf-8"
            )
            with patch(
                "build_common_pron_mfa_adoption.verify_frozen_bundle",
                return_value=self.pin(paths),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "fingerprint mismatch"
                ):
                    adoption.build_adoption_contract(
                        common_manifest_path=paths["common"],
                        frozen_bundle_contract_path=paths["bundle"],
                        decision_application_path=paths["application"],
                        difference_inventory_path=paths["difference"],
                        researcher_approval_path=paths["approval"],
                    )

    def test_application_evidence_archive_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            application = json.loads(
                paths["application"].read_text(encoding="utf-8")
            )
            del application["archives"]["decision_evidence"][
                "filled_workbook"
            ]
            paths["application"].write_text(
                json.dumps(application, ensure_ascii=False),
                encoding="utf-8",
            )
            with patch(
                "build_common_pron_mfa_adoption.verify_frozen_bundle",
                return_value=self.pin(paths),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "evidence archive is incomplete"
                ):
                    adoption.build_adoption_contract(
                        common_manifest_path=paths["common"],
                        frozen_bundle_contract_path=paths["bundle"],
                        decision_application_path=paths[
                            "application"
                        ],
                        difference_inventory_path=paths["difference"],
                        researcher_approval_path=paths["approval"],
                    )

    def test_tampered_applied_correction_registry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            with paths["correction_registry"].open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write("\n")
            with patch(
                "build_common_pron_mfa_adoption.verify_frozen_bundle",
                return_value=self.pin(paths),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "application correction_registry fingerprint mismatch",
                ):
                    adoption.build_adoption_contract(
                        common_manifest_path=paths["common"],
                        frozen_bundle_contract_path=paths["bundle"],
                        decision_application_path=paths[
                            "application"
                        ],
                        difference_inventory_path=paths["difference"],
                        researcher_approval_path=paths["approval"],
                    )

    def test_approval_must_bind_decision_application(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            approval = json.loads(
                paths["approval"].read_text(encoding="utf-8")
            )
            del approval["decision_application_sha256"]
            paths["approval"].write_text(
                json.dumps(approval, ensure_ascii=False),
                encoding="utf-8",
            )
            with patch(
                "build_common_pron_mfa_adoption.verify_frozen_bundle",
                return_value=self.pin(paths),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "researcher approval gate failed"
                ):
                    adoption.build_adoption_contract(
                        common_manifest_path=paths["common"],
                        frozen_bundle_contract_path=paths["bundle"],
                        decision_application_path=paths[
                            "application"
                        ],
                        difference_inventory_path=paths["difference"],
                        researcher_approval_path=paths["approval"],
                    )

    def test_reviewed_no_path_supplement_is_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / "cache.csv"
            cache.write_text("token\n읊어\n", encoding="utf-8")
            cache_fp = file_fingerprint(cache, with_sha256=True)
            repair = root / "repair.json"
            repair.write_text('{"status":"success"}\n', encoding="utf-8")
            repair_fp = file_fingerprint(repair, with_sha256=True)
            supplement = root / "supplement.json"
            supplement.write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "common_pron_g2p_no_path_supplement.v1"
                        ),
                        "status": "success",
                        "kind": (
                            "reviewed_g2p_no_path_method_supplement"
                        ),
                        "production_release_contract_id": "production",
                        "counts": {
                            "reviewed_no_path_words": 1,
                            "manual_phone_override_words": 0,
                        },
                        "policy": {
                            "same_frozen_jamo_g2p_required": True,
                            (
                                "researcher_approved_standard_"
                                "respelling_required"
                            ): True,
                            (
                                "manual_phone_override_same_"
                                "acoustic_inventory_only"
                            ): True,
                            "only_missing_surface_keys_added": True,
                            "existing_model_pronunciations_replaced": 0,
                            "final_spn_words": 0,
                            "phone_inventory_changed": False,
                        },
                        "inputs": {
                            "repair_manifests": [repair_fp]
                        },
                        "outputs": {"g2p_cache": cache_fp},
                    }
                ),
                encoding="utf-8",
            )
            release = {
                "release_contract_id": "production",
                "counts": {
                    "g2p_reviewed_no_path_words": 1,
                    "g2p_reviewed_no_path_manual_override_words": 0,
                    "g2p_existing_model_pronunciations_replaced": 0,
                },
                "outputs": {"g2p_cache": cache_fp},
                "method_supplements": {
                    "reviewed_g2p_no_path": file_fingerprint(
                        supplement, with_sha256=True
                    )
                },
            }
            result = adoption._verified_no_path_supplement(release)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(
                result["counts"]["reviewed_no_path_words"], 1
            )

    def test_tampered_no_path_repair_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / "cache.csv"
            cache.write_text("token\n읊어\n", encoding="utf-8")
            cache_fp = file_fingerprint(cache, with_sha256=True)
            repair = root / "repair.json"
            repair.write_text('{"status":"success"}\n', encoding="utf-8")
            repair_fp = file_fingerprint(repair, with_sha256=True)
            supplement = root / "supplement.json"
            supplement.write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "common_pron_g2p_no_path_supplement.v1"
                        ),
                        "status": "success",
                        "kind": (
                            "reviewed_g2p_no_path_method_supplement"
                        ),
                        "production_release_contract_id": "production",
                        "counts": {
                            "reviewed_no_path_words": 1,
                            "manual_phone_override_words": 0,
                        },
                        "policy": {
                            "same_frozen_jamo_g2p_required": True,
                            (
                                "researcher_approved_standard_"
                                "respelling_required"
                            ): True,
                            (
                                "manual_phone_override_same_"
                                "acoustic_inventory_only"
                            ): True,
                            "only_missing_surface_keys_added": True,
                            "existing_model_pronunciations_replaced": 0,
                            "final_spn_words": 0,
                            "phone_inventory_changed": False,
                        },
                        "inputs": {
                            "repair_manifests": [repair_fp]
                        },
                        "outputs": {"g2p_cache": cache_fp},
                    }
                ),
                encoding="utf-8",
            )
            release = {
                "release_contract_id": "production",
                "counts": {
                    "g2p_reviewed_no_path_words": 1,
                    "g2p_reviewed_no_path_manual_override_words": 0,
                    "g2p_existing_model_pronunciations_replaced": 0,
                },
                "outputs": {"g2p_cache": cache_fp},
                "method_supplements": {
                    "reviewed_g2p_no_path": file_fingerprint(
                        supplement, with_sha256=True
                    )
                },
            }
            repair.write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "repair manifest fingerprint"
            ):
                adoption._verified_no_path_supplement(release)


if __name__ == "__main__":
    unittest.main()
