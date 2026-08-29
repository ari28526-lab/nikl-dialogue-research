#!/usr/bin/env python3
"""Independently audit every full Bareun-v3.1 morphology TextGrid derivative."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_bareun_morph_textgrid_pilot import (  # noqa: E402
    build_new_morph_label,
    load_receipt_rows,
    resolve_path,
)
from pipeline_common import atomic_write_json, now_iso, sha256_file  # noqa: E402
from run_bareun_morph_textgrid_full import (  # noqa: E402
    INVENTORY_FIELDS,
    load_config,
    pid_is_alive,
    source_location,
    storage_roots,
    verify_derived,
)


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_morph_textgrid_full_v1.json"


def read_shard_inventory(path: Path) -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("\t")
        if len(parts) != 5 or len(parts[1]) != 64 or len(parts[4]) != 64:
            raise RuntimeError(f"invalid shard inventory line {line_number}")
        rows.append((parts[0], parts[1], parts[2], parts[3], parts[4]))
    return rows


def read_output_inventory(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != INVENTORY_FIELDS:
            raise RuntimeError(f"output inventory schema mismatch: {path}")
        return list(reader)


def init_audit_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS audited_shards (
        receipt_relative TEXT PRIMARY KEY,
        bareun_receipt_sha256 TEXT NOT NULL,
        shard_receipt_sha256 TEXT NOT NULL,
        output_inventory_sha256 TEXT NOT NULL,
        utterances INTEGER NOT NULL,
        derived INTEGER NOT NULL,
        no_mfa_alignment INTEGER NOT NULL,
        alignment_conflicts INTEGER NOT NULL,
        output_bytes INTEGER NOT NULL,
        audited_at TEXT NOT NULL
        )"""
    )
    return connection


def create_audit_lock(primary_root: Path, *, resume: bool) -> Path:
    lock_path = primary_root / "AUDIT.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        old_pid = int(lock.get("pid", -1))
        if pid_is_alive(old_pid):
            raise RuntimeError(f"active auditor already exists: pid={old_pid}")
        if not resume:
            raise RuntimeError("stale audit lock exists; use --resume")
        archive = primary_root / f"AUDIT.lock.stale.{int(time.time())}.json"
        if archive.exists():
            raise FileExistsError(archive)
        lock_path.replace(archive)
    atomic_write_json(
        lock_path,
        {
            "schema": "bareun_morph_textgrid_full_audit_lock.v1",
            "pid": os.getpid(),
            "started_at": now_iso(),
            "resume": resume,
        },
    )
    return lock_path


def audit_one_shard(
    *,
    final_root: Path,
    source_root: Path,
    roots: Mapping[str, Path],
    primary_root: Path,
    receipt_relative: str,
    bareun_receipt_sha: str,
    storage_id: str,
    shard_receipt_relative: str,
    shard_receipt_sha: str,
) -> dict[str, int]:
    shard_receipt_path = primary_root / shard_receipt_relative
    if sha256_file(shard_receipt_path) != shard_receipt_sha:
        raise RuntimeError(f"shard receipt SHA mismatch: {shard_receipt_path}")
    shard = json.loads(shard_receipt_path.read_text(encoding="utf-8"))
    if shard.get("status") != "completed":
        raise RuntimeError(f"shard is not completed: {shard_receipt_path}")
    if shard.get("bareun_receipt_relative") != receipt_relative:
        raise RuntimeError(f"shard/Bareun receipt mismatch: {shard_receipt_path}")
    if shard.get("bareun_receipt_sha256") != bareun_receipt_sha:
        raise RuntimeError(f"shard/Bareun SHA mismatch: {shard_receipt_path}")
    if shard.get("storage_id") != storage_id:
        raise RuntimeError(f"shard storage mismatch: {shard_receipt_path}")
    output_inventory = primary_root / shard["output_inventory_relative"]
    if output_inventory.stat().st_size != int(shard["output_inventory_bytes"]):
        raise RuntimeError(f"output inventory size mismatch: {output_inventory}")
    output_inventory_sha = sha256_file(output_inventory)
    if output_inventory_sha != shard["output_inventory_sha256"]:
        raise RuntimeError(f"output inventory SHA mismatch: {output_inventory}")

    receipt, utterances, morph_by_utt = load_receipt_rows(
        final_root, receipt_relative, bareun_receipt_sha
    )
    source_file = str(receipt["source_file"])
    expected_by_utt = {str(row["utt_id"]): row for row in utterances}
    output_rows = read_output_inventory(output_inventory)
    if len(output_rows) != len(utterances):
        raise RuntimeError(
            f"utterance inventory count mismatch: {receipt_relative} "
            f"{len(output_rows)} != {len(utterances)}"
        )
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    for row in output_rows:
        utt_id = row["utt_id"]
        if utt_id in seen or utt_id not in expected_by_utt:
            raise RuntimeError(f"duplicate or unknown utt_id: {receipt_relative} {utt_id}")
        seen.add(utt_id)
        utterance = expected_by_utt[utt_id]
        if row["source_row_index"] != str(utterance["source_row_index"]):
            raise RuntimeError(f"source row mismatch: {utt_id}")
        expected_tokens = int(utterance["response_token_count"])
        expected_label, expected_morph_count = build_new_morph_label(
            morph_by_utt.get(utt_id, []), expected_tokens
        )
        if int(row["morph_count"]) != expected_morph_count:
            raise RuntimeError(f"morph count mismatch: {utt_id}")
        year, session, source = source_location(source_root, source_file, utt_id)
        if row["status"] == "no_mfa_alignment":
            if source.exists():
                raise RuntimeError(f"source exists but recorded no MFA: {source}")
            if any(row[name] for name in ("storage_id", "derived_relative", "sha256")):
                raise RuntimeError(f"no-MFA row has output identity: {utt_id}")
            counts["no_mfa_alignment"] += 1
            counts["utterances"] += 1
            continue
        if row["status"] != "derived" or row["storage_id"] != storage_id:
            raise RuntimeError(f"derived status/storage mismatch: {utt_id}")
        if not source.is_file():
            raise RuntimeError(f"source TextGrid missing: {source}")
        expected_relative = (
            Path("textgrids") / year / session / f"{utt_id}.TextGrid"
        ).as_posix()
        if row["derived_relative"] != expected_relative:
            raise RuntimeError(f"derived relative mismatch: {utt_id}")
        derived = roots[storage_id] / expected_relative
        if not derived.is_file():
            raise RuntimeError(f"derived TextGrid missing: {derived}")
        if source.stat().st_size != int(row["source_bytes"]):
            raise RuntimeError(f"source size mismatch: {source}")
        if sha256_file(source) != row["source_sha256"]:
            raise RuntimeError(f"source SHA mismatch: {source}")
        if derived.stat().st_size != int(row["bytes"]):
            raise RuntimeError(f"derived size mismatch: {derived}")
        if sha256_file(derived) != row["sha256"]:
            raise RuntimeError(f"derived SHA mismatch: {derived}")
        verified = verify_derived(source, derived, expected_label)
        labeled_words = int(verified["labeled_word_count"])
        if labeled_words != int(row["labeled_word_count"]):
            raise RuntimeError(f"labeled word count mismatch: {utt_id}")
        expected_conflict = str(labeled_words != expected_tokens).lower()
        if row["alignment_conflict"] != expected_conflict:
            raise RuntimeError(f"alignment conflict flag mismatch: {utt_id}")
        counts["utterances"] += 1
        counts["derived"] += 1
        counts["alignment_conflicts"] += int(expected_conflict == "true")
        counts["output_bytes"] += int(row["bytes"])
    if seen != set(expected_by_utt):
        raise RuntimeError(f"utterance identity coverage mismatch: {receipt_relative}")
    expected_counts = shard["counts"]
    for key in (
        "utterances",
        "derived",
        "no_mfa_alignment",
        "alignment_conflicts",
        "output_bytes",
    ):
        if int(counts[key]) != int(expected_counts[key]):
            raise RuntimeError(f"shard count mismatch {key}: {receipt_relative}")
    counts["output_inventory_sha256"] = output_inventory_sha  # type: ignore[assignment]
    return dict(counts)


def audit_state(
    primary_root: Path,
    *,
    status: str,
    completed: int,
    total: int,
    counts: Mapping[str, int],
    started_epoch: float,
    current_receipt: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    elapsed = max(time.time() - started_epoch, 0.001)
    rate = completed / elapsed
    payload: dict[str, Any] = {
        "schema": "bareun_morph_textgrid_full_audit_state.v1",
        "status": status,
        "updated_at": now_iso(),
        "completed_receipts": completed,
        "total_receipts": total,
        "current_receipt": current_receipt,
        "counts": dict(counts),
        "session_rate_receipts_per_second": round(rate, 4),
        "eta_seconds": round((total - completed) / rate) if rate > 0 else None,
    }
    if error:
        payload["error"] = error
    atomic_write_json(primary_root / "AUDIT_STATE.json", payload)
    return payload


def sum_database(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """SELECT COUNT(*), SUM(utterances), SUM(derived),
        SUM(no_mfa_alignment), SUM(alignment_conflicts), SUM(output_bytes)
        FROM audited_shards"""
    ).fetchone()
    return {
        "audited_receipts": int(row[0] or 0),
        "utterances": int(row[1] or 0),
        "derived": int(row[2] or 0),
        "no_mfa_alignment": int(row[3] or 0),
        "alignment_conflicts": int(row[4] or 0),
        "output_bytes": int(row[5] or 0),
    }


def execute(config_path: Path, config: Mapping[str, Any], *, resume: bool) -> dict[str, Any]:
    roots = storage_roots(config)
    primary_root = roots[str(config["storage"]["primary_id"])]
    manifest_path = primary_root / "BUILD_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError("BUILD_MANIFEST.json missing; build is not complete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != config["output"]["completion_state"]:
        raise RuntimeError("build completion state mismatch")
    inventory_path = primary_root / manifest["shard_receipt_inventory"]
    if inventory_path.stat().st_size != int(manifest["shard_receipt_inventory_bytes"]):
        raise RuntimeError("global shard inventory size mismatch")
    if sha256_file(inventory_path) != manifest["shard_receipt_inventory_sha256"]:
        raise RuntimeError("global shard inventory SHA mismatch")
    rows = read_shard_inventory(inventory_path)
    expected_receipts = int(config["input"]["expected_bareun_receipts"])
    if len(rows) != expected_receipts:
        raise RuntimeError(f"shard count mismatch: {len(rows)} != {expected_receipts}")
    report_path = resolve_path(config["output"]["audit_report"])
    if report_path.exists():
        existing = json.loads(report_path.read_text(encoding="utf-8"))
        if existing.get("passed") is True and existing.get("build_manifest_sha256") == sha256_file(manifest_path):
            return existing
        raise RuntimeError(f"audit report already exists but is not reusable: {report_path}")
    audit_db = primary_root / "AUDIT_CHECKPOINT.sqlite"
    if audit_db.exists() and not resume:
        raise RuntimeError("audit checkpoint exists; use --resume")
    audit_lock = create_audit_lock(primary_root, resume=resume)
    connection = init_audit_database(audit_db)
    started_epoch = time.time()
    final_root = resolve_path(config["input"]["bareun_final_root"])
    source_root = resolve_path(config["input"]["source_textgrid_root"])
    current_receipt: str | None = None
    try:
        for receipt_relative, bareun_sha, storage_id, shard_relative, shard_sha in rows:
            current_receipt = receipt_relative
            completed = connection.execute(
                """SELECT bareun_receipt_sha256, shard_receipt_sha256,
                output_inventory_sha256 FROM audited_shards
                WHERE receipt_relative=?""",
                (receipt_relative,),
            ).fetchone()
            shard_path = primary_root / shard_relative
            shard = json.loads(shard_path.read_text(encoding="utf-8"))
            output_inventory = primary_root / shard["output_inventory_relative"]
            output_inventory_sha = sha256_file(output_inventory)
            if completed:
                if tuple(completed) != (bareun_sha, shard_sha, output_inventory_sha):
                    raise RuntimeError(f"audit resume SHA mismatch: {receipt_relative}")
                continue
            counts = audit_one_shard(
                final_root=final_root,
                source_root=source_root,
                roots=roots,
                primary_root=primary_root,
                receipt_relative=receipt_relative,
                bareun_receipt_sha=bareun_sha,
                storage_id=storage_id,
                shard_receipt_relative=shard_relative,
                shard_receipt_sha=shard_sha,
            )
            connection.execute(
                """INSERT INTO audited_shards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    receipt_relative,
                    bareun_sha,
                    shard_sha,
                    counts.pop("output_inventory_sha256"),
                    counts["utterances"],
                    counts["derived"],
                    counts["no_mfa_alignment"],
                    counts["alignment_conflicts"],
                    counts["output_bytes"],
                    now_iso(),
                ),
            )
            connection.commit()
            summed = sum_database(connection)
            audit_state(
                primary_root,
                status="running",
                completed=summed["audited_receipts"],
                total=expected_receipts,
                counts=summed,
                started_epoch=started_epoch,
                current_receipt=receipt_relative,
            )
        totals = sum_database(connection)
        expected = config["input"]
        mismatches = {
            name: pair
            for name, pair in {
                "receipts": (totals["audited_receipts"], expected_receipts),
                "utterances": (totals["utterances"], int(expected["expected_utterances"])),
                "derived": (totals["derived"], int(expected["expected_aligned_textgrids"])),
                "no_mfa_alignment": (
                    totals["no_mfa_alignment"],
                    int(expected["expected_no_mfa_alignment"]),
                ),
            }.items()
            if int(pair[0]) != int(pair[1])
        }
        if mismatches:
            raise RuntimeError(f"full audit count mismatch: {mismatches}")
        report = {
            "schema": "bareun_morph_textgrid_full_audit.v1",
            "audited_at": now_iso(),
            "passed": True,
            "counts": totals,
            "build_manifest_sha256": sha256_file(manifest_path),
            "shard_receipt_inventory_sha256": sha256_file(inventory_path),
            "bareun_v3_1_labels_match": True,
            "source_textgrids_unchanged_by_sha": True,
            "first_five_tiers_semantically_unchanged": True,
            "morph_tier_boundaries_unchanged": True,
            "source_wav_accessed": False,
            "mfa_rerun": False,
            "external_consolidation_required": True,
            "errors": [],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(report_path, report)
        audit_state(
            primary_root,
            status="passed_pending_external_consolidation",
            completed=totals["audited_receipts"],
            total=expected_receipts,
            counts=totals,
            started_epoch=started_epoch,
        )
        return report
    except BaseException as exc:
        totals = sum_database(connection)
        audit_state(
            primary_root,
            status="failed_safe_to_resume",
            completed=totals["audited_receipts"],
            total=expected_receipts,
            counts=totals,
            started_epoch=started_epoch,
            current_receipt=current_receipt,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    finally:
        connection.close()
        if audit_lock.exists():
            audit_lock.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    result = execute(config_path, config, resume=args.resume)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
