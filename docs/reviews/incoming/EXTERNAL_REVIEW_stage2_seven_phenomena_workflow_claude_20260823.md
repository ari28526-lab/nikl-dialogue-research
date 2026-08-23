# EXTERNAL REVIEW: 일곱 음운현상 파일럿 착수 전 workflow·최소 입력 계약 설계 검토

- 작성: Claude (fable5, Cowork 외부 설계 검토), 2026-08-23 KST
- 성격: **설계 검토 보고서 — 구현 아님.** 코드·config·query·문헌 워크스페이스·
  원자료·TextGrid·DB를 수정하지 않았고, MFA·KOINA·wav2vec2를 실행하지 않았으며,
  git commit을 하지 않았다. 산출물은 이 MD와 동일 내용의 HTML 두 파일뿐이다.
- 목적: 현재 마련된 문헌관리 체계(수업 준비 기간이므로 **문헌을 더 확장하지
  않는다는 전제**)만으로, 일곱 현상 파일럿의 공통 시작 체계 중 무엇을 지금
  안전하게 구현할 수 있고 무엇을 보류해야 하는지 판단한다.
- 검토 전 사전 보완: 사용자 승인 하에 문헌 CURRENT_STATE의 DECISION_LOG 행수
  표기 drift(구 "23행")를 정정하고 LD-026으로 기록했다(검토 시작 후에는 문헌
  워크스페이스를 수정하지 않았다).

## 0. 실측 근거 (2026-08-23, 저장소에서 직접 측정)

읽은 문서: CLAUDE.md · PROJECT_START_HERE.md · PROJECT_CURRENT_STATE.md ·
PLAN_stage2_seven_phenomena_PV_pilot_20260819.md ·
REQUIREMENT_stage2_manual_textgrid_and_phenomenon_release_20260822.md ·
PLAN_stage2_target_query_and_realization_design_20260818.md · 문헌관리
README/CURRENT_STATE/SCHEMA/AUDIT_L0.json · 현상별 MD 7종 ·
phenomena/34_n_insertion/definition.md · pv_preview_boundary_20260819.json ·
build_pv_preview_samples.py · build_pv_reviewer_v2_1.py (전문 15종).

| 파일 (저장소 루트 기준) | 행 | bytes | SHA-256 (앞 16) |
|---|---:|---:|---|
| work/…/01_inventory/SOURCE_INVENTORY.jsonl | 359 | 341,949 | ff27954af639e51e |
| work/…/02_claims/CLAIM_EVIDENCE.jsonl | 26 | 50,689 | dbc219e934104702 |
| work/…/00_admin/DECISION_LOG.jsonl | 26 | 25,229 | f2c87b0450557c19 |
| work/…/01_inventory/SOURCE_RELATIONS.jsonl | 41 | 17,693 | 74ebd3f8b670bdcd |
| work/…/01_inventory/SEMINAR_SOURCE_LINKS.jsonl | 193 | 106,888 | c6553e8cf3d3d2b9 |
| work/…/01_inventory/MISSING_ORIGINALS_WANTED.jsonl | 81 | 66,103 | 38279b8f2fc3d515 |
| work/…/00_admin/CURRENT_STATE.md | — | 11,189 | 80c2452026efea23 |
| work/…/audit/AUDIT_L0.json | — | 10,273 | 885deb9b490b004b |
| phenomena/34_n_insertion/definition.md | — | 4,203 | aa23b940d1e556df |
| config/target_queries/pv_preview_boundary_20260819.json | — | 17,505 | 68d0b8cc0bc97019 |
| scripts/python/build_pv_preview_samples.py | — | 40,900 | e92f61024b490a4b |
| scripts/python/build_pv_reviewer_v2_1.py | — | 23,078 | 545e15b36433b980 |

독립 재확인 결과(스펙 제시 기준과의 대조):

- SOURCE_INVENTORY 359행 — **일치**.
- CLAIM_EVIDENCE 26행, 전부 `reference_evidence.v2`, NI 4편(SRC-297 오미라
  2006 10건 · SRC-287 안미진 2008 6건 · SRC-293 이세창 2016 5건 · SRC-294
  이세창 2024 5건) — **일치**.
- 현상별 A_direct: PT 23 · NAN 13 · NAL 14 · NI 32 · LLN 16 · VH 15 ·
  HIA 6 — **일치**.
- PHENOMENON_ENVIRONMENT_MAP.jsonl / RESEARCH_DECISION_LINKS.jsonl —
  **부재 확인**(폴더만 존재; SCHEMA에 "착수 시 정의" 계약).
- phenomena/ 아래 정식 definition.md — **NI(34_n_insertion)만 존재 확인**.
- DECISION_LOG drift — 사용자 지적 시점 실제 25행 대 표기 23행이었고, 검토
  직전 LD-026 정정을 추가해 **실제 26행 = CURRENT_STATE 표기 26행**으로 해소.
- 문헌 3원 배치: 저장소 정본과 Dropbox 미러(2026_00_research_morpho_phonology)
  동일 상대 구조 동기화 상태(금일 커밋 이력 기준).

## A. 현재 상태에서 구현 가능한 공통 시작 체계

원칙: 아래 8개는 모두 **구조(스키마·상태·경로 계약)를 지금 확정**할 수 있다.
"값"(현상별 확정 조건·분류값)은 NI만 문헌 근거가 있고 나머지는 placeholder로
시작한다. 모든 항목은 기존 1단계 원칙(exact-ID·fail-closed·append-only·독립
감사·연구자 Gate)을 그대로 계승하며, 이미 검증된 선례 구현이 저장소에 있다.

### A1. 현상 definition 템플릿 — 구현 가능

`phenomena/34_n_insertion/definition.md`의 절 구조가 사실상 검증된 템플릿이다:
①현상(수의성 명시) ②환경 조작화(B2 검색 조건) ③실현 판정 증거표(증거원별
"최종 실현값인가" 열 — MFA phone 배제 원칙) ④변수(B4) ⑤산출 목표.
여기에 문헌관리 체계와의 연결 두 절을 추가할 것을 권고한다:

- `문헌 근거` 절: 착수스캐폴드 경로 + 관련 CLM ID 목록(예: NI는 CLM-0001~0026)
- `근거 상태` 절: definition_status ∈ {draft_template, literature_seeded,
  researcher_confirmed} — 6현상은 `draft_template`로 생성 가능.

입력 계약: 템플릿 값의 시드는
`work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/`
의 착수스캐폴드 7종(SHA는 §0)에서 가져온다. **정독 확장 없이** 스캐폴드의
문헌 목록·세미나 연결만 옮기는 것이 안전 범위다.

### A2. phenomenon registry — 구현 가능

단일 선언형 JSON(`config/phenomena_registry.v1.json` 제안). 행 계약:

```text
phenomenon_code(PT|NAN|NAL|NI|LLN|VH|HIA), label_ko,
official_slug(예: 34_n_insertion — NI 외에는 "" + slug_status=pending_f0),
definition_path, definition_status,
literature_scaffold_path, literature_evidence_level(L1_pilot|scaffold_only),
a_direct_count(실측 자동 기입), query_status(frozen|draft_pv_only|none),
frozen_query_sha256(NI만: 744bd8cb…), gate_position, notes
```

근거: PV config가 이미 `phenomenon_order`·`PHENOMENON_LABELS`로 사실상의
registry를 코드 안에 갖고 있다. 이를 선언형 파일로 꺼내면 이후 모든 Gate가
같은 registry를 참조한다. 현상 번호(34_… 식) 공식 부여는 F0 대기이므로
`slug_status=pending_f0` placeholder가 정확한 표현이다.

### A3. 일반적/주변적/탐색적/불명 환경 분류 — 구조 구현 가능, 값은 부분

PROJECT_CURRENT_STATE의 "다음 한 단계"가 요구하는 4단 분류를 enum과 저장
구조로 확정한다:

```text
environment_class ∈ {general_direct, peripheral_reported,
                     theoretical_underreported, unclear_boundary}
+ class_evidence_refs(CLM/SRC/WANT ID 배열), class_status(seeded|pending),
  classified_by, classified_at   — append-only, occurrence가 아니라
  '환경 유형'(query 조건 조합) 단위로 부여
```

값 배정 가능 범위(문헌 확장 없이): **NI만 문헌 시드 가능** — 오미라 2006의
환경표(CLM-0005)와 김선철 재분석(CLM-0006)이 general(/y/ 고유어 복합·파생),
peripheral(/i/ 환경·한자어 공명음+y·혼종어 순서), underreported(보조사 '요',
외래어, 2음절 한자어 수의 재음절화)를 직접 지지한다. 나머지 6현상은 전부
`pending`으로 시작하고, 이는 결함이 아니라 회계다(D5 참조).

### A4. 현상별 inclusion/exclusion/confound 계약 — 구조 구현 가능

현상당 선언형 JSON 한 장:

```text
include_conditions(PV config draft 조건 재사용·SHA 참조),
exclude_conditions(+exclusion_reason, evidence_refs),
confound_phenomena: [{code, relation, discriminator, evidence_refs}],
membership_rules(VH/HIA 공유 멤버십처럼 이미 구현된 규칙의 선언화),
contract_status(draft|frozen)
```

confound 시드는 문헌에서 이미 나와 있다: NI↔PT(사잇소리·경음화가 합성 경계
실현으로 상보/동시 — CLM-0023), NI↔구개음화 경합(밭요 [바쵸]~[반뇨] —
CLM-0009), NI↔ㄴ탈락 전도 논쟁(CLM-0008), NAN·NAL↔LLN 인접, VH↔HIA 물리
중복(build_pv_preview_samples.py의 `infer_memberships`가 이미 구현). PT의
격음화 환경(ㅎ·ㄶ·ㅀ) 제외는 PV 계획의 "관찰 후 확정" 상태를 그대로
`draft` 표시로 보존한다.

### A5. 후보·표본 zero-drop 상태 모델 — 구현 가능

이미 흩어져 검증된 상태 어휘를 하나의 상태 사전으로 선언한다(신규 발명 없음):

- 후보층: `candidate_ready_for_manual_realization_review`,
  `candidate_metadata_only_missing_capped_release_lookup`(builder 실측),
  `not_selected_quota_or_duplicate`, `selected_primary`,
  `selected_shared_membership`
- 시간층: `linked_*`, `pending_textgrid_asset_unavailable`,
  `pending_textgrid_word_mapping_review`
- 후속층(REQUIREMENT R1·R2): `not_needed | required | unsure |
  unavailable | blocked`
- 회계 불변식: **모든 입력 후보는 어느 시점에도 정확히 하나의 상태를 가지며
  삭제되지 않는다.** 감사기는 `입력 = Σ상태별`을 재계산한다.

### A6. 추가 정보 요청 sidecar — 구현 가능

REQUIREMENT R4의 스키마를 그대로 append-only JSONL로 채택한다
(`request_id, phenomenon_id, occurrence_id, information_key,
requested_reason, value_status(pending|unavailable|not_applicable|filled),
value_text_or_ref, evidence_source, evidence_sha256, reviewer, recorded_at,
supersedes`). `information_key`는 자유 문자열로 시작하되
`공통사전 vs 현상별 namespace`(REQUIREMENT §3-4)는 **결정하지 않고**
`key_namespace=unregistered`로 보존한다 — 반복·실사용 항목만 코드북 검토 뒤
정식 열로 승격한다는 R4 원칙이 이미 이 유예를 허용한다.

### A7. 수동 TextGrid 후속 queue + 원본 불변 overlay — 구현 가능

선례가 완결적이다: D9→D10의 exact-ID 격리 materialize·4-tier 작업본·raw/
normalized 동결·adoption Gate 패턴(PROJECT_CURRENT_STATE 실측 이력)을
현상 workflow의 일반 기제로 선언하면 된다. queue 행 계약은 REQUIREMENT R3의
provenance 필드(task_id … supersedes)를 그대로 쓴다. 핵심 사용성 요구
2건은 Gate 2·3 합격 기준으로 아래 §E에 반영했다: `required/unsure` 선택 시
같은 화면 read-only TextGrid 패널 자동 펼침, 필요한 사례만 exact-ID queue
송출. reviewer v2.1 builder가 이미 원본 HTML 무수정·단일 치환 검증·마커
검사 방식을 확립했으므로, 패널 추가도 같은 파생 빌더 패턴으로 가능하다.

### A8. 현상별 공개 파생본 provenance — 구현 가능(스켈레톤)

REQUIREMENT R5의 재생성 계약을 빌더 스켈레톤으로 구현할 수 있다: 입력 =
승인 ledger + overlay provenance + 정보 코드북 + audit manifest(전부 SHA
결속), 출력 = 현상별 공개 파생본 + 재생성 manifest. **localStorage·임시
HTML은 입력 계약에서 명시적으로 배제**한다(§E Gate 4 합격 기준). 원문 음성·
전사 배포 범위는 이용조건 확인 전이므로 기본값을 "비식별 파생값 + exact-ID
재현 절차만"으로 두는 것을 권고한다(D4).

## B. 아직 구현하면 안 되는 것 (근거 포함)

1. **근거가 부족한 현상별 query 확정값** — L1 원문 근거는 NI 4편·26주장뿐이다
   (실측 §0). PT의 좌측 종성 집합·격음화 제외, NAN의 ㅁ 앞 포함, VH/HIA의
   표면형/표제어·범주 목록·방언형(질문 4·5·6)은 전부 "PV 관찰로 확정" 상태로
   문서에 고정되어 있다. draft PV 조건을 동결값으로 승격하는 코드는 금지.
   NI의 동결 query(SHA 744bd8cb…)만 예외적으로 확정값이 존재하나, 아래
   문헌 발견(§C-NI의 '요' 환경) 때문에 **재동결 없이 유지 + 별도 탐색 query
   후보로만 기록**해야 한다.
2. **연구 우선순위의 자동 확정** — PLAN 2026-08-22 후속 결정이 "1차 묶음·
   재검토·1–5 확신도는 근거 정리 뒤 별도 설계 Gate에서 확정"으로 명시. 4단
   분류(A3)의 `pending`을 코드가 기본값으로 채워서는 안 된다.
3. **자동 실현 판정** — CLAUDE.md·definition.md·PV config safety까지 전 층에
   동일 원칙. MFA/G2P/w2v phone은 어떤 파생 계산에서도 decision 열에 못 들어간다.
4. **원자료·6-tier TextGrid 수정** — D:\00_RAW·r3 DB·동결 6-tier·동반표는
   읽기 전용. 수동 작업은 exact-ID 격리 사본·overlay만(A7), adoption은 별도 Gate.
5. **정식 ledger 자동 쓰기** — G7 ledger는 연구자 전용 append-only. reviewer의
   JSONL 내보내기·localStorage는 탐색 기록이며 ledger로 자동 승격하는 경로를
   만들지 않는다(수동 가져오기 + 검토 + 승인 Gate만 허용).

## C. 현상별 최소 착수 카드

표기: 근거 수준 ① = L1 원문 근거(주장 단위, CLM 참조 가능) / ② = 착수스캐폴드
+세미나 연결(문헌 목록 수준, 원문 미정독) / ③ = draft query 조건만.
"판정"은 (a) 코드로 확정 가능 / (b) placeholder만 가능 / (c) 사용자 결정 필요.

### C-PT 경음화 (A_direct 23 · 수배 41 · 근거 ②)

| # | 항목 | 내용 |
|---|---|---|
| 1 | 정의 초안 | 장애음 종성 뒤 평장애음(ㄱㄷㅂㅅㅈ)의 경음 실현. 합성 경계 유형·어휘화가 실현율을 좌우하는 수의층 포함 |
| 2 | 포함 환경 | PV draft: 좌 종성 {ㄱㄲㅋㄳㄺㄷㅅㅆㅈㅊㅌㅂㅍㅄㄼㄿ} + 우 onset {ㄱㄷㅂㅅㅈ}, scope 3종(morph_internal/intra/inter) |
| 3 | 제외 환경 | ㅎ·ㄶ·ㅀ 종성(격음화 환경 — "관찰 후 확정" 유지). J*/E* 처리 미정 |
| 4 | 혼동 요인 | 격음화; 사잇소리 t(V©C 환경 — PT 후보의 좌측 조건 밖이지만 개념상 인접, 이세창 2024는 동일 경계 실현로 통합 · CLM-0023); NI 동시 실현(깻잎형); 어휘화 대조(잠자리) |
| 5 | 일반적 직접 보고 | 장애음 뒤 의무 경음화(내부·어절 내부) — 사잇소리 폴더 34건이 배후 문헌층 |
| 6 | 주변적 보고 | 공명음 말음 합성 경음화(산새류, 수의); 한자어 내부(율격류) |
| 7 | 저보고 탐색 | 어절 간(inter) 경음화; 두 경음 연쇄의 차단 여부(Moon et al. 2024 로컬 보유); 빈도·어휘화에 따른 경계 지각 변이(CLM-0022 예측) |
| 8 | 파일럿 질문 | 의무층과 수의층을 한 모집단으로 둘지; 격음화 제외 확정; V©C(사잇소리) 환경을 PT와 교차 집계할 설계 |
| 9 | 근거 수준 | ② + 이세창 2024 경유 L1 교차 근거(CLM-0022·0023) |
| 10 | 판정 | 상태·enum (a) / query 값 (b) / 모집단 경계·격음화 제외 (c) |

### C-NAN ㄴ 앞 비음화 (A_direct 13 · 수배 0 · 근거 ②)

| # | 항목 | 내용 |
|---|---|---|
| 1 | 정의 초안 | 장애음 종성 + ㄴ 시작 연쇄에서 종성의 비음 실현(밥+니→[밤니]류). 규범상 의무 |
| 2 | 포함 환경 | PV draft: 좌 장애음 집합 + 우 onset ㄴ, scope 3종 |
| 3 | 제외 환경 | 미정 — ㅁ(·ㅇ) 앞 포함 여부는 PV 관찰 메모로 이관된 상태 유지 |
| 4 | 혼동 요인 | NI 연쇄(삽입된 n 앞 비음화 — 색연필형은 NI 소산); NAL·LLN 인접; 음성적 부분 비음화 |
| 5 | 일반적 직접 보고 | 의무 비음화(교과서적 — 형태소 내부·어절 내부) |
| 6 | 주변적 보고 | 어절 간 적용률 |
| 7 | 저보고 탐색 | 의무 현상 내부의 음성 구배(완전/부분 비음화) — 대화 음성에서 측정 가치 |
| 8 | 파일럿 질문 | ㅁ 앞 포함 여부; '의무 현상에서 무엇을 변이로 기록할지'의 코딩 단위 |
| 9 | 근거 수준 | ② |
| 10 | 판정 | 상태·enum (a) / query 값 (b) / ㅁ 앞 범위 (c) |

### C-NAL ㄹ 앞 비음화 (A_direct 14 · 수배 0 · 근거 ②)

| # | 항목 | 내용 |
|---|---|---|
| 1 | 정의 초안 | 장애음 종성 + ㄹ 시작 연쇄에서 ㄹ의 [n] 실현(+선행 비음화 연쇄; 격려·법률류) |
| 2 | 포함 환경 | PV draft: 좌 장애음 집합 + 우 onset ㄹ, scope 3종 |
| 3 | 제외 환경 | 미정 |
| 4 | 혼동 요인 | LLN(ㄴㄹ 연쇄의 유음화 경쟁 — 좌측이 비음이면 LLN, 장애음이면 NAL로 분리됨을 계약에 명시); 외래어 ㄹ 처리 |
| 5 | 일반적 직접 보고 | 한자어 단일어 내부(격려류 — PV 계획이 내부형 핵심으로 명시) |
| 6 | 주변적 보고 | 어절 간(할당 4로 최소) |
| 7 | 저보고 탐색 | 구 경계·외래어 환경; [ll] 대 [nn] 선택의 어휘·세대 변이 |
| 8 | 파일럿 질문 | NAL과 LLN의 후보 중복 처리 규칙(membership으로 둘지 분리로 둘지) |
| 9 | 근거 수준 | ② |
| 10 | 판정 | 상태·enum (a) / query 값 (b) / NAL·LLN 경계 규칙 (c) |

### C-NI ㄴ삽입 (A_direct 32 · 동결 query 있음 · 근거 ① — reference implementation)

| # | 항목 | 내용 |
|---|---|---|
| 1 | 정의 초안 | 자음 종성 형태소 + /i, j/ 시작 형태소 경계의 수의적 [n] 삽입(definition.md B1 개정안). 실현율은 경계·빈도·어종·화자에 민감 |
| 2 | 포함 환경 | 어절 내부/간 2모집단(동결 query SHA 744bd8cb…, G1–G4 완료 94만 행) |
| 3 | 제외 환경 | J*/E* 후행(연음 환경), 숫자·기호 인접, 1음절 미만 |
| 4 | 혼동 요인 | 사잇소리·경음화(합성 경계 상보/동시 — CLM-0023); 구개음화 경합(밭요 — CLM-0009); ㄴ탈락 전도 논쟁(CLM-0008); 재음절화 수의성(2음절 한자어, 속도 의존 — CLM-0015) |
| 5 | 일반적 직접 보고 | /y/ 시작 고유어 복합·파생(선호 70%↑ 전부 /y/ — CLM-0006); 한자어 공명음 말음+y(금융류 — CLM-0004) |
| 6 | 주변적 보고 | /i/ 시작(≈48%); 혼종어 결합 순서 효과(안국역/한국인 — CLM-0005); 장애음 말음 2음절 한자어 비삽입(CLM-0015) |
| 7 | 저보고 탐색 | **보조사 '요' 앞 삽입(밥요[밤뇨] — CLM-0002)**: 문어 연구 부족, 일상대화 코퍼스가 최적 검증 자료. 외래어(붕뉴럽), L2 전이 제외 |
| 8 | 파일럿 질문 | ⚠ **현행 동결 query의 J*/E* 전면 제외가 보조사 '요' 환경(JX)을 모집단에서 배제한다 — 오미라 2006의 직접 반례 보고와 상충.** 동결 query는 유지하되 '요' 환경 별도 탐색 query를 추가할지 사용자 결정 필요(D1). /i/·/y/ 분리 집계 변수 확정 |
| 9 | 근거 수준 | ① (CLM-0001~0026, 4편 전문 정독) |
| 10 | 판정 | 기존 동결 query (a—이미 확정) / 4단 분류 시드 (a) / '요' 탐색 query·B1 잔여 범위 (c) |

### C-LLN ㄴㄹ·ㄹㄴ 연쇄 (A_direct 16 · 수배 4 · 근거 ② · D2 학기 2순위)

| # | 항목 | 내용 |
|---|---|---|
| 1 | 정의 초안 | ㄴ+ㄹ/ㄹ+ㄴ 연쇄에서 유음화([ll])와 비음화([nn])의 방향 경쟁·변이 |
| 2 | 포함 환경 | PV draft 4 query: (ㄴ,ㄹ)·(ㄹ,ㄴ) × intra/inter |
| 3 | 제외 환경 | 미정 |
| 4 | 혼동 요인 | NAL(좌측이 장애음인 경우와 분리); NI 소산 연쇄(삽입 후 ㄴㄹ 생성); 한자어 형태 구조(2+1 vs 1+2) 효과 |
| 5 | 일반적 직접 보고 | 형태소 내부 유음화(신라류 — PV 계획: 내부 ㄴㄹ 6·ㄹㄴ 2) |
| 6 | 주변적 보고 | ㄹㄴ 연쇄(설날류); 파생 접미 경계 |
| 7 | 저보고 탐색 | 어절 간 연쇄; [ll]~[nn] 어휘별 변이(의견란류) — SRC-059 Lee 2018(서지 확정, 9강 인용 SEM-144 verified)이 직접 이론 문헌 |
| 8 | 파일럿 질문 | 방향 선택(유음화/비음화)의 코딩 체계; NAL과의 모집단 분리 확정 |
| 9 | 근거 수준 | ② (+SRC-059 서지 L1급 확정) |
| 10 | 판정 | 상태·enum (a) / query 값 (b) / 방향 코딩·모집단 경계 (c) |

### C-VH 모음조화 (A_direct 15 · 수배 4 · 근거 ②)

| # | 항목 | 내용 |
|---|---|---|
| 1 | 정의 초안 | 용언 어간 + 아/어 계열 어미 선택의 조화·비조화 실현 |
| 2 | 포함 환경 | PV draft: intra, 좌 pos ^V + 우 pos ^E + onset zero + 핵모음 {ㅏ,ㅓ}; 축약 probe(봐/줬…) 별도 |
| 3 | 제외 환경 | 미정 — 표면형/표제어형 기준 자체가 질문 4로 이관된 상태 |
| 4 | 혼동 요인 | HIA(같은 모집단의 부분집합 — 공유 멤버십 구현 존재); 축약·활음화; ㅂ불규칙(고와/고워) |
| 5 | 일반적 직접 보고 | 규범적 조화(잡아/먹어) |
| 6 | 주변적 보고 | 불규칙 어간·세대 변이(고와~고워) |
| 7 | 저보고 탐색 | 구어 비조화형(잡어라류) — 일상대화 코퍼스 최적; Bareun 축약 분절 실측(P0 겸용 probe) |
| 8 | 파일럿 질문 | 질문 4·5·6(표면형/표제어형·범주 목록·방언형) — PV 관찰 항목 유지 |
| 9 | 근거 수준 | ② |
| 10 | 판정 | 상태·enum (a) / query 값 (b) / 질문 4·5·6 (c — 단 파일럿 전 확정 불요, PV 관찰로 유예 가능) |

### C-HIA 모음충돌 회피 (A_direct 6 · 수배 6 · 근거 ② — 문헌 최약)

| # | 항목 | 내용 |
|---|---|---|
| 1 | 정의 초안 | V+V 연쇄(빈 종성 어간 + 모음 어미)에서 활음화·축약·탈락에 의한 충돌 회피 |
| 2 | 포함 환경 | PV draft: VH 조건 + 좌 종성 빈 값; 축약 probe 공유 |
| 3 | 제외 환경 | 미정 |
| 4 | 혼동 요인 | VH(모집단 포함 관계 — HIA ⊂ VH 멤버십 규칙 기구현); 표기 축약(봐/보아 표기 대 발음) |
| 5 | 일반적 직접 보고 | 고빈도 축약(봐·줘·해·돼) |
| 6 | 주변적 보고 | 비축약 유지형(보아라류) |
| 7 | 저보고 탐색 | 축약률의 속도·세대·사용역 변이; 활음화 대 탈락의 선택 |
| 8 | 파일럿 질문 | 활음화·탈락·축약 범주 목록(질문 5); 표면형 판정 단위(질문 4) |
| 9 | 근거 수준 | ② — **로컬 6건으로 7현상 중 최소. 단 착수 시 수배 6건 우선 입수 권고(문헌 확장이 아니라 기확인 수배 목록의 입수)** |
| 10 | 판정 | 상태·enum (a) / query 값 (b) / 범주 목록 (c — PV 관찰 유예 가능) |

## D. 파일럿 전 사용자 결정 (최대 5개 — 이 외에는 질문하지 않고 pending 보존)

| ID | 결정 | 왜 지금인가 | 미결 시 |
|---|---|---|---|
| D1 | **NI B1 잔여 범위 확정 + '요' 환경 처리**: 어절 내부/간 모집단·J*/E*·기호 제외·의미번호 보존은 개정안대로 확정하는가. 보조사 '요' 환경(CLM-0002 근거)을 별도 탐색 query 후보로 등록하는가(동결 query 재동결 아님) | PROJECT_START_HERE의 "B1 개정안 검토 Gate"가 명시적 대기 중이며, reference implementation(NI) 착수의 유일한 실질 차단물 | Gate 1 정지 |
| D2 | **reference implementation 순서 승인**: NI로 공통 체계(A1–A8)를 검증한 뒤 LLN → 나머지로 확대(기존 D2 결정과 정합) | Gate 순서(§E) 전체의 전제 | Gate 0만 진행 가능 |
| D3 | **TextGrid 후속 초기 방식**: REQUIREMENT §3 초기 권고(HTML read-only 패널 + 필요 사례만 격리 작업본 Praat 내보내기/가져오기; in-browser 편집은 반복 수요 확인 뒤 별도 파일럿) 채택 여부 | Gate 2·3의 합격 기준과 구현 범위를 가름 | Gate 2 설계 정지 |
| D4 | **공개 파생본 기본값**: 이용조건 확인 전까지 "비식별 파생값 + exact-ID 재현 절차만"을 공개 빌더의 기본 계약으로 채택 | A8 스켈레톤의 출력 계약 확정에 필요(원문 포함 여부는 이후 별도 확인) | Gate 4 스켈레톤은 가능하나 출력 계약 미동결 |
| D5 | **문헌 확장 없는 착수 승인**: 4단 환경 분류·definition을 NI만 문헌 시드로 채우고 나머지 6현상은 전원 placeholder/pending으로 시작함을 승인(수업 준비 기간 전제의 공식화) | A1–A4의 생성 범위를 확정 | 6현상 스캐폴드형 생성 보류 |
| — | 질문하지 않는 것(pending 보존): 현상 번호·slug(F0), NAN ㅁ 앞, PT 격음화 제외, VH/HIA 질문 4·5·6, sidecar key namespace, 문맥 창 ±2 적정성, 대형 현상 저장 정책, 보조층 열 채택(PV-B), NI 600건 층화 세부 | 전부 "PV 관찰로 확정" 또는 "코드북 검토 뒤 승격" 계약이 이미 존재 | — |

## E. 단계별 구현 권고 — NI reference implementation Gate 순서

공통 정지선(모든 Gate): 원자료·r3 DB·동결 6-tier·동반표·문헌 워크스페이스
수정 0 · MFA/KOINA/w2v 실행 0 · 자동 실현 판정 0 · 정식 ledger 자동 쓰기 0 ·
기존 출력 비덮어쓰기·`.partial` 원자 승격·독립 감사 없이는 다음 Gate 없음.

### Gate 0 — 공통 스키마·registry 동결 (구현: A1 템플릿, A2 registry, A3 enum, A4 계약 틀, A5 상태 사전, A6 sidecar 스키마)

- 입력: 착수스캐폴드 7종 + definition.md(NI) + PV config(SHA §0) + 본 보고서 D1~D5 답
- 출력: `config/phenomena_registry.v1.json`, 현상별 definition 스켈레톤 7종
  (NI=literature_seeded, 나머지=draft_template), 상태 사전·enum 선언, 스키마 문서
- 합격: registry 7행 완결(placeholder 명시), 선언 파일 SHA manifest, 독립
  검사기(파서 왕복·필수 필드) 통과, 기존 파일 수정 0
- 정지선: 어떤 query 값도 동결하지 않음. D5 미승인 시 6현상 스켈레톤 생성 보류

### Gate 1 — NI 착수 카드 → 후보 연결 (기존 동결 자산 재사용)

- 입력: D1 답, 동결 query(SHA 744bd8cb…)·G1–G4 후보 94만 행(읽기 전용),
  4단 분류 NI 시드(CLM 참조)
- 출력: NI inclusion/exclusion/confound 계약 v1(frozen), 환경 유형별 4단
  분류표(+CLM evidence_refs), '요' 환경 탐색 query **후보 문서**(동결 아님)
- 합격: 계약이 동결 query 조건과 모순 0(자동 대조), 분류표 전 행에
  evidence_refs 또는 pending 명시, zero-drop 회계 재계산 통과
- 정지선: G5/G6(문맥 연결·bundle) 대량 실행은 기존 PLAN의 별도 GO 필요

### Gate 2 — 후속 필요성 reviewer (사용성 필수 4건 중 ①②)

- 입력: PV-A 표본(기존 180 packages 재사용) 또는 NI 층화 표본(D1 이후),
  reviewer v2.1 파생 빌더 패턴
- 출력: reviewer v3 파생본 — `textgrid_review_need(not_needed|required|unsure)`
  + 이유 복수 선택 + `additional_information_requests` + 1–5 확신도 입력,
  **required/unsure 선택 즉시 같은 후보의 read-only TextGrid 패널 자동
  펼침**(대상 span·파형/재생 위치·6-tier read-only·근거·SHA·작업본 상태·
  `unavailable` 명시), **exact-ID 수동 작업 queue 내보내기(필요 사례만)**
- 합격(REQUIREMENT §4 전문 승계): 패널 자동 펼침 동작, 미저장 경고 유지,
  저장·재가져오기 후 동일 occurrence 복원, TextGrid 부재 후보
  `unavailable` 보존, `not_needed+required+unsure+unavailable/blocked =
  입력 전체` zero-drop, 원본 변경 0, 자동 판정·ledger 쓰기 0
- 정지선: 패널은 read-only. '필요' 표시가 어떤 자동 수정도 촉발하지 않음

### Gate 3 — 수동 overlay + 가변 sidecar 왕복 (사용성 ③)

- 입력: Gate 2 queue(exact-ID), D3 답(Praat 왕복 방식)
- 출력: D10 패턴의 격리 작업본 묶음(R3 provenance 필드 완비), **append-only
  sidecar JSONL**(A6 스키마 — 현상마다 다른 추가 정보 기록), 반입 시
  raw/normalized 동결 + diff patch
- 합격: 작업본이 원본 SHA·exact-ID에 결속, 원본 파일 변경 0, sidecar 행
  supersedes 사슬 무결, 미확인 값 pending/unavailable 보존(빈값 은폐 0)
- 정지선: adoption(정식 반영)은 별도 감사 + 연구자 승인 Gate

### Gate 4 — 승인 ledger + 공개 파생본 재생성 (사용성 ④)

- 입력: 연구자 판정(G7 ledger, append-only 수동 기록), Gate 3 overlay
  provenance, 정보 코드북, audit manifest, D4 답
- 출력: 현상별 공개 파생본 빌더 — **localStorage·임시 HTML을 입력으로
  받지 않고** ledger+manifest에서만 재생성, 재생성 자체가 결정적(같은 입력
  → 같은 SHA)
- 합격: 재생성 결정성 검증(2회 빌드 SHA 동일), 공개본에 비허용 자산 0
  (기본값 D4), 표본 선택·제외·zero-drop 회계 포함, 독립 감사 JSON `passed`
- 정지선: 배포 범위 확대는 이용조건·윤리 확인 뒤 별도 결정

### Gate 5 — 타 현상 연결 (LLN부터)

- 입력: NI에서 검증된 A1–A8 전 기제, LLN 착수 카드(C-LLN)의 (c) 항목 답
- 출력: LLN definition literature_seeded 승격(그때의 문헌 착수와 병행),
  이후 현상별 반복
- 합격: NI와 동일 감사 통과 + "현상 특이 사항이 sidecar·계약으로 수용됨"
  확인(공통 체계 수정이 필요했다면 그 수정을 registry 버전으로 기록)
- 정지선: 한 번에 한 현상. 대형 현상(PT)의 저장 정책은 착수 전 별도 결정

## F. 검토 중 발견한 문헌 체계 보완 후보 (수정하지 않고 기록 — 사용자 승인 후 2차 보완)

1. `phenomena/34_n_insertion/definition.md`가 문헌관리 정본(CLM ID)을 아직
   참조하지 않는다 — B1 확정 개정 시 `문헌 근거` 절(A1 권고)로 CLM-0001~0026을
   연결하면 정의와 근거가 SHA로 이어진다.
2. NI 동결 query의 J*/E* 전면 제외 대 오미라 2006의 보조사 '요' 반례(CLM-0002)
   — 문헌 쪽에는 이미 기록되어 있으므로 설계 쪽 결정(D1)만 남았다.
3. 착수스캐폴드의 세미나 연결은 리딩 주차 기반 예비값이다(문서에 명시됨) —
   L1 착수 시 개별 확정한다는 기존 계약으로 충분하며 추가 조치 불요.
4. 문헌 CURRENT_STATE 행수 drift는 LD-026으로 정정 완료(재발 방지: 행수를
   산문에 적을 때 audit 재생성 스크립트가 같이 갱신하는 관행 권고).

## G. 부록 — 구현 도구 인계 프롬프트 초안 (사용자가 승인 후 사용)

```text
C:\Users\ari30\research\2026_summer_research 저장소에서 작업한다. 먼저
docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md
를 읽고, 그 §E Gate 0만 구현한다(사용자 결정 D1~D5의 답: [여기 기입]).
문헌 근거는 work/literature_evidence_seven_phenomena_20260822/의 정본
JSONL과 03_phenomenon_synthesis/ 스캐폴드를 읽기 전용으로 참조하고,
자료는 SRC-###/CLM-#### ID와 저장소 상대경로로만 인용한다(규약:
00_admin/문헌자료_참조가이드_20260823.md). 금지: 원자료·6-tier·문헌
워크스페이스 수정, query 값 동결, 자동 실현 판정, MFA/KOINA/wav2vec2 실행,
정식 ledger 쓰기. 신규 출력은 선언 파일과 스켈레톤 문서만이며 기존 출력을
덮어쓰지 않는다. 구현 후 독립 검사기와 SHA manifest를 제출하고 정지한다.
```

## 결론

현재 문헌관리 체계(L0 완결 + NI L1 파일럿 26주장 + 7현상 스캐폴드)는 **공통
시작 체계 8종의 구조를 전부 동결하기에 충분**하고, **현상별 확정값은 NI에만
충분**하다. 따라서 "NI reference implementation으로 Gate 0–4를 검증하고
Gate 5에서 현상을 하나씩 붙이는" §E 순서가 문헌을 확장하지 않는 현 전제와
정확히 정합한다. 사용자 결정은 D1~D5 다섯 개로 압축되며, 나머지는 전부
pending 상태로 보존 가능하다. 본 보고서 작성 후 어떤 구현도 시작하지 않았다.
