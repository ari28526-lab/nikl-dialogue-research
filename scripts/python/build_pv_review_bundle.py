"""Materialize the static PV-A listening bundle and exploratory review forms.

Source utterance clips are copied read-only and serialized for convenience.
The stitched file is explicitly not a reconstruction of original overlapping
session time.  Every context slot receives a stitch status; nothing is silently
dropped.  Browser notes are exploratory and exported separately from G7.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
import sys
import wave
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from pipeline_common import sha256_file
from pv_preview_common import (
    DEFAULT_CONFIG,
    PROJECT_ROOT,
    atomic_write_csv,
    atomic_write_json,
    load_json,
    manifest_file_record,
    now_iso,
    promote_directory,
    require_under,
    validate_config,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


REVIEW_FIELDS = [
    "review_event_id",
    "pv_id",
    "phenomenon_code",
    "pv_query_id",
    "environment_scope",
    "year",
    "utt_id",
    "occurrence_ref",
    "listened",
    "env_impression",
    "realization_impression",
    "audio_quality_note",
    "context_sufficient",
    "missing_info_note",
    "schema_field_suggestion",
    "tool_note",
    "reviewer",
    "reviewed_at",
    "record_role",
]

STITCH_FIELDS = [
    "order",
    "relation",
    "slot_status",
    "utt_id",
    "speaker_id",
    "operational_speaker_run_id",
    "speaker_run_unit_count",
    "target_position_in_speaker_run",
    "derived_turn_id",
    "speaker_change_before",
    "speaker_change_after",
    "source_note_overlap_flag",
    "timestamp_overlap_raw",
    "source_overlap_flag",
    "source_time_gap_before_seconds",
    "source_time_gap_semantics",
    "source_wav",
    "stitch_status",
    "stitch_reason",
    "stitched_start_seconds",
    "stitched_end_seconds",
    "source_clip_start_seconds",
    "source_clip_end_seconds",
    "gap_after_seconds",
    "gap_after_is_synthetic",
    "source_time_rule",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    if not rows:
        raise RuntimeError(f"empty input CSV: {path}")
    return fields, rows


def write_simple_csv(path: Path, fields: list[str], rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def copy_if_present(source_text: str, destination: Path) -> tuple[str, str]:
    source = Path(source_text) if source_text.strip() else None
    if source is None or not source.is_file():
        return "missing", "source path absent or not a file"
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copy2(source, destination)
    return "copied", "read-only source copy"


def stitch_context(
    rows: list[dict[str, str]], output_wav: Path, manifest_path: Path, gap_seconds: float
) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []
    params: tuple[int, int, int, str] | None = None
    for order, row in enumerate(rows, 1):
        record: dict[str, Any] = {
            "order": order,
            "relation": row["relation"],
            "slot_status": row["slot_status"],
            "utt_id": row.get("utt_id", ""),
            "speaker_id": row.get("speaker_id", ""),
            "operational_speaker_run_id": row.get(
                "operational_speaker_run_id", ""
            ),
            "speaker_run_unit_count": row.get("speaker_run_unit_count", ""),
            "target_position_in_speaker_run": row.get(
                "target_position_in_speaker_run", ""
            ),
            "derived_turn_id": row.get("derived_turn_id", ""),
            "speaker_change_before": row.get("speaker_change_before", ""),
            "speaker_change_after": row.get("speaker_change_after", ""),
            "source_note_overlap_flag": row.get(
                "source_note_overlap_flag", ""
            ),
            "timestamp_overlap_raw": row.get("timestamp_overlap_raw", ""),
            "source_overlap_flag": row.get("source_overlap_flag", ""),
            "source_time_gap_before_seconds": row.get(
                "source_time_gap_before_seconds", ""
            ),
            "source_time_gap_semantics": row.get(
                "source_time_gap_semantics", ""
            ),
            "source_wav": row.get("wav_path", ""),
            "stitch_status": "",
            "stitch_reason": "",
            "stitched_start_seconds": "",
            "stitched_end_seconds": "",
            "source_clip_start_seconds": "",
            "source_clip_end_seconds": "",
            "gap_after_seconds": "0",
            "gap_after_is_synthetic": "False",
            "source_time_rule": (
                "individual_utterance_clip_serialized_not_original_session_time; "
                "source_timestamp_gap_never_used_as_pause"
            ),
        }
        if row["slot_status"] != "present":
            record["stitch_status"] = "not_materialized_missing_context_slot"
            record["stitch_reason"] = row["slot_status"]
            manifest.append(record)
            continue
        source = Path(row.get("wav_path", ""))
        if not source.is_file():
            record["stitch_status"] = "not_materialized_wav_missing"
            record["stitch_reason"] = "wav_status=" + row.get("wav_status", "")
            manifest.append(record)
            continue
        try:
            with wave.open(str(source), "rb") as wav_file:
                current = (
                    wav_file.getnchannels(),
                    wav_file.getsampwidth(),
                    wav_file.getframerate(),
                    wav_file.getcomptype(),
                )
                if params is None:
                    params = current
                if current != params:
                    record["stitch_status"] = "not_materialized_format_mismatch"
                    record["stitch_reason"] = f"expected={params} actual={current}"
                    manifest.append(record)
                    continue
                frame_count = wav_file.getnframes()
                data = wav_file.readframes(frame_count)
        except (wave.Error, OSError) as exc:
            record["stitch_status"] = "not_materialized_wav_read_error"
            record["stitch_reason"] = f"{type(exc).__name__}: {exc}"
            manifest.append(record)
            continue
        clips.append(
            {
                "data": data,
                "frames": frame_count,
                "manifest_index": len(manifest),
            }
        )
        record["stitch_status"] = "materialized_serialized_clip"
        record["source_clip_start_seconds"] = "0"
        record["source_clip_end_seconds"] = f"{frame_count / params[2]:.9f}"
        manifest.append(record)
    if not clips or params is None:
        raise RuntimeError("no context WAV clip could be materialized")
    channels, sample_width, frame_rate, compression = params
    if compression != "NONE":
        raise RuntimeError(f"compressed WAV is unsupported for stitch: {compression}")
    gap_frames = round(gap_seconds * frame_rate)
    zero_gap = bytes(gap_frames * channels * sample_width)
    cursor_frames = 0
    with output_wav.open("xb") as raw_output:
        with wave.open(raw_output, "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(sample_width)
            output.setframerate(frame_rate)
            for clip_index, clip in enumerate(clips):
                start = cursor_frames / frame_rate
                output.writeframesraw(clip["data"])
                cursor_frames += int(clip["frames"])
                end = cursor_frames / frame_rate
                record = manifest[clip["manifest_index"]]
                record["stitched_start_seconds"] = f"{start:.9f}"
                record["stitched_end_seconds"] = f"{end:.9f}"
                if clip_index < len(clips) - 1:
                    output.writeframesraw(zero_gap)
                    cursor_frames += gap_frames
                    record["gap_after_seconds"] = f"{gap_frames / frame_rate:.9f}"
                    record["gap_after_is_synthetic"] = "True"
            output.writeframes(b"")
    write_simple_csv(manifest_path, STITCH_FIELDS, manifest)
    return manifest


def review_rows(
    events: list[dict[str, str]], samples_by_id: Mapping[str, dict[str, str]]
) -> list[dict[str, str]]:
    rows = []
    for event in events:
        sample = samples_by_id[event["pv_id"]]
        rows.append(
            {
                "review_event_id": event["review_event_id"],
                "pv_id": event["pv_id"],
                "phenomenon_code": event["phenomenon_code"],
                "pv_query_id": event["pv_query_ids_json"],
                "environment_scope": event["environment_scope"],
                "year": event["year"],
                "utt_id": event["utt_id"],
                "occurrence_ref": event["physical_occurrence_ref"],
                "listened": "",
                "env_impression": "",
                "realization_impression": "",
                "audio_quality_note": "",
                "context_sufficient": "",
                "missing_info_note": "",
                "schema_field_suggestion": "",
                "tool_note": "",
                "reviewer": "",
                "reviewed_at": "",
                "record_role": "exploratory_pv_only_not_formal_realization_ledger",
            }
        )
    return rows


def render_html(
    *,
    samples: list[dict[str, str]],
    events: list[dict[str, str]],
    contexts: list[dict[str, str]],
    package_dirs: Mapping[str, str],
) -> str:
    contexts_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    events_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in contexts:
        contexts_by_id[row["pv_id"]].append(row)
    for row in events:
        events_by_id[row["pv_id"]].append(row)
    cards = []
    event_metadata: dict[str, dict[str, str]] = {}
    for sample in samples:
        pv_id = sample["pv_id"]
        package = package_dirs[pv_id]
        target_exists = Path(sample["wav_path"]).is_file()
        context_table = []
        for row in contexts_by_id[pv_id]:
            context_table.append(
                "<tr>"
                f"<td>{html.escape(row['relation'])}</td>"
                f"<td>{html.escape(row.get('speaker_id', ''))}</td>"
                f"<td>{html.escape(row.get('operational_speaker_run_id', ''))} "
                f"({html.escape(row.get('target_position_in_speaker_run', ''))}/"
                f"{html.escape(row.get('speaker_run_unit_count', ''))})</td>"
                f"<td>{html.escape(row.get('speaker_change_before', ''))}/"
                f"{html.escape(row.get('speaker_change_after', ''))}</td>"
                f"<td>{html.escape(row.get('source_note_overlap_flag', ''))}/"
                f"{html.escape(row.get('timestamp_overlap_raw', ''))}</td>"
                f"<td>{html.escape(row.get('source_time_gap_before_seconds', ''))}<br>"
                f"<small>{html.escape(row.get('source_time_gap_semantics', ''))}</small></td>"
                f"<td>{html.escape(row.get('form', ''))}</td>"
                f"<td>{html.escape(row['slot_status'])}</td>"
                "</tr>"
            )
        forms = []
        for event in events_by_id[pv_id]:
            event_id = event["review_event_id"]
            event_metadata[event_id] = {
                "review_event_id": event_id,
                "pv_id": pv_id,
                "phenomenon_code": event["phenomenon_code"],
                "pv_query_id": event["pv_query_ids_json"],
                "environment_scope": event["environment_scope"],
                "year": event["year"],
                "utt_id": event["utt_id"],
                "occurrence_ref": event["physical_occurrence_ref"],
                "record_role": "exploratory_pv_only_not_formal_realization_ledger",
            }
            primary = event["is_primary_phenomenon"].lower() == "true"
            forms.append(
                f'<form class="review" data-event="{html.escape(event_id)}">'
                f"<h4>{html.escape(event['phenomenon_label'])} "
                f"<small>{'primary' if primary else 'shared membership'}</small></h4>"
                '<label><input type="checkbox" name="listened"> 청취함</label>'
                '<label>환경 인상<select name="env_impression"><option value=""></option>'
                '<option value="env_ok">환경 적절</option><option value="env_wrong">환경 부적절</option>'
                '<option value="unsure">불확실</option></select></label>'
                '<label>실현 인상(자유 기술)<textarea name="realization_impression"></textarea></label>'
                '<label>음질 메모<textarea name="audio_quality_note"></textarea></label>'
                '<label>문맥 충분성<select name="context_sufficient"><option value=""></option>'
                '<option value="yes">충분</option><option value="need_more_before">앞 문맥 필요</option>'
                '<option value="need_more_after">뒤 문맥 필요</option><option value="need_other_file">다른 파일 필요</option>'
                '</select></label>'
                '<label>빠진 정보<textarea name="missing_info_note"></textarea></label>'
                '<label>스키마 열 제안<textarea name="schema_field_suggestion"></textarea></label>'
                '<label>도구 메모<textarea name="tool_note"></textarea></label>'
                '<label>검토자<input name="reviewer"></label>'
                '<button type="button" class="save">새 revision 저장</button>'
                '<span class="saved" aria-live="polite"></span>'
                "</form>"
            )
        target_audio = (
            f'<audio controls preload="none" src="{html.escape(package)}/target.wav"></audio>'
            if target_exists
            else '<p class="warn">target.wav 없음—manifest 상태를 확인하세요.</p>'
        )
        cards.append(
            f'<section class="card" id="{html.escape(pv_id)}">'
            f"<h2>{html.escape(pv_id)} · {html.escape(sample['primary_phenomenon_label'])} · "
            f"{html.escape(sample['year'])}</h2>"
            f"<p><code>{html.escape(sample['utt_id'])}</code> · "
            f"{html.escape(sample['environment_scope'])}</p>"
            f"<p class=\"utterance\">{html.escape(sample['active_form'])}</p>"
            "<h3>대상 발화</h3>" + target_audio +
            "<h3>±2 직렬화 미리듣기</h3>"
            f'<audio controls preload="none" src="{html.escape(package)}/context_pm2.wav"></audio>'
            '<p class="notice">발화 단위 클립을 합성 0.05초 간격으로 직렬화한 편의 파일입니다. '
            "이 간격은 원 대화의 휴지가 아니며, 원 세션 시간이나 겹침을 복원하지 않습니다.</p>"
            "<table><thead><tr><th>관계</th><th>화자</th><th>조작적 화자 묶음(위치/수)</th>"
            "<th>교대(앞/뒤)</th><th>겹침(주석/시간값)</th><th>원시 시간차(휴지 아님)</th>"
            "<th>전사</th><th>상태</th></tr></thead><tbody>"
            + "".join(context_table)
            + "</tbody></table>"
            + "".join(forms)
            + "</section>"
        )
    metadata_json = json.dumps(event_metadata, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PV-A 일곱 현상 미리듣기</title>
<style>
body{{font-family:system-ui,'Malgun Gothic',sans-serif;margin:0;background:#f4f5f7;color:#17202a}}
header{{position:sticky;top:0;background:#14213d;color:white;padding:1rem 1.4rem;z-index:3}}
main{{max-width:1100px;margin:auto;padding:1rem}}.card{{background:white;border:1px solid #d7dce2;border-radius:12px;padding:1.1rem;margin:1rem 0;box-shadow:0 2px 8px #0001}}
.utterance{{font-size:1.15rem;background:#f7f2e8;padding:.8rem;border-radius:8px}}audio{{width:100%;margin:.3rem 0 1rem}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}th,td{{border:1px solid #ccd2d9;padding:.45rem;text-align:left}}th{{background:#edf1f5}}
.review{{border-top:2px solid #d7dce2;margin-top:1.2rem;padding-top:.8rem;display:grid;gap:.6rem}}label{{display:grid;gap:.25rem}}textarea{{min-height:4rem}}select,input,textarea,button{{font:inherit;padding:.45rem}}
.notice{{color:#7a4b00;background:#fff5d6;padding:.6rem}}.warn{{color:#9b1c1c}}small{{font-weight:normal;color:#59636e}}.saved{{color:#146c43;margin-left:.5rem}}
</style></head><body>
<header><h1>PV-A 일곱 현상 미리듣기</h1><p>탐색 전용 · 자동 실현 판정 없음 · 저장 revision은 JSONL로 내보내세요.</p>
<button id="export">저장 revision JSONL 내보내기</button></header><main>{''.join(cards)}</main>
<script>
'use strict';
const META={metadata_json}; const KEY='pv_preview_history_v1';
function history(){{try{{return JSON.parse(localStorage.getItem(KEY)||'[]')}}catch(e){{return []}}}}
document.querySelectorAll('.save').forEach(btn=>btn.addEventListener('click',()=>{{
 const form=btn.closest('form'); const id=form.dataset.event; const data={{...META[id]}};
 form.querySelectorAll('[name]').forEach(el=>data[el.name]=(el.type==='checkbox'?el.checked:el.value));
 data.reviewed_at=new Date().toISOString(); const all=history(); all.push(data); localStorage.setItem(KEY,JSON.stringify(all));
 form.querySelector('.saved').textContent=`저장됨 (revision ${{all.filter(x=>x.review_event_id===id).length}})`;
}}));
document.getElementById('export').addEventListener('click',()=>{{
 const body=history().map(x=>JSON.stringify(x)).join('\n')+'\n';
 const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([body],{{type:'application/jsonl'}}));
 a.download='PV_REVIEW_EXPORT.jsonl'; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}});
</script></body></html>"""


def build(
    *,
    config_path: Path,
    samples_path: Path,
    events_path: Path,
    context_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    require_under(output_dir, PROJECT_ROOT / "outputs" / "pilots")
    if output_dir.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    if partial.exists():
        raise FileExistsError(f"existing partial output is preserved: {partial}")
    config = load_json(config_path)
    validate_config(config)
    sample_fields, samples = read_csv(samples_path)
    _, events = read_csv(events_path)
    context_fields, contexts = read_csv(context_path)
    samples_by_id = {row["pv_id"]: row for row in samples}
    if len(samples_by_id) != len(samples):
        raise RuntimeError("duplicate pv_id")
    events_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    contexts_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        events_by_id[event["pv_id"]].append(event)
    for row in contexts:
        contexts_by_id[row["pv_id"]].append(row)
    unknown_event_ids = set(events_by_id) - set(samples_by_id)
    unknown_context_ids = set(contexts_by_id) - set(samples_by_id)
    if unknown_event_ids or unknown_context_ids:
        raise RuntimeError(
            "event/context pv_id absent from samples: "
            f"events={sorted(unknown_event_ids)} contexts={sorted(unknown_context_ids)}"
        )
    if any(not events_by_id[pv_id] for pv_id in samples_by_id):
        raise RuntimeError("every sample must have at least one review event")
    if any(len(contexts_by_id[pv_id]) != 5 for pv_id in samples_by_id):
        raise RuntimeError("every sample must have exactly five context rows")
    expected_relations = ["before_2", "before_1", "target", "after_1", "after_2"]
    if any(
        [row["relation"] for row in contexts_by_id[pv_id]] != expected_relations
        for pv_id in samples_by_id
    ):
        raise RuntimeError("context rows must preserve the approved ±2 relation order")
    partial.mkdir(parents=True)
    package_dirs: dict[str, str] = {}
    package_receipts: list[dict[str, Any]] = []
    gap = float(config["context_contract"]["stitched_gap_seconds"])
    for index, sample in enumerate(samples, 1):
        pv_id = sample["pv_id"]
        safe_utt = sample["utt_id"].replace(".", "_")
        package_name = (
            f"{index:03d}__{sample['primary_phenomenon_code']}__"
            f"{sample['year']}__{safe_utt}"
        )
        package_dirs[pv_id] = package_name
        package = partial / package_name
        package.mkdir()
        target_status, target_note = copy_if_present(
            sample.get("wav_path", ""), package / "target.wav"
        )
        tg_status, tg_note = copy_if_present(
            sample.get("active_textgrid_path", ""), package / "target_source.TextGrid"
        )
        write_simple_csv(package / "row.csv", sample_fields, [sample])
        write_simple_csv(
            package / "events.csv",
            list(events_by_id[pv_id][0]),
            events_by_id[pv_id],
        )
        package_context = contexts_by_id[pv_id]
        write_simple_csv(package / "context.csv", context_fields, package_context)
        stitch_rows = stitch_context(
            package_context,
            package / "context_pm2.wav",
            package / "context_stitch_manifest.csv",
            gap,
        )
        package_manifest = {
            "schema_version": "pv_review_package.v1",
            "pv_id": pv_id,
            "recorded_at": now_iso(),
            "target_wav_status": target_status,
            "target_wav_note": target_note,
            "target_textgrid_status": tg_status,
            "target_textgrid_note": tg_note,
            "context_slots": len(package_context),
            "context_materialized_clips": sum(
                row["stitch_status"] == "materialized_serialized_clip"
                for row in stitch_rows
            ),
            "source_time_rule": (
                "individual utterance clips serialized; synthetic gaps are not "
                "source pauses; overlap not reconstructed"
            ),
            "synthetic_gap_seconds": gap,
            "files": [
                manifest_file_record(path, package)
                for path in sorted(package.iterdir())
                if path.is_file()
            ],
            "safety": {
                "source_modified": False,
                "realization_judgement_performed": False,
                "derived_turn_is_gold": False,
                "source_timestamp_gap_interpreted_as_pause": False,
                "synthetic_gap_claimed_as_source_silence": False,
            },
        }
        atomic_write_json(package / "PACKAGE_MANIFEST.json", package_manifest)
        package_receipts.append(package_manifest)
    review = review_rows(events, samples_by_id)
    write_simple_csv(partial / "REVIEW.csv", REVIEW_FIELDS, review)
    (partial / "INDEX.html").write_text(
        render_html(
            samples=samples,
            events=events,
            contexts=contexts,
            package_dirs=package_dirs,
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema_version": "pv_review_bundle_build.v1",
        "status": "completed_static_bundle_exploratory_review_only",
        "recorded_at": now_iso(),
        "config_sha256": sha256_file(config_path),
        "inputs": {
            "samples_sha256": sha256_file(samples_path),
            "events_sha256": sha256_file(events_path),
            "context_sha256": sha256_file(context_path),
        },
        "counts": {
            "physical_packages": len(samples),
            "logical_review_events": len(events),
            "review_template_rows": len(review),
            "context_rows": len(contexts),
            "target_wav_missing": sum(
                item["target_wav_status"] != "copied" for item in package_receipts
            ),
            "target_textgrid_missing": sum(
                item["target_textgrid_status"] != "copied" for item in package_receipts
            ),
        },
        "outputs": {
            "index_html": "INDEX.html",
            "review_csv": "REVIEW.csv",
            "sha256_manifest": "SHA256_MANIFEST.csv",
            "package_dirs": package_dirs,
        },
        "safety": {
            "browser_storage_is_convenience_only": True,
            "jsonl_export_is_exploratory_not_g7": True,
            "source_clips_serialized_not_session_reconstructed": True,
            "synthetic_gap_claimed_as_source_silence": False,
            "source_timestamp_gap_interpreted_as_pause": False,
            "source_assets_modified": False,
            "realization_judgement_performed": False,
            "mfa_run": False,
            "koina_run": False,
            "wav2vec2_run": False,
        },
    }
    atomic_write_json(partial / "PV_BUNDLE_BUILD.json", manifest)
    sha_rows = [
        manifest_file_record(path, partial)
        for path in sorted(partial.rglob("*"))
        if path.is_file() and path.name != "SHA256_MANIFEST.csv"
    ]
    atomic_write_csv(
        partial / "SHA256_MANIFEST.csv",
        ["path", "bytes", "sha256"],
        sha_rows,
    )
    promote_directory(partial, output_dir)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(
            config_path=args.config.resolve(),
            samples_path=args.samples.resolve(),
            events_path=args.events.resolve(),
            context_path=args.context.resolve(),
            output_dir=args.output_dir.resolve(),
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
