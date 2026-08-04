import json
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
                (contract, b"contract"),
                (destination, b"repaired"),
                (archive, b"legacy"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
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
                "alignment_contract_id": "ALIGN",
                "input_contract_id": "INPUT",
                "alignment_contract": file_fingerprint(
                    contract, with_sha256=True
                ),
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
                "alignment_contract_id": "ALIGN",
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

            totals, examples, maximum, resume = load_targeted_repair_resume(
                failed_report_path=failed_report,
                repair_manifest_path=repair_manifest,
                db_path=db,
                year="2021",
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
                alignment_contract_id="ALIGN",
                input_contract_id="INPUT",
                reconciliation=reconciliation,
                source_utterance_count=3,
            )
            self.assertEqual(totals["created"], 1)
            self.assertEqual(totals["validated_existing"], 2)
            self.assertEqual(totals["failed"], 0)
            self.assertEqual(totals["targeted_repaired_existing"], 1)
            self.assertEqual(examples, [{"utt_id": "U3"}])
            self.assertEqual(maximum, 0.000003)
            self.assertEqual(resume["repaired_ids"], ["U3"])

            destination.write_bytes(b"tampered")
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
                    alignment_contract_id="ALIGN",
                    input_contract_id="INPUT",
                    reconciliation=reconciliation,
                    source_utterance_count=3,
                )


if __name__ == "__main__":
    unittest.main()
