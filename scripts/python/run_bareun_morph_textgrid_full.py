#!/usr/bin/env python3
"""Build the full Bareun-v3.1 morphology TextGrid derivative safely.

The frozen Bareun CSV release and r3 six-tier TextGrids are read-only.  Work is
routed one Bareun receipt at a time to D: first and then to a local C: spill
root, without crossing either configured free-space floor.  A SQLite journal
and per-receipt inventories make an interrupted run resumable.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time
from typing import Any, Iterable, Mapping, Sequence
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_bareun_morph_textgrid_pilot import (  # noqa: E402
    FIRST_FIVE,
    build_new_morph_label,
    load_receipt_rows,
    one_labeled_interval,
    read_inventory,
    resolve_path,
    same_edges,
    same_intervals,
)
from pipeline_common import atomic_write_json, now_iso, sha256_file  # noqa: E402
from research_textgrid_v2 import (  # noqa: E402
    BASE_TIERS,
    parse_mfa_textgrid,
    write_textgrid_exact,
)


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_morph_textgrid_full_v1.json"
GIB = 1024**3
YEAR_PATTERN = re.compile(r"NIKL_DIALOGUE_(20\d{2})")
INVENTORY_FIELDS = [
    "utt_id",
    "source_row_index",
    "status",
    "storage_id",
    "derived_relative",
    "bytes",
    "sha256",
    "source_bytes",
    "source_sha256",
    "response_token_count",
    "labeled_word_count",
    "morph_count",
    "alignment_conflict",
    "label_changed",
    "old_label_sha256",
    "new_label_sha256",
]


class StorageSafetyStop(RuntimeError):
    """Raised before a receipt when neither volume can remain above its floor."""


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "bareun_morph_textgrid_full_config.v1":
        raise RuntimeError("full TextGrid config schema mismatch")
    if config["contract"]["tier_order"] != BASE_TIERS:
        raise RuntimeError("six-tier contract mismatch")
    if config["output"].get("promotion_during_build") is not False:
        raise RuntimeError("promotion_during_build must remain false")
    return config


def storage_roots(config: Mapping[str, Any]) -> dict[str, Path]:
    storage = config["storage"]
    return {
        str(storage["primary_id"]): resolve_path(storage["primary_building_root"]),
        str(storage["spill_id"]): resolve_path(storage["spill_building_root"]),
    }


def free_bytes_for(path: Path) -> int:
    anchor = Path(path.anchor or path).resolve()
    return int(shutil.disk_usage(anchor).free)


def choose_storage(
    *,
    required_bytes: int,
    primary_free_bytes: int,
    primary_floor_bytes: int,
    spill_free_bytes: int,
    spill_floor_bytes: int,
    primary_id: str = "external_d",
    spill_id: str = "local_c",
) -> str:
    if primary_free_bytes - required_bytes >= primary_floor_bytes:
        return primary_id
    if spill_free_bytes - required_bytes >= spill_floor_bytes:
        return spill_id
    raise StorageSafetyStop(
        "next receipt cannot fit above either storage floor: "
        f"required={required_bytes} primary_free={primary_free_bytes} "
        f"primary_floor={primary_floor_bytes} spill_free={spill_free_bytes} "
        f"spill_floor={spill_floor_bytes}"
    )


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_location(
    source_root: Path, source_file: str, utt_id: str
) -> tuple[str, str, Path]:
    match = YEAR_PATTERN.search(source_file)
    if not match:
        raise RuntimeError(f"year unavailable from source_file: {source_file}")
    year = match.group(1)
    session = Path(source_file).stem
    return year, session, source_root / year / session / f"{utt_id}.TextGrid"


def output_relative(year: str, session: str, utt_id: str) -> Path:
    return Path("textgrids") / year / session / f"{utt_id}.TextGrid"


def derive_atomic(source: Path, destination: Path, new_label: str) -> dict[str, Any]:
    """Create and validate one derivative, refusing to overwrite anything."""

    if destination.exists():
        raise FileExistsError(destination)
    duration, source_tiers = parse_mfa_textgrid(source)
    if duration is None or list(source_tiers) != BASE_TIERS:
        raise RuntimeError(f"source six-tier contract mismatch: {source}")
    morph_intervals = list(source_tiers["morph_analysis_utt"])
    label_index, old_label = one_labeled_interval(
        morph_intervals, "morph_analysis_utt"
    )
    begin, end, _ = morph_intervals[label_index]
    morph_intervals[label_index] = (begin, end, new_label)
    tier_data = [(name, list(source_tiers[name])) for name in FIRST_FIVE] + [
        ("morph_analysis_utt", morph_intervals)
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    # ``write_textgrid_exact`` stages once more before promoting to this path.
    # Repeating the full destination name in both staging layers can cross the
    # legacy Windows MAX_PATH limit in the deeper C: spill root.  Keep this
    # outer diagnostic partial unique but deliberately short.
    temporary = destination.with_name(f".{uuid.uuid4().hex}.partial")
    write_textgrid_exact(temporary, duration=float(duration), tier_data=tier_data)
    try:
        verified = verify_derived_against_parsed_source(
            source_duration=float(duration),
            source_tiers=source_tiers,
            derived=temporary,
            expected_label=new_label,
        )
        if destination.exists():
            raise FileExistsError(destination)
        os.replace(temporary, destination)
    except BaseException:
        # Preserve a partial artifact for diagnosis.  It is never adopted by name.
        raise
    return {
        "old_label": old_label,
        "duration": float(duration),
        "labeled_word_count": int(verified["labeled_word_count"]),
    }


def verify_derived(source: Path, derived: Path, expected_label: str) -> dict[str, Any]:
    source_duration, source_tiers = parse_mfa_textgrid(source)
    if source_duration is None:
        raise RuntimeError("source TextGrid duration missing")
    return verify_derived_against_parsed_source(
        source_duration=float(source_duration),
        source_tiers=source_tiers,
        derived=derived,
        expected_label=expected_label,
    )


def verify_derived_against_parsed_source(
    *,
    source_duration: float,
    source_tiers: Mapping[str, Sequence[tuple[float, float, str]]],
    derived: Path,
    expected_label: str,
) -> dict[str, Any]:
    derived_duration, derived_tiers = parse_mfa_textgrid(derived)
    if derived_duration is None:
        raise RuntimeError("TextGrid duration missing")
    if list(source_tiers) != BASE_TIERS or list(derived_tiers) != BASE_TIERS:
        raise RuntimeError("six-tier contract mismatch")
    if abs(source_duration - float(derived_duration)) > 1e-6:
        raise RuntimeError("duration changed")
    if not all(
        same_intervals(source_tiers[name], derived_tiers[name])
        for name in FIRST_FIVE
    ):
        raise RuntimeError("protected tier changed")
    if not same_edges(
        source_tiers["morph_analysis_utt"],
        derived_tiers["morph_analysis_utt"],
    ):
        raise RuntimeError("morph tier boundary changed")
    _, old_label = one_labeled_interval(
        source_tiers["morph_analysis_utt"], "source morph_analysis_utt"
    )
    _, derived_label = one_labeled_interval(
        derived_tiers["morph_analysis_utt"], "derived morph_analysis_utt"
    )
    if derived_label != expected_label:
        raise RuntimeError("derived morphology label mismatch")
    return {
        "old_label": old_label,
        "labeled_word_count": sum(
            1 for _, _, label in source_tiers["words"] if str(label)
        ),
    }


def init_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS shards (
            source_file TEXT PRIMARY KEY,
            receipt_relative TEXT NOT NULL,
            receipt_sha256 TEXT NOT NULL,
            storage_id TEXT NOT NULL,
            status TEXT NOT NULL,
            estimated_bytes INTEGER NOT NULL,
            aligned_expected INTEGER NOT NULL,
            output_count INTEGER NOT NULL DEFAULT 0,
            no_mfa_count INTEGER NOT NULL DEFAULT 0,
            conflict_count INTEGER NOT NULL DEFAULT 0,
            changed_count INTEGER NOT NULL DEFAULT 0,
            unchanged_count INTEGER NOT NULL DEFAULT 0,
            output_bytes INTEGER NOT NULL DEFAULT 0,
            shard_receipt_relative TEXT,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS outputs (
            source_file TEXT NOT NULL,
            utt_id TEXT NOT NULL,
            source_row_index TEXT NOT NULL,
            status TEXT NOT NULL,
            storage_id TEXT,
            derived_relative TEXT,
            bytes INTEGER,
            sha256 TEXT,
            source_bytes INTEGER,
            source_sha256 TEXT,
            response_token_count INTEGER NOT NULL,
            labeled_word_count INTEGER,
            morph_count INTEGER NOT NULL,
            alignment_conflict INTEGER NOT NULL,
            label_changed INTEGER NOT NULL,
            old_label_sha256 TEXT,
            new_label_sha256 TEXT NOT NULL,
            PRIMARY KEY (source_file, utt_id)
        );
        CREATE INDEX IF NOT EXISTS outputs_status_idx ON outputs(status);
        """
    )
    return connection


def database_counts(connection: sqlite3.Connection) -> dict[str, int]:
    output = connection.execute(
        """SELECT
        COUNT(*),
        SUM(CASE WHEN status='derived' THEN 1 ELSE 0 END),
        SUM(CASE WHEN status='no_mfa_alignment' THEN 1 ELSE 0 END),
        SUM(alignment_conflict), SUM(label_changed),
        SUM(CASE WHEN status='derived' THEN COALESCE(bytes,0) ELSE 0 END)
        FROM outputs"""
    ).fetchone()
    receipts = connection.execute(
        "SELECT COUNT(*) FROM shards WHERE status='completed'"
    ).fetchone()[0]
    return {
        "utterances": int(output[0] or 0),
        "derived": int(output[1] or 0),
        "no_mfa_alignment": int(output[2] or 0),
        "alignment_conflicts": int(output[3] or 0),
        "label_changed": int(output[4] or 0),
        "output_bytes": int(output[5] or 0),
        "completed_receipts": int(receipts or 0),
    }


def atomic_gzip_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    with gzip.open(temporary, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=INVENTORY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    if path.exists():
        raise FileExistsError(path)
    os.replace(temporary, path)


def output_rows_for_shard(
    connection: sqlite3.Connection, source_file: str
) -> list[dict[str, Any]]:
    columns = [row[1] for row in connection.execute("PRAGMA table_info(outputs)")]
    cursor = connection.execute(
        "SELECT * FROM outputs WHERE source_file=? ORDER BY CAST(source_row_index AS INTEGER), utt_id",
        (source_file,),
    )
    rows = []
    for values in cursor:
        row = dict(zip(columns, values))
        for name in ("alignment_conflict", "label_changed"):
            row[name] = str(bool(row[name])).lower()
        rows.append({name: row.get(name, "") for name in INVENTORY_FIELDS})
    return rows


def write_shard_receipt(
    *,
    primary_root: Path,
    receipt_relative: str,
    receipt_sha: str,
    source_file: str,
    storage_id: str,
    connection: sqlite3.Connection,
) -> tuple[str, dict[str, Any]]:
    receipt_parent = Path(receipt_relative).parent
    control_root = primary_root / "shards" / receipt_parent
    inventory_path = control_root / "OUTPUT_INVENTORY.tsv.gz"
    shard_receipt_path = control_root / "SHARD_RECEIPT.json"
    if shard_receipt_path.exists():
        existing = json.loads(shard_receipt_path.read_text(encoding="utf-8"))
        if (
            existing.get("status") == "completed"
            and existing.get("bareun_receipt_relative") == receipt_relative
            and existing.get("bareun_receipt_sha256") == receipt_sha
            and existing.get("storage_id") == storage_id
            and inventory_path.is_file()
            and inventory_path.stat().st_size
            == int(existing.get("output_inventory_bytes", -1))
            and sha256_file(inventory_path)
            == existing.get("output_inventory_sha256")
        ):
            return shard_receipt_path.relative_to(primary_root).as_posix(), existing
        raise RuntimeError(f"unverified shard control exists: {control_root}")
    if inventory_path.exists():
        archive = inventory_path.with_name(
            f"OUTPUT_INVENTORY.orphan.{int(time.time())}.tsv.gz"
        )
        if archive.exists():
            raise FileExistsError(archive)
        os.replace(inventory_path, archive)
    rows = output_rows_for_shard(connection, source_file)
    atomic_gzip_csv(inventory_path, rows)
    counts: dict[str, int] = {
        "utterances": len(rows),
        "derived": sum(row["status"] == "derived" for row in rows),
        "no_mfa_alignment": sum(
            row["status"] == "no_mfa_alignment" for row in rows
        ),
        "alignment_conflicts": sum(
            row["alignment_conflict"] == "true" for row in rows
        ),
        "label_changed": sum(row["label_changed"] == "true" for row in rows),
        "output_bytes": sum(int(row["bytes"] or 0) for row in rows),
    }
    payload = {
        "schema": "bareun_morph_textgrid_shard_receipt.v1",
        "status": "completed",
        "completed_at": now_iso(),
        "source_file": source_file,
        "bareun_receipt_relative": receipt_relative,
        "bareun_receipt_sha256": receipt_sha,
        "storage_id": storage_id,
        "output_inventory_relative": inventory_path.relative_to(primary_root).as_posix(),
        "output_inventory_bytes": inventory_path.stat().st_size,
        "output_inventory_sha256": sha256_file(inventory_path),
        "counts": counts,
    }
    atomic_write_json(shard_receipt_path, payload)
    return shard_receipt_path.relative_to(primary_root).as_posix(), payload


def verify_completed_shard(
    primary_root: Path,
    receipt_relative: str,
    receipt_sha: str,
    shard_receipt_relative: str,
) -> None:
    receipt_path = primary_root / shard_receipt_relative
    if not receipt_path.is_file():
        raise RuntimeError(f"completed shard receipt missing: {receipt_path}")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if payload.get("status") != "completed":
        raise RuntimeError(f"completed shard status mismatch: {receipt_path}")
    if payload.get("bareun_receipt_relative") != receipt_relative:
        raise RuntimeError(f"Bareun receipt relative mismatch: {receipt_path}")
    if payload.get("bareun_receipt_sha256") != receipt_sha:
        raise RuntimeError(f"Bareun receipt SHA contract mismatch: {receipt_path}")
    inventory_path = primary_root / payload["output_inventory_relative"]
    if inventory_path.stat().st_size != int(payload["output_inventory_bytes"]):
        raise RuntimeError(f"shard inventory size mismatch: {inventory_path}")
    if sha256_file(inventory_path) != payload["output_inventory_sha256"]:
        raise RuntimeError(f"shard inventory SHA mismatch: {inventory_path}")


def write_state(
    primary_root: Path,
    *,
    status: str,
    config: Mapping[str, Any],
    connection: sqlite3.Connection | None,
    started_at: str,
    current_receipt: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    counts = database_counts(connection) if connection is not None else {}
    elapsed = max(time.time() - _parse_started_epoch(started_at), 0.001)
    derived = int(counts.get("derived", 0))
    total = int(config["input"]["expected_aligned_textgrids"])
    rate = derived / elapsed
    eta = (total - derived) / rate if rate > 0 else None
    roots = storage_roots(config)
    payload: dict[str, Any] = {
        "schema": "bareun_morph_textgrid_full_state.v1",
        "status": status,
        "updated_at": now_iso(),
        "started_at": started_at,
        "current_receipt": current_receipt,
        "counts": counts,
        "total_receipts": int(config["input"]["expected_bareun_receipts"]),
        "total_aligned_textgrids": total,
        "session_rate_textgrids_per_second": round(rate, 3),
        "eta_seconds": round(eta) if eta is not None else None,
        "storage": {
            storage_id: {
                "root": str(root),
                "free_gib": round(free_bytes_for(root) / GIB, 3),
            }
            for storage_id, root in roots.items()
        },
        "source_textgrid_modified": False,
        "source_wav_accessed": False,
        "mfa_rerun": False,
    }
    if error:
        payload["error"] = error
    atomic_write_json(primary_root / "STATE.json", payload)
    return payload


def _parse_started_epoch(value: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(value).timestamp()


def review_gate(config: Mapping[str, Any]) -> dict[str, bool]:
    audit_path = resolve_path(config["gates"]["pilot_audit"])
    review_path = resolve_path(config["gates"]["user_review_result"])
    audit_ok = False
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_ok = bool(audit.get("passed")) and not audit.get("errors")
    review_text = review_path.read_text(encoding="utf-8") if review_path.is_file() else ""
    required = int(config["gates"]["required_user_final_ok"])
    review_ok = review_text.count("| OK |") >= required
    return {"pilot_audit_passed": audit_ok, "user_review_passed": review_ok}


def preflight(config_path: Path, config: Mapping[str, Any], *, resume: bool) -> dict[str, Any]:
    final_root = resolve_path(config["input"]["bareun_final_root"])
    source_root = resolve_path(config["input"]["source_textgrid_root"])
    roots = storage_roots(config)
    primary_id = str(config["storage"]["primary_id"])
    spill_id = str(config["storage"]["spill_id"])
    primary_root = roots[primary_id]
    spill_root = roots[spill_id]
    final_output = resolve_path(config["output"]["final_root_after_external_consolidation"])
    inventory_path = final_root / "RECEIPT_INVENTORY.tsv"
    inventory_count = 0
    inventory_valid = False
    if inventory_path.is_file():
        try:
            inventory_count = len(read_inventory(final_root))
            inventory_valid = inventory_count == int(
                config["input"]["expected_bareun_receipts"]
            )
        except (OSError, RuntimeError, UnicodeError):
            inventory_valid = False
    gates = review_gate(config)
    fresh_roots_ok = not primary_root.exists() and not spill_root.exists()
    resume_roots_ok = primary_root.is_dir() and (primary_root / "CHECKPOINT.sqlite").is_file()
    mode_roots_ok = resume_roots_ok if resume else fresh_roots_ok
    storage = config["storage"]
    primary_free = free_bytes_for(primary_root)
    spill_free = free_bytes_for(spill_root)
    primary_floor = round(float(storage["primary_minimum_free_gib"]) * GIB)
    spill_floor = round(float(storage["spill_minimum_free_gib"]) * GIB)
    usable = max(primary_free - primary_floor, 0) + max(spill_free - spill_floor, 0)
    required = int(storage["estimated_full_bytes"]) + round(
        float(storage["preflight_extra_headroom_gib"]) * GIB
    )
    checks = {
        "bareun_final_root": final_root.is_dir(),
        "bareun_final_manifest": (final_root / "FINAL_MANIFEST.json").is_file(),
        "receipt_inventory_exact": inventory_valid,
        "source_textgrid_root": source_root.is_dir(),
        "source_year_roots": all(
            (source_root / year).is_dir()
            for year in config["input"]["expected_years"]
        ),
        "pilot_audit_passed": gates["pilot_audit_passed"],
        "user_review_passed": gates["user_review_passed"],
        "mode_output_roots_ok": mode_roots_ok,
        "future_final_absent": not final_output.exists(),
        "combined_storage_headroom": usable >= required if not resume else True,
        "primary_above_floor": primary_free >= primary_floor,
        "spill_above_floor": spill_free >= spill_floor,
    }
    return {
        "schema": "bareun_morph_textgrid_full_preflight.v1",
        "ready": all(checks.values()),
        "mode": "resume" if resume else "fresh",
        "checks": checks,
        "receipt_inventory_count": inventory_count,
        "expected_receipt_count": int(config["input"]["expected_bareun_receipts"]),
        "storage": {
            primary_id: {
                "free_gib": round(primary_free / GIB, 3),
                "minimum_free_gib": float(storage["primary_minimum_free_gib"]),
            },
            spill_id: {
                "free_gib": round(spill_free / GIB, 3),
                "minimum_free_gib": float(storage["spill_minimum_free_gib"]),
            },
            "usable_combined_gib": round(usable / GIB, 3),
            "estimated_plus_headroom_gib": round(required / GIB, 3),
        },
        "config_sha256": sha256_file(config_path),
        "source_textgrid_modified": False,
        "source_wav_accessed": False,
        "mfa_rerun": False,
    }


def ensure_lock(primary_root: Path, *, resume: bool, approved_by: str) -> Path:
    lock_path = primary_root / "RUN.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        old_pid = int(lock.get("pid", -1))
        if pid_is_alive(old_pid):
            raise RuntimeError(f"active runner already exists: pid={old_pid}")
        if not resume:
            raise RuntimeError("stale lock exists; use --resume after inspection")
        archive = primary_root / f"RUN.lock.stale.{int(time.time())}.json"
        if archive.exists():
            raise FileExistsError(archive)
        os.replace(lock_path, archive)
    atomic_write_json(
        lock_path,
        {
            "schema": "bareun_morph_textgrid_full_lock.v1",
            "pid": os.getpid(),
            "started_at": now_iso(),
            "approved_by": approved_by,
            "resume": resume,
        },
    )
    return lock_path


def contract_payload(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "bareun_morph_textgrid_full_run_contract.v1",
        "created_at": now_iso(),
        "run_id": config["run_id"],
        "config_sha256": sha256_file(config_path),
        "contract": config["contract"],
        "input": config["input"],
        "storage": config["storage"],
        "output": config["output"],
    }


def estimate_receipt(
    *,
    utterances: Sequence[Mapping[str, str]],
    source_file: str,
    source_root: Path,
    multiplier: float,
    fixed_bytes: int,
) -> tuple[int, int]:
    source_bytes = 0
    aligned = 0
    for utterance in utterances:
        _, _, source = source_location(source_root, source_file, utterance["utt_id"])
        if source.is_file():
            aligned += 1
            source_bytes += source.stat().st_size
    estimate = round(source_bytes * multiplier) + aligned * fixed_bytes
    return max(estimate, 1), aligned


def process_receipt(
    *,
    config: Mapping[str, Any],
    primary_root: Path,
    roots: Mapping[str, Path],
    connection: sqlite3.Connection,
    final_root: Path,
    source_root: Path,
    receipt_relative: str,
    receipt_sha: str,
    commit_every: int,
) -> dict[str, Any]:
    existing = connection.execute(
        "SELECT status, shard_receipt_relative FROM shards WHERE receipt_relative=?",
        (receipt_relative,),
    ).fetchone()
    if existing and existing[0] == "completed":
        receipt_path = final_root / receipt_relative
        if sha256_file(receipt_path) != receipt_sha:
            raise RuntimeError(f"Bareun receipt SHA mismatch: {receipt_relative}")
        verify_completed_shard(
            primary_root, receipt_relative, receipt_sha, str(existing[1])
        )
        return {"status": "skipped_verified", "receipt_relative": receipt_relative}

    receipt, utterances, morph_by_utt = load_receipt_rows(
        final_root, receipt_relative, receipt_sha
    )
    source_file = str(receipt["source_file"])
    source_file_row = connection.execute(
        "SELECT receipt_sha256, storage_id, status, estimated_bytes, aligned_expected "
        "FROM shards WHERE source_file=?",
        (source_file,),
    ).fetchone()
    storage = config["storage"]
    estimate, aligned_expected = estimate_receipt(
        utterances=utterances,
        source_file=source_file,
        source_root=source_root,
        multiplier=float(storage["shard_estimate_multiplier"]),
        fixed_bytes=int(storage["shard_estimate_fixed_bytes_per_file"]),
    )
    primary_id = str(storage["primary_id"])
    spill_id = str(storage["spill_id"])
    if source_file_row:
        if source_file_row[0] != receipt_sha:
            raise RuntimeError(f"resume receipt SHA mismatch: {source_file}")
        storage_id = str(source_file_row[1])
        already = connection.execute(
            "SELECT COUNT(*) FROM outputs WHERE source_file=? AND status='derived'",
            (source_file,),
        ).fetchone()[0]
        remaining_fraction = max(aligned_expected - int(already), 0) / max(
            aligned_expected, 1
        )
        remaining_estimate = max(round(estimate * remaining_fraction), 1)
        floor_key = (
            "primary_minimum_free_gib" if storage_id == primary_id else "spill_minimum_free_gib"
        )
        floor = round(float(storage[floor_key]) * GIB)
        if free_bytes_for(roots[storage_id]) - remaining_estimate < floor:
            raise StorageSafetyStop(
                f"resume storage {storage_id} cannot finish receipt above floor"
            )
    else:
        storage_id = choose_storage(
            required_bytes=estimate,
            primary_free_bytes=free_bytes_for(roots[primary_id]),
            primary_floor_bytes=round(
                float(storage["primary_minimum_free_gib"]) * GIB
            ),
            spill_free_bytes=free_bytes_for(roots[spill_id]),
            spill_floor_bytes=round(float(storage["spill_minimum_free_gib"]) * GIB),
            primary_id=primary_id,
            spill_id=spill_id,
        )
        connection.execute(
            """INSERT INTO shards
            (source_file, receipt_relative, receipt_sha256, storage_id, status,
             estimated_bytes, aligned_expected)
            VALUES (?, ?, ?, ?, 'processing', ?, ?)""",
            (
                source_file,
                receipt_relative,
                receipt_sha,
                storage_id,
                estimate,
                aligned_expected,
            ),
        )
        connection.commit()

    output_root = roots[storage_id]
    processed_since_commit = 0
    for utterance in utterances:
        utt_id = str(utterance["utt_id"])
        if connection.execute(
            "SELECT 1 FROM outputs WHERE source_file=? AND utt_id=?",
            (source_file, utt_id),
        ).fetchone():
            continue
        expected_tokens = int(utterance["response_token_count"])
        new_label, morph_count = build_new_morph_label(
            morph_by_utt.get(utt_id, []), expected_tokens
        )
        year, session, source = source_location(source_root, source_file, utt_id)
        relative = output_relative(year, session, utt_id)
        destination = output_root / relative
        source_row_index = str(utterance["source_row_index"])
        if not source.is_file():
            values = (
                source_file,
                utt_id,
                source_row_index,
                "no_mfa_alignment",
                None,
                None,
                None,
                None,
                None,
                None,
                expected_tokens,
                None,
                morph_count,
                0,
                0,
                None,
                hash_text(new_label),
            )
        else:
            source_stat = source.stat()
            source_bytes = source_stat.st_size
            source_sha = sha256_file(source)
            if destination.exists():
                verified = verify_derived(source, destination, new_label)
                old_label = str(verified["old_label"])
            else:
                made = derive_atomic(source, destination, new_label)
                old_label = str(made["old_label"])
                verified = made
            source_after = source.stat()
            if (
                source_after.st_size != source_stat.st_size
                or source_after.st_mtime_ns != source_stat.st_mtime_ns
            ):
                raise RuntimeError(f"source TextGrid changed during read: {source}")
            labeled_words = int(verified["labeled_word_count"])
            conflict = int(labeled_words != expected_tokens)
            destination_bytes = destination.stat().st_size
            destination_sha = sha256_file(destination)
            values = (
                source_file,
                utt_id,
                source_row_index,
                "derived",
                storage_id,
                relative.as_posix(),
                destination_bytes,
                destination_sha,
                source_bytes,
                source_sha,
                expected_tokens,
                labeled_words,
                morph_count,
                conflict,
                int(old_label != new_label),
                hash_text(old_label),
                hash_text(new_label),
            )
        connection.execute(
            """INSERT INTO outputs
            (source_file, utt_id, source_row_index, status, storage_id,
             derived_relative, bytes, sha256, source_bytes, source_sha256,
             response_token_count, labeled_word_count, morph_count,
             alignment_conflict, label_changed, old_label_sha256,
             new_label_sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
        processed_since_commit += 1
        if processed_since_commit >= commit_every:
            connection.commit()
            processed_since_commit = 0
    connection.commit()
    receipt_path, shard = write_shard_receipt(
        primary_root=primary_root,
        receipt_relative=receipt_relative,
        receipt_sha=receipt_sha,
        source_file=source_file,
        storage_id=storage_id,
        connection=connection,
    )
    counts = shard["counts"]
    connection.execute(
        """UPDATE shards SET status='completed', output_count=?, no_mfa_count=?,
        conflict_count=?, changed_count=?, unchanged_count=?, output_bytes=?,
        shard_receipt_relative=?, completed_at=? WHERE source_file=?""",
        (
            counts["derived"],
            counts["no_mfa_alignment"],
            counts["alignment_conflicts"],
            counts["label_changed"],
            counts["derived"] - counts["label_changed"],
            counts["output_bytes"],
            receipt_path,
            now_iso(),
            source_file,
        ),
    )
    connection.commit()
    return {
        "status": "completed",
        "receipt_relative": receipt_relative,
        "storage_id": storage_id,
        "counts": counts,
    }


def append_progress(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(dict(payload), ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_build_manifest(
    *,
    config_path: Path,
    config: Mapping[str, Any],
    primary_root: Path,
    roots: Mapping[str, Path],
    connection: sqlite3.Connection,
) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT receipt_relative, receipt_sha256, storage_id, shard_receipt_relative "
        "FROM shards WHERE status='completed' ORDER BY receipt_relative"
    ).fetchall()
    inventory_path = primary_root / "SHARD_RECEIPT_INVENTORY.tsv"
    temporary = inventory_path.with_name(
        f".{inventory_path.name}.{uuid.uuid4().hex}.partial"
    )
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            shard_receipt = primary_root / str(row[3])
            stream.write(
                "\t".join(
                    [str(row[0]), str(row[1]), str(row[2]), str(row[3]), sha256_file(shard_receipt)]
                )
                + "\n"
            )
    if inventory_path.exists():
        if sha256_file(inventory_path) == sha256_file(temporary):
            temporary.unlink()
        else:
            archive = inventory_path.with_name(
                f"SHARD_RECEIPT_INVENTORY.orphan.{int(time.time())}.tsv"
            )
            if archive.exists():
                raise FileExistsError(archive)
            os.replace(inventory_path, archive)
            os.replace(temporary, inventory_path)
    else:
        os.replace(temporary, inventory_path)
    counts = database_counts(connection)
    storage_counts = {
        row[0]: {"files": int(row[1]), "bytes": int(row[2] or 0)}
        for row in connection.execute(
            "SELECT storage_id, COUNT(*), SUM(bytes) FROM outputs "
            "WHERE status='derived' GROUP BY storage_id"
        )
    }
    payload = {
        "schema": "bareun_morph_textgrid_full_build_manifest.v1",
        "status": config["output"]["completion_state"],
        "completed_at": now_iso(),
        "run_id": config["run_id"],
        "counts": counts,
        "storage_counts": storage_counts,
        "storage_roots": {key: str(value) for key, value in roots.items()},
        "shard_receipt_inventory": inventory_path.name,
        "shard_receipt_inventory_bytes": inventory_path.stat().st_size,
        "shard_receipt_inventory_sha256": sha256_file(inventory_path),
        "config_sha256": sha256_file(config_path),
        "runner_sha256": sha256_file(Path(__file__)),
        "source_textgrid_modified": False,
        "source_wav_accessed": False,
        "mfa_rerun": False,
        "final_promotion_performed": False,
        "external_consolidation_required": True,
    }
    atomic_write_json(primary_root / "BUILD_MANIFEST.json", payload)
    return payload


def validate_final_counts(config: Mapping[str, Any], counts: Mapping[str, int]) -> None:
    expected = config["input"]
    checks = {
        "receipts": (
            counts["completed_receipts"], int(expected["expected_bareun_receipts"])
        ),
        "utterances": (counts["utterances"], int(expected["expected_utterances"])),
        "derived": (counts["derived"], int(expected["expected_aligned_textgrids"])),
        "no_mfa_alignment": (
            counts["no_mfa_alignment"], int(expected["expected_no_mfa_alignment"])
        ),
    }
    failures = {name: pair for name, pair in checks.items() if pair[0] != pair[1]}
    if failures:
        raise RuntimeError(f"final count mismatch: {failures}")


def execute(
    config_path: Path,
    config: Mapping[str, Any],
    *,
    resume: bool,
    approved_by: str,
) -> dict[str, Any]:
    check = preflight(config_path, config, resume=resume)
    if not check["ready"]:
        raise RuntimeError(f"preflight failed: {check}")
    final_root = resolve_path(config["input"]["bareun_final_root"])
    source_root = resolve_path(config["input"]["source_textgrid_root"])
    roots = storage_roots(config)
    primary_root = roots[str(config["storage"]["primary_id"])]
    started_at = now_iso()
    if not resume:
        primary_root.parent.mkdir(parents=True, exist_ok=True)
        primary_root.mkdir()
        roots[str(config["storage"]["spill_id"])].parent.mkdir(
            parents=True, exist_ok=True
        )
        roots[str(config["storage"]["spill_id"])].mkdir()
        atomic_write_json(primary_root / "RUN_CONTRACT.json", contract_payload(config_path, config))
        atomic_write_json(
            roots[str(config["storage"]["spill_id"])] / "SPILL_CONTRACT.json",
            {
                "schema": "bareun_morph_textgrid_spill_contract.v1",
                "created_at": now_iso(),
                "run_id": config["run_id"],
                "primary_control_root": str(primary_root),
                "config_sha256": sha256_file(config_path),
            },
        )
    else:
        contract = json.loads((primary_root / "RUN_CONTRACT.json").read_text(encoding="utf-8"))
        if contract.get("config_sha256") != sha256_file(config_path):
            raise RuntimeError("resume config SHA mismatch")
        old_state_path = primary_root / "STATE.json"
        if old_state_path.is_file():
            started_at = str(
                json.loads(old_state_path.read_text(encoding="utf-8")).get(
                    "started_at", started_at
                )
            )
        completed_manifest = primary_root / "BUILD_MANIFEST.json"
        if completed_manifest.is_file():
            payload = json.loads(completed_manifest.read_text(encoding="utf-8"))
            if payload.get("config_sha256") != sha256_file(config_path):
                raise RuntimeError("completed build manifest config SHA mismatch")
            if payload.get("status") != config["output"]["completion_state"]:
                raise RuntimeError("completed build manifest status mismatch")
            return payload
    lock_path = ensure_lock(primary_root, resume=resume, approved_by=approved_by)
    connection: sqlite3.Connection | None = None
    current_receipt: str | None = None
    try:
        connection = init_database(primary_root / "CHECKPOINT.sqlite")
        inventory = read_inventory(final_root)
        write_state(
            primary_root,
            status="running",
            config=config,
            connection=connection,
            started_at=started_at,
        )
        for index, (receipt_relative, receipt_sha) in enumerate(inventory, 1):
            current_receipt = receipt_relative
            result = process_receipt(
                config=config,
                primary_root=primary_root,
                roots=roots,
                connection=connection,
                final_root=final_root,
                source_root=source_root,
                receipt_relative=receipt_relative,
                receipt_sha=receipt_sha,
                commit_every=int(config["storage"]["checkpoint_commit_every_files"]),
            )
            state = write_state(
                primary_root,
                status="running",
                config=config,
                connection=connection,
                started_at=started_at,
                current_receipt=receipt_relative,
            )
            append_progress(
                primary_root / "PROGRESS.jsonl",
                {
                    "schema": "bareun_morph_textgrid_full_progress.v1",
                    "at": now_iso(),
                    "receipt_index": index,
                    "receipt_total": len(inventory),
                    **result,
                    "global_counts": state["counts"],
                },
            )
        counts = database_counts(connection)
        validate_final_counts(config, counts)
        manifest = write_build_manifest(
            config_path=config_path,
            config=config,
            primary_root=primary_root,
            roots=roots,
            connection=connection,
        )
        write_state(
            primary_root,
            status=str(config["output"]["completion_state"]),
            config=config,
            connection=connection,
            started_at=started_at,
        )
        return manifest
    except StorageSafetyStop as exc:
        if connection is not None:
            write_state(
                primary_root,
                status="paused_storage_safety",
                config=config,
                connection=connection,
                started_at=started_at,
                current_receipt=current_receipt,
                error=str(exc),
            )
        raise
    except BaseException as exc:
        if connection is not None:
            write_state(
                primary_root,
                status="failed_safe_to_resume",
                config=config,
                connection=connection,
                started_at=started_at,
                current_receipt=current_receipt,
                error=f"{type(exc).__name__}: {exc}",
            )
        raise
    finally:
        if connection is not None:
            connection.close()
        if lock_path.exists():
            lock_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--approved-by", default="")
    parser.add_argument("--approval-token", default="")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    if args.preflight_only:
        result = preflight(config_path, config, resume=args.resume)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["ready"] else 1
    expected_token = str(config["approval"]["execution_token"])
    if not args.approved_by.strip() or args.approval_token != expected_token:
        raise RuntimeError("exact approval identity and token are required")
    result = execute(
        config_path,
        config,
        resume=args.resume,
        approved_by=args.approved_by.strip(),
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
