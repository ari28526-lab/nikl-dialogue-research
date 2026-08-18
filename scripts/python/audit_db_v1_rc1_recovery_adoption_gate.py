#!/usr/bin/env python3
"""Independently audit the closed DB v1 RC1 recovery-adoption gate."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

from praatio import textgrid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from morph_schema import orth_roman_v2
from pipeline_common import atomic_write_json, now_iso, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_rc1_recovery_adoption_gate_20260818"
DEFAULT_REPORT = PROJECT_ROOT / "outputs/reports/AUDIT_db_v1_rc1_recovery_adoption_gate_20260818.json"
BASE_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815"
D1_ROOT = PROJECT_ROOT / "outputs/releases/nikl_dialogue_research_db_v1_recovery_d0_d4_20260815/D1_recovery_ledger"
BUILDER = PROJECT_ROOT / "scripts/python/build_db_v1_rc1_recovery_adoption_gate.py"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def scan(path: Path, wanted: set[str]) -> dict[str, dict]:
    found = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["utt_id"] in wanted:
                if row["utt_id"] in found:
                    raise RuntimeError(f"duplicate ID in ledger: {row['utt_id']}")
                found[row["utt_id"]] = dict(row)
    return found


def audit(args: argparse.Namespace) -> dict:
    root = args.root.resolve()
    manifest = load(root / "MANIFEST.json")
    if manifest["status"] != "gate_closed_pending_researcher_approval":
        raise RuntimeError("manifest gate status differs")
    if manifest["implementation"]["builder_sha256"] != sha256_file(BUILDER):
        raise RuntimeError("builder fingerprint differs")
    for record in manifest["files"]:
        path = root / record["path"]
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"package file differs: {path}")

    status_doc = load(root / "RECOVERY_STATUS_OVERLAY_CANDIDATE.json")
    snapshots_doc = load(root / "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json")
    approval = load(root / "RESEARCHER_APPROVAL_TEMPLATE.json")
    contract = load(root / "ADOPTION_CONTRACT_PENDING.json")
    rows, snapshots = status_doc["rows"], snapshots_doc["rows"]
    ids = {row["utt_id"] for row in rows}
    if len(rows) != 55 or len(ids) != 55 or len(snapshots) != 16:
        raise RuntimeError("candidate counts/uniqueness differ")
    if approval["status"] != "pending_researcher_approval" or approval["approved_by"] is not None:
        raise RuntimeError("approval template is not pending")
    if approval["automatic_approval_performed"]:
        raise RuntimeError("automatic approval flag is unsafe")
    if approval["candidate_hashes"] != {
        "status_overlay_sha256": sha256_file(root / "RECOVERY_STATUS_OVERLAY_CANDIDATE.json"),
        "manual_snapshots_sha256": sha256_file(root / "MANUAL_ANNOTATION_SNAPSHOTS_CANDIDATE.json"),
    }:
        raise RuntimeError("approval candidate hashes differ")
    if contract["status"] != "gate_closed_pending_researcher_approval" or any(contract["safety"].values()):
        raise RuntimeError("adoption contract safety differs")

    sources = Counter(row["outcome_source"] for row in rows)
    if sources != {"D7": 11, "D8": 25, "D9": 3, "D9+D10": 16}:
        raise RuntimeError(f"outcome source counts differ: {dict(sources)}")
    families = Counter(row["proposed_recovery_family"] for row in rows)
    expected_families = {
        "technical_exclusion": 30, "transcript_recovery": 2, "partial_preserved": 6,
        "curated_recovery": 16, "recovered_alignment": 1,
    }
    if families != expected_families:
        raise RuntimeError(f"recovery family counts differ: {dict(families)}")
    if any(row["base_primary_status"] != "post_mfa_technical_exclusion" for row in rows):
        raise RuntimeError("base status differs")
    if any(row["adoption_status"] != "pending_researcher_approval" for row in rows):
        raise RuntimeError("row adoption status differs")

    base = load(BASE_ROOT / "BASE_RELEASE_MANIFEST_2020_2025.json")
    by_year = Counter(str(row["year"]) for row in rows)
    base_found, route_found = {}, {}
    for year in base["scope"]["years"]:
        wanted = {row["utt_id"] for row in rows if str(row["year"]) == year}
        base_path = BASE_ROOT / f"ledgers/{year}_utterance_status.csv.gz"
        if sha256_file(base_path) != base["years"][year]["ledger"]["sha256"]:
            raise RuntimeError(f"base ledger SHA differs: {year}")
        base_found.update(scan(base_path, wanted))
        route_found.update(scan(D1_ROOT / f"{year}_recovery_routing.csv.gz", wanted))
    if set(base_found) != ids or set(route_found) != ids:
        raise RuntimeError("55 IDs are not complete in base/D1 ledgers")
    for row in rows:
        base_row, route_row = base_found[row["utt_id"]], route_found[row["utt_id"]]
        if base_row["session_id"] != row["session_id"] or route_row["recovery_shard_id"] != row["d1_recovery_shard_id"]:
            raise RuntimeError(f"ledger projection differs: {row['utt_id']}")
        evidence = Path(row["evidence_path"])
        if not evidence.is_file() or sha256_file(evidence) != row["evidence_sha256"]:
            raise RuntimeError(f"evidence differs: {row['utt_id']}")

    curated_ids = {row["utt_id"] for row in rows if row["proposed_recovery_family"] == "curated_recovery"}
    if curated_ids != {row["utt_id"] for row in snapshots}:
        raise RuntimeError("curated status/snapshot IDs differ")
    for snapshot in snapshots:
        path = Path(snapshot["active_textgrid_path_candidate"])
        if not path.is_file() or sha256_file(path) != snapshot["active_textgrid_sha256_candidate"]:
            raise RuntimeError(f"curated TextGrid differs: {snapshot['utt_id']}")
        grid = textgrid.openTextgrid(str(path), includeEmptyIntervals=True, reportingMode="error")
        entries = [entry for entry in grid.getTier("words_manual_working").entries if entry.label.strip()]
        transcript = " ".join(entry.label.strip() for entry in entries)
        if transcript != snapshot["final_transcript"] or orth_roman_v2(transcript) != snapshot["orth_roman_v2"]:
            raise RuntimeError(f"curated transcript/Roman differs: {snapshot['utt_id']}")
        projected = [{"xmin": e.start, "xmax": e.end, "label": e.label} for e in grid.getTier("words_manual_working").entries]
        if projected != snapshot["curated_word_intervals"]:
            raise RuntimeError(f"curated intervals differ: {snapshot['utt_id']}")
        if snapshot["phone_layer_status"] != "d9_reference_only_not_adopted":
            raise RuntimeError(f"unsafe phone status: {snapshot['utt_id']}")
        if snapshot["morph_enrichment_status"] != "pending_rebuild_from_curated_transcript":
            raise RuntimeError(f"unsafe morphology status: {snapshot['utt_id']}")

    report = {
        "schema_version": "research_db_v1_rc1_recovery_adoption_gate_independent_audit.v1",
        "status": "passed_gate_closed_pending_researcher_approval",
        "recorded_at": now_iso(),
        "counts": {"status_rows": 55, "manual_snapshots": 16, "by_year": dict(sorted(by_year.items()))},
        "family_counts": dict(sorted(families.items())),
        "manifest_sha256": sha256_file(root / "MANIFEST.json"),
        "safety": contract["safety"],
    }
    atomic_write_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    audit(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
