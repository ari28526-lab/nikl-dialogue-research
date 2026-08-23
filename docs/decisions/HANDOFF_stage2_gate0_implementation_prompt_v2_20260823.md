# 구현 도구 인계 프롬프트 — Gate 0 (2026-08-23 Codex 검증 반영본)

근거:

- `docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md`
- `docs/decisions/DECISION_stage2_seven_phenomena_workflow_user_decisions_20260823.md`
- `docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json`
- 문헌 L1 확장 완결(LD-027)·운율 경계 문헌 반입(LD-028)

Codex 독립 점검에서 문헌 handoff의 행·SHA·SRC/CLM 결속은 통과했다. 다만
handoff 3종은 존재하지 않는 NI 착수스캐폴드 경로를 기재한다. 구현 시 NI의
`literature_scaffold_path`는 `null`로 두고, 존재하는 NI 현상종합 초안과 기존
정식 definition을 참조한다. incoming 보고서 원본은 provenance를 위해 고치지
않는다.

사용법: 아래 코드 블록 전체를 구현 도구에 첫 메시지로 붙여넣는다. 이 프롬프트는
Gate 0 후보 산출과 독립 감사까지만 허용하며, 연구자 채택·동결과 Gate 1은 별도
GO가 필요하다.

```text
C:\Users\ari30\research\2026_summer_research 저장소에서 작업한다.

[0. 우선순위와 정지선]
- CLAUDE.md가 최우선이다.
- 2026-08-23의 사용자 결정 D1~D5, 문헌 CURRENT_STATE(LD-027/028),
  LITERATURE_HANDOFF JSON이 그보다 앞서 작성된 외부 검토의 359자료/26주장 및
  "NI 외 6현상 placeholder" 기술을 대체한다.
- 아래 파일을 모두 읽고 실측을 마치기 전에는 구현하지 않는다.
- 이번 작업은 Gate 0 후보 산출·감사까지만 한다. 채택·동결, Gate 1, A7, A8은
  시작하지 않는다.

[1. 먼저 읽을 것 — 순서대로]
1) CLAUDE.md
2) docs/README.md
3) docs/environment/PROJECT_START_HERE.md
4) docs/environment/PROJECT_CURRENT_STATE.md
5) docs/decisions/REQUIREMENT_stage2_manual_textgrid_and_phenomenon_release_20260822.md
6) docs/decisions/PLAN_stage2_seven_phenomena_PV_pilot_20260819.md
7) docs/decisions/PLAN_stage2_target_query_and_realization_design_20260818.md
8) docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md
   (§A·§B·§E를 읽되, 오래된 문헌 수치와 D5 초안은 아래 최신 자료로 대체)
9) docs/decisions/DECISION_stage2_seven_phenomena_workflow_user_decisions_20260823.md
10) docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json
    (Gate 0 문헌 seed map 정본)
11) 같은 이름의 .md (사람용 설명; JSON과 충돌하면 JSON 우선)
12) work/literature_evidence_seven_phenomena_20260822/00_admin/문헌자료_참조가이드_20260823.md
13) work/literature_evidence_seven_phenomena_20260822/00_admin/CURRENT_STATE.md
14) work/literature_evidence_seven_phenomena_20260822/00_admin/SCHEMA.md
15) work/literature_evidence_seven_phenomena_20260822/01_inventory/SOURCE_INVENTORY.jsonl
16) work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl
17) work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/
    {NI,PT,NAN,NAL,LLN,VH,HIA}_현상종합_초안_20260823.md
18) phenomena/34_n_insertion/definition.md
19) config/target_queries/n_insertion_production_v1_20260818.json
20) docs/decisions/RESULT_stage2_G4_full_six_year_candidates_20260818.md

[2. 시작 전 실측 Gate]
다음을 실제 파일에서 다시 계산한다. 하나라도 다르면 구현하지 말고 보고한다.
- SOURCE_INVENTORY: 362행, SHA-256
  e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680
- CLAIM_EVIDENCE: 156행, SHA-256
  1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a
- CLM ID: CLM-0001~CLM-0156 연속, source_id/source_sha256 결속 오류 0
- needs_human_check: CLM-0008, CLM-0015, CLM-0026, CLM-0145, CLM-0151
- LITERATURE_HANDOFF JSON SHA-256
  938353d719e1ddc57c8ba96ca4694310f6570a4b4ca944f684a5a66961bdebae
- NI 동결 query SHA-256
  744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6
- 현상종합 7종 존재. 착수스캐폴드는 PT·NAN·NAL·LLN·VH·HIA 6종만 존재하며,
  NI_착수스캐폴드_20260823.md는 존재하지 않는 것이 현재 정합 상태다.
- 작업 시작 시 git status와 보호 입력 파일 SHA를 baseline으로 기록한다.
  작업 트리가 이미 깨끗하지 않으므로 기존 사용자 파일을 수정·삭제·이동하지
  말고, 사전 선언한 신규 파일 allowlist 밖 변화가 있으면 중단한다.

[3. 이번 구현 범위]
외부 검토 §E의 Gate 0 중 A1~A6 구조만 후보로 구현한다.
- A1 definition 템플릿
- A2 phenomena registry
- A3 환경 분류 enum 선언
- A4 inclusion/exclusion/confound 계약 템플릿
- A5 zero-drop 상태 사전
- A6 append-only 추가정보 sidecar 스키마

다음은 범위 밖이다.
- A3의 현상별/환경별 실제 4단 분류값 부여
- A4의 현상별 query 조건·포함/제외값 확정 또는 동결
- A6 데이터 JSONL 생성
- D1의 '요' 탐색 query config·조건 생성(결정 참조와 pending 표지만 허용)
- A7 TextGrid queue·패널·Praat 왕복 구현
- A8 공개 파생본 빌더 구현
- Gate 1 이후의 어떤 작업

[4. 사용자 결정의 Gate 0 반영 범위]
- D1: 기존 NI query와 전체 SHA만 registry에 참조한다. '요' 환경은
  pending_exploratory_query_candidate + CLM-0002 결정 참조만 기록한다.
- D2: gate_position에 NI reference implementation, LLN next를 기록한다.
- D3·D4: future_gate_context/결정 참조로만 보존한다. 기능을 구현하지 않는다.
- D5: 7현상 모두 literature seed를 참조하되 수준을 구분한다.
  NI=pilot_full, 나머지 6현상=core_papers_extracted.
- NI 최초 파일럿 26주장과 NI 전체 태깅 32건을 서로 다른 필드로 보존한다.

[5. 정확한 신규 산출물 allowlist]
다음 파일만 새로 만든다. 기존 NI definition은 수정하지 않는다.
- config/phenomena_registry.v1.json
- phenomena/_templates/definition.v1.md
- phenomena/_draft/PT/definition.md
- phenomena/_draft/NAN/definition.md
- phenomena/_draft/NAL/definition.md
- phenomena/_draft/LLN/definition.md
- phenomena/_draft/VH/definition.md
- phenomena/_draft/HIA/definition.md
- config/stage2_environment_class_enum.v1.json
- config/stage2_inclusion_exclusion_confound_contract_template.v1.json
- config/stage2_zero_drop_status_dictionary.v1.json
- config/stage2_additional_information_sidecar_schema.v1.json
- docs/decisions/SCHEMA_stage2_gate0_common_contracts_20260823.md
- scripts/python/audit_stage2_gate0_common_contracts.py
- tests/test_audit_stage2_gate0_common_contracts.py
- outputs/pilots/stage2_gate0_common_contracts_20260823/
  AUDIT_stage2_gate0_common_contracts_20260823.json
- outputs/pilots/stage2_gate0_common_contracts_20260823/
  SHA256SUMS_stage2_gate0_common_contracts_20260823.txt
- logs/stage2_gate0_common_contracts_20260823/ 아래 검증 로그

모든 신규 파일은 .partial에 완전히 쓴 뒤 원자 승격한다. 기존 동명 파일이 하나라도
있으면 FileExistsError로 쓰기 전에 중단한다. SHA manifest는 자신과 임시파일을
해시하지 않는다.

[6. registry 계약]
최상위 JSON은 다음 구조로 한다.
- schema_version
- generated_from: 문헌 handoff·inventory·claims·NI query의 상대경로와 SHA
- phenomena: 정확히 7개 객체(PT,NAN,NAL,NI,LLN,VH,HIA 중복·누락 0)

현상 객체 필수 필드:
phenomenon_code, label_ko, official_slug, slug_status,
definition_path, definition_status, literature_synthesis_path,
literature_scaffold_path(nullable), literature_evidence_level,
core_extracted_source_count, core_extracted_claim_count,
total_phenomenon_claim_mentions, a_direct_count,
query_status, frozen_query_sha256(nullable), gate_position, notes.

특수 규칙:
- NI official_slug=34_n_insertion, slug_status=assigned_existing,
  definition_path=phenomena/34_n_insertion/definition.md,
  definition_status=researcher_confirmed. 이 파일은 읽기 전용이다.
- NI literature_scaffold_path=null. 존재하지 않는 NI 스캐폴드 경로를 만들거나
  기재하지 않는다.
- 나머지 6현상 official_slug=null, slug_status=pending_f0,
  definition_path=phenomena/_draft/<CODE>/definition.md.
- literature_synthesis_path는 7현상 모두 실제 존재 경로를 넣는다.
- frozen_query_sha256는 NI만 전체 64자리 SHA, 나머지는 null.
- draft PV 조건을 frozen으로 승격하지 않는다.

[7. 문헌 seed 사용 규칙]
- LITERATURE_HANDOFF JSON의 phenomena.<CODE>.seed_map을 사용하고, 모든 참조는
  SRC-###/CLM-#### + 저장소 상대경로로 기록한다. 문헌 본문을 복사하지 않는다.
- claim_verified, pending_researcher_adoption, needs_human_check,
  source_level_only를 구분한다.
- needs_human_check 5건은 모두 Gate 0 non_blocking_pending이다. 값을 확정하지
  말고 ID와 상태만 보존한다.
- SRC-360·361·362·356은 CLAIM_EVIDENCE 행이 없는 source_level_only,
  pending_claim_extraction이다. claim-verified 근거로 쓰지 않는다.
- PT/NI, NAN/NAL/LLN, VH/HIA 중복·경계 문제는 ID와 pending 상태만 기록한다.
- handoff 원본의 NI scaffold_doc 오류는 구현 입력에서만 null로 정규화하고,
  incoming JSON·MD·HTML은 수정하지 않는다.

[8. enum·상태 모델]
- A3은 environment_class enum만 선언한다:
  general_direct | peripheral_reported | theoretical_underreported |
  unclear_boundary. 실제 현상/환경 행을 분류하지 않는다.
- A4는 빈 계약 템플릿과 필드·상태만 선언한다. query 값을 넣지 않는다.
- A5에서 서로 다른 축을 하나의 상호배타 enum으로 합치지 않는다.
  최소 독립 축:
  1) textgrid_review_need = not_needed | required | unsure
  2) textgrid_asset_status = available | unavailable | blocked
  3) manual_task_status = not_created | queued | exported | returned | audited
  required와 unavailable은 동시에 가능하다.
- zero-drop은 각 축에서 입력 행마다 정확히 하나의 값을 가져야 한다는 불변식으로
  정의한다. 서로 다른 축의 상태 수를 한 합계식으로 더하지 않는다.
- A6은 JSON Schema와 예시 1건만 문서에 두고 실제 sidecar 데이터 파일을 만들지
  않는다. append-only·supersedes·미확인 상태 보존을 검증 가능하게 선언한다.

[9. 안전 규칙]
- D:\00_RAW, D:\10_LAYERS, r3 DB, 동결 6-tier·동반표, outputs/candidates의
  G1~G4 산출물, 00_참고문헌, 문헌 work/ 전체는 읽기 전용이다.
- query·PV builder·기존 스크립트·기존 definition을 수정하지 않는다.
- 자동 실현 판정, 정식 ledger 쓰기, MFA/KOINA/wav2vec2, 음성 전수 처리 금지.
- git commit/push 금지.
- Python은 C:\Users\ari30\miniforge3\envs\mfa\python.exe를 사용하고,
  신규 Python 스크립트에 sys.stdout.reconfigure(encoding="utf-8")를 넣는다.
- 비밀값을 출력하지 않는다.

[10. 검증]
독립 감사기는 산출물을 생성한 코드와 독립적으로 다음을 검사한다.
- JSON 파서 왕복, schema_version, 필수 필드, enum 허용값
- registry 7현상 중복·누락 0 및 모든 기재 상대경로 존재
- 문헌/NI query 입력 SHA와 시작 전 snapshot 일치
- 모든 SRC/CLM ID 존재와 CLM→SRC/source_sha256 결속
- NI 26 core와 32 total 구분, needs_human 5건 보존
- NI scaffold=null, 나머지 6 scaffold 경로 존재
- A3 실제 분류행 0, A4 frozen 값 0, A6 데이터행 0
- 허용 신규 파일 외 기존 파일 수정 0(baseline/post SHA + git status 대조)
- manifest 대상 전부 존재, .partial 잔존 0, manifest 자기해시 0

검증 명령은 다음을 모두 남긴다.
- 신규 Python마다 py_compile
- 감사기 대표 성공 시나리오
- 필수 필드/ID/SHA가 잘못된 실패 시나리오
- 기존 출력 존재 시 쓰기 전 중단 시나리오
- 테스트 결과·명령·exit code를 logs/stage2_gate0_common_contracts_20260823/
  아래 UTF-8 로그로 보존

[11. 완료 보고와 정지]
다음을 한국어로 보고하고 정지한다.
- 신규 파일 목록
- 입력 및 산출 SHA
- 독립 감사 JSON과 검증 로그 경로
- 보호 입력/기존 파일 수정 0의 증거
- pending 항목과 미해결 질문
- "Gate 0 후보가 감사 통과했으나 아직 연구자 채택·동결 전"이라는 상태

Gate 1, query 생성·변경, 실행·청취, commit/push는 별도 사용자 GO 없이는 하지
않는다.
```
