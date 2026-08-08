"""Read-only independent audit of the r3 G2P/rule agreement gate."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import (  # noqa: E402
    YEARS,
    edit_distance,
    phone_units,
    roman_units,
)
from build_common_pron_r3_g2p_agreement_gate import (  # noqa: E402
    REGRESSION_TOKENS,
    SCHEMA_VERSION,
    SOURCE_RESULT_FIELDS,
    SUMMARY_FIELDS,
    TARGET_RESULT_FIELDS,
)
from phoneme_roman import load_acoustic_meta, model_group_lookup  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCHEMA = "common_pron_r3_g2p_agreement_gate_audit.v1"
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
        raise RuntimeError(f"agreement fingerprint mismatch: {label}")
    return path


def parse_string_list(value: object, *, label: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON list: {label}") from exc
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise RuntimeError(f"invalid string list: {label}")
    return result


def expected_target_gate(row: dict[str, str], *, comparison: str) -> str:
    if comparison != "exact_rule_roman":
        return "mismatch_not_eligible"
    if clean(row["rewrite_rule"]) != "none":
        return "hold_exact_model_input_rewrite"
    statuses = set(
        parse_string_list(
            row["source_selection_statuses_json"],
            label=f"{row['target_hangul']} source statuses",
        )
    )
    if statuses == {"candidate_replace_rule_dictionary_agree"}:
        return "exact_candidate_dictionary_agree_all_sources"
    return "hold_exact_source_evidence_review"


def expected_source_gate(row: dict[str, str]) -> str:
    if clean(row["comparison_status"]) != "exact_rule_roman":
        return "mismatch_not_eligible"
    if clean(row["target_gate_class"]) == "hold_exact_model_input_rewrite":
        return "hold_exact_model_input_rewrite"
    routes = {
        "candidate_replace_rule_dictionary_agree": (
            "exact_candidate_dictionary_agree"
        ),
        "review_rule_dictionary_conflict": "hold_exact_dictionary_conflict",
        "review_rule_sensitive_no_attested_agreement": (
            "hold_exact_no_attested_agreement"
        ),
    }
    status = clean(row["original_selection_status"])
    if status not in routes:
        raise RuntimeError(f"unexpected source selection status: {status}")
    return routes[status]


def add_summary(
    summary: dict[tuple[str, str], dict[str, object]],
    *,
    layer: str,
    gate: str,
    target: str,
    source_types: int,
    total: int,
    years: dict[str, int],
) -> None:
    record = summary.setdefault(
        (layer, gate),
        {
            "targets": set(),
            "source_type_count": 0,
            "total_occurrences": 0,
            **{f"count_{year}": 0 for year in YEARS},
        },
    )
    record["targets"].add(target)
    record["source_type_count"] += source_types
    record["total_occurrences"] += total
    for year in YEARS:
        record[f"count_{year}"] += years[year]


def audit_gate(*, manifest_path: Path, audit_report: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "success_candidates_not_selected"
    ):
        raise RuntimeError("agreement gate manifest is not successful")
    scope = manifest.get("scope", {})
    required_false = (
        "candidate_is_final_selection",
        "canonical_selection_performed",
        "adoption_performed",
        "annual_mfa_started",
        "textgrids_modified",
        "actual_realization_claimed",
    )
    if any(scope.get(key) is not False for key in required_false):
        raise RuntimeError("agreement gate exceeded candidate-only scope")
    input_paths = {
        key: verify_fingerprint(record, label=f"input {key}")
        for key, record in manifest["inputs"].items()
    }
    output_paths = {
        key: verify_fingerprint(record, label=f"output {key}")
        for key, record in manifest["outputs"].items()
    }
    group_lookup = model_group_lookup(
        load_acoustic_meta(input_paths["acoustic_model"])
    )

    targets: dict[str, dict[str, str]] = {}
    model_inputs: set[str] = set()
    target_counts: Counter[str] = Counter()
    summary: dict[tuple[str, str], dict[str, object]] = {}
    with gzip.open(
        output_paths["target_agreement"],
        "rt",
        encoding="utf-8-sig",
        newline="",
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TARGET_RESULT_FIELDS:
            raise RuntimeError("target agreement column contract mismatch")
        for row in reader:
            target = clean(row["target_hangul"])
            model_input = clean(row["g2p_model_input"])
            if not target or target in targets or model_input in model_inputs:
                raise RuntimeError(f"target agreement identity error: {target}")
            phones = tuple(clean(row["g2p_candidate_phones"]).split())
            candidate_display, candidate_keys = phone_units(phones, group_lookup)
            rule_display, rule_keys = roman_units(row["rule_pron_roman"])
            comparison = (
                "exact_rule_roman"
                if candidate_keys == rule_keys
                else "different_rule_roman"
            )
            expected_gate = expected_target_gate(row, comparison=comparison)
            if (
                clean(row["g2p_candidate_roman"])
                != " ".join(candidate_display)
                or clean(row["rule_pron_roman_normalized"]) != " ".join(rule_display)
                or clean(row["comparison_status"]) != comparison
                or int(row["comparison_edit_distance"])
                != edit_distance(candidate_keys, rule_keys)
                or clean(row["gate_class"]) != expected_gate
                or clean(row["candidate_is_final_selection"]) != "false"
            ):
                raise RuntimeError(f"target agreement recomputation differs: {target}")
            years = {year: int(row[f"count_{year}"]) for year in YEARS}
            total = int(row["total_occurrences"])
            if sum(years.values()) != total:
                raise RuntimeError(f"target year counts differ: {target}")
            targets[target] = row
            model_inputs.add(model_input)
            target_counts[expected_gate] += 1
            add_summary(
                summary,
                layer="target",
                gate=expected_gate,
                target=target,
                source_types=int(row["source_type_count"]),
                total=total,
                years=years,
            )

    source_counts: Counter[str] = Counter()
    source_rows = 0
    source_occurrences = 0
    previous = ""
    target_aggregate: dict[str, dict[str, object]] = {
        target: {
            "source_type_count": 0,
            "total_occurrences": 0,
            "statuses": set(),
            **{f"count_{year}": 0 for year in YEARS},
        }
        for target in targets
    }
    regression_sources: dict[str, dict[str, str]] = {}
    with gzip.open(
        output_paths["source_agreement"],
        "rt",
        encoding="utf-8-sig",
        newline="",
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SOURCE_RESULT_FIELDS:
            raise RuntimeError("source agreement column contract mismatch")
        for row in reader:
            token = clean(row["token"])
            if not token or (previous and token <= previous):
                raise RuntimeError(f"source token order/duplicate error: {token}")
            previous = token
            target = clean(row["target_hangul"])
            if target not in targets:
                raise RuntimeError(f"source target missing: {token}")
            target_row = targets[target]
            linked_fields = (
                "g2p_model_input",
                "g2p_candidate_phones",
                "g2p_candidate_roman",
                "comparison_status",
                "comparison_edit_distance",
            )
            if any(
                clean(row[field]) != clean(target_row[field])
                for field in linked_fields
            ) or clean(row["target_gate_class"]) != clean(target_row["gate_class"]):
                raise RuntimeError(f"source/target gate link differs: {token}")
            expected_gate = expected_source_gate(row)
            if (
                clean(row["source_gate_class"]) != expected_gate
                or clean(row["candidate_is_final_selection"]) != "false"
                or clean(row["manual_decision_id"])
            ):
                raise RuntimeError(f"source gate routing differs: {token}")
            years = {year: int(row[f"count_{year}"]) for year in YEARS}
            total = int(row["total_occurrences"])
            if (
                sum(years.values()) != total
                or sum(value > 0 for value in years.values())
                != int(row["n_years_present"])
            ):
                raise RuntimeError(f"source year counts differ: {token}")
            aggregate = target_aggregate[target]
            aggregate["source_type_count"] += 1
            aggregate["total_occurrences"] += total
            aggregate["statuses"].add(clean(row["original_selection_status"]))
            for year in YEARS:
                aggregate[f"count_{year}"] += years[year]
            source_rows += 1
            source_occurrences += total
            source_counts[expected_gate] += 1
            add_summary(
                summary,
                layer="source",
                gate=expected_gate,
                target=target,
                source_types=1,
                total=total,
                years=years,
            )
            if token in REGRESSION_TOKENS:
                regression_sources[token] = row

    for target, row in targets.items():
        aggregate = target_aggregate[target]
        if (
            aggregate["source_type_count"] != int(row["source_type_count"])
            or aggregate["total_occurrences"] != int(row["total_occurrences"])
            or json.dumps(sorted(aggregate["statuses"]), ensure_ascii=False)
            != clean(row["source_selection_statuses_json"])
            or any(
                aggregate[f"count_{year}"] != int(row[f"count_{year}"])
                for year in YEARS
            )
        ):
            raise RuntimeError(f"source aggregate differs from target: {target}")

    actual_summary: dict[tuple[str, str], dict[str, str]] = {}
    with output_paths["gate_summary"].open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SUMMARY_FIELDS:
            raise RuntimeError("gate summary column contract mismatch")
        for row in reader:
            key = (clean(row["layer"]), clean(row["gate_class"]))
            if key in actual_summary:
                raise RuntimeError(f"duplicate gate summary row: {key}")
            actual_summary[key] = row
    if set(actual_summary) != set(summary):
        raise RuntimeError("gate summary categories differ")
    for key, expected in summary.items():
        row = actual_summary[key]
        expected_numbers = {
            "target_count": len(expected["targets"]),
            "source_type_count": expected["source_type_count"],
            "total_occurrences": expected["total_occurrences"],
            **{
                f"count_{year}": expected[f"count_{year}"]
                for year in YEARS
            },
        }
        if any(int(row[field]) != value for field, value in expected_numbers.items()):
            raise RuntimeError(f"gate summary counts differ: {key}")

    with output_paths["regression_examples"].open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SOURCE_RESULT_FIELDS:
            raise RuntimeError("regression example column contract mismatch")
        rows = list(reader)
    if [row["token"] for row in rows] != list(REGRESSION_TOKENS):
        raise RuntimeError("regression token order/coverage differs")
    for row in rows:
        source = regression_sources.get(row["token"])
        if source is None or any(row[field] != source[field] for field in SOURCE_RESULT_FIELDS):
            raise RuntimeError(f"regression row differs from source: {row['token']}")

    counts = manifest["counts"]
    if (
        int(counts["target_rows"]) != len(targets)
        or int(counts["source_rows"]) != source_rows
        or int(counts["total_occurrences"]) != source_occurrences
        or counts["target_gate_classes"] != dict(sorted(target_counts.items()))
        or counts["source_gate_classes"] != dict(sorted(source_counts.items()))
        or int(counts["regression_tokens"]) != len(REGRESSION_TOKENS)
    ):
        raise RuntimeError("agreement manifest aggregate counts differ")

    result: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "counts": {
            "target_rows": len(targets),
            "source_rows": source_rows,
            "total_occurrences": source_occurrences,
            "target_gate_classes": dict(sorted(target_counts.items())),
            "source_gate_classes": dict(sorted(source_counts.items())),
            "regression_tokens": len(regression_sources),
        },
        "contracts": {
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
            "actual_realization_claimed": False,
        },
        "evidence": {
            "agreement_manifest": file_fingerprint(
                manifest_path, with_sha256=True
            ),
            **{
                key: file_fingerprint(path, with_sha256=True)
                for key, path in output_paths.items()
            },
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(audit_report, result)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--audit-report", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = audit_gate(
        manifest_path=args.manifest.resolve(),
        audit_report=args.audit_report.resolve(),
    )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
