"""Audit a DB v1 target-manifest pilot without making research judgements."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from build_db_v1_target_manifest import row_matches


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PILOT_ROOT = (
    PROJECT_ROOT / "outputs" / "pilots" / "db_v1_target_manifest_pilot_20260818"
)
DEFAULT_ACTIVE_VIEW = (
    PROJECT_ROOT
    / "outputs"
    / "releases"
    / "nikl_dialogue_research_db_v1_active_view_contract_v1_20260818"
    / "ACTIVE_RECOVERY_EXCEPTIONS.csv"
)
DEFAULT_REPORT = (
    PROJECT_ROOT / "outputs" / "reports" / "AUDIT_db_v1_target_manifest_pilot_20260818.json"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def audit(root: Path, active_view_path: Path) -> dict[str, Any]:
    manifest_path = root / "TARGET_MANIFEST_BUILD.json"
    query_path = root / "QUERY_SET.json"
    candidate_path = root / "TARGET_CANDIDATES.csv"
    manifest = load_json(manifest_path)
    query_set = load_json(query_path)
    candidates = read_csv(candidate_path)
    active_rows = read_csv(active_view_path)
    active = {(int(row["year"]), row["utt_id"]): row for row in active_rows}
    queries = {query["query_id"]: query for query in query_set["queries"]}

    for record in manifest["files"]:
        path = root / record["path"]
        if path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"declared file mismatch: {record['path']}")
    occurrence_ids = [row["target_occurrence_id"] for row in candidates]
    if len(occurrence_ids) != len(set(occurrence_ids)):
        raise RuntimeError("duplicate target occurrence ID")
    curated_rows = 0
    for row in candidates:
        query = queries[row["query_id"]]
        evidence = json.loads(row["match_evidence_json"])
        if not row_matches(evidence, query["conditions"]):
            raise RuntimeError(f"query evidence no longer matches: {row['target_occurrence_id']}")
        if row["target_xmin"] or row["target_xmax"]:
            raise RuntimeError("pilot must not claim target timing")
        if row["timing_status"] != "pending_textgrid_interval_link":
            raise RuntimeError("unexpected timing status")
        exception = active.get((int(row["year"]), row["utt_id"]))
        expected_source = (
            "curated"
            if exception and exception["active_annotation_source"] == "curated"
            else "base"
        )
        if row["active_annotation_source"] != expected_source:
            raise RuntimeError(f"active precedence mismatch: {row['utt_id']}")
        if expected_source == "curated":
            curated_rows += 1
            if row["active_form"] != exception["active_transcript"]:
                raise RuntimeError(f"curated transcript mismatch: {row['utt_id']}")
            if row["active_textgrid_path"] != exception["active_textgrid_path"]:
                raise RuntimeError(f"curated TextGrid mismatch: {row['utt_id']}")
        flags = set(json.loads(row["quality_flags_json"]))
        wav_exists = Path(row["wav_path"]).is_file()
        textgrid_exists = bool(row["active_textgrid_path"]) and Path(
            row["active_textgrid_path"]
        ).is_file()
        if row["inclusion_status"] == "candidate_ready_for_manual_realization_review":
            if not wav_exists or not textgrid_exists:
                raise RuntimeError(
                    f"ready candidate has missing asset: {row['target_occurrence_id']}"
                )
        elif row["inclusion_status"] == "candidate_metadata_only_pending_alignment_or_recovery":
            if wav_exists and textgrid_exists:
                raise RuntimeError(
                    f"metadata-only candidate actually has both assets: {row['target_occurrence_id']}"
                )
            if not wav_exists and "wav_unavailable_in_r3_corpus" not in flags:
                raise RuntimeError(f"missing WAV flag absent: {row['utt_id']}")
            if not textgrid_exists and not {
                "active_textgrid_unavailable",
                "active_textgrid_path_missing",
            } & flags:
                raise RuntimeError(f"missing TextGrid flag absent: {row['utt_id']}")
        else:
            raise RuntimeError(f"unknown inclusion status: {row['inclusion_status']}")

    if len(candidates) != manifest["counts"]["candidate_rows"]:
        raise RuntimeError("candidate count mismatch")
    if curated_rows != manifest["counts"]["curated_rows"]:
        raise RuntimeError("curated count mismatch")
    if curated_rows < 2:
        raise RuntimeError("overlay precedence pilot did not exercise curated rows")
    return {
        "schema_version": "nikl_dialogue_target_manifest_audit.v1",
        "status": "passed_pilot_query_and_active_precedence",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_sha256": sha256_file(manifest_path),
        "counts": {
            "candidate_rows": len(candidates),
            "unique_occurrences": len(set(occurrence_ids)),
            "curated_rows": curated_rows,
            "query_rows": {
                query_id: sum(row["query_id"] == query_id for row in candidates)
                for query_id in queries
            },
        },
        "invariants": {
            "all_evidence_re_matches_query": True,
            "active_precedence_verified": True,
            "ready_candidate_assets_exist": True,
            "missing_assets_explicitly_flagged": True,
            "target_timing_not_claimed": True,
            "realization_not_judged": True,
            "source_assets_not_modified": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", type=Path, default=DEFAULT_PILOT_ROOT)
    parser.add_argument("--active-view", type=Path, default=DEFAULT_ACTIVE_VIEW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = audit(args.pilot_root.resolve(), args.active_view.resolve())
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
