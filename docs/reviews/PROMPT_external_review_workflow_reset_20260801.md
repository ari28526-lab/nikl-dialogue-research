# 외부 도구 전달용 프롬프트 — 전체 workflow 감사와 구조 리셋

아래 내용을 그대로 같은 로컬 프로젝트 폴더에서 작업하는 다른 도구에 전달한다.

---

당신은 한국어 언어학 연구 인프라 프로젝트의 독립 workflow 감사자다. 이번 요청은
코드 스타일 리뷰가 아니다. 반복 파일럿·검수에도 전수 생산이 계속 미뤄진 원인을
재구성하고, 사용자 결정이 실제 생산 경로에 반영됐는지 확인하고, 의미 없는 검수를
제거하며, 안전하게 진도를 내는 최종 순서와 문서 archive/구조 refresh 계획을 만드는
것이 목적이다.

프로젝트 루트:

```text
C:\Users\ari30\research\2026_summer_research
```

## A. 절대 원칙

1. 문서의 `완료`, `확정`, `GO` 표현을 사실로 가정하지 마라. 실제 config, schema,
   생산 runner, test, manifest/artifact를 대조하라.
2. 구 2020 MFA/TextGrid를 다시 전수 검토하거나 재사용하는 계획을 제안하지 마라.
3. MFA/G2P phone을 실제 음운 실현 판정으로 취급하지 마라.
4. 형태소 시간경계를 자동 정렬됐다고 주장하지 마라.
5. 사용자에게 요청하는 검수는 언어학적 선택, 자료 제외 승인, 파괴적 작업 승인처럼
   사람이 결정해야 하는 것으로 한정하라.
6. “더 검수하라”는 권고에는 막는 실패, 필요한 표본/전수 범위, 종료 조건, 실패 시
   행동을 반드시 적어라.
7. 새 파일럿은 기존 test/manifest가 다루지 못한 별개의 위험이 있을 때만 권고하라.

## B. 먼저 읽을 정본 후보

다음을 처음부터 끝까지 읽어라.

```text
AGENTS.md
docs/environment/PROJECT_START_HERE.md
docs/environment/linguistics-research-environment-master-notes.md
docs/environment/PROJECT_CURRENT_STATE.md
docs/reviews/BRIEF_external_review_workflow_reset_20260801.md
docs/decisions/PROPOSAL_prebulk_execution_order_20260801.md
docs/decisions/DECISION_pre_MFA_combination_search_v3_20260801.md
docs/decisions/DECISION_r2_realign_all_six_years_20260729.md
docs/decisions/DECISION_incremental_unattended_year_MFA_20260801.md
docs/decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md
docs/WORK_HISTORY_2026-07.md
docs/WORK_HISTORY_2026-08.md
scripts/SCRIPTS_INDEX.md
config/paths.json
```

그 뒤 `rg --files docs`, `git log --oneline --decorate`, `git log --name-status`를
이용해 전체 문서·변경 흐름을 inventory하라. 다음 과거 문서는 현재 방법과 혼동될
가능성이 높으므로 반드시 현재 정본과 관계를 판정하라.

```text
docs/decisions/AUDIT_2020_pre_mfa_full_pipeline_2026-07-26.md
docs/decisions/MONITOR_pre_mfa_bulk_pre_mfa_v1_20260725.md
docs/decisions/MONITOR_2021_pre_mfa_v1_20260727.md
docs/decisions/PLAN_2022_improved_MFA_after_2020_2021.md
docs/decisions/AUDIT_2020_2021_MFA_comparison_and_2022_gate_20260728.md
docs/decisions/DECISION_common_pronunciation_resource_v2_20260728.md
docs/decisions/PLAN_integrated_CSV_MFA_research_infrastructure_20260731.md
docs/decisions/DECISION_auto_phoneme_roman_aux_layer_20260731.md
```

모든 104개 문서를 같은 깊이로 요약할 필요는 없다. 그러나 전체 파일명과 상호 참조를
inventory하고, 현재 상태·실행 순서·출력 계약·검수·archive 판정에 영향을 주는 문서는
직접 읽어라.

## C. 실제 구현·산출물 대조

필요한 범위에서 다음을 읽어라.

```text
scripts/run_morph_search_year_safe.ps1
scripts/python/build_morph_search_year_sharded.py
scripts/prepare_mfa_year_exclusion_review.ps1
scripts/prepare_full_mfa_approval_reviews.ps1
scripts/preflight_mfa_year_queue.ps1
scripts/start_full_mfa_after_review.ps1
scripts/run_mfa_year_queue_safe.ps1
scripts/run_eojeol_realign.ps1
scripts/python/export_mfa_db_research_6tier.py
scripts/python/audit_mfa_research_6tier_year.py
scripts/python/build_research_companion_parquet.py
config/research_companion_tables_schema_v2.json
outputs/reports/EVIDENCE_morph_search_v3_regression_60_20260801.json
outputs/reports/PREFLIGHT_morph_search_v3_2020_shard1_20260801.json
outputs/reports/EVIDENCE_research_6tier_post_review_20260801.json
```

외부 D: manifest는 전체 코퍼스를 스캔하지 말고 문서에 인용된 manifest만 읽기
전용으로 확인하라. 특히 다음 사실을 검증하라.

- 공통 Jamo r2 release/adoption은 실제 success인가?
- 2020–2025 신규 r2 MFA는 실제로 미시작인가?
- 2020 `morph_search.v3`은 실제 1/23에서 멈췄는가?
- 6-tier와 post-MFA 4표가 생산 runner에 실제 연결됐는가?
- pre-MFA 7표와 post-MFA 4표의 최종 joined search view는 실물이 있는가?
- 우리말샘 1:N 후보는 최종 검색층에 실제 연결됐는가?
- 문서에서 반영됐다고 한 결정이 기본 실행 경로에서도 강제되는가, 선택 인자나
  별도 미호출 script에만 존재하는가?

## D. 반드시 수행할 감사

### D1. 전체 생산 단계 재구성

원 JSON/메타데이터부터 형태소·사전·pre-MFA 검색표·LAB·MFA·TextGrid·post-MFA
동반표·최종 검색 DB·후보 bundle·KOINA/wav2vec2·manual judgment까지 한 흐름으로
재구성하라. 각 단계에 입력, 출력, 정본 위치, 실행 entrypoint, manifest, 완료 정의,
재개 지점을 적어라.

### D2. 결정–반영 추적 감사

중요 사용자 결정과 외부 리뷰 지적을 최소 다음 영역에서 추적하라.

- 6개년 전부 Jamo r2로 신규 정렬
- 구 2020/2021 결과 비재사용
- 공통 acoustic/G2P/phone 기준
- 6-tier TextGrid와 모든 tier 0–xmax 경계
- 형태소를 임의 시간분할하지 않고 발화 전체-span 정보로 표시
- 형태소·철자 Roman·위치/경계 조합검색
- 숫자·기호의 근거 기반 읽기와 후보 분리
- dialogue/co-speaker metadata
- 우리말샘 발음의 1:N 보조표 분리
- `phones_mfa`의 broad Roman `phoneme_r_auto`
- KOINA/stitch/wav2vec2의 선별·비덮어쓰기 원칙
- 연도/shard/DB checkpoint와 자동 full-clean 금지
- 연구자 예외 검토 최소화

각 결정에 대해 `문서만`, `코드만`, `테스트만`, `production runner 연결`, `실물 검증`
중 어디까지 왔는지 판정하라.

### D3. 검수 가치 감사

지금까지의 파일럿, workbook 검토, 외부 리뷰, preflight, machine QC, researcher
review를 나열하고 각각을 `유지/통합/기계화/조건부/폐지`로 판정하라.

특히 다음을 찾아라.

- 동일한 invariant를 다른 이름으로 반복 확인한 검수
- 결과가 다음 결정이나 코드 변경으로 이어지지 않은 검수
- 전체 사람이 보지 않아도 전수 기계검사가 가능한 항목
- 계약이 변하지 않았는데 매 연도 반복하는 표본 검토
- 실패해도 조치 규칙이 없어 대기만 만드는 gate
- 이미 사용자 전역 결정으로 해결됐는데 개별 행에 반복 입력하는 검수

사람 검토를 유지한다면 연구자가 정확히 무엇을 듣고/보고 어떤 결정을 기록해야
하는지 한 문장으로 정의하라.

### D4. 진행 교착 원인과 최단 생산 경로

왜 검수에서 생산으로 넘어가지 못했는지 기술·문서·의사결정·도구 운영 원인으로
분류하라. 추가 안전장치가 아니라 기존 gate를 정리해 해결할 수 있는지 우선 보라.

다음 시간축으로 최종 순서를 제시하라.

1. `지금 즉시, 계산 없이`
2. `2020 신규 MFA 전`
3. `2020 첫 생산 연도`
4. `2020 Gate B 후 2021–2025`
5. `6개년 정렬 후 최종 검색 인프라`
6. `선별 실제 연구`

각 단계에 사용자 행동을 최대 한 개만 두고, 나머지는 기계 gate/자동 실행으로 묶는
방안을 우선하라.

### D5. archive와 구조 refresh

현재 파일을 이동하거나 삭제하지 말고 먼저 이동 계획을 작성하라.

- `canonical_active`, `supporting_evidence`, `historical_valid`, `superseded`,
  `failed_diagnostic`, `generated_review_artifact`, `unknown_needs_owner`로 분류
- 현재 경로, 제안 경로, 대체 정본, 이동 이유, 코드/문서 링크 위험을 기록
- `PROJECT_CURRENT_STATE.md`를 짧은 정본으로 교체할 초안을 작성
- 하나의 START_HERE, 하나의 CURRENT_STATE, 하나의 production RUNBOOK,
  active method/schema index, evidence index, archive manifest 구조를 제안
- `git mv`와 link rewrite 순서, 검증 명령, rollback 방법을 제시
- D:/E:/H: 대형 자료는 별도 inventory만 만들고 이동·삭제하지 않음

대규모 물리 이동보다 index와 상태 header만으로 혼동을 줄일 수 있다면 그 최소안을
우선하라.

## E. 결과 파일

다음 다섯 파일만 새로 작성하라.

### 1. 주 보고서

```text
docs/reviews/incoming/EXTERNAL_REVIEW_workflow_reset_20260801.md
```

필수 목차:

```text
# 외부 리뷰: 전체 workflow 감사와 구조 리셋
## 1. 최종 판정 — GO / GO AFTER FIXES / NO_GO
## 2. 실제 현재 상태
## 3. 검수 교착의 근본 원인
## 4. 반영됐다고 했지만 미반영/부분반영인 항목
## 5. 의미 없는·중복된 검수
## 6. 유지해야 할 검수와 사람 판단
## 7. 최단 최종 생산 순서
## 8. 2020 GO 조건과 Gate B
## 9. archive·구조 refresh 권고
## 10. 사용자가 지금 할 한 가지
```

### 2. 결정–반영 추적표

```text
docs/reviews/incoming/WORKFLOW_DECISION_TRACE_20260801.csv
```

UTF-8 BOM CSV 열:

```text
trace_id,domain,user_decision,decision_source,claimed_status,
implementation_evidence,test_or_manifest_evidence,actual_status,gap,severity,next_action
```

`actual_status`는 `fully_applied/partially_applied/not_applied/superseded/
evidence_missing` 중 하나다.

### 3. 검수 가치표

```text
docs/reviews/incoming/WORKFLOW_VALIDATION_VALUE_20260801.csv
```

UTF-8 BOM CSV 열:

```text
validation_id,validation_name,risk_or_decision,unique_evidence,
manual_or_machine,current_frequency,recommendation,keep_until,remove_after,notes
```

`recommendation`은 `keep/merge/automate/conditional/retire` 중 하나다.

### 4. archive 이동안

```text
docs/reviews/incoming/WORKFLOW_ARCHIVE_CANDIDATES_20260801.csv
```

UTF-8 BOM CSV 열:

```text
current_path,classification,canonical_or_superseded_by,proposed_path,
reason,link_or_code_risk,recommended_action
```

### 5. 새 현재상태 초안

```text
docs/reviews/incoming/PROJECT_CURRENT_STATE_REFRESH_DRAFT_20260801.md
```

50–120줄 안에서 연구 목적, 확정 방법, 실제 완료, 실제 미완료, 현재 실행 상태,
다음 명령 하나, 금지사항, 정본 링크만 담아라. 역사 서술은 넣지 마라.

## F. 금지 작업

이번 리뷰에서는 다음을 하지 마라.

- 코드·config·기존 문서 수정
- 기존 파일 이동·이름 변경·삭제
- D:/E:/H: 파일 생성·복사·압축·삭제
- MFA, 전수 CSV, KOINA, wav2vec2 실행
- 제외 후보 자동 승인
- Git commit/push
- 새 종속성 설치 또는 인터넷 검색

읽기 전용 검사와 위 다섯 review 결과 파일 작성만 허용한다. 사실을 확인할 수 없으면
추정으로 채우지 말고 `evidence_missing`으로 표시하라.

---
