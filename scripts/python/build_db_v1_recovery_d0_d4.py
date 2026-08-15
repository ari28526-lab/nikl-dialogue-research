#!/usr/bin/env python3
"""Build the read-only D0--D4 recovery planning package.

The command reads the frozen A--C release and r3 evidence, but it never creates
an MFA corpus, runs MFA, or edits a database/TextGrid/raw WAV.  It stops at a
closed pre-execution gate after producing exact-ID ledgers, read-only
recoverability evidence, a pronunciation-type compression, and one bounded
diagnostic shard.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Iterator

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
YEARS = tuple(str(year) for year in range(2020, 2026))
R3_ID = "common_pron_mfa_r3_20260809"
AC_ID = "nikl_dialogue_research_db_v1_0_0_rc0_20260815"
D_ID = "nikl_dialogue_research_db_v1_recovery_d0_d4_20260815"
EXPECTED = {
    "pre_mfa_technical_exclusion": 95_860,
    "post_mfa_technical_exclusion": 3_086,
    "pronunciation_followup": 718_364,
}
EXPECTED_REASON_COUNTS = {
    "audio_pairing_unresolved": 95_798,
    "text_duration_impossible": 60,
    "audio_unusable": 2,
    "mfa_alignment_missing": 3_061,
    "mfa_feature_generation_failed": 25,
}

D1_FIELDS = [
    "year", "utt_id", "session_id", "source_csv", "primary_status",
    "status_family", "reason_codes_json", "reason_key", "recovery_family",
    "recovery_shard_id", "recovery_priority", "recovery_action",
    "recovery_eligibility", "needs_researcher_review", "alignment_scope",
    "evidence_key", "year_input_contract_id", "alignment_contract_id",
]
D2_FIELDS = [
    "year", "utt_id", "session_id", "source_csv", "primary_status",
    "reason_code", "form", "original_form", "tagged", "start", "end",
    "dur", "pron_reference_status", "align_warn", "canonical_session_path",
    "canonical_session_exists", "canonical_wav_path", "canonical_wav_exists",
    "canonical_wav_bytes", "r3_corpus_wav_path", "r3_corpus_wav_exists",
    "r3_corpus_wav_bytes", "r3_corpus_lab_path", "r3_corpus_lab_exists",
    "r3_corpus_lab_bytes", "recoverability_class", "next_action",
    "data_mutation_performed",
]
D3_FIELDS = [
    "token_role", "token", "utterance_links", "count_2020", "count_2021",
    "count_2022", "count_2023", "count_2024", "count_2025",
    "catalog_found", "catalog_total_occurrences", "orth_roman",
    "rule_pron_hangul", "rule_pron_roman", "surface_rule_names",
    "dictionary_pron_hangul_json", "dictionary_pron_roman_json",
    "dictionary_source_refs_json", "planning_candidate_variant_count",
    "planning_candidate_phones_json", "planning_candidate_roman_json",
    "planning_status", "planning_source", "planning_reason",
    "planning_requires_policy_decision", "planning_zero_fallback_hold",
    "release_selection_class", "release_selected_variant_count",
    "release_selected_pron_phones_json", "release_selected_pron_roman_json",
    "release_selection_status", "release_selection_source",
    "release_selection_reason", "evidence_review_class",
    "automatic_pronunciation_decision_performed",
]
D4_FIELDS = [
    "run_order", "shard_id", "year", "utt_id", "session_id",
    "reason_code", "selection_rule", "form", "original_form",
    "r3_corpus_wav_path", "r3_corpus_wav_bytes", "r3_corpus_lab_path",
    "r3_corpus_lab_bytes", "recoverability_class",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_fingerprint(path: Path, expected: dict | None = None) -> dict:
    if not path.is_file():
        raise RuntimeError(f"required file missing: {path}")
    actual = file_fingerprint(path, with_sha256=True)
    if expected:
        for key in ("bytes", "sha256"):
            if key in expected and actual[key] != expected[key]:
                raise RuntimeError(f"fingerprint mismatch ({key}): {path}")
    return actual


def csv_rows(path: Path) -> Iterator[dict[str, str]]:
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


def write_gzip_csv(path: Path, fields: list[str], rows: Iterable[dict[str, object]]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.unlink(missing_ok=True)
    count = 0
    canonical = hashlib.sha256()
    try:
        with partial.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as text:
                    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
                    writer.writeheader()
                    for source in rows:
                        row = {field: str(source.get(field, "")) for field in fields}
                        writer.writerow(row)
                        canonical.update(
                            (row.get("year", "") + "\t" + row.get("utt_id", "") + "\t" +
                             row.get("token_role", "") + "\t" + row.get("token", "") + "\n").encode("utf-8")
                        )
                        count += 1
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return {
        **file_fingerprint(path, with_sha256=True),
        "rows": count,
        "canonical_key_sha256": canonical.hexdigest(),
    }


def json_list(raw: str, label: str) -> list[str]:
    value = json.loads(raw or "[]")
    if not isinstance(value, list):
        raise RuntimeError(f"expected JSON list: {label}")
    return [str(item) for item in value if str(item)]


def reason_key(reasons: list[str]) -> str:
    return "+".join(reason.replace(":", "_") for reason in sorted(reasons))


def route_fields(status: str, reasons: list[str], year: str) -> dict[str, str]:
    reason_set = set(reasons)
    key = reason_key(reasons)
    if status == "post_mfa_technical_exclusion":
        if "mfa_feature_generation_failed" in reason_set:
            family, priority, action = "post_mfa_feature", "P0", "diagnose_feature_generation"
        else:
            family, priority, action = "post_mfa_alignment", "P0", "diagnose_alignment_missing"
        eligibility = "materialized_input_diagnostic"
    elif status == "pre_mfa_technical_exclusion":
        if "text_duration_impossible" in reason_set:
            family, priority, action = "timing_metadata", "P1", "audit_timing_metadata"
        elif "audio_unusable" in reason_set:
            family, priority, action = "audio_integrity", "P1", "preserve_and_review_audio_integrity"
        else:
            family, priority, action = "audio_identity_topology", "P2", "audit_audio_identity_topology"
        eligibility = "read_only_recoverability_audit"
    elif "pronunciation_policy_token" in reason_set:
        family, priority, action = "pronunciation_policy", "P3", "review_pronunciation_policy_evidence"
        eligibility = "linguistic_evidence_review"
    elif "routing_class:empty_reference" in reason_set:
        family, priority, action = "pronunciation_empty_reference", "P3", "audit_empty_reference"
        eligibility = "linguistic_evidence_review"
    else:
        family, priority, action = "pronunciation_evidence", "P4", "review_pronunciation_type_evidence"
        eligibility = "linguistic_evidence_review"
    return {
        "reason_key": key,
        "recovery_family": family,
        "recovery_shard_id": f"D1_{year}_{family}_{key}",
        "recovery_priority": priority,
        "recovery_action": action,
        "recovery_eligibility": eligibility,
    }


def build_d1_year(ac_ledger: Path, output_path: Path) -> tuple[dict, list[dict[str, str]], Counter[str]]:
    technical: list[dict[str, str]] = []
    counts: Counter[str] = Counter()

    def rows() -> Iterator[dict[str, str]]:
        for row in csv_rows(ac_ledger):
            status = row["primary_status"]
            if status == "aligned_safe_body":
                continue
            if status not in EXPECTED:
                raise RuntimeError(f"unexpected A-C status: {status}")
            reasons = json_list(row["reason_codes_json"], row["utt_id"])
            routed = route_fields(status, reasons, row["year"])
            output = {field: row.get(field, "") for field in D1_FIELDS}
            output.update(routed)
            output["needs_researcher_review"] = "true"
            counts[status] += 1
            for reason in reasons:
                counts[f"reason:{reason}"] += 1
            if status.endswith("technical_exclusion"):
                technical.append({**row, **routed})
            yield output

    info = write_gzip_csv(output_path, D1_FIELDS, rows())
    return info, technical, counts


def load_source_rows(search_root: Path, technical: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    requested: dict[str, set[str]] = defaultdict(set)
    for row in technical:
        requested[row["source_csv"]].add(row["utt_id"])
    found: dict[str, dict[str, str]] = {}
    for index, (relative, utt_ids) in enumerate(sorted(requested.items()), 1):
        source_path = search_root / Path(relative)
        if not source_path.is_file():
            raise RuntimeError(f"search-master source missing: {source_path}")
        remaining = set(utt_ids)
        for source in csv_rows(source_path):
            utt_id = source.get("utt_id", "")
            if utt_id in remaining:
                if utt_id in found:
                    raise RuntimeError(f"duplicate technical source row: {utt_id}")
                found[utt_id] = source
                remaining.remove(utt_id)
                if not remaining:
                    break
        if remaining:
            raise RuntimeError(f"technical IDs absent from {source_path}: {sorted(remaining)[:3]}")
        if index % 500 == 0:
            print(f"  source CSV {index}/{len(requested)}", flush=True)
    if len(found) != len(technical):
        raise RuntimeError(f"technical source join incomplete: {len(found)} != {len(technical)}")
    return found


def stat_fields(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "false", "0"
    return "true", str(path.stat().st_size)


def classify_technical(status: str, reasons: list[str], source_exists: bool, corpus_wav: bool, corpus_lab: bool) -> tuple[str, str]:
    reason_set = set(reasons)
    if status == "post_mfa_technical_exclusion":
        if not (corpus_wav and corpus_lab):
            return "blocked_missing_materialized_input", "restore_exact_materialized_wav_lab_before_diagnostic"
        if "mfa_feature_generation_failed" in reason_set:
            return "ready_for_feature_failure_diagnostic", "run_bounded_feature_diagnostic_after_gate"
        return "ready_for_alignment_diagnostic", "run_bounded_alignment_diagnostic_after_gate"
    if "audio_unusable" in reason_set:
        return "preserve_audio_unusable_research_decision", "researcher_audio_integrity_review"
    if "text_duration_impossible" in reason_set:
        if source_exists:
            return "requires_timing_metadata_review", "compare_csv_timing_against_exact_wav"
        return "blocked_missing_audio", "recover_audio_before_timing_review"
    if source_exists:
        return "requires_audio_identity_review", "verify_same_id_audio_identity_not_filename_only"
    return "requires_session_audio_remap", "recover_or_remap_within_session_without_auto_acceptance"


def build_d2_year(
    *, year: str, technical: list[dict[str, str]], source_rows: dict[str, dict[str, str]],
    wav_root: Path, r3_corpus_root: Path, output_path: Path,
) -> tuple[dict, Counter[str], list[dict[str, str]]]:
    counts: Counter[str] = Counter()
    retained: list[dict[str, str]] = []

    def rows() -> Iterator[dict[str, str]]:
        for item in technical:
            source = source_rows[item["utt_id"]]
            reasons = json_list(item["reason_codes_json"], item["utt_id"])
            session = item["session_id"]
            canonical_session = wav_root / session
            canonical_wav = canonical_session / f"{item['utt_id']}.wav"
            corpus_wav_path = r3_corpus_root / year / session / f"{item['utt_id']}.wav"
            corpus_lab_path = corpus_wav_path.with_suffix(".lab")
            canonical_exists, canonical_bytes = stat_fields(canonical_wav)
            corpus_wav_exists, corpus_wav_bytes = stat_fields(corpus_wav_path)
            corpus_lab_exists, corpus_lab_bytes = stat_fields(corpus_lab_path)
            klass, action = classify_technical(
                item["primary_status"], reasons,
                canonical_exists == "true", corpus_wav_exists == "true", corpus_lab_exists == "true",
            )
            counts[klass] += 1
            for reason in reasons:
                if not reason.startswith("routing_class:"):
                    counts[f"reason:{reason}"] += 1
            row = {
                "year": year, "utt_id": item["utt_id"], "session_id": session,
                "source_csv": item["source_csv"], "primary_status": item["primary_status"],
                "reason_code": "+".join(r for r in reasons if not r.startswith("routing_class:")),
                "form": source.get("form", ""), "original_form": source.get("original_form", ""),
                "tagged": source.get("tagged", ""), "start": source.get("start", ""),
                "end": source.get("end", ""), "dur": source.get("dur", ""),
                "pron_reference_status": source.get("pron_reference_status", ""),
                "align_warn": source.get("align_warn", ""),
                "canonical_session_path": str(canonical_session),
                "canonical_session_exists": str(canonical_session.is_dir()).lower(),
                "canonical_wav_path": str(canonical_wav), "canonical_wav_exists": canonical_exists,
                "canonical_wav_bytes": canonical_bytes,
                "r3_corpus_wav_path": str(corpus_wav_path), "r3_corpus_wav_exists": corpus_wav_exists,
                "r3_corpus_wav_bytes": corpus_wav_bytes,
                "r3_corpus_lab_path": str(corpus_lab_path), "r3_corpus_lab_exists": corpus_lab_exists,
                "r3_corpus_lab_bytes": corpus_lab_bytes,
                "recoverability_class": klass, "next_action": action,
                "data_mutation_performed": "false",
            }
            retained.append(row)
            yield row

    info = write_gzip_csv(output_path, D2_FIELDS, rows())
    return info, counts, retained


def collect_pronunciation_tokens(pron_paths: dict[str, Path]) -> tuple[dict[tuple[str, str], Counter[str]], Counter[str]]:
    token_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    routing: Counter[str] = Counter()
    for year, path in pron_paths.items():
        for row in csv_rows(path):
            routing[f"year:{year}"] += 1
            routing[f"routing:{row.get('routing_class', '')}"] += 1
            has_token = False
            for field, role in (
                ("hold_tokens_json", "hold"),
                ("policy_tokens_json", "policy"),
                ("unknown_tokens_json", "unknown"),
            ):
                tokens = json_list(row.get(field, ""), f"{year}:{row['utt_id']}:{field}")
                if len(tokens) != len(set(tokens)):
                    raise RuntimeError(f"duplicate token in one pronunciation row: {row['utt_id']} {field}")
                for token in tokens:
                    has_token = True
                    token_counts[(role, token)][year] += 1
                    token_counts[(role, token)]["total"] += 1
                    routing[f"role_links:{role}"] += 1
            if not has_token:
                routing["utterances_without_explicit_token"] += 1
    return token_counts, routing


def load_catalog(catalog_path: Path, wanted: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in csv_rows(catalog_path):
        token = row["token"]
        if token in wanted:
            if token in result:
                raise RuntimeError(f"duplicate type catalog token: {token}")
            result[token] = row
    return result


def nonempty_json_list(raw: str) -> bool:
    try:
        return bool(json.loads(raw or "[]"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid catalog JSON list") from exc


def pronunciation_review_class(role: str, catalog: dict[str, str] | None) -> str:
    if role == "policy":
        return "policy_decision_required"
    if role == "unknown" or catalog is None:
        return "token_inventory_investigation"
    if int(catalog.get("release_selected_variant_count", "0") or 0) > 0:
        return "routing_consistency_review"
    if int(catalog.get("planning_candidate_variant_count", "0") or 0) > 0:
        return "candidate_evidence_review"
    if nonempty_json_list(catalog.get("dictionary_pron_hangul_json", "")):
        return "dictionary_evidence_review"
    return "zero_fallback_hold"


def build_d3(
    *, token_counts: dict[tuple[str, str], Counter[str]], catalog: dict[str, dict[str, str]],
    output_path: Path, priority_path: Path,
) -> tuple[dict, dict, Counter[str]]:
    rows: list[dict[str, str]] = []
    classes: Counter[str] = Counter()
    copy_fields = [field for field in D3_FIELDS if field not in {
        "token_role", "token", "utterance_links", *(f"count_{year}" for year in YEARS),
        "catalog_found", "catalog_total_occurrences", "evidence_review_class",
        "automatic_pronunciation_decision_performed",
    }]
    for (role, token), counts in token_counts.items():
        evidence = catalog.get(token)
        review_class = pronunciation_review_class(role, evidence)
        classes[review_class] += 1
        row = {
            "token_role": role, "token": token, "utterance_links": str(counts["total"]),
            "catalog_found": str(evidence is not None).lower(),
            "catalog_total_occurrences": (evidence or {}).get("total_occurrences", ""),
            "evidence_review_class": review_class,
            "automatic_pronunciation_decision_performed": "false",
        }
        for year in YEARS:
            row[f"count_{year}"] = str(counts[year])
        for field in copy_fields:
            row[field] = (evidence or {}).get(field, "")
        rows.append(row)
    rows.sort(key=lambda row: (row["token_role"], -int(row["utterance_links"]), row["token"]))
    full_info = write_gzip_csv(output_path, D3_FIELDS, rows)
    priority = sorted(rows, key=lambda row: (-int(row["utterance_links"]), row["token_role"], row["token"]))[:1000]
    priority_info = write_gzip_csv(priority_path, D3_FIELDS, priority)
    return full_info, priority_info, classes


def choose_first_shard(technical_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    feature = sorted(
        (row for row in technical_rows if row["reason_code"] == "mfa_feature_generation_failed"),
        key=lambda row: (row["year"], row["utt_id"]),
    )
    alignment_by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in technical_rows:
        if row["reason_code"] == "mfa_alignment_missing":
            alignment_by_year[row["year"]].append(row)
    selected = list(feature)
    for year in YEARS:
        seen_sessions: set[str] = set()
        for row in sorted(alignment_by_year[year], key=lambda item: (item["session_id"], item["utt_id"])):
            if row["session_id"] in seen_sessions:
                continue
            if row["recoverability_class"] != "ready_for_alignment_diagnostic":
                continue
            selected.append(row)
            seen_sessions.add(row["session_id"])
            if len(seen_sessions) == 5:
                break
        if len(seen_sessions) != 5:
            raise RuntimeError(f"{year}: could not select five unique-session alignment diagnostics")
    output: list[dict[str, str]] = []
    for order, row in enumerate(selected, 1):
        selection = "all_feature_generation_failures" if row["reason_code"] == "mfa_feature_generation_failed" else "first_five_unique_sessions_by_session_and_utt"
        output.append({
            "run_order": str(order), "shard_id": "D4_POST_MFA_DIAGNOSTIC_0001",
            "year": row["year"], "utt_id": row["utt_id"], "session_id": row["session_id"],
            "reason_code": row["reason_code"], "selection_rule": selection,
            "form": row["form"], "original_form": row["original_form"],
            "r3_corpus_wav_path": row["r3_corpus_wav_path"],
            "r3_corpus_wav_bytes": row["r3_corpus_wav_bytes"],
            "r3_corpus_lab_path": row["r3_corpus_lab_path"],
            "r3_corpus_lab_bytes": row["r3_corpus_lab_bytes"],
            "recoverability_class": row["recoverability_class"],
        })
    return output


def write_text(path: Path, text: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    os.replace(partial, path)
    return file_fingerprint(path, with_sha256=True)


def write_d1_d2_summaries(output_root: Path) -> dict[str, dict]:
    shards: dict[str, dict[str, object]] = {}
    d2_years: dict[str, dict[str, object]] = {}
    d2_total: Counter[str] = Counter()
    for year in YEARS:
        d1_path = output_root / "D1_recovery_ledger" / f"{year}_recovery_routing.csv.gz"
        for row in csv_rows(d1_path):
            shard_id = row["recovery_shard_id"]
            if shard_id not in shards:
                shards[shard_id] = {
                    "shard_id": shard_id, "year": year,
                    "primary_status": row["primary_status"],
                    "reason_key": row["reason_key"],
                    "recovery_family": row["recovery_family"],
                    "recovery_priority": row["recovery_priority"],
                    "recovery_action": row["recovery_action"],
                    "recovery_eligibility": row["recovery_eligibility"],
                    "utterance_count": 0, "sessions": set(),
                    "first_utt_id": row["utt_id"], "last_utt_id": row["utt_id"],
                }
            record = shards[shard_id]
            record["utterance_count"] = int(record["utterance_count"]) + 1
            sessions = record["sessions"]
            assert isinstance(sessions, set)
            sessions.add(row["session_id"])
            record["last_utt_id"] = row["utt_id"]
        classes: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        for row in csv_rows(output_root / "D2_technical_audit" / f"{year}_technical_recoverability.csv.gz"):
            classes[row["recoverability_class"]] += 1
            reasons[row["reason_code"]] += 1
        d2_years[year] = {
            "rows": sum(classes.values()),
            "recoverability_classes": dict(classes),
            "reason_counts": dict(reasons),
        }
        d2_total.update(classes)
    shard_rows = []
    for record in sorted(
        shards.values(),
        key=lambda item: (str(item["recovery_priority"]), str(item["year"]), str(item["shard_id"])),
    ):
        sessions = record.pop("sessions")
        assert isinstance(sessions, set)
        record["session_count"] = len(sessions)
        shard_rows.append(record)
    d1_manifest = {
        "schema_version": "research_db_v1_recovery_shard_manifest.v1",
        "status": "passed_exact_id_routing",
        "recorded_at": now_iso(),
        "recovery_total": sum(int(row["utterance_count"]) for row in shard_rows),
        "shard_count": len(shard_rows),
        "shards": shard_rows,
        "note": "Shard rows are routing units, not final exclusions or automatic approvals.",
    }
    d1_path = output_root / "D1_recovery_ledger" / "D1_SHARD_MANIFEST.json"
    atomic_write_json(d1_path, d1_manifest)
    d2_summary = {
        "schema_version": "research_db_v1_technical_recoverability_summary.v1",
        "status": "passed_read_only_audit",
        "recorded_at": now_iso(),
        "technical_total": sum(d2_total.values()),
        "recoverability_classes": dict(d2_total),
        "years": d2_years,
        "interpretation": {
            "requires_audio_identity_review": "An exact-name WAV exists, but filename equality is not accepted as proof of utterance identity.",
            "requires_session_audio_remap": "The expected exact-name WAV is absent; recovery requires session-bounded identity/topology evidence.",
            "ready_for_alignment_diagnostic": "The frozen r3 WAV/LAB pair exists; bounded diagnostic is possible after a separate gate.",
            "ready_for_feature_failure_diagnostic": "The frozen r3 WAV/LAB pair exists; feature-generation diagnostics are first priority.",
            "requires_timing_metadata_review": "Audio exists, but CSV time metadata must be reconciled before alignment.",
            "preserve_audio_unusable_research_decision": "Retain the explicit audio-integrity decision; do not auto-recover.",
        },
        "mutations": 0,
    }
    d2_path = output_root / "D2_technical_audit" / "D2_SUMMARY.json"
    atomic_write_json(d2_path, d2_summary)
    return {
        "d1_shard_manifest": file_fingerprint(d1_path, with_sha256=True),
        "d2_summary": file_fingerprint(d2_path, with_sha256=True),
    }


def build(args: argparse.Namespace) -> dict:
    project_root = args.project_root.resolve()
    ac_root = args.ac_root.resolve()
    common_root = args.common_root.resolve()
    r3_root = args.r3_root.resolve()
    search_root = args.search_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    ac_output_path = ac_root / "OUTPUT_MANIFEST.json"
    ac_base_path = ac_root / "BASE_RELEASE_MANIFEST_2020_2025.json"
    ac_qa_path = ac_root / "QA_REPORT.json"
    ac_output = load_json(ac_output_path)
    ac_base = load_json(ac_base_path)
    ac_qa = load_json(ac_qa_path)
    if ac_output.get("status") != "passed" or ac_qa.get("status") != "passed":
        raise RuntimeError("A-C release is not passed")
    if ac_base["scope"]["technical_followup_utterances"] != 98_946 or ac_base["scope"]["pronunciation_followup_utterances"] != 718_364:
        raise RuntimeError("A-C followup scope changed")

    type_manifest_path = common_root / "05_research_database" / "TYPE_CATALOG_MANIFEST.json"
    type_manifest = load_json(type_manifest_path)
    catalog_path = Path(type_manifest["output"]["path"])
    cleanup_path = project_root / "outputs" / "reports" / "mfa_r3_storage_cleanup_review_20260815" / "APPLY_RESULT.json"
    cleanup = load_json(cleanup_path)
    if cleanup.get("status") != "passed" or cleanup.get("deleted_files") != 126:
        raise RuntimeError("post-QC cleanup evidence is not passed")
    drive = shutil.disk_usage("D:/")

    d0 = {
        "schema_version": "research_db_v1_recovery_d0_contract.v1",
        "status": "passed_read_only_contract",
        "recorded_at": now_iso(),
        "recovery_plan_id": D_ID,
        "scope": {
            "technical_followup": 98_946,
            "pronunciation_followup": 718_364,
            "total": 817_310,
            "aligned_r3_body_out_of_scope": 4_286_046,
        },
        "inputs": {
            "ac_output_manifest": checked_fingerprint(ac_output_path),
            "ac_base_manifest": checked_fingerprint(ac_base_path),
            "ac_qa": checked_fingerprint(ac_qa_path),
            "type_catalog_manifest": checked_fingerprint(type_manifest_path),
            "type_catalog": checked_fingerprint(catalog_path, type_manifest["output"]),
            "post_qc_cleanup_apply": checked_fingerprint(cleanup_path),
        },
        "storage": {
            "D_role": "canonical active corpus/r3/recovery workspace",
            "E_role": "future separately approved read-only archive only",
            "D_volume_label": "DATA_SSD",
            "D_free_bytes_at_contract": drive.free,
            "D_free_gib_at_contract": round(drive.free / (1024 ** 3), 3),
            "planned_future_root_not_created": str(Path(f"D:/mfa_eojeol/recovery/{R3_ID}")),
        },
        "frozen_invariants": {
            "raw_audio_modified": False,
            "r3_corpus_modified": False,
            "r3_database_modified": False,
            "r3_textgrid_modified": False,
            "mfa_run_performed": False,
            "recovery_files_materialized": False,
            "whole_year_rerun_authorized": False,
            "automatic_linguistic_realization_decision_allowed": False,
            "dictionary_rule_g2p_are_reference_evidence_not_actual_realization": True,
            "exact_id_append_only_recovery_required": True,
        },
        "stage_label_resolution": {
            "canonical_current_D0_D4": "reason-specific recovery planning and pre-execution gate",
            "later_stage": "target extraction/query/manual overlay/session JSON after recovery accounting",
            "note": "Older roadmap letters are superseded only in label, not in scientific scope.",
        },
    }
    atomic_write_json(output_root / "D0_INPUT_CONTRACT.json", d0)

    all_counts: Counter[str] = Counter()
    all_d2_counts: Counter[str] = Counter()
    all_technical_rows: list[dict[str, str]] = []
    pron_paths: dict[str, Path] = {}
    year_manifests: dict[str, dict] = {}
    for year in YEARS:
        print(f"[{year}] D1 routing and D2 read-only audit", flush=True)
        year_contract = load_json(common_root / "03_year_input_contracts" / year / f"YEAR_INPUT_CONTRACT_{year}.json")
        wav_root = Path(year_contract["corpus_binding"]["recovered_wav_root"])
        ac_ledger = ac_root / "ledgers" / f"{year}_utterance_status.csv.gz"
        d1_path = output_root / "D1_recovery_ledger" / f"{year}_recovery_routing.csv.gz"
        d1_info, technical, d1_counts = build_d1_year(ac_ledger, d1_path)
        source_rows = load_source_rows(search_root, technical)
        d2_path = output_root / "D2_technical_audit" / f"{year}_technical_recoverability.csv.gz"
        d2_info, d2_counts, d2_rows = build_d2_year(
            year=year, technical=technical, source_rows=source_rows,
            wav_root=wav_root, r3_corpus_root=r3_root / "corpus", output_path=d2_path,
        )
        pron_path = Path(year_contract["outputs"]["pronunciation_followup_ids"]["path"])
        pron_paths[year] = pron_path
        manifest = {
            "schema_version": "research_db_v1_recovery_year_checkpoint.v1",
            "status": "passed",
            "recorded_at": now_iso(), "year": year,
            "inputs": {
                "ac_ledger": checked_fingerprint(ac_ledger),
                "year_input_contract": checked_fingerprint(common_root / "03_year_input_contracts" / year / f"YEAR_INPUT_CONTRACT_{year}.json"),
                "pronunciation_followup": checked_fingerprint(pron_path, year_contract["outputs"]["pronunciation_followup_ids"]),
            },
            "d1_counts": dict(d1_counts), "d1_ledger": d1_info,
            "d2_counts": dict(d2_counts), "d2_audit": d2_info,
            "mutations": 0,
        }
        manifest_path = output_root / "checkpoints" / f"{year}_D1_D2_MANIFEST.json"
        atomic_write_json(manifest_path, manifest)
        year_manifests[year] = {**manifest, "manifest": checked_fingerprint(manifest_path)}
        all_counts.update(d1_counts)
        all_d2_counts.update(d2_counts)
        all_technical_rows.extend(d2_rows)

    for status, count in EXPECTED.items():
        if all_counts[status] != count:
            raise RuntimeError(f"D1 total mismatch: {status}: {all_counts[status]} != {count}")
    for reason, count in EXPECTED_REASON_COUNTS.items():
        if all_counts[f"reason:{reason}"] != count:
            raise RuntimeError(f"D1 reason mismatch: {reason}: {all_counts[f'reason:{reason}']} != {count}")

    derived_summaries = write_d1_d2_summaries(output_root)

    print("[D3] pronunciation type compression", flush=True)
    token_counts, routing_counts = collect_pronunciation_tokens(pron_paths)
    catalog = load_catalog(catalog_path, {token for _, token in token_counts})
    d3_path = output_root / "D3_pronunciation_types" / "pronunciation_type_summary.csv.gz"
    priority_path = output_root / "D3_pronunciation_types" / "PRIORITY_TOP_1000.csv.gz"
    d3_info, priority_info, evidence_classes = build_d3(
        token_counts=token_counts, catalog=catalog, output_path=d3_path,
        priority_path=priority_path,
    )
    d3_manifest = {
        "schema_version": "research_db_v1_recovery_pronunciation_types.v1",
        "status": "passed_reference_evidence_only",
        "recorded_at": now_iso(),
        "pronunciation_followup_utterances": 718_364,
        "role_and_routing_counts": dict(routing_counts),
        "distinct_role_token_rows": len(token_counts),
        "distinct_tokens": len({token for _, token in token_counts}),
        "catalog_matches": len(catalog),
        "catalog_missing": len({token for _, token in token_counts} - set(catalog)),
        "evidence_review_classes": dict(evidence_classes),
        "full_summary": d3_info, "priority_summary": priority_info,
        "automatic_pronunciation_decisions": 0,
        "interpretation": "Dictionary/rule/G2P candidates are reference evidence; neither MFA phones nor these candidates establish actual realization.",
    }
    atomic_write_json(output_root / "D3_pronunciation_types" / "D3_MANIFEST.json", d3_manifest)

    print("[D4] bounded first diagnostic shard and closed gate", flush=True)
    first_shard = choose_first_shard(all_technical_rows)
    first_path = output_root / "D4_first_shard" / "FIRST_SHARD.csv.gz"
    first_info = write_gzip_csv(first_path, D4_FIELDS, first_shard)
    wav_bytes = sum(int(row["r3_corpus_wav_bytes"]) for row in first_shard)
    lab_bytes = sum(int(row["r3_corpus_lab_bytes"]) for row in first_shard)
    reason_counts = Counter(row["reason_code"] for row in first_shard)
    year_counts = Counter(row["year"] for row in first_shard)
    gate = {
        "schema_version": "research_db_v1_recovery_first_shard_gate.v1",
        "status": "hold_before_materialization_and_mfa",
        "recorded_at": now_iso(),
        "shard_id": "D4_POST_MFA_DIAGNOSTIC_0001",
        "selection": {
            "all_feature_generation_failures": EXPECTED_REASON_COUNTS["mfa_feature_generation_failed"],
            "alignment_missing_unique_session_sample_per_year": 5,
            "generic_pilot_repeated": False,
            "scientific_purpose": "Validate the recovery path and diagnose the most immediately materialized technical failures without reopening the frozen yearly body.",
        },
        "counts": {"rows": len(first_shard), "by_reason": dict(reason_counts), "by_year": dict(year_counts)},
        "first_shard": first_info,
        "capacity": {
            "source_wav_bytes": wav_bytes, "source_lab_bytes": lab_bytes,
            "minimum_D_free_bytes_before_execution": 20 * 1024 ** 3,
            "D_free_bytes_observed_now": drive.free,
            "bounded_working_budget_bytes": 4 * 1024 ** 3,
            "capacity_precheck_passed": drive.free >= 20 * 1024 ** 3,
            "note": "The 4 GiB budget is a conservative shard workspace ceiling, not a prediction of exact MFA use.",
        },
        "execution": {
            "preflight_command": f'& "$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "{project_root}\\scripts\\run_db_v1_recovery_first_shard.ps1" -PreflightOnly',
            "future_execution_command_after_separate_approval": f'& "$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "{project_root}\\scripts\\run_db_v1_recovery_first_shard.ps1" -ApprovalContract "<APPROVED_CONTRACT.json>"',
            "approval_contract_present": False,
            "files_materialized": False,
            "mfa_run": False,
            "runner_scope": "This D0-D4 runner validates and opens the gate only; corpus materialization and MFA remain the next separately approved action.",
        },
        "base_invariants": {"r3_body_mutated": False, "whole_year_rerun": False, "exact_id_only": True},
    }
    atomic_write_json(output_root / "D4_first_shard" / "PRE_MFA_GATE.json", gate)

    summary = {
        "schema_version": "research_db_v1_recovery_d0_d4_build.v1",
        "status": "passed_stopped_before_materialization_and_mfa",
        "recorded_at": now_iso(), "recovery_plan_id": D_ID,
        "counts": {
            "recovery_total": sum(EXPECTED.values()),
            "technical": EXPECTED["pre_mfa_technical_exclusion"] + EXPECTED["post_mfa_technical_exclusion"],
            "pronunciation": EXPECTED["pronunciation_followup"],
            "d1_status": {key: all_counts[key] for key in EXPECTED},
            "d1_technical_reasons": {key: all_counts[f"reason:{key}"] for key in EXPECTED_REASON_COUNTS},
            "d2_recoverability": dict(all_d2_counts),
            "d3_distinct_role_token_rows": len(token_counts),
            "d4_first_shard": len(first_shard),
        },
        "year_checkpoints": year_manifests,
        "derived_summaries": derived_summaries,
        "d3_manifest": checked_fingerprint(output_root / "D3_pronunciation_types" / "D3_MANIFEST.json"),
        "d4_gate": checked_fingerprint(output_root / "D4_first_shard" / "PRE_MFA_GATE.json"),
        "mutation": {
            "raw_audio": False, "r3_corpus": False, "r3_database": False,
            "r3_textgrid": False, "recovery_corpus_created": False, "mfa_run": False,
        },
        "next_gate": "Researcher reviews D2/D3/D4 summaries and separately approves exact D4 shard materialization/MFA.",
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(output_root / "BUILD_SUMMARY.json", summary)

    methods = f"""# D0–D4 recovery planning methods

This package partitions the 817,310 follow-up utterances left outside the frozen
2020–2025 r3 body. It preserves the A–C accounting identity and does not alter
the 4,286,046 aligned utterances, their databases, or their 6-tier TextGrids.

## D0 — frozen input contract

The A–C output manifest, base manifest, QA report, pronunciation type catalog,
and post-QC storage cleanup result are SHA-bound. D: remains the canonical data
drive. No recovery directory on D: was created by this stage.

## D1 — reason-specific exact-ID ledger

Every follow-up utterance occurs exactly once, with year, session, source CSV,
primary status, reason code, recovery family, priority, and shard identifier.
The partition is 95,860 pre-MFA technical + 3,086 post-MFA technical + 718,364
pronunciation follow-up = 817,310. This is routing, not final exclusion.

## D2 — technical recoverability audit

The 98,946 technical rows were joined back to the frozen search-master CSV and
checked read-only against canonical source WAV paths and, for post-MFA cases,
the already materialized r3 WAV/LAB pair. Filename existence alone is not
treated as proof of audio identity; audio-pairing cases therefore remain review
or remapping work rather than automatic recovery.

## D3 — pronunciation-type compression

The 718,364 pronunciation follow-up utterances were compressed by token role
(hold/policy/unknown), token, and year frequency, then linked to the frozen
pronunciation type catalog. Dictionary, rule, and G2P values are reference
evidence only. No candidate was declared the observed realization and no
linguistic decision was automatically approved.

## D4 — first bounded diagnostic shard

The first shard contains all 25 feature-generation failures and five
unique-session alignment-missing cases per year. It is a recovery-path
diagnostic cohort, not a repeated generic pilot. The gate is closed before any
file is copied or MFA is started.

Build status: `{summary['status']}`.
"""
    write_text(output_root / "METHODS_D0_D4.md", methods)
    runbook = f"""# D0–D4 runbook

Current state: **STOP before recovery corpus materialization and MFA**.

Read-only preflight command:

```powershell
& "$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "{project_root}\\scripts\\run_db_v1_recovery_first_shard.ps1" `
  -PreflightOnly
```

Do not replace `-PreflightOnly` until a separate, scope-bound researcher
approval contract exists for `D4_POST_MFA_DIAGNOSTIC_0001`. The frozen r3 body
must not be reused as a writable output and no whole-year rerun is authorized.
"""
    write_text(output_root / "RUNBOOK_STOP_BEFORE_MFA.md", runbook)
    print(f"[OK] D0-D4 built; stopped before materialization/MFA: {output_root}", flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ac-root", type=Path, default=PROJECT_ROOT / "outputs" / "releases" / AC_ID)
    parser.add_argument("--common-root", type=Path, default=Path(f"D:/mfa_common_pron/releases/{R3_ID}"))
    parser.add_argument("--r3-root", type=Path, default=Path(f"D:/mfa_eojeol/r3/{R3_ID}"))
    parser.add_argument("--search-root", type=Path, default=Path("D:/10_LAYERS/05_search_master_pre_mfa_staging/pre_mfa_v1_20260725"))
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs" / "releases" / D_ID)
    parser.add_argument("--derive-summaries-only", action="store_true")
    args = parser.parse_args()
    if args.derive_summaries_only:
        output_root = args.output_root.resolve()
        derived = write_d1_d2_summaries(output_root)
        summary_path = output_root / "BUILD_SUMMARY.json"
        summary = load_json(summary_path)
        summary["derived_summaries"] = derived
        summary["summary_refresh_recorded_at"] = now_iso()
        atomic_write_json(summary_path, summary)
        print(f"[OK] D1/D2 summaries derived from verified ledgers: {output_root}")
        return 0
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
