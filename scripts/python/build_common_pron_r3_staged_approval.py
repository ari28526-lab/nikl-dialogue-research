"""Materialize the explicit r3 targeted-review and staged-scope approval."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_researcher_approval.v1"
PROVENANCE_SCHEMA_VERSION = "common_pron_r3_researcher_approval_provenance.v2"
EXPECTED_REVIEW = {
    "08": ("SDRW2200000232.1.1.84", "있지"),
    "09": ("SDRW2200001945.1.1.10", "놨던"),
    "15": ("SDRW2200001283.1.1.87", "슬프겠지만"),
    "24": ("SDRW2200001947.1.1.192", "없는"),
}
REVIEW_FIELDS = (
    "review_id",
    "utt_id",
    "target_word",
    "automatic_verdict",
    "decision",
    "notes",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_approved_reviews(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise RuntimeError("targeted review CSV field contract mismatch")
        rows = [
            {field: str(row.get(field, "")).strip() for field in REVIEW_FIELDS}
            for row in reader
        ]
    if len(rows) != len(EXPECTED_REVIEW):
        raise RuntimeError("targeted review row count differs")
    observed: set[str] = set()
    for row in rows:
        review_id = row["review_id"]
        if review_id in observed or review_id not in EXPECTED_REVIEW:
            raise RuntimeError("targeted review ID invalid or duplicated")
        observed.add(review_id)
        if (row["utt_id"], row["target_word"]) != EXPECTED_REVIEW[review_id]:
            raise RuntimeError("targeted review identity differs")
        if row["automatic_verdict"] != "pass":
            raise RuntimeError("targeted automatic verdict is not pass")
        if row["decision"] != "approved":
            raise RuntimeError("targeted review is not explicitly approved")
    if observed != set(EXPECTED_REVIEW):
        raise RuntimeError("targeted review ID coverage differs")
    return rows


def stable_contract_id(identity: dict) -> str:
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def provenance_content_identity(input_records: dict[str, dict]) -> dict:
    """Return the content-only identity used to deduplicate provenance records."""
    return {
        key: {
            "bytes": int(value["bytes"]),
            "sha256": str(value["sha256"]),
        }
        for key, value in sorted(input_records.items())
    }


def record_approval_provenance(
    *,
    approval_contract_id: str,
    approval_fingerprint: dict,
    input_records: dict[str, dict],
    sidecar: Path,
) -> tuple[dict, bool]:
    """Append one content-distinct provenance observation to a v2 sidecar.

    The researcher approval itself is immutable.  This sidecar may only gain a
    new record; existing records are validated and preserved byte-for-byte at
    the logical JSON-object level.
    """
    content_identity = provenance_content_identity(input_records)
    approval_content_identity = {
        "bytes": int(approval_fingerprint["bytes"]),
        "sha256": str(approval_fingerprint["sha256"]),
    }
    record_id = stable_contract_id(
        {
            "approval_contract_id": approval_contract_id,
            "content_fingerprints": content_identity,
        }
    )
    new_record = {
        "sequence": 1,
        "observed_at": now_iso(),
        "provenance_record_id": record_id,
        "content_fingerprints": content_identity,
        "inputs": input_records,
    }
    if sidecar.is_file():
        payload = load_json(sidecar)
        if (
            payload.get("schema_version") != PROVENANCE_SCHEMA_VERSION
            or payload.get("status") != "append_only_provenance"
            or payload.get("approval_contract_id") != approval_contract_id
            or payload.get("immutable_approval") != approval_content_identity
            or not isinstance(payload.get("records"), list)
        ):
            raise RuntimeError("existing approval provenance sidecar differs")
        records = payload["records"]
        seen: set[str] = set()
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict) or record.get("sequence") != index:
                raise RuntimeError("approval provenance sequence differs")
            existing_id = str(record.get("provenance_record_id", ""))
            expected_id = stable_contract_id(
                {
                    "approval_contract_id": approval_contract_id,
                    "content_fingerprints": record.get("content_fingerprints"),
                }
            )
            if not existing_id or existing_id != expected_id or existing_id in seen:
                raise RuntimeError("approval provenance record identity differs")
            seen.add(existing_id)
        if record_id in seen:
            return payload, False
        new_record["sequence"] = len(records) + 1
        payload["records"] = [*records, new_record]
    else:
        payload = {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "status": "append_only_provenance",
            "approval_contract_id": approval_contract_id,
            "immutable_approval": approval_content_identity,
            "records": [new_record],
        }
    atomic_write_json(sidecar, payload)
    return payload, True


def build_approval(
    *,
    review_csv: Path,
    targeted_audit_path: Path,
    routing_audit_path: Path,
    candidate_audit_path: Path,
    workflow_policy_path: Path,
    output: Path,
) -> tuple[dict, bool]:
    paths = [
        review_csv,
        targeted_audit_path,
        routing_audit_path,
        candidate_audit_path,
        workflow_policy_path,
    ]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    rows = read_approved_reviews(review_csv)
    targeted = load_json(targeted_audit_path)
    routing = load_json(routing_audit_path)
    candidate = load_json(candidate_audit_path)
    workflow = load_json(workflow_policy_path)

    if (
        targeted.get("status")
        != "passed_automatic_checks_pending_researcher_audio_review"
        or int(targeted.get("checks", {}).get("automatic_pass", -1)) != 4
        or int(targeted.get("checks", {}).get("spn_total", -1)) != 0
    ):
        raise RuntimeError("targeted regression automatic audit differs")
    if routing.get("status") != "passed_independent_full_scan":
        raise RuntimeError("routing independent audit is not passed")
    if (
        candidate.get("status")
        != "passed_full_projection_and_dictionary_equivalence"
    ):
        raise RuntimeError("candidate independent audit is not passed")
    decision = workflow.get("researcher_decision", {})
    scope = workflow.get("scope", {})
    if (
        workflow.get("schema_version") != "mfa_r3_full_realign_workflow.v1"
        or decision.get("approved_by") != "ari30"
        or decision.get("targeted_regression_boundaries_approved") is not True
        or decision.get("staged_safe_body_adoption_approved") is not True
        or decision.get("full_r3_realign_safe_body_all_years") is not True
        or decision.get("reuse_r2_intervals_in_final_r3") is not False
        or int(scope.get("safe_body_utterances", -1)) != 4_384_992
        or int(scope.get("followup_utterances", -1)) != 718_364
    ):
        raise RuntimeError("workflow researcher decision contract differs")

    input_records = {
        "review_csv": file_fingerprint(review_csv, with_sha256=True),
        "targeted_regression_audit": file_fingerprint(
            targeted_audit_path, with_sha256=True
        ),
        "routing_independent_audit": file_fingerprint(
            routing_audit_path, with_sha256=True
        ),
        "candidate_independent_audit": file_fingerprint(
            candidate_audit_path, with_sha256=True
        ),
        "workflow_policy": file_fingerprint(
            workflow_policy_path, with_sha256=True
        ),
    }
    stable_identity = {
        "schema_version": SCHEMA_VERSION,
        "approved_by": decision["approved_by"],
        "approved_date": workflow["recorded_date"],
        "statement": decision["statement"],
        "review_rows": [
            {
                "review_id": row["review_id"],
                "utt_id": row["utt_id"],
                "target_word": row["target_word"],
                "decision": row["decision"],
            }
            for row in rows
        ],
        "scope": {
            "years": scope["years"],
            "safe_body_utterances": int(scope["safe_body_utterances"]),
            "followup_utterances": int(scope["followup_utterances"]),
            "full_r3_realign_safe_body_all_years": True,
            "reuse_r2_intervals_in_final_r3": False,
        },
        # The researcher's decision is bound to the reviewed evidence, not to the
        # byte layout of an implementation plan that may improve after external
        # review.  The review CSV and workflow policy remain provenance inputs,
        # but harmless documentation edits must not manufacture a new approval.
        "evidence_sha256": {
            key: input_records[key]["sha256"]
            for key in (
                "targeted_regression_audit",
                "routing_independent_audit",
                "candidate_independent_audit",
            )
        },
    }
    contract_id = stable_contract_id(stable_identity)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_explicit_researcher_approval",
        "recorded_at": now_iso(),
        "approval_contract_id": contract_id,
        "researcher": {
            "approved_by": decision["approved_by"],
            "approved_date": workflow["recorded_date"],
            "source": decision["source"],
            "statement": decision["statement"],
        },
        "review_rows": rows,
        "scope": stable_identity["scope"],
        "inputs": input_records,
        "gate": {
            "allow_staged_release_materialization": True,
            "allow_full_corpus_completion_claim": False,
            "allow_production_mfa_now": False,
            "reason_production_still_blocked": (
                "external workflow review and r3 runner/adoption audit remain"
            ),
        },
    }
    if output.is_file():
        existing = load_json(output)
        if (
            existing.get("status") == result["status"]
            and existing.get("approval_contract_id") == contract_id
        ):
            # The approval record is immutable after first materialization.
            # Changed implementation provenance is recorded in the separate
            # v2 sidecar by main(), never by rewriting this file.
            return existing, False
        raise RuntimeError("existing approval output has a different identity")
    atomic_write_json(output, result)
    return result, True


def main() -> int:
    review_root = (
        PROJECT_ROOT
        / "outputs"
        / "reviews"
        / "common_pron_r3_targeted_regression_20260808"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", type=Path, default=review_root / "REVIEW.csv")
    parser.add_argument(
        "--targeted-audit",
        type=Path,
        default=(
            Path("D:/mfa_common_pron/staging/common_pron_mfa_r3_20260807")
            / "21_targeted_regression_2022"
            / "TARGETED_REGRESSION_AUDIT.json"
        ),
    )
    parser.add_argument(
        "--routing-audit",
        type=Path,
        default=(
            PROJECT_ROOT
            / "outputs/reports/AUDIT_common_pron_r3_pre_adoption_routing_20260808.json"
        ),
    )
    parser.add_argument(
        "--candidate-audit",
        type=Path,
        default=(
            PROJECT_ROOT
            / "outputs/reports/AUDIT_common_pron_r3_safe_body_candidate_20260808.json"
        ),
    )
    parser.add_argument(
        "--workflow-policy",
        type=Path,
        default=PROJECT_ROOT / "config/mfa_r3_full_realign_workflow_v1.json",
    )
    parser.add_argument(
        "--output", type=Path, default=review_root / "RESEARCHER_APPROVAL.json"
    )
    parser.add_argument(
        "--provenance-sidecar",
        type=Path,
        help=(
            "append-only provenance JSON; defaults beside --output as "
            "<stem>.provenance.v2.json"
        ),
    )
    args = parser.parse_args()
    result, wrote = build_approval(
        review_csv=args.review_csv.resolve(),
        targeted_audit_path=args.targeted_audit.resolve(),
        routing_audit_path=args.routing_audit.resolve(),
        candidate_audit_path=args.candidate_audit.resolve(),
        workflow_policy_path=args.workflow_policy.resolve(),
        output=args.output.resolve(),
    )
    sidecar = (
        args.provenance_sidecar.resolve()
        if args.provenance_sidecar is not None
        else args.output.resolve().with_name(
            f"{args.output.resolve().stem}.provenance.v2.json"
        )
    )
    input_records = {
        "review_csv": file_fingerprint(args.review_csv.resolve(), with_sha256=True),
        "targeted_regression_audit": file_fingerprint(
            args.targeted_audit.resolve(), with_sha256=True
        ),
        "routing_independent_audit": file_fingerprint(
            args.routing_audit.resolve(), with_sha256=True
        ),
        "candidate_independent_audit": file_fingerprint(
            args.candidate_audit.resolve(), with_sha256=True
        ),
        "workflow_policy": file_fingerprint(
            args.workflow_policy.resolve(), with_sha256=True
        ),
    }
    _, sidecar_wrote = record_approval_provenance(
        approval_contract_id=result["approval_contract_id"],
        approval_fingerprint=file_fingerprint(
            args.output.resolve(), with_sha256=True
        ),
        input_records=input_records,
        sidecar=sidecar,
    )
    print(
        "[OK] staged r3 researcher approval: "
        f"{result['approval_contract_id'][:12]} "
        f"(approval={'written' if wrote else 'immutable'}, "
        f"provenance={'appended' if sidecar_wrote else 'unchanged'})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
