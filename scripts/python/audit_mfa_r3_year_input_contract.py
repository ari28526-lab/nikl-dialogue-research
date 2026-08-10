"""Independently audit an exact-ID r3 year input contract."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SCHEMA = "mfa_r3_year_input_contract.v1"
CONTRACT_STATUS = "materialized_pending_independent_year_input_audit_gate_closed"
POLICY_SCHEMA = "mfa_r3_year_input_contract_policy.v1"
SCHEMA_VERSION = "mfa_r3_year_input_contract_audit.v1"
STATUS = "passed_independent_exact_id_audit_pending_alignment_contract_gate_closed"
POLICY_STATUSES = {
    "approved_contract_building_only_gate_closed",
    "approved_contract_building_release_adopted",
}
ID_FIELDS = ("year", "utt_id", "session_id", "source_csv")
FOLLOWUP_FIELDS = ID_FIELDS + (
    "routing_class",
    "hold_tokens_json",
    "policy_tokens_json",
    "unknown_tokens_json",
)
EXCLUSION_FIELDS = ID_FIELDS + ("reason_codes_json",)
REENTRY_FIELDS = ID_FIELDS + ("r2_post_mfa_reason_codes_json",)

csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify(record: dict, path: Path, label: str) -> None:
    if (
        Path(clean(record.get("path"))).resolve() != path.resolve()
        or not path.is_file()
        or int(record.get("bytes", -1)) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def inventory(files: list[Path], root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        stat = path.stat()
        relative = path.relative_to(root).as_posix()
        digest.update(
            f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8")
        )
        total_bytes += stat.st_size
    return {
        "root": str(root.resolve()),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "path_size_mtime_sha256": digest.hexdigest(),
    }


def update_digest(digest: "hashlib._Hash", fields: tuple[str, ...], row: dict) -> None:
    digest.update("\0".join(clean(row.get(field)) for field in fields).encode("utf-8"))
    digest.update(b"\n")


def read_output(
    path: Path,
    fields: tuple[str, ...],
    *,
    year: str,
    membership,
) -> tuple[set[str], str]:
    ids: set[str] = set()
    digest = hashlib.sha256()
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise RuntimeError(f"output field contract differs: {path.name}")
        for row in reader:
            utt_id = clean(row["utt_id"])
            if clean(row["year"]) != year or not utt_id or utt_id in ids:
                raise RuntimeError(f"output duplicate/wrong-year ID: {path.name} {utt_id}")
            if not membership(utt_id, row):
                raise RuntimeError(f"output category membership differs: {path.name} {utt_id}")
            ids.add(utt_id)
            update_digest(digest, fields, row)
    return ids, digest.hexdigest()


def approval_rows(manifest_path: Path, year: str) -> tuple[dict, list[dict[str, str]]]:
    manifest = load_json(manifest_path)
    if (
        manifest.get("schema_version") != "mfa_approved_exclusions.v1"
        or manifest.get("status") != "approved"
        or clean(manifest.get("year")) != year
    ):
        raise RuntimeError("approved exclusion identity differs")
    csv_path = Path(clean(manifest["review_csv"]["path"])).resolve()
    verify(manifest["review_csv"], csv_path, "approved review CSV")
    rows: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"year", "utt_id", "reason_code", "exclusion_scope", "decision"}
        if not required.issubset(reader.fieldnames or ()):
            raise RuntimeError("approved review fields differ")
        for row in reader:
            if (
                clean(row["year"]) != year
                or clean(row["decision"]).lower() != "approved"
                or clean(row["exclusion_scope"]) != "alignment_and_analysis"
            ):
                raise RuntimeError("approved review row identity differs")
            rows.append(row)
            counts[f"{clean(row['reason_code'])}|alignment_and_analysis"] += 1
    if len(rows) != int(manifest["row_count"]) or dict(counts) != {
        str(key): int(value) for key, value in manifest["counts"].items()
    }:
        raise RuntimeError("approved review accounting differs")
    return manifest, rows


def reasons_by_id(rows: list[dict[str, str]], allowed: set[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        reason = clean(row["reason_code"])
        if reason in allowed:
            utt_id = clean(row["utt_id"])
            if reason in result[utt_id]:
                raise RuntimeError(f"duplicate approved reason: {utt_id} {reason}")
            result[utt_id].add(reason)
    return dict(result)


def calculate_contract_id(manifest: dict) -> str:
    inputs = manifest["inputs"]
    identity = {
        "release_id": manifest["release_id"],
        "pronunciation_contract_id": manifest["pronunciation_contract_id"],
        "year": manifest["year"],
        "stage19_blocked_sha256": inputs["stage19_blocked_routing"]["sha256"],
        "stage19_year_summary_sha256": inputs["stage19_year_summary"]["sha256"],
        "search_master_inventory_sha256": inputs["frozen_search_master_inventory"][
            "path_size_mtime_sha256"
        ],
        "initial_approval_sha256": inputs["initial_pre_mfa_approval_manifest"]["sha256"],
        "combined_approval_sha256": inputs["combined_r2_approval_manifest"]["sha256"],
        "corpus_contract_id": manifest["corpus_binding"]["corpus_contract_id"],
        "policy_sha256": inputs["year_input_policy"]["sha256"],
        "output_sha256": {
            key: record["sha256"] for key, record in manifest["outputs"].items()
        },
        "accounting": manifest["accounting"],
    }
    canonical = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def audit(contract_path: Path, output_path: Path) -> dict:
    contract = load_json(contract_path)
    if (
        contract.get("schema_version") != CONTRACT_SCHEMA
        or contract.get("status") != CONTRACT_STATUS
        or contract.get("scope", {}).get("production_mfa_allowed") is not False
        or contract.get("scope", {}).get("textgrid_materialization_allowed") is not False
        or any(
            contract.get("scope", {}).get(key) is not False
            for key in ("stage_01_21_modified", "r2_artifacts_modified", "raw_corpus_modified")
        )
    ):
        raise RuntimeError("year input contract identity or closed gate differs")
    year = clean(contract["year"])
    inputs = contract["inputs"]
    for label, record in inputs.items():
        if label == "frozen_search_master_inventory":
            continue
        verify(record, Path(clean(record["path"])), f"contract input {label}")
    output_paths: dict[str, Path] = {}
    for label, record in contract["outputs"].items():
        path = Path(clean(record["path"])).resolve()
        verify(record, path, f"contract output {label}")
        output_paths[label] = path
    if calculate_contract_id(contract) != contract["year_input_contract_id"]:
        raise RuntimeError("year input contract ID differs")

    policy = load_json(Path(clean(inputs["year_input_policy"]["path"])))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") not in POLICY_STATUSES
        or policy.get("scope", {}).get("production_mfa_allowed") is not False
        or year not in policy.get("scope", {}).get("years_enabled", [])
    ):
        raise RuntimeError("year input policy differs")
    year_policy = policy["years"][year]
    pre_reasons = set(policy["reason_policy"]["pre_mfa_technical_exclusions"])
    post_reasons = set(
        policy["reason_policy"]["r2_post_mfa_failures_must_not_be_pre_exclusions"]
    )

    routing = load_json(Path(clean(inputs["stage19_routing_manifest"]["path"])))
    blocked_path = Path(clean(inputs["stage19_blocked_routing"]["path"])).resolve()
    summary_path = Path(clean(inputs["stage19_year_summary"]["path"])).resolve()
    search_root = Path(clean(inputs["frozen_search_master_inventory"]["root"])).resolve()
    all_files = [
        path
        for source_year in (str(value) for value in range(2020, 2026))
        for path in sorted((search_root / source_year).glob("*.csv"))
    ]
    actual_inventory = inventory(all_files, search_root)
    for key in ("root", "file_count", "total_bytes", "path_size_mtime_sha256"):
        if clean(actual_inventory[key]) != clean(inputs["frozen_search_master_inventory"].get(key)):
            raise RuntimeError(f"independent search inventory differs: {key}")
    year_files = [path for path in all_files if path.parent.name == year]

    blocked: dict[str, dict[str, str]] = {}
    with gzip.open(blocked_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            if clean(row.get("year")) != year:
                continue
            utt_id = clean(row.get("utt_id"))
            if not utt_id or utt_id in blocked or json.loads(row["unknown_tokens_json"] or "[]"):
                raise RuntimeError("independent blocked routing identity differs")
            blocked[utt_id] = row
    with summary_path.open("r", encoding="utf-8-sig", newline="") as stream:
        summary_rows = [
            row for row in csv.DictReader(stream) if clean(row.get("year")) == year
        ]
    if len(summary_rows) != 1:
        raise RuntimeError("independent year summary identity differs")
    summary = summary_rows[0]

    _, initial_rows = approval_rows(
        Path(clean(inputs["initial_pre_mfa_approval_manifest"]["path"])), year
    )
    _, combined_rows = approval_rows(
        Path(clean(inputs["combined_r2_approval_manifest"]["path"])), year
    )
    initial_pre = reasons_by_id(initial_rows, pre_reasons)
    combined_pre = reasons_by_id(combined_rows, pre_reasons)
    post_ids = reasons_by_id(combined_rows, post_reasons)
    pre_ids: dict[str, set[str]] = defaultdict(set)
    for collection in (initial_pre, combined_pre):
        for utt_id, reasons in collection.items():
            pre_ids[utt_id].update(reasons)

    corpus = load_json(Path(clean(inputs["recovered_wav_corpus_contract"]["path"])))
    recovered_root = Path(clean(corpus["output_year"])).resolve()
    corpus_schema = clean(corpus.get("schema_version"))
    expected_corpus_schema = clean(
        year_policy.get("corpus_contract_schema", "wav_recovery_corpus.v1")
    )
    expected_corpus_contract_id = clean(
        year_policy.get(
            "corpus_contract_id",
            year_policy.get("recovered_corpus_contract_id"),
        )
    )
    expected_corpus_files = int(
        year_policy.get(
            "expected_corpus_wav_files",
            year_policy.get("expected_recovered_wav_files", -1),
        )
    )
    if (
        corpus.get("status") != "passed"
        or corpus_schema != expected_corpus_schema
        or clean(corpus.get("year")) != year
        or clean(corpus.get("corpus_contract_id"))
        != expected_corpus_contract_id
        or corpus.get("source_wav_tree_untouched") is not True
        or int(corpus.get("wav_files", -1)) != expected_corpus_files
    ):
        raise RuntimeError("independent WAV corpus contract differs")
    wav_ids: set[str] = set()
    for path in recovered_root.rglob("*.wav"):
        if path.stem in wav_ids:
            raise RuntimeError(f"duplicate recovered WAV: {path.stem}")
        wav_ids.add(path.stem)

    expected_digests = {
        "pronunciation_safe_ids": hashlib.sha256(),
        "pronunciation_followup_ids": hashlib.sha256(),
        "pre_mfa_exclusion_ids": hashlib.sha256(),
        "expected_mfa_input_ids": hashlib.sha256(),
        "r2_post_mfa_reentry_ids": hashlib.sha256(),
    }
    expected_fields = {
        "pronunciation_safe_ids": ID_FIELDS,
        "pronunciation_followup_ids": FOLLOWUP_FIELDS,
        "pre_mfa_exclusion_ids": EXCLUSION_FIELDS,
        "expected_mfa_input_ids": ID_FIELDS,
        "r2_post_mfa_reentry_ids": REENTRY_FIELDS,
    }
    source_ids: set[str] = set()
    expected_safe: set[str] = set()
    expected_pre: set[str] = set()
    expected_mfa: set[str] = set()
    expected_reentry: set[str] = set()
    for path in year_files:
        relative = path.relative_to(search_root).as_posix()
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                utt_id = clean(row.get("utt_id"))
                if clean(row.get("year")) != year or not utt_id or utt_id in source_ids:
                    raise RuntimeError("independent source exact-ID identity differs")
                source_ids.add(utt_id)
                base = {
                    "year": year,
                    "utt_id": utt_id,
                    "session_id": clean(row.get("session_id")),
                    "source_csv": relative,
                }
                if utt_id in blocked:
                    blocked_row = blocked[utt_id]
                    followup = {
                        **base,
                        "routing_class": blocked_row["routing_class"],
                        "hold_tokens_json": blocked_row["hold_tokens_json"],
                        "policy_tokens_json": blocked_row["policy_tokens_json"],
                        "unknown_tokens_json": blocked_row["unknown_tokens_json"],
                    }
                    update_digest(
                        expected_digests["pronunciation_followup_ids"],
                        FOLLOWUP_FIELDS,
                        followup,
                    )
                    continue
                expected_safe.add(utt_id)
                update_digest(expected_digests["pronunciation_safe_ids"], ID_FIELDS, base)
                if utt_id in pre_ids:
                    expected_pre.add(utt_id)
                    exclusion = {
                        **base,
                        "reason_codes_json": json.dumps(
                            sorted(pre_ids[utt_id]), ensure_ascii=False
                        ),
                    }
                    update_digest(
                        expected_digests["pre_mfa_exclusion_ids"],
                        EXCLUSION_FIELDS,
                        exclusion,
                    )
                    continue
                expected_mfa.add(utt_id)
                update_digest(expected_digests["expected_mfa_input_ids"], ID_FIELDS, base)
                if utt_id in post_ids:
                    expected_reentry.add(utt_id)
                    reentry = {
                        **base,
                        "r2_post_mfa_reason_codes_json": json.dumps(
                            sorted(post_ids[utt_id]), ensure_ascii=False
                        ),
                    }
                    update_digest(
                        expected_digests["r2_post_mfa_reentry_ids"],
                        REENTRY_FIELDS,
                        reentry,
                    )

    if set(blocked) - source_ids or (set(pre_ids) | set(post_ids)) - source_ids:
        raise RuntimeError("independent routing/approval IDs are outside source")
    audio_pairing = {
        utt_id for utt_id, reasons in pre_ids.items() if "audio_pairing_unresolved" in reasons
    }
    source_missing_wav = source_ids - wav_ids
    corpus_extra_wav = wav_ids - source_ids
    if source_missing_wav - audio_pairing or expected_mfa - wav_ids:
        raise RuntimeError("independent WAV eligibility equation differs")
    if corpus_schema == "wav_recovery_corpus.v1" and (
        source_missing_wav != audio_pairing or corpus_extra_wav
    ):
        raise RuntimeError("independent recovered WAV exact-ID equation differs")

    expected_sets = {
        "pronunciation_safe_ids": expected_safe,
        "pronunciation_followup_ids": set(blocked),
        "pre_mfa_exclusion_ids": expected_pre,
        "expected_mfa_input_ids": expected_mfa,
        "r2_post_mfa_reentry_ids": expected_reentry,
    }
    actual_sets: dict[str, set[str]] = {}
    actual_digests: dict[str, str] = {}
    membership = {
        key: (lambda target: lambda utt_id, row: utt_id in target)(target)
        for key, target in expected_sets.items()
    }
    for key, fields in expected_fields.items():
        ids, digest = read_output(
            output_paths[key], fields, year=year, membership=membership[key]
        )
        if ids != expected_sets[key] or digest != expected_digests[key].hexdigest():
            raise RuntimeError(f"independent exact output differs: {key}")
        actual_sets[key] = ids
        actual_digests[key] = digest

    accounting = contract["accounting"]
    expected_accounting = {
        "source_utterances": len(source_ids),
        "pronunciation_safe": len(expected_safe),
        "pronunciation_followup": len(blocked),
        "pre_mfa_exclusions_applied_to_pron_safe": len(expected_pre),
        "expected_mfa_input": len(expected_mfa),
        "r2_post_mfa_reentered": len(expected_reentry),
        "recovered_wav_ids": len(wav_ids),
    }
    if "source_wav_missing" in accounting:
        expected_accounting["source_wav_missing"] = len(source_missing_wav)
    if "corpus_extra_wav_ids" in accounting:
        expected_accounting["corpus_extra_wav_ids"] = len(corpus_extra_wav)
    for key, value in expected_accounting.items():
        if int(accounting.get(key, -1)) != value:
            raise RuntimeError(f"independent accounting differs: {key}")
    summary_expected = {
        "utterances": len(source_ids),
        "safe_utterances": len(expected_safe),
        "blocked_utterances": len(blocked),
        "unknown_involved_utterances": 0,
    }
    for key, value in summary_expected.items():
        if int(summary[key]) != value:
            raise RuntimeError(f"independent year summary differs: {key}")
    if len(source_ids) != len(expected_safe) + len(blocked) or expected_safe & set(blocked):
        raise RuntimeError("independent safe/follow-up partition differs")
    if expected_safe != expected_pre | expected_mfa or expected_pre & expected_mfa:
        raise RuntimeError("independent expected MFA input equation differs")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "release_id": contract["release_id"],
        "pronunciation_contract_id": contract["pronunciation_contract_id"],
        "year": year,
        "year_input_contract_id": contract["year_input_contract_id"],
        "verdict": {
            "exact_id_partition_passed": True,
            "recovered_wav_binding_passed": True,
            "wav_source_snapshot_binding_passed": True,
            "r2_post_mfa_failures_reentered_when_eligible": True,
            "production_mfa_allowed": False,
            "textgrid_materialization_allowed": False,
            "release_gate_remains_closed": True,
            "contract_build_only": True,
        },
        "checks": {
            "source_equals_safe_union_followup": True,
            "safe_followup_intersection_empty": True,
            "unknown_ids": 0,
            "year_summary_exact": True,
            "expected_mfa_input_equation_exact": True,
            "recovered_wav_equation_exact": True,
            "expected_mfa_input_has_wav": True,
            "output_row_content_and_order_exact": True,
            "output_fingerprints_exact": True,
        },
        "counts": expected_accounting,
        "output_row_digests": actual_digests,
        "inputs": {
            "year_input_contract": file_fingerprint(contract_path, with_sha256=True),
            **{
                key: contract["outputs"][key] for key in contract["outputs"]
            },
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.contract.resolve(), args.output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
