#!/usr/bin/env python3
"""Audit whether local reference-tree files are represented in literature ledgers.

Registered paths are checked against SOURCE_INVENTORY and SOURCE_INSTANCES.
Unregistered paths are hashed and classified without editing any canonical file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_unique(path: Path) -> str:
    lowered_parts = [part.casefold() for part in path.parts]
    stem = path.stem.casefold()
    suffix = path.suffix.casefold()
    if suffix in {".m4a", ".mp3", ".wav", ".flac"}:
        return "derived_audio_or_summary"
    if suffix in {".exe", ".dll", ".bat", ".cmd"}:
        return "supplemental_software"
    if "supplement" in lowered_parts or "supplementalfiles" in lowered_parts:
        return "supplemental_data"
    if "ocr" in stem:
        return "ocr_variant_candidate"
    return "unregistered_work_candidate"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--literature-root", type=Path, default=Path("00_참고문헌"))
    parser.add_argument(
        "--canonical-root",
        type=Path,
        default=Path("work/literature_evidence_seven_phenomena_20260822"),
    )
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    args = parser.parse_args()

    for output in (args.output_json, args.output_csv):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {output}")

    project_root = args.project_root.resolve()
    literature_root = (project_root / args.literature_root).resolve()
    canonical_root = (project_root / args.canonical_root).resolve()
    sources = read_jsonl(canonical_root / "01_inventory/SOURCE_INVENTORY.jsonl")
    instances = read_jsonl(canonical_root / "01_inventory/SOURCE_INSTANCES.jsonl")
    registered = sources + instances

    registered_paths: set[Path] = set()
    sha_to_ids: dict[str, list[str]] = {}
    for row in registered:
        relative = row.get("relative_path")
        if relative:
            registered_paths.add((project_root / str(relative)).resolve())
        digest = str(row.get("sha256", ""))
        record_id = str(row.get("source_id") or row.get("instance_id") or "")
        if digest:
            sha_to_ids.setdefault(digest, []).append(record_id)

    files = sorted(
        path
        for path in literature_root.rglob("*")
        if path.is_file() and not {".git", ".agents"}.intersection(path.parts)
    )
    unregistered = [path for path in files if path.resolve() not in registered_paths]
    rows: list[dict[str, Any]] = []
    for path in unregistered:
        digest = sha256(path)
        if digest in sha_to_ids:
            status = "exact_duplicate_registered"
            registered_ids = ",".join(sha_to_ids[digest])
        else:
            status = classify_unique(path.relative_to(literature_root))
            registered_ids = ""
        rows.append(
            {
                "status": status,
                "relative_path": path.relative_to(project_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest,
                "registered_ids": registered_ids,
            }
        )

    status_counts = Counter(str(row["status"]) for row in rows)
    report = {
        "schema_version": "literature_tree_coverage_audit.v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "passed": status_counts.get("unregistered_work_candidate", 0) == 0,
        "status": (
            "passed_no_unregistered_scholarly_work_candidate"
            if status_counts.get("unregistered_work_candidate", 0) == 0
            else "needs_human_review_unregistered_work_candidates"
        ),
        "scope": "local_00_reference_tree_only_no_dropbox_completeness_claim",
        "counts": {
            "tree_files": len(files),
            "registered_source_rows": len(sources),
            "registered_instance_rows": len(instances),
            "registered_physical_paths": len(registered_paths),
            "unregistered_paths": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
        },
        "limitations": [
            "Exact SHA detects byte-identical copies but not different editions or scans.",
            "OCR, audio, software, and supplemental data classifications are path and extension heuristics.",
            "Dropbox and newly published literature require separate searches.",
        ],
        "unregistered_rows": rows,
    }

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["status", "relative_path", "bytes", "sha256", "registered_ids"],
        )
        writer.writeheader()
        writer.writerows(rows)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
