"""Create only missing TextGrids blocked by source line separators.

The failed full-pass report is the exact candidate inventory.  This repair is
allowed only when every failure is a TextGrid control-character rejection,
the destination did not previously exist, and the corresponding frozen search
row contains line/paragraph separators in a display-tier field.  Source CSV,
MFA DB, WAV, LAB, and every previously generated TextGrid remain read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping

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
from research_textgrid_v2 import (
    TEXTGRID_LABEL_LINE_SEPARATORS,
    normalize_search_label_for_textgrid,
    validate_base_textgrid_from_intervals,
    write_base_textgrid_from_intervals,
)


SCHEMA_VERSION = "mfa_textgrid_search_label_control_repair.v1"
REPAIR_MODE = "create_missing_textgrid_after_label_normalization"
DISPLAY_SOURCE_FIELDS = ("form", "tagged")


def _fingerprint_matches(path: Path, expected: Mapping[str, object]) -> bool:
    if not path.is_file():
        return False
    observed = file_fingerprint(path, with_sha256=True)
    return (
        int(observed["bytes"]) == int(expected.get("bytes", -1))
        and str(observed["sha256"]) == str(expected.get("sha256", ""))
    )


def _label_control_evidence(row: Mapping[str, object]) -> dict[str, object]:
    fields: dict[str, object] = {}
    for field in DISPLAY_SOURCE_FIELDS:
        raw = str(row.get(field, ""))
        counts = Counter(
            f"U+{ord(char):04X}"
            for char in raw
            if char in TEXTGRID_LABEL_LINE_SEPARATORS
        )
        if not counts:
            continue
        normalized = normalize_search_label_for_textgrid(raw)
        fields[field] = {
            "control_counts": dict(sorted(counts.items())),
            "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "normalized_sha256": hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest(),
            "changed": raw != normalized,
        }
    if not fields or not all(bool(item["changed"]) for item in fields.values()):
        raise RuntimeError("no proven search-label line separator to normalize")
    return fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    failed_report_path = args.failed_report.resolve()
    manifest_path = args.manifest.resolve()
    report = json.loads(failed_report_path.read_text(encoding="utf-8-sig"))
    failures = list(report.get("failed_examples") or [])
    failed_count = int((report.get("counts") or {}).get("failed", 0))
    failed_ids = [str(row.get("utt_id", "")).strip() for row in failures]
    if (
        report.get("status") != "failed"
        or report.get("analysis_ready_status") != "blocked"
        or failed_count <= 0
        or failed_count != len(failures)
        or any(not value for value in failed_ids)
        or len(set(failed_ids)) != failed_count
        or any(
            "TextGrid" not in str(row.get("error", ""))
            or "U+" not in str(row.get("error", ""))
            for row in failures
        )
    ):
        raise RuntimeError("failed report is not an exact label-control checkpoint")

    year = str(report["year"])
    db_path = Path(str(report["db_path"])).resolve()
    search_root = Path(str(report["search_master_root"])).resolve()
    output_root = Path(str(report["output_root"])).resolve()
    acoustic_model = Path(
        str((report.get("acoustic_model") or {}).get("path", ""))
    ).resolve()
    groups = model_group_lookup(load_acoustic_meta(acoustic_model))

    def phone_mapper(phone: str) -> str:
        return classify_phone(phone, groups).phone_class_r_auto

    connection = open_readonly(db_path)
    try:
        word_labels, phone_labels = _db_inventory(connection)
        marks = placeholders(len(failed_ids))
        db_rows = list(
            connection.execute(
                """
                SELECT u.id, f.name, f.relative_path, sf.duration
                FROM utterance u
                JOIN file f ON f.id=u.file_id
                JOIN sound_file sf ON sf.file_id=f.id
                WHERE u.ignored=0 AND f.name IN ("""
                + marks
                + ") ORDER BY f.name",
                failed_ids,
            )
        )
        by_name = {str(row[1]): row for row in db_rows}
        words_by_utt, phones_by_utt = _session_intervals(
            connection,
            [int(row[0]) for row in db_rows],
            word_labels,
            phone_labels,
        )
    finally:
        connection.close()
    if set(by_name) != set(failed_ids):
        raise RuntimeError("failed IDs and retained database IDs differ")

    completed: dict[str, dict[str, object]] = {}
    prior_status = ""
    if manifest_path.is_file():
        prior = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        prior_status = str(prior.get("status", ""))
        if prior_status in {"ready", "running", "failed", "success"}:
            if not _fingerprint_matches(
                failed_report_path, prior.get("source_failed_report") or {}
            ):
                raise RuntimeError("existing repair progress belongs to another report")
            completed = {
                str(record["utt_id"]): record
                for record in prior.get("records") or []
            }
            for utt_id, record in completed.items():
                if not _fingerprint_matches(
                    Path(str(record["destination"])),
                    record.get("destination_after") or {},
                ):
                    raise RuntimeError(
                        f"completed repair fingerprint mismatch: {utt_id}"
                    )
    if (
        not args.apply
        and prior_status == "success"
        and set(completed) == set(failed_ids)
    ):
        print(manifest_path)
        print(f"READY existing_success={len(completed)}")
        return 0

    prepared: dict[str, dict[str, object]] = {}
    candidates: list[dict[str, object]] = []
    all_field_evidence: dict[str, object] = {}
    for utt_id in failed_ids:
        db_row = by_name[utt_id]
        uid = int(db_row[0])
        session = str(db_row[2] or utt_id.split(".", 1)[0])
        duration = float(db_row[3])
        search = load_session_rows(search_root, year, session)[utt_id]
        evidence = _label_control_evidence(search)
        all_field_evidence[utt_id] = evidence
        destination = output_root / year / session / f"{utt_id}.TextGrid"
        if utt_id in completed:
            continue
        if destination.exists():
            raise RuntimeError(
                f"unrecorded destination already exists; refusing overwrite: {destination}"
            )
        word_rows, _word_count, _word_max = _normalize_db_interval_rows(
            words_by_utt[uid], duration
        )
        phone_rows, _phone_count, _phone_max = _normalize_db_interval_rows(
            phones_by_utt[uid], duration
        )
        words = [(row[1], row[2], row[3]) for row in word_rows]
        phones = [(row[1], row[2], row[3]) for row in phone_rows]
        candidate = {
            "utt_id": utt_id,
            "session": session,
            "destination": str(destination),
            "destination_previously_absent": True,
            "source_control_validation_passed": True,
            "source_label_controls": evidence,
            "archive_path": "",
            "archive_fingerprint": {},
        }
        candidates.append(candidate)
        prepared[utt_id] = {
            "candidate": candidate,
            "duration": duration,
            "search": search,
            "words": words,
            "phones": phones,
        }

    base: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if not args.apply else "running",
        "repair_mode": REPAIR_MODE,
        "year": year,
        "db_path": str(db_path),
        "search_master_root": str(search_root),
        "output_root": str(output_root),
        "alignment_contract_id": str(report["alignment_contract_id"]),
        "input_contract_id": str(report["input_contract_id"]),
        "source_failed_report": file_fingerprint(
            failed_report_path, with_sha256=True
        ),
        "failed_count": failed_count,
        "candidate_count": len(candidates) + len(completed),
        "candidates": candidates,
        "records": [
            completed[utt_id] for utt_id in failed_ids if utt_id in completed
        ],
        "textgrid_label_normalization": {
            "policy": (
                "search-derived TextGrid display tiers only: Unicode line "
                "and paragraph separators become one ASCII space; frozen "
                "source CSV and companion-table source fields remain unchanged"
            ),
            "utterances_adjusted": failed_count,
            "fields_by_utterance": all_field_evidence,
        },
        "mutation_scope": (
            "create exact missing derived TextGrids only; existing TextGrids, "
            "DB, WAV, LAB, and source CSV unchanged"
        ),
    }
    atomic_write_json(manifest_path, base)
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
            destination = Path(str(candidate["destination"]))
            result = write_base_textgrid_from_intervals(
                destination,
                duration=float(item["duration"]),
                words=item["words"],
                phones=item["phones"],
                row=item["search"],
                phone_mapper=phone_mapper,
            )
            validation = validate_base_textgrid_from_intervals(
                destination,
                duration=float(item["duration"]),
                words=item["words"],
                phones=item["phones"],
                row=item["search"],
                phone_mapper=phone_mapper,
            )
            if not result.get("valid") or not validation.get("valid"):
                raise RuntimeError(f"replacement validation failed: {utt_id}")
            candidate["destination_after"] = file_fingerprint(
                destination, with_sha256=True
            )
            candidate["replacement_validation_passed"] = True
            completed[utt_id] = candidate
            base["records"] = [
                completed[value] for value in failed_ids if value in completed
            ]
            atomic_write_json(manifest_path, base)
            print(f"created {len(completed)}/{failed_count}: {utt_id}", flush=True)
    except Exception as exc:
        base["status"] = "failed"
        base["error"] = f"{type(exc).__name__}: {exc}"
        atomic_write_json(manifest_path, base)
        raise

    if set(completed) != set(failed_ids):
        raise RuntimeError("repair did not cover the exact failed inventory")
    base["status"] = "success"
    base["repaired_count"] = len(completed)
    base["repaired_ids"] = sorted(completed)
    base["records"] = [completed[value] for value in failed_ids]
    base.pop("error", None)
    atomic_write_json(manifest_path, base)
    print(manifest_path)
    print(f"SUCCESS created={len(completed)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
