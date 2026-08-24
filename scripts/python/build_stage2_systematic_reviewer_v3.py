#!/usr/bin/env python3
"""Build the append-only Stage2 systematic researcher reviewer v3.

The builder verifies and copies reviewer v2, refreshes its literature payload
from the append-only claim ledger, and adds researcher-first notes, factor maps,
sample-balance warnings, a safe localhost Praat launcher, and a Claude Cowork
handoff.  It never edits v1/v2, source corpus files, or researcher JSONL.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from build_stage2_two_hour_seven_phenomena_reviewer import (
    EXPECTED_CODES,
    extract_json_script,
    literature_payload,
    read_jsonl,
    verify_package_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_ROOT = PROJECT_ROOT / "outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823"
DEFAULT_SOURCE = PILOT_ROOT / "researcher_review_package_v2"
DEFAULT_OUTPUT = PILOT_ROOT / "researcher_review_package_v3_systematic"
DEFAULT_CARDS = PROJECT_ROOT / "config/phenomenon_scope_cards_candidate_v2_20260824.jsonl"
DEFAULT_FACTORS = PROJECT_ROOT / "config/phenomenon_factor_maps_candidate_v1_20260824.json"
DEFAULT_CLAIMS = PROJECT_ROOT / "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl"
EXPECTED_SAMPLE_COUNT = 84


class BuildError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_for_html(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def replace_once(document: str, old: str, new: str, label: str) -> str:
    count = document.count(old)
    require(count == 1, f"expected one {label} anchor, measured {count}")
    return document.replace(old, new, 1)


def replace_json_script(document: str, element_id: str, value: Any) -> str:
    pattern = re.compile(
        rf'(<script id="{re.escape(element_id)}" type="application/json">).*?(</script>)',
        flags=re.DOTALL,
    )
    replaced, count = pattern.subn(
        lambda match: match.group(1) + json_for_html(value) + match.group(2), document, count=1
    )
    require(count == 1, f"embedded JSON script replacement failed: {element_id}")
    return replaced


def load_factor_maps(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = value.get("phenomena", [])
    require([row.get("phenomenon_code") for row in rows] == EXPECTED_CODES, "factor-map code order")
    return {str(row["phenomenon_code"]): row for row in rows}


def sample_audit(samples: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(samples) == EXPECTED_SAMPLE_COUNT, f"sample count: {len(samples)}")
    result: dict[str, Any] = {}
    for code in EXPECTED_CODES:
        rows = [row for row in samples if row.get("phenomenon_code") == code]
        roles = Counter(str(row.get("population_role", "missing")) for row in rows)
        scopes = Counter(str(row.get("environment_scope", "missing")) for row in rows)
        queries = Counter(str(row.get("query_id", "missing")) for row in rows)
        warning = "현재 12건은 탐색 표본이며 형태소·품사·음운·운율 요인이 균형화된 확정 표본이 아닙니다."
        if code == "PT":
            warning += " 특히 12건 모두 compoundness probe이고 대부분 단일 NNG 내부 음절쌍이므로 저해음 뒤 기준층·합성어 변이층의 비교 표본으로 쓰면 안 됩니다."
        elif code == "NAN":
            warning += " 특히 /ㄴ/ 중심이며 /ㅁ/ 기준층과 형태소·품사 층화가 빠져 있습니다. 어절 간 사례는 운율경계 탐색층으로만 봅니다."
        elif code == "LLN":
            warning += " /ㄹ+ㄴ/에 크게 치우쳐 있어 /ㄴ+ㄹ/ 방향 비교가 필요합니다."
        result[code] = {
            "sample_count": len(rows),
            "population_roles": dict(sorted(roles.items())),
            "environment_scopes": dict(sorted(scopes.items())),
            "query_ids": dict(sorted(queries.items())),
            "warning": warning,
            "status": "exploratory_not_balanced",
        }
    return result


EXTRA_CSS = r'''
.research-first{border:2px solid #2b6c9d;border-radius:11px;padding:.85rem;background:#f3f9fc;grid-column:1/-1}.research-first legend{font-weight:800;color:#164f7a;padding:0 .35rem}.factor-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem}.factor-box{border:1px solid var(--line);border-radius:8px;padding:.6rem;background:#f8fafb}.factor-box h4{margin:.1rem 0}.factor-box ul{margin:.3rem 0;padding-left:1.25rem}.scope-family{border-left:4px solid #2b6c9d;padding:.45rem .65rem;margin:.45rem 0;background:#eef7fc}.sample-audit{background:#ffe8e4;border:2px solid #a14c40;padding:.75rem;border-radius:9px}.thoughts td{min-width:130px;white-space:pre-wrap}.phenomenon-only{grid-column:1/-1;border:1px dashed #7b8d99;border-radius:9px;padding:.65rem;background:#fff}.praat-live{background:#176742}.status-error{color:#8b2d23;font-weight:700}
@media(max-width:850px){.factor-grid{grid-template-columns:1fr}}
'''


LITERATURE_PANEL = r'''<section class="panel" id="literature-panel"><h2 id="literature-title"></h2><div id="schedule" class="warning"></div><p id="definition"></p><p id="literature-path" class="meta"></p><div id="sampling-warning" class="sample-audit"></div><details open><summary>연구 질문·요인 지도</summary><div id="research-map"></div></details><details open><summary>이 파일럿의 범위·제외·혼란변수</summary><div id="scope-contract"></div></details><details><summary>문헌 주장과 한계 — 20분 읽기</summary><div id="claims"></div></details><label>현상 전체 문헌 메모<textarea id="phenomenon-lit-note" style="width:100%;min-height:100px" placeholder="떠오르는 생각을 먼저 자유롭게 적고, 아래 사례 기록과 4시간 문헌 종합 템플릿에서 근거·반례·한계를 분리하세요."></textarea></label><div class="actions"><button type="button" id="phenomenon-summary-save">현상 요약 저장</button><span id="phenomenon-summary-status" class="saved"></span></div><p class="meta">현상 요약은 사례 행과 분리된 탐색 전용 revision입니다. 연구자 승인 전에는 동결된 질의·설정·정식 ledger를 자동 변경하지 않습니다.</p></section>'''


TEXTGRID_PANEL = r'''<section class="panel"><details open><summary>TextGrid 미리보기와 실제 Praat 작업</summary><p class="warning">아래 tier 그림은 위치를 빠르게 확인하는 읽기 전용 미리보기일 뿐입니다. 경계를 판정·수정하려면 실제 Praat에서 WAV와 praat_work TextGrid를 함께 여세요.</p><p id="textgrid-meta" class="meta"></p><div id="tiers"></div><p><a id="source-textgrid-link" href="">원본 보존 복사본</a> · <a id="work-textgrid-link" href="">Praat 수정 작업본</a></p><p id="praat-command" class="copytext"></p><div class="actions"><button type="button" class="praat-live" id="open-praat-live">실제 Praat에서 이 사례 열기</button><button type="button" class="ghost" id="copy-praat">Praat 명령 복사</button><span id="open-praat-live-status" class="meta"></span></div><p class="meta">초록색 버튼은 START_REVIEWER_WITH_PRAAT.cmd로 화면을 열었을 때만 작동합니다. Praat가 설치되어 있지 않으면 경로 안내만 표시하며 자동 설치하지 않습니다.</p></details></section>'''


RESEARCH_FIELDS = r'''
<fieldset class="research-first"><legend>내 생각 먼저 — 사례 하나의 연구 메모</legend><p class="meta">정답을 맞히는 칸이 아닙니다. 관찰과 해석을 분리하고, 나중에 바뀔 수 있는 생각을 revision으로 남깁니다.</p><div class="factor-grid">
<label>내가 먼저 본 것<textarea name="research_observation" placeholder="무엇이 들리거나 보였는가? 해석 전 관찰"></textarea></label>
<label>환경 가설<textarea name="research_environment_hypothesis" placeholder="어떤 음운 환경이 핵심이라고 생각하는가?"></textarea></label>
<label>형태론 가설<textarea name="research_morphology_hypothesis" placeholder="형태소 원본·표면형·경계·품사 분석과 이상점"></textarea></label>
<label>운율 가설<textarea name="research_prosody_hypothesis" placeholder="AP/IP·휴지·경계음조·장음화·초점에 대한 생각"></textarea></label>
<label>문헌 연결<textarea name="research_literature_link" placeholder="지지·반례·적용 범위·떠오르는 저자/문헌"></textarea></label>
<label>대안 설명<textarea name="research_alternative_explanation" placeholder="자료 오류·속도·어휘화 등 다른 설명"></textarea></label>
<label class="wide">다음 행동<textarea name="research_next_action" placeholder="재청취, Praat, 형태소 재분석, 원문 페이지 확인, 새 표본 요청 등"></textarea></label>
</div><div class="factor-grid">
<label>형태소 경계 유형<input name="factor_morph_boundary_type" placeholder="형태소 내부 / 어간+어미 / 체언+조사 / 파생 / 합성 / 어절 간"></label>
<label>좌우 품사 구성<input name="factor_pos_configuration" placeholder="예: VV+EC, NNG+NNG"></label>
<label>운율 경계 잠정값<input name="factor_prosodic_boundary" placeholder="same AP / AP / IP / pause / unclear"></label>
<label>과제·장르<input name="factor_task_genre" placeholder="대화 / 독백 / 낭독 / 기타"></label>
<label>자료 품질<select name="factor_data_quality"><option value=""></option><option value="good">양호</option><option value="usable_with_limit">제한 있으나 사용 가능</option><option value="poor">판정 곤란</option><option value="unclear">불확실</option></select></label>
<label>복수 membership<input name="factor_memberships" placeholder="쉼표로 복수 기록"></label>
</div>
<div id="pt-specific" class="phenomenon-only"><strong>PT 전용 — 서로 지우지 말고 각각 판정</strong><div class="factor-grid"><label>저해음 뒤 경음화 membership<select name="pt_post_obstruent_membership"><option value=""></option><option value="yes">해당</option><option value="no">비해당</option><option value="unclear">불확실</option></select></label><label>합성어 경음화 membership<select name="pt_compound_tensification_membership"><option value=""></option><option value="yes">해당</option><option value="no">비해당</option><option value="unclear">불확실</option></select></label><label class="wide">사이시옷 분석<select name="pt_sai_siot_analysis"><option value=""></option><option value="required">필요</option><option value="possible">가능</option><option value="excluded">배제</option><option value="unclear">불확실</option></select></label></div></div>
<div id="nan-specific" class="phenomenon-only"><strong>NAN 전용 — 필수 기준층과 운율 탐색층 분리</strong><div class="factor-grid"><label>후행 비음<select name="nan_c2_nasal"><option value=""></option><option value="n">/ㄴ/</option><option value="m">/ㅁ/</option><option value="inserted_n">삽입된 /n/</option><option value="unclear">불확실</option></select></label><label>연구 층<select name="nan_baseline_or_prosody"><option value=""></option><option value="mandatory_intra_baseline">어절 내부 기준층</option><option value="interword_prosody_probe">어절 간 운율 탐색층</option><option value="derived_n_overlap">ㄴ삽입 중첩층</option><option value="unclear">불확실</option></select></label></div></div>
</fieldset>
'''


THOUGHTS_PANEL = r'''<section class="panel"><h2>이 현상에서 내가 적은 생각 모아보기</h2><p class="meta">불러온 기록과 이 브라우저의 저장 기록을 합친 뒤, 사례별 가장 최근 revision만 보여 줍니다.</p><div class="actions"><button id="refresh-thoughts" type="button">표 새로고침</button><button id="export-thoughts" class="secondary" type="button">현상 메모 Markdown 저장</button></div><div class="tablewrap"><table class="thoughts"><thead><tr><th>사례·단어</th><th>관찰</th><th>형태론 가설</th><th>운율 가설</th><th>실현</th><th>문헌 연결</th><th>다음 행동</th></tr></thead><tbody id="thoughts-body"></tbody></table></div></section>'''


RENDER_LITERATURE_JS = r'''function renderResearchMap(){const f=FACTOR_MAPS[currentCode];if(!f){byId('research-map').innerHTML='<p class="empty">요인 지도 없음</p>';return}const questions=(f.research_questions||[]).map(x=>`<li><strong>${esc(x.id)}</strong> ${esc(x.question)}</li>`).join('');const scopes=(f.scope_families||[]).map(x=>`<div class="scope-family"><strong>${esc(x.id)} · ${esc(x.label)}</strong><br>${esc(x.description)}</div>`).join('');const factors=Object.entries(f.factor_dimensions||{}).map(([k,v])=>`<div class="factor-box"><h4>${esc(k)}</h4><p>${esc((v||[]).join(' · '))}</p></div>`).join('');const sampling=(f.sampling_requirements||[]).map(x=>`<li>${esc(x)}</li>`).join('');byId('research-map').innerHTML=`<h3>질문</h3><ol>${questions}</ol><h3>모집단·범위 층</h3>${scopes}<h3>기록할 요인</h3><div class="factor-grid">${factors}</div><h3>다음 균형 표본의 요구사항</h3><ul>${sampling}</ul>`}
function renderLiterature(){const l=LITERATURE[currentCode];byId('literature-title').textContent=`${currentCode} · ${l.label_ko}`;byId('definition').textContent=l.definition_summary;byId('literature-path').textContent=`문헌 종합 초안: ${l.literature_synthesis_path} · 근거 수준 ${l.literature_evidence_level}`;byId('schedule').innerHTML=l.pilot_schedule.map(x=>`<strong>${x.minutes}분</strong> ${esc(x.activity)}`).join(' → ');byId('sampling-warning').textContent=SAMPLE_AUDIT[currentCode]?.warning||'현재 표본의 균형을 별도 확인하세요.';renderResearchMap();const populations=Object.entries(l.population_contract).map(([k,rows])=>`<h4>${esc(k)}</h4><ul>${rows.map(x=>`<li><strong>${esc(x.condition_id)}</strong> ${esc(x.description)} · 우선 ${esc(x.priority)} · ${esc((x.evidence_refs||[]).join(', '))}</li>`).join('')}</ul>`).join('');const confounds=`<h4>혼란변수</h4><ul>${l.confounds.map(x=>`<li>${esc(x.name)} · ${esc((x.evidence_refs||[]).join(', '))}</li>`).join('')}</ul><h4>근거 한계</h4><ul>${l.evidence_limits.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h4>열린 질문</h4><ul>${l.open_questions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;byId('scope-contract').innerHTML=populations+confounds;byId('claims').innerHTML=l.claims.map(c=>`<div class="claim"><strong>${esc(c.claim_id)} · ${esc(c.source_id)}</strong><p>${esc(c.claim_ko)}</p><p><b>적용:</b> ${esc(c.applies_when)}</p><p><b>확립하지 않는 것:</b> ${esc(c.does_not_establish)}</p><p><b>검토 질문:</b> ${esc(c.review_question)}</p><p class="meta">${esc(c.citation)} · 인쇄면 ${esc(c.printed_page??'—')} / PDF면 ${esc(c.pdf_page??'—')}</p></div>`).join('')+`<p class="meta">source-only refs: ${esc(l.source_only_refs.join(', ')||'없음')}</p>`;const key=STORAGE_KEY+'_lit_'+currentCode;const localNote=localStorage.getItem(key);const importedSummary=latestImportedSummary(currentCode);const sampleNote=latestSampleNote(currentCode);byId('phenomenon-lit-note').value=localNote!==null?localNote:(importedSummary?.phenomenon_literature_note??sampleNote?.phenomenon_literature_note??'');const latestSummary=newest(summaryRows(currentCode));byId('phenomenon-summary-status').textContent=latestSummary?.reviewed_at?`최근 현상 요약 ${latestSummary.reviewed_at}`:'';renderThoughts()}'''


THOUGHTS_JS = r'''function latestForCode(code){const out=[];const rows=latest();SAMPLES.filter(s=>s.phenomenon_code===code).forEach(s=>{if(rows[s.sample_id])out.push({sample:s,row:rows[s.sample_id]})});return out}
function renderThoughts(){const rows=latestForCode(currentCode);byId('thoughts-body').innerHTML=rows.map(x=>`<tr><td><strong>${esc(x.sample.sample_id)}</strong><br>${esc((x.sample.target_word_labels||[]).join(' · '))}</td><td>${esc(x.row.research_observation||'')}</td><td>${esc(x.row.research_morphology_hypothesis||x.row.morph_environment_note||'')}</td><td>${esc(x.row.research_prosody_hypothesis||'')}</td><td>${esc(x.row.realization_impression||'')}</td><td>${esc(x.row.research_literature_link||x.row.literature_connection_note||'')}</td><td>${esc(x.row.research_next_action||x.row.uncertainty_and_question||'')}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">아직 저장된 사례 메모가 없습니다.</td></tr>'}
function thoughtsMarkdown(){const lines=[`# ${currentCode} · ${LABEL()} 연구자 사례 메모`,``,`> 탐색용 최신 revision 집계. 정식 판정 ledger가 아님.`,``,SAMPLE_AUDIT[currentCode]?.warning||'',``];latestForCode(currentCode).forEach(x=>{const r=x.row;lines.push(`## ${x.sample.sample_id} · ${(x.sample.target_word_labels||[]).join(' · ')}`,``,`- 관찰: ${r.research_observation||''}`,`- 환경 가설: ${r.research_environment_hypothesis||''}`,`- 형태론 가설: ${r.research_morphology_hypothesis||r.morph_environment_note||''}`,`- 운율 가설: ${r.research_prosody_hypothesis||''}`,`- 문헌 연결: ${r.research_literature_link||r.literature_connection_note||''}`,`- 대안 설명: ${r.research_alternative_explanation||''}`,`- 다음 행동: ${r.research_next_action||r.uncertainty_and_question||''}`,`- 형태소 경계 / POS / 운율: ${r.factor_morph_boundary_type||''} / ${r.factor_pos_configuration||''} / ${r.factor_prosodic_boundary||''}`,``)});return lines.join('\n')}
function downloadText(name,text,type='text/markdown;charset=utf-8'){const blob=new Blob([text],{type});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();URL.revokeObjectURL(a.href)}
async function openPraatLive(){const status=byId('open-praat-live-status');if(location.protocol==='file:'){status.className='status-error';status.textContent='START_REVIEWER_WITH_PRAAT.cmd로 화면을 다시 여세요.';return}status.className='meta';status.textContent='Praat 실행 요청 중…';try{const response=await fetch('/api/open-praat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_id:currentId})});const result=await response.json();if(!response.ok)throw new Error(result.error||`HTTP ${response.status}`);status.className='saved';status.textContent=`Praat 실행됨: ${result.sample_id}`}catch(error){status.className='status-error';status.textContent=`Praat 실행 실패: ${error.message||error}`}}
'''


SERVER_SCRIPT = r'''#!/usr/bin/env python3
"""Serve reviewer v3 locally and open whitelisted samples in Praat."""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("STAGE2_REVIEWER_PORT", "8765"))


def load_samples() -> set[str]:
    with (PACKAGE_ROOT / "ASSET_MANIFEST.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["sample_id"] for row in csv.DictReader(handle)}


ALLOWED_SAMPLES = load_samples()


def find_praat() -> Path | None:
    candidates = [os.environ.get("PRAAT_EXE", ""), shutil.which("praat.exe") or ""]
    candidates.extend([
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Praat/praat.exe"),
        r"C:\Program Files\Praat\praat.exe",
        r"C:\Program Files (x86)\Praat\praat.exe",
    ])
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    return None


def sample_paths(sample_id: str) -> tuple[Path, Path]:
    if sample_id not in ALLOWED_SAMPLES:
        raise ValueError("허용되지 않은 sample_id")
    wav = (PACKAGE_ROOT / "assets" / sample_id / "target.wav").resolve()
    textgrid = (PACKAGE_ROOT / "praat_work" / sample_id / f"{sample_id}.TextGrid").resolve()
    if PACKAGE_ROOT.resolve() not in wav.parents or PACKAGE_ROOT.resolve() not in textgrid.parents:
        raise ValueError("패키지 밖 경로는 열 수 없음")
    if not wav.is_file() or not textgrid.is_file():
        raise FileNotFoundError("WAV 또는 TextGrid 작업본이 없음")
    return wav, textgrid


def launch_praat(sample_id: str) -> dict[str, str]:
    praat = find_praat()
    if praat is None:
        raise FileNotFoundError("Praat.exe를 찾지 못했습니다. PRAAT_EXE 환경변수에 전체 경로를 지정하세요.")
    wav, textgrid = sample_paths(sample_id)
    subprocess.Popen([str(praat), "--open", str(wav), str(textgrid)])
    return {"sample_id": sample_id, "praat": str(praat), "wav": str(wav), "textgrid": str(textgrid)}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PACKAGE_ROOT), **kwargs)

    def do_POST(self) -> None:
        if self.path != "/api/open-praat":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 4096:
                raise ValueError("요청 크기 오류")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = launch_praat(str(payload.get("sample_id", "")))
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            status = 200
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            status = 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    url = f"http://{HOST}:{PORT}/STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print(f"연구자 화면: {url}")
    print("종료: Ctrl+C")
    server.serve_forever()


if __name__ == "__main__":
    main()
'''


START_CMD = r'''@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 run_reviewer_with_praat.py
) else (
  python run_reviewer_with_praat.py
)
if errorlevel 1 pause
'''


def transform_html(
    document: str,
    literature: dict[str, Any],
    factor_maps: dict[str, Any],
    audit: dict[str, Any],
    build_meta: dict[str, Any],
) -> str:
    document = replace_json_script(document, "literature-data", literature)
    document = replace_json_script(document, "build-data", build_meta)
    document = replace_once(document, "<title>7현상 2시간 연구 파일럿</title>", "<title>7현상 체계적 연구 작업공간 v3</title>", "title")
    document = replace_once(document, "<header><h1>7현상 · 현상당 2시간 연구 파일럿</h1>", "<header><h1>7현상 · 체계적 연구 작업공간 v3</h1>", "heading")
    document = replace_once(document, "@media(max-width:850px)", EXTRA_CSS + "\n@media(max-width:850px)", "CSS insertion")
    document = re.sub(r'<section class="panel" id="literature-panel">.*?</section>', LITERATURE_PANEL, document, count=1, flags=re.DOTALL)
    require('id="sampling-warning"' in document, "literature panel transform")
    document = re.sub(r'<section class="panel"><details open><summary>읽기 전용 TextGrid 패널</summary>.*?</details></section>', TEXTGRID_PANEL, document, count=1, flags=re.DOTALL)
    require('id="open-praat-live"' in document, "TextGrid panel transform")
    document = replace_once(document, '<form id="review-form" class="form">', '<form id="review-form" class="form">' + RESEARCH_FIELDS, "research fields")
    document = replace_once(document, '<section class="panel"><h2>기록 파일</h2>', THOUGHTS_PANEL + '<section class="panel"><h2>기록 파일</h2>', "thoughts panel")
    marker = '<script id="textgrids-data" type="application/json">'
    additions = (
        '<script id="factor-data" type="application/json">' + json_for_html(factor_maps) + '</script>'
        '<script id="sample-audit-data" type="application/json">' + json_for_html(audit) + '</script>'
    )
    document = replace_once(document, marker, additions + marker, "factor scripts")
    document = replace_once(
        document,
        "const TEXTGRIDS=JSON.parse(document.getElementById('textgrids-data').textContent);",
        "const FACTOR_MAPS=JSON.parse(document.getElementById('factor-data').textContent);const SAMPLE_AUDIT=JSON.parse(document.getElementById('sample-audit-data').textContent);const TEXTGRIDS=JSON.parse(document.getElementById('textgrids-data').textContent);",
        "JS data declarations",
    )
    document, count = re.subn(r'function renderLiterature\(\)\{.*?\}\nfunction renderMorph', RENDER_LITERATURE_JS + "\nfunction renderMorph", document, count=1, flags=re.DOTALL)
    require(count == 1, "renderLiterature replacement")
    old_restore = re.search(r'function restoreForm\(s\)\{.*?\}\nfunction renderCurrent', document, flags=re.DOTALL)
    require(old_restore is not None, "restoreForm anchor")
    restore = old_restore.group(0)[:-len("\nfunction renderCurrent")]
    restore = replace_once(
        restore,
        "byId('compoundness-label').style.display=currentCode==='PT'?'grid':'none';",
        "byId('compoundness-label').style.display=currentCode==='PT'?'grid':'none';byId('pt-specific').style.display=currentCode==='PT'?'block':'none';byId('nan-specific').style.display=currentCode==='NAN'?'block':'none';",
        "phenomenon field toggle",
    )
    document = document[: old_restore.start()] + restore + "\nfunction renderCurrent" + document[old_restore.end() :]
    document = replace_once(document, "restoreForm(s);renderDialogue(s);}", "restoreForm(s);renderDialogue(s);renderThoughts();byId('open-praat-live-status').textContent='';}", "renderCurrent extension")
    document = replace_once(document, "schema_version:'stage2_two_hour_exploratory_review.v1'", "schema_version:'stage2_two_hour_exploratory_review.v2'", "review schema")
    document = replace_once(document, "renderList()});\nbyId('phenomenon-summary-save')", "renderList();renderThoughts()});\nbyId('phenomenon-summary-save')", "post-save aggregate")
    document = replace_once(document, "byId('copy-praat').onclick=", "byId('open-praat-live').onclick=openPraatLive;byId('refresh-thoughts').onclick=renderThoughts;byId('export-thoughts').onclick=()=>downloadText(`P2H_${currentCode}_RESEARCHER_THOUGHTS.md`,thoughtsMarkdown());\n" + THOUGHTS_JS + "\nbyId('copy-praat').onclick=", "aggregate handlers")
    document = replace_once(document, "renderLiterature();restoreForm(SAMPLE_MAP[currentId]);renderList()", "renderLiterature();restoreForm(SAMPLE_MAP[currentId]);renderList();renderThoughts()", "post-import aggregate")
    return document


def markdown_research_map(factors: dict[str, Any]) -> str:
    lines = ["# 7현상 체계적 연구 지도", "", "> 후보 설계입니다. 연구자 승인 전 동결 설정과 정식 판정표를 바꾸지 않습니다.", ""]
    for code in EXPECTED_CODES:
        row = factors[code]
        lines.extend([f"## {code} · {row['label_ko']}", "", "### 질문", ""])
        lines.extend(f"- {q['id']}: {q['question']}" for q in row.get("research_questions", []))
        lines.extend(["", "### 모집단·범위 층", ""])
        lines.extend(f"- {x['id']} · {x['label']}: {x['description']}" for x in row.get("scope_families", []))
        lines.extend(["", "### 다음 표본 요구", ""])
        lines.extend(f"- {x}" for x in row.get("sampling_requirements", []))
        lines.append("")
    return "\n".join(lines)


def current_sample_audit_md(audit: dict[str, Any]) -> str:
    lines = ["# 현재 84건 표본 감사", "", "> 결론: 현재 v2/v3의 84건은 연구 질문을 찾는 탐색 표본이지, 현상별 요인을 균형화한 본 분석 표본이 아닙니다.", ""]
    for code in EXPECTED_CODES:
        row = audit[code]
        lines.extend([f"## {code}", "", row["warning"], "", f"- population role: `{json.dumps(row['population_roles'], ensure_ascii=False)}`", f"- environment scope: `{json.dumps(row['environment_scopes'], ensure_ascii=False)}`", f"- query: `{json.dumps(row['query_ids'], ensure_ascii=False)}`", ""])
    return "\n".join(lines)


def claude_handoff() -> str:
    return """# Claude Cowork 인계 — 4시간 연구자 중심 선행연구 종합\n\n## 목적\n\n연구자가 약 4시간 동안 기존 연구에 관해 떠오르는 생각을 자유롭게 종합한다. Claude는 생각을 대신 결정하지 않고, 연구자의 메모가 이후 근거 장부·현상별 요인 지도·범위/표본 계약·Codex 코드 초안으로 이어지게 정리한다.\n\n## 꼭 지킬 경계\n\n- 자유 메모 원문을 보존하고, Claude의 정규화·추론과 섞지 않는다.\n- 주장마다 출처, 정확한 페이지, 직접/인접/방법론/미확인, 확신도, `does_not_establish`를 둔다.\n- 원문을 확인하지 못한 기억은 `researcher_recall_unverified`로 둔다.\n- PT는 저해음 뒤 기준 경음화, 합성어 경음화, 사이시옷을 각각 판정하며 복수 membership을 보존한다.\n- NAN은 어절 내부 저해음+/ㄴ·ㅁ/ 기준층과 어절 간 운율 탐색층을 합치지 않는다.\n- 필수 환경은 형태소 경계와 좌우 POS를 층화한다.\n- 연구자 승인 전 동결 query/config, 원자료, 정식 realization ledger를 바꾸지 않는다. 모든 수정안은 `candidate`로 낸다.\n\n## 4시간 진행\n\n1. 0:00–0:30 자유 회상: 수정하거나 평가하지 말고 연구자 표현 그대로 기록.\n2. 0:30–1:30 근거 지도: 직접 주장, 반례, 적용 조건, 한계, 원문 미확인을 분리.\n3. 1:30–2:30 7현상 요인 지도: 음운입력·형태론/POS·어휘·운율·화자·담화·측정 요인과 상호작용 갱신.\n4. 2:30–3:15 공백과 우선순위: 반드시 원문을 확인할 것, 새 표본/대조, 세미나에 없던 필수 환경 결정.\n5. 3:15–4:00 코드 인계: 확정하지 말고 후보 scope card, sampling frame, query/reviewer 변경 요구로 번역.\n\n## 산출물\n\n- `RESEARCHER_FREE_NOTES_YYYYMMDD.md` — 연구자 원문 중심\n- `CLAIM_LEDGER_PATCH_CANDIDATE.jsonl` — 근거 행 후보\n- `FACTOR_MAP_PATCH_CANDIDATE.json` — 7현상 요인 변경 후보\n- `SCOPE_AND_SAMPLING_DECISIONS_CANDIDATE.md` — 확정/보류/반려를 구분\n- `CODE_HANDOFF_TO_CODEX.md` — 파일·필드·테스트·마이그레이션 요구\n\n## Codex로 되돌릴 때\n\n`Claude Cowork의 4시간 문헌 종합 산출물을 읽고, 연구자 원문과 Claude 추론을 분리 감사해줘. 승인된 결정만 후보 config/claim ledger/query/reviewer 초안에 반영하고, v1/v2와 기존 JSONL은 보존해. PT/NAN 모집단 분리, 복수 membership, 형태소·POS 층화가 테스트되는지 확인한 뒤 변경 내역·미확인 근거·다음 연구자 결정을 보고해줘. commit/push 전에는 diff와 감사 결과를 먼저 보여줘.`\n"""


def four_hour_template() -> str:
    return """# 4시간 선행연구 종합 작업지\n\n## 세션 정보\n\n- 날짜/시간:\n- 집중 환경:\n- 오늘 우선 현상:\n- 이번 세션에서 결정하지 않을 것:\n\n## 0:00–0:30 자유 메모 — 원문 보존\n\n<!-- 문장 다듬기·분류보다 기억과 의문을 먼저 씁니다. -->\n\n## 0:30–1:30 근거별 정리\n\n| 내 생각/주장 | 출처·페이지 | 직접/인접/방법/미확인 | 지지/반례 | 적용 조건 | 확립하지 않는 것 | 확신도 |\n|---|---|---|---|---|---|---|\n\n## 1:30–2:30 현상별 요인\n\n| 현상 | 음운 입력 | 형태소 경계·POS | 어휘 | 운율 | 화자·담화 | 측정 | 상호작용 |\n|---|---|---|---|---|---|---|---|\n| PT | | | | | | | |\n| NAN | | | | | | | |\n| NAL | | | | | | | |\n| NI | | | | | | | |\n| LLN | | | | | | | |\n| VH | | | | | | | |\n| HIA | | | | | | | |\n\n## 2:30–3:15 공백·우선순위\n\n- 원문 확인이 필요한 기억:\n- 직접 근거가 없는 핵심 주장:\n- 반드시 추가할 기준 환경·대조:\n- 지금 표본에서 답할 수 없는 질문:\n\n## 3:15–4:00 후보 결정과 코드 인계\n\n### 승인 후보\n\n### 보류\n\n### 반려\n\n### reviewer 화면 변경\n\n### query/표본 프레임 변경\n\n### 테스트·감사 기준\n"""


def four_hour_html() -> str:
    sections = [
        ("step1", "0:00–0:30 · 자유 회상", "문장을 다듬거나 평가하지 말고 떠오르는 연구·주장·의문을 연구자 표현 그대로 적습니다."),
        ("step2", "0:30–1:30 · 근거와 반례", "각 생각을 직접 근거·인접 현상·방법론·미확인 기억으로 나누고 출처·페이지·적용 조건·확립하지 않는 것을 적습니다."),
        ("step3", "1:30–2:30 · 7현상 요인", "음운 입력, 형태소 경계와 POS, 어휘, 운율, 화자·담화, 측정, 상호작용을 현상별로 갱신합니다."),
        ("step4", "2:30–3:15 · 공백과 우선순위", "원문 확인, 필수 기준 환경, 비교군, 새 표본, 현재 84건으로 답할 수 없는 질문을 정합니다."),
        ("step5", "3:15–4:00 · 후보 결정과 코드 인계", "승인 후보·보류·반려를 나누고 reviewer/query/표본 프레임/테스트 변경 요구를 Codex 인계문으로 씁니다."),
    ]
    panels = "".join(
        f'<section><h2>{title}</h2><p>{description}</p><textarea id="{key}" placeholder="여기에 적기"></textarea><label><input type="checkbox" id="{key}-done"> 이 단계 완료</label></section>'
        for key, title, description in sections
    )
    script_rows = json.dumps([{"id": key, "title": title} for key, title, _ in sections], ensure_ascii=False)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>4시간 선행연구 종합</title><style>:root{{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;color:#17212b}}body{{margin:0;background:#edf2f5;line-height:1.6}}header{{background:#173b57;color:#fff;padding:1rem}}main{{max-width:1000px;margin:auto;padding:1rem}}section{{background:#fff;border:1px solid #ced9e0;border-radius:12px;padding:1rem;margin:1rem 0}}textarea{{width:100%;min-height:260px;padding:.7rem;border:1px solid #8da0ad;border-radius:8px;font:inherit}}button{{padding:.7rem 1rem;border:0;border-radius:8px;background:#285f9e;color:#fff;font-weight:700;margin:.3rem}}.warn{{background:#fff2cb;padding:.8rem;border-radius:8px}}.done{{color:#176742;font-weight:700}}</style></head><body><header><h1>4시간 선행연구 종합 작업지</h1><p>연구자 생각을 먼저 보존하고, 나중에 근거·요인·코드 후보로 연결합니다.</p></header><main><p class="warn">이 화면은 브라우저에 임시 저장됩니다. 30분마다 Markdown을 내려받으세요. 연구자 승인 전에는 동결 config/query/정식 ledger를 바꾸지 않습니다.</p><div><button id="save">지금 저장</button><button id="export">Markdown 내려받기</button><span id="status"></span></div>{panels}<section><h2>Claude Cowork에 넘길 때</h2><p><code>CLAUDE_COWORK_4H_SESSION_PROMPT.txt</code>와 이 화면에서 내려받은 Markdown을 함께 전달하세요. Claude의 추론은 연구자 원문과 분리하고 모든 변경은 candidate로 냅니다.</p></section></main><script>const STEPS={script_rows};const KEY='stage2_four_hour_literature_session_v1';function values(){{return Object.fromEntries(STEPS.flatMap(x=>[[x.id,document.getElementById(x.id).value],[x.id+'_done',document.getElementById(x.id+'-done').checked]]))}}function save(){{localStorage.setItem(KEY,JSON.stringify(values()));document.getElementById('status').textContent=' 저장됨 '+new Date().toLocaleTimeString();document.getElementById('status').className='done'}}function restore(){{try{{const v=JSON.parse(localStorage.getItem(KEY)||'{{}}');STEPS.forEach(x=>{{document.getElementById(x.id).value=v[x.id]||'';document.getElementById(x.id+'-done').checked=Boolean(v[x.id+'_done'])}})}}catch{{}}}}function markdown(){{const v=values();return ['# 4시간 선행연구 종합 — 연구자 기록','',...STEPS.flatMap(x=>[`## ${{x.title}}`,'',v[x.id]||'',`완료: ${{v[x.id+'_done']?'예':'아니오'}}`,''])].join('\\n')}}document.getElementById('save').onclick=save;document.getElementById('export').onclick=()=>{{save();const blob=new Blob([markdown()],{{type:'text/markdown;charset=utf-8'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='RESEARCHER_FREE_NOTES_4H.md';a.click();URL.revokeObjectURL(a.href)}};document.querySelectorAll('textarea,input').forEach(x=>x.addEventListener('input',()=>localStorage.setItem(KEY,JSON.stringify(values()))));restore();</script></body></html>'''


def research_map_html(factors: dict[str, Any]) -> str:
    parts = []
    for code in EXPECTED_CODES:
        row = factors[code]
        questions = "".join(f"<li><strong>{q['id']}</strong> {q['question']}</li>" for q in row.get("research_questions", []))
        scopes = "".join(f"<li><strong>{x['id']} · {x['label']}</strong>: {x['description']}</li>" for x in row.get("scope_families", []))
        sampling = "".join(f"<li>{x}</li>" for x in row.get("sampling_requirements", []))
        parts.append(f"<details><summary>{code} · {row['label_ko']}</summary><h3>질문</h3><ol>{questions}</ol><h3>모집단·범위</h3><ul>{scopes}</ul><h3>다음 표본 요구</h3><ul>{sampling}</ul></details>")
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>7현상 연구 지도</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;max-width:1050px;margin:auto;padding:1rem;line-height:1.6;color:#17212b}}details{{border:1px solid #ced9e0;border-radius:10px;padding:.8rem;margin:.8rem 0}}summary{{font-weight:800;color:#164f7a;cursor:pointer}}.warn{{background:#fff2cb;padding:1rem;border-radius:9px}}li{{margin:.35rem 0}}</style></head><body><h1>7현상 체계적 연구 지도</h1><p class="warn">후보 설계입니다. 현재 84건은 균형 표본이 아니며 연구자 승인 전 동결 설정을 바꾸지 않습니다.</p>{''.join(parts)}</body></html>'''


def write_support_files(package: Path, factors: dict[str, Any], audit: dict[str, Any]) -> None:
    research_dir = package / "RESEARCH_SYSTEM"
    research_dir.mkdir(parents=True, exist_ok=False)
    (research_dir / "00_READ_ME_FIRST.md").write_text(
        "# 먼저 읽기\n\n1. 기존 기록이 있으면 HTML에서 JSONL을 먼저 불러옵니다.\n2. 화면을 실제 Praat와 연결하려면 상위 폴더의 `START_REVIEWER_WITH_PRAAT.cmd`를 실행합니다. Praat가 없으면 화면은 정상 작동하지만 실제 열기 버튼은 경로 안내를 표시합니다.\n3. 한 사례에서 `내 생각 먼저`를 적고 저장하면 아래 집계표에 최신 revision이 모입니다.\n4. 84건은 탐색 표본입니다. `CURRENT_SAMPLE_AUDIT.md`의 부족 조건을 본 연구 결과처럼 해석하지 않습니다.\n5. 4시간 문헌 종합은 `FOUR_HOUR_LITERATURE_SESSION.html`을 열어 단계별로 진행하고, 내려받은 Markdown과 `CLAUDE_COWORK_4H_SESSION_PROMPT.txt`를 Claude Cowork에 전달합니다.\n6. 연구자 승인 전에는 candidate 산출물만 만들고 동결 config/query/정식 ledger는 바꾸지 않습니다.\n",
        encoding="utf-8",
    )
    (research_dir / "SEVEN_PHENOMENA_RESEARCH_MAP.md").write_text(markdown_research_map(factors), encoding="utf-8")
    (research_dir / "CURRENT_SAMPLE_AUDIT.md").write_text(current_sample_audit_md(audit), encoding="utf-8")
    (research_dir / "CURRENT_SAMPLE_AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (research_dir / "CLAUDE_COWORK_HANDOFF.md").write_text(claude_handoff(), encoding="utf-8")
    (research_dir / "CLAUDE_COWORK_4H_SESSION_PROMPT.txt").write_text(claude_handoff(), encoding="utf-8")
    (research_dir / "FOUR_HOUR_LITERATURE_SYNTHESIS_TEMPLATE.md").write_text(four_hour_template(), encoding="utf-8")
    (research_dir / "FOUR_HOUR_LITERATURE_SESSION.html").write_text(four_hour_html(), encoding="utf-8")
    (research_dir / "SEVEN_PHENOMENA_RESEARCH_MAP.html").write_text(research_map_html(factors), encoding="utf-8")
    gap_rows = []
    frame_rows = []
    for code in EXPECTED_CODES:
        for index, question in enumerate(factors[code].get("research_questions", []), 1):
            gap_rows.append({"schema_version": "literature_gap_candidate.v1", "phenomenon_code": code, "gap_id": f"{code}-GAP-{index:02d}", "question": question["question"], "status": "candidate_pending_researcher_review", "resolution": ""})
        for family in factors[code].get("scope_families", []):
            frame_rows.append({"phenomenon_code": code, "scope_family_id": family["id"], "scope_family_label": family["label"], "description": family["description"], "morph_boundary_type": "to_stratify", "left_pos": "to_stratify", "right_pos": "to_stratify", "prosodic_boundary": "to_stratify", "sample_status": "candidate_not_selected"})
    with (research_dir / "LITERATURE_GAP_REGISTER.jsonl").open("w", encoding="utf-8") as handle:
        for row in gap_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (research_dir / "LITERATURE_GAP_REGISTER.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(gap_rows[0]))
        writer.writeheader(); writer.writerows(gap_rows)
    with (research_dir / "SAMPLING_FRAME_CANDIDATE.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(frame_rows[0]))
        writer.writeheader(); writer.writerows(frame_rows)


def build(source: Path, output: Path, cards_path: Path, factors_path: Path, claims_path: Path) -> dict[str, Any]:
    source = source.resolve(); output = output.resolve()
    require(source.is_dir(), f"source missing: {source}")
    require(PILOT_ROOT.resolve() in source.parents, "source outside pilot root")
    require(PILOT_ROOT.resolve() in output.parents, "output outside pilot root")
    require(source != output, "source and output must differ")
    require(not output.exists(), f"output exists: {output}")
    partial = output.with_name(output.name + ".partial")
    require(not partial.exists(), f"partial exists: {partial}")
    source_manifest = verify_package_manifest(source)
    source_manifest_sha_before = sha256_file(source / "SHA256SUMS.txt")
    cards = read_jsonl(cards_path)
    require([row.get("phenomenon_code") for row in cards] == EXPECTED_CODES, "scope-card order")
    claims = read_jsonl(claims_path)
    require(len(claims) == 173, f"expected 173 claims, measured {len(claims)}")
    factors = load_factor_maps(factors_path)
    source_html = (source / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html").read_text(encoding="utf-8")
    samples = extract_json_script(source_html, "samples-data")
    audit = sample_audit(samples)
    literature = literature_payload(cards, claims)
    require(list(literature) == EXPECTED_CODES, "literature payload order")
    old_build = extract_json_script(source_html, "build-data")
    build_meta = {**old_build, "schema_version": "stage2_systematic_reviewer_build.v3", "reviewer_version": "v3_systematic", "source_v2_manifest_sha256": source_manifest_sha_before, "claims_sha256": sha256_file(claims_path), "claims_rows": len(claims), "scope_cards_sha256": sha256_file(cards_path), "factor_maps_sha256": sha256_file(factors_path), "sample_status": "exploratory_not_balanced"}
    transformed = transform_html(source_html, literature, factors, audit, build_meta)
    shutil.copytree(source, partial)
    try:
        for name in ["SHA256SUMS.txt", "BUILD_RECEIPT.json"]:
            (partial / name).unlink()
        (partial / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html").write_text(transformed, encoding="utf-8")
        start = (partial / "START_HERE.html").read_text(encoding="utf-8")
        start = start.replace("7현상 · 현상당 2시간 연구 파일럿", "7현상 · 체계적 연구 작업공간 v3")
        start = start.replace("<body>", "<body><p class=\"warn\"><strong>실제 Praat 연동:</strong> 이 파일을 직접 열기보다 <code>START_REVIEWER_WITH_PRAAT.cmd</code>를 실행하세요. 기존 JSONL은 화면에서 그대로 불러올 수 있습니다.</p>", 1)
        (partial / "START_HERE.html").write_text(start, encoding="utf-8")
        readme = "# Stage2 7현상 체계적 연구 작업공간 v3\n\n- v1/v2와 기존 JSONL은 보존합니다. 이 폴더는 새 복사본입니다.\n- 시작: `START_REVIEWER_WITH_PRAAT.cmd` 또는 `START_HERE.html`\n- 기존 기록: HTML의 `JSONL 불러오기`에서 `P2H_EXPLORATORY_REVIEWS.jsonl` 선택\n- 사례별 `내 생각 먼저` 저장 후 아래 집계표와 Markdown 내보내기를 사용합니다.\n- 현재 84건은 균형 표본이 아닙니다. `RESEARCH_SYSTEM/CURRENT_SAMPLE_AUDIT.md`를 먼저 확인하세요.\n- 4시간 문헌 종합: `RESEARCH_SYSTEM/FOUR_HOUR_LITERATURE_SESSION.html`을 열고, 내보낸 Markdown과 `CLAUDE_COWORK_4H_SESSION_PROMPT.txt`를 Claude Cowork에 전달하세요.\n- 실제 Praat가 없으면 미리보기와 기록은 가능하지만 Praat 실행 버튼은 작동하지 않습니다. 설치는 자동 수행하지 않습니다.\n"
        (partial / "README.md").write_text(readme, encoding="utf-8")
        (partial / "run_reviewer_with_praat.py").write_text(SERVER_SCRIPT, encoding="utf-8")
        (partial / "START_REVIEWER_WITH_PRAAT.cmd").write_text(START_CMD, encoding="utf-8")
        write_support_files(partial, factors, audit)
        inventory = []
        for path in sorted(p for p in partial.rglob("*") if p.is_file()):
            relative = path.relative_to(partial).as_posix()
            inventory.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        receipt = {"schema_version": "stage2_systematic_reviewer_build_receipt.v3", "passed": True, "status": "researcher_ready_existing_jsonl_import_required", "source_package": str(source), "source_manifest": source_manifest, "source_manifest_sha256_before": source_manifest_sha_before, "source_manifest_sha256_after": sha256_file(source / "SHA256SUMS.txt"), "sample_count": len(samples), "phenomenon_count": len(factors), "claim_count": len(claims), "current_sample_status": "exploratory_not_balanced", "safety": {"v1_v2_untouched": True, "source_assets_exact_copies": True, "researcher_jsonl_not_mutated": True, "frozen_configs_not_auto_changed": True, "praat_launch_whitelist": True}, "inventory_before_receipt": inventory}
        (partial / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_lines = []
        for path in sorted(p for p in partial.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
            manifest_lines.append(f"{sha256_file(path)}  {path.relative_to(partial).as_posix()}")
        (partial / "SHA256SUMS.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        require(source_manifest_sha_before == sha256_file(source / "SHA256SUMS.txt"), "source v2 changed during build")
        os.replace(partial, output)
    except Exception:
        if partial.exists():
            shutil.rmtree(partial)
        raise
    return {"output": str(output), "files": len(manifest_lines), "samples": len(samples), "claims": len(claims), "source_v2_manifest_sha256": source_manifest_sha_before, "output_manifest_sha256": sha256_file(output / "SHA256SUMS.txt")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--factors", type=Path, default=DEFAULT_FACTORS)
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    args = parser.parse_args()
    result = build(args.source, args.output, args.cards, args.factors, args.claims)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
