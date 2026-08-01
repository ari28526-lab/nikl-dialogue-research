# 외부 리뷰: 전체 workflow 감사와 구조 리셋

- 감사일: 2026-08-01 KST
- 감사 범위: 결정→문서→config/schema→runner→test→실물 artifact 반영 사슬,
  검수 가치, 진행 교착 원인, archive/구조 refresh
- 감사 방법: 정본 문서 통독 + 코드 파일:줄 단위 대조 + `outputs/reports` 및
  D: manifest 읽기 전용 실측 + Git 이력. 문서의 완료·GO 표현은 근거로 쓰지 않았다.
- 동반 산출물:
  - `WORKFLOW_DECISION_TRACE_20260801.csv` (결정–반영 추적 18건)
  - `WORKFLOW_VALIDATION_VALUE_20260801.csv` (검수 가치 판정 18건)
  - `WORKFLOW_ARCHIVE_CANDIDATES_20260801.csv` (문서 이동안)
  - `PROJECT_CURRENT_STATE_REFRESH_DRAFT_20260801.md` (새 현재상태 초안)

## 1. 최종 판정 — GO

**2020 생산 진입은 GO다. 코드 수정 없이 시작할 수 있다.**

근거: 실물 대조 18개 항목 전부에서 문서 주장과 실측이 일치했고(불일치 0),
runner 배선 감사 10개 질문 전부가 파일:줄 단위로 확인됐다. 남은 blocker는
코드 결함이나 미검증 위험이 아니라 **정의된 실행 순서 그 자체**다:
① 2020 검색표 shard 2–23 재개, ② 승인 제외 계약(연구자 서명), ③ preflight `GO`.
이 중 사람이 해야 하는 것은 ②뿐이다.

단, "GO"에는 다음 두 가지 **비차단 조건**이 붙는다 (계산을 막지 않음):

1. 대체된 검토 적체 3건(§5)을 공식 폐지하고 CURRENT_STATE를 교체한다 —
   폐지하지 않으면 교착 패턴이 재발한다.
2. 전수 실행 기간에는 새 파일럿·새 설계 외부 리뷰를 열지 않는다
   (방법 계약 변경 시에만 예외).

## 2. 실제 현재 상태

문서가 아니라 실측으로 확인한 상태다.

| 영역 | 실측 결과 | 근거 |
|---|---|---|
| r2 사전 release/adoption | 실제 `success`/`passed`, `allow_yearly_mfa=true`, SHA 일치 | D: `00_contract\*.json` 직접 판독 |
| 동결 search master | 실물 존재, 5,103,356발화·17,156세션, `success` | `_build_meta.json` |
| 2020 morph_search.v3 | 실제 1/23 정지, `paused_after_max_shards`, lock 파일 0건 | D: `YEAR_PROGRESS.json` + find |
| 신규 r2 MFA | 실제 미시작 — `D:\mfa_eojeol\year_queue` 및 6-tier staging 폴더 자체가 없음 | D: 디렉터리 실측 |
| 최종 preflight | `NO_GO`, 유일 사유는 승인 계약 부재(사전·공간·lock·테스트는 전부 passed) | `PREFLIGHT_mfa_year_queue_...json` |
| 생산 코드 배선 | 6-tier·동반표·승인제외·checkpoint 전부 기본 경로에 강제 | §4 참조 |
| 회귀 증거 | 60발화 42/42·24/24 gzip SHA, Parquet 왕복 24/24, spn 0 — 전부 실물 JSON 확인 | `outputs/reports/EVIDENCE_*` |

**중요한 총평**: 이 프로젝트의 문서는 과장 방향의 거짓이 거의 없다. 오히려
두 곳에서 **코드가 문서보다 앞서** 있었다(§4의 T11, T17). 교착의 원인은
"반영 안 된 결정"이 아니라 **검수 구조 자체**다(§3).

## 3. 검수 교착의 근본 원인

7/24 이후 5주간 전수 생산이 시작되지 못한 원인을 4종으로 분류한다.

### 3.1 기술 원인 (작음)

r1의 숨은 `spn`, PowerShell CP949/BOM, Dropbox rename lock 등 실제 결함이
연쇄적으로 나왔으나 모두 해결됐다. 기술 부채는 현재 blocker가 아니다.

### 3.2 의사결정 원인 (핵심): 설계가 파일럿마다 재발견됨

표시 계약이 5주간 4번 바뀌었다:
3-tier → 4-tier(legacy morphemes) → 4-tier(utterance_search) →
5-tier(phoneme 보조) → **6-tier(현행)**.

각 재설계마다 「새 파일럿 → 새 Dropbox 검토본 → 새 외부 리뷰 → 수정」
사이클이 돌았고, **이전 사이클의 연구자 검토는 완료되기 전에 대상 자체가
대체됐다** (REVIEW.xlsx 60행 중 1행 검토 시점에 tier 재설계 결정,
12발화 검토 중 phoneme 파일럿 추가, phoneme 수용 대기 중 6-tier 확정).
즉 검토가 느려서가 아니라, **검토 완료보다 설계 진화가 빨라서** 어떤 검토도
끝까지 간 적이 없다. 이것은 파일럿이 제 역할(위험 조기 발견)을 한 결과이기도
하므로, 처방은 "검토를 더 빨리"가 아니라 **"설계 동결 후에는 검토 대상을
다시 만들지 않기"**다. 현재 6-tier는 외부 리뷰·회귀·mini pilot까지 통과했으므로
동결 조건이 성립했다.

### 3.3 검수 운영 원인: gate는 추가만 되고 은퇴하지 않음

7/28 이후 외부 리뷰 프롬프트 7건이 각각 새 gate를 낳았으나, 어떤 리뷰도
기존 gate를 폐지하지 않았다. 그 결과 사람 검토 대기열에 서로 다른 세대의
검토 5건(60행·12발화·phoneme·mini pilot·승인계약)이 동시에 쌓였고, 이 중
3건은 이미 무의미해졌는데 공식 폐지가 없어 "해야 할 일"로 계속 노출됐다.
**검수 가치표(V01–V03)의 폐지 판정이 이번 리뷰의 실질 처방이다.**

### 3.4 문서 원인: 상태 정본이 append-only

`PROJECT_CURRENT_STATE.md` 안에 "최신 정지점"이 3개 공존하고, 과거의
"다음 작업"들이 그대로 남아 있다. 세션이 바뀔 때마다 현재 상태를 재구성하는
비용이 커졌고, 문서와 코드의 선후 관계를 확인하는 감사(본 리뷰 포함)가
반복적으로 필요해졌다. 처방은 §9.

## 4. 반영됐다고 했지만 미반영/부분반영인 항목

전체 추적은 `WORKFLOW_DECISION_TRACE_20260801.csv` (18건: fully 12, partially 2,
not_applied 3, superseded 1). 주의가 필요한 것만 요약한다.

| # | 항목 | 실태 | 판정 |
|---|---|---|---|
| T16 | morph_search.v3 ↔ MFA 연도 큐 연결 gate | 코드 상호 참조 0건. 두 runner는 동결 search master를 각자 확인할 뿐 | not_applied — 단 결정 자체가 본 리뷰에 위임돼 있었음. §8에서 판정 |
| T09 | pre-MFA 7표+post-MFA 4표 joined 검색층 | `duckdb` 0건, `build_search_parquet.py` 미작성(색인에 정직 기록) | not_applied — 의도된 후행. MFA를 막지 않음 |
| T10 | 우리말샘 1:N 후보표 연결 | 연결 코드 부재 + **선행조건인 reference 어휘부 4종이 구 HDD 유일본** | not_applied — Stage 5 과제. HDD 회수가 먼저 |
| T06 | 조합검색 전수 | 2020 1/23, 2021–2025 미생성 | partially — 재개 명령 하나로 진행 |
| T11 | phoneme_r_auto 연도 runner 배선 | CURRENT_STATE는 "아직"이라 하나 **실제로는 배선 완료** | 문서가 낡음(진행 과소 기록) |
| T17 | alignment_contract 배선 | SCRIPTS_INDEX는 "배선 대기"라 하나 **실제로는 전 연도 무조건 실행+큐 소비** | 문서가 낡음 |
| 추가 | **CLAUDE.md의 진입점 링크** | `TODO_A단계.md`(7/23 동결)와 `HANDOFF_pilot_search_master.md`(대체됨)를 여전히 정본·새 세션 시작점으로 지정. `docs/README.md` 색인도 폐기된 r1 RUNBOOK을 "실행 정본"으로 라벨 | **새 세션이 낡은 경로로 유도될 실위험** — §9-0에서 최우선 수정 |

반대로 다음은 **주장대로 실재함**을 확인했다: 6-tier 기본 경로 강제(legacy
4-tier 폴백은 기본 경로에서 도달 불가), 승인 제외 4중 방어(자동 승인 경로
미발견, pending 행 1개만 있어도 계약 build 실패), 무인 큐의 full-clean 미전달,
`start_full_mfa_after_review.ps1`의 JSON 파싱 GO 검증, KOINA seam 금지 하드코딩.

## 5. 의미 없는·중복된 검수

전체 판정은 `WORKFLOW_VALIDATION_VALUE_20260801.csv`. **즉시 폐지 4건**:

1. **V01 — REVIEW.xlsx 59행 개별 검토**: 검토 대상(legacy 4-tier)이 6-tier로
   대체됐고, 이 검토의 성과(G-TIER-01/G-CSV-01)는 이미 코드에 반영·기계 검증됨.
2. **V02 — 12발화 utterance_search 검토**: 같은 이유. padding 버그 발견이라는
   성과를 이미 냈고 대상 스키마가 폐기됨.
3. **V03 — phoneme 5-tier 수용 검토**: 연구자의 6-tier 승인이 이 검토의 상위
   결정을 이미 내렸음.
4. **V13 — difference inventory 반복**: 완료·목적 달성. 논문 증거로 보존만.

**통합 1건**: V05 mini pilot 육안 확인은 2020 첫 연도 표본 검토에 흡수.

**조건부 전환 2건**: V08(2021–2025 연도별 사람 표본 검토)은 차단 gate에서
비차단 병행 검토로 완화 권고(§8 Gate B). V12(설계 외부 리뷰)는 본 리뷰를
마지막으로, 방법 계약이 바뀔 때만 재개.

**같은 invariant의 중복 검사**는 사람 검수 쪽에 있었고(위 4건이 그 사례),
기계 gate 쪽 중복은 의도된 독립 이중화(exporter 보고 vs 독립 감사)라서
비용이 거의 없으므로 유지가 옳다.

## 6. 유지해야 할 검수와 사람 판단

사람에게 남는 것은 정확히 3종이다. 각각 "무엇을 보고 무엇을 기록하는가"를
한 문장으로 고정한다.

1. **승인 제외 검토(V06, 연도당 1회)**: 자동 분류된 제외 후보 각 행의
   사유·범위·증거에 동의하는지만 판정한다 — 음성 청취 불필요, 후보 0건이면
   0행 계약 서명만.
2. **2020 첫 연도 표본 검토(V07, 1회)**: 표본 발화(화자 5명 이상)의 WAV를
   듣고 TextGrid·CSV 연결과 경계가 연구 열람에 쓸 만한지, 문제 발화의
   제외/재수출 필요만 기록한다 — 음운 실현 판정이 아니다.
3. **파괴적 작업 승인**: archive/prune/문서 이동 실행 전 승인 (기존
   dry-run→승인 토큰 체계 유지).

기계 유지: preflight(V09), shard SHA·원자 승격(V14), 연도 6-tier 감사+DB
표본 재수출(V15), 전체 테스트·정적 검사(V16), cross-year audit(V18).

## 7. 최단 최종 생산 순서

각 단계에 사용자 행동은 최대 1개다. 명령은 전부 커밋된 스크립트 1줄이며
결과는 `logs/`·manifest로 남는다 (콘솔 한 줄 지시 금지 원칙 준수).

### ① 지금 즉시, 계산 없이
- 본 리뷰 반영: V01–V03 폐지 선언, CURRENT_STATE 교체(초안 제공됨),
  SCRIPTS_INDEX 낡은 2행 갱신, archive 이동안 승인. **사용자 행동: 이 리뷰
  결과 승인 1회.**

### ② 2020 신규 MFA 전
- `run_morph_search_year_safe.ps1 -Year 2020` 재개 → shard 2–23 → `YEAR_MANIFEST=success` (기계, 약 1시간대)
- `prepare_full_mfa_approval_reviews.ps1` → 6개년 lab 검증·제외 후보표 (기계, MFA 미시작)
- **사용자 행동: 제외 후보 승인/기각 1회** (연도별 후보표, 0건이면 0행 서명)

### ③ 2020 첫 생산 연도
- `start_full_mfa_after_review.ps1 -ApprovedBy <연구자>` → preflight `GO` 확인 후
  연도 큐가 2020 MFA→6-tier→동반표→독립 QC→표본 재수출까지 무인 수행
- **사용자 행동: 2020 표본 검토 1회(V07)** → `machine_qc_passed_human_review_pending` 해제

### ④ 2020 Gate B 후 2021–2025
- 방법 계약 변경 없음 확인(기계) → 같은 큐가 연도별 순차 무인 진행.
  연도별 morph_search는 MFA와 I/O 경합 없는 시간대에 독립 실행 가능.
- **사용자 행동: 연도별 제외 후보 승인만** (그 외 표본 검토는 비차단 병행 — §8)

### ⑤ 6개년 정렬 후 최종 검색 인프라
- joined 검색층(7표+4표 → Parquet/DuckDB view) 신규 작성 + 회귀 질의(Q1–Q7 기계화)
- HDD reference 회수 후 우리말샘 1:N 후보표 연결
- **사용자 행동: 검색층 설계 확인 1회**

### ⑥ 선별 실제 연구
- 후보 bundle → KOINA/이어붙이기/wav2vec2(선별) → manual judgment 표.
- 여기서부터가 언어학적 판단의 본령이다.

## 8. 2020 GO 조건과 Gate B

**2020 GO 조건 (전부 기계 판정, 사람 1회)**:
1. `YEAR_MANIFEST=success` (2020 검색표) — hard gate가 아니라 **운영 순서**로
   먼저 완료 (아래 판정 참조)
2. 2020 승인 제외 계약 존재·input contract 결속 (사람 서명)
3. `preflight_mfa_year_queue.ps1 -RunRepositoryTests` = `GO`

**T16 판정 — 검색표 manifest를 MFA hard gate로 할 것인가**: **아니오.**
두 산출물의 정합성 원천은 "같은 동결 search master"이며, 이는 양쪽 runner가
이미 각자 `_build_meta.json`으로 검증한다. 검색표는 정렬 후에도 재생성
가능한 레이어이므로 YEAR_MANIFEST를 MFA의 코드 gate로 만들면 불필요한
직렬화가 생긴다. 대신 **preflight에 "두 runner가 같은 `_build_meta` SHA를
봤는가" 확인 1줄 추가**만 권고한다(소규모 수정, 전수 중 아무 때나 가능).
2020에 한해서는 원 입력 문제를 조기 발견하기 위해 검색표 선완료를 운영
순서로 유지한다(§7-②).

**Gate B (2020 → 2021–2025 허가, 전부 기계)**:
1. 2020 입력·정렬·출력·QC manifest가 동일 input/alignment contract를 가리킴
   (`preflight_next_year_after_research_qc.py` — 이미 구현·배선 확인)
2. 방법 계약 SHA 변경 없음
3. 2020 표본 검토(V07) 완료 기록
4. D: 여유 공간 확인

Gate B 통과 후 2021–2025에서는 **연도별 사람 표본 검토를 차단 gate에서
해제**할 것을 권고한다(V08). 근거: 방법 동일성은 기계 gate가 검사하는
invariant이고, 사람 검토가 차단하는 위험 중 계약 불변 조건에서 기계가 못
잡는 것이 파일럿·2020 검토 이후에는 남지 않는다. 검토는 병행하되 "정본
승격"만 검토 뒤로 미루면, 계산은 멈추지 않고 안전 의미는 유지된다.
(이 완화는 사용자 결정 사항이다 — 기본값 변경이므로 Gate B 시점에 1회 확인.)

## 9. archive·구조 refresh 권고

원칙: **물리 이동 최소, index·상태 header 우선.** Git이 있으므로 삭제는
없다. 문서 106개 전수 분류 결과: canonical_active 27 / supporting_evidence 17 /
historical_valid 40 / superseded 17 / failed_diagnostic 2 /
generated_review_artifact 2 / unknown 0. 스크립트→문서 참조는 전부 주석
수준이나, `build_textgrid_v2_mini_pilot.py:275`는 문서 경로를 산출물
manifest에 기록하므로 `PROPOSAL_Seoul_...`은 **이동 절대 금지**다. 상세
파일별 이동안은 `WORKFLOW_ARCHIVE_CANDIDATES_20260801.csv`.

0. **최우선(오도 위험 제거)**: CLAUDE.md가 대체된 `TODO_A단계.md`·
   `HANDOFF_pilot_search_master.md`를 정본·세션 시작점으로 지정하고 있고,
   `docs/README.md`는 폐기된 r1 RUNBOOK을 "실행 정본"으로 라벨하고 있다.
   새 세션·새 도구가 낡은 경로로 유도되는 실위험이므로 CLAUDE.md와
   README 색인 갱신을 이동 작업보다 먼저 한다.
1. **CURRENT_STATE 교체**가 개편의 90%다. 현재 파일을
   `docs/archive/PROJECT_CURRENT_STATE_20260801_full.md`로 `git mv`하고,
   제공된 80줄 초안으로 교체한다. 이후 규칙: 이 파일은 **append 금지,
   전체 교체만** — "최신 정지점"이 2개가 되는 순간이 부패의 시작이다.
2. **START_HERE 일원화**: `docs/environment/PROJECT_START_HERE.md`는 이미
   자기 자신을 낡았다고 표시한 문서다. 상단 리다이렉트 3줄만 남기거나
   archive하고, 진입점을 `docs/README.md` 하나로 고정한다.
3. **RUNBOOK 일원화**: §7의 6단계를 `docs/RUNBOOK_production_2020_2025.md`
   하나로 만들고, 구 RUNBOOK 6종은 헤더에 상태 표식(`superseded by ...`)만
   추가한다 (물리 이동 불필요 — 코드·문서 참조가 많아 이동 위험이 큼).
4. **decision 53개**: 물리 이동 대신 `docs/decisions/_INDEX.md`를 신설해
   `canonical_active`(약 10개) / `historical_valid` / `superseded` /
   `failed_diagnostic`을 표로 선언한다. superseded 문서에는 헤더 1줄
   (`> 상태: superseded by X — 역사 기록용`)만 추가한다. 이 방식이면
   `git mv` 링크 깨짐 위험이 0이다.
5. **generated_review_artifact** (Dropbox 검토본, `outputs/`의 구 파일럿
   폴더, `019f9337-...` 폴더 등)는 재생성 가능하므로 리포에서는 목록
   manifest만 유지하고, 정리는 전수 완료 후 일괄 (지금 하지 않음).
6. 이동 실행 시 순서: manifest 작성 → 사용자 승인 → `git mv` →
   `rg "docs/"` link 검증 → 커밋. rollback은 해당 커밋 revert 하나로 끝나게
   이동을 단일 커밋으로 묶는다.

## 10. 사용자가 지금 할 한 가지

**이 리뷰의 폐지 판정(V01–V03)과 CURRENT_STATE 교체를 승인한다** — 그러면
다음 계산 명령은 자동으로 정해진다:
`scripts\run_morph_search_year_safe.ps1 -Year 2020` (shard 2–23 재개, 기계).

이 승인 하나로: 검토 적체 5건 → 1건(승인 제외)으로 줄고, "다음에 뭘 해야
하지"가 §7의 단일 경로로 고정되며, 이후 사람이 기다려야 하는 지점은
②의 제외 승인과 ③의 2020 표본 검토, 정확히 두 번만 남는다.

## 11. 부록 — 파격적 대안 workflow 3안 (사용자 요청)

기본 권고는 §7이다. 아래는 더 공격적인 대안으로, 각각 무엇을 얻고 무엇을
포기하는지 명시한다.

**사용자 판정 (2026-08-01)**: A **기각** — 정렬 전체가 기본 산출물이므로
6개년 검색 선완주로 MFA를 미루지 않는다(§7의 순서 유지: 2020 검색표만
선완료, 2021–2025 검색표는 MFA와 경합 없는 시간대 병행).
B **채택(수정)** — 승인 창구는 주 1회가 아니라 **2일 1회**.
C **채택**.

### 대안 A — 「검색 우선, 정렬 후행」 (research-first) — 기각됨

6개년 `morph_search.v3`를 **먼저 전부** 완주한다(연도당 1시간대, CPU만,
밤 1–2회로 끝). MFA는 그 뒤 시작한다.

- 얻는 것: **연구자가 지금 당장 실제 연구 질문의 후보 검색을 시작**할 수
  있다(형태소·Roman·경계·기호 조합검색은 정렬 불필요). 5주간 인프라만
  만지며 소진된 상황에서, "내 연구 질문에 후보가 몇 건 나오는가"를 이번
  주에 보는 것은 동기 면에서 가치가 크다. 검색 스키마의 실사용 피드백을
  MFA 전에 받으므로, 스키마 재설계 위험이 정렬 이후로 새는 것도 막는다.
- 포기하는 것: 2020 MFA 시작이 며칠 늦어진다.
- 판정: §7과 모순되지 않는 **저위험 변형**. 검색과 청취를 분리할 수 있는
  연구 질문이 있다면 이 안을 권한다.

### 대안 B — 「승인 창구 2일 1회」 (non-blocking human review) — 채택됨

사람 검토를 파이프라인의 차단 지점에서 빼고, **2일 1회 고정 슬롯**으로
모든 승인(제외 후보, 표본 검토 기록, 파괴적 작업)을 일괄 처리한다.
무인 큐는 승인이 없는 연도를 건너뛰고 준비 가능한 다른 연도의 검색표·lab
검증을 계속 진행한다(현 큐 설계가 이미 이를 지원함 — 코드 수정 불필요).

- 얻는 것: "연구자가 지쳐서 검토를 못 하면 전체가 멈추는" 구조가 사라진다.
  검토가 밀려도 기계가 할 수 있는 일은 다 해 놓는다.
- 포기하는 것: 승인 지연 시 MFA 시작도 그만큼 밀린다(그러나 지금도 그렇다).
- 판정: **운영 규칙만 바꾸는 무비용 대안.** §7과 병행 채택 가능.
- 채택 형태: 2일 1회 슬롯에서 ① 제외 후보 승인, ② 완료 연도 표본 검토
  기록, ③ 파괴적 작업 승인을 일괄 처리한다. 슬롯 사이에는 큐가 준비
  가능한 작업(검색표·lab 검증·다음 연도 준비)을 무인으로 계속한다.

### 대안 C — 「문서 상태기계화」 (docs-as-state-machine) — 채택됨

활성 문서를 4개로 강제 축소한다: `README(색인)` / `CURRENT_STATE(80줄,
전체 교체만)` / `RUNBOOK(생산 6단계)` / `ASSETS_LEDGER(실측)`. 나머지
100여 개는 전부 "역사"로 선언하고(헤더 표식), 새 문서 생성 규칙을
"decision은 계약 변경 시에만, 세션 로그는 WORK_HISTORY 1파일 append만"으로
제한한다. 상태 갱신은 손으로 쓰지 않고, manifest·logs에서 상태 요약을
생성하는 스크립트(`show_project_state.ps1` 신설)로 대체한다.

- 얻는 것: 세션 시작 비용과 "문서 vs 실제" 감사 비용이 구조적으로 사라진다.
  이번 교착의 3.4 원인을 재발 불가능하게 만든다.
- 포기하는 것: 상태 요약 스크립트 작성 비용(반나절), 그리고 문서화 습관의
  전환 비용. 논문 방법론용 상세 기록은 지금처럼 decision에 남긴다.
- 판정: §9의 급진판. 전수 실행이 무인으로 도는 기간(며칠)이 이 전환을
  하기 가장 좋은 시점이다.

**확정된 최종 운영 형태 (사용자 판정 반영)**: §7의 기본 순서(정렬이
기본 축) + B(2일 1회 승인 창구) + C(문서 상태기계화). 사람의 정기 업무는
"2일 1회 승인 슬롯"으로 고정되고, 그 사이 인프라는 백그라운드 무인
작업이 된다. C의 전환 작업(활성 문서 4개 축소·상태 요약 스크립트)은
전수 MFA가 무인으로 도는 기간에 수행한다.
