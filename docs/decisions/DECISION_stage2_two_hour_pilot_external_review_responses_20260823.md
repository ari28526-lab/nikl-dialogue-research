# DECISION — Stage 2 2시간 파일럿 외부 검토 응답과 reviewer v2 재빌드 범위

- 날짜: 2026-08-23 KST
- 결정 주체: 사용자 (질문 8건에 대한 직접 답변; 8건 모두 권고안 채택)
- 근거 문서:
  - `docs/reviews/incoming/EXTERNAL_REVIEW_stage2_two_hour_pilot_workflow_claude_cowork_20260823.md`(+`.jsonl`, 제안 22건)
  - `docs/reviews/incoming/CROSSCHECK_stage2_two_hour_pilot_workflow_external_review_20260823.md`
    (22건 전건 confirmed 교차확인 + §5 신규 결함: `const history` 전역 가림으로
    현상 드롭다운 전환이 TypeError로 중단)
  - `docs/decisions/RESULT_stage2_seven_phenomena_two_hour_research_pilot_preparation_20260823.md`
- 지위: 이 문서가 reviewer 패키지 **v2 재빌드**와 **행 계약 확장(현상 요약 행)**의
  승인 근거다. 방법·출력 계약 변경분은 이 결정으로 승인되었으므로 새 외부 설계
  리뷰를 다시 열지 않는다(CLAUDE.md 규칙 9). 실행은 부록 A 프롬프트로 Codex
  세션에 위임하고, git commit·push는 사용자 검토 후 별도 지시한다.

## 1. 결정 8건

| # | 대상 | 결정 |
|---|---|---|
| 1 | WF-M1 + 신규 결함(§5) | **재빌드 승인, 개선 전부 한 빌드로 묶음.** v1 보존, v2 생성, 독립 감사 1회 재통과 후에만 파일럿 시작 |
| 2 | WF-M3 | **셔플 재확인 모드 코드 추가** — 판정 필드(들린 실현·청취 확신도)를 가린 빈 폼으로 시작, 별도 revision 저장 |
| 3 | WF-M2 | **코드 보완** — 문헌 메모 입력 즉시 localStorage 반영 + 현상 요약 전용 행·저장 버튼 추가 |
| 4 | WF-S7 | **선별 재확인 채택** — 재확인 대상 = 청취 확신도 ≤3 또는 scope unclear 또는 boundary_edit_need 불확실, 여기에 확실 사례 2–3건을 대조로 포함. 20분 초과분은 다음 현상 전에 이월 기록 |
| 5 | WF-S6 | **Praat 이관 기준 제안 문안 확정** (§2.1) |
| 6 | WF-D1 | **sidecar 미루기 동의** — 운율·동음이의어·우리말샘 의미번호·어원·빈도는 화면 무표시 유지. 운율 경계 인상만 음운 메모에 자유 기술로 수집하고 파일럿 후 sidecar 설계에 반영 |
| 7 | WF-S4 | **확신도 앵커 채택** (§2.2) — 결정 문서 기록 + 화면 셀렉트 라벨에도 표시(재빌드 포함) |
| 8 | WF-S1·S3·S5·S8·S9·S10 | **절차 규칙 6건 일괄 채택** (§2.3) |

## 2. 확정 문안

### 2.1 Praat '경계 수정 필요' 기준 (WF-S6)

실현 판정이 경계 위치에 의존하고, 현재 TextGrid 경계가 표적 자음·모음 구간을
청취상 명백히 벗어날 때만 '필요'로 표시한다. 판정과 무관한 미세 어긋남은
'불필요'로 두고 메모에만 적는다. 첫 현상에서 '필요' 건수가 12건 중 0–4건
범위인지 점검한다.

### 2.2 확신도 1–5 앵커 (WF-S4, 환경·청취 두 확신도 공통)

- 5 = 단서 명확·재청취 불필요
- 4 = 단서 우세
- 3 = 단서 있으나 상충
- 2 = 인상 수준
- 1 = 추측

### 2.3 절차 규칙 6건 (WF-S1·S3·S5·S8·S9·S10)

1. (S1) 60분 사례 단계 시작 때 문헌·범위 패널을 접는다. 먼저 듣고 실현
   판정·확신도를 적은 뒤 문헌 연결 메모를 쓴다.
2. (S3) JSONL 불러오기 후 반드시 "n행 불러옴" 메시지를 확인하고, 없으면
   진행하지 않는다.
3. (S5) 데이터 문제(전사 오류·음질)는 `[DATA]`, 도구 문제(화면 버그)는
   `[TOOL]` 접두어로 불확실성 메모에 적는다.
4. (S8) 세션마다 문헌 메모 끝에 "빌드 8043eb25…, 헤드폰, 조용한 방" 형식의
   세션 노트 한 줄을 남긴다.
5. (S9) export 직후 파일명에 날짜·현상을 붙여 정본 폴더에 1개만 보관하고,
   다음 세션에는 그 1개만 불러온다.
6. (S10) 현상 종료 조건 = 12사례 listened + 불확실 목록 확정 + 현상 요약
   기록 + JSONL export·보관 확인의 4항 체크 후 다음 현상으로 이동. 중단 시
   문헌 메모 끝에 "어디까지 완료" 한 줄.

## 3. v2 재빌드 코드 변경 범위 (A–H)

- **A (WF-M1)** START_HERE 현상 링크 라벨 7건을 scope card `label_ko` 단일
  소스에서 생성. 수용 기준: 카드와 문자열 diff 0.
- **B (신규 결함)** 메인 스크립트 최상위 `const history=…`를 다른 이름으로
  개명해 `window.history` 가림을 제거하고, replaceState 호출은
  `window.history.replaceState`로 명시. 수용 기준: 드롭다운 현상 전환이 오류
  없이 목록·본문·URL을 갱신.
- **C (WF-S2)** 오디오 옆 "표적 구간으로 이동" 버튼(`audio.currentTime =
  target_xmin`). 수용 기준: 임의 3사례 동작.
- **D (WF-M2)** ① lit-note input 즉시 localStorage 저장(이 편집만으로는 dirty
  미설정) ② "현상 요약 저장" 버튼 → 현상 수준 행 append(schema_version
  `stage2_two_hour_phenomenon_summary.v1`, record_role
  `phenomenon_summary_exploratory_only_not_formal_ledger`, 현상별 summary
  revision 체인) ③ 사례 집계(latest·renderList·progress)에서 summary 행 제외
  ④ import가 summary 행 수용 ⑤ 메모 복원 우선순위 localStorage → import된
  최신 summary 행 → 최신 사례 행 필드(기기 간 복원 결함 해결).
- **E (WF-M3)** shuffled 모드에서 해당 사례의 최신 저장 행이 grouped 저장분이면
  들린 실현·청취 확신도 두 필드만 빈 값으로 시작(최신 행이 shuffled 저장분이면
  그대로 복원). "재확인 모드" 배너에 §1-4 선별 기준 한 줄 표시. 저장은 기존
  append-only 새 revision 그대로.
- **F (WF-S4)** 두 확신도 셀렉트 옵션 라벨에 §2.2 앵커 표기(저장 값은 1–5
  유지 — 행 계약 불변).
- **G (WF-S6+절차)** 패키지 README·START_HERE에 §2.1 기준, §1-4 선별 기준,
  §2.3 절차 규칙 6건 반영. boundary_edit_need 라벨 옆 기준 힌트 한 줄.
- **H (WF-S3 코드 부분)** import 핸들러 try/catch — 실패 시 행 번호 포함
  오류를 import-status에 표시, imported 무변경. (import를 D에서 어차피
  수정하므로 이번 빌드에 포함. 외부 검토의 "코드(후속)" 권고에 해당하며 행
  계약 불변.)

## 4. 이번 빌드에서 제외 (동결 유지)

- 행 `build_sha` 필드, import event_uuid dedupe, export 파일명 timestamp
  (WF-S8·S9의 코드 부분 — 정식 단계 스키마 v2로 미룸)
- not_judgeable 사유 선택지화(WF-D3), 재생 횟수 로그(WF-D4), 단계 타이머
  UI(WF-D2)
- 표본 84행·query 16종·문헌 claim 데이터 무변경. 빌드 입력 samples SHA-256
  `8043eb2564e041881051cad4c8f92370b061b363572ad8a4afb21c2e33eaca9f` 불변.
- 사례 행(`stage2_two_hour_exploratory_review.v1`)의 기존 필드·값 계약 불변.

## 5. 산출·검증 요구

- `researcher_review_package_v1`·`reviewer_package_audit_v1` 보존(무수정),
  빌더 `--output-dir`로 `researcher_review_package_v2` 생성.
- 감사 스크립트에 A·B·C·D·F 존재 검증을 추가한 뒤 v2 재감사 →
  `reviewer_package_audit_v2/`.
- Node 런타임 테스트 강화: `vm.Script` 컴파일 검사만으로는 B 같은 실행기
  오류를 못 잡았음(교차확인 §5)을 반영해 회귀 어서션 추가.
- Python 테스트 갱신·전체 통과, 검증 로그 파일 보존.
- 파일럿 시작은 v2 감사 통과 + 사용자 화면 확인(부록 A §6 체크리스트 7항)
  뒤에만.

## 부록 A — Codex 실행 프롬프트 (전달본)

```text
[Codex 작업 지시 — stage2 2시간 파일럿 reviewer 패키지 v2 재빌드]

작업 디렉터리: C:\Users\ari30\research\2026_summer_research
파이썬: C:\Users\ari30\miniforge3\envs\mfa\python.exe

## 0. 먼저 읽을 것 (순서대로)
1. docs/decisions/DECISION_stage2_two_hour_pilot_external_review_responses_20260823.md
   — 이번 작업의 승인 근거이자 범위 정본(변경 항목 A–H, 확정 문안, 제외 목록)
2. docs/reviews/incoming/CROSSCHECK_stage2_two_hour_pilot_workflow_external_review_20260823.md
   — 코드 위치(압축 HTML 행 번호)·브라우저 실측 재현 로그·신규 결함 §5
3. docs/reviews/incoming/EXTERNAL_REVIEW_stage2_two_hour_pilot_workflow_claude_cowork_20260823.md
   — 원 제안 22건 (같은 이름 .jsonl 병행)
4. scripts/python/build_stage2_two_hour_seven_phenomena_reviewer.py,
   scripts/python/audit_stage2_two_hour_seven_phenomena_reviewer.py,
   tests/test_stage2_two_hour_seven_phenomena_reviewer.py,
   tests/test_stage2_two_hour_seven_phenomena_reviewer_runtime.js

## 1. 목표
outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/
researcher_review_package_v1 을 그대로 보존한 채, 빌더를 수정해 같은 부모 아래
researcher_review_package_v2 를 생성한다. 표본 84행·query·문헌 데이터는 불변
(빌드 입력 samples SHA-256
8043eb2564e041881051cad4c8f92370b061b363572ad8a4afb21c2e33eaca9f)이고,
화면 코드·라벨·패키지 문서만 바뀐다.

## 2. 변경 항목 A–H (전부 빌더/내장 템플릿 수정으로 구현)
A. (WF-M1) START_HERE.html 현상 링크 라벨 7건을 scope card의 label_ko 단일
   소스에서 생성. 수용: config/phenomenon_scope_cards_candidate_v1_20260823.jsonl
   의 label_ko와 문자열 diff 0.
B. (신규 결함) 메인 스크립트 최상위 `const history=…`가 window.history를 가려
   현상 드롭다운 전환이 "history.replaceState is not a function" TypeError로
   중단된다(CROSSCHECK §5 실측). 이 상수를 다른 이름(예: reviewRows)으로
   개명하고 replaceState 호출은 window.history.replaceState 로 명시. 수용:
   드롭다운 전환 시 오류 없이 목록·본문·URL 갱신.
C. (WF-S2) 오디오 옆 "표적 구간으로 이동" 버튼: audio.currentTime = 해당 사례
   target_xmin. 수용: 임의 3사례에서 동작.
D. (WF-M2) 문헌 메모·현상 요약:
   - phenomenon-lit-note input 즉시 localStorage(_lit_ 키) 저장. 이 편집만으로는
     dirty를 세우지 않는다(자동 저장되므로 이동 확인창 대상 아님).
   - "현상 요약 저장" 버튼 추가 → 현상 수준 행 append: schema_version
     "stage2_two_hour_phenomenon_summary.v1", record_role
     "phenomenon_summary_exploratory_only_not_formal_ledger", phenomenon_code,
     phenomenon_literature_note, event_uuid·revision_seq·supersedes_event_uuid
     (현상별 summary 체인), reviewed_at. sample_id는 빈 값 또는 필드 생략 중
     택1 후 문서화.
   - latest()·renderList()·progress 등 사례 집계는 summary 행을 제외한다.
   - import가 summary 행을 수용한다(사례 행만 SAMPLE_MAP 검증).
   - renderLiterature의 메모 복원 우선순위: localStorage → import된 최신
     summary 행 → 최신 사례 행의 phenomenon_literature_note. (다른 기기에서
     JSONL만 불러오면 메모가 복원되지 않던 결함 해결)
E. (WF-M3) 셔플 재확인 모드: order-mode가 shuffled이고 해당 사례의 최신 저장
   행이 grouped 저장분이면 realization_impression·realization_confidence 두
   필드만 빈 값으로 시작한다(최신 행이 shuffled 저장분이면 그대로 복원).
   배너 표시: "재확인 모드 — 1차 판정(들린 실현·청취 확신도)은 가려집니다.
   재확인 대상: 청취 확신도 ≤3 / scope unclear / 경계 불확실 + 대조 2–3건".
   저장은 기존 append-only 새 revision 그대로(review_order_mode로 구분).
F. (WF-S4) 두 확신도 셀렉트의 옵션 라벨에 앵커 표기(저장 값은 1~5 그대로):
   5 단서 명확·재청취 불필요 / 4 단서 우세 / 3 단서 있으나 상충 / 2 인상 수준
   / 1 추측.
G. (WF-S6+절차) 패키지 README와 START_HERE에 결정 문서의 확정 문안 반영:
   Praat '필요' 기준(§2.1), 선별 재확인 기준(§1-4), 절차 규칙 6건(§2.3 —
   패널 접기·먼저 듣기 / 불러오기 n행 확인 / [DATA]·[TOOL] 태그 / 세션 노트
   한 줄 / export 파일 보관 1개 원칙 / 종료 4항 체크리스트). 화면의
   boundary_edit_need 라벨 옆에도 기준 힌트 한 줄.
H. (WF-S3 코드 부분) import 핸들러에 try/catch — 실패 시 행 번호를 포함한
   오류를 import-status에 표시하고 imported는 변경하지 않는다. D의 import
   수정과 함께 구현한다.

## 3. 이번 빌드에서 하지 말 것
행 build_sha 필드, import event_uuid dedupe, export 파일명 timestamp,
not_judgeable 사유 선택지화, 재생 횟수 로그, 단계 타이머 UI. 사례 행
(stage2_two_hour_exploratory_review.v1)의 기존 필드·값 계약은 불변으로 둔다.

## 4. 검증 (전부 통과 후 보고)
1. py_compile + tests/test_stage2_two_hour_seven_phenomena_reviewer.py 를 변경
   내용에 맞게 갱신하고 전체 통과.
2. tests/test_stage2_two_hour_seven_phenomena_reviewer_runtime.js 강화:
   vm.Script 컴파일 검사만으로는 B 같은 실행기 오류를 못 잡았다(CROSSCHECK
   §5). 최소 회귀 어서션 추가 — 메인 스크립트에 `const history=` 부재,
   `window.history.replaceState` 사용, 점프 버튼·현상 요약 저장·앵커 문자열
   존재. 가능하면 최소 DOM 스텁으로 스모크 실행하되 새 외부 의존성은 추가하지
   않는다.
3. scripts/python/audit_stage2_two_hour_seven_phenomena_reviewer.py 에 신규
   검사(A 라벨 일치, B 가림 부재, C 점프 버튼, D summary 행 지원, F 앵커)를
   추가한 뒤 v2 대상으로 재실행 → reviewer_package_audit_v2/ 에 감사 JSON
   생성. v1 감사 산출물은 무수정.
4. 검증 로그를 파일로 남기고 경로를 보고에 포함.

## 5. 금지·안전 (위반 소지가 보이면 중단하고 질문)
- D:\00_RAW 등 원자료·r3·6-tier 무접근·무수정. 이번 작업은 전부 C: 저장소 안.
- query 16종·probe 산출·표본 84행·문헌 claim 데이터 무변경. config/ 의 기존
  파일 무수정(꼭 필요하면 새 버전 파일 추가만).
- researcher_review_package_v1, reviewer_package_audit_v1,
  docs/reviews/incoming/ 의 기존 문서 무수정.
- 자동 실현 판정·MFA·KOINA·wav2vec2·대량 음성 처리 금지.
- git commit·push 금지 — 변경 파일 목록 보고까지만. partial·로그 자동 삭제
  금지.
- .ps1 을 수정·생성하면 UTF-8 BOM(EF BB BF)을 확인하고 PowerShell 5.1 호환
  (&&·|| 미사용)을 지킨다. 생성 텍스트는 UTF-8.

## 6. 완료 보고 형식
- 수정 파일 목록과 A–H 항목별 구현 요약.
- v2 패키지 경로, 감사 JSON 경로, 테스트·검증 로그 경로.
- docs/decisions/RESULT_stage2_two_hour_reviewer_v2_rebuild_20260823.md 초안
  작성 + docs/decisions/_INDEX.md 상단 한 줄 추가 +
  docs/WORK_HISTORY_2026-08.md 말미 항목 추가.
- 사용자 화면 확인 체크리스트 7항을 제시: ① 드롭다운 현상 전환 정상
  ② 표적 점프 버튼 ③ 메모 입력 후 사례 이동해도 유지 ④ "현상 요약 저장" 행이
  export JSONL에 존재 ⑤ 셔플 모드에서 판정 필드 빈 폼 ⑥ 깨진 JSONL 불러오기
  오류 표시 ⑦ START_HERE 라벨 7건 = 카드 label_ko.
- 파일럿 시작은 v2 감사 통과 + 사용자 화면 확인 뒤에만 한다.
```
