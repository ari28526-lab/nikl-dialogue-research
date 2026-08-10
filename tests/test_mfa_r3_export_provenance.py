import csv
import gzip
import io
import json
import sqlite3
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts" / "python"))

from audit_mfa_research_6tier_year import audit_year  # noqa: E402
from build_mfa_r3_alignment_contract import (  # noqa: E402
    recompute_alignment_contract_id,
)
from export_mfa_db_research_6tier import (  # noqa: E402
    R3_REQUIRED_MANIFEST_FIELDS,
    export_database,
)
from mfa_exclusion_contract import REVIEW_FIELDS, build_contract  # noqa: E402
from pipeline_common import file_fingerprint, sha256_file  # noqa: E402
from research_textgrid_v2 import write_textgrid_exact  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402
from verify_mfa_db_research_6tier_sample import verify_sample  # noqa: E402
from tests.test_export_mfa_db_research_6tier import (  # noqa: E402
    ExportMfaDbResearch6TierTests as ExportFixture,
)


class MfaR3ExportProvenanceTests(unittest.TestCase):
    year = "2021"
    input_contract_id = "YEAR_INPUT_R3_FIXTURE"

    def make_r3_contract(
        self, root: Path, *, db: Path, acoustic: Path
    ) -> Path:
        dictionary = root / "common_r3.dict"
        dictionary.write_text("가\tk\n", encoding="utf-8")
        g2p = root / "jamo_g2p.zip"
        g2p.write_bytes(b"fixture-g2p")
        expected_ids = root / "expected_mfa_input_ids.csv.gz"
        with expected_ids.open("wb") as raw:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=0
            ) as compressed:
                with io.TextIOWrapper(
                    compressed, encoding="utf-8-sig", newline=""
                ) as text:
                    writer = csv.DictWriter(
                        text, fieldnames=["year", "utt_id"], lineterminator="\n"
                    )
                    writer.writeheader()
                    writer.writerow({"year": self.year, "utt_id": "S1.1"})
        expected_record = file_fingerprint(expected_ids, with_sha256=True)
        models = {
            "dictionary": file_fingerprint(dictionary, with_sha256=True),
            "acoustic": file_fingerprint(acoustic, with_sha256=True),
            "g2p_provenance": file_fingerprint(g2p, with_sha256=True),
        }
        identity = {
            "pronunciation_release_id": "common_pron_mfa_r3_fixture",
            "pronunciation_contract_id": "1" * 64,
            "pronunciation_release_manifest_sha256": "2" * 64,
            "staged_adoption_contract_sha256": "3" * 64,
            "staged_adoption_audit_sha256": "4" * 64,
            "researcher_approval_sha256": "5" * 64,
            "safe_body_routing_contract_id": "6" * 64,
            "year_input_contract_id": self.input_contract_id,
            "year_input_contract_sha256": "7" * 64,
            "expected_mfa_input_sha256": expected_record["sha256"],
            "followup_inventory_sha256": "9" * 64,
            "corpus_contract_id": "a" * 64,
            "frozen_model_pin_sha256": "b" * 64,
            "mfa_dictionary_sha256": sha256_file(dictionary),
            "acoustic_model_sha256": sha256_file(acoustic),
            "g2p_model_sha256": sha256_file(g2p),
            "runtime": {
                "python": "3.13.fixture",
                "montreal_forced_aligner": "3.4.fixture",
                "pynini": "2.1.fixture",
            },
        }
        research_root = root / "05_research_database" / self.year
        research_root.mkdir(parents=True)
        research_inputs = {}
        for name in (
            "type_catalog_audit",
            "year_database_manifest",
            "year_input_contract",
            "utterance_scope",
            "occurrences",
        ):
            path = research_root / f"{name}.dat"
            path.write_bytes(name.encode("utf-8"))
            research_inputs[name] = file_fingerprint(path, with_sha256=True)
        research_audit = research_root / f"AUDIT_RESEARCH_DATABASE_{self.year}.json"
        research_audit.write_text(
            json.dumps(
                {
                    "schema_version": "mfa_r3_pronunciation_occurrence_year_audit.v1",
                    "status": "passed",
                    "year": self.year,
                    "release_id": identity["pronunciation_release_id"],
                    "pronunciation_contract_id": identity["pronunciation_contract_id"],
                    "post_mfa_join_key": ["year", "utt_id", "reference_eojeol_idx"],
                    "verdict": {"ready_for_mfa_preflight": True},
                    "inputs": research_inputs,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        contract = {
            "schema_version": "mfa_r3_alignment_contract.v1",
            "status": "materialized_pending_runner_preflight_and_release_gate",
            "year": self.year,
            "pronunciation_mode": "latest_jamo_common_dictionary_required",
            "alignment_origin": "fresh_r3_full_realign",
            "r3_full_realign": True,
            "identity": identity,
            "alignment_contract_id": "",
            "scope": {
                "production_mfa_allowed": False,
                "textgrid_materialization_allowed": False,
                "legacy_marker_reuse_allowed": False,
                "legacy_db_reuse_allowed": False,
            },
            "models": models,
            "year_input": {
                "expected_mfa_input": 1,
                "expected_mfa_input_ids": expected_record,
            },
            "fixture_source_db_sha256": sha256_file(db),
        }
        contract["alignment_contract_id"] = recompute_alignment_contract_id(
            contract
        )
        path = root / "alignment_r3.json"
        path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def make_empty_exclusions(self, root: Path) -> Path:
        review = root / "approved_exclusions.csv"
        with review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
        output = root / "approved_exclusions.json"
        build_contract(
            review_csv=review,
            output=output,
            year=self.year,
            input_contract_id=self.input_contract_id,
            approved_by="fixture-researcher",
            approved_at="2026-08-09T00:00:00+09:00",
        )
        return output

    def make_missing_exclusion(self, root: Path) -> Path:
        review = root / "approved_missing.csv"
        with review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "year": self.year,
                    "input_contract_id": self.input_contract_id,
                    "utt_id": "S1.1",
                    "reason_code": "mfa_alignment_missing",
                    "exclusion_scope": "alignment_and_analysis",
                    "evidence_path": "fixture-db",
                    "decision": "approved",
                    "notes": "fixture exact-ID technical failure",
                }
            )
        output = root / "approved_missing.json"
        build_contract(
            review_csv=review,
            output=output,
            year=self.year,
            input_contract_id=self.input_contract_id,
            approved_by="fixture-researcher",
            approved_at="2026-08-09T00:00:00+09:00",
        )
        return output

    def make_alignment_marker(
        self, root: Path, *, db: Path, alignment: Path
    ) -> Path:
        contract = json.loads(alignment.read_text(encoding="utf-8"))
        marker = root / "ALIGN_DONE_2021.json"
        marker.write_text(
            json.dumps(
                {
                    "schema_version": "mfa_r3_alignment_done.v1",
                    "status": "passed",
                    "year": self.year,
                    "alignment_contract_id": contract["alignment_contract_id"],
                    "source_db": file_fingerprint(db, with_sha256=True),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return marker

    def build_fixture(self, root: Path) -> dict[str, Path | dict]:
        fixture = ExportFixture()
        db = root / "2021.db"
        acoustic = root / "acoustic.zip"
        search = root / "search"
        labs = root / "labs"
        output = root / "output"
        fixture.make_db(db)
        fixture.make_acoustic(acoustic)
        fixture.make_search(search)
        lab = labs / self.year / "S1" / "S1.1.lab"
        lab.parent.mkdir(parents=True)
        lab.write_text("가", encoding="utf-8")
        with wave.open(str(lab.with_suffix(".wav")), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\x00\x00" * 16000)
        alignment = self.make_r3_contract(root, db=db, acoustic=acoustic)
        exclusions = self.make_empty_exclusions(root)
        exported = export_database(
            db_path=db,
            year=self.year,
            search_master_root=search,
            output_root=output,
            acoustic_model=acoustic,
            alignment_contract=alignment,
            approved_exclusions_contract=exclusions,
            lab_root=labs,
        )
        self.assertEqual(exported["status"], "success", exported)
        return {
            "db": db,
            "acoustic": acoustic,
            "search": search,
            "labs": labs,
            "output": output,
            "alignment": alignment,
            "exclusions": exclusions,
            "exported": exported,
        }

    def audit(self, root: Path, fixture: dict[str, Path | dict], name: str) -> dict:
        alignment = Path(fixture["alignment"])
        contract = json.loads(alignment.read_text(encoding="utf-8"))
        return audit_year(
            year=self.year,
            lab_root=Path(fixture["labs"]),
            textgrid_root=Path(fixture["output"]),
            acoustic_model=Path(fixture["acoustic"]),
            approved_exclusions_contract=Path(fixture["exclusions"]),
            input_contract_id=self.input_contract_id,
            alignment_contract_id=contract["alignment_contract_id"],
            alignment_contract=alignment,
            source_db=Path(fixture["db"]),
            report_path=root / f"audit_{name}.json",
            missing_csv_path=root / f"missing_{name}.csv",
        )

    def test_r3_export_pins_ten_fields_and_audit_recomputes_phonemes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = self.build_fixture(root)
            exported = fixture["exported"]
            manifest_path = (
                Path(fixture["output"])
                / self.year
                / "_tables"
                / "TABLES_MANIFEST.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for field in R3_REQUIRED_MANIFEST_FIELDS:
                self.assertIn(field, exported)
                self.assertEqual(manifest[field], exported[field])
            self.assertEqual(exported["source_db_sha256"], sha256_file(Path(fixture["db"])))
            report = self.audit(root, fixture, "clean")
            self.assertEqual(report["status"], "success", report)
            self.assertTrue(
                all(value == 0 for value in report["hard_failure_counts"].values())
            )
            sample = verify_sample(
                db_path=Path(fixture["db"]),
                year=self.year,
                search_master_root=Path(fixture["search"]),
                final_root=Path(fixture["output"]),
                scratch_root=root / "r3_sample_scratch",
                acoustic_model=Path(fixture["acoustic"]),
                alignment_contract=Path(fixture["alignment"]),
                approved_exclusions_contract=Path(fixture["exclusions"]),
                report_path=root / "r3_sample.json",
                sample_csv_path=root / "r3_sample.csv",
                sample_size=1,
            )
            self.assertEqual(sample["status"], "success", sample)
            self.assertEqual(sample["input_contract_id"], self.input_contract_id)

            textgrid = (
                Path(fixture["output"])
                / self.year
                / "S1"
                / "S1.1.TextGrid"
            )
            duration, tiers = parse_mfa_textgrid(textgrid)
            phonemes = [
                (begin, end, "WRONG" if str(label).strip() == "G" else label)
                for begin, end, label in tiers["phoneme_r_auto"]
            ]
            tier_data = [
                (name, phonemes if name == "phoneme_r_auto" else intervals)
                for name, intervals in tiers.items()
            ]
            write_textgrid_exact(
                textgrid, duration=float(duration), tier_data=tier_data
            )
            tampered = self.audit(root, fixture, "phoneme_tamper")
            self.assertEqual(tampered["status"], "failed")
            self.assertEqual(tampered["hard_failure_counts"]["invalid_textgrids"], 1)
            self.assertEqual(tampered["reason_counts"]["phoneme_label"], 1)

    def test_r3_manifest_provenance_tamper_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = self.build_fixture(root)
            manifest_path = (
                Path(fixture["output"])
                / self.year
                / "_tables"
                / "TABLES_MANIFEST.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["pronunciation_release_id"] = "wrong-release"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = self.audit(root, fixture, "manifest_tamper")
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["hard_failure_counts"]["table_manifest_error"], 1)
            self.assertIn("provenance mismatch", report["table_manifest_error"])

    def test_companion_row_contract_tamper_is_blocked_after_sha_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = self.build_fixture(root)
            table_root = Path(fixture["output"]) / self.year / "_tables"
            table = table_root / "utterance_alignment.csv.gz"
            with gzip.open(
                table, "rt", encoding="utf-8-sig", newline=""
            ) as stream:
                reader = csv.DictReader(stream)
                fields = list(reader.fieldnames or ())
                rows = list(reader)
            rows[0]["alignment_contract_id"] = "WRONG_ALIGNMENT"
            with table.open("wb") as raw:
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=raw, mtime=0
                ) as compressed:
                    with io.TextIOWrapper(
                        compressed, encoding="utf-8-sig", newline=""
                    ) as text:
                        writer = csv.DictWriter(
                            text, fieldnames=fields, lineterminator="\n"
                        )
                        writer.writeheader()
                        writer.writerows(rows)
            manifest_path = table_root / "TABLES_MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["tables"]["utterances"].update(
                {"bytes": table.stat().st_size, "sha256": sha256_file(table)}
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = self.audit(root, fixture, "row_contract_tamper")
            self.assertEqual(report["status"], "failed")
            self.assertEqual(
                report["hard_failure_counts"]
                ["utterance_table_contract_id_mismatch"],
                1,
            )

    def test_r3_preflight_requires_exact_post_mfa_approval_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = ExportFixture()
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            search = root / "search"
            labs = root / "labs"
            output = root / "output"
            fixture.make_db(db)
            connection = sqlite3.connect(db)
            connection.execute("DELETE FROM word_interval")
            connection.execute("DELETE FROM phone_interval")
            connection.commit()
            connection.close()
            fixture.make_acoustic(acoustic)
            fixture.make_search(search)
            lab = labs / self.year / "S1" / "S1.1.lab"
            lab.parent.mkdir(parents=True)
            lab.write_text("가", encoding="utf-8")
            alignment = self.make_r3_contract(root, db=db, acoustic=acoustic)

            blocked = export_database(
                db_path=db,
                year=self.year,
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=alignment,
                lab_root=labs,
                preflight_only=True,
            )
            self.assertEqual(blocked["status"], "failed")
            self.assertEqual(
                blocked["exact_id_reconciliation"]["counts"]
                ["unaligned_ids_without_approval"],
                1,
            )
            self.assertFalse(output.exists())

            exclusions = self.make_missing_exclusion(root)
            passed = export_database(
                db_path=db,
                year=self.year,
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=alignment,
                approved_exclusions_contract=exclusions,
                lab_root=labs,
                preflight_only=True,
            )
            self.assertEqual(passed["status"], "preflight_passed", passed)
            self.assertFalse(passed["materialization_started"])
            self.assertEqual(passed["counts"]["post_mfa_unaligned_ids"], 1)
            self.assertEqual(
                passed["counts"]["approved_alignment_exclusions"], 1
            )
            self.assertFalse(output.exists())

    def test_r3_preflight_binds_completed_alignment_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = ExportFixture()
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            search = root / "search"
            labs = root / "labs"
            output = root / "output"
            fixture.make_db(db)
            fixture.make_acoustic(acoustic)
            fixture.make_search(search)
            lab = labs / self.year / "S1" / "S1.1.lab"
            lab.parent.mkdir(parents=True)
            lab.write_text("가", encoding="utf-8")
            alignment = self.make_r3_contract(root, db=db, acoustic=acoustic)
            marker = self.make_alignment_marker(
                root, db=db, alignment=alignment
            )
            exclusions = self.make_empty_exclusions(root)
            passed = export_database(
                db_path=db,
                year=self.year,
                search_master_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=alignment,
                alignment_marker=marker,
                approved_exclusions_contract=exclusions,
                lab_root=labs,
                preflight_only=True,
            )
            self.assertEqual(passed["status"], "preflight_passed", passed)
            self.assertEqual(
                passed["alignment_done_marker"]["sha256"],
                sha256_file(marker),
            )

            marker_data = json.loads(marker.read_text(encoding="utf-8"))
            marker_data["source_db"]["sha256"] = "0" * 64
            marker.write_text(json.dumps(marker_data), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "marker/source DB"):
                export_database(
                    db_path=db,
                    year=self.year,
                    search_master_root=search,
                    output_root=output,
                    acoustic_model=acoustic,
                    alignment_contract=alignment,
                    alignment_marker=marker,
                    approved_exclusions_contract=exclusions,
                    lab_root=labs,
                    preflight_only=True,
                )

if __name__ == "__main__":
    unittest.main()
