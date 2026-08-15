#!/usr/bin/env python3
"""Build the read-only A--C preparation package for research DB v1.

This command never runs MFA and never edits the frozen r3 corpus, databases,
TextGrids, or companion tables.  It binds their existing contracts, verifies
the six-year method identity, and materializes one exact-ID status ledger per
year.  Per-year manifests are checkpoints, so an interrupted run can resume
without rebuilding an already verified year.
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
from collections import Counter
from pathlib import Path
from typing import Iterator

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
YEARS = tuple(str(year) for year in range(2020, 2026))
RELEASE_ID = "common_pron_mfa_r3_20260809"
PREP_ID = "nikl_dialogue_research_db_v1_0_0_rc0_20260815"
LEDGER_FIELDS = [
    "year",
    "utt_id",
    "session_id",
    "source_csv",
    "primary_status",
    "status_family",
    "reason_codes_json",
    "mfa_expected",
    "textgrid_available",
    "followup_required",
    "alignment_scope",
    "evidence_key",
    "year_input_contract_id",
    "alignment_contract_id",
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
        raise RuntimeError(f"required file is missing: {path}")
    actual = file_fingerprint(path, with_sha256=True)
    if expected is not None:
        for key in ("bytes", "sha256"):
            if key in expected and actual[key] != expected[key]:
                raise RuntimeError(
                    f"fingerprint mismatch ({key}): {path}: "
                    f"{actual[key]} != {expected[key]}"
                )
    return actual


def csv_rows(path: Path) -> Iterator[dict[str, str]]:
    if path.suffix == ".gz":
        stream_context = gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    else:
        stream_context = path.open("r", encoding="utf-8-sig", newline="")
    with stream_context as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "utt_id" not in reader.fieldnames:
            raise RuntimeError(f"CSV utt_id header missing: {path}")
        yield from reader


def load_reason_map(path: Path, reason_field: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for line_number, row in enumerate(csv_rows(path), 2):
        utt_id = row["utt_id"].strip()
        if not utt_id:
            raise RuntimeError(f"blank utt_id at {path}:{line_number}")
        if utt_id in result:
            raise RuntimeError(f"duplicate utt_id at {path}:{line_number}: {utt_id}")
        raw = row.get(reason_field, "")
        if reason_field.endswith("_json"):
            values = json.loads(raw or "[]")
            if not isinstance(values, list):
                raise RuntimeError(f"reason list is not JSON array: {path}:{line_number}")
            result[utt_id] = sorted({str(value) for value in values if str(value)})
        else:
            value = str(raw or "").strip()
            result[utt_id] = [value] if value else []
    return result


def followup_reason_codes(row: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    for field, code in (
        ("hold_tokens_json", "pronunciation_hold_token"),
        ("policy_tokens_json", "pronunciation_policy_token"),
        ("unknown_tokens_json", "pronunciation_unknown_token"),
    ):
        values = json.loads(row.get(field, "") or "[]")
        if not isinstance(values, list):
            raise RuntimeError(f"{field} is not a JSON array for {row.get('utt_id')}")
        if values:
            reasons.append(code)
    routing_class = str(row.get("routing_class", "") or "").strip()
    if routing_class:
        reasons.append(f"routing_class:{routing_class}")
    return sorted(set(reasons))


def output_row(
    source: dict[str, str],
    *,
    status: str,
    family: str,
    reasons: list[str],
    mfa_expected: bool,
    textgrid_available: bool,
    followup_required: bool,
    alignment_scope: str,
    evidence_key: str,
    year_input_contract_id: str,
    alignment_contract_id: str,
) -> dict[str, str]:
    return {
        "year": source["year"],
        "utt_id": source["utt_id"],
        "session_id": source.get("session_id", ""),
        "source_csv": source.get("source_csv", ""),
        "primary_status": status,
        "status_family": family,
        "reason_codes_json": json.dumps(reasons, ensure_ascii=False, separators=(",", ":")),
        "mfa_expected": str(mfa_expected).lower(),
        "textgrid_available": str(textgrid_available).lower(),
        "followup_required": str(followup_required).lower(),
        "alignment_scope": alignment_scope,
        "evidence_key": evidence_key,
        "year_input_contract_id": year_input_contract_id,
        "alignment_contract_id": alignment_contract_id,
    }


def write_deterministic_gzip_csv(path: Path, rows: Iterator[dict[str, str]]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.unlink(missing_ok=True)
    canonical_digest = hashlib.sha256()
    count = 0
    try:
        with partial.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as text:
                    writer = csv.DictWriter(text, fieldnames=LEDGER_FIELDS, lineterminator="\n")
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)
                        canonical_digest.update(
                            (row["year"] + "\t" + row["utt_id"] + "\t" + row["primary_status"] + "\n").encode("utf-8")
                        )
                        count += 1
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return {
        **file_fingerprint(path, with_sha256=True),
        "rows": count,
        "canonical_year_utt_status_sha256": canonical_digest.hexdigest(),
    }


def year_ledger_rows(
    *,
    year: str,
    safe_path: Path,
    followup_path: Path,
    expected_path: Path,
    pre_reasons: dict[str, list[str]],
    post_reasons: dict[str, list[str]],
    year_input_contract_id: str,
    alignment_contract_id: str,
    counters: Counter[str],
) -> Iterator[dict[str, str]]:
    expected_iter = iter(csv_rows(expected_path))
    seen_source: set[str] = set()
    seen_pre: set[str] = set()
    seen_post: set[str] = set()

    for row in csv_rows(safe_path):
        utt_id = row["utt_id"]
        if row["year"] != year:
            raise RuntimeError(f"{year}: safe-list year mismatch: {utt_id}")
        if utt_id in seen_source:
            raise RuntimeError(f"{year}: duplicate source utt_id in safe list: {utt_id}")
        seen_source.add(utt_id)
        if utt_id in pre_reasons:
            seen_pre.add(utt_id)
            counters["pre_mfa_technical_exclusion"] += 1
            yield output_row(
                row,
                status="pre_mfa_technical_exclusion",
                family="technical_exclusion",
                reasons=pre_reasons[utt_id],
                mfa_expected=False,
                textgrid_available=False,
                followup_required=True,
                alignment_scope="alignment_and_analysis",
                evidence_key="year_input.pre_mfa_exclusion_ids",
                year_input_contract_id=year_input_contract_id,
                alignment_contract_id=alignment_contract_id,
            )
            continue

        expected = next(expected_iter, None)
        if expected is None or expected["utt_id"] != utt_id:
            got = None if expected is None else expected["utt_id"]
            raise RuntimeError(f"{year}: expected MFA exact-ID mismatch: safe={utt_id}, expected={got}")
        if utt_id in post_reasons:
            seen_post.add(utt_id)
            counters["post_mfa_technical_exclusion"] += 1
            yield output_row(
                row,
                status="post_mfa_technical_exclusion",
                family="technical_exclusion",
                reasons=post_reasons[utt_id],
                mfa_expected=True,
                textgrid_available=False,
                followup_required=True,
                alignment_scope="alignment_and_analysis",
                evidence_key="post_mfa.approved_exclusions",
                year_input_contract_id=year_input_contract_id,
                alignment_contract_id=alignment_contract_id,
            )
        else:
            counters["aligned_safe_body"] += 1
            yield output_row(
                row,
                status="aligned_safe_body",
                family="aligned",
                reasons=[],
                mfa_expected=True,
                textgrid_available=True,
                followup_required=False,
                alignment_scope="alignment_and_analysis",
                evidence_key="r3.qc_passed_textgrid",
                year_input_contract_id=year_input_contract_id,
                alignment_contract_id=alignment_contract_id,
            )

    extra_expected = next(expected_iter, None)
    if extra_expected is not None:
        raise RuntimeError(f"{year}: extra expected MFA ID: {extra_expected['utt_id']}")
    if seen_pre != set(pre_reasons):
        raise RuntimeError(f"{year}: pre-MFA IDs outside pronunciation-safe set")
    if seen_post != set(post_reasons):
        raise RuntimeError(f"{year}: post-MFA IDs outside expected MFA input")

    for row in csv_rows(followup_path):
        utt_id = row["utt_id"]
        if row["year"] != year:
            raise RuntimeError(f"{year}: follow-up year mismatch: {utt_id}")
        if utt_id in seen_source:
            raise RuntimeError(f"{year}: safe/follow-up overlap or duplicate: {utt_id}")
        seen_source.add(utt_id)
        counters["pronunciation_followup"] += 1
        yield output_row(
            row,
            status="pronunciation_followup",
            family="pronunciation_followup",
            reasons=followup_reason_codes(row),
            mfa_expected=False,
            textgrid_available=False,
            followup_required=True,
            alignment_scope="pronunciation_resolution_before_alignment",
            evidence_key="year_input.pronunciation_followup_ids",
            year_input_contract_id=year_input_contract_id,
            alignment_contract_id=alignment_contract_id,
        )
    counters["source_total"] = len(seen_source)
    counters["methodological_exclusion"] = 0


def method_key(alignment: dict) -> dict:
    identity = alignment["identity"]
    return {
        "pronunciation_mode": alignment["pronunciation_mode"],
        "alignment_origin": alignment["alignment_origin"],
        "r3_full_realign": alignment["r3_full_realign"],
        "pronunciation_release_id": identity["pronunciation_release_id"],
        "pronunciation_contract_id": identity["pronunciation_contract_id"],
        "pronunciation_release_manifest_sha256": identity["pronunciation_release_manifest_sha256"],
        "staged_adoption_contract_sha256": identity["staged_adoption_contract_sha256"],
        "staged_adoption_audit_sha256": identity["staged_adoption_audit_sha256"],
        "researcher_approval_sha256": identity["researcher_approval_sha256"],
        "safe_body_routing_contract_id": identity["safe_body_routing_contract_id"],
        "frozen_model_pin_sha256": identity["frozen_model_pin_sha256"],
        "mfa_dictionary_sha256": identity["mfa_dictionary_sha256"],
        "acoustic_model_sha256": identity["acoustic_model_sha256"],
        "g2p_model_sha256": identity["g2p_model_sha256"],
        "runtime": identity["runtime"],
    }


def discover_export_report(project_root: Path, year: str, expected_sha256: str) -> Path:
    """Select the final export bound by the independent QC checkpoint.

    A failed first export is evidence and must remain on disk.  A later targeted
    recovery can therefore coexist with it.  The QC state's frozen SHA, rather
    than filename recency, is the authoritative selector.
    """
    candidates = sorted((project_root / "outputs" / "reports").glob(f"*EXPORT*{year}*.json"))
    matches = [path for path in candidates if sha256(path) == expected_sha256]
    if len(matches) != 1:
        raise RuntimeError(
            f"{year}: QC-bound export report not unique: expected_sha={expected_sha256}, "
            f"matches={len(matches)}, candidates={len(candidates)}"
        )
    return matches[0]


def drive_snapshot(path: Path) -> dict:
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_gib": round(usage.free / (1024**3), 3),
    }


def write_output_manifest(output_root: Path, project_root: Path) -> dict:
    output_files = []
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "OUTPUT_MANIFEST.json":
            output_files.append(file_fingerprint(path, with_sha256=True))
    output_manifest = {
        "schema_version": "research_db_v1_prep_output_manifest.v1",
        "status": "passed",
        "recorded_at": now_iso(),
        "release_prep_id": PREP_ID,
        "implementation": {
            "builder": file_fingerprint(Path(__file__).resolve(), with_sha256=True),
            "independent_auditor": file_fingerprint(
                Path(__file__).resolve().with_name("audit_db_v1_release_prep.py"),
                with_sha256=True,
            ),
        },
        "files": output_files,
        "file_count": len(output_files),
        "runtime": runtime_snapshot(project_root),
        "next_gate": "STOP before Stage D recovery/MFA",
    }
    atomic_write_json(output_root / "OUTPUT_MANIFEST.json", output_manifest)
    return output_manifest


def build(args: argparse.Namespace) -> dict:
    project_root = args.project_root.resolve()
    release_root = args.pronunciation_release_root.resolve()
    r3_root = args.r3_root.resolve()
    qc_root = args.qc_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    ledgers_root = output_root / "ledgers"
    ledgers_root.mkdir(exist_ok=True)

    workflow_path = project_root / "config" / "mfa_r3_full_realign_workflow_v1.json"
    workflow = load_json(workflow_path)
    input_records: dict[str, object] = {
        "workflow": checked_fingerprint(workflow_path),
        "years": {},
    }
    method_reference: dict | None = None
    year_records: dict[str, dict] = {}
    total_counts: Counter[str] = Counter()
    retained_bytes = Counter()

    for year in YEARS:
        print(f"[{year}] A-C contract and exact-ID audit", flush=True)
        year_input_path = release_root / "03_year_input_contracts" / year / f"YEAR_INPUT_CONTRACT_{year}.json"
        alignment_path = release_root / "04_alignment_contracts" / year / f"ALIGNMENT_CONTRACT_{year}.json"
        marker_path = r3_root / "markers" / f"ALIGN_DONE_{year}.json"
        qc_state_path = qc_root / year / "QC_STATE.json"
        qc_audit_path = qc_root / year / "01_year_audit.json"
        post_contract_path = project_root / "outputs" / "reviews" / f"mfa_r3_post_mfa_reconciliation_{RELEASE_ID}_{year}" / "05_APPROVED_EXCLUSIONS.json"

        year_input = load_json(year_input_path)
        alignment = load_json(alignment_path)
        marker = load_json(marker_path)
        qc_state = load_json(qc_state_path)
        qc_audit = load_json(qc_audit_path)
        export_path = discover_export_report(
            project_root,
            year,
            qc_state["qc_input"]["export_report_sha256"],
        )
        export = load_json(export_path)
        post_contract = load_json(post_contract_path)
        if str(year_input.get("year")) != year or str(alignment.get("year")) != year:
            raise RuntimeError(f"{year}: contract year mismatch")
        if marker.get("status") != "passed" or qc_state.get("status") != "passed" or qc_audit.get("status") != "success" or export.get("status") != "success":
            raise RuntimeError(f"{year}: completion/QC/export gate is not passed")
        if post_contract.get("status") != "approved" or str(post_contract.get("year")) != year:
            raise RuntimeError(f"{year}: post-MFA approval gate is not approved")
        if alignment["identity"]["year_input_contract_id"] != year_input["year_input_contract_id"]:
            raise RuntimeError(f"{year}: year-input contract ID mismatch")
        if marker["alignment_contract_id"] != alignment["alignment_contract_id"]:
            raise RuntimeError(f"{year}: marker/alignment contract ID mismatch")
        if qc_state["qc_input"]["source_db_expected_sha256"] != marker["source_db"]["sha256"]:
            raise RuntimeError(f"{year}: QC/marker database SHA mismatch")
        current_method = method_key(alignment)
        if method_reference is None:
            method_reference = current_method
        elif current_method != method_reference:
            raise RuntimeError(f"{year}: cross-year common method mismatch")

        safe_path = Path(year_input["outputs"]["pronunciation_safe_ids"]["path"])
        followup_path = Path(year_input["outputs"]["pronunciation_followup_ids"]["path"])
        pre_path = Path(year_input["outputs"]["pre_mfa_exclusion_ids"]["path"])
        expected_path = Path(year_input["outputs"]["expected_mfa_input_ids"]["path"])
        post_csv_path = Path(post_contract["review_csv"]["path"])
        evidence = {
            "year_input_contract": checked_fingerprint(year_input_path),
            "alignment_contract": checked_fingerprint(alignment_path),
            "alignment_marker": checked_fingerprint(marker_path),
            "qc_state": checked_fingerprint(qc_state_path),
            "qc_audit": checked_fingerprint(qc_audit_path),
            "export_report": checked_fingerprint(export_path),
            "post_mfa_approval_contract": checked_fingerprint(post_contract_path),
            "post_mfa_approval_csv": checked_fingerprint(post_csv_path, post_contract["review_csv"]),
            "pronunciation_safe_ids": checked_fingerprint(safe_path, year_input["outputs"]["pronunciation_safe_ids"]),
            "pronunciation_followup_ids": checked_fingerprint(followup_path, year_input["outputs"]["pronunciation_followup_ids"]),
            "pre_mfa_exclusion_ids": checked_fingerprint(pre_path, year_input["outputs"]["pre_mfa_exclusion_ids"]),
            "expected_mfa_input_ids": checked_fingerprint(expected_path, year_input["outputs"]["expected_mfa_input_ids"]),
        }

        db_path = Path(marker["source_db"]["path"])
        db_stat = file_fingerprint(db_path, with_sha256=args.verify_large_assets)
        if db_stat["bytes"] != marker["source_db"]["bytes"]:
            raise RuntimeError(f"{year}: frozen database size changed")
        if args.verify_large_assets and db_stat["sha256"] != marker["source_db"]["sha256"]:
            raise RuntimeError(f"{year}: frozen database SHA changed")
        retained_bytes["mfa_databases"] += db_stat["bytes"]

        table_manifest = qc_audit["table_manifest"]
        table_manifest_path = r3_root / "research_6tier" / year / "_tables" / "TABLES_MANIFEST.json"
        evidence["table_manifest"] = checked_fingerprint(table_manifest_path, {"sha256": qc_state["qc_input"]["table_manifest_sha256"]})
        table_assets: dict[str, dict] = {}
        for name, contract in table_manifest["tables"].items():
            table_path = table_manifest_path.parent / contract["path"]
            actual = file_fingerprint(table_path, with_sha256=args.verify_large_assets)
            if actual["bytes"] != contract["bytes"]:
                raise RuntimeError(f"{year}: {name} companion table size changed")
            if args.verify_large_assets and actual["sha256"] != contract["sha256"]:
                raise RuntimeError(f"{year}: {name} companion table SHA changed")
            table_assets[name] = actual
            retained_bytes["companion_tables"] += actual["bytes"]

        pre_reasons = load_reason_map(pre_path, "reason_codes_json")
        post_reasons = load_reason_map(post_csv_path, "reason_code")
        counters: Counter[str] = Counter()
        ledger_path = ledgers_root / f"{year}_utterance_status.csv.gz"
        year_manifest_path = ledgers_root / f"{year}_LEDGER_MANIFEST.json"
        input_signature = {key: value["sha256"] for key, value in evidence.items() if isinstance(value, dict) and "sha256" in value}
        resume = False
        if ledger_path.is_file() and year_manifest_path.is_file():
            old = load_json(year_manifest_path)
            if old.get("input_signature") == input_signature and sha256(ledger_path) == old.get("ledger", {}).get("sha256"):
                year_manifest = old
                counters.update(old["counts"])
                resume = True
                print(f"[{year}] verified checkpoint reused", flush=True)
        if not resume:
            ledger_info = write_deterministic_gzip_csv(
                ledger_path,
                year_ledger_rows(
                    year=year,
                    safe_path=safe_path,
                    followup_path=followup_path,
                    expected_path=expected_path,
                    pre_reasons=pre_reasons,
                    post_reasons=post_reasons,
                    year_input_contract_id=year_input["year_input_contract_id"],
                    alignment_contract_id=alignment["alignment_contract_id"],
                    counters=counters,
                ),
            )
            expected_counts = {
                "source_total": year_input["accounting"]["source_utterances"],
                "aligned_safe_body": qc_state["counts"]["textgrids"],
                "post_mfa_technical_exclusion": post_contract["row_count"],
                "pre_mfa_technical_exclusion": year_input["accounting"]["pre_mfa_exclusions_applied_to_pron_safe"],
                "pronunciation_followup": year_input["accounting"]["pronunciation_followup"],
                "methodological_exclusion": 0,
            }
            if dict(counters) != expected_counts:
                raise RuntimeError(f"{year}: ledger count mismatch: {dict(counters)} != {expected_counts}")
            year_manifest = {
                "schema_version": "research_db_v1_year_status_ledger.v1",
                "status": "passed",
                "recorded_at": now_iso(),
                "year": year,
                "release_prep_id": PREP_ID,
                "input_signature": input_signature,
                "counts": dict(counters),
                "ledger": ledger_info,
                "column_schema": LEDGER_FIELDS,
            }
            atomic_write_json(year_manifest_path, year_manifest)
        total_counts.update(counters)
        year_records[year] = {
            "year_input_contract_id": year_input["year_input_contract_id"],
            "alignment_contract_id": alignment["alignment_contract_id"],
            "counts": dict(counters),
            "evidence": evidence,
            "frozen_database": db_stat,
            "companion_tables": table_assets,
            "textgrid_schema": table_manifest["textgrid_schema_version"],
            "textgrid_tiers": export["tier_names"],
            "ledger_manifest": checked_fingerprint(year_manifest_path),
            "ledger": year_manifest["ledger"],
        }
        input_records["years"][year] = evidence  # type: ignore[index]

    expected_totals = {
        "source_total": 5_103_356,
        "aligned_safe_body": 4_286_046,
        "post_mfa_technical_exclusion": 3_086,
        "pre_mfa_technical_exclusion": 95_860,
        "pronunciation_followup": 718_364,
        "methodological_exclusion": 0,
    }
    if dict(total_counts) != expected_totals:
        raise RuntimeError(f"six-year ledger totals mismatch: {dict(total_counts)} != {expected_totals}")
    if sum(total_counts[key] for key in expected_totals if key != "source_total") != total_counts["source_total"]:
        raise RuntimeError("six-year status partition is not exhaustive")

    common_method = method_reference or {}
    cross_year_audit = {
        "schema_version": "mfa_r3_cross_year_release_audit.v1",
        "status": "passed",
        "recorded_at": now_iso(),
        "release_id": RELEASE_ID,
        "years": list(YEARS),
        "methodological_claim": "2020-2025 were freshly aligned with the same frozen r3 pronunciation release, dictionary, acoustic model, G2P provenance, MFA/Pynini/Python runtime, routing contract, and research TextGrid schema; year input contracts differ only by year-bound exact-ID scope.",
        "common_method_contract": common_method,
        "gate": {
            "cross_year_method_mismatches": 0,
            "all_alignment_markers_passed": True,
            "all_independent_qc_passed": True,
            "all_exports_passed": True,
            "large_asset_sha_reverified_now": bool(args.verify_large_assets),
        },
        "years_detail": year_records,
    }
    atomic_write_json(output_root / "CROSS_YEAR_CONTRACT_AUDIT.json", cross_year_audit)

    storage_plan = {
        "schema_version": "research_db_v1_storage_read_only_plan.v1",
        "status": "planned_no_mutation",
        "recorded_at": now_iso(),
        "policy": {
            "D_role": "canonical r3 source, databases, final 6-tier TextGrids, and active contracts",
            "E_role": "preferred future read-only archive after a separately approved copy-verify-freeze operation",
            "H_role": "selective secondary backup only; current free space is insufficient for an assumed full mirror",
            "C_project_role": "versioned code/docs/small manifests plus ignored compressed A-C ledgers",
            "deletion_or_move_performed": False,
            "archive_copy_performed": False,
        },
        "drives": {
            "C": drive_snapshot(Path("C:/")),
            "D": drive_snapshot(Path("D:/")),
            "E": drive_snapshot(Path("E:/")),
            "H": drive_snapshot(Path("H:/")),
        },
        "manifest_derived_retained_bytes": dict(retained_bytes),
        "limitations": [
            "No recursive rescan of 4,286,046 TextGrid files was performed in A-C; per-year export and independent QC counts remain the frozen evidence.",
            "A future archive action requires an exact allowlist, copy verification, archive manifest, and separate researcher approval before any source removal.",
            "Do not begin recovery/MFA stage D while D free space is below the future stage-specific capacity gate.",
        ],
    }
    atomic_write_json(output_root / "STORAGE_READ_ONLY_PLAN.json", storage_plan)

    base_manifest = {
        "schema_version": "nikl_dialogue_research_db_base_release.v1",
        "status": "internal_rc0_ac_complete",
        "recorded_at": now_iso(),
        "release_prep_id": PREP_ID,
        "source_release_id": RELEASE_ID,
        "scope": {
            "years": list(YEARS),
            "source_utterances": total_counts["source_total"],
            "aligned_6tier_utterances": total_counts["aligned_safe_body"],
            "technical_followup_utterances": total_counts["pre_mfa_technical_exclusion"] + total_counts["post_mfa_technical_exclusion"],
            "pronunciation_followup_utterances": total_counts["pronunciation_followup"],
            "methodological_exclusions": total_counts["methodological_exclusion"],
        },
        "accounting_equation": "5,103,356 = 4,286,046 aligned + 95,860 pre-MFA technical + 3,086 post-MFA technical + 718,364 pronunciation follow-up + 0 methodological exclusions",
        "common_method_contract": common_method,
        "years": year_records,
        "mutation": {
            "raw_corpus_modified": False,
            "mfa_recomputed": False,
            "database_modified": False,
            "textgrid_modified": False,
            "archive_or_delete_performed": False,
        },
        "next_gate": "Stage D reason-specific recovery shards; not authorized by this A-C run",
    }
    atomic_write_json(output_root / "BASE_RELEASE_MANIFEST_2020_2025.json", base_manifest)
    atomic_write_json(
        output_root / "INPUT_CONTRACT.json",
        {
            "schema_version": "research_db_v1_prep_input_contract.v1",
            "status": "passed",
            "recorded_at": now_iso(),
            "release_prep_id": PREP_ID,
            "inputs": input_records,
        },
    )
    qa_report = {
        "schema_version": "research_db_v1_prep_qa.v1",
        "status": "passed",
        "recorded_at": now_iso(),
        "counts": dict(total_counts),
        "hard_failures": {
            "missing_source_ids": 0,
            "duplicate_source_ids_within_year": 0,
            "safe_followup_overlap": 0,
            "unclassified_source_ids": 0,
            "expected_mfa_equation_mismatches": 0,
            "post_mfa_ids_outside_expected_input": 0,
            "cross_year_method_mismatches": 0,
            "failed_completion_or_qc_gates": 0,
            "frozen_large_asset_fingerprint_mismatches": 0,
        },
        "large_asset_sha_reverified_now": bool(args.verify_large_assets),
        "methodological_exclusion_note": "No research-question-based exclusion has yet been applied. Current exclusions are technical or pronunciation-routing states and remain recoverable exact-ID records.",
    }
    atomic_write_json(output_root / "QA_REPORT.json", qa_report)

    output_manifest = write_output_manifest(output_root, project_root)
    print(f"[OK] A-C complete: {output_root}", flush=True)
    return output_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--pronunciation-release-root",
        type=Path,
        default=Path(f"D:/mfa_common_pron/releases/{RELEASE_ID}"),
    )
    parser.add_argument(
        "--r3-root",
        type=Path,
        default=Path(f"D:/mfa_eojeol/r3/{RELEASE_ID}"),
    )
    parser.add_argument(
        "--qc-root",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "reports" / f"mfa_r3_research_qc_{RELEASE_ID}",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "releases" / PREP_ID,
    )
    parser.add_argument("--verify-large-assets", action="store_true")
    parser.add_argument(
        "--refresh-output-manifest-only",
        action="store_true",
        help="Rehash only the completed A-C package after adding documentation.",
    )
    args = parser.parse_args()
    if args.refresh_output_manifest_only:
        output_root = args.output_root.resolve()
        base = load_json(output_root / "BASE_RELEASE_MANIFEST_2020_2025.json")
        qa = load_json(output_root / "QA_REPORT.json")
        if base.get("status") != "internal_rc0_ac_complete" or qa.get("status") != "passed" or not qa.get("large_asset_sha_reverified_now"):
            raise RuntimeError("completed SHA-reverified A-C package is required before manifest-only refresh")
        manifest = write_output_manifest(output_root, args.project_root.resolve())
        print(f"[OK] output manifest refreshed: {manifest['file_count']} files", flush=True)
    else:
        build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
