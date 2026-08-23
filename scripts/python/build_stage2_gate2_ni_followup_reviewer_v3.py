"""Build the approved Stage 2 Gate 2 NI follow-up reviewer v3.

The builder derives only from the audited PV reviewer v2.1 and the 14 matching
PV-A package copies.  It embeds a read-only TextGrid projection and a small
waveform peak summary.  It never edits source audio/TextGrid files, judges
realization, creates formal manual tasks, or writes a formal ledger.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "pv_seven_phenomena_reviewer_v2_1_20260822"
)
DEFAULT_PV_ROOT = (
    PROJECT_ROOT / "outputs" / "pilots" / "pv_seven_phenomena_20260819"
)
DEFAULT_PLAN = (
    PROJECT_ROOT
    / "docs"
    / "decisions"
    / "PLAN_stage2_gate2_NI_followup_textgrid_reviewer_20260823.md"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "stage2_gate2_ni_followup_reviewer_v3_20260823"
)

SOURCE_HTML = "PV_REVIEWER_V2_1.html"
SOURCE_BUILD = "PV_REVIEWER_V2_1_BUILD.json"
SOURCE_IMPORTED = "PV_REVIEWER_V2_1_IMPORTED_BASE.jsonl"
SOURCE_DIALOGUES = "PV_REVIEWER_V2_1_DIALOGUES.jsonl"
SOURCE_AUDIT = Path("audit") / "PV_REVIEWER_V2_1_AUDIT.json"
SOURCE_MANIFEST = "PV_REVIEWER_V2_1_SHA256_MANIFEST.csv"

HTML_NAME = "STAGE2_GATE2_NI_REVIEWER_V3.html"
BUILD_NAME = "STAGE2_GATE2_NI_REVIEWER_V3_BUILD.json"
IMPORTED_NAME = "STAGE2_GATE2_NI_REVIEWER_V3_IMPORTED_BASE.jsonl"
DIALOGUE_NAME = "STAGE2_GATE2_NI_REVIEWER_V3_DIALOGUES.jsonl"

EXPECTED_SHA256 = {
    "source_html": "4ac9edd77fd8889aaeb73b8c15afc6c2ee1a3c0eb5cca1e4d2b24e862da98a7e",
    "source_build": "3db5b74367a43a2f79babfdc67f6700e0e5a06105da112321823dcb631955a7c",
    "source_audit": "3a47c2e3509dae16852ff90dcf295ddc602c89f6773e0198a9e9e700b242fc78",
    "samples_csv": "31bea32b1cd44f5e9e77baa84259a6fa3566a192f866a5b006371700fa1fe93f",
    "pv_manifest": "acb8772e1f4ab8860ebc0631517f616eeb2b2e0f5eeb8e1d890abf462248ad51",
    "zero_drop_dictionary": "f87a5684d4c7f21752ad9c4c023c28264471436eae9885a93cbd7a34e601c173",
    "additional_information_schema": "b1992e21f9431e5d066e396264eb61b89dff652d950f4e6fa7a6bb9d1b14c3f3",
    "approved_plan": "22ec8d8ca8ba286f93bcf027b25e97bf9a312bb53f73acb9f21e24833ced1bd9",
}

EXPECTED_TIERS = [
    "words",
    "phones_mfa",
    "phoneme_r_auto",
    "utterance",
    "utterance_orth_r",
    "morph_analysis_utt",
]
EXPECTED_NI_IDS = ["PV0015", "PV0163"]
WAVEFORM_BINS = 320


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_pinned_file(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    path = path.resolve(strict=True)
    measured = sha256_file(path)
    if measured != expected_sha256:
        raise RuntimeError(
            f"{label} SHA-256 differs: expected={expected_sha256}, measured={measured}"
        )
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": measured}


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


def replace_once(document: str, old: str, new: str, label: str) -> str:
    count = document.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source fragment, measured {count}")
    return document.replace(old, new, 1)


def json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def extract_json_constant(document: str, name: str, next_name: str) -> Any:
    match = re.search(
        rf"const {re.escape(name)}=(.*?);\nconst {re.escape(next_name)}=",
        document,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"HTML JSON constant missing: {name}")
    return json.loads(match.group(1))


def _praat_unquote(value: str) -> str:
    return value.replace('""', '"')


def parse_long_textgrid(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    if 'File type = "ooTextFile"' not in text or 'Object class = "TextGrid"' not in text:
        raise ValueError("unsupported or invalid TextGrid header")
    xmax_match = re.search(r"(?m)^xmax = ([+\-0-9.eE]+)\s*$", text)
    if not xmax_match:
        raise ValueError("TextGrid xmax missing")
    global_xmax = float(xmax_match.group(1))
    tier_matches = list(re.finditer(r"(?m)^    item \[(\d+)\]:\s*$", text))
    if not tier_matches:
        raise ValueError("TextGrid tiers missing")
    tiers: list[dict[str, Any]] = []
    for index, match in enumerate(tier_matches):
        end = tier_matches[index + 1].start() if index + 1 < len(tier_matches) else len(text)
        block = text[match.end() : end]
        class_match = re.search(r'^        class = "([^"]+)"\s*$', block, re.MULTILINE)
        name_match = re.search(r'^        name = "((?:""|[^"])*)"\s*$', block, re.MULTILINE)
        xmin_match = re.search(r"(?m)^        xmin = ([+\-0-9.eE]+)\s*$", block)
        xmax_tier_match = re.search(r"(?m)^        xmax = ([+\-0-9.eE]+)\s*$", block)
        if not all((class_match, name_match, xmin_match, xmax_tier_match)):
            raise ValueError(f"TextGrid tier {index + 1} metadata incomplete")
        tier_class = class_match.group(1)
        if tier_class != "IntervalTier":
            raise ValueError(f"unsupported tier class: {tier_class}")
        intervals: list[dict[str, Any]] = []
        pattern = re.compile(
            r"(?ms)^        intervals \[(\d+)\]:\s*\n"
            r"            xmin = ([+\-0-9.eE]+)\s*\n"
            r"            xmax = ([+\-0-9.eE]+)\s*\n"
            r'            text = "((?:""|[^"])*)"\s*$'
        )
        for interval_match in pattern.finditer(block):
            xmin = float(interval_match.group(2))
            xmax = float(interval_match.group(3))
            if xmax < xmin:
                raise ValueError("TextGrid interval has negative duration")
            intervals.append(
                {
                    "index": int(interval_match.group(1)),
                    "xmin": xmin,
                    "xmax": xmax,
                    "text": _praat_unquote(interval_match.group(4)),
                }
            )
        size_match = re.search(r"(?m)^        intervals: size = (\d+)\s*$", block)
        if not size_match or int(size_match.group(1)) != len(intervals):
            raise ValueError(f"TextGrid tier {index + 1} interval count mismatch")
        tiers.append(
            {
                "index": int(match.group(1)),
                "name": _praat_unquote(name_match.group(1)),
                "xmin": float(xmin_match.group(1)),
                "xmax": float(xmax_tier_match.group(1)),
                "intervals": intervals,
            }
        )
    return {"xmin": 0.0, "xmax": global_xmax, "tiers": tiers}


def waveform_peaks(path: Path, bins: int = WAVEFORM_BINS) -> dict[str, Any]:
    if bins < 1:
        raise ValueError("waveform bins must be positive")
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        sample_width = stream.getsampwidth()
        frame_rate = stream.getframerate()
        frame_count = stream.getnframes()
        compression = stream.getcomptype()
        payload = stream.readframes(frame_count)
    if compression != "NONE" or channels < 1 or frame_rate < 1 or frame_count < 1:
        raise ValueError("unsupported or empty WAV")
    if sample_width not in {1, 2, 3, 4}:
        raise ValueError(f"unsupported WAV sample width: {sample_width}")
    frame_width = channels * sample_width
    if len(payload) != frame_count * frame_width:
        raise ValueError("WAV PCM byte count mismatch")
    maximum = float((1 << (sample_width * 8 - 1)) - 1)
    peaks = [0.0] * bins
    for frame_index in range(frame_count):
        offset = frame_index * frame_width
        frame_peak = 0
        for channel in range(channels):
            start = offset + channel * sample_width
            sample = payload[start : start + sample_width]
            if sample_width == 1:
                value = int(sample[0]) - 128
            else:
                value = int.from_bytes(sample, byteorder="little", signed=True)
            frame_peak = max(frame_peak, abs(value))
        bin_index = min(bins - 1, frame_index * bins // frame_count)
        peaks[bin_index] = max(peaks[bin_index], min(1.0, frame_peak / maximum))
    return {
        "bins": bins,
        "peaks": [round(value, 6) for value in peaks],
        "duration_seconds": frame_count / frame_rate,
        "frame_rate": frame_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "frame_count": frame_count,
    }


def read_samples(samples_csv: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with samples_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 180 or len({row["pv_id"] for row in rows}) != 180:
        raise RuntimeError("PV_SAMPLES.csv is not the frozen 180-row unique set")
    return rows, {row["pv_id"]: row for row in rows}


def index_packages(bundle_root: Path) -> tuple[dict[str, dict[str, Any]], int]:
    manifests = sorted(bundle_root.glob("*/PACKAGE_MANIFEST.json"))
    if len(manifests) != 180:
        raise RuntimeError(f"PV-A package manifest count differs: {len(manifests)}")
    result: dict[str, dict[str, Any]] = {}
    for path in manifests:
        value = json.loads(path.read_text(encoding="utf-8"))
        pv_id = str(value.get("pv_id", ""))
        if not pv_id or pv_id in result:
            raise RuntimeError(f"duplicate or missing package pv_id: {pv_id}")
        result[pv_id] = {"manifest_path": path, "manifest": value}
    return result, len(manifests)


def _package_file_entry(package: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    entries = [row for row in package.get("files", []) if row.get("path") == name]
    return entries[0] if len(entries) == 1 else None


def build_asset(
    sample: Mapping[str, Any],
    sample_row: Mapping[str, str],
    package_info: Mapping[str, Any] | None,
) -> dict[str, Any]:
    pv_id = str(sample["pv_id"])
    role = "ni_method_reference" if sample.get("phenomenon_code") == "NI" else "cross_phenomenon_ui_regression_only"
    base: dict[str, Any] = {
        "pv_id": pv_id,
        "gate_method_role": role,
        "textgrid_asset_status": "unavailable",
        "manual_task_status": "not_created",
        "asset_issue_codes": [],
        "target_xmin": float(sample_row["target_xmin"]),
        "target_xmax": float(sample_row["target_xmax"]),
        "timing_status": sample_row["timing_status"],
        "source_textgrid_identifier": None,
        "source_textgrid_sha256": sample_row["active_textgrid_sha256"],
        "source_wav_identifier": None,
        "source_wav_sha256": None,
        "textgrid": None,
        "waveform": None,
    }
    if package_info is None:
        base["asset_issue_codes"] = ["package_manifest_unavailable"]
        return base
    manifest_path = Path(package_info["manifest_path"])
    package = package_info["manifest"]
    textgrid_entry = _package_file_entry(package, "target_source.TextGrid")
    wav_entry = _package_file_entry(package, "target.wav")
    textgrid_path = manifest_path.parent / "target_source.TextGrid"
    wav_path = manifest_path.parent / "target.wav"
    base["source_textgrid_identifier"] = textgrid_path.relative_to(PROJECT_ROOT).as_posix()
    base["source_wav_identifier"] = wav_path.relative_to(PROJECT_ROOT).as_posix()
    if textgrid_entry is None or wav_entry is None or not textgrid_path.is_file() or not wav_path.is_file():
        base["asset_issue_codes"] = ["package_asset_unavailable"]
        return base
    actual_textgrid_sha = sha256_file(textgrid_path)
    actual_wav_sha = sha256_file(wav_path)
    base["source_wav_sha256"] = actual_wav_sha
    mismatches = []
    if actual_textgrid_sha != str(textgrid_entry.get("sha256")):
        mismatches.append("textgrid_package_manifest_sha_mismatch")
    if actual_textgrid_sha != sample_row["active_textgrid_sha256"]:
        mismatches.append("textgrid_active_source_sha_mismatch")
    if actual_wav_sha != str(wav_entry.get("sha256")):
        mismatches.append("wav_package_manifest_sha_mismatch")
    if mismatches:
        base["textgrid_asset_status"] = "blocked"
        base["asset_issue_codes"] = mismatches
        return base
    try:
        textgrid = parse_long_textgrid(textgrid_path)
        tier_names = [tier["name"] for tier in textgrid["tiers"]]
        if tier_names != EXPECTED_TIERS:
            raise ValueError(f"unexpected tier order: {tier_names}")
        if not (0 <= base["target_xmin"] < base["target_xmax"] <= textgrid["xmax"] + 1e-9):
            raise ValueError("target span outside TextGrid duration")
        waveform = waveform_peaks(wav_path)
        if abs(waveform["duration_seconds"] - textgrid["xmax"]) > 0.02:
            raise ValueError("WAV/TextGrid duration mismatch exceeds 0.02 seconds")
    except Exception as exc:
        base["textgrid_asset_status"] = "blocked"
        base["asset_issue_codes"] = [f"asset_projection_failed:{type(exc).__name__}"]
        return base
    base["textgrid_asset_status"] = "available"
    base["textgrid"] = textgrid
    base["waveform"] = waveform
    return base


GATE2_CSS = r"""
.gate-role{background:#e8eef2;color:#29495c}.gate-role.ni{background:#dff2e6;color:#14683a}
.followup-box{border:2px solid #6a5a96;border-radius:11px;padding:13px;background:#f4f0fa}.followup-box legend{font-weight:800;padding:0 6px}
.reason-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.reason-grid .check{border:1px solid #b9adc9;border-radius:8px;padding:7px;background:#fff}
.info-request-row{display:grid;grid-template-columns:1fr 1fr auto;gap:7px;margin:7px 0}.info-request-row button{background:#7b4f49}
.textgrid-panel[open]{border-top:4px solid #6a5a96}.asset-status{font-weight:800}.asset-warning{background:#ffe7df;padding:11px;border-radius:8px}
.wave-wrap{position:relative;border:1px solid #9aabb6;border-radius:9px;background:#f7fafc;overflow:hidden}.wave-wrap canvas{display:block;width:100%;height:145px}
.tier-view{overflow-x:auto}.tier-row{position:relative;height:48px;min-width:720px;border:1px solid #b6c3cb;border-top:0;background:#f8fafb}.tier-name{position:absolute;left:0;top:0;bottom:0;width:145px;padding:5px;background:#e6edf1;border-right:1px solid #9cadb8;font-weight:750;z-index:2}.tier-track{position:absolute;left:145px;right:0;top:0;bottom:0}.tier-interval{position:absolute;top:3px;bottom:3px;border:1px solid #4a7b96;background:#e1f1f8;color:#17212b;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;padding:3px;font-size:.78rem;cursor:pointer}.tier-interval.target{background:#ffd978;border-color:#9a6500}.readonly-note{background:#e8f3fa;padding:9px;border-radius:8px}
@media(max-width:820px){.reason-grid{grid-template-columns:1fr 1fr}.info-request-row{grid-template-columns:1fr}.tier-name{width:110px}.tier-track{left:110px}}
@media(prefers-color-scheme:dark){.followup-box{background:#2c263c}.reason-grid .check{background:#1a2730}.wave-wrap,.tier-row{background:#14212a}.tier-name{background:#25343d}.tier-interval{background:#1c485e;color:#eef4f8}.tier-interval.target{background:#665117}.readonly-note{background:#17384a}}
"""


GATE2_FORM = r"""
      <fieldset class="wide followup-box">
        <legend>Gate 2 · TextGrid 후속 검토 필요성</legend>
        <label>후속 TextGrid 검토<select id="textgrid-review-need" name="textgrid_review_need"><option value="">아직 기록하지 않음</option><option value="not_needed">불필요</option><option value="required">필요</option><option value="unsure">불확실</option></select></label>
        <div class="wide"><strong>필요한 이유(복수 선택)</strong><div class="reason-grid" id="textgrid-reasons">
          <label class="check"><input type="checkbox" class="tg-reason" value="boundary"> 경계</label>
          <label class="check"><input type="checkbox" class="tg-reason" value="label"> label</label>
          <label class="check"><input type="checkbox" class="tg-reason" value="transcription"> 전사</label>
          <label class="check"><input type="checkbox" class="tg-reason" value="target_span"> 표적 span</label>
          <label class="check"><input type="checkbox" class="tg-reason" value="other"> 기타</label>
        </div></div>
        <input type="hidden" name="textgrid_review_reasons_json" value="[]">
        <label>후속 필요성 판단 확신도<select name="followup_need_confidence"><option value="">선택</option><option value="1">1 · 매우 낮음</option><option value="2">2</option><option value="3">3 · 중간</option><option value="4">4</option><option value="5">5 · 매우 높음</option></select></label>
        <label class="wide">후속 검토 메모<textarea name="followup_note" placeholder="TextGrid를 더 보아야 하는 이유나 판단의 어려움"></textarea></label>
        <div class="wide"><strong>추가로 확인할 정보</strong><p class="meta">운율·의미번호·화자 정보처럼 나중에 확인할 정보명과 이유를 적습니다.</p><div id="info-requests"></div><button id="add-info-request" type="button" class="secondary">+ 정보 요청 추가</button></div>
        <input type="hidden" name="additional_information_requests_json" value="[]">
      </fieldset>
"""


GATE2_PANEL = r"""
  <section class="panel">
    <details id="textgrid-panel" class="textgrid-panel"><summary>read-only TextGrid·파형 후속 검토</summary>
      <p class="readonly-note">이 패널은 원본을 보여주기만 합니다. 경계·label 수정과 실제 실현 판정은 하지 않습니다.</p>
      <div id="textgrid-asset-message"></div>
      <div id="textgrid-meta" class="table-wrap"></div>
      <div id="wave-wrap" class="wave-wrap"><canvas id="waveform" width="900" height="145" aria-label="표적 발화 파형과 표적 시간 span"></canvas></div>
      <div class="actions"><button id="play-target-span" type="button">표적 span 재생 위치로 이동</button><span id="playback-position" class="meta"></span></div>
      <div id="tier-view" class="tier-view"></div>
    </details>
  </section>
"""


GATE2_HELPERS = r"""
const GATE2_NEEDS=new Set(['not_needed','required','unsure']);
const GATE2_REASONS=new Set(['boundary','label','transcription','target_span','other']);
const MANUAL_STATUSES=new Set(['not_created','queued','exported','returned','audited']);
const ASSET_MAP=Object.fromEntries(TEXTGRID_ASSETS.map(x=>[x.pv_id,x]));
function parseJsonArrayField(value){try{const parsed=JSON.parse(String(value||'[]'));return Array.isArray(parsed)?parsed:[];}catch(_error){return [];}}
function gateRole(sample){return sample.phenomenon_code==='NI'?'ni_method_reference':'cross_phenomenon_ui_regression_only';}
function filterGate2Ids(query,phenomenon){const q=String(query||'').trim().toLowerCase();return SAMPLES.filter(s=>(phenomenon==='all'||s.phenomenon_code===phenomenon)&&(!q||[s.pv_id,s.phenomenon_code,s.phenomenon_label,s.year,s.active_form,s.utt_id].join(' ').toLowerCase().includes(q))).map(s=>s.pv_id);}
function validateGate2Values(values){const errors=[];const need=String(values.textgrid_review_need||'');const confidence=String(values.followup_need_confidence||'');const reasons=parseJsonArrayField(values.textgrid_review_reasons_json);const requests=parseJsonArrayField(values.additional_information_requests_json);if(!GATE2_NEEDS.has(need))errors.push('TextGrid 후속 검토 필요성을 선택하세요.');if(!/^[1-5]$/.test(confidence))errors.push('후속 필요성 판단 확신도 1–5를 선택하세요.');if(reasons.some(x=>!GATE2_REASONS.has(String(x))))errors.push('허용되지 않은 TextGrid 검토 이유가 있습니다.');if((need==='required'||need==='unsure')&&!reasons.length)errors.push('필요/불확실이면 이유를 하나 이상 선택하세요.');if(need==='not_needed'&&reasons.length)errors.push('불필요를 선택했을 때 검토 이유는 비워야 합니다.');requests.forEach((row,index)=>{if(!row||typeof row!=='object'||!String(row.information_key||'').trim()||!String(row.requested_reason||'').trim())errors.push(`추가 정보 요청 ${index+1}의 정보명과 이유를 모두 적으세요.`);});return {ok:errors.length===0,errors,reasons,requests};}
function makeGate2Revision(meta,values,history,viewedPanels,asset){const eventRows=history.filter(x=>x.review_event_id===meta.review_event_id);const previous=latestByEvent(eventRows)[meta.review_event_id];const previousIndex=previous?history.indexOf(previous):-1;const maxSeq=eventRows.reduce((value,row)=>Math.max(value,Number(row.revision_seq)||0),0);const validation=validateGate2Values(values);if(!validation.ok)throw new Error(validation.errors.join(' '));const row={...meta,schema_version:'pv_reviewer_event.v3',event_uuid:makeUuid(),revision_seq:maxSeq+1,supersedes_event_uuid:previous?eventIdentity(previous,previousIndex):'',import_source_path:GATE2_META.imported_source_path,import_source_sha256:GATE2_META.imported_source_sha256,possible_duplicate_of:'',legacy_priority_tier:meta.priority_tier,target_display_status:meta.target_display_status,morph_display_status:meta.morph_display_status,...values,textgrid_review_reasons_json:JSON.stringify(validation.reasons),additional_information_requests_json:JSON.stringify(validation.requests),textgrid_asset_status:asset.textgrid_asset_status,manual_task_status:previous&&MANUAL_STATUSES.has(previous.manual_task_status)?previous.manual_task_status:'not_created',gate_method_role:gateRole(meta),context_viewed:Array.from(viewedPanels).join('|')||'pm2',reference_panels_viewed_json:JSON.stringify(Array.from(viewedPanels).filter(x=>x.endsWith('-panel'))),ipad_batch:'gate2_ni_followup_reviewer_v3_20260823',record_role:'exploratory_gate2_followup_need_not_formal_realization_ledger',reviewer:'ari30',reviewed_at:new Date().toISOString()};delete row.priority_tier;delete row.heard_variant_tags;if(previous&&semanticFingerprint(previous)===semanticFingerprint(row))row.possible_duplicate_of=eventIdentity(previous,previousIndex);return row;}
function reviewCoverage(samples,history,assets){const latest=latestByEvent(history);const decision={not_needed:0,required:0,unsure:0,not_reviewed:0};const asset={available:0,unavailable:0,blocked:0};const manual={not_created:0,queued:0,exported:0,returned:0,audited:0};samples.forEach(sample=>{const row=latest[sample.review_event_id];const need=row&&GATE2_NEEDS.has(row.textgrid_review_need)?row.textgrid_review_need:'not_reviewed';decision[need]+=1;const a=assets.find(x=>x.pv_id===sample.pv_id)||{textgrid_asset_status:'unavailable',manual_task_status:'not_created'};asset[a.textgrid_asset_status in asset?a.textgrid_asset_status:'blocked']+=1;const manualValue=row&&MANUAL_STATUSES.has(row.manual_task_status)?row.manual_task_status:a.manual_task_status;manual[manualValue in manual?manualValue:'not_created']+=1;});return {input:samples.length,decision,asset,manual};}
function buildQueueCandidates(samples,history,assets){const latest=latestByEvent(history);return samples.map(sample=>{const row=latest[sample.review_event_id];if(!row||!['required','unsure'].includes(row.textgrid_review_need))return null;const asset=assets.find(x=>x.pv_id===sample.pv_id)||{};return {schema_version:'stage2_gate2_queue_candidate.v1',queue_candidate_id:`TGQ:${sample.pv_id}:${row.event_uuid||row.reviewed_at||'legacy'}`,phenomenon_id:sample.phenomenon_code,occurrence_id:sample.occurrence_ref,utt_id:sample.utt_id,source_review_event_id:sample.review_event_id,source_event_uuid:row.event_uuid||null,source_reviewed_at:row.reviewed_at||null,textgrid_review_need:row.textgrid_review_need,textgrid_review_reasons:parseJsonArrayField(row.textgrid_review_reasons_json),additional_information_requests:parseJsonArrayField(row.additional_information_requests_json),followup_need_confidence:String(row.followup_need_confidence||''),source_textgrid_identifier:asset.source_textgrid_identifier||null,source_textgrid_sha256:asset.source_textgrid_sha256||null,source_wav_identifier:asset.source_wav_identifier||null,source_wav_sha256:asset.source_wav_sha256||null,source_span:{xmin:asset.target_xmin??null,xmax:asset.target_xmax??null},textgrid_asset_status:asset.textgrid_asset_status||'unavailable',manual_task_status:'not_created',queue_candidate_status:'exported_candidate',reviewer:row.reviewer||null,record_role:'exploratory_queue_candidate_not_manual_task'};}).filter(Boolean);}
function shouldOpenTextGrid(row,asset){return Boolean(row&&(['required','unsure'].includes(row.textgrid_review_need)||row.manual_task_status&&row.manual_task_status!=='not_created')||asset&&asset.manual_task_status&&asset.manual_task_status!=='not_created');}
"""


GATE2_INIT = r"""function init(){
let currentId=SAMPLES[0].pv_id;let visibleIds=SAMPLES.map(x=>x.pv_id);let viewedPanels=new Set(['pm2']);let formDirty=false;let infoRequests=[];
const byId=id=>document.getElementById(id);const form=byId('review-form');
function current(){return SAMPLE_MAP[currentId];}
function currentAsset(){return ASSET_MAP[currentId]||{pv_id:currentId,textgrid_asset_status:'unavailable',manual_task_status:'not_created',asset_issue_codes:['asset_record_missing']};}
function tableRows(pairs){return '<table><tbody>'+pairs.map(([k,v])=>`<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v===null||v===undefined||v===''?'—':v)}</td></tr>`).join('')+'</tbody></table>';}
function allHistory(){return BASE_HISTORY.concat(localHistory());}
function markDirty(){formDirty=true;byId('saved').textContent='저장하지 않은 변경이 있습니다.';}
function syncReasons(){const values=Array.from(document.querySelectorAll('.tg-reason:checked')).map(x=>x.value);form.elements.textgrid_review_reasons_json.value=JSON.stringify(values);return values;}
function renderInfoRequests(){byId('info-requests').innerHTML=infoRequests.map((row,index)=>`<div class="info-request-row" data-info-index="${index}"><input class="info-key" value="${escapeHtml(row.information_key||'')}" placeholder="정보명: prosodic_boundary_review"><input class="info-reason" value="${escapeHtml(row.requested_reason||'')}" placeholder="왜 필요한가"><button type="button" class="remove-info">삭제</button></div>`).join('')||'<p class="empty">추가 정보 요청 없음</p>';document.querySelectorAll('.info-request-row').forEach(container=>{const index=Number(container.dataset.infoIndex);container.querySelector('.info-key').addEventListener('input',event=>{infoRequests[index].information_key=event.target.value;syncInfoRequests();markDirty();});container.querySelector('.info-reason').addEventListener('input',event=>{infoRequests[index].requested_reason=event.target.value;syncInfoRequests();markDirty();});container.querySelector('.remove-info').addEventListener('click',()=>{infoRequests.splice(index,1);syncInfoRequests();renderInfoRequests();markDirty();});});}
function syncInfoRequests(){form.elements.additional_information_requests_json.value=JSON.stringify(infoRequests.map(row=>({information_key:String(row.information_key||'').trim(),requested_reason:String(row.requested_reason||'').trim()})));}
function loadGate2Fields(row){document.querySelectorAll('.tg-reason').forEach(box=>{box.checked=false;});for(const value of parseJsonArrayField(row&&row.textgrid_review_reasons_json)){const box=document.querySelector(`.tg-reason[value="${CSS.escape(String(value))}"]`);if(box)box.checked=true;}infoRequests=parseJsonArrayField(row&&row.additional_information_requests_json).map(item=>({information_key:String(item.information_key||''),requested_reason:String(item.requested_reason||'')}));syncReasons();syncInfoRequests();renderInfoRequests();}
function renderCandidateButtons(){const latest=latestByEvent(allHistory());byId('candidate-buttons').innerHTML=visibleIds.map(id=>{const s=SAMPLE_MAP[id];const row=latest[s.review_event_id];const done=row&&GATE2_NEEDS.has(row.textgrid_review_need)?'✓ ':'';const role=s.phenomenon_code==='NI'?'NI 기준':'UI 회귀';return `<button type="button" class="candidate ${id===currentId?'active':''}" data-pv="${escapeHtml(id)}">${done}${escapeHtml(s.phenomenon_label)} · ${escapeHtml(s.year)}<small>${escapeHtml(id)} · ${role} · ${escapeHtml(s.active_form)}</small></button>`;}).join('')||'<p class="empty">검색 결과가 없습니다.</p>';document.querySelectorAll('.candidate').forEach(btn=>btn.addEventListener('click',()=>requestActivate(btn.dataset.pv)));}
function renderProgress(){const coverage=reviewCoverage(SAMPLES,allHistory(),TEXTGRID_ASSETS);byId('global-progress').textContent=`Gate 2 판단 ${coverage.input-coverage.decision.not_reviewed}/${coverage.input} · 미검토 ${coverage.decision.not_reviewed} · TextGrid available ${coverage.asset.available}/${coverage.input} · 추가 revision ${localHistory().length}`;byId('import-summary').textContent=`기존 사용자 JSONL ${BASE_HISTORY.length}행을 원문 그대로 포함했습니다. 새 기록은 탐색용 Gate 2 revision이며 정식 ledger가 아닙니다.`;}
function renderMorph(s){const d=s.target_display;const parts=(d.segments||[]).map(seg=>`<span class="morph"><strong>${escapeHtml(seg.surface||seg.units||'형태소 미상')}</strong> / ${escapeHtml(seg.pos||'POS 미상')}<br><small>초점 ${escapeHtml(seg.focus_unit||seg.units||'—')}</small></span>`);byId('morph-display').innerHTML=parts.join('<span class="boundary">│</span>')+`<span class="boundary">${morphBoundaryLabel(d.kind)} ${escapeHtml(d.boundary||'—')}</span>`;byId('morph-limit').textContent=`${morphStatusText(d.status)} [${d.status}] 이 표시는 검색 환경 근거이며 음향적 경계나 실제 실현 판정이 아닙니다.`;}
function rowButton(row){const overlap=row.source_note_overlap_flag==='True'||row.timestamp_overlap_raw==='True';return `<button type="button" class="transcript-row ${row.is_target?'target':''} ${overlap?'overlap':''}" data-utt="${escapeHtml(row.utt_id)}"><span>${escapeHtml(row.source_rank_in_dialogue)}</span><span>${escapeHtml(row.speaker_id)}</span><span>${escapeHtml(row.form||'(전사 없음)')}</span></button>`;}
function wireTranscriptClicks(){document.querySelectorAll('.transcript-row').forEach(btn=>btn.addEventListener('click',()=>{byId('selected-context').textContent=`선택한 문맥: ${btn.dataset.utt}`;viewedPanels.add('dialogue_search');}));}
function renderSpeakerRun(s){const rows=(DIALOGUES[s.pv_id]||[]).filter(x=>x.derived_turn_id===s.target_metadata.derived_turn_id);byId('speaker-run').innerHTML=rows.length?rows.map(rowButton).join(''):'<p class="empty">묶음 텍스트를 찾지 못했습니다.</p>';wireTranscriptClicks();}
function renderDialogue(){const s=current();const rows=DIALOGUES[s.pv_id]||[];const q=byId('dialogue-search').value.trim().toLowerCase();const showAll=byId('dialogue-all').checked;const targetIndex=rows.findIndex(x=>x.is_target);let shown;if(q)shown=rows.filter(x=>[x.form,x.original_form,x.note,x.speaker_id].join(' ').toLowerCase().includes(q));else if(showAll)shown=rows;else shown=rows.filter((_,i)=>Math.abs(i-targetIndex)<=10);byId('dialogue-results').innerHTML=shown.length?shown.map(rowButton).join(''):'<p class="empty">검색 결과가 없습니다.</p>';wireTranscriptClicks();}
function renderPm2(s){const rows=s.context_pm2||[];byId('pm2-table').innerHTML='<table><thead><tr><th>위치</th><th>화자</th><th>전사</th><th>turn/상태</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${escapeHtml(r.relation)}</td><td>${escapeHtml(r.speaker_id||'—')}</td><td>${escapeHtml(r.form||'(없음)')}</td><td>${escapeHtml(r.derived_turn_id||'—')} / ${escapeHtml(r.slot_status||'')}</td></tr>`).join('')+'</tbody></table>';}
function renderMeta(s){const m=s.target_metadata||{};const a=currentAsset();byId('social-meta').innerHTML=tableRows([['화자',m.speaker_id],['성별',m.sex],['연령',m.age_norm],['현재 거주지역',m.current_residence_norm],['출생지역',m.birthplace_norm],['대화 유형',m.discourse_mode],['말뭉치 범주',m.category_norm],['주제',m.topic],['관계',m.relation],['조작적 화자 묶음',`${m.derived_turn_id||'—'} · ${m.target_position_in_speaker_run||'—'}/${m.speaker_run_unit_count||'—'}`]]);byId('pron-meta').innerHTML=tableRows([['규칙 예상형(한글)',m.pron_pred_hangul],['규칙 예상형(IPA)',m.pron_pred_ipa],['사전 참조형',m.pron_reference_hangul],['사전 참조 상태',m.pron_reference_status],['사전 참조 출처',m.pron_reference_source]]);byId('audit-meta').innerHTML=tableRows([['pv_id',s.pv_id],['utt_id',s.utt_id],['occurrence',s.occurrence_ref],['query',s.pv_query_id],['Gate 2 역할',a.gate_method_role],['이전 PV-A 표본 태그(연구 우선순위 아님)',s.priority_tier],['TextGrid asset',a.textgrid_asset_status],['source TextGrid SHA',a.source_textgrid_sha256],['source manifest SHA',BUILD_META.source_manifest_sha256],['Gate 2 source SHA',GATE2_META.source_v2_1_html_sha256]]);}
function drawWaveform(asset){const canvas=byId('waveform');const ctx=canvas.getContext('2d');const width=Math.max(720,canvas.clientWidth||900);const height=145;if(canvas.width!==width)canvas.width=width;canvas.height=height;ctx.clearRect(0,0,width,height);ctx.fillStyle='#f7fafc';ctx.fillRect(0,0,width,height);if(!asset.waveform||!asset.waveform.peaks.length)return;const duration=asset.waveform.duration_seconds;const startX=asset.target_xmin/duration*width;const endX=asset.target_xmax/duration*width;ctx.fillStyle='#ffe09a';ctx.fillRect(startX,0,Math.max(2,endX-startX),height);ctx.strokeStyle='#2a6b8d';ctx.lineWidth=1;const mid=height/2;asset.waveform.peaks.forEach((peak,index)=>{const x=index/(asset.waveform.peaks.length-1)*width;const h=peak*(height*.43);ctx.beginPath();ctx.moveTo(x,mid-h);ctx.lineTo(x,mid+h);ctx.stroke();});const audio=byId('target-audio');const currentTime=Number(audio.currentTime)||0;ctx.strokeStyle='#b33c31';ctx.lineWidth=2;const playX=Math.min(width,Math.max(0,currentTime/duration*width));ctx.beginPath();ctx.moveTo(playX,0);ctx.lineTo(playX,height);ctx.stroke();byId('playback-position').textContent=`재생 ${currentTime.toFixed(3)}초 / 표적 ${asset.target_xmin.toFixed(3)}–${asset.target_xmax.toFixed(3)}초`;}
function renderTiers(asset){if(!asset.textgrid){byId('tier-view').innerHTML='';return;}const duration=asset.textgrid.xmax;byId('tier-view').innerHTML=asset.textgrid.tiers.map(tier=>{const intervals=tier.intervals.map(interval=>{const left=interval.xmin/duration*100;const width=Math.max(.12,(interval.xmax-interval.xmin)/duration*100);const target=interval.xmax>asset.target_xmin&&interval.xmin<asset.target_xmax;return `<button type="button" class="tier-interval ${target?'target':''}" data-seek="${interval.xmin}" style="left:${left}%;width:${width}%" title="${escapeHtml(interval.xmin.toFixed(3)+'–'+interval.xmax.toFixed(3)+' '+interval.text)}">${escapeHtml(interval.text||'∅')}</button>`;}).join('');return `<div class="tier-row"><div class="tier-name">${escapeHtml(tier.name)}</div><div class="tier-track">${intervals}</div></div>`;}).join('');document.querySelectorAll('.tier-interval').forEach(button=>button.addEventListener('click',()=>{byId('target-audio').currentTime=Number(button.dataset.seek)||0;drawWaveform(asset);}));}
function renderTextGrid(){const asset=currentAsset();byId('textgrid-asset-message').innerHTML=asset.textgrid_asset_status==='available'?`<p class="asset-status">TextGrid available · 6-tier read-only</p>`:`<p class="asset-warning">${escapeHtml(asset.textgrid_asset_status)} · ${escapeHtml((asset.asset_issue_codes||[]).join(', ')||'자산을 표시할 수 없습니다.')} 후보는 삭제하지 않고 유지합니다.</p>`;byId('textgrid-meta').innerHTML=tableRows([['source TextGrid',asset.source_textgrid_identifier],['TextGrid SHA-256',asset.source_textgrid_sha256],['source WAV',asset.source_wav_identifier],['WAV SHA-256',asset.source_wav_sha256],['target span',`${Number(asset.target_xmin).toFixed(3)}–${Number(asset.target_xmax).toFixed(3)}초`],['timing status',asset.timing_status],['asset status',asset.textgrid_asset_status],['manual task status',asset.manual_task_status]]);byId('wave-wrap').style.display=asset.textgrid_asset_status==='available'?'block':'none';byId('play-target-span').disabled=asset.textgrid_asset_status!=='available';drawWaveform(asset);renderTiers(asset);}
function restoreForm(s){form.reset();form.elements.judgement_confidence.value='unjudged';form.elements.overlap_impression.value='not_checked';const row=latestByEvent(allHistory())[s.review_event_id];if(row)Array.from(form.elements).forEach(el=>{if(!el.name||!(el.name in row))return;if(el.type==='checkbox')el.checked=Boolean(row[el.name]);else if(el.name==='heard_variant_tags'&&row.heard_variant_tags_json){try{el.value=JSON.parse(row.heard_variant_tags_json).join(', ');}catch(_error){el.value='';}}else el.value=row[el.name]??'';});loadGate2Fields(row||{});byId('saved').textContent=row?'기존 최신 revision을 복원했습니다.':'';byId('textgrid-panel').open=shouldOpenTextGrid(row,currentAsset());formDirty=false;}
function setActive(id){if(!SAMPLE_MAP[id])return;currentId=id;viewedPanels=new Set(['pm2']);const s=current();const a=currentAsset();const index=SAMPLES.findIndex(x=>x.pv_id===id);byId('position').textContent=`${index+1}/14 · ${s.phenomenon_code} · ${s.year}`;byId('sample-title').textContent=`${s.phenomenon_label} · ${s.year}`;byId('sample-meta').textContent=`${s.pv_id} · ${s.utt_id} · ${s.environment_scope}`;byId('active-form').innerHTML=highlightActiveForm(s);const tag=byId('gate-role-tag');tag.textContent=s.phenomenon_code==='NI'?'NI 방법론 기준':'타 현상 UI 회귀만';tag.className=`tag gate-role ${s.phenomenon_code==='NI'?'ni':''}`;renderMorph(s);byId('target-audio').src=s.target_audio;byId('context-audio').src=s.context_audio;renderPm2(s);renderSpeakerRun(s);byId('dialogue-search').value='';byId('dialogue-all').checked=false;byId('selected-context').textContent='';renderDialogue();renderMeta(s);restoreForm(s);renderTextGrid();renderCandidateButtons();renderProgress();if(a.textgrid_asset_status!=='available')byId('textgrid-panel').open=true;}
function requestActivate(id){if(!SAMPLE_MAP[id]||id===currentId)return true;if(!canDiscardDirty(formDirty,message=>confirm(message)))return false;formDirty=false;setActive(id);return true;}
function applyFilter(){visibleIds=filterGate2Ids(byId('candidate-search').value,byId('phenomenon-filter').value);renderCandidateButtons();if(visibleIds.length&&!visibleIds.includes(currentId)&&!formDirty)setActive(visibleIds[0]);}
function move(delta){const list=visibleIds.length?visibleIds:SAMPLES.map(x=>x.pv_id);let index=list.indexOf(currentId);if(index<0)index=0;index=(index+delta+list.length)%list.length;if(requestActivate(list[index]))window.scrollTo({top:0,behavior:'smooth'});}
function downloadText(filename,body){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([body],{type:'application/x-ndjson;charset=utf-8'}));a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
byId('candidate-search').addEventListener('input',applyFilter);byId('phenomenon-filter').addEventListener('change',applyFilter);byId('prev').addEventListener('click',()=>move(-1));byId('next').addEventListener('click',()=>move(1));
form.addEventListener('input',event=>{if(!event.target.classList.contains('info-key')&&!event.target.classList.contains('info-reason'))markDirty();});form.addEventListener('change',()=>markDirty());window.addEventListener('beforeunload',event=>{if(formDirty){event.preventDefault();event.returnValue='';}});
byId('textgrid-review-need').addEventListener('change',event=>{if(event.target.value==='required'||event.target.value==='unsure'){byId('textgrid-panel').open=true;viewedPanels.add('textgrid-panel');renderTextGrid();}if(event.target.value==='not_needed'){document.querySelectorAll('.tg-reason').forEach(box=>{box.checked=false;});syncReasons();}});document.querySelectorAll('.tg-reason').forEach(box=>box.addEventListener('change',syncReasons));
byId('add-info-request').addEventListener('click',()=>{infoRequests.push({information_key:'',requested_reason:''});syncInfoRequests();renderInfoRequests();markDirty();});
byId('play-target-span').addEventListener('click',()=>{const a=currentAsset();if(a.textgrid_asset_status==='available'){byId('target-audio').currentTime=a.target_xmin;drawWaveform(a);}});byId('target-audio').addEventListener('timeupdate',()=>drawWaveform(currentAsset()));window.addEventListener('resize',()=>drawWaveform(currentAsset()));
byId('dialogue-search').addEventListener('input',()=>{viewedPanels.add('dialogue_search');renderDialogue();});byId('dialogue-all').addEventListener('change',()=>{viewedPanels.add('dialogue_search');renderDialogue();});document.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>{if(d.open){viewedPanels.add(d.id);if(d.id==='textgrid-panel')renderTextGrid();}}));
byId('save').addEventListener('click',()=>{syncReasons();syncInfoRequests();const s=current();const values={};Array.from(form.elements).forEach(el=>{if(!el.name)return;values[el.name]=el.type==='checkbox'?el.checked:el.value;});const validation=validateGate2Values(values);if(!validation.ok){byId('saved').textContent=validation.errors.join(' ');form.elements.textgrid_review_need.focus();return;}const history=allHistory();const row=makeGate2Revision({review_event_id:s.review_event_id,pv_id:s.pv_id,phenomenon_code:s.phenomenon_code,phenomenon_label:s.phenomenon_label,pv_query_id:s.pv_query_id,environment_scope:s.environment_scope,year:String(s.year),utt_id:s.utt_id,occurrence_ref:s.occurrence_ref,priority_tier:s.priority_tier,target_display_status:s.target_display_status,morph_display_status:s.morph_display_status},values,history,viewedPanels,currentAsset());const local=localHistory();local.push(row);setLocalHistory(local);formDirty=false;byId('saved').textContent=`저장됨 · 이 표본 Gate 2 revision ${row.revision_seq}`;renderProgress();renderCandidateButtons();});
byId('import-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;if(!canDiscardDirty(formDirty,message=>confirm(message))){event.target.value='';byId('import-status').textContent='저장하지 않은 입력을 보존하기 위해 가져오기를 취소했습니다.';return;}formDirty=false;try{const rows=parseJsonl(await file.text());const dup=duplicateCount(allHistory(),rows);if(dup&&!confirm(`${dup}개 행이 기존 기록과 내용상 같습니다. 삭제하지 않고 모두 추가할까요?`)){byId('import-status').textContent='가져오기를 취소했습니다.';return;}const local=localHistory();local.push(...rows);setLocalHistory(local);localStorage.setItem(IMPORT_META_KEY,JSON.stringify({name:file.name,rows:rows.length,imported_at:new Date().toISOString()}));byId('import-status').textContent=`${rows.length}행을 원형 그대로 추가했습니다. 내용상 중복 ${dup}행도 삭제하지 않았습니다.`;setActive(currentId);}catch(error){byId('import-status').textContent=`가져오기 실패: ${error.message}`;}finally{event.target.value='';}});
function exportBody(){return toJsonl(allHistory());}
byId('export').addEventListener('click',()=>downloadText(`STAGE2_GATE2_NI_REVIEWER_V3_${new Date().toISOString().replace(/[:.]/g,'-')}.jsonl`,exportBody()));
byId('export-queue').addEventListener('click',()=>{const rows=buildQueueCandidates(SAMPLES,allHistory(),TEXTGRID_ASSETS);if(!rows.length){byId('import-status').textContent='현재 최신값에는 required/unsure queue 후보가 없습니다.';return;}downloadText(`STAGE2_GATE2_QUEUE_CANDIDATES_${new Date().toISOString().replace(/[:.]/g,'-')}.jsonl`,toJsonl(rows));byId('import-status').textContent=`Gate 3 작업 전 후보 ${rows.length}행을 내보냈습니다. 정식 task나 ledger가 아닙니다.`;});
byId('copy').addEventListener('click',async()=>{const body=exportBody();const panel=byId('copy-panel');const area=byId('copy-text');area.value=body;panel.style.display='block';area.focus();area.select();try{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(body);}catch(_error){}});
byId('literature').innerHTML=LITERATURE.map(x=>`<li><strong>인쇄 ${escapeHtml(x.printed_page??'—')}쪽</strong> ${escapeHtml(x.claim_ko)}<br><small>한계: ${escapeHtml(x.does_not_establish||'—')}</small></li>`).join('');
setActive(currentId);
}
if(typeof document!=='undefined')init();"""


def transform_html(
    source: str,
    assets: list[dict[str, Any]],
    gate2_meta: Mapping[str, Any],
) -> str:
    document = replace_once(
        source,
        "<title>PV 검토 화면 v2.1</title>",
        "<title>Stage 2 Gate 2 · NI 후속 TextGrid reviewer v3</title>",
        "document title",
    )
    document = replace_once(
        document,
        "<header><h1>PV 검토 화면 v2.1 · 균형 14개</h1>",
        "<header><h1>Stage 2 Gate 2 · NI 후속 TextGrid reviewer v3</h1>",
        "visible title",
    )
    document = replace_once(
        document,
        "</style>",
        GATE2_CSS + "\n</style>",
        "Gate 2 CSS",
    )
    old_filter = (
        '<div class="control"><label for="priority-filter">우선순위</label>'
        '<select id="priority-filter"><option value="all">전체</option>'
        '<option value="core">핵심 5현상</option><option value="exploratory">'
        "탐색 VH·HIA</option></select></div>"
    )
    new_filter = (
        '<div class="control"><label for="phenomenon-filter">현상 필터</label>'
        '<select id="phenomenon-filter"><option value="all">전체 14개(UI 회귀 포함)</option>'
        '<option value="NI">NI 2개만</option><option value="PT">PT</option>'
        '<option value="NAN">NAN</option><option value="NAL">NAL</option>'
        '<option value="LLN">LLN</option><option value="VH">VH</option>'
        '<option value="HIA">HIA</option></select></div>'
    )
    document = replace_once(document, old_filter, new_filter, "research priority removal")
    document = replace_once(
        document,
        '<div class="titleline"><span id="priority-tag" class="tag"></span><h2 id="sample-title"></h2></div>',
        '<div class="titleline"><span id="gate-role-tag" class="tag gate-role"></span><h2 id="sample-title"></h2></div>',
        "Gate method role tag",
    )
    listened_marker = '      <label class="check wide"><input type="checkbox" name="listened"> 청취함</label>\n'
    document = replace_once(
        document,
        listened_marker,
        listened_marker + GATE2_FORM,
        "Gate 2 form",
    )
    panel_marker = (
        "  </section>\n  <section class=\"panel\">\n"
        "    <details id=\"pm2-panel\"><summary>±2 문맥 전사</summary>"
    )
    document = replace_once(
        document,
        panel_marker,
        "  </section>\n" + GATE2_PANEL + "  <section class=\"panel\">\n"
        "    <details id=\"pm2-panel\"><summary>±2 문맥 전사</summary>",
        "TextGrid panel",
    )
    document = replace_once(
        document,
        '<button id="export" type="button">전체 JSONL 저장</button><button id="copy"',
        '<button id="export" type="button">전체 JSONL 저장</button><button id="export-queue" type="button" class="secondary">Gate 3 queue 후보 저장</button><button id="copy"',
        "queue export button",
    )
    document = replace_once(
        document,
        "const DIALOGUES=",
        f"const TEXTGRID_ASSETS={json_for_script(assets)};\n"
        f"const GATE2_META={json_for_script(dict(gate2_meta))};\nconst DIALOGUES=",
        "embedded Gate 2 assets",
    )
    document = replace_once(
        document,
        "const LOCAL_KEY='pv_reviewer_v2_local_history_20260822';",
        "const LOCAL_KEY='stage2_gate2_ni_reviewer_v3_local_history_20260823';",
        "Gate 2 local key",
    )
    document = replace_once(
        document,
        "const IMPORT_META_KEY='pv_reviewer_v2_import_meta_20260822';",
        "const IMPORT_META_KEY='stage2_gate2_ni_reviewer_v3_import_meta_20260823';",
        "Gate 2 import key",
    )
    document = replace_once(
        document,
        "const ALLOWED_BATCHES=new Set(['balanced14_2020_2025_v1','balanced14_2020_2025_reviewer_v2']);",
        "const ALLOWED_BATCHES=new Set(['balanced14_2020_2025_v1','balanced14_2020_2025_reviewer_v2','gate2_ni_followup_reviewer_v3_20260823']);",
        "Gate 2 import batch",
    )
    api_marker = (
        "globalThis.PV_REVIEWER_V2_TEST_API={SAMPLES,BASE_HISTORY,LITERATURE,BUILD_META,"
        "parseJsonl,duplicateCount,latestByEvent,makeRevision,filterIds,toJsonl,semanticFingerprint,"
        "reviewedAtMs,canDiscardDirty,highlightActiveForm,morphStatusText,morphBoundaryLabel};"
    )
    document = replace_once(
        document,
        api_marker,
        GATE2_HELPERS
        + "\n"
        + api_marker
        + "\n"
        + "globalThis.PV_REVIEWER_V3_TEST_API={SAMPLES,TEXTGRID_ASSETS,BASE_HISTORY,GATE2_META,parseJsonl,latestByEvent,toJsonl,canDiscardDirty,filterGate2Ids,validateGate2Values,makeGate2Revision,reviewCoverage,buildQueueCandidates,shouldOpenTextGrid,gateRole};",
        "Gate 2 helpers and test API",
    )
    init_pattern = re.compile(
        r"function init\(\)\{.*?\n\}\nif\(typeof document!=='undefined'\)init\(\);",
        flags=re.DOTALL,
    )
    document, count = init_pattern.subn(lambda _: GATE2_INIT, document, count=1)
    if count != 1:
        raise RuntimeError(f"Gate 2 init replacement count={count}")
    required = (
        "Stage 2 Gate 2 · NI 후속 TextGrid reviewer v3",
        "textgrid_review_need",
        "followup_need_confidence",
        "read-only TextGrid·파형 후속 검토",
        "PV_REVIEWER_V3_TEST_API",
        "exploratory_queue_candidate_not_manual_task",
        "이전 PV-A 표본 태그(연구 우선순위 아님)",
    )
    missing = [marker for marker in required if marker not in document]
    if missing:
        raise RuntimeError(f"Gate 2 behavior markers missing: {missing}")
    return document


def prepare(
    *, source_dir: Path, pv_root: Path, plan_path: Path
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    source_dir = source_dir.resolve(strict=True)
    pv_root = pv_root.resolve(strict=True)
    plan_path = plan_path.resolve(strict=True)
    source_html_path = source_dir / SOURCE_HTML
    source_build_path = source_dir / SOURCE_BUILD
    source_imported_path = source_dir / SOURCE_IMPORTED
    source_dialogue_path = source_dir / SOURCE_DIALOGUES
    source_audit_path = source_dir / SOURCE_AUDIT
    source_manifest_path = source_dir / SOURCE_MANIFEST
    samples_csv = pv_root / "samples" / "PV_SAMPLES.csv"
    pv_manifest_path = pv_root / "PV_MANIFEST.json"
    zero_drop_path = PROJECT_ROOT / "config" / "stage2_zero_drop_status_dictionary.v1.json"
    info_schema_path = PROJECT_ROOT / "config" / "stage2_additional_information_sidecar_schema.v1.json"
    pinned = {
        "source_html": verify_pinned_file(source_html_path, EXPECTED_SHA256["source_html"], "source v2.1 HTML"),
        "source_build": verify_pinned_file(source_build_path, EXPECTED_SHA256["source_build"], "source v2.1 build"),
        "source_audit": verify_pinned_file(source_audit_path, EXPECTED_SHA256["source_audit"], "source v2.1 audit"),
        "samples_csv": verify_pinned_file(samples_csv, EXPECTED_SHA256["samples_csv"], "PV samples"),
        "pv_manifest": verify_pinned_file(pv_manifest_path, EXPECTED_SHA256["pv_manifest"], "PV manifest"),
        "zero_drop_dictionary": verify_pinned_file(zero_drop_path, EXPECTED_SHA256["zero_drop_dictionary"], "zero-drop dictionary"),
        "additional_information_schema": verify_pinned_file(info_schema_path, EXPECTED_SHA256["additional_information_schema"], "additional information schema"),
        "approved_plan": verify_pinned_file(plan_path, EXPECTED_SHA256["approved_plan"], "approved Gate 2 plan"),
    }
    source_build = json.loads(source_build_path.read_text(encoding="utf-8"))
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
    if source_build.get("status") != "built_pending_independent_audit":
        raise RuntimeError("source v2.1 build status differs")
    if source_audit.get("passed") is not True or source_audit.get("errors") != []:
        raise RuntimeError("source v2.1 independent audit is not a clean pass")
    source_document = source_html_path.read_text(encoding="utf-8")
    samples = extract_json_constant(source_document, "SAMPLES", "DIALOGUES")
    if len(samples) != 14 or len({row.get("pv_id") for row in samples}) != 14:
        raise RuntimeError("source v2.1 is not the frozen 14 unique samples")
    by_phenomenon: dict[str, int] = {}
    for sample in samples:
        code = str(sample.get("phenomenon_code"))
        by_phenomenon[code] = by_phenomenon.get(code, 0) + 1
    if by_phenomenon != {"PT": 2, "NAN": 2, "NAL": 2, "NI": 2, "LLN": 2, "VH": 2, "HIA": 2}:
        raise RuntimeError(f"source phenomenon balance differs: {by_phenomenon}")
    if [row["pv_id"] for row in samples if row.get("phenomenon_code") == "NI"] != EXPECTED_NI_IDS:
        raise RuntimeError("NI method-reference pv_id set differs")
    _rows, rows_by_pv = read_samples(samples_csv)
    packages, package_count = index_packages(pv_root / "bundle")
    assets = [build_asset(sample, rows_by_pv[sample["pv_id"]], packages.get(sample["pv_id"])) for sample in samples]
    role_counts = {
        "ni_method_reference": sum(row["gate_method_role"] == "ni_method_reference" for row in assets),
        "cross_phenomenon_ui_regression_only": sum(row["gate_method_role"] == "cross_phenomenon_ui_regression_only" for row in assets),
    }
    asset_counts = {
        status: sum(row["textgrid_asset_status"] == status for row in assets)
        for status in ("available", "unavailable", "blocked")
    }
    gate2_meta = {
        "schema_version": "stage2_gate2_reviewer_v3_embedded_meta.v1",
        "source_v2_1_html_sha256": pinned["source_html"]["sha256"],
        "pv_samples_sha256": pinned["samples_csv"]["sha256"],
        "pv_manifest_sha256": pinned["pv_manifest"]["sha256"],
        "approved_plan_sha256": pinned["approved_plan"]["sha256"],
        "imported_source_path": str(source_imported_path),
        "imported_source_sha256": sha256_file(source_imported_path),
        "record_role": "exploratory_gate2_followup_need_not_formal_realization_ledger",
    }
    document = transform_html(source_document, assets, gate2_meta)
    receipt = {
        "schema_version": "stage2_gate2_ni_followup_reviewer_v3_build.v1",
        "status": "preflight_ready",
        "recorded_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "scope": {
            "samples": 14,
            "ni_method_reference": 2,
            "cross_phenomenon_ui_regression_only": 12,
            "new_candidate_extraction": False,
            "g5_g6_run": False,
            "inter_eojeol_ni_method_sample": False,
        },
        "pinned_inputs": pinned,
        "source_v2_1": {
            "root": str(source_dir),
            "imported_jsonl": {"path": str(source_imported_path), "sha256": sha256_file(source_imported_path)},
            "dialogue_jsonl": {"path": str(source_dialogue_path), "sha256": sha256_file(source_dialogue_path)},
            "manifest": {"path": str(source_manifest_path), "sha256": sha256_file(source_manifest_path)},
        },
        "asset_projection": {
            "package_manifests_scanned": package_count,
            "selected_assets": len(assets),
            "role_counts": role_counts,
            "asset_status_counts": asset_counts,
            "expected_tier_order": EXPECTED_TIERS,
            "waveform_bins": WAVEFORM_BINS,
            "asset_rows": [
                {
                    "pv_id": row["pv_id"],
                    "gate_method_role": row["gate_method_role"],
                    "textgrid_asset_status": row["textgrid_asset_status"],
                    "source_textgrid_identifier": row["source_textgrid_identifier"],
                    "source_textgrid_sha256": row["source_textgrid_sha256"],
                    "source_wav_identifier": row["source_wav_identifier"],
                    "source_wav_sha256": row["source_wav_sha256"],
                    "target_xmin": row["target_xmin"],
                    "target_xmax": row["target_xmax"],
                    "asset_issue_codes": row["asset_issue_codes"],
                }
                for row in assets
            ],
        },
        "safety": {
            "source_files_modified": False,
            "source_corpus_scanned": False,
            "source_audio_modified": False,
            "source_textgrid_modified": False,
            "textgrid_boundary_edit_enabled": False,
            "formal_manual_task_created": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "mfa_run": False,
            "koina_run": False,
            "wav2vec2_run": False,
            "existing_output_overwritten": False,
        },
    }
    return document, receipt, assets


def build(*, source_dir: Path, pv_root: Path, plan_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    approved_parent = (PROJECT_ROOT / "outputs" / "pilots").resolve(strict=True)
    if output_dir.parent != approved_parent:
        raise RuntimeError(f"Gate 2 output must be a direct outputs/pilots child: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    if partial.exists():
        raise FileExistsError(f"existing partial output is preserved: {partial}")
    document, receipt, _assets = prepare(source_dir=source_dir, pv_root=pv_root, plan_path=plan_path)
    partial.mkdir(parents=True)
    html_path = partial / HTML_NAME
    imported_path = partial / IMPORTED_NAME
    dialogue_path = partial / DIALOGUE_NAME
    write_text_atomic(html_path, document)
    write_bytes_atomic(imported_path, (source_dir / SOURCE_IMPORTED).resolve(strict=True).read_bytes())
    write_bytes_atomic(dialogue_path, (source_dir / SOURCE_DIALOGUES).resolve(strict=True).read_bytes())
    receipt["status"] = "built_pending_independent_audit"
    receipt["output"] = {
        "html": {"path": HTML_NAME, "bytes": html_path.stat().st_size, "sha256": sha256_file(html_path)},
        "imported_jsonl": {"path": IMPORTED_NAME, "bytes": imported_path.stat().st_size, "sha256": sha256_file(imported_path)},
        "dialogue_jsonl": {"path": DIALOGUE_NAME, "bytes": dialogue_path.stat().st_size, "sha256": sha256_file(dialogue_path)},
    }
    write_text_atomic(partial / BUILD_NAME, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    os.replace(partial, output_dir)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--pv-root", type=Path, default=DEFAULT_PV_ROOT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.preflight_only:
            _document, receipt, _assets = prepare(
                source_dir=args.source_dir, pv_root=args.pv_root, plan_path=args.plan
            )
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
        else:
            receipt = build(
                source_dir=args.source_dir,
                pv_root=args.pv_root,
                plan_path=args.plan,
                output_dir=args.output_dir,
            )
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
