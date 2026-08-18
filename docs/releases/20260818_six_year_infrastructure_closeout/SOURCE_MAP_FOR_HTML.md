# 외부 HTML 제작용 source map

이 문서는 다른 AI 도구 또는 공동연구자가 저장소에서 무엇을 정본으로 읽고,
어떤 문서를 역사 자료로만 취급해야 하는지 정한다. 파일 수정 시각이나 가장 긴
문서를 기준으로 정본을 추측하지 않는다.

## 1. 사실 우선순위

상충하는 숫자·버전·상태가 있으면 다음 순서를 따른다.

1. 최종 release의 machine-readable manifest와 독립 감사
2. 현재 상태 정본과 현행 runbook
3. 이 closeout의 해설 문서
4. 개별 날짜의 decision/result 문서
5. `docs/archive`와 과거 review 문서

역사 문서는 오류와 설계 변화의 근거로는 사용할 수 있지만, 현행 명령·정본 수량을
정하는 근거로 사용하면 안 된다.

## 2. 반드시 읽을 정본

### 2.1 범위·회계·같은 방법론

- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/README.md`
- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/BASE_RELEASE_MANIFEST_2020_2025.json`
- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/QA_REPORT.json`
- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/CROSS_YEAR_CONTRACT_AUDIT.json`
- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/METHODS_A_C.md`
- `outputs/reports/AUDIT_db_v1_release_prep_ac_20260815.json`

여기서 5,103,356 원천 발화, 4,286,046 정렬, 95,860 MFA 전 기술 후속,
3,086 MFA 후 기술 후속, 718,364 발음 후속을 가져온다.

### 2.2 수동 recovery와 active view

- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818/README.md`
- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818/ACCOUNTING.json`
- `outputs/releases/nikl_dialogue_research_db_v1_active_view_contract_v1_20260818/README.md`
- `outputs/reports/AUDIT_db_v1_rc1_recovery_sidecar_20260818.json`
- `outputs/reports/AUDIT_db_v1_active_view_contract_20260818.json`

RC1은 6개년 본체를 대체하는 새 전체 DB가 아니라 55행 상태·16행 curated pointer를
가진 append-only sidecar다.

### 2.3 검색·후보·TextGrid 연결

- `docs/decisions/RESULT_db_v1_target_manifest_pilot_20260818.md`
- `docs/decisions/RESULT_db_v1_target_interval_link_pilot_20260818.md`
- `outputs/reports/AUDIT_db_v1_target_manifest_pilot_20260818.json`
- `outputs/reports/AUDIT_db_v1_target_interval_link_pilot_20260818.json`
- `docs/decisions/PLAN_n_insertion_B1_to_production_query_20260818.md`
- `outputs/approvals/APPROVAL_n_insertion_B1_revision_20260818.json`

후보 파일럿은 검색·자산·문맥 시간 연결 검증이다. 음운 현상 실현 결과로 쓰지
않는다. B1 승인은 개념 규칙 승인이고 6개년 production query 실행 승인이 아니다.

### 2.4 운영·환경·저장 구조

- `docs/environment/PROJECT_START_HERE.md`
- `docs/environment/PROJECT_CURRENT_STATE.md`
- `docs/environment/linguistics-research-environment-master-notes.md`
- `docs/RUNBOOK_production_2020_2025.md`
- `docs/DATA_LAYOUT.md`
- `docs/ASSETS_LEDGER.md`
- `config/paths.json`

공개 HTML에서는 로컬 절대경로를 설치 예시와 혼동하지 않게 표시한다. API key와
개인 Dropbox 경로는 공개하지 않는다.

### 2.5 이 closeout의 해설

- `docs/releases/20260818_six_year_infrastructure_closeout/README.md`
- `docs/releases/20260818_six_year_infrastructure_closeout/METHODS_RESULTS_LIMITATIONS.md`
- `docs/releases/20260818_six_year_infrastructure_closeout/CHRONOLOGY_AND_DECISIONS.md`
- `docs/releases/20260818_six_year_infrastructure_closeout/LESSONS_AND_REUSE_GUIDE.md`
- `docs/releases/20260818_six_year_infrastructure_closeout/CLEANUP_LEDGER.md`
- `outputs/reports/SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json`

## 3. 로컬 대형 자산과 GitHub 공개 자산 구분

| 범주 | 내부 정본 | GitHub 공개 방식 |
|---|---|---|
| 원 음성·전사 | 허가된 corpus drive | 재배포하지 않고 확보 방법·라이선스 설명 |
| 공통발음·MFA DB | D: release/model/DB | manifest·hash·생성 코드·작은 예시 |
| 6-tier TextGrid 4,286,046건 | D: `research_6tier` | schema·수량·비식별/허용 표본 |
| 검색층 5,103,356건 | D: morph/search release | schema·manifest·생성 코드·작은 예시 |
| RC0/RC1 JSON·MD | 프로젝트 `outputs/releases` | 그대로 공개 가능 여부를 라이선스 재확인 |
| 연구자 Dropbox 검토본 | 개인 검토 사본 | 외부 공개 금지 |

## 4. HTML이 반드시 보여줄 그림과 표

1. 원 JSON/WAV → 검색 CSV → 공통발음 → MFA DB/TextGrid → target manifest →
   수동 판정의 흐름도
2. 연도별 원천·정렬·기술 후속·발음 후속 표
3. 전체 회계식과 84% 정렬/나머지 후속의 의미
4. 6-tier의 이름·내용·오해 방지 표
5. RC0 base + RC1 sidecar + active view 구조
6. 실패 → exact-ID queue → 별도 recovery → 명시 Gate의 재개 흐름
7. 같은 corpus 재현과 다른 corpus 이식의 차이

## 5. 금지된 주장

- “6개년 전체가 MFA 정렬됐다.”
- “MFA phone이 실제 발음을 판정했다.”
- “718,364발화는 사용할 수 없다.”
- “ㄴ 삽입 실현을 자동으로 검출했다.”
- “RC1이 RC0 510만 행을 수정했다.”
- “AI가 연구를 자율적으로 수행했다.”
- “원 음성·전사를 GitHub에서 내려받을 수 있다.”
- “KOINA 또는 wav2vec/HuBERT 분석이 이미 전수 완료됐다.”

## 6. 권장 용어

| 사용할 표현 | 피할 표현 |
|---|---|
| 정렬 안전 본체 | 완벽하게 정렬된 전체 corpus |
| 발음 근거 후속 | 발음 오류 파일 |
| 기술 후속 exact-ID | 버린 파일 |
| 자동 보조층 | 정답 전사 |
| 연구자 실현 판정 | MFA 자동 판정 |
| append-only overlay | 원본 수정본 |
| 내부 release candidate | 공개 완성 DB |

## 7. 완료 검증 체크리스트

- 수량이 RC0 QA와 정확히 같은가?
- 81만 건도 전체 검색층에 남는다고 설명했는가?
- TextGrid가 있는 428만 건과 전체 510만 검색층을 구분했는가?
- 실제 실현 판정이 미완료임을 적었는가?
- Claude Code·Codex 보조와 연구자 책임을 함께 밝혔는가?
- archive를 현재 실행 지침처럼 인용하지 않았는가?
- 원자료 라이선스와 비공개 경로를 보호했는가?
- 실패와 보류를 재현성 장점으로 설명하되 성과를 과장하지 않았는가?
