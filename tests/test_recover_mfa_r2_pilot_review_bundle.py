import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from package_mfa_r2_pilot_review import ALL_YEARS  # noqa: E402
from pipeline_common import file_fingerprint, sha256_file  # noqa: E402
from recover_mfa_r2_pilot_review_bundle import (  # noqa: E402
    recover_bundle,
)


class RecoverMfaR2PilotReviewBundleTests(unittest.TestCase):
    def test_verifies_normalizes_and_promotes_complete_v1_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            output = parent / "MFA_R2_INFRA_PILOT_TEST"
            partial = parent / ".MFA_R2_INFRA_PILOT_TEST.123.partial"
            sources = parent / "sources"
            evidence_root = parent / "evidence"
            partial.mkdir()
            sources.mkdir()
            evidence_root.mkdir()

            payload_records = []
            review_rows = []
            selection_rows = []
            roles = (
                ("wav", ".wav"),
                ("lab", ".lab"),
                ("TextGrid", ".TextGrid"),
                ("selected_search_row_csv", ".csv"),
            )
            order = 0
            for year in ALL_YEARS:
                for offset in range(10):
                    order += 1
                    utt_id = f"SDRW{year}TEST.{offset}"
                    prefix = f"{year}__{utt_id}"
                    for role, suffix in roles:
                        source = sources / f"{prefix}.{role}.source"
                        source.write_bytes(
                            f"{year}|{offset}|{role}".encode()
                        )
                        destination = partial / f"{prefix}{suffix}"
                        destination.write_bytes(source.read_bytes())
                        record = file_fingerprint(
                            destination, with_sha256=True
                        )
                        record.update(
                            {
                                "role": role,
                                "source_path": str(source),
                                "source_sha256": sha256_file(source),
                            }
                        )
                        payload_records.append(record)
                    row = {
                        "review_order": str(order),
                        "year": year,
                        "utt_id": utt_id,
                    }
                    review_rows.append(row)
                    selection_rows.append(
                        {"year": year, "utt_id": utt_id}
                    )

            def write_rows(
                path: Path,
                fields: list[str],
                rows: list[dict[str, str]],
            ) -> None:
                with path.open(
                    "w", encoding="utf-8-sig", newline=""
                ) as stream:
                    writer = csv.DictWriter(
                        stream, fieldnames=fields
                    )
                    writer.writeheader()
                    writer.writerows(rows)

            write_rows(
                partial / "REVIEW.csv",
                ["review_order", "year", "utt_id"],
                review_rows,
            )
            write_rows(
                partial / "MANIFEST.csv",
                ["year", "utt_id"],
                selection_rows,
            )
            (partial / "README.md").write_text(
                "test bundle", encoding="utf-8"
            )
            supporting = {
                name: file_fingerprint(
                    partial / name, with_sha256=True
                )
                for name in ("REVIEW.csv", "MANIFEST.csv", "README.md")
            }

            markers = {}
            contracts = {}
            for year in ALL_YEARS:
                marker = evidence_root / f"{year}.machine_done.json"
                marker.write_text(year, encoding="utf-8")
                sample = evidence_root / f"{year}.sample.json"
                sample.write_text(f"sample-{year}", encoding="utf-8")
                database = evidence_root / f"{year}.db"
                database.write_bytes(b"sqlite")
                markers[year] = file_fingerprint(
                    marker, with_sha256=True
                )
                contracts[year] = {
                    "database": str(database),
                    "db_textgrid_sample_report": file_fingerprint(
                        sample, with_sha256=True
                    ),
                }
            cross = evidence_root / "cross.json"
            cross.write_text("cross", encoding="utf-8")
            bundle = {
                "schema_version": "mfa_r2_flat_review_bundle.v1",
                "status": "success",
                "flat_layout": True,
                "utterances": 60,
                "files_per_utterance": 4,
                "review_scope": "infrastructure_acceptance_only",
                "realization_judgment_performed": False,
                "machine_gate_evidence": {
                    "years": list(ALL_YEARS),
                    "machine_markers": markers,
                    "year_contracts": contracts,
                    "cross_year_method_audit": file_fingerprint(
                        cross, with_sha256=True
                    ),
                },
                "supporting_files": supporting,
                "files": payload_records,
            }
            (partial / "BUNDLE_MANIFEST.json").write_text(
                json.dumps(bundle), encoding="utf-8"
            )

            report_path = parent / "recovery.json"
            report = recover_bundle(
                partial_root=partial,
                output_root=output,
                report_path=report_path,
                timeout_seconds=2,
            )

            self.assertEqual(report["status"], "success")
            self.assertTrue(output.is_dir())
            self.assertFalse(partial.exists())
            recovered = json.loads(
                (output / "BUNDLE_MANIFEST.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                recovered["schema_version"],
                "mfa_r2_flat_review_bundle.v2",
            )
            self.assertTrue(
                recovered["recovery"][
                    "destination_paths_normalized_to_relative"
                ]
            )
            for record in recovered["files"]:
                self.assertIn("relative_path", record)
                self.assertNotIn("path", record)
            self.assertTrue(report_path.is_file())


if __name__ == "__main__":
    unittest.main()
