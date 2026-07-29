"""Apply validated common-pronunciation researcher decisions transactionally.

This is the only bridge from the normalized workbook decision artifacts to
the two D: researcher review ledgers.  It does not repair G2P shards or create
the final dictionary.  Default execution is a read-only plan; writes require
``--apply`` and a ``ready_for_apply`` validation manifest.

Before changing either ledger the script:

1. verifies the workbook validation manifest and normalized CSV fingerprints;
2. verifies that the current ledgers still match the clean workbook inputs;
3. re-checks all approved phones against the frozen 107-phone inventory;
4. writes and re-reads proposed ledgers in an isolated transaction folder;
5. archives both originals and all decision evidence.

Each ledger is promoted with ``os.replace``.  If any promotion or post-write
verification fails, both ledgers are restored from the exact archived bytes.
The correction registry is a separate immutable output; raw corpus files are
never changed.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_common_pron_mfa_lexicon as lexicon  # noqa: E402
import common_pron_no_path_review as no_path  # noqa: E402
import validate_common_pron_researcher_review_xlsx as validator  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_researcher_decision_application.v1"
EXPECTED_NO_PATH_DECISIONS = 23
EXPECTED_JAMO_DECISIONS = 4
EXPECTED_CORRECTIONS = {"외곬수적인", "천구백칤비육"}


class DecisionApplicationError(RuntimeError):
    """Validated decisions cannot be safely applied to current ledgers."""


def clean(value: object) -> str:
    return str(value or "").strip()


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved_root = root.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise DecisionApplicationError(
            f"path boundary violation: {resolved} (root={resolved_root})"
        )
    return resolved


@contextmanager
def application_lock(lock_path: Path, transaction_id: str):
    """Hold the same exclusive release lock used by the r2 runner."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "common_pron_researcher_decision_application_lock",
        "transaction_id": transaction_id,
        "pid": os.getpid(),
        "created_at": now_iso(),
    }
    try:
        with lock_path.open(
            "x", encoding="utf-8", newline="\n"
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise DecisionApplicationError(
            f"r2 runner/application lock exists: {lock_path}"
        ) from exc
    try:
        yield payload
    finally:
        if lock_path.exists():
            current = read_json(lock_path)
            if (
                current.get("transaction_id") != transaction_id
                or current.get("pid") != os.getpid()
            ):
                raise DecisionApplicationError(
                    f"application lock ownership changed: {lock_path}"
                )
            lock_path.unlink()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(
    path: Path, expected_fields: tuple[str, ...]
) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != expected_fields:
            raise DecisionApplicationError(
                f"CSV field contract mismatch: {path} "
                f"{reader.fieldnames}"
            )
        return [
            {field: clean(row.get(field)) for field in expected_fields}
            for row in reader
        ]


def write_csv(
    path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=fields, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def verify_record(path: Path, record: dict[str, Any], label: str) -> None:
    if not path.is_file():
        raise DecisionApplicationError(f"{label} is missing: {path}")
    actual = file_fingerprint(path, with_sha256=True)
    if (
        actual["bytes"] != record.get("bytes")
        or actual["sha256"] != record.get("sha256")
    ):
        raise DecisionApplicationError(
            f"{label} fingerprint changed: {path}"
        )


def decision_notes(row: dict[str, str]) -> str:
    researcher_notes = clean(row["researcher_notes"])
    if researcher_notes:
        return (
            f"workbook_decision={row['researcher_decision']}; "
            f"researcher_notes={researcher_notes}"
        )
    return (
        f"workbook_decision={row['researcher_decision']}; "
        f"fixed_evidence={row['reason']}"
    )


def decision_evidence(row: dict[str, str]) -> str:
    return "|".join(
        value
        for value in (
            clean(row["approved_phone_provenance"]),
            clean(row["approved_phone_source"]),
            clean(row["source_url"]),
        )
        if value
    )


def validate_normalized_decisions(
    rows: list[dict[str, str]], inventory: set[str]
) -> dict[str, dict[str, str]]:
    if len(rows) != EXPECTED_NO_PATH_DECISIONS + EXPECTED_JAMO_DECISIONS:
        raise DecisionApplicationError(
            f"normalized decision row count mismatch: {len(rows)}"
        )
    tokens = [row["token"] for row in rows]
    if len(tokens) != len(set(tokens)):
        raise DecisionApplicationError(
            "normalized decision tokens are duplicated"
        )
    categories = Counter(row["category"] for row in rows)
    if categories != Counter(
        {
            "no_path": EXPECTED_NO_PATH_DECISIONS,
            "jamo_ls": EXPECTED_JAMO_DECISIONS,
        }
    ):
        raise DecisionApplicationError(
            f"normalized decision categories mismatch: {dict(categories)}"
        )

    for row in rows:
        token = row["token"]
        if row["researcher_decision"] not in validator.AFFIRMATIVE_DECISIONS:
            raise DecisionApplicationError(
                f"non-affirmative normalized decision: {token}"
            )
        approved = validator.validate_phone(
            token=token,
            label="approved",
            value=row["approved_pron_phones_mfa"],
            inventory=inventory,
            required=True,
        )
        candidate = validator.validate_phone(
            token=token,
            label="model_candidate",
            value=row["model_candidate_phone"],
            inventory=inventory,
            required=True,
        )
        if approved != row["approved_pron_phones_mfa"]:
            raise DecisionApplicationError(
                f"approved phone is not canonicalized: {token}"
            )
        if candidate != row["model_candidate_phone"]:
            raise DecisionApplicationError(
                f"candidate phone is not canonicalized: {token}"
            )
        if (
            approved != candidate
            and row["approved_phone_provenance"]
            != "researcher_workbook_manual_same_inventory"
        ):
            raise DecisionApplicationError(
                f"manual phone provenance mismatch: {token}"
            )
        if (
            approved == candidate
            and row["approved_phone_provenance"]
            != "researcher_workbook_same_frozen_candidate"
        ):
            raise DecisionApplicationError(
                f"same-model provenance mismatch: {token}"
            )
        if (
            approved != candidate
            and not clean(row["researcher_notes"])
        ):
            raise DecisionApplicationError(
                f"manual approved phone has no researcher notes: {token}"
            )
    return {row["token"]: row for row in rows}


def build_no_path_rows(
    current: list[dict[str, str]],
    decisions: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    decision_rows = {
        token: row
        for token, row in decisions.items()
        if row["category"] == "no_path"
    }
    current_by_surface = {row["surface"]: row for row in current}
    if len(current_by_surface) != len(current):
        raise DecisionApplicationError("no-path ledger surface duplicate")
    pending_surfaces = {
        row["surface"]
        for row in current
        if row["decision"] == "pending"
    }
    if set(decision_rows) != pending_surfaces:
        raise DecisionApplicationError(
            "no-path normalized tokens differ from current pending rows: "
            f"missing={sorted(pending_surfaces - set(decision_rows))}, "
            f"extras={sorted(set(decision_rows) - pending_surfaces)}"
        )
    existing_approved = [
        row for row in current if row["decision"] == "approved"
    ]
    if (
        len(existing_approved) != 1
        or existing_approved[0]["surface"] != "읊어"
    ):
        raise DecisionApplicationError(
            "expected preserved legacy approval 읊어 is missing or changed"
        )

    proposed: list[dict[str, str]] = []
    for row in current:
        decision = decision_rows.get(row["surface"])
        if decision is None:
            proposed.append(dict(row))
            continue
        if (
            decision["model_input"] != row["respelled"]
            or decision["model_candidate_phone"]
            != row["pron_phones_mfa"]
        ):
            raise DecisionApplicationError(
                f"no-path candidate changed: {row['surface']}"
            )
        updated = dict(row)
        updated["approved_pron_phones_mfa"] = decision[
            "approved_pron_phones_mfa"
        ]
        updated["approved_phone_evidence"] = decision_evidence(decision)
        updated["decision"] = "approved"
        updated["notes"] = decision_notes(decision)
        proposed.append(updated)
    if sum(row["decision"] == "approved" for row in proposed) != 24:
        raise DecisionApplicationError(
            "no-path proposed approval count is not 24"
        )
    return proposed


def build_jamo_rows(
    current: list[dict[str, str]],
    decisions: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    decision_rows = {
        token: row
        for token, row in decisions.items()
        if row["category"] == "jamo_ls"
    }
    current_by_token = {row["token"]: row for row in current}
    if (
        len(current_by_token) != EXPECTED_JAMO_DECISIONS
        or set(current_by_token) != set(decision_rows)
    ):
        raise DecisionApplicationError(
            "Jamo normalized tokens differ from current ledger"
        )
    if any(row["decision"] != "pending" for row in current):
        raise DecisionApplicationError(
            "Jamo ledger has a pre-existing non-pending decision"
        )

    proposed: list[dict[str, str]] = []
    for row in current:
        decision = decision_rows[row["token"]]
        if (
            decision["model_input"] != row["model_input"]
            or decision["model_candidate_phone"]
            != row["pron_phones_mfa"]
        ):
            raise DecisionApplicationError(
                f"Jamo candidate changed: {row['token']}"
            )
        proposed.append(
            {
                **row,
                "approved_pron_phones_mfa": decision[
                    "approved_pron_phones_mfa"
                ],
                "decision": "approved",
                "evidence_source": decision_evidence(decision),
                "notes": decision_notes(decision),
            }
        )
    if len(proposed) != 4 or any(
        row["decision"] != "approved"
        or not row["approved_pron_phones_mfa"]
        for row in proposed
    ):
        raise DecisionApplicationError(
            "Jamo proposed approval contract is incomplete"
        )
    return proposed


def load_application_plan(
    *,
    validation_manifest_path: Path,
    no_path_review_path: Path,
    jamo_review_path: Path,
) -> dict[str, Any]:
    validation_manifest = read_json(validation_manifest_path)
    if (
        validation_manifest.get("schema_version")
        != validator.SCHEMA_VERSION
        or validation_manifest.get("status") != "ready_for_apply"
        or validation_manifest.get("ready_for_apply") is not True
    ):
        raise DecisionApplicationError(
            "validation manifest is not ready_for_apply"
        )
    outputs = validation_manifest.get("outputs", {})
    decision_record = outputs.get("normalized_decisions", {})
    correction_record = outputs.get("correction_registry", {})
    decision_path = Path(clean(decision_record.get("path")))
    correction_path = Path(clean(correction_record.get("path")))
    verify_record(
        decision_path, decision_record, "normalized decisions"
    )
    verify_record(
        correction_path, correction_record, "correction registry"
    )
    decisions = read_csv(decision_path, validator.DECISION_FIELDS)
    corrections = read_csv(
        correction_path, validator.CORRECTION_FIELDS
    )
    correction_tokens = {row["token"] for row in corrections}
    if (
        len(corrections) != 2
        or correction_tokens != EXPECTED_CORRECTIONS
    ):
        raise DecisionApplicationError(
            f"correction registry mismatch: {sorted(correction_tokens)}"
        )

    template_manifest_record = validation_manifest.get("inputs", {}).get(
        "template_manifest", {}
    )
    template_manifest_path = Path(
        clean(template_manifest_record.get("path"))
    )
    verify_record(
        template_manifest_path,
        template_manifest_record,
        "clean template manifest",
    )
    template_manifest = read_json(template_manifest_path)
    no_path_record = template_manifest.get("inputs", {}).get(
        "no_path_review", {}
    )
    jamo_record = template_manifest.get("inputs", {}).get(
        "jamo_review", {}
    )
    verify_record(
        no_path_review_path, no_path_record, "current no-path ledger"
    )
    verify_record(
        jamo_review_path, jamo_record, "current Jamo ledger"
    )

    inventory, inventory_contract, model_bundle_path = (
        validator.load_frozen_inventory(template_manifest)
    )
    decision_by_token = validate_normalized_decisions(
        decisions, inventory
    )
    current_no_path = no_path.read_review(no_path_review_path)
    current_jamo = lexicon.read_special_review(jamo_review_path)
    proposed_no_path = build_no_path_rows(
        current_no_path, decision_by_token
    )
    proposed_jamo = build_jamo_rows(current_jamo, decision_by_token)
    return {
        "validation_manifest": validation_manifest,
        "validation_manifest_path": validation_manifest_path,
        "template_manifest_path": template_manifest_path,
        "model_bundle_path": model_bundle_path,
        "decision_path": decision_path,
        "correction_path": correction_path,
        "corrections": corrections,
        "current_no_path": current_no_path,
        "current_jamo": current_jamo,
        "proposed_no_path": proposed_no_path,
        "proposed_jamo": proposed_jamo,
        "inventory_contract": inventory_contract,
        "counts": {
            "normalized_decisions": len(decisions),
            "no_path_existing_approved_preserved": 1,
            "no_path_new_approved": 23,
            "no_path_total_approved": 24,
            "jamo_new_approved": 4,
            "correction_registry_rows": len(corrections),
        },
    }


def copy_exact(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"archive destination exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256_file(source) != sha256_file(destination):
        raise DecisionApplicationError(
            f"archive copy hash mismatch: {source} -> {destination}"
        )


def promote_copy(source: Path, destination: Path, txid: str) -> None:
    temp = destination.with_name(f".{destination.name}.{txid}.partial")
    if temp.exists():
        raise FileExistsError(f"stale promotion partial exists: {temp}")
    shutil.copy2(source, temp)
    if sha256_file(source) != sha256_file(temp):
        raise DecisionApplicationError(
            f"promotion staging hash mismatch: {destination}"
        )
    os.replace(temp, destination)


def restore_copy(source: Path, destination: Path, txid: str) -> None:
    temp = destination.with_name(f".{destination.name}.{txid}.rollback")
    if temp.exists():
        raise FileExistsError(f"stale rollback partial exists: {temp}")
    shutil.copy2(source, temp)
    if sha256_file(source) != sha256_file(temp):
        raise DecisionApplicationError(
            f"rollback staging hash mismatch: {destination}"
        )
    os.replace(temp, destination)


def verify_proposed_files(
    no_path_path: Path,
    jamo_path: Path,
    expected_no_path: list[dict[str, str]],
    expected_jamo: list[dict[str, str]],
) -> None:
    if no_path.read_review(no_path_path) != expected_no_path:
        raise DecisionApplicationError(
            f"no-path proposal verification failed: {no_path_path}"
        )
    if lexicon.read_special_review(jamo_path) != expected_jamo:
        raise DecisionApplicationError(
            f"Jamo proposal verification failed: {jamo_path}"
        )


def _apply_plan_locked(
    *,
    plan: dict[str, Any],
    release_root: Path,
    no_path_review_path: Path,
    jamo_review_path: Path,
) -> dict[str, Any]:
    release_root = release_root.resolve()
    no_path_review_path = ensure_within(
        no_path_review_path, release_root
    )
    jamo_review_path = ensure_within(jamo_review_path, release_root)
    release_id = release_root.name

    filled_sha = plan["validation_manifest"]["inputs"][
        "filled_workbook"
    ]["sha256"]
    txid = f"review_{filled_sha[:12]}"
    review_root = release_root / "03_review"
    transaction_root = review_root / "decision_transactions" / txid
    final_manifest_path = (
        review_root / f"decision_application_{txid}.manifest.json"
    )
    correction_destination = (
        review_root / f"correction_registry_{txid}.csv"
    )

    if final_manifest_path.exists():
        existing = read_json(final_manifest_path)
        if (
            existing.get("status") == "applied"
            and existing.get("transaction_id") == txid
        ):
            for label, path in (
                ("no_path_review", no_path_review_path),
                ("jamo_review", jamo_review_path),
                ("correction_registry", correction_destination),
            ):
                verify_record(
                    path,
                    existing["outputs"][label],
                    f"idempotent {label}",
                )
            return existing
        raise DecisionApplicationError(
            f"existing application manifest is not reusable: "
            f"{final_manifest_path}"
        )
    if transaction_root.exists() or correction_destination.exists():
        raise DecisionApplicationError(
            f"incomplete or conflicting transaction exists: "
            f"{transaction_root}"
        )

    archive_root = transaction_root / "archive"
    proposal_root = transaction_root / "proposed"
    evidence_root = transaction_root / "evidence"
    archive_no_path = archive_root / no_path_review_path.name
    archive_jamo = archive_root / jamo_review_path.name
    proposal_no_path = proposal_root / no_path_review_path.name
    proposal_jamo = proposal_root / jamo_review_path.name
    proposal_corrections = proposal_root / correction_destination.name

    transaction_root.mkdir(parents=True, exist_ok=False)
    copy_exact(no_path_review_path, archive_no_path)
    copy_exact(jamo_review_path, archive_jamo)
    for source in (
        plan["validation_manifest_path"],
        plan["template_manifest_path"],
        plan["decision_path"],
        plan["correction_path"],
    ):
        copy_exact(source, evidence_root / source.name)

    proposal_root.mkdir(parents=True, exist_ok=True)
    write_csv(
        proposal_no_path,
        no_path.REVIEW_FIELDS,
        plan["proposed_no_path"],
    )
    write_csv(
        proposal_jamo,
        lexicon.SPECIAL_REVIEW_FIELDS,
        plan["proposed_jamo"],
    )
    write_csv(
        proposal_corrections,
        validator.CORRECTION_FIELDS,
        plan["corrections"],
    )
    verify_proposed_files(
        proposal_no_path,
        proposal_jamo,
        plan["proposed_no_path"],
        plan["proposed_jamo"],
    )
    prepared_manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "kind": "common_pron_researcher_decision_application",
        "recorded_at": now_iso(),
        "transaction_id": txid,
        "release_id": release_id,
        "inputs": {
            "validation_manifest": file_fingerprint(
                plan["validation_manifest_path"], with_sha256=True
            ),
            "no_path_review": file_fingerprint(
                no_path_review_path, with_sha256=True
            ),
            "jamo_review": file_fingerprint(
                jamo_review_path, with_sha256=True
            ),
        },
        "archives": {
            "no_path_review": file_fingerprint(
                archive_no_path, with_sha256=True
            ),
            "jamo_review": file_fingerprint(
                archive_jamo, with_sha256=True
            ),
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
        "counts": plan["counts"],
        "phone_inventory_contract": plan["inventory_contract"],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    prepared_manifest_path = transaction_root / "prepared_manifest.json"
    atomic_write_json(prepared_manifest_path, prepared_manifest)

    try:
        promote_copy(proposal_no_path, no_path_review_path, txid)
        promote_copy(proposal_jamo, jamo_review_path, txid)
        promote_copy(
            proposal_corrections, correction_destination, txid
        )
        verify_proposed_files(
            no_path_review_path,
            jamo_review_path,
            plan["proposed_no_path"],
            plan["proposed_jamo"],
        )
        if sha256_file(correction_destination) != sha256_file(
            proposal_corrections
        ):
            raise DecisionApplicationError(
                "promoted correction registry hash mismatch"
            )
        final_manifest = {
            **prepared_manifest,
            "status": "applied",
            "applied_at": now_iso(),
            "prepared_manifest": file_fingerprint(
                prepared_manifest_path, with_sha256=True
            ),
            "outputs": {
                "no_path_review": file_fingerprint(
                    no_path_review_path, with_sha256=True
                ),
                "jamo_review": file_fingerprint(
                    jamo_review_path, with_sha256=True
                ),
                "correction_registry": file_fingerprint(
                    correction_destination, with_sha256=True
                ),
            },
            "gates": {
                "exclusive_runner_lock_held": True,
                "originals_archived_before_promotion": True,
                "no_path_post_write_verified": True,
                "jamo_post_write_verified": True,
                "correction_registry_hash_verified": True,
                "raw_corpus_modified": False,
                "g2p_shards_modified": False,
                "final_dictionary_created": False,
            },
            "implementation": {
                "apply_script": file_fingerprint(
                    Path(__file__).resolve(), with_sha256=True
                )
            },
            "runtime": runtime_snapshot(PROJECT_ROOT),
        }
        applied_manifest_path = (
            transaction_root / "applied_manifest.json"
        )
        atomic_write_json(applied_manifest_path, final_manifest)
        promote_copy(
            applied_manifest_path, final_manifest_path, txid
        )
        return final_manifest
    except BaseException as error:
        rollback_errors: list[str] = []
        for archive, destination in (
            (archive_no_path, no_path_review_path),
            (archive_jamo, jamo_review_path),
        ):
            try:
                restore_copy(archive, destination, txid)
            except BaseException as rollback_error:
                rollback_errors.append(str(rollback_error))
        failure = {
            **prepared_manifest,
            "status": "rolled_back"
            if not rollback_errors
            else "rollback_failed",
            "failed_at": now_iso(),
            "error": repr(error),
            "rollback_errors": rollback_errors,
            "post_rollback": {
                "no_path_review": file_fingerprint(
                    no_path_review_path, with_sha256=True
                ),
                "jamo_review": file_fingerprint(
                    jamo_review_path, with_sha256=True
                ),
            },
        }
        atomic_write_json(
            transaction_root / "failure_manifest.json", failure
        )
        raise


def apply_plan(
    *,
    plan: dict[str, Any],
    release_root: Path,
    no_path_review_path: Path,
    jamo_review_path: Path,
) -> dict[str, Any]:
    release_root = release_root.resolve()
    filled_sha = plan["validation_manifest"]["inputs"][
        "filled_workbook"
    ]["sha256"]
    txid = f"review_{filled_sha[:12]}"
    common_root = release_root.parents[1]
    lock_path = common_root / "locks" / f"{release_root.name}.lock"
    with application_lock(lock_path, txid):
        final_manifest_path = (
            release_root
            / "03_review"
            / f"decision_application_{txid}.manifest.json"
        )
        if final_manifest_path.exists():
            return _apply_plan_locked(
                plan=plan,
                release_root=release_root,
                no_path_review_path=no_path_review_path,
                jamo_review_path=jamo_review_path,
            )
        refreshed = load_application_plan(
            validation_manifest_path=plan[
                "validation_manifest_path"
            ],
            no_path_review_path=no_path_review_path,
            jamo_review_path=jamo_review_path,
        )
        refreshed_sha = refreshed["validation_manifest"]["inputs"][
            "filled_workbook"
        ]["sha256"]
        if refreshed_sha != filled_sha:
            raise DecisionApplicationError(
                "validation input changed while acquiring application lock"
            )
        return _apply_plan_locked(
            plan=refreshed,
            release_root=release_root,
            no_path_review_path=no_path_review_path,
            jamo_review_path=jamo_review_path,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="검증된 공통발음 r2 연구자 결정을 두 원장에 적용"
    )
    parser.add_argument(
        "--validation-manifest", type=Path, required=True
    )
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--no-path-review", type=Path, required=True)
    parser.add_argument("--jamo-review", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="archive와 검증 뒤 실제 두 원장을 원자 교체",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    plan = load_application_plan(
        validation_manifest_path=args.validation_manifest.resolve(),
        no_path_review_path=args.no_path_review.resolve(),
        jamo_review_path=args.jamo_review.resolve(),
    )
    if not args.apply:
        print(
            json.dumps(
                {
                    "status": "validated_dry_run",
                    "apply_requested": False,
                    "counts": plan["counts"],
                    "phone_inventory_contract": plan[
                        "inventory_contract"
                    ],
                    "writes": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    manifest = apply_plan(
        plan=plan,
        release_root=args.release_root.resolve(),
        no_path_review_path=args.no_path_review.resolve(),
        jamo_review_path=args.jamo_review.resolve(),
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "transaction_id": manifest["transaction_id"],
                "counts": manifest["counts"],
                "manifest": str(
                    (
                        args.release_root.resolve()
                        / "03_review"
                        / (
                            "decision_application_"
                            f"{manifest['transaction_id']}.manifest.json"
                        )
                    )
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
