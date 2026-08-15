"""Apply an exact, previously inventoried MFA r3 temp-file cleanup.

This deliberately does not discover additional deletion targets.  It accepts
only files classified by ``inventory_mfa_storage.py`` as
``cleanup_candidate_after_qc`` and revalidates every path, size, mtime, and
classification immediately before unlinking it.  Alignment databases and
reproducibility files are verified as retained assets.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from inventory_mfa_storage import classify_temp_file
from pipeline_common import atomic_write_json, file_fingerprint, now_iso


SUMMARY_SCHEMA = "mfa_r3_storage_cleanup_review.v1"
INVENTORY_KIND = "mfa_storage_inventory_and_cleanup_dry_run"
CANDIDATE_CLASS = "cleanup_candidate_after_qc"
APPROVAL_SCOPES: dict[str, dict[str, Any]] = {
    "R3_TEMP_CLEANUP_2020_2023_ARI30_20260813": {
        "years": ["2020", "2021", "2022", "2023"],
        "expected_files": 252,
        "expected_bytes": 73_230_387_524,
    },
    "R3_TEMP_CLEANUP_2024_2025_ARI30_20260815": {
        "years": ["2024", "2025"],
        "expected_files": 126,
        "expected_bytes": 38_640_655_415,
    },
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object가 아님: {path}")
    return value


def same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
        str(right.resolve(strict=False))
    )


def assert_under(path: Path, root: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise RuntimeError(f"허용 root 밖의 경로: {path}") from exc


def stat_matches(path: Path, record: dict[str, Any]) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    stat = path.stat()
    return (
        stat.st_size == int(record["bytes"])
        and stat.st_mtime_ns == int(record["mtime_ns"])
    )


def validate_approval_scope(
    *,
    approval_token: str,
    years: list[str],
    expected_files: int,
    expected_bytes: int,
) -> None:
    """Bind a destructive approval token to one immutable cleanup scope."""

    scope = APPROVAL_SCOPES.get(approval_token)
    if scope is None:
        raise RuntimeError("연구자 승인 token 불일치")
    observed = {
        "years": years,
        "expected_files": expected_files,
        "expected_bytes": expected_bytes,
    }
    if observed != scope:
        raise RuntimeError(
            "연구자 승인 범위 불일치: "
            f"approved={scope!r}, requested={observed!r}"
        )


def build_plan(
    *,
    summary_path: Path,
    release_root: Path,
    years: list[str],
    expected_files: int,
    expected_bytes: int,
) -> dict[str, Any]:
    summary_path = summary_path.resolve()
    release_root = release_root.resolve(strict=False)
    summary = read_json(summary_path)
    blockers: list[str] = []

    if summary.get("schema_version") != SUMMARY_SCHEMA:
        blockers.append("summary_schema_mismatch")
    if summary.get("status") != "ready_for_researcher_review":
        blockers.append("summary_not_ready")
    if str(summary.get("release_id") or "") != release_root.name:
        blockers.append("release_id_mismatch")
    scope = summary.get("scope")
    if not isinstance(scope, dict) or scope.get("temp_only") is not True:
        blockers.append("summary_not_temp_only")
    elif [str(value) for value in scope.get("years", [])] != years:
        blockers.append("summary_years_mismatch")
    safety = summary.get("safety")
    if not isinstance(safety, dict):
        blockers.append("summary_safety_missing")
    else:
        required_false = (
            "deletion_performed",
            "move_performed",
            "archive_performed",
            "apply_supported",
            "source_corpus_modified",
        )
        for key in required_false:
            if safety.get(key) is not False:
                blockers.append(f"summary_{key}_not_false")
        for key in ("authorization_required_for_cleanup", "databases_retained", "final_6tier_retained"):
            if safety.get(key) is not True:
                blockers.append(f"summary_{key}_not_true")

    report_rows = summary.get("reports")
    if not isinstance(report_rows, list):
        report_rows = []
        blockers.append("summary_reports_missing")
    report_by_year = {str(row.get("year")): row for row in report_rows if isinstance(row, dict)}
    if sorted(report_by_year) != sorted(years):
        blockers.append("summary_report_years_mismatch")

    candidates: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    report_fingerprints: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for year in years:
        row = report_by_year.get(year)
        if row is None:
            continue
        report_path = Path(str(row.get("report_path") or "")).resolve(strict=False)
        if not report_path.is_file():
            blockers.append(f"{year}:inventory_report_missing")
            continue
        report_fingerprints.append(file_fingerprint(report_path, with_sha256=True))
        inventory = read_json(report_path)
        if inventory.get("kind") != INVENTORY_KIND:
            blockers.append(f"{year}:inventory_kind_mismatch")
        if inventory.get("status") != "ready_for_user_review":
            blockers.append(f"{year}:inventory_not_ready")
        if str(inventory.get("year") or "") != year:
            blockers.append(f"{year}:inventory_year_mismatch")
        if inventory.get("blockers") not in ([], None):
            blockers.append(f"{year}:inventory_has_blockers")
        if inventory.get("unsafe_links") not in ([], None):
            blockers.append(f"{year}:inventory_has_unsafe_links")
        if inventory.get("active_transaction_files") not in ([], None):
            blockers.append(f"{year}:inventory_has_active_transactions")
        if inventory.get("unclassified_files") not in ([], None):
            blockers.append(f"{year}:inventory_has_unclassified_files")

        temp_year = release_root / "temp" / year
        if not same_path(Path(str(inventory.get("temp_year") or "")), temp_year):
            blockers.append(f"{year}:temp_root_mismatch")
        if not temp_year.is_dir():
            blockers.append(f"{year}:temp_root_missing")
            continue

        for suffix in (".db-journal", ".db-wal", ".db-shm"):
            if any(temp_year.rglob(f"*{suffix}")):
                blockers.append(f"{year}:live_sqlite_transaction_present")

        files = inventory.get("files")
        if not isinstance(files, list):
            blockers.append(f"{year}:inventory_files_missing")
            continue
        year_candidates = 0
        year_candidate_bytes = 0
        for record in files:
            if not isinstance(record, dict):
                blockers.append(f"{year}:invalid_file_record")
                continue
            relative = str(record.get("relative_path") or "")
            path = Path(str(record.get("path") or "")).resolve(strict=False)
            expected_path = (temp_year / Path(relative)).resolve(strict=False)
            try:
                assert_under(path, temp_year)
            except RuntimeError:
                blockers.append(f"{year}:path_outside_temp:{relative}")
                continue
            if not same_path(path, expected_path):
                blockers.append(f"{year}:path_relative_mismatch:{relative}")
                continue
            key = os.path.normcase(str(path))
            if key in seen_paths:
                blockers.append(f"{year}:duplicate_path:{relative}")
                continue
            seen_paths.add(key)
            classification = str(record.get("classification") or "")
            observed_class, _ = classify_temp_file(year=year, relative_path=relative)
            if observed_class != classification:
                blockers.append(f"{year}:classification_changed:{relative}")
                continue
            if not stat_matches(path, record):
                blockers.append(f"{year}:file_changed_or_missing:{relative}")
                continue
            normalized = relative.replace("\\", "/").lower()
            if classification == CANDIDATE_CLASS:
                if normalized.endswith((".db", ".mdl", ".fst", ".yaml", ".log", "/tree")):
                    blockers.append(f"{year}:protected_suffix_in_candidates:{relative}")
                    continue
                candidates.append({"year": year, **record})
                year_candidates += 1
                year_candidate_bytes += int(record["bytes"])
            else:
                retained.append({"year": year, **record})

        if year_candidates != int(row.get("candidate_files", -1)):
            blockers.append(f"{year}:candidate_count_mismatch")
        if year_candidate_bytes != int(row.get("candidate_bytes", -1)):
            blockers.append(f"{year}:candidate_bytes_mismatch")

    candidate_bytes = sum(int(record["bytes"]) for record in candidates)
    if len(candidates) != expected_files:
        blockers.append("total_candidate_count_mismatch")
    if candidate_bytes != expected_bytes:
        blockers.append("total_candidate_bytes_mismatch")

    return {
        "schema_version": "mfa_r3_exact_temp_cleanup.v1",
        "status": "dry_run_passed" if not blockers else "blocked",
        "checked_at": now_iso(),
        "summary": file_fingerprint(summary_path, with_sha256=True),
        "release_root": str(release_root),
        "years": years,
        "expected": {"files": expected_files, "bytes": expected_bytes},
        "observed": {"files": len(candidates), "bytes": candidate_bytes},
        "blockers": sorted(set(blockers)),
        "inventory_reports": report_fingerprints,
        "candidates": candidates,
        "retained_assets": retained,
        "safety": {
            "source_corpus_modified": False,
            "alignment_databases_deleted": False,
            "final_6tier_deleted": False,
            "reproducibility_files_deleted": False,
            "only_exact_inventory_candidates_may_be_deleted": True,
        },
    }


def verify_retained(records: list[dict[str, Any]]) -> None:
    changed = [record["path"] for record in records if not stat_matches(Path(record["path"]), record)]
    if changed:
        raise RuntimeError(f"보존 자산 변경/누락: {changed[:5]}")


def apply_plan(plan: dict[str, Any], output: Path) -> dict[str, Any]:
    output = output.resolve(strict=False)
    free_before = shutil.disk_usage(Path(plan["release_root"])).free
    state = dict(plan)
    state.update(
        {
            "status": "deletion_in_progress",
            "apply_started_at": now_iso(),
            "deleted": [],
            "current_path": None,
            "drive_free_bytes_before": free_before,
        }
    )
    atomic_write_json(output, state)
    try:
        for record in plan["candidates"]:
            path = Path(record["path"])
            state["current_path"] = str(path)
            atomic_write_json(output, state)
            if not stat_matches(path, record):
                raise RuntimeError(f"삭제 직전 파일 변경/누락: {path}")
            path.unlink()
            state["deleted"].append(
                {"path": str(path), "bytes": int(record["bytes"]), "deleted_at": now_iso()}
            )
            state["current_path"] = None
            atomic_write_json(output, state)
        verify_retained(plan["retained_assets"])
        remaining = [record["path"] for record in plan["candidates"] if Path(record["path"]).exists()]
        if remaining:
            raise RuntimeError(f"정리 후보가 남음: {remaining[:5]}")
        free_after = shutil.disk_usage(Path(plan["release_root"])).free
        state.update(
            {
                "status": "passed",
                "completed_at": now_iso(),
                "current_path": None,
                "drive_free_bytes_after": free_after,
                "drive_free_bytes_delta": free_after - free_before,
                "deleted_files": len(state["deleted"]),
                "deleted_bytes": sum(int(row["bytes"]) for row in state["deleted"]),
            }
        )
        atomic_write_json(output, state)
        return state
    except BaseException as exc:
        state.update({"status": "failed", "failed_at": now_iso(), "error": repr(exc)})
        atomic_write_json(output, state)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--years", nargs="+", required=True)
    parser.add_argument("--expected-files", required=True, type=int)
    parser.add_argument("--expected-bytes", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token", default="")
    args = parser.parse_args()

    years = [str(year) for year in args.years]
    if args.apply:
        validate_approval_scope(
            approval_token=args.approval_token,
            years=years,
            expected_files=args.expected_files,
            expected_bytes=args.expected_bytes,
        )
    plan = build_plan(
        summary_path=args.summary,
        release_root=args.release_root,
        years=years,
        expected_files=args.expected_files,
        expected_bytes=args.expected_bytes,
    )
    if plan["status"] != "dry_run_passed":
        atomic_write_json(args.output.resolve(strict=False), plan)
        print(json.dumps({"status": plan["status"], "blockers": plan["blockers"]}, ensure_ascii=False, indent=2))
        return 2
    if args.apply:
        result = apply_plan(plan, args.output)
    else:
        atomic_write_json(args.output.resolve(strict=False), plan)
        result = plan
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(
        json.dumps(
            {
                "status": result["status"],
                "files": result.get("deleted_files", result["observed"]["files"]),
                "bytes": result.get("deleted_bytes", result["observed"]["bytes"]),
                "output": str(args.output.resolve(strict=False)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
