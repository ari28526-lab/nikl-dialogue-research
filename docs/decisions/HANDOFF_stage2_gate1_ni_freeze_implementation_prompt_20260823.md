# 구현 도구 인계 프롬프트 — Gate 1 NI freeze (2026-08-23)

근거:

- `docs/decisions/DECISION_stage2_gate1_ni_contracts_adoption_20260823.md`
  (연구자 채택 결정, SHA `637f7b0fa0198241fbca84fbfbfbf2e590adb1dbf4168ee0e59a05cf9031796e`)
- `docs/reviews/incoming/EXTERNAL_REVIEW_stage2_gate1_n_insertion_contracts_claude_code_20260823.md`
  (독립 검토 `GO_FREEZE_REVIEW`, P0·P1 0건, SHA `8ed621ccf75f8ba9044799c96506bb00fbe39f881e6b1f8455b3752a4e495bc0`)
- Codex Gate 1 감사 `passed=true`
  (AUDIT SHA `f08dfe99…8ad15e`, 검토에서 독립 재계산 일치)

사용법: 아래 코드 블록 전체를 구현 도구에 첫 메시지로 붙여넣는다. 이 프롬프트는
Gate 1 후보의 frozen v1 생성·채택 감사·색인 갱신까지만 허용하며, G5/G6·'요'
query 생성·commit/push는 별도 사용자 GO가 필요하다.

```text
C:\Users\ari30\research\2026_summer_research 저장소에서 작업한다.

[0. 우선순위와 정지선]
- CLAUDE.md가 최우선이다.
- 이번 작업은 연구자 채택 결정
  docs/decisions/DECISION_stage2_gate1_ni_contracts_adoption_20260823.md
  (D-G1-A/B/C)의 freeze 구현 1회다. 그 문서 §4가 이 프롬프트의 정본 근거다.
- 아래 파일을 모두 읽고 [2]의 실측을 마치기 전에는 구현하지 않는다.
- frozen v1 생성·채택 감사·색인 2종 갱신까지만 한다. G5/G6, '요' query JSON
  생성, 신규 후보 추출·occurrence 파생, 실현 판정, TextGrid 수정,
  MFA·KOINA·wav2vec2, 정식 ledger, probe 회귀 보강(D-G1-C, 미결정), Dropbox
  전달, commit/push는 시작하지 않는다.

[1. 먼저 읽을 것 — 순서대로]
1) CLAUDE.md
2) docs/environment/PROJECT_START_HERE.md
3) docs/decisions/DECISION_stage2_gate0_common_contracts_adoption_20260823.md
4) docs/decisions/PLAN_stage2_gate1_NI_reference_implementation_20260823.md
5) docs/decisions/DECISION_stage2_gate1_ni_contracts_adoption_20260823.md  ← 이번 결정 정본
6) docs/reviews/incoming/EXTERNAL_REVIEW_stage2_gate1_n_insertion_contracts_claude_code_20260823.md
   (특히 §2 P2-1~P2-4, §5 환경 유형 검토표, §7 CLM-0015)
7) config/candidate_sources/n_insertion_g1_g4_source_registry_v1_20260823.json
8) config/phenomenon_contracts/n_insertion_contract_candidate_v1_20260823.json
9) config/environment_types/n_insertion_environment_types_candidate_v1_20260823.jsonl
10) phenomena/34_n_insertion/definition_stage2_candidate_v1_20260823.md
11) docs/decisions/NOTE_n_insertion_yo_exploratory_query_candidate_20260823.md
12) config/stage2_environment_class_enum.v1.json
13) scripts/python/audit_stage2_gate1_n_insertion_contracts.py (참조용 — 수정 금지)

[2. 시작 전 실측 Gate]
다음을 실제 파일에서 다시 계산한다. 하나라도 다르면 구현하지 말고 보고한다.
- 채택 결정 문서 SHA-256
  637f7b0fa0198241fbca84fbfbfbf2e590adb1dbf4168ee0e59a05cf9031796e
- 검토 보고서 MD SHA-256
  8ed621ccf75f8ba9044799c96506bb00fbe39f881e6b1f8455b3752a4e495bc0
- Gate 1 candidate 산출물 SHA-256 (freeze의 동결 입력):
  - source registry
    06d44af2e930429f63019a31777dd472d293411723b92d0d56e409ebe6af6b12
  - 계약 candidate
    2c5a1f4cf4eb89ac4be57878d41f77906cee9cfa21f6f87c1d751a600de7c9ff
  - 환경 유형 candidate
    60c3f44d847e0e183d763b5e02dab584a42c8d15ce08cebab4aa3020cec84427
  - definition candidate
    10a5e81f299ba5b2eae65e1f2a14ee323ba4b6f7072ab37767f3a926fba111f3
  - '요' NOTE
    34ba06931c1947cd925d1ce1ec06eacca93c5c8cb3629da437eb4ecbc5d2ce91
  - Gate 1 AUDIT JSON
    f08dfe99ad94bc47a66ac3302c3c483a810946e20551441c81291425228ad15e
  - Gate 1 SHA manifest
    ea7e160f9cea3be1db6487e87bab33d65dc5c2778906cfacaf59c6101deb25d5
- 보호 입력 SHA-256:
  - NI 동결 query
    744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6
  - join 계약
    12d811632a9c440e33fd76f814620c65e47113bdfda4ea058581b5e476c44050
  - 기존 definition.md
    aa23b940d1e556df98cee5f332e8757f886ab098f468620fe084b93e90983513
  - SOURCE_INVENTORY(362행)
    e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680
  - CLAIM_EVIDENCE(156행)
    1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a
- needs_human_check: 정확히 CLM-0008, CLM-0015, CLM-0026, CLM-0145, CLM-0151.
  CLM-0015의 플래그는 true 그대로여야 한다(freeze에서도 해제하지 않는다).
- source registry 재집계: 후보 941,903 = joined 941,903, 어절 내부 353,626,
  어절 간 588,277 (연도별 manifest·감사 JSON 경유, 대용량 CSV 재스캔 금지).
- 작업 시작 시 git status를 baseline으로 기록한다. 현재 worktree에는 Gate 0·
  Gate 1 산출물, 검토 보고서 2종, 채택 결정 문서, 이 인계 문서가 미추적으로
  존재하고, 추적 파일 변경은 색인 2종( M docs/decisions/_INDEX.md,
   M scripts/SCRIPTS_INDEX.md)뿐인 것이 정합 상태다. 그 밖의 변화가 있으면
  중단하고 보고한다.

[3. 이번 구현 범위 — 결정 반영 규칙]
D-G1-B(채택)에 따라 frozen v1을 만들되, D-G1-A(환경 최대 포함 + CLM-0015
유보)를 다음과 같이 정확히 반영한다.

frozen 계약
config/phenomenon_contracts/n_insertion_contract_frozen_v1_20260823.json
- candidate의 query_contract·include·exclude·retention·confound·membership
  내용을 의미 변경 없이 유지한다. 조건 7종(scope + 공통 6)은 동결 query와
  완전 동일해야 하며 새 occurrence 필터를 추가하지 않는다.
- contract_status="frozen", status="frozen_researcher_adopted_20260823",
  researcher="ari30", confirmed_at=실제 시각(KST 명시).
- supersedes에 candidate 경로와 SHA(2c5a1f4c…)를 결속한다.
- adoption_decision에 채택 결정 문서 경로와 SHA(637f7b0f…)를 결속한다.
- source_registry_reference를 경로+SHA(06d44af2…)로 강화한다.
- unresolved_items는 삭제하지 않는다:
  - NI_UNR_001 → status="deferred_by_decision_d_g1_a" + 결정 문서 참조.
    유보 사유(Hwang 2007/2008 원전 대조 필요, 원문 미보유·수배 중)를 기록.
  - NI_UNR_005 → status="resolved_by_adoption_20260823" + 결정 문서 참조.
  - NI_UNR_002/003/004는 non_blocking/deferred 그대로 보존.
- safety 5항목은 전부 false 유지.

frozen 환경 유형
config/environment_types/n_insertion_environment_types_frozen_v1_20260823.jsonl
- 7행, ID·순서는 candidate와 동일. 어떤 행도 삭제·추가하지 않는다
  (D-G1-A: 환경을 최대한 전부 포함).
- 행별 처리:
  - NI_ENV_CORE_C_J, NI_ENV_CORE_C_I, NI_ENV_YO_JX →
    class_status="researcher_confirmed",
    classified_by="researcher_adoption_decision_20260823",
    classified_at=실제 시각, supersedes에 candidate 파일 경로+SHA와
    해당 environment_type_id를 기록(조용한 승격 금지 — 추적 가능해야 함).
    분류값·priority_band·근거 refs는 변경하지 않는다.
  - NI_ENV_SINO_RESONANT_J, NI_ENV_SINO_OBSTRUENT_J →
    class_status="pending" 유지. pending_reason을 D-G1-A 유보로 갱신
    ("CLM-0015 deferred by DECISION…adoption_20260823 §D-G1-A; Hwang 원전
    입수 후 해소"). 환경은 포함 상태로 보존, 비교군 삭제 금지.
  - NI_ENV_INTER_EOJEOL → environment_class=null, class_status="pending",
    deferred 그대로(후속 Gate 기결정, 변경 금지).
  - NI_ENV_UNCLEAR_BOUNDARY → pending 그대로.
- 전 행 occurrence_assignment_status="not_started" 유지. freeze는 occurrence
  배정을 시작하지 않는다.
- NI_ENV_YO_JX의 decision_status="treatment_decided_query_not_created" 유지.
  '요' query JSON·후보 CSV를 만들지 않는다.

frozen definition
phenomena/34_n_insertion/definition_stage2_frozen_v1_20260823.md
- candidate 내용을 유지하되 상태를 갱신한다: definition_status는 짧은 enum
  "researcher_confirmed"(Gate 0 P2-6 방향), 생명주기 상태는
  "frozen_v1_adopted_20260823"로 별도 표기. 두 값을 한 문자열로 합치지 않는다.
- CLM-0015 유보와 한자어 2행 pending 사실, '요'·어절 간 기결정, G5/G6
  정지선을 그대로 명시한다.
- 기존 definition.md와 definition_stage2_candidate_v1_20260823.md는 수정하지
  않는다.

색인 2종 갱신 (이번 작업에서 유일하게 허용되는 기존 추적 파일 수정)
- scripts/SCRIPTS_INDEX.md: audit_stage2_gate1_n_insertion_contracts.py(2026-08-23
  스냅샷 검사기로 보존)와 신규 freeze 감사기 행을 추가.
- docs/decisions/_INDEX.md: DECISION_stage2_gate1_ni_contracts_adoption과
  NOTE_n_insertion_yo_exploratory_query_candidate 항목을 추가하고 최종 갱신일을
  갱신. 다른 항목은 건드리지 않는다.

[4. 정확한 신규 산출물 allowlist]
다음 파일만 새로 만든다(색인 2종 수정 외 기존 파일 수정 금지).
- config/phenomenon_contracts/n_insertion_contract_frozen_v1_20260823.json
- config/environment_types/n_insertion_environment_types_frozen_v1_20260823.jsonl
- phenomena/34_n_insertion/definition_stage2_frozen_v1_20260823.md
- scripts/python/audit_stage2_gate1_ni_freeze_contracts.py
- tests/test_audit_stage2_gate1_ni_freeze_contracts.py
- outputs/pilots/stage2_gate1_ni_freeze_20260823/
  AUDIT_stage2_gate1_ni_freeze_20260823.json
- outputs/pilots/stage2_gate1_ni_freeze_20260823/
  SHA256SUMS_stage2_gate1_ni_freeze_20260823.txt
- logs/stage2_gate1_ni_freeze_20260823/ 아래 검증 로그

모든 신규 파일은 .partial에 완전히 쓴 뒤 원자 승격한다. 기존 동명 파일이
하나라도 있으면 FileExistsError로 쓰기 전에 중단한다. SHA manifest는 자신과
임시파일을 해시하지 않는다. 실착수일이 2026-08-23이 아니면 파일명·폴더명
날짜를 실제 날짜로 바꾸고 보고에 명시한다.

[5. freeze 독립 감사기 요구사항]
audit_stage2_gate1_ni_freeze_contracts.py는 산출 코드와 독립적으로 검사한다.
- [2]의 모든 SHA 재확인(candidate 7종·AUDIT·manifest·결정 문서·검토 보고서
  MD·보호 입력). candidate가 1바이트라도 바뀌었으면 실패.
- frozen 계약: 동결 query 실파일과 조건 7종 완전 일치 재검사, researcher·
  confirmed_at 존재, supersedes/adoption_decision SHA 결속, 새 occurrence
  필터 0, NI_UNR_001 유보 기록 존재(삭제 금지), safety false 5종.
- frozen 환경: 7행·ID 순서, 행 1·2·5 researcher_confirmed + 추적 가능한
  classified_by/supersedes, 행 3·4 pending + D-G1-A 사유, 행 6 null+pending,
  행 7 pending, 전 행 occurrence_assignment_status=not_started,
  모든 SRC/CLM 참조 실재, CLM-0015 정본 플래그 true 유지.
- frozen definition의 상태 표기와 정지선 문구.
- zero-drop: source registry SHA 불변 + 941,903/353,626/588,277 재집계
  (manifest 경유, CSV 재스캔 금지). 신규 occurrence 파생 0.
- '요' query JSON·후보 CSV 부재. config/target_queries/ 파일 3종 그대로.
- 색인 2종에 요구 항목 존재 + git status의 추적 파일 변경이 색인 2종뿐임을
  확인. baseline 대비 그 밖의 worktree 변화 0.
- .partial 잔존 0, manifest 자기해시 0, 기존 출력 존재 시 쓰기 전 중단.

단위 테스트 최소 시나리오:
- 실제 산출물 성공 경로
- candidate SHA 불일치 실패
- supersedes/adoption_decision SHA 불일치 실패
- 존재하지 않는 CLM 참조 실패
- 한자어 행(3·4)을 researcher_confirmed로 바꾼 조용한 승격 실패
- NI_UNR_001 삭제 시 실패
- 기존 출력 존재 시 FileExistsError
- manifest 자기 제외

[6. 안전 규칙]
- D:\00_RAW, D:\10_LAYERS, D:\30_RELEASES, r3 DB, 동결 6-tier·동반표,
  outputs/candidates·outputs/reports의 G1~G4 산출물, 00_참고문헌, 문헌 work/
  전체, docs/reviews/incoming/(_to_delete 포함)은 읽기 전용이다.
- 동결 query·join 계약·기존 definition·Gate 1 candidate 5종·Gate 1 감사기·
  테스트·AUDIT·manifest·검토 보고서·채택 결정 문서를 수정하지 않는다.
- 대용량 CSV 전체 재해시·전수 스캔 금지.
- 자동 실현 판정, 정식 ledger 쓰기, MFA/KOINA/wav2vec2, 음성 처리 금지.
- git add/commit/push 금지(완료 보고 후 사용자가 별도 승인).
- Python은 C:\Users\ari30\miniforge3\envs\mfa\python.exe를 사용하고, 신규
  Python에 sys.stdout.reconfigure(encoding="utf-8")를 넣는다.
- 비밀값·발화 원문을 출력하지 않는다.

[7. 검증 명령과 로그]
다음을 모두 실행하고 명령·exit code·결과를
logs/stage2_gate1_ni_freeze_20260823/ 아래 UTF-8 로그로 보존한다.
- 신규 Python마다 py_compile
- freeze 감사기 단위 테스트 전체
- --check-only 성공 실행(출력 생성 전)
- 산출물 생성 실행 1회
- 기존 출력 존재 시 재실행이 FileExistsError로 중단됨을 확인
- 최종: AUDIT JSON·manifest 독립 재해시와 사후 --check-only
참고: 기존 Gate 1 감사기(audit_stage2_gate1_n_insertion_contracts.py)는
2026-08-23 스냅샷 검사기라 현재 worktree에서 git 검사가 의도적으로 실패한다.
재기준선하지 말고 그대로 보존한다(Gate 0 채택 문서 §4와 같은 정책).

[8. 완료 보고와 정지]
다음을 한국어로 보고하고 정지한다.
- 신규 파일 목록과 각 SHA-256
- candidate→frozen supersedes 매핑 표
- freeze 감사 JSON·manifest 경로와 SHA
- 색인 2종 diff 요약(다른 추적 파일 변경 0의 증거)
- CLM-0015 유보가 어디에 어떻게 기록됐는지
- 검증 로그 목록
- "frozen v1 생성·감사 통과, commit은 사용자 승인 대기" 상태 명시

이후 단계(commit·push, LLN Gate 1 착수, G5/G6, '요' query 설계, probe 보강
D-G1-C)는 별도 사용자 GO 없이는 하지 않는다.
```
