"""Independently audit a target occurrence to TextGrid context-span pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from praatio import textgrid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "outputs/pilots/db_v1_target_manifest_pilot_20260818"
DEFAULT_LINK_ROOT = PROJECT_ROOT / "outputs/pilots/db_v1_target_interval_link_pilot_20260818"
DEFAULT_REPORT = PROJECT_ROOT / "outputs/reports/AUDIT_db_v1_target_interval_link_pilot_20260818.json"
ALLOWED_CHANGED = {"target_xmin", "target_xmax", "timing_status"}
APPENDED = {
    "target_word_indices_json", "target_word_labels_json",
    "textgrid_words_tier_count", "active_textgrid_sha256",
    "timing_method", "timing_notes",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def norm(value: str) -> str:
    value = unicodedata.normalize("NFC", value.strip())
    while value and unicodedata.category(value[0]).startswith("P"):
        value = value[1:]
    while value and unicodedata.category(value[-1]).startswith("P"):
        value = value[:-1]
    return value


def audit(source_root: Path, link_root: Path) -> dict[str, Any]:
    source_fields, source_rows = read_csv(source_root / "TARGET_CANDIDATES.csv")
    linked_fields, linked_rows = read_csv(link_root / "TARGET_CANDIDATES_WITH_CONTEXT_TIMES.csv")
    manifest_path = link_root / "INTERVAL_LINK_BUILD.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(source_rows) != len(linked_rows):
        raise RuntimeError("source/linked row count mismatch")
    if set(linked_fields) != set(source_fields) | APPENDED:
        raise RuntimeError("linked field contract mismatch")
    statuses: Counter[str] = Counter()
    linked_count = 0
    for source, linked in zip(source_rows, linked_rows):
        if source["target_occurrence_id"] != linked["target_occurrence_id"]:
            raise RuntimeError("target occurrence order or identity changed")
        for field in source_fields:
            if field in ALLOWED_CHANGED:
                continue
            if source[field] != linked[field]:
                raise RuntimeError(f"source field changed: {field}")
        status = linked["timing_status"]
        statuses[status] += 1
        if source["query_role"] == "infrastructure_validation":
            if status != "not_applicable_infrastructure_query":
                raise RuntimeError("infrastructure query received target timing")
            if linked["target_xmin"] or linked["target_xmax"]:
                raise RuntimeError("infrastructure timing must be blank")
            continue
        if not source["active_textgrid_path"]:
            if status != "pending_textgrid_asset_unavailable":
                raise RuntimeError("missing asset candidate not retained explicitly")
            continue
        if not status.startswith("linked_"):
            continue
        path = Path(source["active_textgrid_path"])
        if sha256_file(path) != linked["active_textgrid_sha256"]:
            raise RuntimeError(f"TextGrid SHA mismatch: {source['utt_id']}")
        grid = textgrid.openTextgrid(str(path), includeEmptyIntervals=True, reportingMode="error")
        words = [
            (float(entry.start), float(entry.end), entry.label.strip())
            for entry in grid.getTier("words").entries if entry.label.strip()
        ]
        if [norm(x) for x in source["active_form"].split()] != [norm(x[2]) for x in words]:
            raise RuntimeError(f"active/TextGrid sequence mismatch: {source['utt_id']}")
        evidence = json.loads(source["match_evidence_json"])
        left, right = int(evidence["left_eojeol_idx"]), int(evidence["right_eojeol_idx"])
        first, last = min(left, right), max(left, right)
        selected = words[first - 1:last]
        if json.loads(linked["target_word_indices_json"]) != list(range(first, last + 1)):
            raise RuntimeError("linked word indices mismatch")
        if json.loads(linked["target_word_labels_json"]) != [x[2] for x in selected]:
            raise RuntimeError("linked word labels mismatch")
        if abs(float(linked["target_xmin"]) - selected[0][0]) > 1e-9:
            raise RuntimeError("target xmin mismatch")
        if abs(float(linked["target_xmax"]) - selected[-1][1]) > 1e-9:
            raise RuntimeError("target xmax mismatch")
        linked_count += 1
    if dict(sorted(statuses.items())) != manifest["counts"]["timing_status"]:
        raise RuntimeError("timing status counts disagree with manifest")
    if linked_count == 0:
        raise RuntimeError("pilot linked no context spans")
    if manifest["safety"] != {
        "context_span_only": True,
        "narrow_phonological_boundary_claimed": False,
        "realization_judgement_performed": False,
        "textgrid_modified": False,
        "mfa_run": False,
    }:
        raise RuntimeError("safety contract changed")
    return {
        "schema_version": "nikl_dialogue_target_interval_link_audit.v1",
        "status": "passed_context_span_link_no_realization_judgement",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_sha256": sha256_file(manifest_path),
        "counts": {
            "rows": len(linked_rows),
            "linked_context_spans": linked_count,
            "timing_status": dict(sorted(statuses.items())),
        },
        "invariants": {
            "source_rows_preserved": True,
            "textgrid_sha_verified": True,
            "morph_eojeol_indices_recomputed": True,
            "context_span_not_narrow_boundary": True,
            "realization_not_judged": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--link-root", type=Path, default=DEFAULT_LINK_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        result = audit(args.source_root.resolve(), args.link_root.resolve())
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
