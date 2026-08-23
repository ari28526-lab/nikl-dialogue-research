from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

sys.stdout.reconfigure(encoding="utf-8")


EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"blank JSONL line: {path}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row must be object: {path}:{line_number}")
            rows.append(value)
    codes = [str(row.get("phenomenon_code", "")) for row in rows]
    if codes != EXPECTED_CODES:
        raise ValueError(f"unexpected phenomenon order: {codes}")
    return rows


def ensure_absent(paths: Iterable[Path]) -> None:
    for path in paths:
        partial = path.with_name(path.name + ".partial")
        if path.exists() or partial.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")


def atomic_write_pair(first: Path, first_payload: bytes, second: Path, second_payload: bytes) -> None:
    ensure_absent([first, second])
    first.parent.mkdir(parents=True, exist_ok=True)
    second.parent.mkdir(parents=True, exist_ok=True)
    first_partial = first.with_name(first.name + ".partial")
    second_partial = second.with_name(second.name + ".partial")
    try:
        with first_partial.open("xb") as handle:
            handle.write(first_payload)
            handle.flush()
            os.fsync(handle.fileno())
        with second_partial.open("xb") as handle:
            handle.write(second_payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(first_partial, first)
        os.replace(second_partial, second)
    except Exception:
        # Materialized partials remain as evidence; a later run must not overwrite them.
        raise


def refs_text(refs: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in refs) if refs else "없음"


def conditions_markdown(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- 없음"]
    return [
        f"- `{item['condition_id']}` — {item['description']} "
        f"(우선순위 {item['priority']}; {refs_text(item['evidence_refs'])}; `{item['status']}`)"
        for item in items
    ]


def build_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 일곱 형태음운 현상 — 현상당 2시간 연구 파일럿 범위 카드",
        "",
        "- 작성일: 2026-08-23 KST",
        "- 상태: `candidate_pending_researcher_adoption`",
        "- 총 연구자 시간: 현상당 120분 × 7 = 840분(14시간)",
        "- 표본 목표: 현상당 12개(중심 10, 주변·탐색 최대 2; 2020–2025 연도당 최대 2)",
        "- 정지선: 이 문서는 query 동결·실현 판정·Praat 수정을 수행하지 않는다.",
        "",
        "## 먼저 읽는 법",
        "",
        "각 현상에서 `중심 모집단`을 먼저 보고, `주변·탐색`은 최대 2개만 본다. "
        "같은 형태소 조합과 단어를 붙여 보는 순서와 지각 편향을 확인하기 위한 결정적 "
        "혼합 순서를 모두 준비한다. `불명`은 삭제가 아니라 보존 상태다.",
        "",
        "## 공통 120분 시간표",
        "",
        "| 단계 | 시간 | 활동 |",
        "|---|---:|---|",
        "| 문헌 | 20분 | 핵심 주장·근거 한계 읽기 |",
        "| 범위 | 10분 | 중심/주변/탐색/범위 밖 확인 |",
        "| 사례 | 60분 | 중심 10개 + 주변·탐색 최대 2개 |",
        "| 재확인 | 20분 | 불확실·경계 사례와 향후 Praat 필요 표시 |",
        "| 정리 | 10분 | 잠정 패턴·질문·JSONL 저장 |",
        "",
        "## 준비 상태 요약",
        "",
        "| 코드 | 현상 | 문헌 수준 | 시작 query 상태 | 현재 막힘 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['phenomenon_code']} | {row['label_ko']} | "
            f"`{row['literature_evidence_level']}` | `{row['query_status_at_start']}` | "
            f"{row['readiness']['blocking_reason']} |"
        )
    for row in rows:
        code = row["phenomenon_code"]
        lines.extend([
            "",
            f"## {code} — {row['label_ko']}",
            "",
            row["definition_summary"],
            "",
            f"- definition: `{row['definition_path']}`",
            f"- synthesis: `{row['literature_synthesis_path']}`",
            f"- 근거: {refs_text(row['evidence_refs'])}",
            "",
            "### 최소 대조",
            "",
        ])
        lines.extend(f"- {item}" for item in row["minimum_contrast"])
        lines.extend(["", "### 경계 범위", ""])
        for item in row["boundary_scopes"]:
            lines.append(
                f"- **{item['status']}** — {item['name']} ({refs_text(item['evidence_refs'])})"
            )
        lines.extend([
            "",
            "### 표면형–형태소–POS 왕복",
            "",
            f"- 표면형: {row['surface_morph_pos_contract']['surface_rule']}",
            f"- 형태소: {row['surface_morph_pos_contract']['morph_rule']}",
            f"- POS: {row['surface_morph_pos_contract']['pos_rule']}",
            "- 고위험 예:",
        ])
        lines.extend(f"  - {item}" for item in row["surface_morph_pos_contract"]["high_risk_examples"])
        for key, title in (
            ("primary", "중심 모집단"),
            ("peripheral", "주변 모집단"),
            ("exploratory", "탐색 모집단"),
            ("out_of_scope", "범위 밖"),
            ("unclear", "불명 보존"),
        ):
            lines.extend(["", f"### {title}", ""])
            lines.extend(conditions_markdown(row["population_contract"][key]))
        lines.extend(["", "### 후보 실현 범주", ""])
        lines.extend(f"- `{item}`" for item in row["realization_categories_candidate"])
        lines.extend(["", "### 사람이 볼 항목", ""])
        lines.extend(f"- {item}" for item in row["human_review_items"])
        lines.extend(["", "### 근거의 한계", ""])
        lines.extend(f"- {item}" for item in row["evidence_limits"])
        lines.extend(["", "### 아직 열린 질문", ""])
        lines.extend(f"- {item}" for item in row["open_questions"])
    lines.extend([
        "",
        "## 범위 밖",
        "",
        "- 자동 실현 판정",
        "- MFA·KOINA·wav2vec2 실행",
        "- production query 동결",
        "- 원자료·r3·6-tier·기존 PV 출력 수정",
        "- 연구자 검토를 했다고 자동 기록",
        "",
    ])
    return "\n".join(lines)


def build_html(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    labels = {row["phenomenon_code"]: row["label_ko"] for row in rows}
    buttons = "".join(
        f'<button class="phenomenon-tab" data-code="{html.escape(code)}">'
        f'{html.escape(code)}<span>{html.escape(labels[code])}</span></button>'
        for code in EXPECTED_CODES
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>일곱 현상 2시간 연구 파일럿 범위 카드</title>
  <style>
    :root {{ --ink:#17202a; --muted:#5f6b76; --paper:#fbfaf7; --card:#fff; --line:#d8d4cc; --accent:#215c55; --soft:#e9f2ef; --warn:#8a4b12; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif; line-height:1.62; }}
    header {{ padding:24px clamp(18px,5vw,64px) 18px; background:linear-gradient(120deg,#173e3a,#286b61); color:white; }}
    header h1 {{ margin:0 0 8px; font-size:clamp(1.35rem,3vw,2.15rem); }}
    header p {{ margin:4px 0; max-width:980px; }}
    .layout {{ display:grid; grid-template-columns:minmax(170px,240px) minmax(0,1fr); gap:24px; padding:24px clamp(16px,4vw,52px) 52px; }}
    nav {{ position:sticky; top:12px; align-self:start; display:grid; gap:8px; }}
    .phenomenon-tab {{ text-align:left; border:1px solid var(--line); background:white; padding:11px 12px; border-radius:10px; cursor:pointer; font-weight:700; color:var(--ink); }}
    .phenomenon-tab span {{ display:block; color:var(--muted); font-size:.78rem; font-weight:400; margin-top:2px; }}
    .phenomenon-tab.active {{ border-color:var(--accent); background:var(--soft); box-shadow:0 0 0 2px rgba(33,92,85,.12); }}
    main {{ min-width:0; }}
    .toolbar {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }}
    button.action {{ border:1px solid var(--accent); background:white; color:var(--accent); border-radius:8px; padding:8px 12px; cursor:pointer; font-weight:700; }}
    button.action.primary {{ background:var(--accent); color:white; }}
    .status {{ color:var(--muted); font-size:.9rem; align-self:center; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:clamp(18px,3vw,34px); box-shadow:0 10px 30px rgba(0,0,0,.045); }}
    .card h2 {{ margin:0; font-size:1.65rem; }}
    .badge {{ display:inline-block; background:var(--soft); color:var(--accent); border-radius:999px; padding:3px 9px; font-size:.8rem; margin:8px 6px 0 0; }}
    section {{ border-top:1px solid var(--line); margin-top:22px; padding-top:18px; }}
    section h3 {{ margin:0 0 10px; font-size:1.05rem; }}
    .schedule {{ display:grid; grid-template-columns:repeat(5,minmax(105px,1fr)); gap:8px; }}
    .schedule div {{ background:#f3f1ec; border-radius:9px; padding:10px; font-size:.88rem; }}
    .schedule strong {{ display:block; color:var(--accent); }}
    .population {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .population article {{ border:1px solid var(--line); border-radius:10px; padding:12px; }}
    .population h4 {{ margin:0 0 6px; }}
    ul {{ margin:.4rem 0; padding-left:1.35rem; }}
    code {{ background:#f0eee8; padding:1px 4px; border-radius:4px; overflow-wrap:anywhere; }}
    .refs {{ color:var(--muted); font-size:.85rem; }}
    .warn {{ color:var(--warn); }}
    textarea {{ width:100%; min-height:130px; resize:vertical; padding:12px; border:1px solid var(--line); border-radius:9px; font:inherit; }}
    .checklist label {{ display:block; padding:5px 0; }}
    @media(max-width:850px) {{ .layout {{ grid-template-columns:1fr; }} nav {{ position:static; grid-template-columns:repeat(4,minmax(0,1fr)); }} .phenomenon-tab span {{ display:none; }} .schedule {{ grid-template-columns:1fr 1fr; }} }}
    @media(max-width:560px) {{ nav {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .population {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<header>
  <h1>일곱 현상 · 현상당 2시간 연구 파일럿</h1>
  <p>문헌 20분 + 범위 10분 + 사례 60분 + 재확인 20분 + 정리 10분. 현재 화면은 범위 후보 검토용이며 실현 판정이나 연구 완료 기록이 아닙니다.</p>
  <p>표본 목표: 현상당 12개(중심 10개, 주변·탐색 최대 2개), 2020–2025 연도당 최대 2개.</p>
</header>
<div class="layout">
  <nav aria-label="현상 선택">{buttons}</nav>
  <main>
    <div class="toolbar">
      <button class="action" id="prev">이전 현상</button>
      <button class="action" id="next">다음 현상</button>
      <button class="action primary" id="save">이 현상 메모 저장</button>
      <button class="action" id="export">전체 메모 JSONL 내보내기</button>
      <span class="status" id="status" aria-live="polite"></span>
    </div>
    <div class="card" id="card"></div>
  </main>
</div>
<script>
const CARDS={payload};
const CODES=CARDS.map(x=>x.phenomenon_code);
const KEY='stage2_two_hour_scope_cards_notes_v1';
let current=0;
let notes={{}};
try {{ notes=JSON.parse(localStorage.getItem(KEY)||'{{}}'); }} catch (_) {{ notes={{}}; }}
const esc=(s)=>String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const list=(items)=>'<ul>'+items.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>';
const refs=(items)=>items.length?'<span class="refs">'+items.map(x=>'<code>'+esc(x)+'</code>').join(' ')+'</span>':'<span class="refs">근거 ID 없음</span>';
const cond=(items)=>items.length?'<ul>'+items.map(x=>'<li><code>'+esc(x.condition_id)+'</code> '+esc(x.description)+' <span class="refs">우선순위 '+x.priority+'</span><br>'+refs(x.evidence_refs)+'</li>').join('')+'</ul>':'<p>없음</p>';
function render() {{
  const c=CARDS[current];
  document.querySelectorAll('.phenomenon-tab').forEach(b=>b.classList.toggle('active',b.dataset.code===c.phenomenon_code));
  const schedule=c.pilot_schedule.map(x=>'<div><strong>'+x.minutes+'분</strong>'+esc(x.activity)+'</div>').join('');
  const boundaries=c.boundary_scopes.map(x=>'<li><strong>'+esc(x.status)+'</strong> — '+esc(x.name)+'<br>'+refs(x.evidence_refs)+'</li>').join('');
  const high=list(c.surface_morph_pos_contract.high_risk_examples);
  const questions=c.open_questions.map((x,i)=>'<label><input type="checkbox" data-q="'+i+'" '+(notes[c.phenomenon_code]?.checks?.[i]?'checked':'')+'> '+esc(x)+'</label>').join('');
  document.getElementById('card').innerHTML=`
    <h2>${{esc(c.phenomenon_code)}} — ${{esc(c.label_ko)}}</h2>
    <span class="badge">${{esc(c.literature_evidence_level)}}</span><span class="badge">${{esc(c.query_status_at_start)}}</span>
    <p>${{esc(c.definition_summary)}}</p>
    <p class="refs"><code>${{esc(c.definition_path)}}</code><br><code>${{esc(c.literature_synthesis_path)}}</code></p>
    <section><h3>120분 시간표</h3><div class="schedule">${{schedule}}</div></section>
    <section><h3>최소 대조</h3>${{list(c.minimum_contrast)}}</section>
    <section><h3>경계 범위</h3><ul>${{boundaries}}</ul></section>
    <section><h3>표면형–형태소–POS 왕복</h3><ul><li><strong>표면형:</strong> ${{esc(c.surface_morph_pos_contract.surface_rule)}}</li><li><strong>형태소:</strong> ${{esc(c.surface_morph_pos_contract.morph_rule)}}</li><li><strong>POS:</strong> ${{esc(c.surface_morph_pos_contract.pos_rule)}}</li></ul><h4>고위험 예</h4>${{high}}</section>
    <section><h3>모집단 우선순위</h3><div class="population"><article><h4>중심 10개</h4>${{cond(c.population_contract.primary)}}</article><article><h4>주변</h4>${{cond(c.population_contract.peripheral)}}</article><article><h4>탐색(최대 2개에 포함)</h4>${{cond(c.population_contract.exploratory)}}</article><article><h4>범위 밖</h4>${{cond(c.population_contract.out_of_scope)}}</article><article><h4>불명 — 삭제 금지</h4>${{cond(c.population_contract.unclear)}}</article></div></section>
    <section><h3>후보 실현 범주</h3>${{list(c.realization_categories_candidate)}}<p class="warn">이 범주는 아직 실제 판정값이 아닙니다.</p></section>
    <section><h3>사람이 볼 항목</h3>${{list(c.human_review_items)}}</section>
    <section><h3>근거의 한계</h3>${{list(c.evidence_limits)}}</section>
    <section class="checklist"><h3>열린 질문</h3>${{questions}}</section>
    <section><h3>내 메모</h3><textarea id="memo" placeholder="범위 정정, 궁금한 점, 파일럿에서 보고 싶은 대조를 적습니다.">${{esc(notes[c.phenomenon_code]?.memo||'')}}</textarea></section>`;
  document.getElementById('status').textContent=(current+1)+' / '+CARDS.length;
}}
function saveCurrent() {{
  const c=CARDS[current];
  notes[c.phenomenon_code]={{memo:document.getElementById('memo').value,checks:Array.from(document.querySelectorAll('[data-q]')).map(x=>x.checked),saved_at:new Date().toISOString()}};
  localStorage.setItem(KEY,JSON.stringify(notes));
  document.getElementById('status').textContent='저장됨 · '+(current+1)+' / '+CARDS.length;
}}
function move(delta) {{ saveCurrent(); current=(current+delta+CODES.length)%CODES.length; render(); window.scrollTo({{top:0,behavior:'smooth'}}); }}
document.querySelectorAll('.phenomenon-tab').forEach(b=>b.addEventListener('click',()=>{{saveCurrent();current=CODES.indexOf(b.dataset.code);render();}}));
document.getElementById('prev').addEventListener('click',()=>move(-1));
document.getElementById('next').addEventListener('click',()=>move(1));
document.getElementById('save').addEventListener('click',saveCurrent);
document.getElementById('export').addEventListener('click',()=>{{
  saveCurrent();
  const lines=CODES.map(code=>JSON.stringify({{schema_version:'stage2_two_hour_scope_note.v1',phenomenon_code:code,...(notes[code]||{{memo:'',checks:[],saved_at:null}})}}));
  const blob=new Blob([lines.join('\n')+'\n'],{{type:'application/x-ndjson;charset=utf-8'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='STAGE2_TWO_HOUR_SCOPE_NOTES.jsonl';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}});
render();
</script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 2 two-hour scope-card MD/HTML review")
    repo_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument(
        "--cards",
        default="config/phenomenon_scope_cards_candidate_v1_20260823.jsonl",
    )
    parser.add_argument(
        "--markdown-output",
        default="docs/reviews/incoming/REVIEW_stage2_seven_phenomena_two_hour_scope_cards_20260823.md",
    )
    parser.add_argument(
        "--html-output",
        default="docs/reviews/incoming/REVIEW_stage2_seven_phenomena_two_hour_scope_cards_20260823.html",
    )
    return parser.parse_args()


def repo_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    value = (root / relative).resolve()
    if value != root and root not in value.parents:
        raise ValueError(f"path escapes repo: {relative}")
    return value


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    cards = read_jsonl(repo_path(root, args.cards))
    markdown_path = repo_path(root, args.markdown_output)
    html_path = repo_path(root, args.html_output)
    markdown_payload = (build_markdown(cards) + "\n").encode("utf-8")
    html_payload = build_html(cards).encode("utf-8")
    atomic_write_pair(markdown_path, markdown_payload, html_path, html_payload)
    print(f"built cards={len(cards)} markdown={markdown_path} html={html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
