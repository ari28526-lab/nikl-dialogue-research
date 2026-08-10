from __future__ import annotations

import csv
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.audit_mfa_r3_year_input_contract import audit
from scripts.python.build_mfa_r3_year_input_contract import build
from scripts.python.pipeline_common import file_fingerprint


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_gzip_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class YearInputContractTests(unittest.TestCase):
    def fixture(self, root: Path) -> dict[str, Path]:
        year = "2020"
        search_root = root / "search"
        source = search_root / year / "session.csv"
        source_rows = [
            {"year": year, "utt_id": f"u{index}", "session_id": "S1"}
            for index in range(1, 6)
        ]
        write_csv(source, ("year", "utt_id", "session_id"), source_rows)
        search_meta = search_root / "_build_meta.json"
        write_json(search_meta, {"status": "success", "run_id": "test"})
        stat = source.stat()
        inventory_digest = hashlib.sha256(
            f"2020/session.csv\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8")
        ).hexdigest()
        inventory = {
            "root": str(search_root.resolve()),
            "file_count": 1,
            "total_bytes": stat.st_size,
            "path_size_mtime_sha256": inventory_digest,
        }

        blocked = root / "routing" / "blocked.csv.gz"
        blocked_fields = (
            "year",
            "utt_id",
            "source_csv",
            "pron_reference_status",
            "pron_reference_n_eojeol",
            "lab_n_eojeol",
            "routing_class",
            "hold_tokens_json",
            "policy_tokens_json",
            "unknown_tokens_json",
            "safe_body_included",
            "followup_required",
        )
        write_gzip_csv(
            blocked,
            blocked_fields,
            [
                {
                    "year": year,
                    "utt_id": "u2",
                    "source_csv": "2020/session.csv",
                    "pron_reference_status": "empty",
                    "pron_reference_n_eojeol": "0",
                    "lab_n_eojeol": "0",
                    "routing_class": "empty_reference",
                    "hold_tokens_json": "[]",
                    "policy_tokens_json": "[]",
                    "unknown_tokens_json": "[]",
                    "safe_body_included": "false",
                    "followup_required": "true",
                }
            ],
        )
        summary = root / "routing" / "year_summary.csv"
        write_csv(
            summary,
            (
                "year",
                "search_master_csv_files",
                "utterances",
                "safe_utterances",
                "blocked_utterances",
                "unknown_involved_utterances",
            ),
            [
                {
                    "year": year,
                    "search_master_csv_files": "1",
                    "utterances": "5",
                    "safe_utterances": "4",
                    "blocked_utterances": "1",
                    "unknown_involved_utterances": "0",
                }
            ],
        )
        routing_manifest = root / "routing" / "PRE_ADOPTION_ROUTING_MANIFEST.json"
        write_json(
            routing_manifest,
            {
                "schema_version": "common_pron_r3_pre_adoption_routing.v1",
                "status": "success_read_only_routing_not_adopted",
                "inputs": {
                    "search_master_build_meta": file_fingerprint(
                        search_meta, with_sha256=True
                    ),
                    "search_master_inventory": inventory,
                },
                "outputs": {
                    "blocked_utterance_routing": file_fingerprint(
                        blocked, with_sha256=True
                    ),
                    "year_routing_summary": file_fingerprint(
                        summary, with_sha256=True
                    ),
                },
            },
        )
        release_manifest = root / "release" / "RELEASE_MANIFEST.json"
        write_json(
            release_manifest,
            {
                "schema_version": "common_pron_mfa_r3_staged_release.v1",
                "status": "materialized_pending_independent_adoption_audit_and_release_gate",
                "release_id": "common_pron_mfa_r3_20260809",
                "pronunciation_contract_id": "pron-test",
                "scope": {"allow_yearly_mfa": False},
                "inputs": {
                    "stage19_routing_manifest": file_fingerprint(
                        routing_manifest, with_sha256=True
                    )
                },
            },
        )
        release_audit = root / "release_audit.json"
        write_json(
            release_audit,
            {
                "status": "passed_independent_staged_adoption_audit_pending_release_gate",
                "verdict": {
                    "production_mfa_allowed": False,
                    "release_gate_remains_closed": True,
                },
                "inputs": {
                    "release_manifest": file_fingerprint(
                        release_manifest, with_sha256=True
                    )
                },
            },
        )

        approval_fields = (
            "year",
            "input_contract_id",
            "utt_id",
            "reason_code",
            "exclusion_scope",
            "evidence_path",
            "decision",
            "notes",
        )
        base_rows = [
            {
                "year": year,
                "input_contract_id": "old",
                "utt_id": "u2",
                "reason_code": "empty_reference_unresolved_symbol",
                "exclusion_scope": "alignment_and_analysis",
                "evidence_path": "test",
                "decision": "approved",
                "notes": "",
            },
            {
                "year": year,
                "input_contract_id": "old",
                "utt_id": "u3",
                "reason_code": "audio_pairing_unresolved",
                "exclusion_scope": "alignment_and_analysis",
                "evidence_path": "test",
                "decision": "approved",
                "notes": "",
            },
        ]
        initial_csv = root / "initial.csv"
        write_csv(initial_csv, approval_fields, base_rows)
        initial = root / "initial.json"
        write_json(
            initial,
            {
                "schema_version": "mfa_approved_exclusions.v1",
                "status": "approved",
                "year": year,
                "review_csv": file_fingerprint(initial_csv, with_sha256=True),
                "row_count": 2,
                "counts": {
                    "empty_reference_unresolved_symbol|alignment_and_analysis": 1,
                    "audio_pairing_unresolved|alignment_and_analysis": 1,
                },
            },
        )
        combined_rows = base_rows + [
            {
                "year": year,
                "input_contract_id": "old",
                "utt_id": "u5",
                "reason_code": "audio_unusable",
                "exclusion_scope": "alignment_and_analysis",
                "evidence_path": "test",
                "decision": "approved",
                "notes": "",
            },
            {
                "year": year,
                "input_contract_id": "old",
                "utt_id": "u4",
                "reason_code": "mfa_alignment_missing",
                "exclusion_scope": "alignment_and_analysis",
                "evidence_path": "test",
                "decision": "approved",
                "notes": "",
            },
        ]
        combined_csv = root / "combined.csv"
        write_csv(combined_csv, approval_fields, combined_rows)
        combined = root / "combined.json"
        write_json(
            combined,
            {
                "schema_version": "mfa_approved_exclusions.v1",
                "status": "approved",
                "year": year,
                "review_csv": file_fingerprint(combined_csv, with_sha256=True),
                "row_count": 4,
                "counts": {
                    "empty_reference_unresolved_symbol|alignment_and_analysis": 1,
                    "audio_pairing_unresolved|alignment_and_analysis": 1,
                    "audio_unusable|alignment_and_analysis": 1,
                    "mfa_alignment_missing|alignment_and_analysis": 1,
                },
            },
        )

        wav_root = root / "recovered" / year / "S1"
        wav_root.mkdir(parents=True)
        for utt_id in ("u1", "u2", "u4", "u5"):
            (wav_root / f"{utt_id}.wav").write_bytes(b"RIFFtest")
        corpus = root / "corpus.json"
        write_json(
            corpus,
            {
                "schema_version": "wav_recovery_corpus.v1",
                "status": "passed",
                "corpus_contract_id": "corpus-test",
                "year": year,
                "source_wav_tree_untouched": True,
                "output_year": str((root / "recovered" / year).resolve()),
                "wav_files": 4,
                "omitted_for_review": 1,
            },
        )
        policy = root / "policy.json"
        write_json(
            policy,
            {
                "schema_version": "mfa_r3_year_input_contract_policy.v1",
                "status": "approved_contract_building_only_gate_closed",
                "release_id": "common_pron_mfa_r3_20260809",
                "scope": {
                    "years_enabled": [year],
                    "production_mfa_allowed": False,
                    "textgrid_materialization_allowed": False,
                },
                "reason_policy": {
                    "pre_mfa_technical_exclusions": [
                        "audio_pairing_unresolved",
                        "empty_reference_unresolved_symbol",
                        "text_duration_impossible",
                        "audio_unusable",
                    ],
                    "r2_post_mfa_failures_must_not_be_pre_exclusions": [
                        "mfa_alignment_missing",
                        "mfa_feature_generation_failed",
                    ],
                },
                "years": {
                    year: {
                        "expected_source_utterances": 5,
                        "expected_pronunciation_safe": 4,
                        "expected_pronunciation_followup": 1,
                        "expected_unknown": 0,
                        "expected_recovered_wav_files": 4,
                        "expected_recovered_omitted": 1,
                        "expected_approved_pre_mfa_reason_counts": {
                            "audio_pairing_unresolved": 1,
                            "empty_reference_unresolved_symbol": 1,
                            "audio_unusable": 1,
                        },
                        "expected_r2_post_mfa_reason_counts": {
                            "mfa_alignment_missing": 1
                        },
                        "recovered_corpus_contract_id": "corpus-test",
                    }
                },
            },
        )
        return {
            "release_manifest": release_manifest,
            "release_audit": release_audit,
            "initial": initial,
            "combined": combined,
            "corpus": corpus,
            "policy": policy,
            "output": root / "release" / "03_year_input_contracts" / year,
        }

    def run_build(self, paths: dict[str, Path]) -> dict:
        return build(
            year="2020",
            release_manifest_path=paths["release_manifest"],
            release_audit_path=paths["release_audit"],
            policy_path=paths["policy"],
            initial_approval_path=paths["initial"],
            combined_approval_path=paths["combined"],
            corpus_contract_path=paths["corpus"],
            output_root=paths["output"],
        )

    def test_exact_id_partition_and_post_mfa_reentry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            manifest = self.run_build(paths)
            self.assertEqual(manifest["accounting"]["pronunciation_safe"], 4)
            self.assertEqual(manifest["accounting"]["pre_mfa_exclusions_applied_to_pron_safe"], 2)
            self.assertEqual(manifest["accounting"]["expected_mfa_input"], 2)
            self.assertEqual(manifest["accounting"]["r2_post_mfa_reentered"], 1)
            reentry = Path(manifest["outputs"]["r2_post_mfa_reentry_ids"]["path"])
            with gzip.open(reentry, "rt", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["utt_id"] for row in rows], ["u4"])

    def test_independent_audit_passes_and_gate_stays_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            self.run_build(paths)
            contract = paths["output"] / "YEAR_INPUT_CONTRACT_2020.json"
            report = audit(contract, Path(temp) / "audit.json")
            self.assertTrue(report["verdict"]["exact_id_partition_passed"])
            self.assertFalse(report["verdict"]["production_mfa_allowed"])
            self.assertTrue(report["verdict"]["release_gate_remains_closed"])

    def test_existing_contract_is_idempotent_but_tamper_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            first = self.run_build(paths)
            second = self.run_build(paths)
            self.assertEqual(
                first["year_input_contract_id"], second["year_input_contract_id"]
            )
            expected = Path(first["outputs"]["expected_mfa_input_ids"]["path"])
            expected.write_bytes(expected.read_bytes() + b"tamper")
            with self.assertRaisesRegex(RuntimeError, "fingerprint mismatch"):
                self.run_build(paths)

    def test_source_snapshot_allows_non_search_wavs_but_not_missing_mfa_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            corpus = json.loads(paths["corpus"].read_text(encoding="utf-8"))
            wav_root = Path(corpus["output_year"])
            (wav_root / "S1" / "outside-search.wav").write_bytes(b"RIFFextra")
            corpus.update(
                {
                    "schema_version": "mfa_wav_source_snapshot.v1",
                    "corpus_contract_id": "source-snapshot-test",
                    "wav_files": 5,
                }
            )
            corpus.pop("omitted_for_review", None)
            write_json(paths["corpus"], corpus)
            policy = json.loads(paths["policy"].read_text(encoding="utf-8"))
            year_policy = policy["years"]["2020"]
            year_policy.update(
                {
                    "corpus_contract_schema": "mfa_wav_source_snapshot.v1",
                    "corpus_contract_id": "source-snapshot-test",
                    "expected_corpus_wav_files": 5,
                }
            )
            write_json(paths["policy"], policy)
            manifest = self.run_build(paths)
            self.assertEqual(manifest["accounting"]["source_wav_missing"], 1)
            self.assertEqual(manifest["accounting"]["corpus_extra_wav_ids"], 1)
            report = audit(
                paths["output"] / "YEAR_INPUT_CONTRACT_2020.json",
                Path(temp) / "source_snapshot_audit.json",
            )
            self.assertTrue(report["verdict"]["wav_source_snapshot_binding_passed"])


if __name__ == "__main__":
    unittest.main()
