#!/usr/bin/env python3
"""Delete only an explicitly approved exact MFA temp inventory.

The inventory is treated as immutable.  Every candidate and retained asset is
revalidated by resolved path, classification, byte size, and mtime before any
unlink.  No directory or wildcard deletion is supported.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping

from inventory_mfa_storage import classify_temp_file
from pipeline_common import atomic_write_json, now_iso, sha256_file


CANDIDATE_CLASS = "cleanup_candidate_after_qc"
INVENTORY_KIND = "mfa_storage_inventory_and_cleanup_dry_run"
APPROVAL_SCOPES: dict[str, dict[str, Any]] = {
    "MFA_R2_TEMP_CLEANUP_2021_ARI30_20260831": {
        "year": "2021",
        "temp_root": r"D:\mfa_tmp\2021",
        "inventory_sha256": (
            "495a62282ef060dcace0d59a8bbde1adc652ff1060cc2f26062dada002d82fc7"
        ),
        "candidate_files": 63,
        "candidate_bytes": 33_754_468_034,
        "retained_db_sha256": (
            "a7719a62c41b6694783aa0f43aab70dbf7dfecd3864edfdc09af7b3953348d07"
        ),
    }
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
        str(right.resolve(strict=False))
    )


def assert_under(path: Path, root: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise RuntimeError(f"path outside approved temp root: {path}") from exc


def stat_matches(path: Path, record: Mapping[str, Any]) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    stat = path.stat()
    return (
        stat.st_size == int(record["bytes"])
        and stat.st_mtime_ns == int(record["mtime_ns"])
    )


def build_plan(
    inventory_path: Path,
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    inventory_path = inventory_path.resolve()
    inventory = read_json(inventory_path)
    blockers: list[str] = []
    inventory_sha = sha256_file(inventory_path)
    if inventory_sha != str(scope["inventory_sha256"]):
        blockers.append("inventory_sha256_mismatch")
    if inventory.get("kind") != INVENTORY_KIND:
        blockers.append("inventory_kind_mismatch")
    if inventory.get("status") != "ready_for_user_review":
        blockers.append("inventory_not_ready")
    if str(inventory.get("year") or "") != str(scope["year"]):
        blockers.append("inventory_year_mismatch")
    for key in (
        "blockers",
        "unsafe_links",
        "active_transaction_files",
        "unclassified_files",
    ):
        if inventory.get(key) not in ([], None):
            blockers.append(f"inventory_{key}_present")

    temp_root = Path(str(inventory.get("temp_year") or "")).resolve(strict=False)
    approved_root = Path(str(scope["temp_root"])).resolve(strict=False)
    if not same_path(temp_root, approved_root):
        blockers.append("temp_root_mismatch")
    if not temp_root.is_dir():
        blockers.append("temp_root_missing")
    for suffix in (".db-journal", ".db-wal", ".db-shm"):
        if temp_root.is_dir() and any(temp_root.rglob(f"*{suffix}")):
            blockers.append("live_sqlite_transaction_present")

    candidates: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    seen: set[str] = set()
    rows = inventory.get("files")
    if not isinstance(rows, list):
        rows = []
        blockers.append("inventory_files_missing")
    for record in rows:
        if not isinstance(record, dict):
            blockers.append("invalid_file_record")
            continue
        relative = str(record.get("relative_path") or "")
        path = Path(str(record.get("path") or "")).resolve(strict=False)
        expected = (temp_root / Path(relative)).resolve(strict=False)
        try:
            assert_under(path, temp_root)
        except RuntimeError:
            blockers.append(f"path_outside_root:{relative}")
            continue
        if not same_path(path, expected):
            blockers.append(f"relative_path_mismatch:{relative}")
            continue
        key = os.path.normcase(str(path))
        if key in seen:
            blockers.append(f"duplicate_path:{relative}")
            continue
        seen.add(key)
        observed_class, _ = classify_temp_file(
            year=str(scope["year"]), relative_path=relative
        )
        recorded_class = str(record.get("classification") or "")
        if observed_class != recorded_class:
            blockers.append(f"classification_changed:{relative}")
            continue
        if not stat_matches(path, record):
            blockers.append(f"file_changed_or_missing:{relative}")
            continue
        if recorded_class == CANDIDATE_CLASS:
            normalized = relative.replace("\\", "/").lower()
            if normalized.endswith(
                (".db", ".mdl", ".fst", ".yaml", ".log", "/tree")
            ):
                blockers.append(f"protected_candidate:{relative}")
                continue
            candidates.append(record)
        else:
            retained.append(record)

    candidate_bytes = sum(int(row["bytes"]) for row in candidates)
    if len(candidates) != int(scope["candidate_files"]):
        blockers.append("candidate_count_mismatch")
    if candidate_bytes != int(scope["candidate_bytes"]):
        blockers.append("candidate_bytes_mismatch")

    db_rows = [
        row
        for row in retained
        if str(row.get("classification")) == "retain_critical"
        and str(row.get("relative_path")) == f"{scope['year']}.db"
    ]
    if len(db_rows) != 1:
        blockers.append("retained_db_contract_mismatch")
    elif sha256_file(Path(str(db_rows[0]["path"]))) != str(
        scope["retained_db_sha256"]
    ):
        blockers.append("retained_db_sha256_mismatch")

    return {
        "schema": "mfa_temp_exact_cleanup_apply.v1",
        "status": "dry_run_passed" if not blockers else "blocked",
        "checked_at": now_iso(),
        "inventory": {
            "path": str(inventory_path),
            "sha256": inventory_sha,
        },
        "year": str(scope["year"]),
        "temp_root": str(temp_root),
        "expected": {
            "files": int(scope["candidate_files"]),
            "bytes": int(scope["candidate_bytes"]),
        },
        "observed": {"files": len(candidates), "bytes": candidate_bytes},
        "blockers": sorted(set(blockers)),
        "candidates": candidates,
        "retained_assets": retained,
        "retained_db_sha256": str(scope["retained_db_sha256"]),
        "safety": {
            "directory_deletion_supported": False,
            "wildcard_deletion_supported": False,
            "only_exact_inventory_candidates_may_be_unlinked": True,
        },
    }


def verify_retained(records: list[dict[str, Any]]) -> None:
    changed = [
        str(row["path"])
        for row in records
        if not stat_matches(Path(str(row["path"])), row)
    ]
    if changed:
        raise RuntimeError(f"retained asset changed or missing: {changed[:5]}")


def apply_plan(plan: dict[str, Any], output: Path) -> dict[str, Any]:
    output = output.resolve(strict=False)
    temp_root = Path(str(plan["temp_root"]))
    state = dict(plan)
    state.update(
        {
            "status": "deletion_in_progress",
            "apply_started_at": now_iso(),
            "drive_free_bytes_before": shutil.disk_usage(temp_root).free,
            "deleted": [],
            "current_path": None,
        }
    )
    atomic_write_json(output, state)
    try:
        for record in plan["candidates"]:
            path = Path(str(record["path"]))
            assert_under(path, temp_root)
            state["current_path"] = str(path)
            atomic_write_json(output, state)
            if not stat_matches(path, record):
                raise RuntimeError(f"candidate changed before unlink: {path}")
            path.unlink()
            state["deleted"].append(
                {
                    "path": str(path),
                    "bytes": int(record["bytes"]),
                    "deleted_at": now_iso(),
                }
            )
            state["current_path"] = None
            atomic_write_json(output, state)
        verify_retained(plan["retained_assets"])
        remaining = [
            str(row["path"])
            for row in plan["candidates"]
            if Path(str(row["path"])).exists()
        ]
        if remaining:
            raise RuntimeError(f"approved candidates remain: {remaining[:5]}")
        db_path = temp_root / f"{plan['year']}.db"
        observed_db_sha = sha256_file(db_path)
        if observed_db_sha != plan["retained_db_sha256"]:
            raise RuntimeError("retained DB SHA changed after cleanup")
        free_after = shutil.disk_usage(temp_root).free
        state.update(
            {
                "status": "passed",
                "completed_at": now_iso(),
                "current_path": None,
                "deleted_files": len(state["deleted"]),
                "deleted_bytes": sum(int(row["bytes"]) for row in state["deleted"]),
                "drive_free_bytes_after": free_after,
                "drive_free_bytes_delta": free_after
                - int(state["drive_free_bytes_before"]),
                "retained_db_sha256_after": observed_db_sha,
            }
        )
        atomic_write_json(output, state)
        return state
    except BaseException as exc:
        state.update(
            {
                "status": "failed",
                "failed_at": now_iso(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        atomic_write_json(output, state)
        raise


def finalize_existing_apply(
    inventory_path: Path,
    scope: Mapping[str, Any],
    output: Path,
) -> dict[str, Any]:
    """Finish verification after interruption following all exact unlinks."""
    inventory_path = inventory_path.resolve()
    output = output.resolve(strict=False)
    inventory = read_json(inventory_path)
    state = read_json(output)
    if state.get("status") != "deletion_in_progress":
        raise RuntimeError("existing apply report is not resumable")
    if sha256_file(inventory_path) != str(scope["inventory_sha256"]):
        raise RuntimeError("inventory SHA changed during finalization")
    if str(inventory.get("year")) != str(scope["year"]):
        raise RuntimeError("inventory year changed during finalization")
    temp_root = Path(str(inventory.get("temp_year") or "")).resolve(strict=False)
    if not same_path(temp_root, Path(str(scope["temp_root"]))):
        raise RuntimeError("temp root changed during finalization")

    rows = inventory.get("files")
    if not isinstance(rows, list):
        raise RuntimeError("inventory files missing during finalization")
    candidates = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("classification")) == CANDIDATE_CLASS
    ]
    retained = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("classification")) != CANDIDATE_CLASS
    ]
    candidate_bytes = sum(int(row["bytes"]) for row in candidates)
    if len(candidates) != int(scope["candidate_files"]):
        raise RuntimeError("candidate count changed during finalization")
    if candidate_bytes != int(scope["candidate_bytes"]):
        raise RuntimeError("candidate bytes changed during finalization")

    approved = {
        os.path.normcase(str(Path(str(row["path"])).resolve(strict=False))): int(
            row["bytes"]
        )
        for row in candidates
    }
    deleted_rows = state.get("deleted")
    if not isinstance(deleted_rows, list):
        raise RuntimeError("deleted ledger missing during finalization")
    deleted = {
        os.path.normcase(str(Path(str(row["path"])).resolve(strict=False))): int(
            row["bytes"]
        )
        for row in deleted_rows
        if isinstance(row, dict)
    }
    if deleted != approved:
        raise RuntimeError("deleted ledger differs from approved candidates")
    remaining = [str(row["path"]) for row in candidates if Path(str(row["path"])).exists()]
    if remaining:
        raise RuntimeError(f"approved candidates remain: {remaining[:5]}")
    verify_retained(retained)
    db_path = temp_root / f"{scope['year']}.db"
    observed_db_sha = sha256_file(db_path)
    if observed_db_sha != str(scope["retained_db_sha256"]):
        raise RuntimeError("retained DB SHA changed after interrupted cleanup")
    free_after = shutil.disk_usage(temp_root).free
    state.update(
        {
            "status": "passed",
            "completed_at": now_iso(),
            "completion_mode": "postdelete_verification_after_interruption",
            "current_path": None,
            "deleted_files": len(deleted_rows),
            "deleted_bytes": sum(int(row["bytes"]) for row in deleted_rows),
            "drive_free_bytes_after": free_after,
            "drive_free_bytes_delta": free_after
            - int(state["drive_free_bytes_before"]),
            "retained_db_sha256_after": observed_db_sha,
        }
    )
    atomic_write_json(output, state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--finalize-existing", action="store_true")
    parser.add_argument("--approval-token", default="")
    args = parser.parse_args()
    if args.apply or args.finalize_existing:
        scope = APPROVAL_SCOPES.get(args.approval_token)
        if scope is None:
            raise RuntimeError("exact researcher approval token mismatch")
    else:
        scope = next(iter(APPROVAL_SCOPES.values()))
    if args.finalize_existing:
        result = finalize_existing_apply(args.inventory, scope, args.output)
    else:
        plan = build_plan(args.inventory, scope)
        if plan["status"] != "dry_run_passed":
            atomic_write_json(args.output.resolve(strict=False), plan)
            print(json.dumps({"status": "blocked", "blockers": plan["blockers"]}))
            return 2
        result = apply_plan(plan, args.output) if args.apply else plan
        if not args.apply:
            atomic_write_json(args.output.resolve(strict=False), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "files": result.get("deleted_files", result["observed"]["files"]),
                "bytes": result.get("deleted_bytes", result["observed"]["bytes"]),
                "output": str(args.output.resolve(strict=False)),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
