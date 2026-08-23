#!/usr/bin/env python3
"""Build research-first guides for the seven Stage2 two-hour pilots.

The builder reads only C:-side scope cards and an already verified reviewer
package.  It never reads corpus source paths embedded in the asset manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPECTED_CODES = ("PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA")
SCOPE_GROUPS = (
    ("primary", "중심 모집단"),
    ("peripheral", "주변 모집단"),
    ("exploratory", "탐색 모집단"),
    ("out_of_scope", "범위 밖"),
    ("unclear", "불확실"),
)
CONFIDENCE_ANCHORS = (
    "5 · 단서 명확·재청취 불필요",
    "4 · 단서 우세",
    "3 · 단서 있으나 상충",
    "2 · 인상 수준",
    "1 · 추측",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip() + "\n")


def load_scope_cards(path: Path) -> list[dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                card = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"scope card JSON error at line {line_number}: {exc}") from exc
            code = card.get("phenomenon_code")
            if code in cards:
                raise ValueError(f"duplicate phenomenon_code: {code}")
            cards[code] = card
    if set(cards) != set(EXPECTED_CODES):
        raise ValueError(f"scope card codes mismatch: {sorted(cards)}")
    ordered = [cards[code] for code in EXPECTED_CODES]
    for card in ordered:
        for key in (
            "label_ko",
            "card_status",
            "definition_summary",
            "minimum_contrast",
            "population_contract",
            "confounds",
            "human_review_items",
            "evidence_limits",
            "pilot_schedule",
            "open_questions",
        ):
            if key not in card:
                raise ValueError(f"{card['phenomenon_code']} missing required field: {key}")
        if "candidate" not in card["card_status"]:
            raise ValueError(f"{card['phenomenon_code']} card must remain candidate")
    return ordered


def reviewer_counts(reviewer_package: Path) -> Counter[str]:
    manifest = reviewer_package / "ASSET_MANIFEST.csv"
    review_html = reviewer_package / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
    start_html = reviewer_package / "START_HERE.html"
    for required in (manifest, review_html, start_html):
        if not required.is_file():
            raise FileNotFoundError(required)
    counts: Counter[str] = Counter()
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            counts[row["phenomenon_code"]] += 1
    if set(counts) != set(EXPECTED_CODES):
        raise ValueError(f"reviewer phenomenon codes mismatch: {dict(counts)}")
    if any(counts[code] != 12 for code in EXPECTED_CODES):
        raise ValueError(f"reviewer must contain 12 samples per phenomenon: {dict(counts)}")
    return counts


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def md_list(items: Iterable[Any]) -> str:
    values = list(items)
    return "\n".join(f"- {item}" for item in values) if values else "- 없음"


def html_list(items: Iterable[Any]) -> str:
    values = list(items)
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in values) + "</ul>"


def page(title: str, body: str, *, nested: bool = False) -> str:
    home = "../START_HERE.html" if nested else "START_HERE.html"
    common = "../ACTUAL_RESEARCH_GUIDE.html" if nested else "ACTUAL_RESEARCH_GUIDE.html"
    checklist = "../SESSION_CHECKLIST.html" if nested else "SESSION_CHECKLIST.html"
    return f"""<!doctype html>
<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{esc(title)}</title>
<style>
:root{{--ink:#17212b;--muted:#5d6872;--paper:#f5f7f8;--line:#d7e0e5;--blue:#155d86;--blue2:#e8f3f8;--green:#e9f6ed;--amber:#fff4cf;--red:#fff0ed}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,\"Apple SD Gothic Neo\",\"Malgun Gothic\",sans-serif;line-height:1.62}}
main{{max-width:1080px;margin:0 auto;padding:28px 20px 70px}}nav{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:22px}}nav a,.button{{display:inline-block;text-decoration:none;color:white;background:var(--blue);font-weight:750;border-radius:9px;padding:9px 13px}}
nav a{{background:white;color:var(--blue);border:1px solid var(--line)}}h1{{font-size:clamp(1.75rem,4vw,2.6rem);line-height:1.2;margin:.25rem 0 .75rem}}h2{{margin-top:2.1rem;border-bottom:1px solid var(--line);padding-bottom:.35rem}}h3{{margin-top:1.45rem}}p.lead{{font-size:1.05rem;color:var(--muted);max-width:800px}}
.notice{{background:var(--amber);border:1px solid #e6cf82;border-radius:13px;padding:15px 17px;margin:18px 0}}.safe{{background:var(--green);border:1px solid #b9ddc4;border-radius:13px;padding:15px 17px}}.danger{{background:var(--red);border:1px solid #e7beb5;border-radius:13px;padding:15px 17px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:13px}}.card{{background:white;border:1px solid var(--line);border-radius:13px;padding:16px;box-shadow:0 2px 9px rgba(23,33,43,.04)}}.card .code{{font-weight:850;color:var(--blue);letter-spacing:.04em}}.actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}}.actions a{{text-decoration:none;font-weight:750;border-radius:8px;padding:8px 10px;background:var(--blue2);color:var(--blue)}}
table{{width:100%;border-collapse:collapse;background:white;font-size:.95rem}}th,td{{border:1px solid var(--line);padding:9px 10px;text-align:left;vertical-align:top}}th{{background:#edf2f4}}code{{overflow-wrap:anywhere}}li{{margin:.28rem 0}}.stage{{border-left:5px solid var(--blue);padding-left:14px;margin:1.25rem 0}}.badge{{display:inline-block;padding:2px 8px;border-radius:999px;background:var(--blue2);color:var(--blue);font-weight:750;font-size:.83rem}}
@media(max-width:620px){{main{{padding:20px 13px 50px}}table{{display:block;overflow-x:auto}}}}
</style></head><body><main>
<nav><a href=\"{home}\">안내서 시작</a><a href=\"{common}\">공통 실제 연구 안내서</a><a href=\"{checklist}\">세션 체크시트</a></nav>
{body}
</main></body></html>"""


def common_guide_markdown(cards: list[dict[str, Any]]) -> str:
    card_links = "\n".join(
        f"- [{card['phenomenon_code']} · {card['label_ko']}](PHENOMENON_GUIDES/{card['phenomenon_code']}.md)"
        for card in cards
    )
    return f"""# 실제 연구 수행 안내서 — Stage2 7개 현상

이 안내서는 reviewer 조작법이 아니라 **실제 연구에서 무엇을 보고 어떤 근거를 남길지**를 설명한다. 모든 범위 기준은 `candidate`이며 연구자 판단으로 수정할 수 있다. 자동 실현 판정이나 정식 realization ledger가 아니다.

## 시작 전 5분

1. 동기화된 로컬 폴더에서 reviewer를 연다. Dropbox 웹 HTML 미리보기는 사용하지 않는다.
2. 오늘 작업할 현상 하나와 종료할 단계를 정한다.
3. 헤드폰·조용한 방·재생 음량을 확인한다.
4. 재개 세션이면 해당 현상의 최신 정본 JSONL **하나만** 불러오고 `n행 불러옴`을 확인한다.
5. 문헌 메모 끝에 `빌드 8043eb25…, 헤드폰, 조용한 방` 형식의 환경 메모를 남긴다.

## 1단계 — 문헌 20분

- 문헌 패널에서 현상의 정의, 핵심 주장, 자료 범위, 근거 한계를 읽는다.
- 각 주장에 대해 `이 연구의 어떤 사례를 설명하는가`, `어떤 사례에는 적용되지 않는가`, `무엇을 추가 확인해야 하는가`를 메모한다.
- 문헌을 정답표로 사용하지 않는다. 사례를 듣기 전에 예상 실현을 확정하지 않는다.
- 문헌 메모에는 확정 결론보다 근거와 질문을 남긴다.

## 2단계 — 범위 10분

| reviewer 범위 판정 | 안내서 의미 |
|---|---|
| 일반적·중심 환경 | `primary` 계약과 직접 맞는 사례 |
| 비전형이지만 관련 가능 | `peripheral` 계약 또는 문헌상 관련 있으나 전형성이 낮은 사례 |
| 탐색 환경 | `exploratory` 계약으로 별도 관찰할 사례 |
| 범위 밖 | 명시적 제외 조건에 해당하는 사례 |
| 불확실 | 형태론·경계·중복 현상 때문에 현재 자료만으로 범위를 정할 수 없는 사례 |

범위 판정은 음성 실현 판정과 분리한다. 형태소 분석과 MFA phone은 검색·분절 보조 정보이며 실제 발음이나 형태소 경계를 자동 확정하지 않는다.

## 3단계 — 사례 60분

각 사례를 다음 순서로 처리한다.

1. 문헌·범위 패널을 접고 발화 전체를 먼저 듣는다.
2. `표적 구간으로 이동`을 사용해 표적 주변을 다시 듣는다.
3. 범위 판정과 환경 확신도를 기록한다.
4. 들린 실현과 청취 확신도를 기록한다. 들리지 않거나 단서가 충돌하면 `not_judgeable` 또는 낮은 확신도를 사용한다.
5. 대화 문맥·화자·형태론·TextGrid를 확인하고 필요한 메모를 남긴다.
6. 실현 판정이 경계 위치에 의존하고 현재 경계가 표적 구간을 명백히 벗어날 때만 Praat 경계 수정 `필요`를 고른다.
7. `이 사례를 청취함`을 표시하고 수정본을 저장한다.

### 확신도 공통 앵커

{md_list(CONFIDENCE_ANCHORS)}

### 메모 접두어

- `[DATA]`: 음성·전사·형태소·TextGrid 등 자료 문제
- `[TOOL]`: 재생·저장·불러오기·화면 등 도구 문제

## 4단계 — 선별 재확인 20분

- 청취 확신도 3 이하
- 범위 `불확실`
- Praat 경계 수정 `불확실` 또는 `필요`
- 위 사례와 비교할 확실 사례 2–3건

고정 셔플 모드에서는 grouped의 기존 실현 판정이 가려진 상태로 다시 듣는다. 20분을 넘기면 미완료 목록을 메모하고 다음 세션으로 이월한다.

## 5단계 — 현상 요약 10분

1. 중심·주변·탐색 환경에서 보인 잠정 패턴을 분리해 쓴다.
2. 문헌과 맞는 점, 맞지 않는 점, 자료로 판단할 수 없는 점을 구분한다.
3. 대안 설명과 다음 문헌·자료 질문을 남긴다.
4. `현상 요약 저장`을 누른다.
5. JSONL을 내려받아 `YYYY-MM-DD_현상코드_reviewer_v2.jsonl`로 보관한다.

현상 종료 조건은 `12사례 listened`, `불확실 목록 확정`, `현상 요약 저장`, `JSONL export 확인`의 네 가지다.

## 중단·재개

- 중단 전 문헌 메모 끝에 `어디까지 완료`를 한 줄로 남긴다.
- 반드시 JSONL을 내보낸다.
- 재개할 때 여러 export를 합치지 말고 현상별 최신 정본 하나만 불러온다.
- 브라우저 localStorage는 임시 편의 기능이며 정본이 아니다.

## 화면 개선 기록

연구를 막는 저장·오디오·현상 전환 문제는 즉시 `Blocker`로 기록한다. 단순 불편은 연구를 계속하면서 별도 UI 기록 양식에 남긴다. 같은 불편이 둘 이상의 세션이나 현상에서 반복될 때 화면 재설계를 검토한다.

## 현상별 안내서

{card_links}
"""


def common_guide_html(cards: list[dict[str, Any]]) -> str:
    cards_html = "".join(
        f"<div class=\"card\"><div class=\"code\">{esc(c['phenomenon_code'])}</div><strong>{esc(c['label_ko'])}</strong><div class=\"actions\"><a href=\"PHENOMENON_GUIDES/{esc(c['phenomenon_code'])}.html\">현상 안내서</a><a href=\"../researcher_review_package_v2/STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html?phenomenon={esc(c['phenomenon_code'])}\">reviewer</a></div></div>"
        for c in cards
    )
    anchors = html_list(CONFIDENCE_ANCHORS)
    body = f"""
<span class=\"badge\">RESEARCH GUIDE v1</span><h1>실제 연구 수행 안내서</h1>
<p class=\"lead\">reviewer 조작법보다 한 단계 더 구체적으로, 실제 연구에서 무엇을 보고 어떤 근거를 남길지 안내합니다.</p>
<div class=\"notice\"><strong>모든 기준은 candidate입니다.</strong> 안내서가 연구 판단을 대신하지 않습니다. 자동 실현 판정이나 정식 realization ledger가 아닙니다.</div>
<h2>시작 전 5분</h2><ol><li>동기화된 로컬 폴더에서 reviewer를 엽니다.</li><li>현상 하나와 오늘 종료할 단계를 정합니다.</li><li>헤드폰·조용한 방·음량을 확인합니다.</li><li>재개라면 최신 JSONL 하나만 불러오고 “n행 불러옴”을 확인합니다.</li><li>문헌 메모에 빌드·청취 환경을 적습니다.</li></ol>
<div class=\"stage\"><h2>1 · 문헌 20분</h2><p>정의·핵심 주장·자료 범위·근거 한계를 읽고, 설명되는 사례·적용되지 않는 사례·추가 확인 질문을 메모합니다. 문헌을 청취 정답표로 사용하지 않습니다.</p></div>
<div class=\"stage\"><h2>2 · 범위 10분</h2><table><tr><th>reviewer 판정</th><th>의미</th></tr><tr><td>일반적·중심</td><td>primary 계약과 직접 일치</td></tr><tr><td>비전형이지만 관련 가능</td><td>peripheral 또는 전형성이 낮은 관련 사례</td></tr><tr><td>탐색</td><td>exploratory로 별도 관찰</td></tr><tr><td>범위 밖</td><td>명시적 제외 조건</td></tr><tr><td>불확실</td><td>형태론·경계·중복 현상 때문에 현재 확정 불가</td></tr></table><p>MFA phone과 형태소 분석은 보조 정보이며 실제 실현을 자동 확정하지 않습니다.</p></div>
<div class=\"stage\"><h2>3 · 사례 60분</h2><ol><li>문헌·범위 패널을 접고 발화 전체를 먼저 듣습니다.</li><li>표적 주변을 다시 듣습니다.</li><li>범위·환경 확신도를 기록합니다.</li><li>들린 실현·청취 확신도를 기록합니다.</li><li>문맥·화자·형태론·TextGrid를 확인합니다.</li><li>경계가 판정에 중요하고 명백히 벗어날 때만 Praat ‘필요’를 고릅니다.</li><li>청취함을 표시하고 수정본을 저장합니다.</li></ol><h3>확신도 앵커</h3>{anchors}<p><code>[DATA]</code>는 자료 문제, <code>[TOOL]</code>은 도구 문제에 사용합니다.</p></div>
<div class=\"stage\"><h2>4 · 선별 재확인 20분</h2><p>청취 확신도 ≤3, 범위 불확실, 경계 필요/불확실 사례와 확실 대조 2–3건을 고정 셔플에서 다시 듣습니다. 초과분은 다음 세션으로 이월합니다.</p></div>
<div class=\"stage\"><h2>5 · 요약 10분</h2><ol><li>중심·주변·탐색 패턴을 분리합니다.</li><li>문헌과의 일치·불일치·판단 불가를 구분합니다.</li><li>대안 설명과 다음 질문을 씁니다.</li><li>현상 요약을 저장합니다.</li><li>날짜·현상 코드가 있는 JSONL을 내보냅니다.</li></ol></div>
<div class=\"safe\"><strong>종료 조건:</strong> 12사례 listened · 불확실 목록 확정 · 현상 요약 저장 · JSONL export 확인</div>
<h2>중단·재개</h2><p>중단 지점을 문헌 메모에 남기고 JSONL을 내보냅니다. 재개할 때는 현상별 최신 정본 하나만 불러옵니다. localStorage는 정본이 아닙니다.</p>
<h2>현상별 안내서</h2><div class=\"grid\">{cards_html}</div>
"""
    return page("실제 연구 수행 안내서", body)


def scope_rows(card: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    population = card["population_contract"]
    for key, label in SCOPE_GROUPS:
        for item in population.get(key, []):
            rows.append((label, item))
    return rows


def phenomenon_markdown(card: dict[str, Any], count: int) -> str:
    code = card["phenomenon_code"]
    scope_table = ["| 분류 | 조건 ID | 설명 | 우선 | 상태 | 근거 |", "|---|---|---|---:|---|---|"]
    for label, item in scope_rows(card):
        refs = ", ".join(item.get("evidence_refs", [])) or "—"
        scope_table.append(f"| {label} | `{item['condition_id']}` | {item['description']} | {item.get('priority', '—')} | {item.get('status', '—')} | {refs} |")
    boundary = card.get("boundary_scopes", [])
    boundary_table = ["| 경계 범위 | 상태 | 근거 |", "|---|---|---|"]
    for item in boundary:
        boundary_table.append(f"| {item['name']} | {item['status']} | {', '.join(item.get('evidence_refs', [])) or '—'} |")
    confounds = [f"**{item['name']}** — {item.get('status', '')}; {', '.join(item.get('evidence_refs', [])) or '근거 ID 없음'}" for item in card["confounds"]]
    schedule = ["| 순서 | 시간 | 활동 | 산출물 |", "|---:|---:|---|---|"]
    for item in card["pilot_schedule"]:
        schedule.append(f"| {item['order']} | {item['minutes']}분 | {item['activity']} | {item['output']} |")
    contract = card.get("surface_morph_pos_contract", {})
    return f"""# {code} · {card['label_ko']} — 실제 연구 안내서

> 상태: **{card['card_status']}**. 이 문서는 연구 시작용 잠정 기준이며 연구자 판단에 따라 수정한다.

[reviewer에서 {code} 시작](../../researcher_review_package_v2/STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html?phenomenon={code}) · 준비 사례 {count}건

## 이 현상에서 묻는 것

{card['definition_summary']}

### 최소 대조

{md_list(card['minimum_contrast'])}

## 120분 진행

{chr(10).join(schedule)}

## 포함·제외·별도 탐색 기준

{chr(10).join(scope_table)}

### 경계 범위

{chr(10).join(boundary_table)}

## 표면형·형태론·품사 확인

- **표면형:** {contract.get('surface_rule', '카드에 별도 규칙 없음')}
- **형태론:** {contract.get('morph_rule', '카드에 별도 규칙 없음')}
- **품사:** {contract.get('pos_rule', '카드에 별도 규칙 없음')}
- **표면–분석 불일치 상태:** `{contract.get('mismatch_status', 'surface_analysis_mismatch')}`

### 고위험 오인

{md_list(contract.get('high_risk_examples', []))}

## 사례를 들을 때 확인할 것

{md_list(card['human_review_items'])}

먼저 발화 전체를 듣고, 표적 주변을 다시 들은 뒤 범위와 실현을 따로 기록한다. 형태소·MFA phone·TextGrid를 실현 정답으로 사용하지 않는다.

### 잠정 실현 범주

{md_list(card.get('realization_categories_candidate', []))}

### 판단 불가 사유

{md_list(card.get('not_judgeable_reasons', []))}

## 주요 혼란변수

{md_list(confounds)}

## 문헌 근거와 한계

### 근거 한계

{md_list(card['evidence_limits'])}

### 연결 근거 ID

{md_list(card.get('evidence_refs', []))}

### 문헌 종합 초안

`{card.get('literature_synthesis_path', '없음')}`

## 세션 끝에 답할 열린 질문

{md_list(card['open_questions'])}

## 중단·종료

- 중단: 문헌 메모에 완료 지점을 남기고 JSONL export
- 종료: {count}사례 listened, 불확실 목록 확정, 현상 요약 저장, JSONL export 확인
- 화면 문제: 연구 기록과 섞지 말고 별도 UI 관찰 양식에 기록
"""


def phenomenon_html(card: dict[str, Any], count: int) -> str:
    code = card["phenomenon_code"]
    scope_html = "".join(
        f"<tr><td>{esc(label)}</td><td><code>{esc(item['condition_id'])}</code></td><td>{esc(item['description'])}</td><td>{esc(item.get('priority', '—'))}</td><td>{esc(item.get('status', '—'))}</td><td>{esc(', '.join(item.get('evidence_refs', [])) or '—')}</td></tr>"
        for label, item in scope_rows(card)
    )
    boundary_html = "".join(
        f"<tr><td>{esc(item['name'])}</td><td>{esc(item['status'])}</td><td>{esc(', '.join(item.get('evidence_refs', [])) or '—')}</td></tr>"
        for item in card.get("boundary_scopes", [])
    )
    schedule_html = "".join(
        f"<tr><td>{esc(item['order'])}</td><td>{esc(item['minutes'])}분</td><td>{esc(item['activity'])}</td><td>{esc(item['output'])}</td></tr>"
        for item in card["pilot_schedule"]
    )
    confounds = [f"{item['name']} — {item.get('status', '')}; {', '.join(item.get('evidence_refs', [])) or '근거 ID 없음'}" for item in card["confounds"]]
    contract = card.get("surface_morph_pos_contract", {})
    body = f"""
<span class=\"badge\">{esc(code)} · CANDIDATE</span><h1>{esc(card['label_ko'])}</h1>
<p class=\"lead\">{esc(card['definition_summary'])}</p>
<div class=\"notice\"><strong>{esc(card['card_status'])}</strong> — 잠정 연구 기준입니다. 사례와 문헌 근거에 따라 수정할 수 있습니다.</div>
<p><a class=\"button\" href=\"../../researcher_review_package_v2/STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html?phenomenon={esc(code)}\">reviewer에서 {esc(code)} 시작</a> · 준비 사례 {count}건</p>
<h2>최소 대조</h2>{html_list(card['minimum_contrast'])}
<h2>120분 진행</h2><table><tr><th>순서</th><th>시간</th><th>활동</th><th>산출물</th></tr>{schedule_html}</table>
<h2>포함·제외·별도 탐색</h2><table><tr><th>분류</th><th>조건 ID</th><th>설명</th><th>우선</th><th>상태</th><th>근거</th></tr>{scope_html}</table>
<h3>경계 범위</h3><table><tr><th>경계 범위</th><th>상태</th><th>근거</th></tr>{boundary_html}</table>
<h2>표면형·형태론·품사 확인</h2><ul><li><strong>표면형:</strong> {esc(contract.get('surface_rule', '카드에 별도 규칙 없음'))}</li><li><strong>형태론:</strong> {esc(contract.get('morph_rule', '카드에 별도 규칙 없음'))}</li><li><strong>품사:</strong> {esc(contract.get('pos_rule', '카드에 별도 규칙 없음'))}</li><li><strong>불일치 상태:</strong> <code>{esc(contract.get('mismatch_status', 'surface_analysis_mismatch'))}</code></li></ul>
<h3>고위험 오인</h3>{html_list(contract.get('high_risk_examples', []))}
<h2>사례를 들을 때 확인할 것</h2>{html_list(card['human_review_items'])}<p>발화 전체 → 표적 주변 → 범위 → 실현 순서로 확인합니다. 형태소·MFA phone·TextGrid는 실현 정답이 아닙니다.</p>
<h3>잠정 실현 범주</h3>{html_list(card.get('realization_categories_candidate', []))}<h3>판단 불가 사유</h3>{html_list(card.get('not_judgeable_reasons', []))}
<h2>주요 혼란변수</h2>{html_list(confounds)}
<h2>문헌 근거와 한계</h2><h3>근거 한계</h3>{html_list(card['evidence_limits'])}<h3>연결 근거 ID</h3>{html_list(card.get('evidence_refs', []))}<p><strong>문헌 종합 초안:</strong> <code>{esc(card.get('literature_synthesis_path', '없음'))}</code></p>
<h2>세션 끝에 답할 열린 질문</h2>{html_list(card['open_questions'])}
<div class=\"safe\"><strong>종료:</strong> {count}사례 listened · 불확실 목록 확정 · 현상 요약 저장 · JSONL export 확인</div>
"""
    return page(f"{code} 실제 연구 안내서", body, nested=True)


def session_checklist_markdown() -> str:
    return """# 실제 연구 세션 체크시트

## 시작 전

- [ ] 동기화된 로컬 폴더에서 열었다.
- [ ] 오늘 작업할 현상과 종료 단계를 정했다.
- [ ] 헤드폰·조용한 방·음량을 확인했다.
- [ ] 재개라면 최신 정본 JSONL 하나만 불러오고 `n행 불러옴`을 확인했다.
- [ ] 문헌 메모에 빌드·청취 환경을 남겼다.

## 문헌 20분

- [ ] 정의·핵심 주장·자료 범위·근거 한계를 읽었다.
- [ ] 설명되는 사례와 적용되지 않는 사례를 분리했다.
- [ ] 추가 확인할 질문을 적었다.

## 범위 10분

- [ ] primary/peripheral/exploratory/out_of_scope/unclear를 확인했다.
- [ ] 범위 판정과 실현 판정을 섞지 않았다.
- [ ] 형태소·MFA phone을 자동 정답으로 사용하지 않았다.

## 사례 60분

- [ ] 먼저 듣고 나중에 문헌·형태론 정보를 확인했다.
- [ ] 각 사례에서 범위·실현·두 확신도를 기록했다.
- [ ] 판단 불가를 억지로 범주화하지 않았다.
- [ ] `[DATA]`와 `[TOOL]` 문제를 구분했다.

## 재확인 20분

- [ ] 확신도 ≤3, 범위 불확실, 경계 필요/불확실 사례를 모았다.
- [ ] 확실 대조 2–3건을 포함했다.
- [ ] 초과분은 이월 목록으로 남겼다.

## 요약 10분

- [ ] 중심·주변·탐색 패턴을 분리했다.
- [ ] 문헌 일치·불일치·판단 불가를 구분했다.
- [ ] 대안 설명과 다음 질문을 남겼다.
- [ ] 현상 요약을 저장했다.
- [ ] `YYYY-MM-DD_현상코드_reviewer_v2.jsonl`을 보관했다.

## 종료 조건

- [ ] 12사례 listened
- [ ] 불확실 목록 확정
- [ ] 현상 요약 저장
- [ ] JSONL export 확인
"""


def session_checklist_html() -> str:
    sections = [
        ("시작 전", ["로컬 동기화 폴더에서 열기", "현상·종료 단계 정하기", "헤드폰·방·음량 확인", "최신 JSONL 하나 불러오기", "빌드·환경 메모"]),
        ("문헌 20분", ["정의·주장·자료·한계 읽기", "적용·비적용 사례 분리", "추가 질문 기록"]),
        ("범위 10분", ["다섯 범위 범주 확인", "범위와 실현 분리", "자동 정보는 보조로만 사용"]),
        ("사례 60분", ["먼저 듣고 나중에 정보 확인", "범위·실현·확신도 기록", "판단 불가 보존", "DATA/TOOL 구분"]),
        ("재확인 20분", ["확신도 ≤3·불확실·경계 사례", "확실 대조 2–3건", "초과분 이월"]),
        ("요약 10분", ["세 모집단 패턴 분리", "문헌 일치·불일치·판단 불가", "대안·다음 질문", "현상 요약 저장", "날짜·현상 JSONL export"]),
    ]
    cards = "".join(f"<div class=\"card\"><h2>{esc(title)}</h2>" + "".join(f"<p>☐ {esc(item)}</p>" for item in items) + "</div>" for title, items in sections)
    body = f"<span class=\"badge\">ONE SESSION</span><h1>실제 연구 세션 체크시트</h1><p class=\"lead\">긴 안내서를 반복해서 읽지 않고 현재 단계와 다음 행동만 확인합니다.</p><div class=\"grid\">{cards}</div><div class=\"safe\"><strong>종료 네 항목:</strong> 12사례 listened · 불확실 목록 확정 · 현상 요약 저장 · JSONL export 확인</div>"
    return page("실제 연구 세션 체크시트", body)


def ui_template_markdown() -> str:
    return """# 화면 재설계 관찰 기록

연구 내용은 reviewer JSONL에, 화면 문제는 이 문서에 분리해 기록한다.

| 날짜 | 현상 | 단계 | 등급 | 문제 | 연구 영향 | 임시 우회 | 최소 변경 | 화면 캡처 |
|---|---|---|---|---|---|---|---|---|
|  |  | 문헌/범위/사례/재확인/요약 | Blocker/Friction/Enhancement |  |  |  |  |  |

- **Blocker**: 저장·불러오기·오디오·현상 전환 실패처럼 연구를 계속할 수 없음
- **Friction**: 연구는 가능하지만 반복해서 시간을 빼앗음
- **Enhancement**: 없어도 연구할 수 있으나 있으면 편리함

같은 Friction이 둘 이상의 세션 또는 현상에서 반복될 때 다음 화면 버전을 검토한다.
"""


def ui_template_html() -> str:
    body = """<span class=\"badge\">UI EVIDENCE</span><h1>화면 재설계 관찰 기록</h1><p class=\"lead\">연구 내용과 화면 문제를 분리합니다.</p><table><tr><th>날짜</th><th>현상</th><th>단계</th><th>등급</th><th>문제</th><th>연구 영향</th><th>임시 우회</th><th>최소 변경</th></tr><tr><td>&nbsp;</td><td></td><td>문헌/범위/사례/재확인/요약</td><td>Blocker/Friction/Enhancement</td><td></td><td></td><td></td><td></td></tr></table><h2>등급</h2><ul><li><strong>Blocker:</strong> 연구를 계속할 수 없음</li><li><strong>Friction:</strong> 반복해서 시간을 빼앗음</li><li><strong>Enhancement:</strong> 있으면 편리함</li></ul><div class=\"notice\">같은 Friction이 둘 이상의 세션 또는 현상에서 반복될 때 다음 화면 버전을 검토합니다.</div>"""
    return page("화면 재설계 관찰 기록", body)


def start_html(cards: list[dict[str, Any]], counts: Counter[str]) -> str:
    cards_html = "".join(
        f"<article class=\"card\"><div class=\"code\">{esc(c['phenomenon_code'])}</div><h3>{esc(c['label_ko'])}</h3><p>{counts[c['phenomenon_code']]}개 사례 · candidate</p><div class=\"actions\"><a href=\"PHENOMENON_GUIDES/{esc(c['phenomenon_code'])}.html\">먼저 안내서</a><a href=\"../researcher_review_package_v2/STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html?phenomenon={esc(c['phenomenon_code'])}\">바로 연구</a></div></article>"
        for c in cards
    )
    body = f"""
<span class=\"badge\">STAGE2 · ALL 7 READY</span><h1>실제 연구 안내서</h1>
<p class=\"lead\">공통 절차와 현상별 기준을 먼저 확인한 뒤, 같은 카드에서 reviewer를 시작할 수 있습니다.</p>
<div class=\"notice\"><strong>연구 판단은 아직 candidate입니다.</strong> 안내서는 판단을 대신하지 않고, 근거·불확실성·수정할 기준을 체계적으로 남기도록 돕습니다.</div>
<div class=\"actions\"><a href=\"ACTUAL_RESEARCH_GUIDE.html\">공통 실제 연구 안내서</a><a href=\"SESSION_CHECKLIST.html\">세션 체크시트</a><a href=\"UI_REDESIGN_OBSERVATIONS_TEMPLATE.html\">화면 문제 기록</a></div>
<h2>현상 선택</h2><div class=\"grid\">{cards_html}</div>
<h2>짧게 시작한다면</h2><ol><li>현상 안내서에서 정의·제외·혼란변수를 읽습니다.</li><li>reviewer를 열고 문헌 20분부터 시작합니다.</li><li>중단 시 완료 지점 메모와 JSONL export를 남깁니다.</li></ol>
"""
    return page("Stage2 실제 연구 안내서 — 7개 현상", body)


def phenomenon_index_html(cards: list[dict[str, Any]]) -> str:
    rows = "".join(f"<tr><td><strong>{esc(c['phenomenon_code'])}</strong></td><td>{esc(c['label_ko'])}</td><td>{esc(c['card_status'])}</td><td><a href=\"{esc(c['phenomenon_code'])}.html\">안내서</a></td></tr>" for c in cards)
    return page("현상별 실제 연구 안내서", f"<h1>현상별 실제 연구 안내서</h1><table><tr><th>코드</th><th>현상</th><th>상태</th><th>열기</th></tr>{rows}</table>", nested=True)


def build_guides(scope_cards_path: Path, reviewer_package: Path, output_dir: Path) -> dict[str, Any]:
    scope_cards_path = scope_cards_path.resolve()
    reviewer_package = reviewer_package.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {output_dir}")
    cards = load_scope_cards(scope_cards_path)
    counts = reviewer_counts(reviewer_package)
    output_dir.mkdir(parents=True)

    write_text(output_dir / "START_HERE.html", start_html(cards, counts))
    write_text(output_dir / "ACTUAL_RESEARCH_GUIDE.md", common_guide_markdown(cards))
    write_text(output_dir / "ACTUAL_RESEARCH_GUIDE.html", common_guide_html(cards))
    write_text(output_dir / "SESSION_CHECKLIST.md", session_checklist_markdown())
    write_text(output_dir / "SESSION_CHECKLIST.html", session_checklist_html())
    write_text(output_dir / "UI_REDESIGN_OBSERVATIONS_TEMPLATE.md", ui_template_markdown())
    write_text(output_dir / "UI_REDESIGN_OBSERVATIONS_TEMPLATE.html", ui_template_html())
    write_text(output_dir / "PHENOMENON_GUIDES" / "index.html", phenomenon_index_html(cards))
    for card in cards:
        code = card["phenomenon_code"]
        write_text(output_dir / "PHENOMENON_GUIDES" / f"{code}.md", phenomenon_markdown(card, counts[code]))
        write_text(output_dir / "PHENOMENON_GUIDES" / f"{code}.html", phenomenon_html(card, counts[code]))
    write_text(
        output_dir / "RESEARCH_RECORDS" / "README.md",
        "# 연구 기록 보관\n\nreviewer에서 내보낸 JSONL을 `YYYY-MM-DD_현상코드_reviewer_v2.jsonl` 형식으로 보관한다. 현상별 최신 정본 하나를 유지하고, 이전 파일을 덮어쓰기 전에 별도 사본으로 보존한다.\n",
    )

    receipt = {
        "schema_version": "stage2_actual_research_guides_build.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope_cards_path": str(scope_cards_path),
        "scope_cards_sha256": sha256(scope_cards_path),
        "reviewer_package": str(reviewer_package),
        "reviewer_asset_manifest_sha256": sha256(reviewer_package / "ASSET_MANIFEST.csv"),
        "reviewer_html_sha256": sha256(reviewer_package / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"),
        "phenomenon_codes": list(EXPECTED_CODES),
        "sample_counts": {code: counts[code] for code in EXPECTED_CODES},
        "total_samples": sum(counts.values()),
        "candidate_status_preserved": True,
        "automatic_realization_judgement": False,
        "raw_corpus_read": False,
    }
    write_text(output_dir / "BUILD_RECEIPT.json", json.dumps(receipt, ensure_ascii=False, indent=2))

    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    manifest_lines = [f"{sha256(path)}  {path.relative_to(output_dir).as_posix()}" for path in files]
    write_text(output_dir / "SHA256SUMS.txt", "\n".join(manifest_lines))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-cards", required=True, type=Path)
    parser.add_argument("--reviewer-package", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = build_guides(args.scope_cards, args.reviewer_package, args.output_dir)
    print(json.dumps({"status": "built", **receipt}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
