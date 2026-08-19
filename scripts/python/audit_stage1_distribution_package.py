#!/usr/bin/env python3
"""Independently audit a materialized stage-1 distribution package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FORBIDDEN_PARTS = (
    "stage2_",
    "n_insertion_v1_",
    "outputs/candidates",
    "outputs/reviews",
    "outputs/approvals",
    "docs/archive",
    "repo_snapshot_",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(package_root: Path) -> dict[str, object]:
    package_root = package_root.resolve()
    manifest_path = package_root / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {record["relpath"]: record for record in manifest["files"]}
    actual = {
        path.relative_to(package_root).as_posix(): path
        for path in package_root.rglob("*")
        if path.is_file() and path != manifest_path
    }

    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    mismatches: list[str] = []
    forbidden: list[str] = []
    for relative, path in actual.items():
        lowered = relative.lower()
        if any(part in lowered for part in FORBIDDEN_PARTS):
            forbidden.append(relative)
        record = expected.get(relative)
        if record is None:
            continue
        if path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
            mismatches.append(relative)

    checks = {
        "manifest_stage2_false": manifest.get("stage2_payload_included") is False,
        "manifest_repo_snapshot_false": manifest.get("repository_snapshot_included") is False,
        "manifest_source_match_all_true": all(
            record.get("source_match") is True for record in manifest["files"]
        ),
        "file_count_matches": manifest.get("file_count") == len(expected) == len(actual),
        "missing_zero": not missing,
        "unexpected_zero": not unexpected,
        "sha_mismatch_zero": not mismatches,
        "forbidden_zero": not forbidden,
        "release_scope_present": "outputs/releases/stage1_infrastructure_distribution_20260819/RELEASE_SCOPE.json" in actual,
        "d_handoff_guide_present": "docs/releases/20260818_six_year_infrastructure_closeout/DISTRIBUTION_D_DRIVE.md" in actual,
        "code_only_guide_present": "docs/releases/20260818_six_year_infrastructure_closeout/DISTRIBUTION_CODE_ONLY.md" in actual,
        "nontechnical_html_present": "outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html" in actual,
        "nontechnical_html_audit_present": "outputs/reports/AUDIT_stage1_distribution_guide_for_nontechnical_readers_20260819.json" in actual,
    }
    passed = all(checks.values())
    return {
        "schema_version": "stage1_distribution_package_audit.v1",
        "status": "passed" if passed else "failed",
        "package_root": str(package_root),
        "checks": checks,
        "counts": {
            "manifest_files": len(expected),
            "actual_files_excluding_manifest": len(actual),
            "missing": len(missing),
            "unexpected": len(unexpected),
            "sha_mismatches": len(mismatches),
            "forbidden": len(forbidden),
        },
        "details": {
            "missing": missing,
            "unexpected": unexpected,
            "sha_mismatches": mismatches,
            "forbidden": forbidden,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit(args.package_root)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
