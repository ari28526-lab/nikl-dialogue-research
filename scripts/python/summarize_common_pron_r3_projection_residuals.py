"""Summarize audited r3 projection candidates and unresolved evidence routes."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_projection_candidates import (  # noqa: E402
    SCHEMA_VERSION,
    SOURCE_PROJECTION_FIELDS,
    TARGET_PROJECTION_FIELDS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_SCHEMA = "common_pron_r3_projection_residual_summary.v1"
TARGET_FIELDS = (
    "projection_status",
    "diagnostic_layer",
    "diagnostic_class",
    "edit_signature",
    "target_count",
    "source_type_count",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
    "example_targets_json",
)
SOURCE_FIELDS = (
    "source_projection_gate_class",
    "original_selection_status",
    "target_projection_status",
    "dictionary_rule_agreement",
    "target_count",
    "source_type_count",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
    "example_tokens_json",
    "example_targets_json",
)
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")
    return path


def new_record() -> dict[str, object]:
    return {
        "targets": set(),
        "source_type_count": 0,
        "total_occurrences": 0,
        **{f"count_{year}": 0 for year in YEARS},
        "example_targets": [],
        "example_tokens": [],
    }


def add_counts(record: dict[str, object], row: dict[str, str], *, source_types: int) -> None:
    record["source_type_count"] += source_types
    record["total_occurrences"] += int(row["total_occurrences"])
    for year in YEARS:
        record[f"count_{year}"] += int(row[f"count_{year}"])


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    with temp.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def summarize(
    *,
    manifest_path: Path,
    target_summary: Path,
    target_handoff: Path,
    source_summary: Path,
    report_path: Path,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("projection manifest is not completed")
    target_path = verify(manifest["outputs"]["target_projection_candidates"], label="target projection")
    source_path = verify(manifest["outputs"]["source_projection_candidates"], label="source projection")

    target_groups: dict[tuple[str, str, str, str], dict[str, object]] = defaultdict(new_record)
    ready_targets = ready_occurrences = unresolved_targets = unresolved_occurrences = 0
    with gzip.open(target_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_PROJECTION_FIELDS:
            raise RuntimeError("target projection columns differ")
        for row in reader:
            status = row["projection_status"]
            count = int(row["projection_candidate_count"])
            occurrences = int(row["total_occurrences"])
            if count:
                ready_targets += 1
                ready_occurrences += occurrences
            else:
                unresolved_targets += 1
                unresolved_occurrences += occurrences
                key = (
                    status,
                    row["diagnostic_layer"],
                    row["diagnostic_class"],
                    row["edit_signature"],
                )
                record = target_groups[key]
                record["targets"].add(row["target_hangul"])
                add_counts(record, row, source_types=int(row["source_type_count"]))
                if len(record["example_targets"]) < 5:
                    record["example_targets"].append(row["target_hangul"])

    target_rows: list[dict[str, object]] = []
    for key, record in target_groups.items():
        target_rows.append(
            {
                **dict(zip(TARGET_FIELDS[:4], key, strict=True)),
                "target_count": len(record["targets"]),
                "source_type_count": record["source_type_count"],
                "total_occurrences": record["total_occurrences"],
                **{f"count_{year}": record[f"count_{year}"] for year in YEARS},
                "example_targets_json": json.dumps(record["example_targets"], ensure_ascii=False),
            }
        )
    target_rows.sort(key=lambda row: (-int(row["total_occurrences"]), str(row["projection_status"]), str(row["edit_signature"])))
    selected_indices: set[int] = set()
    cumulative = 0
    for index, row in enumerate(target_rows):
        selected_indices.add(index)
        cumulative += int(row["total_occurrences"])
        if cumulative / unresolved_occurrences >= 0.95:
            break
    represented: set[tuple[str, str]] = set()
    for index, row in enumerate(target_rows):
        key = (str(row["projection_status"]), str(row["diagnostic_class"]))
        if key not in represented:
            selected_indices.add(index)
            represented.add(key)
    target_handoff_rows = [target_rows[index] for index in sorted(selected_indices)]
    handoff_occurrences = sum(int(row["total_occurrences"]) for row in target_handoff_rows)

    source_groups: dict[tuple[str, str, str, str], dict[str, object]] = defaultdict(new_record)
    ready_sources = ready_source_occurrences = 0
    with gzip.open(source_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SOURCE_PROJECTION_FIELDS:
            raise RuntimeError("source projection columns differ")
        for row in reader:
            route = row["source_projection_gate_class"]
            if route == "candidate_projection_dictionary_agree":
                ready_sources += 1
                ready_source_occurrences += int(row["total_occurrences"])
            key = (
                route,
                row["original_selection_status"],
                row["target_projection_status"],
                row["dictionary_rule_agreement"],
            )
            record = source_groups[key]
            record["targets"].add(row["target_hangul"])
            add_counts(record, row, source_types=1)
            if len(record["example_tokens"]) < 5:
                record["example_tokens"].append(row["token"])
                record["example_targets"].append(row["target_hangul"])

    source_rows: list[dict[str, object]] = []
    for key, record in source_groups.items():
        source_rows.append(
            {
                **dict(zip(SOURCE_FIELDS[:4], key, strict=True)),
                "target_count": len(record["targets"]),
                "source_type_count": record["source_type_count"],
                "total_occurrences": record["total_occurrences"],
                **{f"count_{year}": record[f"count_{year}"] for year in YEARS},
                "example_tokens_json": json.dumps(record["example_tokens"], ensure_ascii=False),
                "example_targets_json": json.dumps(record["example_targets"], ensure_ascii=False),
            }
        )
    source_rows.sort(key=lambda row: (-int(row["total_occurrences"]), str(row["source_projection_gate_class"])))

    write_csv(target_summary, TARGET_FIELDS, target_rows)
    write_csv(target_handoff, TARGET_FIELDS, target_handoff_rows)
    write_csv(source_summary, SOURCE_FIELDS, source_rows)
    total_targets = ready_targets + unresolved_targets
    total_occurrences = ready_occurrences + unresolved_occurrences
    report: dict[str, object] = {
        "schema_version": REPORT_SCHEMA,
        "status": "success_summary_not_selection",
        "recorded_at": now_iso(),
        "headline": {
            "target_candidate_ready": ready_targets,
            "target_candidate_ready_percent": round(100 * ready_targets / total_targets, 3),
            "target_unresolved": unresolved_targets,
            "target_unresolved_percent": round(100 * unresolved_targets / total_targets, 3),
            "occurrence_candidate_ready": ready_occurrences,
            "occurrence_candidate_ready_percent": round(100 * ready_occurrences / total_occurrences, 3),
            "occurrence_unresolved": unresolved_occurrences,
            "occurrence_unresolved_percent": round(100 * unresolved_occurrences / total_occurrences, 3),
            "source_dictionary_agree_candidate_types": ready_sources,
            "source_dictionary_agree_candidate_occurrences": ready_source_occurrences,
        },
        "counts": {
            "target_residual_pattern_rows": len(target_rows),
            "target_residual_handoff_rows": len(target_handoff_rows),
            "target_residual_handoff_occurrences": handoff_occurrences,
            "target_residual_handoff_coverage_percent": round(
                100 * handoff_occurrences / unresolved_occurrences, 3
            ),
            "source_route_pattern_rows": len(source_rows),
        },
        "scope": {
            "summary_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
        },
        "evidence": {
            "projection_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "target_residual_patterns": file_fingerprint(target_summary, with_sha256=True),
            "target_residual_handoff": file_fingerprint(target_handoff, with_sha256=True),
            "source_route_patterns": file_fingerprint(source_summary, with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(report_path, report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--target-summary", type=Path, required=True)
    result.add_argument("--target-handoff", type=Path, required=True)
    result.add_argument("--source-summary", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    report = summarize(
        manifest_path=args.manifest.resolve(),
        target_summary=args.target_summary.resolve(),
        target_handoff=args.target_handoff.resolve(),
        source_summary=args.source_summary.resolve(),
        report_path=args.report.resolve(),
    )
    print(json.dumps(report["headline"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
