"""Build a self-contained, iPad-oriented PV-A review file.

The derivative embeds copied target/context WAV bytes without transforming
audio.  It reads the passed PV-A output and never changes that frozen result.
"""

from __future__ import annotations

import argparse
import base64
import csv
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_ROOT = (
    PROJECT_ROOT / "outputs" / "pilots" / "pv_seven_phenomena_20260819"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "work" / "pv_ipad_balanced14_20260820"
PHENOMENON_ORDER = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
ENDPOINT_YEARS = [2020, 2025]
HTML_NAME = "PV_IPAD_BALANCED14_20260820.html"
RECEIPT_NAME = "PV_IPAD_BALANCED14_20260820_RECEIPT.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def data_uri(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise RuntimeError(f"not a RIFF/WAVE file: {path}")
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:audio/wav;base64,{encoded}", len(payload)


def pick_balanced_samples(
    samples: Iterable[Mapping[str, str]],
) -> list[dict[str, str]]:
    rows = list(samples)
    selected: list[dict[str, str]] = []
    for code in PHENOMENON_ORDER:
        for year in ENDPOINT_YEARS:
            matches = [
                dict(row)
                for row in rows
                if row.get("primary_phenomenon_code") == code
                and int(row.get("year", 0)) == year
            ]
            if not matches:
                raise RuntimeError(f"balanced iPad cell is empty: {code}|{year}")
            matches.sort(key=lambda row: row["pv_id"])
            selected.append(matches[0])
    if len(selected) != 14 or len({row["pv_id"] for row in selected}) != 14:
        raise RuntimeError("balanced iPad selection must contain 14 unique packages")
    return selected


def package_map(bundle_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for manifest_path in sorted(bundle_root.glob("*/PACKAGE_MANIFEST.json")):
        manifest = load_json(manifest_path)
        pv_id = str(manifest.get("pv_id", ""))
        if not pv_id or pv_id in result:
            raise RuntimeError(f"invalid/duplicate package pv_id: {manifest_path}")
        result[pv_id] = manifest_path.parent
    return result


def json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def context_table(rows: list[dict[str, str]]) -> str:
    cells = []
    for row in rows:
        relation = row.get("relation", "")
        speaker = row.get("speaker_id", "") or "—"
        form = row.get("form", "") or "(문맥 슬롯 없음)"
        status = row.get("slot_status", "")
        audio = row.get("wav_status", "") or "not_applicable"
        cells.append(
            "<tr>"
            f"<td>{html.escape(relation)}</td>"
            f"<td>{html.escape(speaker)}</td>"
            f"<td>{html.escape(form)}</td>"
            f"<td>{html.escape(status)} / {html.escape(audio)}</td>"
            "</tr>"
        )
    return "".join(cells)


def build_html(
    *,
    selected: list[dict[str, str]],
    events: list[dict[str, str]],
    packages: Mapping[str, Path],
) -> tuple[str, list[dict[str, Any]], int]:
    primary_events = {
        (row["pv_id"], row["phenomenon_code"]): row
        for row in events
        if row.get("is_primary_phenomenon") == "True"
    }
    cards: list[str] = []
    metadata: dict[str, dict[str, str]] = {}
    selected_receipts: list[dict[str, Any]] = []
    embedded_audio_bytes = 0
    for ordinal, sample in enumerate(selected, 1):
        pv_id = sample["pv_id"]
        code = sample["primary_phenomenon_code"]
        event = primary_events.get((pv_id, code))
        if event is None:
            raise RuntimeError(f"primary review event missing: {pv_id}|{code}")
        package = packages.get(pv_id)
        if package is None:
            raise RuntimeError(f"bundle package missing: {pv_id}")
        target_path = package / "target.wav"
        context_path = package / "context_pm2.wav"
        target_uri, target_bytes = data_uri(target_path)
        context_uri, context_bytes = data_uri(context_path)
        embedded_audio_bytes += target_bytes + context_bytes
        context_rows = read_csv(package / "context.csv")
        if len(context_rows) != 5:
            raise RuntimeError(f"context row count is not five: {pv_id}")
        event_id = event["review_event_id"]
        metadata[event_id] = {
            "review_event_id": event_id,
            "pv_id": pv_id,
            "phenomenon_code": code,
            "phenomenon_label": sample["primary_phenomenon_label"],
            "pv_query_id": event["pv_query_ids_json"],
            "environment_scope": sample["environment_scope"],
            "year": sample["year"],
            "utt_id": sample["utt_id"],
            "occurrence_ref": sample["physical_occurrence_ref"],
            "record_role": "exploratory_pv_only_not_formal_realization_ledger",
            "ipad_batch": "balanced14_2020_2025_v1",
        }
        context_sufficient = context_rows[2].get(
            "context_sufficient_for_preview", ""
        )
        cards.append(
            f"""
<section class="sample" id="{html.escape(pv_id)}">
  <h2>{ordinal}. {html.escape(sample['primary_phenomenon_label'])} · {html.escape(sample['year'])}</h2>
  <p class="meta"><code>{html.escape(pv_id)}</code> · <code>{html.escape(sample['utt_id'])}</code> · {html.escape(sample['environment_scope'])}</p>
  <p class="utterance">{html.escape(sample['active_form'])}</p>
  <div class="audio-block">
    <label>대상 발화</label>
    <audio controls preload="metadata" src="{target_uri}"></audio>
  </div>
  <div class="audio-block">
    <label>앞뒤 문맥 ±2 직렬화</label>
    <audio controls preload="metadata" src="{context_uri}"></audio>
  </div>
  <p class="notice">문맥 음성의 0.05초 간격은 합성 간격이며 원 대화의 휴지가 아닙니다. 자동 실현 판정을 하지 않습니다.</p>
  <details>
    <summary>문맥 전사 보기 · 사전 충분성 {html.escape(context_sufficient)}</summary>
    <div class="table-wrap"><table>
      <thead><tr><th>위치</th><th>화자</th><th>전사</th><th>상태</th></tr></thead>
      <tbody>{context_table(context_rows)}</tbody>
    </table></div>
  </details>
  <form class="review" data-event="{html.escape(event_id)}">
    <label class="check"><input type="checkbox" name="listened"> 청취함</label>
    <label>환경 인상
      <select name="env_impression">
        <option value=""></option><option value="env_ok">환경 적절</option>
        <option value="env_wrong">환경 부적절</option><option value="unsure">불확실</option>
      </select>
    </label>
    <label>실현 인상(자유 기술)<textarea name="realization_impression"></textarea></label>
    <label>음질 메모<textarea name="audio_quality_note"></textarea></label>
    <label>문맥 충분성
      <select name="context_sufficient">
        <option value=""></option><option value="yes">충분</option>
        <option value="need_more_before">앞 문맥 필요</option>
        <option value="need_more_after">뒤 문맥 필요</option>
        <option value="need_other_file">다른 파일 필요</option>
      </select>
    </label>
    <label>빠진 정보<textarea name="missing_info_note"></textarea></label>
    <label>스키마 열 제안<textarea name="schema_field_suggestion"></textarea></label>
    <label>도구·화면 메모<textarea name="tool_note"></textarea></label>
    <button type="button" class="save">새 revision 저장</button>
    <span class="saved" aria-live="polite"></span>
  </form>
</section>"""
        )
        selected_receipts.append(
            {
                "ordinal": ordinal,
                "pv_id": pv_id,
                "review_event_id": event_id,
                "phenomenon_code": code,
                "year": int(sample["year"]),
                "utt_id": sample["utt_id"],
                "package_directory": package.name,
                "target_wav_bytes": target_bytes,
                "target_wav_sha256": sha256_file(target_path),
                "context_wav_bytes": context_bytes,
                "context_wav_sha256": sha256_file(context_path),
            }
        )

    metadata_json = json_for_script(metadata)
    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>PV-A iPad 균형 14개</title>
<style>
:root {{ color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif; }}
body {{ margin: 0; background: #f3f5f8; color: #17202a; }}
header {{ background: #183153; color: white; padding: 18px max(18px, env(safe-area-inset-left)); }}
header h1 {{ margin: 0 0 8px; font-size: 1.35rem; }}
header p {{ margin: 5px 0; line-height: 1.45; }}
.toolbar {{ background: #eaf0f7; color: #17202a; padding: 14px 18px; border-bottom: 1px solid #c8d2df; }}
.toolbar label {{ display: block; margin-bottom: 10px; font-weight: 600; }}
.toolbar input {{ width: min(320px, 100%); }}
.actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
button {{ min-height: 46px; border: 0; border-radius: 9px; padding: 10px 15px; font: inherit; font-weight: 700; background: #285f9e; color: white; }}
button.secondary {{ background: #516170; }}
#progress {{ font-weight: 700; }}
main {{ max-width: 920px; margin: auto; padding: 12px; }}
.sample {{ background: white; border: 1px solid #d7dee8; border-radius: 13px; padding: 16px; margin: 14px 0; box-shadow: 0 2px 8px #18315312; }}
.sample h2 {{ margin: 0 0 5px; font-size: 1.2rem; }}
.meta {{ color: #536271; overflow-wrap: anywhere; }}
.utterance {{ font-size: 1.15rem; background: #f4efe3; padding: 12px; border-radius: 9px; }}
.audio-block {{ margin: 14px 0; }}
.audio-block label {{ display: block; font-weight: 700; margin-bottom: 5px; }}
audio {{ width: 100%; }}
.notice {{ padding: 10px; background: #fff2c9; color: #553f00; border-radius: 8px; line-height: 1.45; }}
details {{ margin: 14px 0; }}
summary {{ min-height: 36px; font-weight: 700; cursor: pointer; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; min-width: 620px; font-size: .9rem; }}
th, td {{ border-bottom: 1px solid #d8dee7; padding: 8px; text-align: left; vertical-align: top; }}
.review {{ display: grid; gap: 12px; border-top: 2px solid #d7dee8; padding-top: 14px; }}
.review label:not(.check) {{ display: grid; gap: 5px; font-weight: 650; }}
input, select, textarea {{ box-sizing: border-box; width: 100%; min-height: 44px; border: 1px solid #9caabc; border-radius: 8px; padding: 9px; font: inherit; background: white; color: #17202a; }}
textarea {{ min-height: 78px; resize: vertical; }}
.check {{ display: flex; align-items: center; gap: 10px; font-weight: 700; }}
.check input {{ width: 25px; min-height: 25px; }}
.saved {{ color: #176c42; font-weight: 700; margin-left: 8px; }}
#copy-panel {{ display: none; max-width: 920px; margin: 12px auto; padding: 12px; }}
#copy-panel textarea {{ height: 260px; font-family: ui-monospace, monospace; }}
@media (prefers-color-scheme: dark) {{
  body {{ background: #111820; color: #edf2f7; }}
  .sample {{ background: #1c2732; border-color: #3b4a58; }}
  .toolbar {{ background: #202c38; color: #edf2f7; border-color: #3b4a58; }}
  .meta {{ color: #bac6d2; }}
  .utterance {{ background: #393427; }}
  .notice {{ background: #463b18; color: #fff0b2; }}
  input, select, textarea {{ background: #111820; color: #edf2f7; border-color: #64778a; }}
  th, td {{ border-color: #3b4a58; }}
}}
</style>
</head>
<body>
<header>
  <h1>PV-A iPad 균형 14개</h1>
  <p>현상별 2개: 2020년 1개 + 2025년 1개. 원 음성 bytes를 변환 없이 포함했습니다.</p>
  <p><strong>중요:</strong> 각 항목에서 revision 저장 후, 작업을 마칠 때 JSONL 파일 저장 또는 복사용 텍스트 만들기를 실행하세요.</p>
</header>
<section class="toolbar">
  <label>검토자 <input id="reviewer" autocomplete="name" placeholder="예: ari30"></label>
  <div class="actions">
    <button type="button" id="export">JSONL 파일 저장</button>
    <button type="button" id="copy" class="secondary">복사용 JSONL 펼치기</button>
    <span id="progress" aria-live="polite"></span>
  </div>
</section>
<section id="copy-panel">
  <p>파일 저장이 안 되면 아래 내용을 전체 선택하여 메모 앱이나 Dropbox의 텍스트 파일에 붙여 넣으세요.</p>
  <textarea id="copy-text" readonly></textarea>
</section>
<main>{''.join(cards)}</main>
<script>
const META={metadata_json};
const KEY='pv_ipad_balanced14_20260820_history_v1';
const REVIEWER_KEY='pv_ipad_balanced14_20260820_reviewer_v1';
const reviewer=document.getElementById('reviewer');
function history(){{try{{const v=JSON.parse(localStorage.getItem(KEY)||'[]');return Array.isArray(v)?v:[];}}catch(e){{return [];}}}}
function setHistory(v){{localStorage.setItem(KEY,JSON.stringify(v));}}
function toJsonl(){{const h=history();return h.length?h.map(x=>JSON.stringify(x)).join('\\n')+'\\n':'';}}
function values(form){{const data={{...META[form.dataset.event]}};form.querySelectorAll('[name]').forEach(el=>data[el.name]=(el.type==='checkbox'?el.checked:el.value));data.reviewer=reviewer.value.trim();data.reviewed_at=new Date().toISOString();return data;}}
function restore(){{const h=history();const latest={{}};h.forEach(x=>latest[x.review_event_id]=x);document.querySelectorAll('form.review').forEach(form=>{{const row=latest[form.dataset.event];if(!row)return;form.querySelectorAll('[name]').forEach(el=>{{if(!(el.name in row))return;if(el.type==='checkbox')el.checked=Boolean(row[el.name]);else el.value=row[el.name]??'';}});form.querySelector('.saved').textContent='이 기기의 마지막 revision 복원됨';}});updateProgress();}}
function updateProgress(){{const h=history();const listened=new Set(h.filter(x=>x.listened===true).map(x=>x.review_event_id));document.getElementById('progress').textContent=`청취 저장 ${{listened.size}}/14 · revision ${{h.length}}개`;}}
reviewer.value=localStorage.getItem(REVIEWER_KEY)||'';
reviewer.addEventListener('input',()=>localStorage.setItem(REVIEWER_KEY,reviewer.value));
document.querySelectorAll('.save').forEach(btn=>btn.addEventListener('click',()=>{{const form=btn.closest('form');const all=history();all.push(values(form));setHistory(all);const count=all.filter(x=>x.review_event_id===form.dataset.event).length;form.querySelector('.saved').textContent=`저장됨 (revision ${{count}})`;updateProgress();}}));
document.getElementById('export').addEventListener('click',()=>{{const body=toJsonl();if(!body){{alert('저장된 revision이 없습니다.');return;}}const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([body],{{type:'application/x-ndjson;charset=utf-8'}}));const stamp=new Date().toISOString().replace(/[:.]/g,'-');a.download=`PV_REVIEW_IPAD_BALANCED14_${{stamp}}.jsonl`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}});
document.getElementById('copy').addEventListener('click',async()=>{{const body=toJsonl();if(!body){{alert('저장된 revision이 없습니다.');return;}}const panel=document.getElementById('copy-panel');const area=document.getElementById('copy-text');area.value=body;panel.style.display='block';area.focus();area.select();let copied=false;try{{if(navigator.clipboard&&window.isSecureContext){{await navigator.clipboard.writeText(body);copied=true;}}}}catch(e){{copied=false;}}alert(copied?'JSONL을 클립보드에 복사했습니다.':'아래 JSONL이 선택되었습니다. 복사 명령을 사용하세요.');}});
restore();
</script>
</body>
</html>
"""
    return document, selected_receipts, embedded_audio_bytes


def build(*, run_root: Path, output_dir: Path) -> dict[str, Any]:
    run_root = run_root.resolve(strict=True)
    approved_root = (PROJECT_ROOT / "outputs" / "pilots").resolve(strict=True)
    if run_root.parent != approved_root:
        raise RuntimeError(f"run root is outside approved pilots root: {run_root}")
    output_dir = output_dir.resolve()
    approved_work = (PROJECT_ROOT / "work").resolve(strict=True)
    if output_dir == approved_work or approved_work not in output_dir.parents:
        raise RuntimeError(f"iPad derivative output must stay under work: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    if partial.exists():
        raise FileExistsError(f"existing partial output is preserved: {partial}")

    run_manifest_path = run_root / "PV_MANIFEST.json"
    audit_path = run_root / "audit" / "PV_AUDIT.json"
    samples_path = run_root / "samples" / "PV_SAMPLES.csv"
    events_path = run_root / "samples" / "PV_REVIEW_EVENTS.csv"
    run_manifest = load_json(run_manifest_path)
    audit = load_json(audit_path)
    if run_manifest.get("status") != "passed_listening_may_begin":
        raise RuntimeError("PV run is not passed for listening")
    if audit.get("passed") is not True or audit.get("listening_gate") != "open":
        raise RuntimeError("PV independent audit is not open")
    selected = pick_balanced_samples(read_csv(samples_path))
    document, selected_receipts, audio_bytes = build_html(
        selected=selected,
        events=read_csv(events_path),
        packages=package_map(run_root / "bundle"),
    )

    partial.mkdir(parents=True)
    html_path = partial / HTML_NAME
    html_partial = partial / f"{HTML_NAME}.partial"
    html_partial.write_text(document, encoding="utf-8", newline="\n")
    os.replace(html_partial, html_path)
    receipt = {
        "schema_version": "pv_ipad_balanced14_build.v1",
        "status": "built_self_contained_ipad_review_no_realization_judgement",
        "recorded_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "source_run_root": str(run_root),
        "source_run_manifest_sha256": sha256_file(run_manifest_path),
        "source_audit_sha256": sha256_file(audit_path),
        "source_audit_passed": True,
        "selection": {
            "phenomenon_order": PHENOMENON_ORDER,
            "years_per_phenomenon": ENDPOINT_YEARS,
            "physical_packages": len(selected_receipts),
            "primary_review_events": len(selected_receipts),
            "records": selected_receipts,
        },
        "output": {
            "path": HTML_NAME,
            "bytes": html_path.stat().st_size,
            "sha256": sha256_file(html_path),
            "embedded_source_wav_bytes": audio_bytes,
        },
        "capabilities": {
            "embedded_target_and_context_audio": True,
            "browser_local_revision_history": True,
            "jsonl_download": True,
            "jsonl_visible_copy_fallback": True,
        },
        "safety": {
            "source_files_modified": False,
            "audio_transcoded": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "existing_output_overwritten": False,
        },
    }
    receipt_path = partial / RECEIPT_NAME
    receipt_partial = partial / f"{RECEIPT_NAME}.partial"
    receipt_partial.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(receipt_partial, receipt_path)
    os.replace(partial, output_dir)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    try:
        result = build(run_root=args.run_root, output_dir=args.output_dir)
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
