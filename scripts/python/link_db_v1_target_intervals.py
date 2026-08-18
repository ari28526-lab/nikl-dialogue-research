"""Link target-manifest occurrences to existing TextGrid word intervals.

This is a derived, read-only context-span linker.  It does not claim a narrow
phonological boundary, judge realization, or modify any TextGrid.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import unicodedata
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from praatio import textgrid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_ROOT = (
    PROJECT_ROOT / "outputs" / "pilots" / "db_v1_target_manifest_pilot_20260818"
)
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT / "outputs" / "pilots" / "db_v1_target_interval_link_pilot_20260818"
)
APPENDED_FIELDS = [
    "target_word_indices_json",
    "target_word_labels_json",
    "textgrid_words_tier_count",
    "active_textgrid_sha256",
    "timing_method",
    "timing_notes",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_eojeol(value: str) -> str:
    """Normalize only outer punctuation omitted by MFA's word labels."""

    value = unicodedata.normalize("NFC", value.strip())
    while value and unicodedata.category(value[0]).startswith("P"):
        value = value[1:]
    while value and unicodedata.category(value[-1]).startswith("P"):
        value = value[:-1]
    return value


def nonempty_words(path: Path) -> list[tuple[float, float, str]]:
    grid = textgrid.openTextgrid(
        str(path), includeEmptyIntervals=True, reportingMode="error"
    )
    if "words" not in grid.tierNames:
        raise RuntimeError(f"words tier missing: {path}")
    return [
        (float(entry.start), float(entry.end), entry.label.strip())
        for entry in grid.getTier("words").entries
        if entry.label.strip()
    ]


def validate_word_sequence(
    active_form: str, words: Iterable[tuple[float, float, str]]
) -> list[tuple[float, float, str]]:
    words = list(words)
    tokens = active_form.split()
    labels = [item[2] for item in words]
    if len(tokens) != len(labels):
        raise RuntimeError(
            f"active/TextGrid eojeol count mismatch: {len(tokens)} != {len(labels)}"
        )
    if [normalize_eojeol(x) for x in tokens] != [normalize_eojeol(x) for x in labels]:
        raise RuntimeError("active/TextGrid eojeol sequence mismatch")
    return words


def resolve_boundary_span(
    words: list[tuple[float, float, str]], evidence: dict[str, Any]
) -> dict[str, Any]:
    left = int(evidence["left_eojeol_idx"])
    right = int(evidence["right_eojeol_idx"])
    if left < 1 or right < 1 or left > len(words) or right > len(words):
        raise RuntimeError(
            f"morph eojeol index outside words tier: left={left} right={right} "
            f"words={len(words)}"
        )
    first, last = min(left, right), max(left, right)
    selected = words[first - 1 : last]
    indices = list(range(first, last + 1))
    scope = str(evidence.get("boundary_scope") or "")
    if left == right:
        method = "morph_eojeol_index_to_single_word_interval"
        status = "linked_single_eojeol_context_span"
    else:
        method = "morph_eojeol_indices_to_adjacent_word_context_span"
        status = "linked_inter_eojeol_context_span"
    return {
        "target_xmin": f"{selected[0][0]:.9f}",
        "target_xmax": f"{selected[-1][1]:.9f}",
        "timing_status": status,
        "target_word_indices_json": json.dumps(indices, ensure_ascii=False),
        "target_word_labels_json": json.dumps(
            [item[2] for item in selected], ensure_ascii=False
        ),
        "timing_method": method,
        "timing_notes": (
            f"context span from morph boundary scope={scope}; "
            "not a narrow phonological boundary"
        ),
    }


def link_row(row: dict[str, str]) -> dict[str, str]:
    linked = dict(row)
    linked.update({field: "" for field in APPENDED_FIELDS})
    role = row["query_role"]
    if role == "infrastructure_validation":
        linked["timing_status"] = "not_applicable_infrastructure_query"
        linked["timing_method"] = "none"
        linked["timing_notes"] = "active precedence smoke test; no target occurrence"
        return linked
    if role != "candidate_environment_pilot":
        linked["timing_status"] = "pending_unsupported_query_role"
        linked["timing_notes"] = f"unsupported query role: {role}"
        return linked
    path_text = row.get("active_textgrid_path", "").strip()
    if not path_text:
        linked["timing_status"] = "pending_textgrid_asset_unavailable"
        linked["timing_notes"] = "candidate retained as metadata-only"
        return linked
    path = Path(path_text)
    try:
        words = validate_word_sequence(row["active_form"], nonempty_words(path))
        evidence = json.loads(row["match_evidence_json"])
        timing = resolve_boundary_span(words, evidence)
    except Exception as exc:
        linked["timing_status"] = "pending_textgrid_word_mapping_review"
        linked["timing_notes"] = f"{type(exc).__name__}: {exc}"
        return linked
    linked.update({key: str(value) for key, value in timing.items()})
    linked["textgrid_words_tier_count"] = str(len(words))
    linked["active_textgrid_sha256"] = sha256_file(path)
    return linked


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(input_root: Path, output_root: Path) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"output exists: {output_root}")
    source_path = input_root / "TARGET_CANDIDATES.csv"
    with source_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        source_fields = list(reader.fieldnames or ())
        source_rows = list(reader)
    if not source_rows:
        raise RuntimeError("target candidate input is empty")
    fields = source_fields + [field for field in APPENDED_FIELDS if field not in source_fields]
    linked_rows = [link_row(row) for row in source_rows]
    partial = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    partial.mkdir(parents=True)
    try:
        linked_path = partial / "TARGET_CANDIDATES_WITH_CONTEXT_TIMES.csv"
        write_csv(linked_path, fields, linked_rows)
        status_counts = Counter(row["timing_status"] for row in linked_rows)
        manifest = {
            "schema_version": "nikl_dialogue_target_interval_link_build.v1",
            "status": "pilot_context_spans_linked_no_realization_judgement",
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_candidate_sha256": sha256_file(source_path),
            "counts": {
                "rows": len(linked_rows),
                "timing_status": dict(sorted(status_counts.items())),
            },
            "output": {
                "path": linked_path.name,
                "bytes": linked_path.stat().st_size,
                "sha256": sha256_file(linked_path),
            },
            "safety": {
                "context_span_only": True,
                "narrow_phonological_boundary_claimed": False,
                "realization_judgement_performed": False,
                "textgrid_modified": False,
                "mfa_run": False,
            },
        }
        (partial / "INTERVAL_LINK_BUILD.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (partial / "README.md").write_text(
            "# DB v1 target interval-link pilot\n\n"
            "Times are TextGrid word-context spans derived from morph eojeol indices. "
            "They are not narrow phonological boundaries or realization judgements.\n",
            encoding="utf-8",
        )
        os.replace(partial, output_root)
    except Exception:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        result = build(args.input_root.resolve(), args.output_root.resolve())
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
