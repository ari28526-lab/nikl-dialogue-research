# 구현 도구 인계 프롬프트 — Gate 0 (2026-08-23 확정본)

근거: `docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md` §G 초안
+ `docs/decisions/DECISION_stage2_seven_phenomena_workflow_user_decisions_20260823.md` (D1~D5)
+ 문헌 L1 확장 완결(LD-027)·운율 경계 문헌 반입(LD-028) 반영.

사용법: 아래 코드 블록 전체를 구현 도구(예: Claude Code)에 첫 메시지로 붙여넣는다.
Gate 0가 끝나고 정지하면 산출물을 검토한 뒤, Gate 1은 별도 프롬프트로 넘긴다(한 번에 한 Gate).

```text
C:\Users\ari30\research\2026_summer_research 저장소에서 작업한다.

[1. 먼저 읽을 것 — 순서대로, 모두 읽기 전 구현 금지]
1) docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md
   (특히 §A 구현 항목, §B 금지 목록, §E Gate 0)
2) docs/decisions/DECISION_stage2_seven_phenomena_workflow_user_decisions_20260823.md
3) work/literature_evidence_seven_phenomena_20260822/00_admin/문헌자료_참조가이드_20260823.md
   (문헌 자료의 경로·ID 인용 규약)
4) work/literature_evidence_seven_phenomena_20260822/00_admin/CURRENT_STATE.md
   (문헌 쪽 최신 상태 — 2026-08-23 L1 확장 완료 기준)

[2. 이번 작업 범위]
검토 보고서 §E의 **Gate 0만** 구현한다: 공통 스키마·registry 동결
(A1 definition 템플릿, A2 phenomena registry, A3 enum·상태 사전,
A4 inclusion/exclusion/confound 계약 틀, A5 zero-drop 상태 사전,
A6 append-only sidecar 스키마). Gate 1 이후는 착수하지 않는다.

[3. 사용자 결정 D1~D5 — 확정 답]
- D1: NI B1 잔여 범위는 개정안대로 확정(어절 내부/간 2모집단, J*/E*·숫자·
  기호 제외, 의미번호 불확실성 보존). 동결 query(SHA 744bd8cb…)는 재동결
  없이 유지. 보조사 '요' 앞 ㄴ삽입(문헌 근거 CLM-0002)은 **별도 탐색 query
  후보로 등록**하되 본모집단과 분리 회계한다(등록만, 동결 아님).
- D2: 승인 — NI reference implementation으로 공통 체계(A1~A8) 검증 후
  LLN → 나머지 현상 순으로 확대.
- D3: TextGrid 후속 초기 방식은 read-only 패널 + Praat 왕복
  (HTML은 read-only TextGrid 패널 즉시 확인만; 수정 필요 사례만 exact-ID
  격리 작업본으로 내보내기/가져오기; in-browser 경계 편집은 별도 파일럿).
- D4: 공개 파생본 기본 출력 계약은 "비식별 파생값 + exact-ID 재현 절차만".
  원문 음성·전사·TextGrid는 공개본에 넣지 않는다.
- D5: 승인 후 같은 날 개정 — 나머지 6현상 문헌정리를 Cowork에서 선행 완료
  했다(2026-08-23, LD-027). 따라서 §E Gate 0 출력 중 definition 스켈레톤은
  NI만 literature_seeded가 아니라 **7현상 모두 문헌 시드 참조가 가능**하다.
  단, 시드 수준이 다르므로 registry의 literature_evidence_level 필드에
  구분해 기록한다: NI=pilot_full(26주장), PT·NAN·NAL·LLN·VH·HIA=
  core_papers_extracted(현상당 핵심 1~5편 정독·주장 추출 완료, 나머지 문헌은
  목록 수준), 상세는 각 현상종합 초안의 "0. 정독 범위" 절을 따른다.

[4. 문헌 근거 참조 방법 — 읽기 전용]
- 정본: work/literature_evidence_seven_phenomena_20260822/
  - 01_inventory/SOURCE_INVENTORY.jsonl (362행, SRC-001~362)
  - 02_claims/CLAIM_EVIDENCE.jsonl (156행, CLM-0001~0156,
    reference_evidence.v2 — source_sha256로 인벤토리와 결속)
  - 03_phenomenon_synthesis/{NI,PT,NAN,NAL,LLN,VH,HIA}_현상종합_초안_20260823.md
    (논문별 핵심 주장·근거 논리·주장 행 — definition 스켈레톤의 '문헌 근거'
    절은 여기의 CLM ID를 인용)
  - 03_phenomenon_synthesis/*_착수스캐폴드_20260823.md (A_direct 목록·수배 항목)
- 인용은 반드시 SRC-###/CLM-#### ID + 저장소 상대경로로 한다. 문헌 파일의
  본문을 복사해 붙이지 않는다.
- 운율 경계 참고(각 현상 문서의 해당 절): 필수 현상(경음화·비음화)도 운율
  경계(음운구/억양구)별로 적용이 다르다는 문헌 근거(SRC-360 Jun 1998,
  SRC-362 신지영 2011 8장 등)가 등재되어 있다. Gate 0에서는 이를 definition
  템플릿의 confound 후보 항목("운율 경계 개입")으로만 반영하고, 값을
  확정하지 않는다.

[5. 금지 (§B 전문 승계)]
- 원자료·r3 DB·동결 6-tier·동반표·문헌 워크스페이스
  (work/literature_evidence_seven_phenomena_20260822/ 포함) 수정 금지.
- 00_참고문헌/ 이동·수정 금지.
- 어떤 query 값도 새로 동결하지 않는다(동결 query 744bd8cb…는 읽기 전용).
- 자동 실현 판정 금지. MFA/KOINA/wav2vec2 실행 금지. 대량 음성 처리 금지.
- 정식 ledger 자동 쓰기 금지. git commit/push는 사용자 지시 없이는 금지.
- 기존 출력 파일을 덮어쓰지 않는다. 신규 산출은 `.partial` 작성 후 원자 승격.

[6. Gate 0 산출물과 합격 기준 (§E Gate 0 그대로)]
- 출력: config/phenomena_registry.v1.json(7행 완결 — phenomenon_code,
  label_ko, official_slug/slug_status=pending_f0, definition_path/status,
  literature_scaffold_path, literature_evidence_level, a_direct_count,
  query_status, frozen_query_sha256(NI만), gate_position),
  현상별 definition 스켈레톤 7종, 상태 사전·enum 선언 파일, 스키마 문서.
- 합격: registry 7행 완결(placeholder 명시), 선언 파일 SHA manifest,
  독립 검사기(파서 왕복·필수 필드) 통과, 기존 파일 수정 0.
- 구현 후 독립 검사기 결과와 SHA manifest를 제출하고 **정지한다**.
  Gate 1은 별도 지시가 있을 때만 시작한다.
```
