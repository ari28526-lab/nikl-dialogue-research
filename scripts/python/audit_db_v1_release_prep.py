#!/usr/bin/env python3
"""Independently audit the A--C research DB v1 preparation package."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
YEARS = tuple(str(year) for year in range(2020, 2026))
EXPECTED = {
    "aligned_safe_body": 4_286_046,
    "pre_mfa_technical_exclusion": 95_860,
    "post_mfa_technical_exclusion": 3_086,
    "pronunciation_followup": 718_364,
}
INVARIANTS = {
    "aligned_safe_body": ("true", "true", "false", "aligned"),
    "pre_mfa_technical_exclusion": ("false", "false", "true", "technical_exclusion"),
    "post_mfa_technical_exclusion": ("true", "false", "true", "technical_exclusion"),
    "pronunciation_followup": ("false", "false", "true", "pronunciation_followup"),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_ledger(path: Path, year: str, manifest: dict) -> dict:
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    canonical = hashlib.sha256()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "year", "utt_id", "primary_status", "status_family",
            "mfa_expected", "textgrid_available", "followup_required",
            "year_input_contract_id", "alignment_contract_id",
        }
        if not required.issubset(reader.fieldnames or []):
            raise RuntimeError(f"{year}: ledger schema is incomplete")
        for line_number, row in enumerate(reader, 2):
            utt_id = row["utt_id"]
            status = row["primary_status"]
            if row["year"] != year:
                raise RuntimeError(f"{year}: row-year mismatch at line {line_number}")
            if len(utt_id) < 6 or utt_id[4:6] != year[2:4]:
                raise RuntimeError(f"{year}: utt_id year binding mismatch: {utt_id}")
            if utt_id in seen:
                raise RuntimeError(f"{year}: duplicate utt_id: {utt_id}")
            seen.add(utt_id)
            if status not in INVARIANTS:
                raise RuntimeError(f"{year}: unknown primary_status: {status}")
            observed = (
                row["mfa_expected"], row["textgrid_available"],
                row["followup_required"], row["status_family"],
            )
            if observed != INVARIANTS[status]:
                raise RuntimeError(f"{year}: status invariant failed for {utt_id}: {observed}")
            if row["year_input_contract_id"] != manifest["year_input_contract_id"]:
                raise RuntimeError(f"{year}: input contract binding mismatch: {utt_id}")
            if row["alignment_contract_id"] != manifest["alignment_contract_id"]:
                raise RuntimeError(f"{year}: alignment contract binding mismatch: {utt_id}")
            counts[status] += 1
            canonical.update((year + "\t" + utt_id + "\t" + status + "\n").encode("utf-8"))
    if len(seen) != manifest["ledger"]["rows"]:
        raise RuntimeError(f"{year}: distinct ledger row count mismatch")
    if canonical.hexdigest() != manifest["ledger"]["canonical_year_utt_status_sha256"]:
        raise RuntimeError(f"{year}: canonical status digest mismatch")
    if sha256(path) != manifest["ledger"]["sha256"]:
        raise RuntimeError(f"{year}: compressed ledger SHA mismatch")
    return {"rows": len(seen), "counts": dict(counts)}


def audit(args: argparse.Namespace) -> dict:
    release_root = args.release_root.resolve()
    output_manifest = load_json(release_root / "OUTPUT_MANIFEST.json")
    base = load_json(release_root / "BASE_RELEASE_MANIFEST_2020_2025.json")
    cross = load_json(release_root / "CROSS_YEAR_CONTRACT_AUDIT.json")
    qa = load_json(release_root / "QA_REPORT.json")
    if output_manifest.get("status") != "passed" or cross.get("status") != "passed" or qa.get("status") != "passed":
        raise RuntimeError("A-C package gate is not passed")
    if not cross["gate"].get("large_asset_sha_reverified_now") or not qa.get("large_asset_sha_reverified_now"):
        raise RuntimeError("large frozen assets were not SHA-reverified in the final A-C run")

    manifest_paths: set[Path] = set()
    for record in output_manifest["files"]:
        path = Path(record["path"])
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise RuntimeError(f"output-manifest fingerprint mismatch: {path}")
        manifest_paths.add(path.resolve())
    actual_paths = {
        path.resolve()
        for path in release_root.rglob("*")
        if path.is_file() and path.name != "OUTPUT_MANIFEST.json"
    }
    if actual_paths != manifest_paths:
        raise RuntimeError("output manifest file inventory is not exact")

    common_method = None
    total: Counter[str] = Counter()
    years: dict[str, dict] = {}
    for year in YEARS:
        year_record = base["years"][year]
        ledger_manifest_path = release_root / "ledgers" / f"{year}_LEDGER_MANIFEST.json"
        ledger_path = release_root / "ledgers" / f"{year}_utterance_status.csv.gz"
        ledger_manifest = load_json(ledger_manifest_path)
        if ledger_manifest.get("status") != "passed" or ledger_manifest.get("year") != year:
            raise RuntimeError(f"{year}: ledger manifest gate failed")
        ledger_result = audit_ledger(ledger_path, year, year_record)
        total.update(ledger_result["counts"])

        alignment_path = Path(year_record["evidence"]["alignment_contract"]["path"])
        alignment = load_json(alignment_path)
        identity = alignment["identity"]
        method = {
            "pronunciation_mode": alignment["pronunciation_mode"],
            "alignment_origin": alignment["alignment_origin"],
            "r3_full_realign": alignment["r3_full_realign"],
            "pronunciation_release_id": identity["pronunciation_release_id"],
            "pronunciation_contract_id": identity["pronunciation_contract_id"],
            "dictionary": identity["mfa_dictionary_sha256"],
            "acoustic": identity["acoustic_model_sha256"],
            "g2p": identity["g2p_model_sha256"],
            "runtime": identity["runtime"],
            "routing": identity["safe_body_routing_contract_id"],
        }
        if common_method is None:
            common_method = method
        elif method != common_method:
            raise RuntimeError(f"{year}: independent common-method mismatch")

        marker = load_json(Path(year_record["evidence"]["alignment_marker"]["path"]))
        if year_record["frozen_database"].get("sha256") != marker["source_db"]["sha256"]:
            raise RuntimeError(f"{year}: database SHA is not bound to ALIGN_DONE marker")
        table_manifest = load_json(Path(year_record["evidence"]["table_manifest"]["path"]))
        for name, actual in year_record["companion_tables"].items():
            if actual.get("sha256") != table_manifest["tables"][name]["sha256"]:
                raise RuntimeError(f"{year}: {name} table SHA is not bound to table manifest")
        years[year] = ledger_result

    if dict(total) != EXPECTED:
        raise RuntimeError(f"independent six-year count mismatch: {dict(total)} != {EXPECTED}")
    source_total = sum(total.values())
    if source_total != 5_103_356 or source_total != base["scope"]["source_utterances"]:
        raise RuntimeError("independent source-total equation mismatch")

    report = {
        "schema_version": "research_db_v1_prep_independent_audit.v1",
        "status": "passed",
        "recorded_at": now_iso(),
        "release_prep_id": base["release_prep_id"],
        "source_utterances": source_total,
        "counts": dict(total),
        "years": years,
        "hard_failures": {
            "output_fingerprint_mismatch": 0,
            "unmanifested_output_files": 0,
            "duplicate_utt_ids_within_year": 0,
            "utt_id_year_binding_mismatch": 0,
            "status_invariant_mismatch": 0,
            "contract_binding_mismatch": 0,
            "cross_year_method_mismatch": 0,
            "frozen_database_sha_binding_mismatch": 0,
            "companion_table_sha_binding_mismatch": 0,
            "unclassified_or_missing_source_ids": 0,
        },
        "implementation": {
            "auditor": file_fingerprint(Path(__file__).resolve(), with_sha256=True),
            "builder": file_fingerprint(
                Path(__file__).resolve().with_name("build_db_v1_release_prep.py"),
                with_sha256=True,
            ),
        },
        "scope_note": "Individual TextGrid byte-Merkle inventory is deferred to release QA I; A-C uses passed annual export/QC counts and reverified database/companion-table SHA values.",
        "runtime": runtime_snapshot(args.project_root.resolve()),
    }
    atomic_write_json(args.output.resolve(), report)
    print(f"[OK] independent A-C audit: {args.output.resolve()}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--release-root",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "releases" / "nikl_dialogue_research_db_v1_0_0_rc0_20260815",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "reports" / "AUDIT_db_v1_release_prep_ac_20260815.json",
    )
    args = parser.parse_args()
    audit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
