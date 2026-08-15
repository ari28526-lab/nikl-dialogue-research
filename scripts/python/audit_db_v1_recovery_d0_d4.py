#!/usr/bin/env python3
"""Independently audit and seal the D0--D4 recovery planning package."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
YEARS = tuple(str(year) for year in range(2020, 2026))
AC_ID = "nikl_dialogue_research_db_v1_0_0_rc0_20260815"
D_ID = "nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
EXPECTED_STATUS = {
    "pre_mfa_technical_exclusion": 95_860,
    "post_mfa_technical_exclusion": 3_086,
    "pronunciation_followup": 718_364,
}
EXPECTED_REASONS = {
    "audio_pairing_unresolved": 95_798,
    "text_duration_impossible": 60,
    "audio_unusable": 2,
    "mfa_alignment_missing": 3_061,
    "mfa_feature_generation_failed": 25,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def csv_rows(path: Path):
    context = (
        gzip.open(path, "rt", encoding="utf-8-sig", newline="")
        if path.suffix.lower() == ".gz"
        else path.open("r", encoding="utf-8-sig", newline="")
    )
    with context as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise RuntimeError(f"CSV header missing: {path}")
        yield from reader


def list_value(raw: str, label: str) -> list[str]:
    value = json.loads(raw or "[]")
    if not isinstance(value, list):
        raise RuntimeError(f"not a JSON list: {label}")
    return [str(item) for item in value if str(item)]


def verify_record(record: dict) -> Path:
    path = Path(record["path"])
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
        raise RuntimeError(f"fingerprint mismatch: {path}")
    return path


def audit_d1(ac_root: Path, d_root: Path) -> tuple[Counter[str], dict[str, set[str]]]:
    totals: Counter[str] = Counter()
    d_ids: dict[str, set[str]] = {}
    for year in YEARS:
        expected: dict[str, tuple[str, str]] = {}
        aligned: set[str] = set()
        for row in csv_rows(ac_root / "ledgers" / f"{year}_utterance_status.csv.gz"):
            status = row["primary_status"]
            if status == "aligned_safe_body":
                aligned.add(row["utt_id"])
            else:
                expected[row["utt_id"]] = (status, row["reason_codes_json"])
        observed: set[str] = set()
        for row in csv_rows(d_root / "D1_recovery_ledger" / f"{year}_recovery_routing.csv.gz"):
            utt_id = row["utt_id"]
            if row["year"] != year or utt_id in observed:
                raise RuntimeError(f"{year}: D1 year/duplicate failure: {utt_id}")
            if utt_id in aligned or utt_id not in expected:
                raise RuntimeError(f"{year}: D1 contains aligned/unknown ID: {utt_id}")
            status, reasons_json = expected[utt_id]
            if row["primary_status"] != status or row["reason_codes_json"] != reasons_json:
                raise RuntimeError(f"{year}: D1 status/reason drift: {utt_id}")
            if row["needs_researcher_review"] != "true" or not row["recovery_shard_id"].startswith(f"D1_{year}_"):
                raise RuntimeError(f"{year}: D1 routing invariant failure: {utt_id}")
            observed.add(utt_id)
            totals[status] += 1
            for reason in list_value(row["reason_codes_json"], utt_id):
                totals[f"reason:{reason}"] += 1
        if observed != set(expected):
            raise RuntimeError(f"{year}: D1 exact-ID set differs from A-C")
        d_ids[year] = observed
    return totals, d_ids


def audit_d2(d_root: Path, d1_ids: dict[str, set[str]]) -> tuple[Counter[str], set[tuple[str, str]], list[dict[str, str]]]:
    counts: Counter[str] = Counter()
    technical_ids: set[tuple[str, str]] = set()
    rows_out: list[dict[str, str]] = []
    allowed_classes = {
        "blocked_missing_materialized_input", "ready_for_feature_failure_diagnostic",
        "ready_for_alignment_diagnostic", "preserve_audio_unusable_research_decision",
        "requires_timing_metadata_review", "blocked_missing_audio",
        "requires_audio_identity_review", "requires_session_audio_remap",
    }
    for year in YEARS:
        for row in csv_rows(d_root / "D2_technical_audit" / f"{year}_technical_recoverability.csv.gz"):
            key = (year, row["utt_id"])
            if key in technical_ids or row["utt_id"] not in d1_ids[year]:
                raise RuntimeError(f"D2 duplicate/unknown ID: {key}")
            if row["primary_status"] not in {"pre_mfa_technical_exclusion", "post_mfa_technical_exclusion"}:
                raise RuntimeError(f"D2 nontechnical status: {key}")
            if row["recoverability_class"] not in allowed_classes or row["data_mutation_performed"] != "false":
                raise RuntimeError(f"D2 class/mutation invariant failure: {key}")
            for exists_field, path_field, bytes_field in (
                ("canonical_wav_exists", "canonical_wav_path", "canonical_wav_bytes"),
                ("r3_corpus_wav_exists", "r3_corpus_wav_path", "r3_corpus_wav_bytes"),
                ("r3_corpus_lab_exists", "r3_corpus_lab_path", "r3_corpus_lab_bytes"),
            ):
                exists_now = Path(row[path_field]).is_file()
                if row[exists_field] != str(exists_now).lower():
                    raise RuntimeError(f"D2 current existence drift: {key} {path_field}")
                if exists_now and Path(row[path_field]).stat().st_size != int(row[bytes_field]):
                    raise RuntimeError(f"D2 current size drift: {key} {path_field}")
            if row["primary_status"] == "post_mfa_technical_exclusion" and row["recoverability_class"].startswith("ready_for_"):
                if row["r3_corpus_wav_exists"] != "true" or row["r3_corpus_lab_exists"] != "true":
                    raise RuntimeError(f"D2 ready case lacks materialized pair: {key}")
            technical_ids.add(key)
            counts[row["recoverability_class"]] += 1
            counts[f"reason:{row['reason_code']}"] += 1
            rows_out.append(row)
    if len(technical_ids) != 98_946:
        raise RuntimeError(f"D2 total differs: {len(technical_ids)}")
    return counts, technical_ids, rows_out


def source_pronunciation_counts(ac_root: Path) -> tuple[dict[tuple[str, str], Counter[str]], int]:
    base = load_json(ac_root / "BASE_RELEASE_MANIFEST_2020_2025.json")
    result: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    utterances = 0
    for year in YEARS:
        path = Path(base["years"][year]["evidence"]["pronunciation_followup_ids"]["path"])
        for row in csv_rows(path):
            utterances += 1
            for field, role in (
                ("hold_tokens_json", "hold"),
                ("policy_tokens_json", "policy"),
                ("unknown_tokens_json", "unknown"),
            ):
                values = list_value(row.get(field, ""), f"{year}:{row['utt_id']}")
                for token in values:
                    result[(role, token)][year] += 1
                    result[(role, token)]["total"] += 1
    return result, utterances


def audit_d3(ac_root: Path, d_root: Path) -> dict:
    expected, utterances = source_pronunciation_counts(ac_root)
    observed: dict[tuple[str, str], Counter[str]] = {}
    invalid_decisions = 0
    for row in csv_rows(d_root / "D3_pronunciation_types" / "pronunciation_type_summary.csv.gz"):
        key = (row["token_role"], row["token"])
        if key in observed:
            raise RuntimeError(f"D3 duplicate role-token: {key}")
        counts = Counter({year: int(row[f"count_{year}"]) for year in YEARS})
        counts["total"] = int(row["utterance_links"])
        observed[key] = counts
        if row["automatic_pronunciation_decision_performed"] != "false":
            invalid_decisions += 1
    if observed != expected:
        raise RuntimeError("D3 role-token frequency compression differs from exact source")
    if utterances != 718_364 or invalid_decisions:
        raise RuntimeError("D3 scope/automatic-decision invariant failed")
    return {
        "pronunciation_followup_utterances": utterances,
        "distinct_role_token_rows": len(observed),
        "automatic_pronunciation_decisions": invalid_decisions,
    }


def audit_d4(d_root: Path, technical_rows: list[dict[str, str]]) -> dict:
    source = {(row["year"], row["utt_id"]): row for row in technical_rows}
    seen: set[tuple[str, str]] = set()
    reasons: Counter[str] = Counter()
    sessions: dict[str, set[str]] = defaultdict(set)
    rows = list(csv_rows(d_root / "D4_first_shard" / "FIRST_SHARD.csv.gz"))
    for expected_order, row in enumerate(rows, 1):
        key = (row["year"], row["utt_id"])
        if row["run_order"] != str(expected_order) or key in seen or key not in source:
            raise RuntimeError(f"D4 order/identity failure: {key}")
        original = source[key]
        if row["reason_code"] != original["reason_code"] or original["recoverability_class"] not in {
            "ready_for_feature_failure_diagnostic", "ready_for_alignment_diagnostic",
        }:
            raise RuntimeError(f"D4 source/class failure: {key}")
        seen.add(key)
        reasons[row["reason_code"]] += 1
        if row["reason_code"] == "mfa_alignment_missing":
            sessions[row["year"]].add(row["session_id"])
    all_feature = {
        (row["year"], row["utt_id"])
        for row in technical_rows
        if row["reason_code"] == "mfa_feature_generation_failed"
    }
    selected_feature = {
        key for key in seen if source[key]["reason_code"] == "mfa_feature_generation_failed"
    }
    if selected_feature != all_feature or reasons["mfa_feature_generation_failed"] != 25:
        raise RuntimeError("D4 does not contain all feature failures")
    if any(len(sessions[year]) != 5 for year in YEARS) or reasons["mfa_alignment_missing"] != 30:
        raise RuntimeError("D4 alignment sample is not five unique sessions per year")
    gate = load_json(d_root / "D4_first_shard" / "PRE_MFA_GATE.json")
    if gate.get("status") != "hold_before_materialization_and_mfa":
        raise RuntimeError("D4 gate is not closed")
    execution = gate["execution"]
    if execution["files_materialized"] or execution["mfa_run"] or execution["approval_contract_present"]:
        raise RuntimeError("D4 gate falsely records execution/approval")
    return {"rows": len(rows), "reasons": dict(reasons), "unique_alignment_sessions": {year: len(sessions[year]) for year in YEARS}}


def seal_output_manifest(d_root: Path, project_root: Path) -> dict:
    files = []
    for path in sorted(d_root.rglob("*"), key=lambda item: str(item).lower()):
        if path.is_file() and path.name != "OUTPUT_MANIFEST.json":
            files.append(file_fingerprint(path, with_sha256=True))
    manifest = {
        "schema_version": "research_db_v1_recovery_d0_d4_output_manifest.v1",
        "status": "passed_stopped_before_materialization_and_mfa",
        "recorded_at": now_iso(), "recovery_plan_id": D_ID,
        "files": files, "file_count": len(files),
        "implementation": {
            "builder": file_fingerprint(Path(__file__).with_name("build_db_v1_recovery_d0_d4.py"), with_sha256=True),
            "auditor": file_fingerprint(Path(__file__).resolve(), with_sha256=True),
        },
        "runtime": runtime_snapshot(project_root),
        "next_gate": "separate researcher approval before D4 exact-ID corpus materialization/MFA",
    }
    atomic_write_json(d_root / "OUTPUT_MANIFEST.json", manifest)
    return manifest


def audit(args: argparse.Namespace) -> dict:
    project_root = args.project_root.resolve()
    ac_root = args.ac_root.resolve()
    d_root = args.output_root.resolve()
    d0 = load_json(d_root / "D0_INPUT_CONTRACT.json")
    if d0.get("status") != "passed_read_only_contract" or d0["scope"]["total"] != 817_310:
        raise RuntimeError("D0 contract not passed")
    for record in d0["inputs"].values():
        verify_record(record)

    totals, d1_ids = audit_d1(ac_root, d_root)
    for status, expected in EXPECTED_STATUS.items():
        if totals[status] != expected:
            raise RuntimeError(f"D1 status total mismatch: {status}")
    for reason, expected in EXPECTED_REASONS.items():
        if totals[f"reason:{reason}"] != expected:
            raise RuntimeError(f"D1 reason total mismatch: {reason}")
    shard_manifest = load_json(d_root / "D1_recovery_ledger" / "D1_SHARD_MANIFEST.json")
    if (
        shard_manifest.get("status") != "passed_exact_id_routing"
        or shard_manifest.get("recovery_total") != 817_310
        or sum(int(row["utterance_count"]) for row in shard_manifest.get("shards", [])) != 817_310
        or any(int(row["session_count"]) <= 0 for row in shard_manifest.get("shards", []))
    ):
        raise RuntimeError("D1 shard manifest accounting failed")
    d2_counts, technical_ids, technical_rows = audit_d2(d_root, d1_ids)
    d2_summary = load_json(d_root / "D2_technical_audit" / "D2_SUMMARY.json")
    d2_classes = {key: value for key, value in d2_counts.items() if not key.startswith("reason:")}
    if (
        d2_summary.get("status") != "passed_read_only_audit"
        or d2_summary.get("technical_total") != 98_946
        or d2_summary.get("recoverability_classes") != d2_classes
        or d2_summary.get("mutations") != 0
    ):
        raise RuntimeError("D2 summary accounting failed")
    d3 = audit_d3(ac_root, d_root)
    d4 = audit_d4(d_root, technical_rows)
    build_summary = load_json(d_root / "BUILD_SUMMARY.json")
    if build_summary.get("status") != "passed_stopped_before_materialization_and_mfa":
        raise RuntimeError("build summary is not passed")
    if any(build_summary["mutation"].values()):
        raise RuntimeError("build summary records a forbidden mutation")
    report = {
        "schema_version": "research_db_v1_recovery_d0_d4_independent_audit.v1",
        "status": "passed_stopped_before_materialization_and_mfa",
        "recorded_at": now_iso(), "recovery_plan_id": D_ID,
        "counts": {
            "d1_status": {key: totals[key] for key in EXPECTED_STATUS},
            "d1_reason": {key: totals[f"reason:{key}"] for key in EXPECTED_REASONS},
            "d1_total": sum(EXPECTED_STATUS.values()),
            "d2_total": len(technical_ids), "d2_classes": dict(d2_counts),
            "d3": d3, "d4": d4,
        },
        "hard_failures": {
            "input_fingerprint_mismatch": 0, "D1_missing_or_duplicate_or_aligned_ids": 0,
            "D1_status_or_reason_drift": 0, "D2_current_path_state_drift": 0,
            "D2_missing_source_join": 0, "D3_frequency_mismatch": 0,
            "automatic_pronunciation_decisions": 0, "D4_selection_mismatch": 0,
            "base_r3_mutations": 0, "materialization_or_mfa_started": 0,
        },
        "gate": "HOLD before recovery file materialization and MFA",
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(d_root / "INDEPENDENT_AUDIT.json", report)
    seal_output_manifest(d_root, project_root)
    print(f"[OK] independent D0-D4 audit passed: {d_root}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ac-root", type=Path, default=PROJECT_ROOT / "outputs" / "releases" / AC_ID)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs" / "releases" / D_ID)
    args = parser.parse_args()
    audit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
