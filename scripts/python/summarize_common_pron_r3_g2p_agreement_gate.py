"""Summarize the r3 G2P/rule gate and make a small evidence handoff.

The handoff is diagnostic only.  It never turns an exact G2P candidate into a
canonical pronunciation and it does not authorize dictionary adoption, MFA,
or TextGrid materialization.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import heapq
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    REGRESSION_TOKENS,
    SCHEMA_VERSION,
    SOURCE_RESULT_FIELDS,
    TARGET_RESULT_FIELDS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_SCHEMA = "common_pron_r3_g2p_agreement_gate_summary.v1"
SAMPLE_FIELDS = (
    "sample_reason",
    "token",
    "target_hangul",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
    "rule_pron_hangul",
    "rule_pron_roman",
    "g2p_candidate_phones",
    "g2p_candidate_roman",
    "comparison_status",
    "comparison_edit_distance",
    "target_gate_class",
    "source_gate_class",
    "surface_rule_names",
    "dictionary_pron_hangul_json",
    "dictionary_pron_roman_json",
    "dictionary_source_refs_json",
    "original_selection_status",
    "original_selection_reason",
    "morph_context_required",
    "candidate_is_final_selection",
)
SAMPLE_QUOTAS = {
    "exact_candidate_dictionary_agree": 12,
    "hold_exact_dictionary_conflict": 100,
    "hold_exact_no_attested_agreement": 24,
    "hold_exact_model_input_rewrite": 100,
    "mismatch_not_eligible": 24,
}
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify_fingerprint(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"gate fingerprint mismatch: {label}")
    return path


def atomic_write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with temp.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SAMPLE_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def sample_row(row: dict[str, str], *, reason: str) -> dict[str, object]:
    return {
        "sample_reason": reason,
        **{field: clean(row.get(field)) for field in SAMPLE_FIELDS if field != "sample_reason"},
    }


def percentage(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 3) if denominator else 0.0


def summarize(
    *, manifest_path: Path, report_path: Path, evidence_sample_path: Path
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "success_candidates_not_selected"
    ):
        raise RuntimeError("agreement gate is not a completed candidate-only gate")
    if manifest.get("scope", {}).get("candidate_is_final_selection") is not False:
        raise RuntimeError("agreement gate scope permits final selection")
    outputs = {
        key: verify_fingerprint(record, label=key)
        for key, record in manifest["outputs"].items()
    }

    target_comparison: Counter[str] = Counter()
    target_gate: Counter[str] = Counter()
    edit_distance: Counter[int] = Counter()
    with gzip.open(
        outputs["target_agreement"], "rt", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_RESULT_FIELDS:
            raise RuntimeError("target agreement column contract mismatch")
        for row in reader:
            target_comparison[clean(row["comparison_status"])] += 1
            target_gate[clean(row["gate_class"])] += 1
            edit_distance[int(row["comparison_edit_distance"])] += 1

    source_rows: Counter[str] = Counter()
    source_occurrences: Counter[str] = Counter()
    source_years: dict[str, Counter[str]] = {
        year: Counter() for year in YEARS
    }
    top: dict[str, list[tuple[int, str, dict[str, str]]]] = defaultdict(list)
    regression: dict[str, dict[str, str]] = {}
    with gzip.open(
        outputs["source_agreement"], "rt", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SOURCE_RESULT_FIELDS:
            raise RuntimeError("source agreement column contract mismatch")
        for row in reader:
            gate = clean(row["source_gate_class"])
            total = int(row["total_occurrences"])
            token = clean(row["token"])
            source_rows[gate] += 1
            source_occurrences[gate] += total
            for year in YEARS:
                source_years[year][gate] += int(row[f"count_{year}"])
            quota = SAMPLE_QUOTAS.get(gate, 0)
            if quota:
                item = (total, token, row)
                heapq.heappush(top[gate], item)
                if len(top[gate]) > quota:
                    heapq.heappop(top[gate])
            if token in REGRESSION_TOKENS:
                regression[token] = row

    exact_source_gates = {
        gate for gate in source_rows if gate != "mismatch_not_eligible"
    }
    year_summary: dict[str, dict[str, object]] = {}
    for year in YEARS:
        exact = sum(source_years[year][gate] for gate in exact_source_gates)
        mismatch = source_years[year]["mismatch_not_eligible"]
        total = exact + mismatch
        year_summary[year] = {
            "exact_occurrences": exact,
            "mismatch_occurrences": mismatch,
            "total_occurrences": total,
            "exact_percent": percentage(exact, total),
            "mismatch_percent": percentage(mismatch, total),
            "by_source_gate": dict(sorted(source_years[year].items())),
        }

    sample_rows: list[dict[str, object]] = []
    included: set[str] = set()
    for gate in sorted(top):
        for _, token, row in sorted(top[gate], key=lambda item: (-item[0], item[1])):
            if token in included:
                continue
            sample_rows.append(sample_row(row, reason=f"high_frequency:{gate}"))
            included.add(token)
    for token in REGRESSION_TOKENS:
        row = regression.get(token)
        if row is None:
            raise RuntimeError(f"regression source missing: {token}")
        if token not in included:
            sample_rows.append(sample_row(row, reason="known_regression_example"))
            included.add(token)
    sample_rows.sort(key=lambda row: (clean(row["sample_reason"]), -int(row["total_occurrences"]), clean(row["token"])))
    atomic_write_csv(evidence_sample_path, sample_rows)

    total_targets = sum(target_comparison.values())
    exact_targets = target_comparison["exact_rule_roman"]
    total_source_occurrences = sum(source_occurrences.values())
    exact_source_occurrences = sum(
        source_occurrences[gate] for gate in exact_source_gates
    )
    result: dict[str, object] = {
        "schema_version": REPORT_SCHEMA,
        "status": "summarized_candidates_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "evidence_handoff_only": True,
            "researcher_approval_required_now": False,
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
        },
        "target_results": {
            "total": total_targets,
            "exact": exact_targets,
            "mismatch": total_targets - exact_targets,
            "exact_percent": percentage(exact_targets, total_targets),
            "mismatch_percent": percentage(total_targets - exact_targets, total_targets),
            "comparison_statuses": dict(sorted(target_comparison.items())),
            "gate_classes": dict(sorted(target_gate.items())),
            "edit_distance_distribution": {
                str(key): value for key, value in sorted(edit_distance.items())
            },
        },
        "source_results": {
            "rows_by_gate": dict(sorted(source_rows.items())),
            "occurrences_by_gate": dict(sorted(source_occurrences.items())),
            "total_occurrences": total_source_occurrences,
            "exact_occurrences": exact_source_occurrences,
            "mismatch_occurrences": source_occurrences["mismatch_not_eligible"],
            "exact_percent": percentage(exact_source_occurrences, total_source_occurrences),
            "mismatch_percent": percentage(source_occurrences["mismatch_not_eligible"], total_source_occurrences),
        },
        "year_summary": year_summary,
        "regression_examples": {
            token: {
                "target_hangul": clean(regression[token]["target_hangul"]),
                "rule_pron_roman": clean(regression[token]["rule_pron_roman"]),
                "g2p_candidate_phones": clean(regression[token]["g2p_candidate_phones"]),
                "g2p_candidate_roman": clean(regression[token]["g2p_candidate_roman"]),
                "comparison_status": clean(regression[token]["comparison_status"]),
                "source_gate_class": clean(regression[token]["source_gate_class"]),
            }
            for token in REGRESSION_TOKENS
        },
        "handoff": {
            "sample_rows": len(sample_rows),
            "purpose": "evidence inspection before a separately authorized canonical-selection stage",
            "not_an_approval_queue": True,
            "evidence_sample": file_fingerprint(evidence_sample_path, with_sha256=True),
        },
        "inputs": {
            "agreement_manifest": file_fingerprint(manifest_path, with_sha256=True),
            **{
                key: file_fingerprint(path, with_sha256=True)
                for key, path in outputs.items()
            },
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(report_path, result)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--evidence-sample", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = summarize(
        manifest_path=args.manifest.resolve(),
        report_path=args.report.resolve(),
        evidence_sample_path=args.evidence_sample.resolve(),
    )
    print(json.dumps({
        "target_results": result["target_results"],
        "source_results": result["source_results"],
        "sample_rows": result["handoff"]["sample_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
