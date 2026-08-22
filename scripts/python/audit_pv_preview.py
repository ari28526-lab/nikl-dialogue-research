"""Independently audit the seven-phenomena PV-A preview build.

The auditor intentionally does not import candidate generators or their query
matcher.  It re-evaluates the frozen preview conditions, allocation, context,
bundle hashes, and stitched WAV arithmetic from the emitted records.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from pipeline_common import now_iso, sha256_file
from pv_preview_common import (
    DEFAULT_CONFIG,
    PHENOMENON_LABELS,
    PROJECT_ROOT,
    atomic_write_csv,
    atomic_write_json,
    load_json,
    promote_directory,
    require_under,
    validate_config,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


RELATIONS = ["before_2", "before_1", "target", "after_1", "after_2"]
OFFSETS = {"before_2": -2, "before_1": -1, "target": 0, "after_1": 1, "after_2": 2}
PT_CODAS = {"ㄱ", "ㄲ", "ㅋ", "ㄳ", "ㄺ", "ㄷ", "ㅅ", "ㅆ", "ㅈ", "ㅊ", "ㅌ", "ㅂ", "ㅍ", "ㅄ", "ㄼ", "ㄿ"}
PT_ONSETS = {"ㄱ", "ㄷ", "ㅂ", "ㅅ", "ㅈ"}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    return fields, rows


def parse_json_list(value: str, *, field: str) -> list[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise RuntimeError(f"{field} must be a JSON string list")
    return parsed


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def condition_matches(row: Mapping[str, Any], condition: Mapping[str, Any]) -> bool:
    """Local matcher for the six operators admitted by the preview config."""

    field = str(condition["field"])
    value = str(row.get(field, ""))
    op = str(condition["op"])
    if op == "eq":
        return value == str(condition.get("value", ""))
    if op == "in":
        return value in {str(item) for item in condition.get("values", [])}
    if op == "nonempty":
        return bool(value.strip())
    if op == "truthy":
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if op == "contains":
        return str(condition.get("value", "")) in value
    if op == "regex":
        return re.search(str(condition.get("pattern", "")), value) is not None
    raise RuntimeError(f"unsupported audit condition op: {op}")


def internal_matches(rule: str, evidence: Mapping[str, Any]) -> bool:
    if evidence.get("boundary_scope") != "morph_internal":
        return False
    if evidence.get("left_unit_type") != "hangul" or evidence.get("right_unit_type") != "hangul":
        return False
    try:
        adjacent = int(str(evidence["right_unit_idx_in_morph"])) == int(
            str(evidence["left_unit_idx_in_morph"])
        ) + 1
    except (KeyError, TypeError, ValueError):
        return False
    if not adjacent:
        return False
    coda = str(evidence.get("left_coda_jamo", ""))
    onset = str(evidence.get("right_onset_jamo", ""))
    if rule == "pt":
        return coda in PT_CODAS and onset in PT_ONSETS
    if rule == "nan":
        return coda in PT_CODAS and onset == "ㄴ"
    if rule == "nal":
        return coda in PT_CODAS and onset == "ㄹ"
    if rule == "lln":
        return (coda, onset) in {("ㄴ", "ㄹ"), ("ㄹ", "ㄴ")}
    return False


def inferred_memberships(rows: Iterable[Mapping[str, str]]) -> list[str]:
    rows = list(rows)
    memberships = {row["phenomenon_code"] for row in rows}
    if "HIA" in memberships:
        memberships.add("VH")
    for row in rows:
        evidence = json.loads(row["match_evidence_json"])
        if row["environment_scope"] == "orth_contraction_probe" and row[
            "phenomenon_code"
        ] in {"VH", "HIA"}:
            memberships.update({"VH", "HIA"})
        if row["phenomenon_code"] == "VH" and evidence.get("left_coda_jamo") == "":
            memberships.add("HIA")
    order = list(PHENOMENON_LABELS)
    return sorted(memberships, key=order.index)


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, str]] = []

    def add(self, check_id: str, passed: bool, details: object) -> None:
        if isinstance(details, str):
            rendered = details
        else:
            rendered = json.dumps(details, ensure_ascii=False, sort_keys=True)
        self.rows.append(
            {
                "check_id": check_id,
                "passed": str(bool(passed)),
                "details": rendered,
            }
        )

    @property
    def passed(self) -> bool:
        return bool(self.rows) and all(row["passed"] == "True" for row in self.rows)


def expected_primary_quotas(config: Mapping[str, Any], year: int) -> dict[str, int]:
    allocation = config["pilot_allocation"]
    base = int(allocation["base_primary_quota_per_phenomenon_year"])
    result = {code: base for code in allocation["phenomenon_order"]}
    for code in allocation["rotating_extra_primary_phenomena"][str(year)]:
        result[code] += 1
    exception = allocation.get("approved_primary_quota_exceptions", {}).get(
        str(year), {}
    )
    deltas = exception.get("deltas", {})
    if sum(int(value) for value in deltas.values()) != 0:
        raise RuntimeError(f"approved quota deltas do not sum to zero: {year}")
    for code, delta in deltas.items():
        if code not in result:
            raise RuntimeError(f"unknown phenomenon in approved quota exception: {code}")
        result[code] += int(delta)
    expected_total = int(allocation["unique_physical_packages_per_year"])
    if any(value < 0 for value in result.values()) or sum(result.values()) != expected_total:
        raise RuntimeError(f"invalid independently calculated quota: {year} {result}")
    return result


def audit_candidates(
    checks: Checks,
    config: Mapping[str, Any],
    candidates: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    query_map = {row["query_id"]: row for row in config["queries"]}
    internal_map = {row["query_id"]: row for row in config["internal_rules"]}
    ni_map = {
        spec["pv_query_id"]: (source_query_id, spec)
        for source_query_id, spec in config["n_insertion_source"]["query_map"].items()
    }
    allowed_statuses = {
        "selected_primary",
        "selected_shared_membership",
        "not_selected_quota_or_duplicate",
    }
    errors: list[str] = []
    seen_ids: set[str] = set()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row_number, row in enumerate(candidates, 2):
        candidate_id = row.get("candidate_row_id", "")
        if not candidate_id or candidate_id in seen_ids:
            errors.append(f"row {row_number}: duplicate/empty candidate_row_id={candidate_id!r}")
        seen_ids.add(candidate_id)
        if row.get("selection_status") not in allowed_statuses:
            errors.append(f"{candidate_id}: invalid selection_status")
        if row.get("query_role") != "preview_environment_sweep":
            errors.append(f"{candidate_id}: non-preview query role")
        try:
            evidence = json.loads(row["match_evidence_json"])
        except (KeyError, json.JSONDecodeError) as exc:
            errors.append(f"{candidate_id}: invalid match_evidence_json ({exc})")
            continue
        query_id = row.get("pv_query_id", "")
        if query_id in query_map:
            spec = query_map[query_id]
            if row.get("phenomenon_code") != spec["phenomenon_code"]:
                errors.append(f"{candidate_id}: phenomenon/query mismatch")
            if not all(condition_matches(evidence, item) for item in spec["conditions"]):
                errors.append(f"{candidate_id}: declarative boundary condition failed")
        elif query_id in internal_map:
            spec = internal_map[query_id]
            if row.get("phenomenon_code") != spec["phenomenon_code"] or not internal_matches(
                str(spec["rule"]), evidence
            ):
                errors.append(f"{candidate_id}: internal jamo recheck failed")
        elif query_id in ni_map:
            source_query_id, spec = ni_map[query_id]
            if (
                row.get("source_query_id") != source_query_id
                or row.get("phenomenon_code") != "NI"
                or row.get("environment_scope") != spec["environment_scope"]
            ):
                errors.append(f"{candidate_id}: frozen NI mapping mismatch")
        else:
            errors.append(f"{candidate_id}: unknown pv_query_id={query_id}")
        grouped[row.get("physical_occurrence_ref", "")].append(row)
    for ref, rows in grouped.items():
        inferred = inferred_memberships(rows)
        for row in rows:
            try:
                recorded = parse_json_list(
                    row["membership_codes_json"], field="membership_codes_json"
                )
            except (KeyError, RuntimeError, json.JSONDecodeError) as exc:
                errors.append(f"{row.get('candidate_row_id')}: {exc}")
                continue
            if recorded != inferred:
                errors.append(f"{ref}: recorded memberships {recorded} != inferred {inferred}")
    checks.add(
        "candidate_zero_drop_and_environment_recheck",
        not errors and bool(candidates),
        {"candidate_rows": len(candidates), "errors": errors[:50], "error_count": len(errors)},
    )
    return grouped


def audit_samples_and_events(
    checks: Checks,
    config: Mapping[str, Any],
    candidates_by_ref: Mapping[str, list[dict[str, str]]],
    samples: list[dict[str, str]],
    events: list[dict[str, str]],
) -> None:
    errors: list[str] = []
    if len(samples) != 180:
        errors.append(f"physical package count={len(samples)} expected=180")
    sample_by_id = {row.get("pv_id", ""): row for row in samples}
    if len(sample_by_id) != len(samples) or "" in sample_by_id:
        errors.append("pv_id is empty or duplicated")
    refs = [row.get("physical_occurrence_ref", "") for row in samples]
    if len(set(refs)) != len(refs):
        errors.append("selected physical_occurrence_ref is duplicated")
    actual_by_year_phenomenon = Counter(
        (int(row["year"]), row["primary_phenomenon_code"]) for row in samples
    )
    actual_by_year = Counter(int(row["year"]) for row in samples)
    for year in config["pilot_allocation"]["years"]:
        year = int(year)
        if actual_by_year[year] != 30:
            errors.append(f"year {year}: {actual_by_year[year]} packages, expected 30")
        for code, expected in expected_primary_quotas(config, year).items():
            actual = actual_by_year_phenomenon[(year, code)]
            if actual != expected:
                errors.append(f"{year}|{code}: primary={actual}, expected={expected}")
    events_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    event_ids: set[str] = set()
    for event in events:
        event_id = event.get("review_event_id", "")
        if not event_id or event_id in event_ids:
            errors.append(f"duplicate/empty review_event_id={event_id!r}")
        event_ids.add(event_id)
        events_by_id[event.get("pv_id", "")].append(event)
        if event.get("record_role") != "exploratory_pv_event_not_g7_ledger":
            errors.append(f"{event_id}: formal-ledger separation marker missing")
    for pv_id, sample in sample_by_id.items():
        ref = sample.get("physical_occurrence_ref", "")
        source_rows = candidates_by_ref.get(ref, [])
        if not source_rows:
            errors.append(f"{pv_id}: no candidate accounting rows")
            continue
        expected_memberships = inferred_memberships(source_rows)
        try:
            memberships = parse_json_list(
                sample["phenomenon_memberships_json"],
                field="phenomenon_memberships_json",
            )
            recorded_event_ids = parse_json_list(
                sample["review_event_ids_json"], field="review_event_ids_json"
            )
        except (KeyError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"{pv_id}: {exc}")
            continue
        if memberships != expected_memberships:
            errors.append(f"{pv_id}: membership mismatch")
        if sample.get("primary_phenomenon_code") not in memberships:
            errors.append(f"{pv_id}: primary phenomenon absent from memberships")
        pv_events = events_by_id.get(pv_id, [])
        if {row.get("phenomenon_code") for row in pv_events} != set(memberships):
            errors.append(f"{pv_id}: logical event membership mismatch")
        if {row.get("review_event_id") for row in pv_events} != set(recorded_event_ids):
            errors.append(f"{pv_id}: recorded event IDs mismatch")
        primary_events = [row for row in pv_events if as_bool(row.get("is_primary_phenomenon"))]
        if len(primary_events) != 1 or primary_events[0].get("phenomenon_code") != sample.get(
            "primary_phenomenon_code"
        ):
            errors.append(f"{pv_id}: primary logical event mismatch")
        selected_source_rows = [
            row for row in source_rows if row.get("selected_pv_id") == pv_id
        ]
        if len(selected_source_rows) != len(source_rows):
            errors.append(f"{pv_id}: candidate selected_pv_id zero-drop mapping mismatch")
        if sample.get("inclusion_status") != "candidate_ready_for_manual_realization_review":
            errors.append(f"{pv_id}: selected asset is not candidate-ready")
        if not str(sample.get("timing_status", "")).startswith("linked_"):
            errors.append(f"{pv_id}: target timing is not linked")
        interpretation_limit = sample.get("interpretation_limit", "")
        normalized_limit = interpretation_limit.lower()
        if "not an automatic realization judgement" not in normalized_limit:
            errors.append(f"{pv_id}: no explicit realization interpretation limit")
    checks.add(
        "sample_allocation_membership_and_events",
        not errors,
        {
            "physical_packages": len(samples),
            "logical_events": len(events),
            "by_year": dict(sorted(actual_by_year.items())),
            "errors": errors[:50],
            "error_count": len(errors),
        },
    )


def audit_context(
    checks: Checks,
    samples: list[dict[str, str]],
    contexts: list[dict[str, str]],
) -> None:
    errors: list[str] = []
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in contexts:
        grouped[row.get("pv_id", "")].append(row)
    for sample in samples:
        pv_id = sample["pv_id"]
        rows = grouped.get(pv_id, [])
        if len(rows) != 5 or [row.get("relation") for row in rows] != RELATIONS:
            errors.append(f"{pv_id}: context is not five ordered zero-drop slots")
            continue
        target = rows[2]
        if target.get("slot_status") != "present" or target.get("utt_id") != sample["utt_id"]:
            errors.append(f"{pv_id}: target context slot mismatch")
            continue
        target_rank = int(target["source_rank_in_dialogue"])
        present_ids: list[str] = []
        for row in rows:
            relation = row["relation"]
            if row.get("rank_offset") != str(OFFSETS[relation]):
                errors.append(f"{pv_id}|{relation}: rank_offset mismatch")
            if row.get("slot_status") != "present":
                if row.get("slot_status") != "missing_dialogue_edge_with_zero_drop_status":
                    errors.append(f"{pv_id}|{relation}: unrecognized missing-slot status")
                continue
            ledger_lookup_status = row.get("ledger_lookup_status", "")
            if ledger_lookup_status not in {
                "available_within_approved_scan_cap",
                "missing_within_approved_scan_cap_zero_drop",
            }:
                errors.append(
                    f"{pv_id}|{relation}: unrecognized ledger lookup status "
                    f"{ledger_lookup_status}"
                )
            if (
                relation == "target"
                and ledger_lookup_status != "available_within_approved_scan_cap"
            ):
                errors.append(f"{pv_id}: target ledger row is unavailable within cap")
            present_ids.append(row.get("utt_id", ""))
            if row.get("session_id") != sample.get("session_id") or row.get(
                "target_session_id"
            ) != sample.get("session_id"):
                errors.append(f"{pv_id}|{relation}: cross-session context")
            if row.get("dialogue_id") != target.get("dialogue_id"):
                errors.append(f"{pv_id}|{relation}: cross-dialogue context")
            try:
                actual_offset = int(row["source_rank_in_dialogue"]) - target_rank
            except (KeyError, ValueError):
                actual_offset = 999
            if actual_offset != OFFSETS[relation]:
                errors.append(f"{pv_id}|{relation}: existing-row rank mismatch")
            if row.get("derived_turn_is_exploratory") != "True":
                errors.append(f"{pv_id}|{relation}: speaker run claimed as gold")
            if row.get("operational_speaker_run_rule") != "consecutive_existing_rows_with_identical_speaker_id":
                errors.append(f"{pv_id}|{relation}: operational speaker-run rule mismatch")
            if "not_pause" not in row.get("source_time_gap_semantics", "") and row.get(
                "source_time_gap_semantics"
            ) != "not_applicable_session_start":
                errors.append(f"{pv_id}|{relation}: timestamp gap lacks non-pause semantics")
            if row.get("same_file_as_target") != "True":
                errors.append(f"{pv_id}|{relation}: file/session preservation marker mismatch")
        if len(present_ids) != len(set(present_ids)):
            errors.append(f"{pv_id}: duplicate utterance in context window")
    if set(grouped) != {row["pv_id"] for row in samples}:
        errors.append("context/sample pv_id sets differ")
    checks.add(
        "context_existing_rank_zero_drop_and_turn_limits",
        not errors and len(contexts) == len(samples) * 5,
        {
            "context_rows": len(contexts),
            "expected": len(samples) * 5,
            "errors": errors[:50],
            "error_count": len(errors),
        },
    )


def audit_stitch(package: Path, stitch_rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    output = package / "context_pm2.wav"
    if not output.is_file():
        return [f"{package.name}: context_pm2.wav missing"]
    materialized = [
        row for row in stitch_rows if row.get("stitch_status") == "materialized_serialized_clip"
    ]
    if not materialized:
        return [f"{package.name}: no materialized context clips"]
    try:
        with wave.open(str(output), "rb") as stream:
            actual_seconds = stream.getnframes() / stream.getframerate()
            tolerance = 1.0 / stream.getframerate() + 1e-9
    except (OSError, wave.Error) as exc:
        return [f"{package.name}: stitched WAV unreadable ({exc})"]
    expected_seconds = 0.0
    previous_end = 0.0
    for index, row in enumerate(materialized):
        try:
            source_seconds = float(row["source_clip_end_seconds"]) - float(
                row["source_clip_start_seconds"]
            )
            gap_seconds = float(row["gap_after_seconds"])
            stitched_start = float(row["stitched_start_seconds"])
            stitched_end = float(row["stitched_end_seconds"])
        except (KeyError, ValueError) as exc:
            errors.append(f"{package.name}: non-numeric stitch manifest ({exc})")
            continue
        if abs(stitched_start - previous_end) > tolerance:
            errors.append(f"{package.name}: stitched start is discontinuous at clip {index + 1}")
        if abs((stitched_end - stitched_start) - source_seconds) > tolerance:
            errors.append(f"{package.name}: source/stitch duration mismatch at clip {index + 1}")
        if index < len(materialized) - 1 and (
            gap_seconds <= 0 or not as_bool(row.get("gap_after_is_synthetic"))
        ):
            errors.append(f"{package.name}: inter-clip gap lacks synthetic marker")
        if index == len(materialized) - 1 and gap_seconds != 0:
            errors.append(f"{package.name}: trailing synthetic gap is not zero")
        expected_seconds += source_seconds + gap_seconds
        previous_end = stitched_end + gap_seconds
    if abs(actual_seconds - expected_seconds) > tolerance:
        errors.append(
            f"{package.name}: WAV={actual_seconds:.9f}, reverse sum={expected_seconds:.9f}"
        )
    return errors


def audit_bundle(
    checks: Checks,
    bundle_root: Path,
    samples: list[dict[str, str]],
    events: list[dict[str, str]],
) -> None:
    manifest = load_json(bundle_root / "PV_BUNDLE_BUILD.json")
    package_dirs = manifest.get("outputs", {}).get("package_dirs", {})
    errors: list[str] = []
    if set(package_dirs) != {row["pv_id"] for row in samples}:
        errors.append("bundle package/sample pv_id sets differ")
    _, review_rows = read_csv(bundle_root / "REVIEW.csv")
    if {row.get("review_event_id") for row in review_rows} != {
        row.get("review_event_id") for row in events
    }:
        errors.append("REVIEW.csv logical-event set mismatch")
    if any(row.get("record_role") != "exploratory_pv_only_not_formal_realization_ledger" for row in review_rows):
        errors.append("REVIEW.csv formal-ledger separation marker missing")
    for pv_id, relative in package_dirs.items():
        package = bundle_root / relative
        if not package.is_dir():
            errors.append(f"{pv_id}: package directory missing")
            continue
        for required in (
            "target.wav",
            "target_source.TextGrid",
            "row.csv",
            "events.csv",
            "context.csv",
            "context_pm2.wav",
            "context_stitch_manifest.csv",
            "PACKAGE_MANIFEST.json",
        ):
            if not (package / required).is_file():
                errors.append(f"{pv_id}: {required} missing")
        stitch_path = package / "context_stitch_manifest.csv"
        if stitch_path.is_file():
            _, stitch_rows = read_csv(stitch_path)
            if len(stitch_rows) != 5 or [row.get("relation") for row in stitch_rows] != RELATIONS:
                errors.append(f"{pv_id}: stitch manifest is not five ordered slots")
            else:
                errors.extend(audit_stitch(package, stitch_rows))
        package_manifest_path = package / "PACKAGE_MANIFEST.json"
        if package_manifest_path.is_file():
            package_manifest = load_json(package_manifest_path)
            safety = package_manifest.get("safety", {})
            if (
                safety.get("source_modified") is not False
                or safety.get("realization_judgement_performed") is not False
                or safety.get("source_timestamp_gap_interpreted_as_pause") is not False
                or safety.get("synthetic_gap_claimed_as_source_silence") is not False
            ):
                errors.append(f"{pv_id}: package safety assertion failed")
    sha_path = bundle_root / "SHA256_MANIFEST.csv"
    _, sha_rows = read_csv(sha_path)
    listed: set[str] = set()
    for row in sha_rows:
        relative = row.get("path", "")
        path = bundle_root / Path(relative)
        listed.add(Path(relative).as_posix())
        if not path.is_file():
            errors.append(f"SHA manifest file missing: {relative}")
            continue
        if path.stat().st_size != int(row["bytes"]) or sha256_file(path) != row["sha256"]:
            errors.append(f"SHA manifest mismatch: {relative}")
    actual = {
        path.relative_to(bundle_root).as_posix()
        for path in bundle_root.rglob("*")
        if path.is_file() and path.name != "SHA256_MANIFEST.csv"
    }
    if listed != actual:
        errors.append(
            f"SHA coverage mismatch: missing={sorted(actual - listed)[:10]} extra={sorted(listed - actual)[:10]}"
        )
    checks.add(
        "bundle_files_sha_and_stitch_reverse_arithmetic",
        not errors and len(package_dirs) == 180,
        {
            "package_dirs": len(package_dirs),
            "sha_manifest_rows": len(sha_rows),
            "errors": errors[:50],
            "error_count": len(errors),
        },
    )


def audit_safety(
    checks: Checks,
    config: Mapping[str, Any],
    manifests: Iterable[tuple[str, Mapping[str, Any]]],
) -> None:
    errors: list[str] = []
    if int(config["safety"].get("max_rows_scanned_per_table_year", 0)) != 200_000:
        errors.append("approved scan cap is not 200000")
    if config["safety"].get("automatic_scan_cap_increase") is not False:
        errors.append("automatic scan-cap increase is enabled")
    if config["safety"].get("mfa_koina_wav2vec2_execution") is not False:
        errors.append("forbidden tool execution is enabled in config")
    for label, manifest in manifests:
        safety = manifest.get("safety", {})
        for field in ("source_assets_modified", "realization_judgement_performed"):
            if safety.get(field) is not False:
                errors.append(f"{label}: {field} is not false")
        for field in ("mfa_run", "koina_run", "wav2vec2_run"):
            if safety.get(field) is not False:
                errors.append(f"{label}: {field} is not false")
    checks.add(
        "source_write_and_forbidden_tool_assertions",
        not errors,
        {
            "check_method": "output_containment_plus_build_manifest_assertions",
            "errors": errors,
        },
    )


def perform_audit(*, config_path: Path, run_root: Path, output_dir: Path) -> dict[str, Any]:
    require_under(run_root, PROJECT_ROOT / "outputs" / "pilots")
    require_under(output_dir, PROJECT_ROOT / "outputs" / "pilots")
    config = load_json(config_path)
    validate_config(config)
    samples_root = run_root / "samples"
    context_root = run_root / "context"
    bundle_root = run_root / "bundle"
    paths = {
        "candidates": samples_root / "PV_CANDIDATE_ACCOUNTING.csv",
        "samples": samples_root / "PV_SAMPLES.csv",
        "events": samples_root / "PV_REVIEW_EVENTS.csv",
        "sample_build": samples_root / "PV_SAMPLE_BUILD.json",
        "internal_scan": samples_root / "internal" / "PV_INTERNAL_SCAN.json",
        "context": context_root / "PV_CONTEXT.csv",
        "context_build": context_root / "PV_CONTEXT_BUILD.json",
        "bundle_build": bundle_root / "PV_BUNDLE_BUILD.json",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("required audit inputs missing: " + "; ".join(missing))
    _, candidates = read_csv(paths["candidates"])
    _, samples = read_csv(paths["samples"])
    _, events = read_csv(paths["events"])
    _, contexts = read_csv(paths["context"])
    manifests = {
        "internal_scan": load_json(paths["internal_scan"]),
        "sample_build": load_json(paths["sample_build"]),
        "context_build": load_json(paths["context_build"]),
        "bundle_build": load_json(paths["bundle_build"]),
    }
    checks = Checks()
    candidates_by_ref = audit_candidates(checks, config, candidates)
    audit_samples_and_events(checks, config, candidates_by_ref, samples, events)
    expected_exceptions = config["pilot_allocation"].get(
        "approved_primary_quota_exceptions", {}
    )
    recorded_exceptions = manifests["sample_build"].get(
        "approved_primary_quota_exceptions", {}
    )
    checks.add(
        "approved_quota_exception_traceability",
        recorded_exceptions == expected_exceptions,
        {
            "expected": expected_exceptions,
            "recorded": recorded_exceptions,
        },
    )
    audit_context(checks, samples, contexts)
    audit_bundle(checks, bundle_root, samples, events)
    audit_safety(checks, config, manifests.items())
    output_status = "passed_listening_may_begin" if checks.passed else "failed_do_not_begin_listening"
    payload = {
        "schema_version": "pv_preview_independent_audit.v1",
        "status": output_status,
        "passed": checks.passed,
        "recorded_at": now_iso(),
        "auditor_independence": {
            "candidate_generator_imported": False,
            "generator_query_matcher_imported": False,
            "conditions_reimplemented_and_reapplied": True,
        },
        "config": {
            "path": str(config_path),
            "sha256": sha256_file(config_path),
        },
        "run_root": str(run_root),
        "input_files": {
            name: {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for name, path in paths.items()
        },
        "counts": {
            "candidate_rows": len(candidates),
            "physical_packages": len(samples),
            "logical_review_events": len(events),
            "context_rows": len(contexts),
            "checks": len(checks.rows),
            "failed_checks": sum(row["passed"] != "True" for row in checks.rows),
        },
        "checks": checks.rows,
        "listening_gate": "open" if checks.passed else "closed",
    }
    if output_dir.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    if partial.exists():
        raise FileExistsError(f"existing partial output is preserved: {partial}")
    partial.mkdir(parents=True)
    atomic_write_csv(
        partial / "PV_AUDIT_CHECKS.csv",
        ["check_id", "passed", "details"],
        checks.rows,
    )
    atomic_write_json(partial / "PV_AUDIT.json", payload)
    promote_directory(partial, output_dir)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else run_root / "audit"
    try:
        result = perform_audit(
            config_path=args.config.resolve(),
            run_root=run_root,
            output_dir=output_dir,
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
