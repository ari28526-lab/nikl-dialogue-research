"""Build the approved UI-only PV reviewer v2.1 derivative.

The source is the independently audited, self-contained reviewer v2 HTML.
This builder adds only the accepted R01/R06/R07/R08/R09 usability fixes.  It
does not scan the corpus, change audio, judge realization, or alter the v2 root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "pv_seven_phenomena_reviewer_v2_20260822"
)
DEFAULT_SAMPLES_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "pv_seven_phenomena_20260819"
    / "samples"
    / "PV_SAMPLES.csv"
)
DEFAULT_APPROVAL_REVIEW = (
    PROJECT_ROOT
    / "docs"
    / "reviews"
    / "incoming"
    / "EXTERNAL_REVIEW_pv_reviewer_v2_research_tool_claude_20260822.md"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "pv_seven_phenomena_reviewer_v2_1_20260822"
)

SOURCE_HTML = "PV_REVIEWER_V2.html"
SOURCE_BUILD = "PV_REVIEWER_V2_BUILD.json"
SOURCE_IMPORTED = "PV_REVIEWER_V1_IMPORTED.jsonl"
SOURCE_DIALOGUES = "PV_REVIEWER_V2_DIALOGUES.jsonl"
SOURCE_AUDIT = Path("audit") / "PV_REVIEWER_V2_AUDIT.json"
SOURCE_MANIFEST = "PV_REVIEWER_V2_SHA256_MANIFEST.csv"

HTML_NAME = "PV_REVIEWER_V2_1.html"
BUILD_NAME = "PV_REVIEWER_V2_1_BUILD.json"
IMPORTED_NAME = "PV_REVIEWER_V2_1_IMPORTED_BASE.jsonl"
DIALOGUE_NAME = "PV_REVIEWER_V2_1_DIALOGUES.jsonl"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def extract_json_constant(document: str, name: str, next_name: str) -> Any:
    pattern = rf"const {re.escape(name)}=(.*?);\nconst {re.escape(next_name)}="
    match = re.search(pattern, document, flags=re.DOTALL)
    if not match:
        raise RuntimeError(f"HTML JSON constant missing: {name}")
    return json.loads(match.group(1))


def load_highlight_metadata(
    samples_csv: Path, pv_ids: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload = samples_csv.read_bytes()
    with samples_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = {row["pv_id"]: row for row in csv.DictReader(stream)}
    missing = sorted(set(pv_ids) - set(rows))
    if missing:
        raise RuntimeError(f"selected pv_id missing from frozen samples: {missing}")
    result: dict[str, dict[str, Any]] = {}
    highlighted_tokens = 0
    for pv_id in pv_ids:
        row = rows[pv_id]
        indices = json.loads(row["target_word_indices_json"])
        labels = json.loads(row["target_word_labels_json"])
        if not isinstance(indices, list) or not isinstance(labels, list):
            raise RuntimeError(f"{pv_id}: target highlight metadata is not a list")
        if len(indices) != len(labels) or not indices:
            raise RuntimeError(f"{pv_id}: target index/label cardinality mismatch")
        tokens = row["active_form"].split()
        if any(not isinstance(index, int) or index < 1 or index > len(tokens) for index in indices):
            raise RuntimeError(f"{pv_id}: target word index outside active_form")
        measured = [tokens[index - 1] for index in indices]
        result[pv_id] = {
            "target_word_indices": indices,
            "target_word_labels": labels,
            "target_word_tokens_measured": measured,
        }
        highlighted_tokens += len(indices)
    return result, {
        "path": str(samples_csv),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "samples": len(result),
        "highlighted_tokens": highlighted_tokens,
    }


def transform_html(
    source: str, highlight_by_pv: dict[str, dict[str, Any]]
) -> tuple[str, dict[str, Any]]:
    samples = extract_json_constant(source, "SAMPLES", "DIALOGUES")
    if len(samples) != 14 or len({row["pv_id"] for row in samples}) != 14:
        raise RuntimeError("source v2 SAMPLES contract is not 14 unique items")
    for sample in samples:
        sample.update(highlight_by_pv[sample["pv_id"]])
    samples_json = json.dumps(samples, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    document = re.sub(
        r"const SAMPLES=.*?;\nconst DIALOGUES=",
        lambda _: f"const SAMPLES={samples_json};\nconst DIALOGUES=",
        source,
        count=1,
        flags=re.DOTALL,
    )
    if document == source:
        raise RuntimeError("SAMPLES enrichment replacement did not occur")

    document = replace_once(
        document,
        "<title>PV 검토 화면 v2</title>",
        "<title>PV 검토 화면 v2.1</title>",
        "document title",
    )
    document = replace_once(
        document,
        "<header><h1>PV 검토 화면 v2 · 균형 14개</h1>",
        "<header><h1>PV 검토 화면 v2.1 · 균형 14개</h1>",
        "visible title",
    )
    document = replace_once(
        document,
        ".utterance{font-size:1.25rem;background:#f4efe2;padding:13px;border-radius:9px}",
        ".utterance{font-size:1.25rem;background:#f4efe2;padding:13px;border-radius:9px}"
        ".utterance mark{background:#ffd666;color:#17212b;border-radius:4px;padding:.05em .16em;box-shadow:0 0 0 2px #a65d00}",
        "target highlight CSS",
    )
    document = replace_once(
        document,
        "<label>판단 확신도<select name=\"judgement_confidence\">",
        "<label>들린 형식·실현 인상에 대한 확신도<select name=\"judgement_confidence\">",
        "confidence label",
    )

    old_latest = (
        "function latestByEvent(rows){const latest={};rows.forEach((row,index)=>"
        "{latest[row.review_event_id]={row,index};});return Object.fromEntries("
        "Object.entries(latest).map(([k,v])=>[k,v.row]));}"
    )
    new_latest = (
        "function reviewedAtMs(row){const value=Date.parse(row&&row.reviewed_at||'');"
        "return Number.isFinite(value)?value:Number.NEGATIVE_INFINITY;}\n"
        "function latestByEvent(rows){const latest={};rows.forEach((row,index)=>{const key=row.review_event_id;"
        "const candidate={row,index,time:reviewedAtMs(row)};const previous=latest[key];"
        "if(!previous||candidate.time>previous.time||(candidate.time===previous.time&&index>previous.index))"
        "latest[key]=candidate;});return Object.fromEntries(Object.entries(latest).map(([k,v])=>[k,v.row]));}\n"
        "function canDiscardDirty(isDirty,confirmFn){return !isDirty||Boolean(confirmFn('저장하지 않은 입력이 있습니다. 이동하면 사라집니다. 버리고 이동할까요?'));}"
    )
    document = replace_once(document, old_latest, new_latest, "latest revision logic")

    old_filter = (
        "function filterIds(query,priority){const q=String(query||'').trim().toLowerCase();"
        "return SAMPLES.filter(s=>(priority==='all'||s.priority_tier===priority)&&(!q||"
        "[s.pv_id,s.phenomenon_code,s.phenomenon_label,s.year,s.active_form,s.utt_id]"
        ".join(' ').toLowerCase().includes(q))).map(s=>s.pv_id);}"
    )
    new_filter = old_filter + "\n" + (
        "function highlightActiveForm(sample){const targets=new Set((sample.target_word_indices||[]).map(Number));"
        "let wordIndex=0;return String(sample.active_form||'').split(/(\\s+)/).map(part=>{"
        "if(/^\\s+$/.test(part))return part;wordIndex+=1;const safe=escapeHtml(part);"
        "return targets.has(wordIndex)?`<mark data-word-index=\"${wordIndex}\">${safe}</mark>`:safe;}).join('');}\n"
        "function morphStatusText(status){const labels={direct_from_match_evidence:'기존 검색 근거에서 직접 표시했습니다.',"
        "linked_exact_eojeol_within_cap:'형태소 분석 어절과 정확히 연결했습니다.',"
        "unavailable_form_tagged_count_mismatch_zero_drop:'표기 어절 수와 형태소 분석 어절 수가 달라 형태소를 연결하지 않았습니다. 후보는 삭제 없이 유지됩니다.',"
        "missing_linked_eojeol_within_cap_zero_drop:'승인된 상한 안에서 연결 형태소를 찾지 못했습니다. 후보는 삭제 없이 유지됩니다.'};"
        "return labels[status]||`상태 코드는 ${status||'미기록'}입니다.`;}\n"
        "function morphBoundaryLabel(kind){return kind==='orth_contraction_probe'?'축약 음절':'경계';}"
    )
    document = replace_once(document, old_filter, new_filter, "highlight/status helpers")

    old_api = (
        "globalThis.PV_REVIEWER_V2_TEST_API={SAMPLES,BASE_HISTORY,LITERATURE,BUILD_META,"
        "parseJsonl,duplicateCount,latestByEvent,makeRevision,filterIds,toJsonl,semanticFingerprint};"
    )
    new_api = (
        "globalThis.PV_REVIEWER_V2_TEST_API={SAMPLES,BASE_HISTORY,LITERATURE,BUILD_META,"
        "parseJsonl,duplicateCount,latestByEvent,makeRevision,filterIds,toJsonl,semanticFingerprint,"
        "reviewedAtMs,canDiscardDirty,highlightActiveForm,morphStatusText,morphBoundaryLabel};"
    )
    document = replace_once(document, old_api, new_api, "test API")

    document = replace_once(
        document,
        "let currentId=SAMPLES[0].pv_id;let visibleIds=SAMPLES.map(x=>x.pv_id);let viewedPanels=new Set(['pm2']);",
        "let currentId=SAMPLES[0].pv_id;let visibleIds=SAMPLES.map(x=>x.pv_id);let viewedPanels=new Set(['pm2']);let formDirty=false;",
        "dirty state",
    )
    document = replace_once(
        document,
        "btn.addEventListener('click',()=>setActive(btn.dataset.pv))",
        "btn.addEventListener('click',()=>requestActivate(btn.dataset.pv))",
        "candidate navigation guard",
    )

    old_render_morph = (
        "function renderMorph(s){const d=s.target_display;const parts=(d.segments||[]).map(seg=>"
        "`<span class=\"morph\"><strong>${escapeHtml(seg.surface||seg.units||'형태소 미상')}</strong> / "
        "${escapeHtml(seg.pos||'POS 미상')}<br><small>초점 ${escapeHtml(seg.focus_unit||seg.units||'—')}</small></span>`);"
        "byId('morph-display').innerHTML=parts.join('<span class=\"boundary\">│</span>')+"
        "`<span class=\"boundary\">경계 ${escapeHtml(d.boundary||'—')}</span>`;"
        "byId('morph-limit').textContent=`형태소 표시 상태: ${d.status}. 이 표시는 검색 환경 근거이며 음향적 경계나 실제 실현 판정이 아닙니다.`;}"
    )
    new_render_morph = (
        "function renderMorph(s){const d=s.target_display;const parts=(d.segments||[]).map(seg=>"
        "`<span class=\"morph\"><strong>${escapeHtml(seg.surface||seg.units||'형태소 미상')}</strong> / "
        "${escapeHtml(seg.pos||'POS 미상')}<br><small>초점 ${escapeHtml(seg.focus_unit||seg.units||'—')}</small></span>`);"
        "byId('morph-display').innerHTML=parts.join('<span class=\"boundary\">│</span>')+"
        "`<span class=\"boundary\">${morphBoundaryLabel(d.kind)} ${escapeHtml(d.boundary||'—')}</span>`;"
        "byId('morph-limit').textContent=`${morphStatusText(d.status)} [${d.status}] 이 표시는 검색 환경 근거이며 음향적 경계나 실제 실현 판정이 아닙니다.`;}"
    )
    document = replace_once(document, old_render_morph, new_render_morph, "morph status UI")

    document = replace_once(
        document,
        "byId('active-form').textContent=s.active_form;",
        "byId('active-form').innerHTML=highlightActiveForm(s);",
        "target highlight rendering",
    )
    document = replace_once(
        document,
        "byId('saved').textContent=row?'기존 최신 revision을 복원했습니다.':'';}",
        "byId('saved').textContent=row?'기존 최신 revision을 복원했습니다.':'';formDirty=false;}",
        "restore dirty reset",
    )

    old_navigation = (
        "function applyFilter(){visibleIds=filterIds(byId('candidate-search').value,byId('priority-filter').value);"
        "if(visibleIds.length&&!visibleIds.includes(currentId))currentId=visibleIds[0];renderCandidateButtons();"
        "if(visibleIds.length)setActive(currentId);}\n"
        "function move(delta){const list=visibleIds.length?visibleIds:SAMPLES.map(x=>x.pv_id);"
        "let index=list.indexOf(currentId);index=(index+delta+list.length)%list.length;"
        "setActive(list[index]);window.scrollTo({top:0,behavior:'smooth'});}"
    )
    new_navigation = (
        "function requestActivate(id){if(!SAMPLE_MAP[id]||id===currentId)return true;"
        "if(!canDiscardDirty(formDirty,message=>confirm(message)))return false;formDirty=false;setActive(id);return true;}\n"
        "function applyFilter(){visibleIds=filterIds(byId('candidate-search').value,byId('priority-filter').value);"
        "renderCandidateButtons();if(visibleIds.length&&!visibleIds.includes(currentId)&&!formDirty)setActive(visibleIds[0]);}\n"
        "function move(delta){const list=visibleIds.length?visibleIds:SAMPLES.map(x=>x.pv_id);"
        "let index=list.indexOf(currentId);if(index<0)index=0;index=(index+delta+list.length)%list.length;"
        "if(requestActivate(list[index]))window.scrollTo({top:0,behavior:'smooth'});}"
    )
    document = replace_once(document, old_navigation, new_navigation, "guarded navigation")

    old_bindings = (
        "byId('candidate-search').addEventListener('input',applyFilter);byId('priority-filter').addEventListener('change',applyFilter);"
        "byId('prev').addEventListener('click',()=>move(-1));byId('next').addEventListener('click',()=>move(1));"
    )
    new_bindings = old_bindings + (
        "form.addEventListener('input',()=>{formDirty=true;byId('saved').textContent='저장하지 않은 변경이 있습니다.';});"
        "form.addEventListener('change',()=>{formDirty=true;byId('saved').textContent='저장하지 않은 변경이 있습니다.';});"
        "window.addEventListener('beforeunload',event=>{if(formDirty){event.preventDefault();event.returnValue='';}});"
    )
    document = replace_once(document, old_bindings, new_bindings, "dirty listeners")
    document = replace_once(
        document,
        "setLocalHistory(local);byId('saved').textContent=`저장됨 · 이 표본 revision ${row.revision_seq}`;",
        "setLocalHistory(local);formDirty=false;byId('saved').textContent=`저장됨 · 이 표본 revision ${row.revision_seq}`;",
        "save dirty reset",
    )
    document = replace_once(
        document,
        "byId('import-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{",
        "byId('import-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;"
        "if(!canDiscardDirty(formDirty,message=>confirm(message))){event.target.value='';byId('import-status').textContent='저장하지 않은 입력을 보존하기 위해 가져오기를 취소했습니다.';return;}"
        "formDirty=false;try{",
        "import dirty guard",
    )

    required_new = (
        "PV 검토 화면 v2.1",
        "highlightActiveForm",
        "canDiscardDirty",
        "reviewedAtMs",
        "unavailable_form_tagged_count_mismatch_zero_drop",
        "들린 형식·실현 인상에 대한 확신도",
    )
    if any(token not in document for token in required_new):
        raise RuntimeError("one or more v2.1 behavior markers are missing")
    return document, {
        "samples": len(samples),
        "samples_with_highlight_metadata": sum(
            bool(row.get("target_word_indices")) for row in samples
        ),
        "highlighted_tokens": sum(
            len(row.get("target_word_indices", [])) for row in samples
        ),
        "accepted_recommendations": ["R01", "R06", "R07", "R08", "R09"],
    }


def build(
    *,
    source_dir: Path,
    samples_csv: Path,
    approval_review: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source_dir = source_dir.resolve(strict=True)
    samples_csv = samples_csv.resolve(strict=True)
    approval_review = approval_review.resolve(strict=True)
    output_dir = output_dir.resolve()
    approved_parent = (PROJECT_ROOT / "outputs" / "pilots").resolve(strict=True)
    if output_dir.parent != approved_parent:
        raise RuntimeError(f"v2.1 output must be a direct pilots derivative: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    if partial.exists():
        raise FileExistsError(f"existing partial output is preserved: {partial}")

    source_html_path = source_dir / SOURCE_HTML
    source_build_path = source_dir / SOURCE_BUILD
    source_imported_path = source_dir / SOURCE_IMPORTED
    source_dialogue_path = source_dir / SOURCE_DIALOGUES
    source_audit_path = source_dir / SOURCE_AUDIT
    source_manifest_path = source_dir / SOURCE_MANIFEST
    source_build = json.loads(source_build_path.read_text(encoding="utf-8"))
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
    if source_build.get("status") != "built_pending_independent_audit":
        raise RuntimeError("source v2 build status is not approved for derivation")
    if source_audit.get("passed") is not True or source_audit.get("errors") != []:
        raise RuntimeError("source v2 independent audit is not passed cleanly")
    source_html_bytes = source_html_path.read_bytes()
    expected_source_sha = source_build.get("output", {}).get("html", {}).get("sha256")
    if sha256_bytes(source_html_bytes) != expected_source_sha:
        raise RuntimeError("source v2 HTML SHA differs from build receipt")

    approval_text = approval_review.read_text(encoding="utf-8")
    for marker in ("R01", "R06", "R07", "R08", "R09", "CONDITIONAL GO"):
        if marker not in approval_text:
            raise RuntimeError(f"approval review marker missing: {marker}")

    source_document = source_html_bytes.decode("utf-8")
    source_samples = extract_json_constant(source_document, "SAMPLES", "DIALOGUES")
    pv_ids = [str(row["pv_id"]) for row in source_samples]
    highlight_by_pv, highlight_receipt = load_highlight_metadata(samples_csv, pv_ids)
    document, transform_receipt = transform_html(source_document, highlight_by_pv)

    partial.mkdir(parents=True)
    html_path = partial / HTML_NAME
    imported_path = partial / IMPORTED_NAME
    dialogue_path = partial / DIALOGUE_NAME
    write_text_atomic(html_path, document)
    write_bytes_atomic(imported_path, source_imported_path.read_bytes())
    write_bytes_atomic(dialogue_path, source_dialogue_path.read_bytes())

    receipt = {
        "schema_version": "pv_reviewer_v2_1_build.v1",
        "status": "built_pending_independent_audit",
        "recorded_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "approval": {
            "user_go_date": "2026-08-22",
            "scope": ["R01", "R06", "R07", "R08", "R09"],
            "review_path": str(approval_review),
            "review_sha256": sha256_file(approval_review),
            "r03_batch_builder_in_scope": False,
            "r04_scan_contract_change_in_scope": False,
        },
        "source_v2": {
            "root": str(source_dir),
            "html": {
                "path": str(source_html_path),
                "bytes": len(source_html_bytes),
                "sha256": sha256_bytes(source_html_bytes),
            },
            "build_sha256": sha256_file(source_build_path),
            "audit_path": str(source_audit_path),
            "audit_sha256": sha256_file(source_audit_path),
            "audit_passed": True,
            "manifest_sha256": sha256_file(source_manifest_path),
            "imported_jsonl_sha256": sha256_file(source_imported_path),
            "dialogue_jsonl_sha256": sha256_file(source_dialogue_path),
        },
        "highlight_source": highlight_receipt,
        "transform": transform_receipt,
        "output": {
            "html": {
                "path": HTML_NAME,
                "bytes": html_path.stat().st_size,
                "sha256": sha256_file(html_path),
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
            "source_v2_modified": False,
            "source_corpus_scanned": False,
            "source_files_modified": False,
            "audio_payload_changed": False,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "mfa_run": False,
            "koina_run": False,
            "wav2vec2_run": False,
            "r03_batch_builder_implemented": False,
            "r04_scan_contract_changed": False,
            "existing_output_overwritten": False,
        },
    }
    write_text_atomic(
        partial / BUILD_NAME,
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
    )
    os.replace(partial, output_dir)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--samples-csv", type=Path, default=DEFAULT_SAMPLES_CSV)
    parser.add_argument("--approval-review", type=Path, default=DEFAULT_APPROVAL_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    try:
        receipt = build(
            source_dir=args.source_dir,
            samples_csv=args.samples_csv,
            approval_review=args.approval_review,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
