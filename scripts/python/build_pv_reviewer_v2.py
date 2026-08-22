"""Build the approved PV reviewer v2 derivative for the frozen 14-item set.

The builder is deliberately narrow: it reuses the already-passed PV-A assets,
preserves the user's 15-row exploratory JSONL byte-for-byte, and materializes
text-only dialogue context for the selected exact IDs.  It never judges
realization and never runs MFA, KOINA, wav2vec2, or audio transformation.
"""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import html
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from build_pv_context_manifest import add_derived_turns
from build_pv_ipad_balanced14 import (
    PHENOMENON_ORDER,
    data_uri,
    package_map,
    pick_balanced_samples,
    read_csv,
)
from pipeline_common import sha256_file
from pv_preview_common import (
    DEFAULT_CONFIG,
    DEFAULT_MORPH_ROOT,
    annual_table_contract,
    capped_rows_by_id_allow_missing,
    load_json,
    source_receipt,
    validate_header,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_ROOT = (
    PROJECT_ROOT / "outputs" / "pilots" / "pv_seven_phenomena_20260819"
)
DEFAULT_IPAD_DIR = PROJECT_ROOT / "work" / "pv_ipad_balanced14_20260820"
DEFAULT_USER_JSONL = Path(
    r"C:\Users\ari30\Dropbox\pv_seven_phenomena_20260819"
) / (
    "PV_REVIEW_IPAD_BALANCED14_2026-08-22T00-45-38-842Z.jsonl"
)
DEFAULT_REFERENCE_JSONL = (
    PROJECT_ROOT
    / "work"
    / "reference_evidence_pilot_20260822"
    / "REFERENCE_EVIDENCE_WON_2022_DRAFT_v2.jsonl"
)
DEFAULT_DESIGN = (
    PROJECT_ROOT
    / "docs"
    / "reviews"
    / "incoming"
    / "EXTERNAL_REVIEW_pv_reviewer_v2_design_codex_20260822.md"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "pv_seven_phenomena_reviewer_v2_20260822"
)

HTML_NAME = "PV_REVIEWER_V2.html"
BUILD_NAME = "PV_REVIEWER_V2_BUILD.json"
IMPORTED_NAME = "PV_REVIEWER_V1_IMPORTED.jsonl"
DIALOGUE_NAME = "PV_REVIEWER_V2_DIALOGUES.jsonl"
CORE_CODES = {"PT", "NAN", "NAL", "NI", "LLN"}
ENDPOINT_YEARS = {2020, 2025}
ALLOWED_IMPORT_BATCHES = {
    "balanced14_2020_2025_v1",
    "balanced14_2020_2025_reviewer_v2",
}

UTTERANCE_FIELDS = [
    "utt_id",
    "year",
    "session_id",
    "utt_seq",
    "dialogue_id",
    "dialogue_speaker_ids",
    "n_dialogue_speakers",
    "co_speaker_ids",
    "n_co_speakers",
    "category_norm",
    "discourse_mode",
    "topic",
    "relation",
    "speaker_id",
    "sex",
    "age_norm",
    "birthplace_norm",
    "current_residence_norm",
    "form",
    "tagged",
    "original_form",
    "start",
    "end",
    "dur",
    "note",
    "pron_pred_hangul",
    "pron_pred_roman",
    "pron_pred_ipa",
    "pron_reference_form",
    "pron_reference_hangul",
    "pron_reference_roman",
    "pron_reference_ipa",
    "pron_reference_source",
    "pron_reference_status",
]

MORPH_UNIT_FIELDS = [
    "utt_id",
    "year",
    "eojeol_idx",
    "morph_idx_in_eojeol",
    "morph_idx_in_utterance",
    "morph_surface",
    "pos",
    "unit_idx_in_morph",
    "unit_idx_in_eojeol",
    "unit_surface",
    "unit_type",
    "onset_jamo",
    "nucleus_jamo",
    "coda_jamo",
]


def json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(path)
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    partial.write_bytes(payload)
    os.replace(partial, path)


def write_text_atomic(path: Path, text: str) -> None:
    write_bytes_atomic(path, text.encode("utf-8"))


def read_jsonl_bytes(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    payload = path.read_bytes()
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(payload.decode("utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"JSONL parse failure line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"JSONL line {line_number} is not an object")
        rows.append(value)
    if not rows:
        raise RuntimeError("user revision JSONL is empty")
    return payload, rows


def semantic_fingerprint(row: Mapping[str, Any]) -> str:
    ignored = {
        "reviewed_at",
        "event_uuid",
        "revision_seq",
        "supersedes_event_uuid",
        "possible_duplicate_of",
        "import_source_path",
        "import_source_sha256",
    }
    payload = {key: row[key] for key in sorted(row) if key not in ignored}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def validate_user_rows(
    rows: list[dict[str, Any]], allowed_event_ids: set[str]
) -> dict[str, Any]:
    unknown = sorted(
        {
            str(row.get("review_event_id", ""))
            for row in rows
            if str(row.get("review_event_id", "")) not in allowed_event_ids
        }
    )
    if unknown:
        raise RuntimeError(f"user JSONL contains unknown review events: {unknown}")
    invalid_batches = sorted(
        {
            str(row.get("ipad_batch", ""))
            for row in rows
            if row.get("ipad_batch")
            and str(row.get("ipad_batch")) not in ALLOWED_IMPORT_BATCHES
        }
    )
    if invalid_batches:
        raise RuntimeError(f"user JSONL contains invalid batches: {invalid_batches}")
    unique_ids = {str(row["review_event_id"]) for row in rows}
    fingerprints: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows, 1):
        fingerprints[semantic_fingerprint(row)].append(index)
    duplicate_groups = [positions for positions in fingerprints.values() if len(positions) > 1]
    return {
        "rows": len(rows),
        "unique_review_events": len(unique_ids),
        "listened_true": sum(row.get("listened") is True for row in rows),
        "semantic_duplicate_groups": duplicate_groups,
        "possible_duplicate_rows": sum(len(group) - 1 for group in duplicate_groups),
    }


def scan_dialogue_text(
    *,
    selected: list[dict[str, str]],
    morph_root: Path,
    row_cap: int,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, str]],
    dict[str, str],
    list[dict[str, Any]],
]:
    targets_by_year: dict[int, set[str]] = defaultdict(set)
    samples_by_id = {row["utt_id"]: row for row in selected}
    for sample in selected:
        targets_by_year[int(sample["year"])].add(sample["utt_id"])

    dialogues: dict[str, list[dict[str, Any]]] = {row["pv_id"]: [] for row in selected}
    target_metadata: dict[str, dict[str, str]] = {row["pv_id"]: {} for row in selected}
    statuses = {row["pv_id"]: "target_not_found_within_cap" for row in selected}
    receipts: list[dict[str, Any]] = []

    for year in sorted(targets_by_year):
        path, record, manifest_path = annual_table_contract(
            morph_root, year, "utterance_master_v2"
        )
        measured_header = validate_header(path, "utterance_master_v2")
        missing_headers = [field for field in UTTERANCE_FIELDS if field not in measured_header]
        if missing_headers:
            raise RuntimeError(f"utterance header missing v2 fields: {missing_headers}")
        target_rows, lookup_rows, missing_ids = capped_rows_by_id_allow_missing(
            path, targets_by_year[year], max_rows=row_cap
        )
        target_keys = {
            (row["dialogue_id"], row["session_id"])
            for row in target_rows.values()
        }
        rows_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        rows_scanned = 0
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for source_order, row in enumerate(reader, 1):
                rows_scanned += 1
                key = (row["dialogue_id"], row["session_id"])
                if key in target_keys:
                    copied = {field: row.get(field, "") for field in UTTERANCE_FIELDS}
                    copied["__source_order"] = str(source_order)
                    rows_by_key[key].append(copied)
                if rows_scanned >= row_cap:
                    break
        for rows in rows_by_key.values():
            rows.sort(
                key=lambda item: (
                    int(item["utt_seq"]) if item["utt_seq"].isdigit() else 2**63 - 1,
                    int(item["__source_order"]),
                )
            )
            add_derived_turns(rows)

        for utt_id in targets_by_year[year]:
            sample = samples_by_id[utt_id]
            pv_id = sample["pv_id"]
            if utt_id in missing_ids:
                dialogues[pv_id] = [
                    {
                        "pv_id": pv_id,
                        "row_status": "target_not_found_within_cap_zero_drop",
                        "utt_id": utt_id,
                        "is_target": False,
                    }
                ]
                continue
            target_source = target_rows[utt_id]
            key = (target_source["dialogue_id"], target_source["session_id"])
            source_rows = rows_by_key.get(key, [])
            target_matches = [row for row in source_rows if row["utt_id"] == utt_id]
            if len(target_matches) != 1:
                statuses[pv_id] = "target_row_count_not_one_zero_drop"
            else:
                statuses[pv_id] = "complete_text_dialogue_with_target"
                target_metadata[pv_id] = {
                    field: target_matches[0].get(field, "") for field in UTTERANCE_FIELDS
                }
                target_metadata[pv_id].update(
                    {
                        "derived_turn_id": target_matches[0]["__derived_turn_id"],
                        "speaker_run_unit_count": target_matches[0][
                            "__speaker_run_unit_count"
                        ],
                        "target_position_in_speaker_run": target_matches[0][
                            "__target_position_in_speaker_run"
                        ],
                    }
                )
            public_rows: list[dict[str, Any]] = []
            for row in source_rows:
                public_rows.append(
                    {
                        "pv_id": pv_id,
                        "row_status": "present",
                        **{field: row.get(field, "") for field in UTTERANCE_FIELDS},
                        "source_rank_in_dialogue": row["__source_rank"],
                        "derived_turn_id": row["__derived_turn_id"],
                        "derived_turn_is_exploratory": True,
                        "speaker_run_unit_count": row["__speaker_run_unit_count"],
                        "position_in_speaker_run": row[
                            "__target_position_in_speaker_run"
                        ],
                        "speaker_change_before": row["__speaker_change_before"],
                        "speaker_change_after": row["__speaker_change_after"],
                        "source_time_gap_before_seconds": row[
                            "__source_time_gap_before_seconds"
                        ],
                        "source_time_gap_semantics": row[
                            "__source_time_gap_semantics"
                        ],
                        "timestamp_overlap_raw": row["__timestamp_overlap_raw"],
                        "source_note_overlap_flag": row[
                            "__source_note_overlap_flag"
                        ],
                        "is_target": row["utt_id"] == utt_id,
                    }
                )
            dialogues[pv_id] = public_rows

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
                "target_lookup_rows": lookup_rows,
                "target_ids_requested": len(targets_by_year[year]),
                "target_ids_missing_within_cap": sorted(missing_ids),
                "retained_dialogue_rows": sum(
                    len(rows) for rows in rows_by_key.values()
                ),
            }
        )
        receipts.append(receipt)
    return dialogues, target_metadata, statuses, receipts


def scan_hia_morph_links(
    *,
    selected: list[dict[str, str]],
    morph_root: Path,
    row_cap: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    specifications: dict[int, list[tuple[dict[str, str], str]]] = defaultdict(list)
    for sample in selected:
        if sample["matched_table"] != "orth_eojeol_tokens":
            continue
        evidence = json.loads(sample["match_evidence_json"])
        specifications[int(sample["year"])].append(
            (sample, str(evidence.get("linked_morph_eojeol_idx", "")))
        )
    result: dict[str, dict[str, Any]] = {}
    receipts: list[dict[str, Any]] = []
    for year, specs in sorted(specifications.items()):
        path, record, manifest_path = annual_table_contract(morph_root, year, "morph_units")
        measured_header = validate_header(path, "morph_units")
        missing_headers = [field for field in MORPH_UNIT_FIELDS if field not in measured_header]
        if missing_headers:
            raise RuntimeError(f"morph_units header missing v2 fields: {missing_headers}")
        wanted = {
            (sample["utt_id"], eojeol_idx): sample["pv_id"]
            for sample, eojeol_idx in specs
            if eojeol_idx
        }
        found: dict[str, list[dict[str, str]]] = defaultdict(list)
        rows_scanned = 0
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                rows_scanned += 1
                pv_id = wanted.get((row["utt_id"], row["eojeol_idx"]))
                if pv_id:
                    found[pv_id].append(
                        {field: row.get(field, "") for field in MORPH_UNIT_FIELDS}
                    )
                if rows_scanned >= row_cap:
                    break
        for sample, eojeol_idx in specs:
            pv_id = sample["pv_id"]
            source_evidence = json.loads(sample["match_evidence_json"])
            rows = found.get(pv_id, [])
            groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
            for row in rows:
                groups[
                    (
                        row["morph_idx_in_eojeol"],
                        row["morph_surface"],
                        row["pos"],
                    )
                ].append(row)
            segments = []
            for (morph_index, surface, pos), units in sorted(
                groups.items(), key=lambda item: int(item[0][0] or 0)
            ):
                units.sort(key=lambda row: int(row["unit_idx_in_morph"] or 0))
                segments.append(
                    {
                        "morph_idx_in_eojeol": morph_index,
                        "surface": surface,
                        "pos": pos,
                        "units": "".join(row["unit_surface"] for row in units),
                    }
                )
            result[pv_id] = {
                "status": (
                    "linked_exact_eojeol_within_cap"
                    if segments
                    else (
                        "unavailable_"
                        f"{source_evidence.get('morph_link_status', 'missing_link')}"
                        "_zero_drop"
                        if not eojeol_idx
                        else "missing_linked_eojeol_within_cap_zero_drop"
                    )
                ),
                "linked_morph_eojeol_idx": eojeol_idx,
                "orth_eojeol_idx": source_evidence.get("orth_eojeol_idx", ""),
                "orth_eojeol_form": source_evidence.get("orth_eojeol_form", ""),
                "source_morph_link_status": source_evidence.get(
                    "morph_link_status", ""
                ),
                "segments": segments,
                "unit_rows": len(rows),
            }
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
                "table": "morph_units",
                "measured_header": measured_header,
                "requested_hia_links": len(specs),
                "linked_hia_rows": sum(len(found.get(sample["pv_id"], [])) for sample, _ in specs),
            }
        )
        receipts.append(receipt)
    return result, receipts


def target_display(
    sample: Mapping[str, str], hia_links: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    evidence = json.loads(sample["match_evidence_json"])
    table = sample["matched_table"]
    if table == "morph_boundaries":
        return {
            "status": "direct_from_match_evidence",
            "kind": "boundary",
            "segments": [
                {
                    "surface": evidence.get("left_morph_surface", ""),
                    "pos": evidence.get("left_pos", ""),
                    "focus_unit": evidence.get("left_unit_surface", ""),
                },
                {
                    "surface": evidence.get("right_morph_surface", ""),
                    "pos": evidence.get("right_pos", ""),
                    "focus_unit": evidence.get("right_unit_surface", ""),
                },
            ],
            "boundary": (
                f"{evidence.get('left_unit_surface', '')}│"
                f"{evidence.get('right_unit_surface', '')}"
            ),
        }
    if table == "morph_units":
        return {
            "status": "direct_from_match_evidence",
            "kind": "morph_internal",
            "segments": [
                {
                    "surface": evidence.get("morph_surface", ""),
                    "pos": evidence.get("pos", ""),
                    "focus_unit": (
                        f"{evidence.get('left_unit_surface', '')}│"
                        f"{evidence.get('right_unit_surface', '')}"
                    ),
                }
            ],
            "boundary": (
                f"{evidence.get('left_unit_surface', '')}│"
                f"{evidence.get('right_unit_surface', '')}"
            ),
        }
    link = dict(hia_links.get(sample["pv_id"], {}))
    return {
        "status": link.get("status", "missing_hia_link_status_zero_drop"),
        "kind": "orth_contraction_probe",
        "segments": link.get("segments", []),
        "boundary": evidence.get("orth_eojeol_form", sample["active_form"]),
        "linked_morph_eojeol_idx": link.get("linked_morph_eojeol_idx", ""),
    }


def load_literature(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    _, rows = read_jsonl_bytes(path)
    positive = [
        {
            "claim_ko": row.get("claim_ko", ""),
            "printed_page": row.get("printed_page"),
            "pdf_page": row.get("pdf_page"),
            "relation": row.get("relation", ""),
            "link_scope": row.get("link_scope", ""),
            "does_not_establish": row.get("does_not_establish", ""),
            "confidence": row.get("confidence", ""),
        }
        for row in rows
        if row.get("evidence_owner") == "paper_author"
        and row.get("relation") != "not_found"
    ]
    return positive, {
        "source_rows": len(rows),
        "positive_common_method_rows": len(positive),
        "not_found_rows_excluded": sum(row.get("relation") == "not_found" for row in rows),
        "cited_source_rows_not_primary_verified": sum(
            row.get("evidence_owner") == "cited_source" for row in rows
        ),
    }


def context_rows_for_display(path: Path) -> list[dict[str, str]]:
    fields = [
        "relation",
        "speaker_id",
        "form",
        "slot_status",
        "wav_status",
        "derived_turn_id",
        "same_derived_turn_as_target",
        "speaker_change_before",
        "speaker_change_after",
        "source_note_overlap_flag",
    ]
    return [{field: row.get(field, "") for field in fields} for row in read_csv(path)]


def dialogue_jsonl(dialogues: Mapping[str, list[Mapping[str, Any]]]) -> str:
    lines = []
    for pv_id in sorted(dialogues):
        for row in dialogues[pv_id]:
            lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + ("\n" if lines else "")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>PV 검토 화면 v2</title>
<style>
:root{--ink:#17212b;--muted:#5a6875;--line:#d5dfe7;--paper:#fff;--bg:#edf2f5;--navy:#173b57;--blue:#eaf4fa;--green:#e5f5eb;--amber:#fff2cb;--violet:#efe9f8;--red:#ffeae7;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;color:var(--ink)}*{box-sizing:border-box}body{margin:0;background:var(--bg);line-height:1.55}button,input,select,textarea{font:inherit}button{min-height:44px;border:0;border-radius:9px;padding:9px 13px;background:#285f9e;color:#fff;font-weight:700}.secondary{background:#536575}.ghost{background:#e7edf2;color:#213b4d}.danger{background:#8d473e}header{background:var(--navy);color:#fff;padding:16px max(16px,env(safe-area-inset-left))}header h1{font-size:1.32rem;margin:0 0 5px}.safety{margin:4px 0;font-size:.9rem}.shell{display:grid;grid-template-columns:280px minmax(0,1fr);max-width:1240px;margin:auto;min-height:calc(100vh - 100px)}aside{border-right:1px solid var(--line);background:#f7fafc;padding:14px;position:sticky;top:0;height:100vh;overflow:auto}.control{display:grid;gap:6px;margin-bottom:10px}.control input,.control select,.review input,.review select,.review textarea{width:100%;min-height:42px;border:1px solid #95a6b5;border-radius:8px;padding:8px;background:#fff;color:var(--ink)}#candidate-buttons{display:grid;gap:7px}.candidate{display:block;width:100%;text-align:left;background:#fff;color:var(--ink);border:1px solid var(--line);min-height:48px}.candidate.active{border:3px solid #2b6c9d;background:var(--blue)}.candidate small{display:block;color:var(--muted)}main{padding:14px;min-width:0}.topnav{display:flex;gap:8px;align-items:center;justify-content:space-between;position:sticky;top:0;background:var(--bg);z-index:3;padding:6px 0}.topnav .status{text-align:center;font-weight:700}.panel{background:var(--paper);border:1px solid var(--line);border-radius:13px;padding:16px;margin:10px 0;box-shadow:0 2px 8px #173b5710}.titleline{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.tag{display:inline-block;padding:.12rem .5rem;border-radius:999px;font-size:.78rem;font-weight:700}.core{background:#dcefe4;color:#176742}.exploratory{background:#eae3f6;color:#6c4a96}.meta{color:var(--muted);overflow-wrap:anywhere}.utterance{font-size:1.25rem;background:#f4efe2;padding:13px;border-radius:9px}.morphs{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.morph{border:2px solid #2a729d;border-radius:10px;padding:8px 11px;background:#eef7fc}.boundary{font-size:1.25rem;font-weight:800;color:#9a3f31}.audio-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.audio-grid label{display:block;font-weight:700;margin-bottom:5px}audio{width:100%}.warning{background:var(--amber);padding:10px;border-radius:8px}.review{display:grid;grid-template-columns:1fr 1fr;gap:12px}.review label{display:grid;gap:4px;font-weight:650}.review .wide{grid-column:1/-1}.review textarea{min-height:72px;resize:vertical}.check{display:flex!important;align-items:center;gap:8px}.check input{width:24px;min-height:24px}.actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.saved{color:#176742;font-weight:700}details{border-top:1px solid var(--line);padding:10px 0}summary{font-weight:750;cursor:pointer;min-height:35px}.transcript-tools{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.transcript-tools input{flex:1;min-width:180px}.transcript{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:9px}.transcript-row{display:grid;grid-template-columns:70px 86px 1fr;gap:8px;width:100%;text-align:left;background:#fff;color:var(--ink);border:0;border-bottom:1px solid var(--line);border-radius:0;font-weight:400}.transcript-row.target{background:#fff0cc;border-left:5px solid #c07a00}.transcript-row.overlap{box-shadow:inset 5px 0 #a74b42}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.9rem}th,td{border-bottom:1px solid var(--line);padding:7px;text-align:left;vertical-align:top}.literature li{margin:.55rem 0}.importbox{background:var(--violet);padding:11px;border-radius:9px}.copy-panel{display:none}.copy-panel textarea{width:100%;min-height:220px;font-family:Consolas,monospace}.empty{color:var(--muted);font-style:italic}
@media(max-width:820px){.shell{display:block}.shell aside{position:static;height:auto;border:0;border-bottom:1px solid var(--line)}#candidate-buttons{grid-template-columns:repeat(2,minmax(0,1fr));max-height:260px;overflow:auto}.audio-grid,.review{grid-template-columns:1fr}.transcript-row{grid-template-columns:58px 72px 1fr}main{padding:10px}.panel{padding:13px}}
@media(prefers-color-scheme:dark){:root{--ink:#eef4f8;--muted:#b8c5cf;--line:#425462;--paper:#1c2933;--bg:#111a22;--navy:#183b56;--blue:#193c50;--green:#193d2b;--amber:#4b3d16;--violet:#332944}.candidate,.transcript-row,.review input,.review select,.review textarea,.control input,.control select{background:#14202a;color:var(--ink)}.utterance{background:#393427}.morph{background:#17384a}}
</style>
</head>
<body>
<header><h1>PV 검토 화면 v2 · 균형 14개</h1><p class="safety">탐색용 기록입니다. 자동 실현 판정·정식 판정 ledger·KOINA 결과가 아닙니다.</p><p class="safety">전체 대화는 텍스트만 제공하며, 문맥 음성의 0.05초 간격은 합성 구분자입니다.</p></header>
<div class="shell">
<aside>
  <div class="control"><label for="candidate-search">후보 검색</label><input id="candidate-search" placeholder="현상·연도·표적·ID"></div>
  <div class="control"><label for="priority-filter">우선순위</label><select id="priority-filter"><option value="all">전체</option><option value="core">핵심 5현상</option><option value="exploratory">탐색 VH·HIA</option></select></div>
  <p id="global-progress" class="meta"></p>
  <div id="candidate-buttons"></div>
</aside>
<main>
  <nav class="topnav"><button id="prev" type="button">← 이전</button><div id="position" class="status"></div><button id="next" type="button">다음 →</button></nav>
  <section class="panel">
    <div class="titleline"><span id="priority-tag" class="tag"></span><h2 id="sample-title"></h2></div>
    <p id="sample-meta" class="meta"></p>
    <p id="active-form" class="utterance"></p>
    <div id="morph-display" class="morphs"></div>
    <p id="morph-limit" class="warning"></p>
  </section>
  <section class="panel audio-grid"><div><label>대상 발화</label><audio id="target-audio" controls preload="metadata"></audio></div><div><label>앞뒤 문맥 ±2</label><audio id="context-audio" controls preload="metadata"></audio></div></section>
  <section class="panel">
    <form id="review-form" class="review">
      <label class="check wide"><input type="checkbox" name="listened"> 청취함</label>
      <label>환경 인상<select name="env_impression"><option value=""></option><option value="env_ok">환경 적절</option><option value="env_wrong">환경 부적절</option><option value="unsure">불확실</option></select></label>
      <label>판단 확신도<select name="judgement_confidence"><option value="unjudged">미판정</option><option value="high">높음</option><option value="medium">중간</option><option value="low">낮음</option></select></label>
      <label class="wide">실현 인상·들린 형식<textarea name="realization_impression" placeholder="예: ‘한식집’의 ㅅ이 된소리처럼 들림 / 불분명"></textarea></label>
      <label>들린 형식(짧게)<input name="heard_form_free" placeholder="예: 한식찝 / 판단불가"></label>
      <label>변이 태그<input name="heard_variant_tags" placeholder="쉼표로 구분: 경음, 비음화, 기타"></label>
      <label>겹침 인상<select name="overlap_impression"><option value="not_checked">확인 안 함</option><option value="no">없음</option><option value="yes">있음</option><option value="unsure">불확실</option></select></label>
      <label>문맥 충분성<select name="context_sufficient"><option value=""></option><option value="yes">충분</option><option value="need_more_before">앞 문맥 필요</option><option value="need_more_after">뒤 문맥 필요</option><option value="need_other_file">다른 파일 필요</option></select></label>
      <label class="wide">음질 메모<textarea name="audio_quality_note" placeholder="예: 적절 / 낮은 음량 / 겹침"></textarea></label>
      <label class="wide">연구 메모·빠진 정보<textarea name="missing_info_note" placeholder="판단에 더 필요했던 맥락이나 정보를 적습니다."></textarea></label>
      <label>스키마 열 제안<textarea name="schema_field_suggestion" placeholder="예: 겹말 여부, 확신도"></textarea></label>
      <label>도구·화면 메모<textarea name="tool_note" placeholder="화면 사용 중 불편한 점"></textarea></label>
      <div class="actions wide"><button id="save" type="button">새 revision 저장</button><span id="saved" class="saved" aria-live="polite"></span></div>
    </form>
  </section>
  <section class="panel">
    <details id="pm2-panel"><summary>±2 문맥 전사</summary><div id="pm2-table" class="table-wrap"></div></details>
    <details id="speaker-run-panel"><summary>조작적 동일화자 연속 묶음</summary><p class="warning">동일 speaker_id의 연속 행을 묶은 탐색 표지이며 실제 말차례·운율구 정답이 아닙니다.</p><div id="speaker-run" class="transcript"></div></details>
    <details id="dialogue-panel"><summary>전체 대화 전사 검색·선택</summary><div class="transcript-tools"><input id="dialogue-search" placeholder="전체 대화에서 검색"><label class="check"><input id="dialogue-all" type="checkbox"> 전체 행 보기</label></div><p id="selected-context" class="meta"></p><div id="dialogue-results" class="transcript"></div></details>
    <details id="social-panel"><summary>화자·대화 상황</summary><div id="social-meta" class="table-wrap"></div></details>
    <details id="pron-panel"><summary>규칙 예상형·사전 참조형</summary><p class="warning">둘 다 실제 들린 발음이나 자동 실현 정답이 아닙니다.</p><div id="pron-meta" class="table-wrap"></div></details>
    <details id="literature-panel"><summary>원유권(2022) 공통 방법론 근거</summary><p class="warning">개별 음운현상의 긍정적 근거가 아닙니다. not_found와 원문 미확인 재인용 행은 아래 긍정 목록에서 제외했습니다.</p><ol id="literature" class="literature"></ol></details>
    <details id="audit-panel"><summary>원자료·감사 정보</summary><div id="audit-meta"></div></details>
  </section>
  <section class="panel importbox"><h3>기존 기록 보존·내보내기</h3><p id="import-summary"></p><div class="actions"><label class="ghost" style="padding:9px 13px;border-radius:9px;font-weight:700">JSONL 가져오기 <input id="import-file" type="file" accept=".jsonl,.ndjson,.txt" style="display:none"></label><button id="export" type="button">전체 JSONL 저장</button><button id="copy" type="button" class="secondary">복사용 JSONL 펼치기</button></div><p id="import-status" aria-live="polite"></p></section>
  <section id="copy-panel" class="panel copy-panel"><textarea id="copy-text" readonly></textarea></section>
</main>
</div>
<script>
const SAMPLES=__SAMPLES__;
const DIALOGUES=__DIALOGUES__;
const BASE_HISTORY=__BASE_HISTORY__;
const LITERATURE=__LITERATURE__;
const BUILD_META=__BUILD_META__;
const LOCAL_KEY='pv_reviewer_v2_local_history_20260822';
const IMPORT_META_KEY='pv_reviewer_v2_import_meta_20260822';
const ALLOWED_BATCHES=new Set(['balanced14_2020_2025_v1','balanced14_2020_2025_reviewer_v2']);
const SAMPLE_MAP=Object.fromEntries(SAMPLES.map(x=>[x.pv_id,x]));
const EVENT_MAP=Object.fromEntries(SAMPLES.map(x=>[x.review_event_id,x]));
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function semanticObject(row){const ignored=new Set(['reviewed_at','event_uuid','revision_seq','supersedes_event_uuid','possible_duplicate_of','import_source_path','import_source_sha256']);return Object.fromEntries(Object.keys(row).filter(k=>!ignored.has(k)).sort().map(k=>[k,row[k]]));}
function semanticFingerprint(row){return JSON.stringify(semanticObject(row));}
function parseJsonl(text){const lines=String(text).split(/\r?\n/).filter(x=>x.trim());if(!lines.length)throw new Error('JSONL이 비어 있습니다.');return lines.map((line,i)=>{let row;try{row=JSON.parse(line);}catch(e){throw new Error(`JSONL ${i+1}행 파싱 실패`);}if(!row||Array.isArray(row)||typeof row!=='object')throw new Error(`JSONL ${i+1}행이 객체가 아닙니다.`);if(!EVENT_MAP[row.review_event_id])throw new Error(`알 수 없는 review_event_id: ${row.review_event_id}`);if(row.ipad_batch&&!ALLOWED_BATCHES.has(row.ipad_batch))throw new Error(`허용되지 않은 batch: ${row.ipad_batch}`);return row;});}
function duplicateCount(existing,incoming){const seen=new Set(existing.map(semanticFingerprint));return incoming.filter(x=>seen.has(semanticFingerprint(x))).length;}
function latestByEvent(rows){const latest={};rows.forEach((row,index)=>{latest[row.review_event_id]={row,index};});return Object.fromEntries(Object.entries(latest).map(([k,v])=>[k,v.row]));}
function localHistory(){try{const value=JSON.parse(localStorage.getItem(LOCAL_KEY)||'[]');return Array.isArray(value)?value:[];}catch(e){return [];}}
function setLocalHistory(rows){localStorage.setItem(LOCAL_KEY,JSON.stringify(rows));}
function allHistory(){return BASE_HISTORY.concat(localHistory());}
function eventIdentity(row,index){return row.event_uuid||`legacy:${row.review_event_id}:${row.reviewed_at||''}:${index}`;}
function makeUuid(){if(globalThis.crypto&&typeof globalThis.crypto.randomUUID==='function')return globalThis.crypto.randomUUID();return `pv2-${Date.now()}-${Math.random().toString(16).slice(2)}`;}
function makeRevision(meta,values,history,viewedPanels){const eventRows=history.filter(x=>x.review_event_id===meta.review_event_id);const previous=eventRows[eventRows.length-1];const row={...meta,schema_version:'pv_reviewer_event.v2',event_uuid:makeUuid(),revision_seq:eventRows.length+1,supersedes_event_uuid:previous?eventIdentity(previous,history.indexOf(previous)):'',import_source_path:BUILD_META.imported_source_path,import_source_sha256:BUILD_META.imported_source_sha256,possible_duplicate_of:'',priority_tier:meta.priority_tier,target_display_status:meta.target_display_status,morph_display_status:meta.morph_display_status,...values,heard_variant_tags_json:JSON.stringify(String(values.heard_variant_tags||'').split(',').map(x=>x.trim()).filter(Boolean)),context_viewed:Array.from(viewedPanels).join('|')||'pm2',reference_panels_viewed_json:JSON.stringify(Array.from(viewedPanels).filter(x=>x.endsWith('-panel'))),ipad_batch:'balanced14_2020_2025_reviewer_v2',record_role:'exploratory_pv_only_not_formal_realization_ledger',reviewed_at:new Date().toISOString()};delete row.heard_variant_tags;if(previous&&semanticFingerprint(previous)===semanticFingerprint(row))row.possible_duplicate_of=eventIdentity(previous,history.indexOf(previous));return row;}
function filterIds(query,priority){const q=String(query||'').trim().toLowerCase();return SAMPLES.filter(s=>(priority==='all'||s.priority_tier===priority)&&(!q||[s.pv_id,s.phenomenon_code,s.phenomenon_label,s.year,s.active_form,s.utt_id].join(' ').toLowerCase().includes(q))).map(s=>s.pv_id);}
function toJsonl(rows){return rows.map(x=>JSON.stringify(x)).join('\n')+'\n';}
globalThis.PV_REVIEWER_V2_TEST_API={SAMPLES,BASE_HISTORY,LITERATURE,BUILD_META,parseJsonl,duplicateCount,latestByEvent,makeRevision,filterIds,toJsonl,semanticFingerprint};

function init(){
let currentId=SAMPLES[0].pv_id;let visibleIds=SAMPLES.map(x=>x.pv_id);let viewedPanels=new Set(['pm2']);
const byId=id=>document.getElementById(id);const form=byId('review-form');
function current(){return SAMPLE_MAP[currentId];}
function tableRows(pairs){return '<table><tbody>'+pairs.map(([k,v])=>`<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v||'—')}</td></tr>`).join('')+'</tbody></table>';}
function renderCandidateButtons(){const latest=latestByEvent(allHistory());byId('candidate-buttons').innerHTML=visibleIds.map(id=>{const s=SAMPLE_MAP[id];const done=latest[s.review_event_id]?.listened===true?'✓ ':'';return `<button type="button" class="candidate ${id===currentId?'active':''}" data-pv="${escapeHtml(id)}">${done}${escapeHtml(s.phenomenon_label)} · ${escapeHtml(s.year)}<small>${escapeHtml(id)} · ${escapeHtml(s.active_form)}</small></button>`;}).join('')||'<p class="empty">검색 결과가 없습니다.</p>';document.querySelectorAll('.candidate').forEach(btn=>btn.addEventListener('click',()=>setActive(btn.dataset.pv)));}
function renderProgress(){const latest=latestByEvent(allHistory());const listened=SAMPLES.filter(s=>latest[s.review_event_id]?.listened===true).length;byId('global-progress').textContent=`청취 최신값 ${listened}/14 · 원기록 ${BASE_HISTORY.length} · 추가 revision ${localHistory().length}`;byId('import-summary').textContent=`기존 사용자 JSONL ${BASE_HISTORY.length}행을 원문 그대로 포함했습니다. 최신 view 14개, possible duplicate ${BUILD_META.base_possible_duplicate_rows}개입니다.`;}
function renderMorph(s){const d=s.target_display;const parts=(d.segments||[]).map(seg=>`<span class="morph"><strong>${escapeHtml(seg.surface||seg.units||'형태소 미상')}</strong> / ${escapeHtml(seg.pos||'POS 미상')}<br><small>초점 ${escapeHtml(seg.focus_unit||seg.units||'—')}</small></span>`);byId('morph-display').innerHTML=parts.join('<span class="boundary">│</span>')+`<span class="boundary">경계 ${escapeHtml(d.boundary||'—')}</span>`;byId('morph-limit').textContent=`형태소 표시 상태: ${d.status}. 이 표시는 검색 환경 근거이며 음향적 경계나 실제 실현 판정이 아닙니다.`;}
function rowButton(row){const overlap=row.source_note_overlap_flag==='True'||row.timestamp_overlap_raw==='True';return `<button type="button" class="transcript-row ${row.is_target?'target':''} ${overlap?'overlap':''}" data-utt="${escapeHtml(row.utt_id)}"><span>${escapeHtml(row.source_rank_in_dialogue)}</span><span>${escapeHtml(row.speaker_id)}</span><span>${escapeHtml(row.form||'(전사 없음)')}</span></button>`;}
function wireTranscriptClicks(){document.querySelectorAll('.transcript-row').forEach(btn=>btn.addEventListener('click',()=>{byId('selected-context').textContent=`선택한 문맥: ${btn.dataset.utt}`;viewedPanels.add('dialogue_search');}));}
function renderSpeakerRun(s){const rows=(DIALOGUES[s.pv_id]||[]).filter(x=>x.derived_turn_id===s.target_metadata.derived_turn_id);byId('speaker-run').innerHTML=rows.length?rows.map(rowButton).join(''):'<p class="empty">묶음 텍스트를 찾지 못했습니다.</p>';wireTranscriptClicks();}
function renderDialogue(){const s=current();const rows=DIALOGUES[s.pv_id]||[];const q=byId('dialogue-search').value.trim().toLowerCase();const showAll=byId('dialogue-all').checked;const targetIndex=rows.findIndex(x=>x.is_target);let shown;if(q)shown=rows.filter(x=>[x.form,x.original_form,x.note,x.speaker_id].join(' ').toLowerCase().includes(q));else if(showAll)shown=rows;else shown=rows.filter((_,i)=>Math.abs(i-targetIndex)<=10);byId('dialogue-results').innerHTML=shown.length?shown.map(rowButton).join(''):'<p class="empty">검색 결과가 없습니다.</p>';wireTranscriptClicks();}
function renderPm2(s){const rows=s.context_pm2||[];byId('pm2-table').innerHTML='<table><thead><tr><th>위치</th><th>화자</th><th>전사</th><th>turn/상태</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${escapeHtml(r.relation)}</td><td>${escapeHtml(r.speaker_id||'—')}</td><td>${escapeHtml(r.form||'(없음)')}</td><td>${escapeHtml(r.derived_turn_id||'—')} / ${escapeHtml(r.slot_status||'')}</td></tr>`).join('')+'</tbody></table>';}
function renderMeta(s){const m=s.target_metadata||{};byId('social-meta').innerHTML=tableRows([['화자',m.speaker_id],['성별',m.sex],['연령',m.age_norm],['현재 거주지역',m.current_residence_norm],['출생지역',m.birthplace_norm],['대화 유형',m.discourse_mode],['말뭉치 범주',m.category_norm],['주제',m.topic],['관계',m.relation],['조작적 화자 묶음',`${m.derived_turn_id||'—'} · ${m.target_position_in_speaker_run||'—'}/${m.speaker_run_unit_count||'—'}`]]);byId('pron-meta').innerHTML=tableRows([['규칙 예상형(한글)',m.pron_pred_hangul],['규칙 예상형(IPA)',m.pron_pred_ipa],['사전 참조형',m.pron_reference_hangul],['사전 참조 상태',m.pron_reference_status],['사전 참조 출처',m.pron_reference_source]]);byId('audit-meta').innerHTML=tableRows([['pv_id',s.pv_id],['utt_id',s.utt_id],['occurrence',s.occurrence_ref],['query',s.pv_query_id],['대화 텍스트 상태',s.dialogue_status],['형태소 상태',s.target_display.status],['source manifest SHA',BUILD_META.source_manifest_sha256],['source audit SHA',BUILD_META.source_audit_sha256]]);}
function restoreForm(s){form.reset();form.elements.judgement_confidence.value='unjudged';form.elements.overlap_impression.value='not_checked';const row=latestByEvent(allHistory())[s.review_event_id];if(row)Array.from(form.elements).forEach(el=>{if(!el.name||!(el.name in row))return;if(el.type==='checkbox')el.checked=Boolean(row[el.name]);else if(el.name==='heard_variant_tags'&&row.heard_variant_tags_json){try{el.value=JSON.parse(row.heard_variant_tags_json).join(', ');}catch(e){el.value='';}}else el.value=row[el.name]??'';});byId('saved').textContent=row?'기존 최신 revision을 복원했습니다.':'';}
function setActive(id){if(!SAMPLE_MAP[id])return;currentId=id;viewedPanels=new Set(['pm2']);const s=current();const index=SAMPLES.findIndex(x=>x.pv_id===id);byId('position').textContent=`${index+1}/14 · ${s.phenomenon_code} · ${s.year}`;byId('sample-title').textContent=`${s.phenomenon_label} · ${s.year}`;byId('sample-meta').textContent=`${s.pv_id} · ${s.utt_id} · ${s.environment_scope}`;byId('active-form').textContent=s.active_form;const tag=byId('priority-tag');tag.textContent=s.priority_tier==='core'?'핵심':'탐색';tag.className=`tag ${s.priority_tier}`;renderMorph(s);byId('target-audio').src=s.target_audio;byId('context-audio').src=s.context_audio;renderPm2(s);renderSpeakerRun(s);byId('dialogue-search').value='';byId('dialogue-all').checked=false;byId('selected-context').textContent='';renderDialogue();renderMeta(s);restoreForm(s);renderCandidateButtons();renderProgress();}
function applyFilter(){visibleIds=filterIds(byId('candidate-search').value,byId('priority-filter').value);if(visibleIds.length&&!visibleIds.includes(currentId))currentId=visibleIds[0];renderCandidateButtons();if(visibleIds.length)setActive(currentId);}
function move(delta){const list=visibleIds.length?visibleIds:SAMPLES.map(x=>x.pv_id);let index=list.indexOf(currentId);index=(index+delta+list.length)%list.length;setActive(list[index]);window.scrollTo({top:0,behavior:'smooth'});}
byId('candidate-search').addEventListener('input',applyFilter);byId('priority-filter').addEventListener('change',applyFilter);byId('prev').addEventListener('click',()=>move(-1));byId('next').addEventListener('click',()=>move(1));byId('dialogue-search').addEventListener('input',()=>{viewedPanels.add('dialogue_search');renderDialogue();});byId('dialogue-all').addEventListener('change',()=>{viewedPanels.add('dialogue_search');renderDialogue();});document.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)viewedPanels.add(d.id);}));
byId('save').addEventListener('click',()=>{const s=current();const values={};Array.from(form.elements).forEach(el=>{if(!el.name)return;values[el.name]=el.type==='checkbox'?el.checked:el.value;});const history=allHistory();const row=makeRevision({review_event_id:s.review_event_id,pv_id:s.pv_id,phenomenon_code:s.phenomenon_code,phenomenon_label:s.phenomenon_label,pv_query_id:s.pv_query_id,environment_scope:s.environment_scope,year:String(s.year),utt_id:s.utt_id,occurrence_ref:s.occurrence_ref},values,history,viewedPanels);const local=localHistory();local.push(row);setLocalHistory(local);byId('saved').textContent=`저장됨 · 이 표본 revision ${row.revision_seq}`;renderProgress();renderCandidateButtons();});
byId('import-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{const rows=parseJsonl(await file.text());const dup=duplicateCount(allHistory(),rows);if(dup&&!confirm(`${dup}개 행이 기존 기록과 내용상 같습니다. 삭제하지 않고 모두 추가할까요?`)){byId('import-status').textContent='가져오기를 취소했습니다.';return;}const local=localHistory();local.push(...rows);setLocalHistory(local);localStorage.setItem(IMPORT_META_KEY,JSON.stringify({name:file.name,rows:rows.length,imported_at:new Date().toISOString()}));byId('import-status').textContent=`${rows.length}행을 원형 그대로 추가했습니다. 내용상 중복 ${dup}행도 삭제하지 않았습니다.`;setActive(currentId);}catch(e){byId('import-status').textContent=`가져오기 실패: ${e.message}`;}finally{event.target.value='';}});
function exportBody(){return toJsonl(allHistory());}
byId('export').addEventListener('click',()=>{const body=exportBody();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([body],{type:'application/x-ndjson;charset=utf-8'}));a.download=`PV_REVIEWER_V2_${new Date().toISOString().replace(/[:.]/g,'-')}.jsonl`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);});
byId('copy').addEventListener('click',async()=>{const body=exportBody();const panel=byId('copy-panel');const area=byId('copy-text');area.value=body;panel.style.display='block';area.focus();area.select();try{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(body);}catch(e){};});
byId('literature').innerHTML=LITERATURE.map(x=>`<li><strong>인쇄 ${escapeHtml(x.printed_page??'—')}쪽</strong> ${escapeHtml(x.claim_ko)}<br><small>한계: ${escapeHtml(x.does_not_establish||'—')}</small></li>`).join('');
setActive(currentId);
}
if(typeof document!=='undefined')init();
</script>
</body></html>'''


def build_html(
    *,
    selected: list[dict[str, str]],
    events: list[dict[str, str]],
    packages: Mapping[str, Path],
    dialogues: Mapping[str, list[dict[str, Any]]],
    target_metadata: Mapping[str, dict[str, str]],
    dialogue_statuses: Mapping[str, str],
    hia_links: Mapping[str, Mapping[str, Any]],
    base_history: list[dict[str, Any]],
    literature: list[dict[str, Any]],
    build_meta: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], int]:
    primary_events = {
        (row["pv_id"], row["phenomenon_code"]): row
        for row in events
        if row.get("is_primary_phenomenon") == "True"
    }
    samples_payload: list[dict[str, Any]] = []
    audio_receipts: list[dict[str, Any]] = []
    total_audio_bytes = 0
    for ordinal, sample in enumerate(selected, 1):
        pv_id = sample["pv_id"]
        code = sample["primary_phenomenon_code"]
        event = primary_events.get((pv_id, code))
        if not event:
            raise RuntimeError(f"primary event missing: {pv_id}|{code}")
        package = packages.get(pv_id)
        if not package:
            raise RuntimeError(f"package missing: {pv_id}")
        target_path = package / "target.wav"
        context_path = package / "context_pm2.wav"
        target_uri, target_bytes = data_uri(target_path)
        context_uri, context_bytes = data_uri(context_path)
        total_audio_bytes += target_bytes + context_bytes
        display = target_display(sample, hia_links)
        samples_payload.append(
            {
                "ordinal": ordinal,
                "pv_id": pv_id,
                "review_event_id": event["review_event_id"],
                "phenomenon_code": code,
                "phenomenon_label": sample["primary_phenomenon_label"],
                "priority_tier": "core" if code in CORE_CODES else "exploratory",
                "pv_query_id": event["pv_query_ids_json"],
                "environment_scope": sample["environment_scope"],
                "year": int(sample["year"]),
                "utt_id": sample["utt_id"],
                "occurrence_ref": sample["physical_occurrence_ref"],
                "active_form": sample["active_form"],
                "phenomenon_memberships_json": sample[
                    "phenomenon_memberships_json"
                ],
                "target_display": display,
                "target_display_status": "visible_structured_card",
                "morph_display_status": display["status"],
                "dialogue_status": dialogue_statuses[pv_id],
                "target_metadata": target_metadata.get(pv_id, {}),
                "context_pm2": context_rows_for_display(package / "context.csv"),
                "target_audio": target_uri,
                "context_audio": context_uri,
            }
        )
        audio_receipts.append(
            {
                "pv_id": pv_id,
                "review_event_id": event["review_event_id"],
                "phenomenon_code": code,
                "year": int(sample["year"]),
                "utt_id": sample["utt_id"],
                "target_wav_bytes": target_bytes,
                "target_wav_sha256": sha256_file(target_path),
                "context_wav_bytes": context_bytes,
                "context_wav_sha256": sha256_file(context_path),
            }
        )
    document = HTML_TEMPLATE
    replacements = {
        "__SAMPLES__": json_for_script(samples_payload),
        "__DIALOGUES__": json_for_script(dialogues),
        "__BASE_HISTORY__": json_for_script(base_history),
        "__LITERATURE__": json_for_script(literature),
        "__BUILD_META__": json_for_script(build_meta),
    }
    for token, value in replacements.items():
        document = document.replace(token, value)
    if any(token in document for token in replacements):
        raise RuntimeError("HTML placeholder replacement incomplete")
    return document, audio_receipts, total_audio_bytes


def build(
    *,
    run_root: Path,
    ipad_dir: Path,
    user_jsonl: Path,
    reference_jsonl: Path,
    design_path: Path,
    config_path: Path,
    morph_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    run_root = run_root.resolve(strict=True)
    ipad_dir = ipad_dir.resolve(strict=True)
    user_jsonl = user_jsonl.resolve(strict=True)
    reference_jsonl = reference_jsonl.resolve(strict=True)
    design_path = design_path.resolve(strict=True)
    config_path = config_path.resolve(strict=True)
    morph_root = morph_root.resolve(strict=True)
    output_dir = output_dir.resolve()
    approved_outputs = (PROJECT_ROOT / "outputs" / "pilots").resolve(strict=True)
    if output_dir.parent != approved_outputs:
        raise RuntimeError(f"v2 output must be a direct pilots derivative: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    if partial.exists():
        raise FileExistsError(f"existing partial output is preserved: {partial}")
    design_text = design_path.read_text(encoding="utf-8")
    for required in (
        "설계 승인 — 구현 GO 대기",
        "항목 4 승인",
        "pv_seven_phenomena_reviewer_v2_20260822",
    ):
        if required not in design_text:
            raise RuntimeError(f"approved design marker missing: {required}")

    source_manifest_path = run_root / "PV_MANIFEST.json"
    source_audit_path = run_root / "audit" / "PV_AUDIT.json"
    source_manifest = load_json(source_manifest_path)
    source_audit = load_json(source_audit_path)
    if source_manifest.get("status") != "passed_listening_may_begin":
        raise RuntimeError("source PV run is not passed")
    if source_audit.get("passed") is not True:
        raise RuntimeError("source PV audit is not passed")

    config = load_json(config_path)
    row_cap = int(config["safety"]["max_rows_scanned_per_table_year"])
    if row_cap != 200000 or config["safety"].get("automatic_scan_cap_increase") is not False:
        raise RuntimeError("approved 200000-row cap contract changed")
    samples_all = read_csv(run_root / "samples" / "PV_SAMPLES.csv")
    selected = pick_balanced_samples(samples_all)
    if {int(row["year"]) for row in selected} != ENDPOINT_YEARS:
        raise RuntimeError("selected years are not the approved 2020/2025 endpoints")
    events = read_csv(run_root / "samples" / "PV_REVIEW_EVENTS.csv")
    packages = package_map(run_root / "bundle")
    event_ids = {
        row["review_event_id"]
        for row in events
        if row.get("is_primary_phenomenon") == "True"
        and row["pv_id"] in {sample["pv_id"] for sample in selected}
    }
    user_bytes, user_rows = read_jsonl_bytes(user_jsonl)
    user_summary = validate_user_rows(user_rows, event_ids)
    if user_summary["rows"] != 15 or user_summary["unique_review_events"] != 14:
        raise RuntimeError(f"approved user JSONL contract changed: {user_summary}")

    dialogues, target_meta, dialogue_statuses, dialogue_receipts = scan_dialogue_text(
        selected=selected,
        morph_root=morph_root,
        row_cap=row_cap,
    )
    hia_links, hia_receipts = scan_hia_morph_links(
        selected=selected,
        morph_root=morph_root,
        row_cap=row_cap,
    )
    literature, literature_summary = load_literature(reference_jsonl)
    build_meta = {
        "schema_version": "pv_reviewer_v2_build_meta.v1",
        "imported_source_path": str(user_jsonl),
        "imported_source_sha256": hashlib.sha256(user_bytes).hexdigest(),
        "base_possible_duplicate_rows": user_summary["possible_duplicate_rows"],
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "source_audit_sha256": sha256_file(source_audit_path),
        "design_sha256": sha256_file(design_path),
    }
    document, audio_receipts, audio_bytes = build_html(
        selected=selected,
        events=events,
        packages=packages,
        dialogues=dialogues,
        target_metadata=target_meta,
        dialogue_statuses=dialogue_statuses,
        hia_links=hia_links,
        base_history=user_rows,
        literature=literature,
        build_meta=build_meta,
    )
    dialogue_text = dialogue_jsonl(dialogues)

    partial.mkdir(parents=True)
    html_path = partial / HTML_NAME
    imported_path = partial / IMPORTED_NAME
    dialogue_path = partial / DIALOGUE_NAME
    write_text_atomic(html_path, document)
    write_bytes_atomic(imported_path, user_bytes)
    write_text_atomic(dialogue_path, dialogue_text)
    build_receipt = {
        "schema_version": "pv_reviewer_v2_build.v1",
        "status": "built_pending_independent_audit",
        "recorded_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "approval": {
            "design_path": str(design_path),
            "design_sha256": sha256_file(design_path),
            "user_go_date": "2026-08-22",
            "derivative_root_approved": True,
        },
        "source": {
            "run_root": str(run_root),
            "manifest_sha256": sha256_file(source_manifest_path),
            "audit_sha256": sha256_file(source_audit_path),
            "audit_passed": True,
            "ipad_dir": str(ipad_dir),
            "ipad_html_sha256": sha256_file(ipad_dir / "PV_IPAD_BALANCED14_20260820.html"),
            "user_jsonl_path": str(user_jsonl),
            "user_jsonl_bytes": len(user_bytes),
            "user_jsonl_sha256": hashlib.sha256(user_bytes).hexdigest(),
            "reference_jsonl_path": str(reference_jsonl),
            "reference_jsonl_sha256": sha256_file(reference_jsonl),
        },
        "selection": {
            "samples": 14,
            "unique_sessions": len({row["session_id"] for row in selected}),
            "phenomenon_order": PHENOMENON_ORDER,
            "years": sorted(ENDPOINT_YEARS),
            "records": audio_receipts,
        },
        "user_history": user_summary,
        "dialogue": {
            "statuses": dialogue_statuses,
            "rows_by_pv_id": {pv_id: len(rows) for pv_id, rows in dialogues.items()},
            "total_rows": sum(len(rows) for rows in dialogues.values()),
            "sources": dialogue_receipts,
        },
        "morph_display": {
            "direct_from_existing_match_evidence": sum(
                row["matched_table"] != "orth_eojeol_tokens" for row in selected
            ),
            "hia_requested": sum(
                row["matched_table"] == "orth_eojeol_tokens" for row in selected
            ),
            "hia_links": hia_links,
            "sources": hia_receipts,
        },
        "literature": literature_summary,
        "output": {
            "html": {
                "path": HTML_NAME,
                "bytes": html_path.stat().st_size,
                "sha256": sha256_file(html_path),
                "embedded_audio_elements": 28,
                "embedded_source_wav_bytes": audio_bytes,
            },
            "imported_jsonl": {
                "path": IMPORTED_NAME,
                "bytes": imported_path.stat().st_size,
                "sha256": sha256_file(imported_path),
            },
            "dialogue_jsonl": {
                "path": DIALOGUE_NAME,
                "bytes": dialogue_path.stat().st_size,
                "sha256": sha256_file(dialogue_path),
            },
        },
        "safety": {
            "source_files_modified": False,
            "audio_transcoded": False,
            "whole_dialogue_audio_embedded": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "mfa_run": False,
            "koina_run": False,
            "wav2vec2_run": False,
            "existing_output_overwritten": False,
            "scan_cap_per_table_year": row_cap,
            "automatic_scan_cap_increase": False,
        },
    }
    build_path = partial / BUILD_NAME
    write_text_atomic(
        build_path,
        json.dumps(build_receipt, ensure_ascii=False, indent=2) + "\n",
    )
    os.replace(partial, output_dir)
    return build_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--ipad-dir", type=Path, default=DEFAULT_IPAD_DIR)
    parser.add_argument("--user-jsonl", type=Path, default=DEFAULT_USER_JSONL)
    parser.add_argument("--reference-jsonl", type=Path, default=DEFAULT_REFERENCE_JSONL)
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--morph-root", type=Path, default=DEFAULT_MORPH_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    try:
        receipt = build(
            run_root=args.run_root,
            ipad_dir=args.ipad_dir,
            user_jsonl=args.user_jsonl,
            reference_jsonl=args.reference_jsonl,
            design_path=args.design,
            config_path=args.config,
            morph_root=args.morph_root,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
