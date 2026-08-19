#!/usr/bin/env python3
"""Build the stage-1-only handoff package without touching frozen assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PACKAGE_NAME = "stage1_infrastructure_distribution_20260819"

SINGLE_FILES = (
    "RELEASE.md",
    "README.md",
    "docs/README.md",
    "docs/ASSETS_LEDGER.md",
    "docs/RUNBOOK_production_2020_2025.md",
    "docs/decisions/DECISION_stage1_data_infrastructure_closure_20260818.md",
    "outputs/reports/STAGE_STATUS_20260818.md",
    "outputs/reports/SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json",
    "outputs/reports/AUDIT_six_year_infrastructure_closeout_20260818.json",
    "outputs/reports/six_year_infrastructure_report_20260818.html",
    "qmd/stage1_distribution_guide_for_nontechnical_readers_20260819.qmd",
    "outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html",
    "outputs/reports/AUDIT_stage1_distribution_guide_for_nontechnical_readers_20260819.json",
    "outputs/releases/stage1_infrastructure_distribution_20260819/README.md",
    "outputs/releases/stage1_infrastructure_distribution_20260819/README_PACKAGE.md",
    "outputs/releases/stage1_infrastructure_distribution_20260819/RELEASE_SCOPE.json",
)

TREE_ROOTS = (
    "docs/releases/20260818_six_year_infrastructure_closeout",
    "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815",
    "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818",
    "outputs/releases/nikl_dialogue_research_db_v1_active_view_contract_v1_20260818",
)

FORBIDDEN_PARTS = (
    "stage2_",
    "n_insertion_v1_",
    "outputs/candidates",
    "outputs/reviews",
    "outputs/approvals",
    "docs/archive",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def iter_sources(root: Path) -> list[Path]:
    files = [root / relative for relative in SINGLE_FILES]
    for relative in TREE_ROOTS:
        files.extend(path for path in (root / relative).rglob("*") if path.is_file())
    unique = sorted(set(files), key=lambda path: path.relative_to(root).as_posix())
    missing = [path for path in unique if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing package sources: {missing}")
    for path in unique:
        relative = path.relative_to(root).as_posix().lower()
        if any(part in relative for part in FORBIDDEN_PARTS):
            raise ValueError(f"Stage-2 or private payload is forbidden: {relative}")
    return unique


def git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def build(output_parent: Path) -> Path:
    root = repo_root()
    output_parent = output_parent.resolve()
    destination = output_parent / PACKAGE_NAME
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing package: {destination}")
    if output_parent == destination or destination.parent != output_parent:
        raise ValueError("Unexpected output path resolution")

    sources = iter_sources(root)
    destination.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []
    try:
        for source in sources:
            relative = source.relative_to(root)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            source_sha = sha256_file(source)
            target_sha = sha256_file(target)
            if source_sha != target_sha:
                raise OSError(f"SHA mismatch after copy: {relative}")
            records.append(
                {
                    "relpath": relative.as_posix(),
                    "bytes": target.stat().st_size,
                    "sha256": target_sha,
                    "source_match": True,
                }
            )

        package_readme_source = (
            root
            / "outputs/releases/stage1_infrastructure_distribution_20260819/README_PACKAGE.md"
        )
        package_readme_target = destination / "README_PACKAGE.md"
        shutil.copy2(package_readme_source, package_readme_target)
        records.append(
            {
                "relpath": "README_PACKAGE.md",
                "bytes": package_readme_target.stat().st_size,
                "sha256": sha256_file(package_readme_target),
                "source_match": sha256_file(package_readme_source)
                == sha256_file(package_readme_target),
            }
        )

        manifest = {
            "schema_version": "stage1_distribution_package.v1",
            "package_name": PACKAGE_NAME,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_git_head": git_head(root),
            "scope": "stage1_mechanical_analysis_and_mfa_infrastructure_only",
            "stage2_payload_included": False,
            "repository_snapshot_included": False,
            "manifest_covers_all_files_except_itself": True,
            "file_count": len(records),
            "total_bytes": sum(int(record["bytes"]) for record in records),
            "files": sorted(records, key=lambda record: str(record["relpath"])),
        }
        manifest_path = destination / "PACKAGE_MANIFEST.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def refresh(output_parent: Path) -> Path:
    root = repo_root()
    destination = output_parent.resolve() / PACKAGE_NAME
    manifest_path = destination / "PACKAGE_MANIFEST.json"
    if not destination.is_dir() or not manifest_path.is_file():
        raise FileNotFoundError(f"Existing package is not refreshable: {destination}")
    current = json.loads(manifest_path.read_text(encoding="utf-8"))
    if current.get("package_name") != PACKAGE_NAME:
        raise ValueError(f"Unexpected package identity: {destination}")

    sources = iter_sources(root)
    expected_relpaths = {path.relative_to(root).as_posix() for path in sources}
    expected_relpaths.add("README_PACKAGE.md")
    actual_relpaths = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and path != manifest_path
    }
    unexpected = sorted(actual_relpaths - expected_relpaths)
    if unexpected:
        raise ValueError(f"Refusing to refresh package with unexpected files: {unexpected}")

    records: list[dict[str, object]] = []
    for source in sources:
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest = sha256_file(target)
        if sha256_file(source) != digest:
            raise OSError(f"SHA mismatch after refresh: {relative}")
        records.append(
            {
                "relpath": relative.as_posix(),
                "bytes": target.stat().st_size,
                "sha256": digest,
                "source_match": True,
            }
        )

    package_readme_source = (
        root
        / "outputs/releases/stage1_infrastructure_distribution_20260819/README_PACKAGE.md"
    )
    package_readme_target = destination / "README_PACKAGE.md"
    shutil.copy2(package_readme_source, package_readme_target)
    records.append(
        {
            "relpath": "README_PACKAGE.md",
            "bytes": package_readme_target.stat().st_size,
            "sha256": sha256_file(package_readme_target),
            "source_match": sha256_file(package_readme_source)
            == sha256_file(package_readme_target),
        }
    )

    current["refreshed_utc"] = datetime.now(timezone.utc).isoformat()
    current["file_count"] = len(records)
    current["total_bytes"] = sum(int(record["bytes"]) for record in records)
    current["files"] = sorted(records, key=lambda record: str(record["relpath"]))
    manifest_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-parent",
        type=Path,
        required=True,
        help="Existing parent directory; the fixed package directory is created below it.",
    )
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Refresh only the fixed package after verifying its identity and contents.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.output_parent.is_dir():
        raise NotADirectoryError(args.output_parent)
    print(refresh(args.output_parent) if args.refresh_existing else build(args.output_parent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
