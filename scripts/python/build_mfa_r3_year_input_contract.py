"""Materialize an exact-ID r3 year input contract without running MFA.

The contract intersects the Stage 19 pronunciation-safe body with approved
pre-MFA technical exclusions.  Historical r2 post-MFA failures are explicitly
kept out of the exclusion side and re-enter the r3 input when otherwise
eligible.  The builder is read-only with respect to Stage 01-21, source audio,
and every r2 artifact.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import (
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
POLICY_SCHEMA = "mfa_r3_year_input_contract_policy.v1"
SCHEMA_VERSION = "mfa_r3_year_input_contract.v1"
STATUS = "materialized_pending_independent_year_input_audit_gate_closed"
RELEASE_SCHEMA = "common_pron_mfa_r3_staged_release.v1"
RELEASE_STATUS = "materialized_pending_independent_adoption_audit_and_release_gate"
RELEASE_AUDIT_STATUS = "passed_independent_staged_adoption_audit_pending_release_gate"
ROUTING_SCHEMA = "common_pron_r3_pre_adoption_routing.v1"
ROUTING_STATUS = "success_read_only_routing_not_adopted"

ID_FIELDS = ("year", "utt_id", "session_id", "source_csv")
FOLLOWUP_FIELDS = ID_FIELDS + (
    "routing_class",
    "hold_tokens_json",
    "policy_tokens_json",
    "unknown_tokens_json",
)
EXCLUSION_FIELDS = ID_FIELDS + ("reason_codes_json",)
REENTRY_FIELDS = ID_FIELDS + ("r2_post_mfa_reason_codes_json",)
SEARCH_REQUIRED_FIELDS = ("year", "utt_id", "session_id")
BLOCKED_REQUIRED_FIELDS = (
    "year",
    "utt_id",
    "routing_class",
    "hold_tokens_json",
    "policy_tokens_json",
    "unknown_tokens_json",
)
APPROVAL_REQUIRED_FIELDS = (
    "year",
    "utt_id",
    "reason_code",
    "exclusion_scope",
    "decision",
)

csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_fingerprint(record: dict, path: Path, label: str) -> None:
    if (
        Path(clean(record.get("path"))).resolve() != path.resolve()
        or not path.is_file()
        or int(record.get("bytes", -1)) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def fingerprint_for_final(temp: Path, final: Path) -> dict:
    result = file_fingerprint(temp, with_sha256=True)
    result["path"] = str(final.resolve())
    return result


@contextmanager
def deterministic_gzip_text_writer(path: Path) -> Iterator[TextIO]:
    with path.open("xb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", compresslevel=6, fileobj=raw, mtime=0
        ) as compressed:
            with io.TextIOWrapper(
                compressed, encoding="utf-8-sig", newline=""
            ) as stream:
                yield stream


def source_inventory_digest(files: list[Path], root: Path) -> dict[str, object]:
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


def verify_source_inventory(record: dict, search_root: Path) -> list[Path]:
    years = tuple(str(year) for year in range(2020, 2026))
    files = [
        path
        for year in years
        for path in sorted((search_root / year).glob("*.csv"))
    ]
    actual = source_inventory_digest(files, search_root)
    for key in ("root", "file_count", "total_bytes", "path_size_mtime_sha256"):
        if clean(actual[key]) != clean(record.get(key)):
            raise RuntimeError(f"frozen search-master inventory differs: {key}")
    return files


def load_year_summary(path: Path, year: str) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = [row for row in reader if clean(row.get("year")) == year]
    if len(rows) != 1:
        raise RuntimeError(f"routing year summary row count differs: {year}")
    return rows[0]


def load_blocked(path: Path, year: str) -> dict[str, dict[str, str]]:
    blocked: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(BLOCKED_REQUIRED_FIELDS).issubset(reader.fieldnames or ()):
            raise RuntimeError("blocked routing fields differ")
        for row in reader:
            if clean(row["year"]) != year:
                continue
            utt_id = clean(row["utt_id"])
            if not utt_id or utt_id in blocked:
                raise RuntimeError(f"blank or duplicate blocked utt_id: {utt_id!r}")
            if clean(row.get("safe_body_included")).lower() != "false":
                raise RuntimeError(f"blocked row marked safe: {utt_id}")
            unknown = json.loads(row["unknown_tokens_json"] or "[]")
            if unknown:
                raise RuntimeError(f"unknown pronunciation token remains: {utt_id}")
            blocked[utt_id] = row
    return blocked


def load_approval(
    manifest_path: Path, year: str, *, label: str
) -> tuple[dict, list[dict[str, str]]]:
    manifest = load_json(manifest_path)
    if (
        manifest.get("schema_version") != "mfa_approved_exclusions.v1"
        or manifest.get("status") != "approved"
        or clean(manifest.get("year")) != year
    ):
        raise RuntimeError(f"approved exclusion identity differs: {label}")
    review_path = Path(clean(manifest["review_csv"]["path"])).resolve()
    verify_fingerprint(manifest["review_csv"], review_path, f"{label} review CSV")
    rows: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    with review_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(APPROVAL_REQUIRED_FIELDS).issubset(reader.fieldnames or ()):
            raise RuntimeError(f"approved exclusion fields differ: {label}")
        for row in reader:
            if clean(row["year"]) != year or clean(row["decision"]).lower() != "approved":
                raise RuntimeError(f"non-approved or wrong-year exclusion: {label}")
            if clean(row["exclusion_scope"]) != "alignment_and_analysis":
                raise RuntimeError(f"exclusion scope differs: {label}")
            if not clean(row["utt_id"]) or not clean(row["reason_code"]):
                raise RuntimeError(f"blank approved exclusion identity: {label}")
            rows.append(row)
            counts[f"{clean(row['reason_code'])}|alignment_and_analysis"] += 1
    if len(rows) != int(manifest.get("row_count", -1)) or dict(counts) != {
        str(key): int(value) for key, value in manifest.get("counts", {}).items()
    }:
        raise RuntimeError(f"approved exclusion accounting differs: {label}")
    return manifest, rows


def collect_reason_ids(
    rows: list[dict[str, str]], allowed: set[str], *, label: str
) -> tuple[dict[str, set[str]], Counter[str]]:
    by_id: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()
    for row in rows:
        reason = clean(row["reason_code"])
        if reason not in allowed:
            continue
        utt_id = clean(row["utt_id"])
        if reason in by_id[utt_id]:
            raise RuntimeError(f"duplicate {label} row: {utt_id} {reason}")
        by_id[utt_id].add(reason)
        counts[reason] += 1
    return dict(by_id), counts


def scan_wav_ids(root: Path) -> set[str]:
    if not root.is_dir():
        raise RuntimeError(f"recovered WAV root missing: {root}")
    result: set[str] = set()
    for path in root.rglob("*.wav"):
        utt_id = path.stem
        if utt_id in result:
            raise RuntimeError(f"duplicate recovered WAV utt_id: {utt_id}")
        result.add(utt_id)
    return result


def id_row(year: str, row: dict[str, str], relative: str) -> dict[str, str]:
    return {
        "year": year,
        "utt_id": clean(row["utt_id"]),
        "session_id": clean(row.get("session_id")),
        "source_csv": relative,
    }


def contract_id(identity: dict) -> str:
    canonical = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_existing(path: Path, year: str, release_id: str) -> dict:
    manifest = load_json(path / f"YEAR_INPUT_CONTRACT_{year}.json")
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != STATUS
        or clean(manifest.get("year")) != year
        or clean(manifest.get("release_id")) != release_id
    ):
        raise RuntimeError("existing year input contract identity differs")
    for label, record in manifest.get("outputs", {}).items():
        verify_fingerprint(record, Path(clean(record["path"])), f"existing {label}")
    return manifest


def build(
    *,
    year: str,
    release_manifest_path: Path,
    release_audit_path: Path,
    policy_path: Path,
    initial_approval_path: Path,
    combined_approval_path: Path,
    corpus_contract_path: Path,
    output_root: Path,
) -> dict:
    policy = load_json(policy_path)
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "approved_contract_building_only_gate_closed"
        or year not in policy.get("scope", {}).get("years_enabled", [])
        or policy.get("scope", {}).get("production_mfa_allowed") is not False
        or policy.get("scope", {}).get("textgrid_materialization_allowed") is not False
    ):
        raise RuntimeError("year input policy identity or gate differs")
    release_id = clean(policy["release_id"])
    if output_root.exists():
        return validate_existing(output_root, year, release_id)

    release = load_json(release_manifest_path)
    release_audit = load_json(release_audit_path)
    if (
        release.get("schema_version") != RELEASE_SCHEMA
        or release.get("status") != RELEASE_STATUS
        or clean(release.get("release_id")) != release_id
        or release.get("scope", {}).get("allow_yearly_mfa") is not False
        or release_audit.get("status") != RELEASE_AUDIT_STATUS
        or release_audit.get("verdict", {}).get("production_mfa_allowed") is not False
        or release_audit.get("verdict", {}).get("release_gate_remains_closed") is not True
    ):
        raise RuntimeError("staged release or independent audit identity differs")
    verify_fingerprint(
        release_audit["inputs"]["release_manifest"],
        release_manifest_path,
        "release manifest through independent audit",
    )

    routing_manifest_path = Path(
        clean(release["inputs"]["stage19_routing_manifest"]["path"])
    ).resolve()
    verify_fingerprint(
        release["inputs"]["stage19_routing_manifest"],
        routing_manifest_path,
        "Stage 19 routing manifest",
    )
    routing = load_json(routing_manifest_path)
    if (
        routing.get("schema_version") != ROUTING_SCHEMA
        or routing.get("status") != ROUTING_STATUS
    ):
        raise RuntimeError("Stage 19 routing identity differs")
    search_meta_path = Path(
        clean(routing["inputs"]["search_master_build_meta"]["path"])
    ).resolve()
    verify_fingerprint(
        routing["inputs"]["search_master_build_meta"],
        search_meta_path,
        "frozen search-master build meta",
    )
    search_root = Path(clean(routing["inputs"]["search_master_inventory"]["root"])).resolve()
    all_search_files = verify_source_inventory(
        routing["inputs"]["search_master_inventory"], search_root
    )
    year_files = [path for path in all_search_files if path.parent.name == year]

    blocked_path = Path(clean(routing["outputs"]["blocked_utterance_routing"]["path"])).resolve()
    summary_path = Path(clean(routing["outputs"]["year_routing_summary"]["path"])).resolve()
    verify_fingerprint(
        routing["outputs"]["blocked_utterance_routing"], blocked_path, "blocked routing"
    )
    verify_fingerprint(
        routing["outputs"]["year_routing_summary"], summary_path, "routing year summary"
    )
    summary = load_year_summary(summary_path, year)
    blocked = load_blocked(blocked_path, year)

    year_policy = policy["years"][year]
    expected_summary = {
        "utterances": int(year_policy["expected_source_utterances"]),
        "safe_utterances": int(year_policy["expected_pronunciation_safe"]),
        "blocked_utterances": int(year_policy["expected_pronunciation_followup"]),
        "unknown_involved_utterances": int(year_policy["expected_unknown"]),
    }
    for key, expected in expected_summary.items():
        if int(summary[key]) != expected:
            raise RuntimeError(f"year routing summary differs: {key}")
    if len(year_files) != int(summary["search_master_csv_files"]):
        raise RuntimeError("year search-master file count differs")
    if len(blocked) != expected_summary["blocked_utterances"]:
        raise RuntimeError("blocked exact-ID count differs from year summary")

    initial_manifest, initial_rows = load_approval(
        initial_approval_path, year, label="initial pre-MFA approval"
    )
    combined_manifest, combined_rows = load_approval(
        combined_approval_path, year, label="combined r2 approval"
    )
    pre_reasons = set(policy["reason_policy"]["pre_mfa_technical_exclusions"])
    post_reasons = set(
        policy["reason_policy"]["r2_post_mfa_failures_must_not_be_pre_exclusions"]
    )
    all_combined_reasons = {clean(row["reason_code"]) for row in combined_rows}
    if not all_combined_reasons <= pre_reasons | post_reasons:
        raise RuntimeError("combined approval has an unclassified reason")
    initial_pre, _ = collect_reason_ids(
        initial_rows, pre_reasons, label="initial pre-MFA exclusion"
    )
    combined_pre, combined_pre_counts = collect_reason_ids(
        combined_rows, pre_reasons, label="combined pre-MFA exclusion"
    )
    post_ids, post_counts = collect_reason_ids(
        combined_rows, post_reasons, label="r2 post-MFA failure"
    )
    pre_ids: dict[str, set[str]] = defaultdict(set)
    for collection in (initial_pre, combined_pre):
        for utt_id, reasons in collection.items():
            pre_ids[utt_id].update(reasons)
    expected_pre_counts = {
        key: int(value)
        for key, value in year_policy["expected_approved_pre_mfa_reason_counts"].items()
    }
    if dict(combined_pre_counts) != expected_pre_counts:
        raise RuntimeError("approved pre-MFA reason counts differ")
    expected_post_counts = {
        key: int(value)
        for key, value in year_policy["expected_r2_post_mfa_reason_counts"].items()
    }
    if dict(post_counts) != expected_post_counts:
        raise RuntimeError("r2 post-MFA reason counts differ")

    corpus = load_json(corpus_contract_path)
    recovered_root = Path(clean(corpus.get("output_year"))).resolve()
    if (
        corpus.get("schema_version") != "wav_recovery_corpus.v1"
        or corpus.get("status") != "passed"
        or clean(corpus.get("year")) != year
        or clean(corpus.get("corpus_contract_id"))
        != clean(year_policy["recovered_corpus_contract_id"])
        or corpus.get("source_wav_tree_untouched") is not True
        or int(corpus.get("wav_files", -1))
        != int(year_policy["expected_recovered_wav_files"])
        or int(corpus.get("omitted_for_review", -1))
        != int(year_policy["expected_recovered_omitted"])
    ):
        raise RuntimeError("recovered WAV corpus contract differs")
    wav_ids = scan_wav_ids(recovered_root)
    if len(wav_ids) != int(corpus["wav_files"]):
        raise RuntimeError("recovered WAV exact-ID count differs")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    names = {
        "pronunciation_safe_ids": f"pronunciation_safe_ids_{year}.csv.gz",
        "pronunciation_followup_ids": f"pronunciation_followup_ids_{year}.csv.gz",
        "pre_mfa_exclusion_ids": f"pre_mfa_exclusion_ids_{year}.csv.gz",
        "expected_mfa_input_ids": f"expected_mfa_input_ids_{year}.csv.gz",
        "r2_post_mfa_reentry_ids": f"r2_post_mfa_reentry_ids_{year}.csv.gz",
    }
    temp_paths = {key: temp_root / name for key, name in names.items()}
    final_paths = {key: output_root / name for key, name in names.items()}
    writers = {}
    streams = []
    contexts = []
    field_map = {
        "pronunciation_safe_ids": ID_FIELDS,
        "pronunciation_followup_ids": FOLLOWUP_FIELDS,
        "pre_mfa_exclusion_ids": EXCLUSION_FIELDS,
        "expected_mfa_input_ids": ID_FIELDS,
        "r2_post_mfa_reentry_ids": REENTRY_FIELDS,
    }
    try:
        for key, path in temp_paths.items():
            context = deterministic_gzip_text_writer(path)
            stream = context.__enter__()
            contexts.append(context)
            streams.append(stream)
            writer = csv.DictWriter(stream, fieldnames=field_map[key], lineterminator="\n")
            writer.writeheader()
            writers[key] = writer

        seen: set[str] = set()
        source_ids: set[str] = set()
        applied_pre_ids: set[str] = set()
        expected_ids: set[str] = set()
        eligible_reentry_ids: set[str] = set()
        counts: Counter[str] = Counter()
        for file_index, path in enumerate(year_files, 1):
            relative = path.relative_to(search_root).as_posix()
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not set(SEARCH_REQUIRED_FIELDS).issubset(reader.fieldnames or ()):
                    raise RuntimeError(f"search-master fields differ: {path}")
                for row in reader:
                    if clean(row["year"]) != year:
                        raise RuntimeError(f"wrong year inside search master: {path}")
                    utt_id = clean(row["utt_id"])
                    if not utt_id or utt_id in seen:
                        raise RuntimeError(f"blank or duplicate source utt_id: {utt_id!r}")
                    seen.add(utt_id)
                    source_ids.add(utt_id)
                    base = id_row(year, row, relative)
                    blocked_row = blocked.get(utt_id)
                    if blocked_row is not None:
                        writers["pronunciation_followup_ids"].writerow(
                            {
                                **base,
                                "routing_class": blocked_row["routing_class"],
                                "hold_tokens_json": blocked_row["hold_tokens_json"],
                                "policy_tokens_json": blocked_row["policy_tokens_json"],
                                "unknown_tokens_json": blocked_row["unknown_tokens_json"],
                            }
                        )
                        counts["pronunciation_followup"] += 1
                        continue
                    writers["pronunciation_safe_ids"].writerow(base)
                    counts["pronunciation_safe"] += 1
                    if utt_id in pre_ids:
                        writers["pre_mfa_exclusion_ids"].writerow(
                            {
                                **base,
                                "reason_codes_json": json.dumps(
                                    sorted(pre_ids[utt_id]), ensure_ascii=False
                                ),
                            }
                        )
                        applied_pre_ids.add(utt_id)
                        counts["pre_mfa_exclusion"] += 1
                        continue
                    if utt_id not in wav_ids:
                        raise RuntimeError(
                            f"pronunciation-safe eligible utterance lacks recovered WAV: {utt_id}"
                        )
                    writers["expected_mfa_input_ids"].writerow(base)
                    expected_ids.add(utt_id)
                    counts["expected_mfa_input"] += 1
                    if utt_id in post_ids:
                        writers["r2_post_mfa_reentry_ids"].writerow(
                            {
                                **base,
                                "r2_post_mfa_reason_codes_json": json.dumps(
                                    sorted(post_ids[utt_id]), ensure_ascii=False
                                ),
                            }
                        )
                        eligible_reentry_ids.add(utt_id)
                        counts["r2_post_mfa_reentry"] += 1
            if file_index % 500 == 0:
                print(
                    f"[{year}] {file_index:,}/{len(year_files):,} CSV; "
                    f"{len(seen):,} utterances",
                    flush=True,
                )
    finally:
        for context in reversed(contexts):
            context.__exit__(*sys.exc_info())

    if len(source_ids) != expected_summary["utterances"]:
        raise RuntimeError("source exact-ID count differs from year summary")
    if set(blocked) - source_ids:
        raise RuntimeError("blocked routing contains unknown source IDs")
    approval_ids = set(pre_ids) | set(post_ids)
    if approval_ids - source_ids:
        raise RuntimeError("approved exclusions contain unknown source IDs")
    if counts["pronunciation_safe"] != expected_summary["safe_utterances"]:
        raise RuntimeError("pronunciation-safe exact-ID count differs")
    if counts["pronunciation_followup"] != expected_summary["blocked_utterances"]:
        raise RuntimeError("pronunciation-followup exact-ID count differs")
    if counts["pronunciation_safe"] + counts["pronunciation_followup"] != len(source_ids):
        raise RuntimeError("source != pronunciation-safe union follow-up")
    if applied_pre_ids & set(blocked):
        raise RuntimeError("applied pre-MFA exclusions intersect pronunciation follow-up")
    if expected_ids & applied_pre_ids or expected_ids | applied_pre_ids != source_ids - set(blocked):
        raise RuntimeError("expected MFA input equation differs")
    audio_pairing_ids = {
        utt_id for utt_id, reasons in pre_ids.items() if "audio_pairing_unresolved" in reasons
    }
    if source_ids - wav_ids != audio_pairing_ids or wav_ids - source_ids:
        raise RuntimeError("recovered WAV IDs != source IDs minus audio pairing unresolved")
    if any(post_reasons & reasons for reasons in (pre_ids[utt_id] for utt_id in applied_pre_ids)):
        raise RuntimeError("r2 post-MFA failure leaked into pre-MFA exclusions")
    expected_eligible_reentry = set(post_ids) & expected_ids
    if eligible_reentry_ids != expected_eligible_reentry:
        raise RuntimeError("r2 post-MFA eligible re-entry accounting differs")

    outputs = {
        key: fingerprint_for_final(temp_paths[key], final_paths[key]) for key in names
    }
    inputs = {
        "staged_release_manifest": file_fingerprint(
            release_manifest_path, with_sha256=True
        ),
        "staged_release_independent_audit": file_fingerprint(
            release_audit_path, with_sha256=True
        ),
        "year_input_policy": file_fingerprint(policy_path, with_sha256=True),
        "stage19_routing_manifest": file_fingerprint(
            routing_manifest_path, with_sha256=True
        ),
        "frozen_search_master_build_meta": file_fingerprint(
            search_meta_path, with_sha256=True
        ),
        "frozen_search_master_inventory": routing["inputs"]["search_master_inventory"],
        "stage19_blocked_routing": file_fingerprint(blocked_path, with_sha256=True),
        "stage19_year_summary": file_fingerprint(summary_path, with_sha256=True),
        "initial_pre_mfa_approval_manifest": file_fingerprint(
            initial_approval_path, with_sha256=True
        ),
        "initial_pre_mfa_approval_csv": initial_manifest["review_csv"],
        "combined_r2_approval_manifest": file_fingerprint(
            combined_approval_path, with_sha256=True
        ),
        "combined_r2_approval_csv": combined_manifest["review_csv"],
        "recovered_wav_corpus_contract": file_fingerprint(
            corpus_contract_path, with_sha256=True
        ),
    }
    accounting = {
        "source_utterances": len(source_ids),
        "pronunciation_safe": counts["pronunciation_safe"],
        "pronunciation_followup": counts["pronunciation_followup"],
        "unknown": 0,
        "approved_pre_mfa_ids_total": len(pre_ids),
        "pre_mfa_exclusions_applied_to_pron_safe": len(applied_pre_ids),
        "approved_pre_mfa_already_in_pron_followup": len(set(pre_ids) & set(blocked)),
        "expected_mfa_input": len(expected_ids),
        "r2_post_mfa_failure_ids_total": len(post_ids),
        "r2_post_mfa_reentered": len(eligible_reentry_ids),
        "r2_post_mfa_outside_pron_safe_or_technically_ineligible": len(post_ids)
        - len(eligible_reentry_ids),
        "recovered_wav_ids": len(wav_ids),
        "recovered_corpus_omitted": int(corpus["omitted_for_review"]),
        "approved_pre_mfa_reason_counts": dict(sorted(combined_pre_counts.items())),
        "r2_post_mfa_reason_counts": dict(sorted(post_counts.items())),
    }
    identity = {
        "release_id": release_id,
        "pronunciation_contract_id": release["pronunciation_contract_id"],
        "year": year,
        "stage19_blocked_sha256": inputs["stage19_blocked_routing"]["sha256"],
        "stage19_year_summary_sha256": inputs["stage19_year_summary"]["sha256"],
        "search_master_inventory_sha256": routing["inputs"]["search_master_inventory"][
            "path_size_mtime_sha256"
        ],
        "initial_approval_sha256": inputs["initial_pre_mfa_approval_manifest"]["sha256"],
        "combined_approval_sha256": inputs["combined_r2_approval_manifest"]["sha256"],
        "corpus_contract_id": corpus["corpus_contract_id"],
        "policy_sha256": inputs["year_input_policy"]["sha256"],
        "output_sha256": {key: record["sha256"] for key, record in outputs.items()},
        "accounting": accounting,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "release_id": release_id,
        "pronunciation_contract_id": release["pronunciation_contract_id"],
        "year": year,
        "year_input_contract_id": contract_id(identity),
        "scope": {
            "exact_id_lists_materialized": True,
            "production_mfa_allowed": False,
            "textgrid_materialization_allowed": False,
            "stage_01_21_modified": False,
            "r2_artifacts_modified": False,
            "raw_corpus_modified": False,
        },
        "equations": {
            "source_equals_pron_safe_union_followup": True,
            "pron_safe_intersect_followup_empty": True,
            "expected_mfa_input_equals_pron_safe_minus_pre_mfa_exclusions": True,
            "recovered_wav_ids_equal_source_minus_audio_pairing_unresolved": True,
            "r2_post_mfa_failures_are_not_pre_mfa_exclusions": True,
        },
        "inputs": inputs,
        "corpus_binding": {
            "corpus_contract_id": corpus["corpus_contract_id"],
            "recovered_wav_root": str(recovered_root),
            "source_wav_tree_untouched": True,
        },
        "accounting": accounting,
        "outputs": outputs,
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    manifest_temp = temp_root / f"YEAR_INPUT_CONTRACT_{year}.json"
    manifest_temp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--year", required=True)
    result.add_argument("--release-manifest", type=Path, required=True)
    result.add_argument("--release-audit", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--initial-approval", type=Path, required=True)
    result.add_argument("--combined-approval", type=Path, required=True)
    result.add_argument("--corpus-contract", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build(
        year=args.year,
        release_manifest_path=args.release_manifest.resolve(),
        release_audit_path=args.release_audit.resolve(),
        policy_path=args.policy.resolve(),
        initial_approval_path=args.initial_approval.resolve(),
        combined_approval_path=args.combined_approval.resolve(),
        corpus_contract_path=args.corpus_contract.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
