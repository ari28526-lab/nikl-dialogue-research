import json
import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from export_mfa_db_research_6tier import (  # noqa: E402
    load_targeted_repair_resume,
)
from pipeline_common import file_fingerprint  # noqa: E402
from repair_mfa_textgrid_terminal_roundoff import (  # noqa: E402
    legacy_materialize_intervals,
)
from research_textgrid_v2 import _materialize_intervals  # noqa: E402


class MfaTextGridRoundoffRepairTests(unittest.TestCase):
    def test_legacy_writer_materializes_float32_terminal_gap(self):
        duration = 98.84
        float32_end = struct.unpack("!f", struct.pack("!f", duration))[0]
        self.assertLess(float32_end, duration)
        old = legacy_materialize_intervals(
            [(0.0, float32_end, "speech")], duration
        )
        current = _materialize_intervals(
            [(0.0, float32_end, "speech")], duration
        )
        self.assertEqual(len(old), 2)
        self.assertEqual(old[-1][2], "")
        self.assertEqual(len(current), 1)
        self.assertEqual(current[-1], (0.0, duration, "speech"))

    def test_exact_targeted_repair_resume_is_accounted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "year.db"
            acoustic = root / "acoustic.zip"
            contract = root / "alignment.json"
            search = root / "search"
            output = root / "partial"
            destination = output / "2021" / "S1" / "U3.TextGrid"
            archive = root / "archive" / "2021" / "S1" / "U3.TextGrid"
            for path, content in (
                (db, b"db"),
                (acoustic, b"acoustic"),
                (destination, b"repaired"),
                (archive, b"legacy"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            contract_data = {
                "schema_version": "mfa_alignment_contract.v1",
                "status": "passed",
                "recorded_at": "2026-08-05T00:00:00+09:00",
                "year": "2021",
                "lab_input_contract_id": "INPUT",
                "runtime": {
                    "python": "3.13.14",
                    "montreal_forced_aligner": "3.4.0",
                    "pynini": "2.1.7",
                },
                "models": {
                    role: {
                        "role": role,
                        "requested_name": role,
                        "path": str(root / f"{role}.model"),
                        "filename": f"{role}.model",
                        "bytes": index + 1,
                        "mtime_ns": 1,
                        "sha256": hashlib.sha256(role.encode()).hexdigest(),
                    }
                    for index, role in enumerate(
                        ("acoustic", "dictionary", "g2p")
                    )
                },
                "frozen_model_pin": {
                    "commit": "PIN",
                    "contract": {"sha256": "BUNDLE"},
                    "models": {
                        "dictionary": {"sha256": "BASE-DICTIONARY"}
                    },
                },
                "common_pron_adoption_contract": {"sha256": "ADOPTION"},
                "approved_exclusions_contract": {"sha256": "EXCLUSION"},
                "pronunciation_mode": "common_pronunciation",
            }
            canonical_identity = {
                "schema_version": "mfa_alignment_contract.v1",
                "year": "2021",
                "lab_input_contract_id": "INPUT",
                "runtime": contract_data["runtime"],
                "frozen_model_pin": {
                    "commit": "PIN",
                    "contract_sha256": "BUNDLE",
                    "base_dictionary_sha256": "BASE-DICTIONARY",
                },
                "pronunciation_mode": "common_pronunciation",
                "common_pron_adoption_sha256": "ADOPTION",
                "approved_exclusions_sha256": "EXCLUSION",
                "models": {
                    role: {
                        "requested_name": role,
                        "bytes": index + 1,
                        "sha256": hashlib.sha256(role.encode()).hexdigest(),
                    }
                    for index, role in enumerate(
                        ("acoustic", "dictionary", "g2p")
                    )
                },
            }
            alignment_id = hashlib.sha256(
                json.dumps(
                    canonical_identity,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            contract_data["alignment_contract_id"] = alignment_id
            contract.write_text(json.dumps(contract_data), encoding="utf-8")
            search.mkdir()
            reconciliation = {
                "status": "passed",
                "full_year_gate": True,
                "counts": {"source_search_ids": 3},
                "inventories": {"unknown": []},
            }
            failed_report = root / "failed.json"
            failed_payload = {
                "status": "failed",
                "year": "2021",
                "db_path": str(db),
                "search_master_root": str(search),
                "output_root": str(output),
                "alignment_contract_id": alignment_id,
                "input_contract_id": "INPUT",
                "alignment_contract": file_fingerprint(
                    contract, with_sha256=True
                ),
                "alignment_models": contract_data["models"],
                "acoustic_model": file_fingerprint(
                    acoustic, with_sha256=True
                ),
                "exact_id_reconciliation": reconciliation,
                "counts": {
                    "source_utterances": 3,
                    "created": 1,
                    "validated_existing": 1,
                    "failed": 1,
                    "approved_excluded": 0,
                    "alignment_missing": 0,
                    "search_row_missing": 0,
                    "word_span_fallback": 0,
                    "spn_intervals": 0,
                    "float32_boundary_adjustments": 2,
                    "utterances_float32_boundary_adjusted": 1,
                },
                "accounted": 3,
                "failed_examples": [{"utt_id": "U3", "error": "old"}],
                "float32_boundary_normalization": {
                    "max_adjustment_seconds": 0.000003,
                    "examples": [{"utt_id": "U3"}],
                },
            }
            failed_report.write_text(
                json.dumps(failed_payload), encoding="utf-8"
            )
            repair_manifest = root / "repair.json"
            repair_payload = {
                "status": "success",
                "year": "2021",
                "db_path": str(db),
                "output_root": str(output),
                "alignment_contract_id": alignment_id,
                "input_contract_id": "INPUT",
                "source_failed_report": file_fingerprint(
                    failed_report, with_sha256=True
                ),
                "repaired_count": 1,
                "repaired_ids": ["U3"],
                "records": [
                    {
                        "utt_id": "U3",
                        "destination": str(destination),
                        "destination_after": file_fingerprint(
                            destination, with_sha256=True
                        ),
                        "archive_path": str(archive),
                        "archive_fingerprint": file_fingerprint(
                            archive, with_sha256=True
                        ),
                        "matches_pre_normalization_policy": True,
                        "replacement_validation_passed": True,
                    }
                ],
            }
            repair_manifest.write_text(
                json.dumps(repair_payload), encoding="utf-8"
            )

            # A normal checkpoint reconstruction changes recorded_at only.
            # The file SHA differs, while its builder-derived identity stays.
            contract_data["recorded_at"] = "2026-08-05T01:00:00+09:00"
            contract.write_text(json.dumps(contract_data), encoding="utf-8")

            totals, examples, maximum, resume = load_targeted_repair_resume(
                failed_report_path=failed_report,
                repair_manifest_path=repair_manifest,
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
                alignment_contract_id=alignment_id,
                input_contract_id="INPUT",
                reconciliation=reconciliation,
                source_utterance_count=3,
            )
            self.assertEqual(totals["created"], 1)
            self.assertEqual(totals["validated_existing"], 2)
            self.assertEqual(totals["failed"], 0)
            self.assertEqual(totals["targeted_repaired_existing"], 1)
            self.assertEqual(totals["targeted_repaired_new"], 0)
            self.assertEqual(examples, [{"utt_id": "U3"}])
            self.assertEqual(maximum, 0.000003)
            self.assertEqual(resume["repaired_ids"], ["U3"])
            self.assertTrue(
                resume["alignment_contract_validation"][
                    "volatile_recorded_at_ignored"
                ]
            )

            creation_manifest = root / "creation_repair.json"
            creation_payload = {
                **repair_payload,
                "repair_mode": (
                    "create_missing_textgrid_after_label_normalization"
                ),
                "records": [
                    {
                        "utt_id": "U3",
                        "destination": str(destination),
                        "destination_after": file_fingerprint(
                            destination, with_sha256=True
                        ),
                        "destination_previously_absent": True,
                        "source_control_validation_passed": True,
                        "archive_path": "",
                        "archive_fingerprint": {},
                        "replacement_validation_passed": True,
                    }
                ],
            }
            creation_manifest.write_text(
                json.dumps(creation_payload), encoding="utf-8"
            )
            created_totals, _examples, _maximum, created_resume = (
                load_targeted_repair_resume(
                    failed_report_path=failed_report,
                    repair_manifest_path=creation_manifest,
                    db_path=db,
                    year="2021",
                    search_master_root=search,
                    output_root=output,
                    acoustic_model=acoustic,
                    alignment_contract=contract,
                    alignment_contract_id=alignment_id,
                    input_contract_id="INPUT",
                    reconciliation=reconciliation,
                    source_utterance_count=3,
                )
            )
            self.assertEqual(created_totals["created"], 2)
            self.assertEqual(created_totals["validated_existing"], 1)
            self.assertEqual(created_totals["targeted_repaired_new"], 1)
            self.assertEqual(created_totals["targeted_repaired_existing"], 0)
            self.assertEqual(
                created_resume["repair_mode"],
                "create_missing_textgrid_after_label_normalization",
            )

            contract_data["models"]["acoustic"]["requested_name"] = (
                "tampered"
            )
            contract.write_text(json.dumps(contract_data), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "alignment_contract_semantic_identity"
            ):
                load_targeted_repair_resume(
                    failed_report_path=failed_report,
                    repair_manifest_path=repair_manifest,
                    db_path=db,
                    year="2021",
                    search_master_root=search,
                    output_root=output,
                    acoustic_model=acoustic,
                    alignment_contract=contract,
                    alignment_contract_id=alignment_id,
                    input_contract_id="INPUT",
                    reconciliation=reconciliation,
                    source_utterance_count=3,
                )
            contract_data["models"]["acoustic"]["requested_name"] = (
                "acoustic"
            )
            contract.write_text(json.dumps(contract_data), encoding="utf-8")

            subsequent_archive = (
                root / "archive2" / "2021" / "S1" / "U3.TextGrid"
            )
            subsequent_archive.parent.mkdir(parents=True, exist_ok=True)
            subsequent_archive.write_bytes(destination.read_bytes())
            source_partial = root / "2021_utterances.csv.gz.partial"
            source_partial.write_bytes(b"complete closed gzip placeholder")
            destination.write_bytes(b"second repair")
            subsequent_manifest = root / "subsequent_repair.json"
            subsequent_payload = {
                "schema_version": (
                    "mfa_textgrid_phone_only_silence_word_repair.v1"
                ),
                "status": "success",
                "year": "2021",
                "db_path": str(db),
                "search_master_root": str(search),
                "output_root": str(output),
                "alignment_contract_id": alignment_id,
                "input_contract_id": "INPUT",
                "source_companion_utterance_partial": file_fingerprint(
                    source_partial, with_sha256=True
                ),
                "source_mismatch_count": 1,
                "candidate_count": 1,
                "repaired_count": 1,
                "repaired_ids": ["U3"],
                "records": [
                    {
                        "utt_id": "U3",
                        "destination": str(destination),
                        "destination_before": file_fingerprint(
                            subsequent_archive, with_sha256=True
                        ),
                        "destination_after": file_fingerprint(
                            destination, with_sha256=True
                        ),
                        "archive_path": str(subsequent_archive),
                        "archive_fingerprint": file_fingerprint(
                            subsequent_archive, with_sha256=True
                        ),
                        "old_policy_validation_passed": True,
                        "replacement_validation_passed": True,
                    }
                ],
            }
            subsequent_manifest.write_text(
                json.dumps(subsequent_payload), encoding="utf-8"
            )
            chained = load_targeted_repair_resume(
                failed_report_path=failed_report,
                repair_manifest_path=repair_manifest,
                subsequent_repair_manifest_path=subsequent_manifest,
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
                alignment_contract_id=alignment_id,
                input_contract_id="INPUT",
                reconciliation=reconciliation,
                source_utterance_count=3,
            )
            self.assertEqual(
                chained[3]["subsequent_repaired_ids"], ["U3"]
            )

            with self.assertRaisesRegex(
                RuntimeError, "invalid targeted repair evidence"
            ):
                load_targeted_repair_resume(
                    failed_report_path=failed_report,
                    repair_manifest_path=repair_manifest,
                    db_path=db,
                    year="2021",
                    search_master_root=search,
                    output_root=output,
                    acoustic_model=acoustic,
                    alignment_contract=contract,
                    alignment_contract_id=alignment_id,
                    input_contract_id="INPUT",
                    reconciliation=reconciliation,
                    source_utterance_count=3,
                )


if __name__ == "__main__":
    unittest.main()
