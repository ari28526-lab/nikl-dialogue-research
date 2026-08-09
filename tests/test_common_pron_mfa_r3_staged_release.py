from __future__ import annotations

import csv
import gzip
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.python.audit_common_pron_mfa_r3_staged_release import audit
from scripts.python.build_common_pron_mfa_r3_staged_release import (
    SOURCE_FIELDS,
    build,
    selected_row,
)
from scripts.python.pipeline_common import file_fingerprint


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class StagedReleaseTests(unittest.TestCase):
    def test_selected_row_is_explicit_promotion_not_adoption(self) -> None:
        source = {field: "x" for field in SOURCE_FIELDS}
        source.update(
            {
                "token": "가",
                "variant_index": "1",
                "variant_count": "1",
                "pron_phones_mfa": "k a",
                "pron_roman": "G A",
                "planning_status": "candidate_test",
                "candidate_only": "true",
                "final_selection": "false",
                "adopted": "false",
            }
        )
        promoted = selected_row(source)
        self.assertEqual(promoted["selected_pron_phones_mfa"], "k a")
        self.assertEqual(promoted["candidate_only"], "false")
        self.assertEqual(promoted["final_selection"], "true")
        self.assertEqual(promoted["adopted"], "false")

    def test_build_and_independent_audit_small_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            approval = root / "RESEARCHER_APPROVAL.json"
            write_json(
                approval,
                {
                    "status": "passed_explicit_researcher_approval",
                    "approval_contract_id": "approval-test",
                },
            )
            approval_fp = file_fingerprint(approval, with_sha256=True)
            provenance = root / "RESEARCHER_APPROVAL.provenance.v2.json"
            write_json(
                provenance,
                {
                    "schema_version": "common_pron_r3_researcher_approval_provenance.v2",
                    "status": "append_only_provenance",
                    "approval_contract_id": "approval-test",
                    "immutable_approval": {
                        "bytes": approval_fp["bytes"],
                        "sha256": approval_fp["sha256"],
                    },
                    "records": [{"sequence": 1}],
                },
            )
            contract = root / "contract.json"
            write_json(
                contract,
                {
                    "schema_version": "common_pronunciation_resource_contract.v3.1",
                    "status": "researcher_approved_staged_scope_pending_release_materialization_and_independent_audit",
                    "invariants": {"production_gate_opened_by_this_contract": False},
                    "researcher_approval": {
                        **approval_fp,
                        "approval_contract_id": "approval-test",
                    },
                    "canonical_type_table": {
                        "full_canonical_type_coverage_required": 4
                    },
                    "staged_selection_scope": {
                        "candidate_types_to_promote": 2,
                        "projected_dictionary_variant_rows": 3,
                        "pronunciation_safe_utterances": 5,
                        "followup_utterances": 2,
                        "not_selected_for_staged_release": {
                            "zero_fallback_hold_types": 1,
                            "explicit_policy_types": 1,
                        },
                    },
                },
            )
            routing = root / "routing.json"
            write_json(
                routing,
                {
                    "status": "success_read_only_routing_not_adopted",
                    "scope": {"safe_body_definition": "fixture"},
                    "counts": {"safe_utterances": 5, "blocked_utterances": 2},
                },
            )
            routing_audit = root / "routing_audit.json"
            write_json(
                routing_audit, {"status": "passed_independent_full_scan"}
            )
            acoustic = root / "acoustic.zip"
            with zipfile.ZipFile(acoustic, "w") as archive:
                archive.writestr(
                    "fixture/meta.json",
                    json.dumps({"phones": ["a", "b", "c"]}),
                )
            frozen_pin = root / "frozen_pin.json"
            write_json(frozen_pin, {"status": "passed"})
            candidate_projection = root / "candidate.csv.gz"
            candidate_rows = [
                ("가", 1, 2, "a b", "A B"),
                ("가", 2, 2, "a c", "A C"),
                ("나", 1, 1, "b a", "B A"),
            ]
            with gzip.open(
                candidate_projection,
                "wt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                writer = csv.DictWriter(
                    stream, fieldnames=SOURCE_FIELDS, lineterminator="\n"
                )
                writer.writeheader()
                for token, variant_index, variant_count, phones, roman in candidate_rows:
                    writer.writerow(
                        {
                            "token": token,
                            "variant_index": variant_index,
                            "variant_count": variant_count,
                            "pron_phones_mfa": phones,
                            "pron_roman": roman,
                            "planning_status": "candidate_fixture",
                            "planning_source": "fixture",
                            "planning_reason": "fixture",
                            "total_occurrences": 10 if token == "가" else 20,
                            **{f"count_{year}": 0 for year in range(2020, 2026)},
                            "candidate_only": "true",
                            "final_selection": "false",
                            "adopted": "false",
                        }
                    )
            candidate_dictionary = root / "candidate.dict"
            candidate_dictionary.write_text(
                "가\ta b\n가\ta c\n나\tb a\n", encoding="utf-8"
            )
            candidate_manifest = root / "candidate_manifest.json"
            write_json(
                candidate_manifest,
                {
                    "status": "passed_candidate_only_not_adopted",
                    "scope": {},
                    "inputs": {
                        "frozen_acoustic_model": file_fingerprint(
                            acoustic, with_sha256=True
                        )
                    },
                    "outputs": {
                        "candidate_projection": file_fingerprint(
                            candidate_projection, with_sha256=True
                        ),
                        "candidate_dictionary_not_adopted": file_fingerprint(
                            candidate_dictionary, with_sha256=True
                        ),
                    },
                    "counts": {
                        "candidate_types": 2,
                        "candidate_occurrences": 30,
                        "dictionary_rows": 3,
                    },
                    "model_contract": {
                        "phone_count": 3,
                        "phone_sorted_sha256": hashlib.sha256(
                            b"a\nb\nc\n"
                        ).hexdigest(),
                    },
                },
            )
            candidate_audit = root / "candidate_audit.json"
            write_json(
                candidate_audit,
                {
                    "status": "passed_full_projection_and_dictionary_equivalence",
                    "inputs": {
                        "candidate_manifest": file_fingerprint(
                            candidate_manifest, with_sha256=True
                        )
                    },
                },
            )
            gate = root / "gate.json"
            write_json(gate, {"status": "blocked_fixture", "allowed_release_ids": []})
            policy = root / "policy.json"
            release_id = "common_pron_mfa_r3_20990101"
            write_json(
                policy,
                {
                    "schema_version": "common_pron_mfa_r3_staged_release_policy.v1",
                    "status": "approved_to_materialize_pending_independent_audit_and_gate",
                    "release_id": release_id,
                    "expected": {
                        "selected_types": 2,
                        "selected_occurrences": 30,
                        "dictionary_rows": 3,
                        "safe_utterances": 5,
                        "followup_utterances": 2,
                    },
                },
            )
            output_root = root / release_id
            build_args = dict(
                contract_path=contract,
                approval_path=approval,
                approval_provenance_path=provenance,
                routing_manifest_path=routing,
                routing_audit_path=routing_audit,
                candidate_manifest_path=candidate_manifest,
                candidate_audit_path=candidate_audit,
                frozen_pin_path=frozen_pin,
                release_gate_path=gate,
                policy_path=policy,
                output_root=output_root,
            )
            manifest = build(**build_args)
            self.assertFalse(manifest["scope"]["adopted"])
            self.assertFalse(manifest["scope"]["allow_yearly_mfa"])
            self.assertEqual(
                manifest["outputs"]["mfa_dictionary"]["sha256"],
                file_fingerprint(candidate_dictionary, with_sha256=True)["sha256"],
            )
            report = audit(
                output_root / "RELEASE_MANIFEST.json", root / "audit.json"
            )
            self.assertEqual(
                report["status"],
                "passed_independent_staged_adoption_audit_pending_release_gate",
            )
            self.assertTrue(report["verdict"]["release_gate_remains_closed"])
            self.assertFalse(report["verdict"]["production_mfa_allowed"])
            self.assertEqual(
                build(**build_args)["pronunciation_contract_id"],
                manifest["pronunciation_contract_id"],
            )
            with (output_root / f"{release_id}.dict").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write("tamper\ta\n")
            with self.assertRaisesRegex(RuntimeError, "fingerprint mismatch"):
                build(**build_args)


if __name__ == "__main__":
    unittest.main()
