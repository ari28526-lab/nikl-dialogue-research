"""Archive and repair only proven pre-normalization terminal TextGrids.

The source MFA database, WAV files, CSV/search-master rows, and alignment
interval labels are read-only.  A candidate is repairable only when its six
tiers exactly match the historical pre-normalization writer and fail the
current writer solely because the terminal float32 endpoint was materialized
as a short trailing interval.  Every replaced derived TextGrid is archived and
fingerprinted first.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping, Sequence

from export_mfa_db_research_6tier import (
    _db_inventory,
    _normalize_db_interval_rows,
    _session_intervals,
    load_session_rows,
    open_readonly,
    placeholders,
)
from phoneme_roman import classify_phone, load_acoustic_meta, model_group_lookup
from pipeline_common import atomic_write_json, file_fingerprint
import research_textgrid_v2 as textgrid_v2
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


SCHEMA_VERSION = "mfa_textgrid_terminal_roundoff_repair.v1"


def legacy_materialize_intervals(
    intervals: Sequence[tuple], duration: float
) -> list[tuple[float, float, str]]:
    """Reproduce the writer immediately before commit f205d32."""

    fixed: list[tuple[float, float, str]] = []
    cursor = 0.0
    for begin, end, label in sorted(
        intervals, key=lambda item: (float(item[0]), float(item[1]))
    ):
        begin = float(begin)
        end = float(end)
        if begin < -1e-6 or end > float(duration) + 1e-6:
            raise ValueError("legacy interval outside 0-xmax")
        if begin < 0:
            begin = 0.0
        if end > float(duration):
            end = float(duration)
        if end - begin <= 1e-9:
            continue
        if begin < cursor - 1e-6:
            raise ValueError("legacy interval overlap")
        if begin - cursor > 1e-6:
            fixed.append((cursor, begin, ""))
        fixed.append((begin, end, str(label)))
        cursor = end
    if not fixed:
        return [(0.0, float(duration), "")]
    if float(duration) - cursor > 1e-6:
        fixed.append((cursor, float(duration), ""))
    return fixed


def _fingerprint_matches(path: Path, expected: Mapping[str, object]) -> bool:
    if not path.is_file():
        return False
    observed = file_fingerprint(path, with_sha256=True)
    return (
        int(observed["bytes"]) == int(expected.get("bytes", -1))
        and str(observed["sha256"]) == str(expected.get("sha256", ""))
    )


def _build_exact_tiers(
    *,
    duration: float,
    words: Sequence[tuple],
    phones: Sequence[tuple],
    search: Mapping[str, object],
    phone_mapper,
) -> tuple[list[tuple[str, list[tuple]]], int, float]:
    normalized_words, word_count, word_max = _normalize_db_interval_rows(
        words, duration
    )
    normalized_phones, phone_count, phone_max = _normalize_db_interval_rows(
        phones, duration
    )
    word_intervals = [
        (row[1], row[2], row[3]) for row in normalized_words
    ]
    phone_intervals = [
        (row[1], row[2], row[3]) for row in normalized_phones
    ]
    tiers, fallback = textgrid_v2.build_base_tier_data_from_intervals(
        duration=duration,
        words=word_intervals,
        phones=phone_intervals,
        row=search,
        phone_mapper=phone_mapper,
    )
    if fallback:
        raise RuntimeError("word span fallback is not repairable")
    return tiers, word_count + phone_count, max(word_max, phone_max)


def _build_legacy_tiers(
    *,
    duration: float,
    words: Sequence[tuple],
    phones: Sequence[tuple],
    search: Mapping[str, object],
    phone_mapper,
) -> list[tuple[str, list[tuple]]]:
    word_intervals = [
        (float(row[1]), float(row[2]), str(row[3])) for row in words
    ]
    phone_intervals = [
        (float(row[1]), float(row[2]), str(row[3])) for row in phones
    ]
    current = textgrid_v2._materialize_intervals
    try:
        textgrid_v2._materialize_intervals = legacy_materialize_intervals
        tiers, fallback = textgrid_v2.build_base_tier_data_from_intervals(
            duration=duration,
            words=word_intervals,
            phones=phone_intervals,
            row=search,
            phone_mapper=phone_mapper,
        )
    finally:
        textgrid_v2._materialize_intervals = current
    if fallback:
        raise RuntimeError("legacy word span fallback is not repairable")
    return tiers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-report", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    failed_report_path = args.failed_report.resolve()
    report = json.loads(failed_report_path.read_text(encoding="utf-8-sig"))
    if report.get("status") != "failed":
        raise RuntimeError("source report must be failed")
    failed_count = int((report.get("counts") or {}).get("failed", 0))
    examples = list(report.get("failed_examples") or [])
    failed_ids = [str(row.get("utt_id", "")).strip() for row in examples]
    if (
        failed_count <= 0
        or failed_count != len(failed_ids)
        or any(not value for value in failed_ids)
        or len(set(failed_ids)) != failed_count
    ):
        raise RuntimeError("failed inventory is incomplete or truncated")

    year = str(report["year"])
    db_path = Path(report["db_path"]).resolve()
    search_root = Path(report["search_master_root"]).resolve()
    output_root = Path(report["output_root"]).resolve()
    acoustic_model = Path(report["acoustic_model"]["path"]).resolve()
    archive_root = args.archive_root.resolve()
    manifest_path = args.manifest.resolve()
    groups = model_group_lookup(load_acoustic_meta(acoustic_model))

    def phone_mapper(phone: str) -> str:
        return classify_phone(phone, groups).phone_class_r_auto

    connection = open_readonly(db_path)
    try:
        word_labels, phone_labels = _db_inventory(connection)
        marks = placeholders(len(failed_ids))
        records = list(
            connection.execute(
                """
                SELECT u.id, f.name, f.relative_path, sf.duration
                FROM utterance u
                JOIN file f ON f.id = u.file_id
                JOIN sound_file sf ON sf.file_id = f.id
                WHERE f.name IN ("""
                + marks
                + ") ORDER BY f.name",
                failed_ids,
            )
        )
        by_name = {str(row[1]): row for row in records}
        words_by_utt, phones_by_utt = _session_intervals(
            connection,
            [int(row[0]) for row in records],
            word_labels,
            phone_labels,
        )
    finally:
        connection.close()
    if set(by_name) != set(failed_ids):
        raise RuntimeError("failed IDs and database IDs differ")

    prior_progress: dict[str, object] | None = None
    completed: dict[str, dict] = {}
    if args.apply and manifest_path.is_file():
        prior_progress = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if prior_progress.get("status") in {"running", "failed"}:
            source = prior_progress.get("source_failed_report") or {}
            if not _fingerprint_matches(failed_report_path, source):
                raise RuntimeError("existing repair progress belongs to another report")
            completed = {
                str(row["utt_id"]): row
                for row in prior_progress.get("records") or []
            }

    candidates: list[dict[str, object]] = []
    prepared: dict[str, dict[str, object]] = {}
    for utt_id in failed_ids:
        if utt_id in completed:
            record = completed[utt_id]
            if not _fingerprint_matches(
                Path(record["destination"]), record["destination_after"]
            ) or not _fingerprint_matches(
                Path(record["archive_path"]), record["archive_fingerprint"]
            ):
                raise RuntimeError(f"completed repair fingerprint mismatch: {utt_id}")
            continue
        db_row = by_name[utt_id]
        uid = int(db_row[0])
        session = str(db_row[2] or utt_id.split(".", 1)[0])
        duration = float(db_row[3])
        search = load_session_rows(search_root, year, session)[utt_id]
        destination = output_root / year / session / f"{utt_id}.TextGrid"
        if not destination.is_file():
            raise FileNotFoundError(destination)
        exact_tiers, adjustment_count, max_adjustment = _build_exact_tiers(
            duration=duration,
            words=words_by_utt[uid],
            phones=phones_by_utt[uid],
            search=search,
            phone_mapper=phone_mapper,
        )
        legacy_tiers = _build_legacy_tiers(
            duration=duration,
            words=words_by_utt[uid],
            phones=phones_by_utt[uid],
            search=search,
            phone_mapper=phone_mapper,
        )
        current_validation = textgrid_v2._validate_against_tier_data(
            destination,
            expected_duration=duration,
            expected_data=exact_tiers,
        )
        legacy_validation = textgrid_v2._validate_against_tier_data(
            destination,
            expected_duration=duration,
            expected_data=legacy_tiers,
        )
        if current_validation["valid"] or not legacy_validation["valid"]:
            raise RuntimeError(
                f"not an exact pre-normalization terminal mismatch: {utt_id}"
            )
        if adjustment_count <= 0 or max_adjustment > textgrid_v2.boundary_roundoff_tolerance(duration):
            raise RuntimeError(f"roundoff evidence outside policy: {utt_id}")
        relative = destination.relative_to(output_root)
        archive_path = archive_root / relative
        candidate = {
            "utt_id": utt_id,
            "session": session,
            "destination": str(destination),
            "archive_path": str(archive_path),
            "destination_before": file_fingerprint(
                destination, with_sha256=True
            ),
            "matches_pre_normalization_policy": True,
            "current_validation_reasons": current_validation["reasons"],
            "boundary_adjustment_count": adjustment_count,
            "max_boundary_adjustment_seconds": max_adjustment,
        }
        candidates.append(candidate)
        prepared[utt_id] = {
            "candidate": candidate,
            "duration": duration,
            "search": search,
            "words": words_by_utt[uid],
            "phones": phones_by_utt[uid],
        }

    base_manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if not args.apply else "running",
        "year": year,
        "db_path": str(db_path),
        "search_master_root": str(search_root),
        "output_root": str(output_root),
        "archive_root": str(archive_root),
        "alignment_contract_id": str(report["alignment_contract_id"]),
        "input_contract_id": str(report["input_contract_id"]),
        "source_failed_report": file_fingerprint(
            failed_report_path, with_sha256=True
        ),
        "failed_count": failed_count,
        "candidate_count": len(candidates) + len(completed),
        "candidates": candidates,
        "records": list(completed.values()),
        "mutation_scope": "derived partial TextGrid only; DB/WAV/CSV unchanged",
    }
    atomic_write_json(manifest_path, base_manifest)
    if not args.apply:
        print(manifest_path)
        print(f"READY candidates={len(candidates)}")
        return 0

    try:
        for utt_id in failed_ids:
            if utt_id in completed:
                continue
            item = prepared[utt_id]
            candidate = dict(item["candidate"])
            destination = Path(candidate["destination"])
            archive_path = Path(candidate["archive_path"])
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            if archive_path.exists():
                if not _fingerprint_matches(
                    archive_path, candidate["destination_before"]
                ):
                    raise RuntimeError(f"conflicting archive file: {archive_path}")
            else:
                partial_archive = archive_path.with_name(
                    archive_path.name + f".{os.getpid()}.partial"
                )
                shutil.copy2(destination, partial_archive)
                if not _fingerprint_matches(
                    partial_archive, candidate["destination_before"]
                ):
                    raise RuntimeError(f"archive copy verification failed: {utt_id}")
                os.replace(partial_archive, archive_path)

            temporary = destination.with_name(
                destination.name + f".{os.getpid()}.repair.partial"
            )
            temporary.unlink(missing_ok=True)
            normalized_words, _wc, _wm = _normalize_db_interval_rows(
                item["words"], float(item["duration"])
            )
            normalized_phones, _pc, _pm = _normalize_db_interval_rows(
                item["phones"], float(item["duration"])
            )
            textgrid_v2.write_base_textgrid_from_intervals(
                temporary,
                duration=float(item["duration"]),
                words=[(row[1], row[2], row[3]) for row in normalized_words],
                phones=[(row[1], row[2], row[3]) for row in normalized_phones],
                row=item["search"],
                phone_mapper=phone_mapper,
            )
            replacement_fingerprint = file_fingerprint(
                temporary, with_sha256=True
            )
            os.replace(temporary, destination)
            if not _fingerprint_matches(destination, replacement_fingerprint):
                raise RuntimeError(f"replacement verification failed: {utt_id}")
            exact_tiers, _count, _maximum = _build_exact_tiers(
                duration=float(item["duration"]),
                words=item["words"],
                phones=item["phones"],
                search=item["search"],
                phone_mapper=phone_mapper,
            )
            validation = textgrid_v2._validate_against_tier_data(
                destination,
                expected_duration=float(item["duration"]),
                expected_data=exact_tiers,
            )
            if not validation["valid"]:
                raise RuntimeError(f"replacement validation failed: {utt_id}")
            candidate["archive_fingerprint"] = file_fingerprint(
                archive_path, with_sha256=True
            )
            candidate["destination_after"] = file_fingerprint(
                destination, with_sha256=True
            )
            candidate["replacement_validation_passed"] = True
            completed[utt_id] = candidate
            base_manifest["records"] = [
                completed[value]
                for value in failed_ids
                if value in completed
            ]
            atomic_write_json(manifest_path, base_manifest)
            print(f"repaired {len(completed)}/{failed_count}: {utt_id}", flush=True)
    except Exception as exc:
        base_manifest["status"] = "failed"
        base_manifest["error"] = f"{type(exc).__name__}: {exc}"
        atomic_write_json(manifest_path, base_manifest)
        raise

    if set(completed) != set(failed_ids):
        raise RuntimeError("repair did not cover the exact failed inventory")
    base_manifest["status"] = "success"
    base_manifest["repaired_count"] = len(completed)
    base_manifest["repaired_ids"] = sorted(completed)
    base_manifest["records"] = [completed[value] for value in failed_ids]
    base_manifest.pop("error", None)
    atomic_write_json(manifest_path, base_manifest)
    print(manifest_path)
    print(f"SUCCESS repaired={len(completed)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
