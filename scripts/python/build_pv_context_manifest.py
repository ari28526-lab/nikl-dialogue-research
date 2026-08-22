"""Build five explicit context slots around each selected PV target.

Context is defined by existing-row rank within the same session and dialogue,
not by arithmetic ``utt_seq ± n``.  Speaker runs are exploratory display aids,
not gold conversational-turn annotations.  Missing slots are retained with a
status so every input target has exactly five output rows.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from pipeline_common import sha256_file
from pv_preview_common import (
    DEFAULT_ACTIVE_VIEW_ROOT,
    DEFAULT_CONFIG,
    DEFAULT_MORPH_ROOT,
    DEFAULT_R3_ROOT,
    DEFAULT_RC0_ROOT,
    annual_table_contract,
    atomic_write_csv,
    atomic_write_json,
    base_build_receipt,
    capped_rows_by_id,
    capped_rows_by_id_allow_missing,
    load_json,
    numeric_utt_seq,
    read_active_exceptions,
    PROJECT_ROOT,
    require_under,
    source_receipt,
    validate_config,
    validate_header,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


RELATIONS = ["before_2", "before_1", "target", "after_1", "after_2"]
OFFSETS = {"before_2": -2, "before_1": -1, "target": 0, "after_1": 1, "after_2": 2}
CONTEXT_FIELDS = [
    "pv_id",
    "target_utt_id",
    "relation",
    "rank_offset",
    "slot_status",
    "year",
    "dialogue_id",
    "target_session_id",
    "session_id",
    "utt_id",
    "speaker_id",
    "utt_seq",
    "source_rank_in_dialogue",
    "transcription_unit_interpretation",
    "operational_speaker_run_id",
    "operational_speaker_run_rule",
    "speaker_run_unit_count",
    "target_position_in_speaker_run",
    "distance_to_speaker_run_start",
    "distance_to_speaker_run_end",
    "derived_turn_id",
    "derived_turn_is_exploratory",
    "same_derived_turn_as_target",
    "speaker_change_before",
    "speaker_change_after",
    "utt_seq_gap_before",
    "source_time_gap_before_seconds",
    "source_time_gap_semantics",
    "timestamp_overlap_raw",
    "source_start",
    "source_end",
    "source_dur",
    "source_note",
    "source_note_overlap_flag",
    "source_overlap_flag",
    "same_file_as_target",
    "context_window_status",
    "context_audio_status",
    "context_sufficient_for_preview",
    "wav_path",
    "wav_status",
    "active_textgrid_path",
    "textgrid_status",
    "alignment_family",
    "active_form_source",
    "form",
    "ledger_lookup_status",
    "ledger_primary_status",
]


def read_samples(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = set(reader.fieldnames or ())
    required = {"pv_id", "year", "utt_id", "session_id"}
    if missing := required - fields:
        raise RuntimeError(f"sample fields missing: {sorted(missing)}")
    if not rows:
        raise RuntimeError("sample input is empty")
    if len({row["pv_id"] for row in rows}) != len(rows):
        raise RuntimeError("duplicate pv_id in sample input")
    return rows


def scan_dialogues(
    *,
    samples: list[dict[str, str]],
    morph_root: Path,
    row_cap: int,
) -> tuple[dict[tuple[int, str, str], list[dict[str, str]]], list[dict[str, Any]]]:
    targets_by_year: dict[int, set[tuple[str, str]]] = defaultdict(set)
    target_ids_by_year: dict[int, set[str]] = defaultdict(set)
    for sample in samples:
        year = int(sample["year"])
        target_ids_by_year[year].add(sample["utt_id"])
    result: dict[tuple[int, str, str], list[dict[str, str]]] = defaultdict(list)
    receipts: list[dict[str, Any]] = []
    for year in sorted(target_ids_by_year):
        path, record, manifest_path = annual_table_contract(
            morph_root, year, "utterance_master_v2"
        )
        measured_header = validate_header(path, "utterance_master_v2")
        # First capped pass finds the target dialogue IDs without assuming that
        # utt_seq values are consecutive.
        target_rows, first_pass_rows = capped_rows_by_id(
            path, target_ids_by_year[year], max_rows=row_cap
        )
        targets_by_year[year] = {
            (row["dialogue_id"], row["session_id"])
            for row in target_rows.values()
        }
        rows_scanned = 0
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for source_order, row in enumerate(reader, 1):
                rows_scanned += 1
                dialogue_session = (row["dialogue_id"], row["session_id"])
                if dialogue_session in targets_by_year[year]:
                    copied = {
                        key: row.get(key, "")
                        for key in (
                            "utt_id",
                            "year",
                            "session_id",
                            "utt_seq",
                            "dialogue_id",
                            "speaker_id",
                            "form",
                            "start",
                            "end",
                            "dur",
                            "note",
                        )
                    }
                    copied["__source_order"] = str(source_order)
                    result[(year, row["dialogue_id"], row["session_id"])].append(
                        copied
                    )
                if rows_scanned >= row_cap:
                    break
        for key in [key for key in result if key[0] == year]:
            result[key].sort(
                key=lambda row: (
                    numeric_utt_seq(row["utt_seq"]),
                    int(row["__source_order"]),
                )
            )
        receipt = source_receipt(
            path,
            record,
            manifest_path,
            rows_scanned=rows_scanned,
            stopped_at_row_cap=rows_scanned >= row_cap,
        )
        receipt.update(
            {
                "year": year,
                "table": "utterance_master_v2",
                "measured_header": measured_header,
                "target_lookup_first_pass_rows": first_pass_rows,
                "target_dialogue_sessions": len(targets_by_year[year]),
                "retained_dialogue_rows": sum(
                    len(rows)
                    for (item_year, _, _), rows in result.items()
                    if item_year == year
                ),
            }
        )
        receipts.append(receipt)
    return result, receipts


def add_derived_turns(rows: list[dict[str, str]]) -> None:
    """Add an operational consecutive-speaker run, never a gold turn."""

    turn = 0
    previous_speaker = None
    previous_seq: int | None = None
    previous_end: float | None = None
    for rank, row in enumerate(rows, 1):
        speaker = row["speaker_id"]
        speaker_change = previous_speaker is not None and speaker != previous_speaker
        if rank == 1 or speaker_change:
            turn += 1
        current_seq = numeric_utt_seq(row["utt_seq"])[0]
        seq_gap = ""
        if previous_seq is not None and current_seq < 2**63 - 1:
            seq_gap = str(current_seq - previous_seq)
        try:
            start = float(row["start"])
        except (TypeError, ValueError):
            start = float("inf")
        time_gap = ""
        timestamp_overlap = False
        if previous_end is not None and start != float("inf"):
            delta = start - previous_end
            time_gap = f"{delta:.9f}"
            timestamp_overlap = delta < 0
        row["__source_rank"] = str(rank)
        row["__derived_turn_id"] = f"DTRN{turn:04d}"
        row["__speaker_change_before"] = str(speaker_change)
        row["__utt_seq_gap_before"] = seq_gap
        row["__source_time_gap_before_seconds"] = time_gap
        if not time_gap:
            gap_semantics = "not_applicable_session_start"
        elif row.get("year") == "2020" and abs(float(time_gap) - 0.01) <= 0.0005:
            gap_semantics = "reported_2020_mechanical_pattern_not_pause"
        else:
            gap_semantics = "raw_corpus_timestamp_delta_not_pause_or_turn_evidence"
        row["__source_time_gap_semantics"] = gap_semantics
        row["__timestamp_overlap_raw"] = str(timestamp_overlap)
        note_overlap = "발화겹침" in row.get("note", "")
        row["__source_note_overlap_flag"] = str(note_overlap)
        row["__source_overlap_flag"] = str(note_overlap)
        previous_speaker = speaker
        previous_seq = current_seq if current_seq < 2**63 - 1 else None
        try:
            previous_end = float(row["end"])
        except (TypeError, ValueError):
            previous_end = None

    members_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        members_by_run[row["__derived_turn_id"]].append(row)
    for members in members_by_run.values():
        count = len(members)
        for position, row in enumerate(members, 1):
            row["__speaker_run_unit_count"] = str(count)
            row["__target_position_in_speaker_run"] = str(position)
            row["__distance_to_speaker_run_start"] = str(position - 1)
            row["__distance_to_speaker_run_end"] = str(count - position)
    for index, row in enumerate(rows):
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        row["__speaker_change_after"] = str(
            next_row is not None and next_row["speaker_id"] != row["speaker_id"]
        )


def asset_payload(
    *,
    source: Mapping[str, str],
    year: int,
    ledger: Mapping[str, str],
    active_exception: Mapping[str, str] | None,
    r3_root: Path,
) -> dict[str, str]:
    utt_id = source["utt_id"]
    session = source["session_id"]
    wav_path = r3_root / "corpus" / str(year) / session / f"{utt_id}.wav"
    base_tg = (
        r3_root
        / "research_6tier"
        / str(year)
        / session
        / f"{utt_id}.TextGrid"
    )
    if active_exception and active_exception.get("active_annotation_source") == "curated":
        form = active_exception.get("active_transcript", source["form"])
        tg_path = Path(active_exception.get("active_textgrid_path", ""))
        family = "curated_recovery_textgrid"
        form_source = "curated"
    else:
        form = source["form"]
        tg_path = base_tg
        family = "r3_research_6tier"
        form_source = "base"
    return {
        "wav_path": str(wav_path),
        "wav_status": "available" if wav_path.is_file() else "missing",
        "active_textgrid_path": str(tg_path) if tg_path else "",
        "textgrid_status": "available" if tg_path.is_file() else "missing",
        "alignment_family": family,
        "active_form_source": form_source,
        "form": form,
        "ledger_lookup_status": (
            "available_within_approved_scan_cap"
            if ledger
            else "missing_within_approved_scan_cap_zero_drop"
        ),
        "ledger_primary_status": ledger.get("primary_status", ""),
    }


def build(
    *,
    config_path: Path,
    samples_path: Path,
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    require_under(output_dir, PROJECT_ROOT / "outputs" / "pilots")
    output_csv = output_dir / "PV_CONTEXT.csv"
    output_json = output_dir / "PV_CONTEXT_BUILD.json"
    for path in (output_csv, output_json):
        if path.exists():
            raise FileExistsError(f"existing output is never overwritten: {path}")
    config = load_json(config_path)
    validate_config(config)
    samples = read_samples(samples_path)
    row_cap = int(config["safety"]["max_rows_scanned_per_table_year"])
    dialogues, receipts = scan_dialogues(
        samples=samples, morph_root=morph_root, row_cap=row_cap
    )
    for rows in dialogues.values():
        add_derived_turns(rows)
    context_ids_by_year: dict[int, set[str]] = defaultdict(set)
    windows: dict[str, list[dict[str, str] | None]] = {}
    for sample in samples:
        key = (int(sample["year"]), "")
        matching_keys = [
            item_key
            for item_key, rows in dialogues.items()
            if item_key[0] == int(sample["year"])
            and any(row["utt_id"] == sample["utt_id"] for row in rows)
        ]
        if len(matching_keys) != 1:
            raise RuntimeError(
                f"target must resolve to one capped dialogue: {sample['pv_id']} "
                f"{matching_keys}"
            )
        key = matching_keys[0]
        rows = dialogues[key]
        target_index = next(
            index for index, row in enumerate(rows) if row["utt_id"] == sample["utt_id"]
        )
        slots: list[dict[str, str] | None] = []
        for relation in RELATIONS:
            index = target_index + OFFSETS[relation]
            source = rows[index] if 0 <= index < len(rows) else None
            slots.append(source)
            if source is not None:
                context_ids_by_year[int(sample["year"])].add(source["utt_id"])
        windows[sample["pv_id"]] = slots
    ledgers: dict[tuple[int, str], dict[str, str]] = {}
    ledger_lookup_receipts: list[dict[str, Any]] = []
    missing_ledger_ids_by_year: dict[int, set[str]] = {}
    for year, identifiers in context_ids_by_year.items():
        path = rc0_root / "ledgers" / f"{year}_utterance_status.csv.gz"
        selected, rows_scanned, missing = capped_rows_by_id_allow_missing(
            path, identifiers, max_rows=row_cap
        )
        ledgers.update(
            {(year, utt_id): row for utt_id, row in selected.items()}
        )
        ledgers.update({(year, utt_id): {} for utt_id in missing})
        missing_ledger_ids_by_year[year] = missing
        ledger_lookup_receipts.append(
            {
                "year": year,
                "path": str(path),
                "requested_ids": len(identifiers),
                "found_ids": len(selected),
                "missing_ids_within_approved_cap": len(missing),
                "missing_utt_ids": sorted(missing),
                "rows_scanned": rows_scanned,
                "row_cap": row_cap,
                "cap_increased": False,
                "missing_rows_dropped": False,
            }
        )
    active_exceptions = read_active_exceptions(active_view_root)
    output_rows: list[dict[str, str]] = []
    missing_slots = 0
    for sample in samples:
        slots = windows[sample["pv_id"]]
        target_row = slots[RELATIONS.index("target")]
        if target_row is None:
            raise RuntimeError(f"target slot missing: {sample['pv_id']}")
        target_turn = target_row["__derived_turn_id"]
        sample_rows: list[dict[str, str]] = []
        for relation, source in zip(RELATIONS, slots):
            common = {
                "pv_id": sample["pv_id"],
                "target_utt_id": sample["utt_id"],
                "relation": relation,
                "rank_offset": str(OFFSETS[relation]),
                "year": sample["year"],
                "target_session_id": sample["session_id"],
                "derived_turn_is_exploratory": "True",
                "transcription_unit_interpretation": config["context_contract"][
                    "corpus_transcription_unit_interpretation"
                ],
                "operational_speaker_run_rule": config["context_contract"][
                    "speaker_run_rule"
                ],
            }
            if source is None:
                missing_slots += 1
                sample_rows.append(
                    {
                        **common,
                        "slot_status": "missing_dialogue_edge_with_zero_drop_status",
                    }
                )
                continue
            year = int(sample["year"])
            assets = asset_payload(
                source=source,
                year=year,
                ledger=ledgers[(year, source["utt_id"])],
                active_exception=active_exceptions.get((year, source["utt_id"])),
                r3_root=r3_root,
            )
            sample_rows.append(
                {
                    **common,
                    "slot_status": "present",
                    "dialogue_id": source["dialogue_id"],
                    "session_id": source["session_id"],
                    "utt_id": source["utt_id"],
                    "speaker_id": source["speaker_id"],
                    "utt_seq": source["utt_seq"],
                    "source_rank_in_dialogue": source["__source_rank"],
                    "operational_speaker_run_id": source["__derived_turn_id"],
                    "speaker_run_unit_count": source["__speaker_run_unit_count"],
                    "target_position_in_speaker_run": source[
                        "__target_position_in_speaker_run"
                    ],
                    "distance_to_speaker_run_start": source[
                        "__distance_to_speaker_run_start"
                    ],
                    "distance_to_speaker_run_end": source[
                        "__distance_to_speaker_run_end"
                    ],
                    "derived_turn_id": source["__derived_turn_id"],
                    "same_derived_turn_as_target": str(
                        source["__derived_turn_id"] == target_turn
                    ),
                    "speaker_change_before": source["__speaker_change_before"],
                    "speaker_change_after": source["__speaker_change_after"],
                    "utt_seq_gap_before": source["__utt_seq_gap_before"],
                    "source_time_gap_before_seconds": source[
                        "__source_time_gap_before_seconds"
                    ],
                    "source_time_gap_semantics": source[
                        "__source_time_gap_semantics"
                    ],
                    "timestamp_overlap_raw": source["__timestamp_overlap_raw"],
                    "source_start": source["start"],
                    "source_end": source["end"],
                    "source_dur": source["dur"],
                    "source_note": source["note"],
                    "source_note_overlap_flag": source[
                        "__source_note_overlap_flag"
                    ],
                    "source_overlap_flag": source["__source_overlap_flag"],
                    "same_file_as_target": str(
                        source["session_id"] == sample["session_id"]
                    ),
                    **{key: assets[key] for key in (
                        "wav_path",
                        "wav_status",
                        "active_textgrid_path",
                        "textgrid_status",
                        "alignment_family",
                        "active_form_source",
                        "form",
                        "ledger_lookup_status",
                        "ledger_primary_status",
                    )},
                }
            )
        window_complete = all(row.get("slot_status") == "present" for row in sample_rows)
        audio_complete = all(
            row.get("slot_status") != "present" or row.get("wav_status") == "available"
            for row in sample_rows
        )
        window_status = "complete_five_existing_rows" if window_complete else "truncated_at_session_dialogue_edge"
        audio_status = "all_present_slots_available" if audio_complete else "one_or_more_present_slots_missing_audio"
        sufficient = window_complete and audio_complete
        for row in sample_rows:
            row["context_window_status"] = window_status
            row["context_audio_status"] = audio_status
            row["context_sufficient_for_preview"] = str(sufficient)
        output_rows.extend(sample_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_csv(output_csv, CONTEXT_FIELDS, output_rows)
    manifest = {
        "schema_version": "pv_context_manifest_build.v1",
        "status": "completed_existing_row_rank_pm2_zero_drop",
        **base_build_receipt(config_path),
        "input": {
            "path": str(samples_path),
            "rows": len(samples),
            "sha256": sha256_file(samples_path),
        },
        "counts": {
            "target_samples": len(samples),
            "context_rows": len(output_rows),
            "expected_context_rows": len(samples) * 5,
            "present_slots": sum(row["slot_status"] == "present" for row in output_rows),
            "missing_edge_slots": missing_slots,
            "ledger_ids_missing_within_approved_cap": sum(
                len(values) for values in missing_ledger_ids_by_year.values()
            ),
            "derived_turns_are_exploratory": True,
            "operational_speaker_run_rule": config["context_contract"][
                "speaker_run_rule"
            ],
            "complete_context_windows": sum(
                row["relation"] == "target"
                and row["context_window_status"] == "complete_five_existing_rows"
                for row in output_rows
            ),
            "preview_sufficient_targets": sum(
                row["relation"] == "target"
                and row["context_sufficient_for_preview"] == "True"
                for row in output_rows
            ),
        },
        "sources": receipts,
        "ledger_lookups": ledger_lookup_receipts,
        "output": {
            "path": output_csv.name,
            "bytes": output_csv.stat().st_size,
            "sha256": sha256_file(output_csv),
        },
        "safety": {
            "same_session_dialogue_only": True,
            "utt_seq_arithmetic_used": False,
            "missing_slots_dropped": False,
            "missing_ledger_rows_dropped": False,
            "ledger_lookup_cap_increased": False,
            "turn_gold_annotation_claimed": False,
            "source_timestamp_gap_interpreted_as_pause": False,
            "timestamp_overlap_used_as_overlap_gold": False,
            "realization_judgement_performed": False,
            "source_assets_modified": False,
            "mfa_run": False,
            "koina_run": False,
            "wav2vec2_run": False,
        },
    }
    atomic_write_json(output_json, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--morph-root", type=Path, default=DEFAULT_MORPH_ROOT)
    parser.add_argument("--rc0-root", type=Path, default=DEFAULT_RC0_ROOT)
    parser.add_argument(
        "--active-view-root", type=Path, default=DEFAULT_ACTIVE_VIEW_ROOT
    )
    parser.add_argument("--r3-root", type=Path, default=DEFAULT_R3_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(
            config_path=args.config.resolve(),
            samples_path=args.samples.resolve(),
            morph_root=args.morph_root.resolve(),
            rc0_root=args.rc0_root.resolve(),
            active_view_root=args.active_view_root.resolve(),
            r3_root=args.r3_root.resolve(),
            output_dir=args.output_dir.resolve(),
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
