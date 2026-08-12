# Codex 리밋·새 대화 뒤 프로젝트 연속성

최종 갱신: 2026-08-12 KST

이 절차는 새 계정을 만들기 위한 것이 아니다. 같은 계정에서 Codex 사용 한도가
초기화되기를 기다리거나 새 대화를 열어도, 로컬 계산과 연구 계약을 잃지 않고
이어가기 위한 절차다.

## 가장 중요한 원칙

1. Codex 대화가 멈춰도 별도 PowerShell에서 실행한 작업은 독립적으로 계속된다.
2. 실행 창을 닫거나 같은 명령을 다시 입력하기 전에 반드시 읽기 전용 상태판을
   확인한다.
3. `*.partial`, MFA DB, shard manifest, lock을 임의로 삭제하지 않는다.
4. 채팅 기억이 아니라 현재 파일·manifest·Git commit을 정본으로 사용한다.
5. 2020–2022 r2 완성본과 원본 WAV/CSV는 변경하지 않는다. r3는 release 전용
   경로에서만 생성한다.

## 현재 재개 checkpoint

2020·2021·2022 r3는 정렬 DB, 6-tier·동반표, 독립 전수 QC와 DB 재수출
24/24까지 완료해 동결했다. 2022 최종 `QC_STATE.json` checkpoint는
`7cf3af24c5da8f58126837742902495724f4dc69140a00b6ea6d162a9eda7c89`다.
이 세 연도의 runner·전수 수출·QC를 다시 실행하지 않는다. 새 대화의 다음 단계는
2022 marker/QC SHA를 검증하는 2022→2023 전환 Gate와 2023 한 연도 준비다.

## 새 대화에서 가장 먼저 할 일

다음 문서를 순서대로 읽는다.

1. `docs/environment/PROJECT_START_HERE.md`
2. `docs/environment/PROJECT_CURRENT_STATE.md`
3. `docs/RUNBOOK_production_2020_2025.md`
4. 이 문서

그 다음 아래 두 항목을 읽기 전용으로 확인한다.

```powershell
Set-Location "C:\Users\ari30\research\2026_summer_research"
git status --short
git log -3 --oneline
```

현재 단계가 pre-MFA 검색표라면 다음 상태판만 실행한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_production_year_pre_mfa_status.ps1" `
  -Year "2021"
```

상태 해석은 다음과 같다.

- `running`: 기존 PowerShell을 그대로 두고 모니터링한다.
- `complete`: annual manifest와 source contract를 독립 재검증한 뒤 다음 gate로
  진행한다.
- `interrupted_or_paused_resumable`: 완료 shard를 보존하고 partial 원인을 먼저
  조사한다. 자동 삭제·처음부터 재실행을 하지 않는다.
- `not_started`: RUNBOOK의 현재 한 단계만 실행한다.

r2 역사·복구 단계에서는 `show_mfa_year_queue_status.ps1`를 쓴다. 현재 r3
연도 MFA 단계에서는 다음 release 전용 읽기 상태판만 사용한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_mfa_r3_year_status.ps1" `
  -Year 2023
```

`ready_not_started`면 RUNBOOK 3.0의 명령을 한 번 실행한다.
`corpus_materializing_or_mfa_starting` 또는 `mfa_running`이면 기존 PowerShell을
그대로 둔다. 중단 상태면 corpus·temp·DB를 삭제하지 않고 같은 명령으로 한 번만
재개한다.

## 2026-08-07 r3 공통발음 후보 단계

현재 r2 연도 MFA는 차단돼 있다. r3 정본을 만들기 위한 Jamo G2P 후보 실행
상태는 다음 읽기 전용 상태판으로 확인한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_common_pron_mfa_r3_g2p_status.ps1"
```

- `prepared_not_started`: 310,605개·13 shard 입력만 준비됐고 G2P는 시작 전이다.
- `g2p_running`: 별도 PowerShell 계산이 진행 중이므로 창과 lock을 그대로 둔다.
- `interrupted_resumable`: 같은 실행 명령을 사용하면 완료 보고서가 있는 shard는
  건너뛰고 중단 shard만 다시 계산한다.
- `success_candidates_not_selected`: 후보 생성만 끝난 역사적 상태다. 현재는 이후
  Stage 19–21과 연구자 단계적 범위 승인까지 완료됐으며, 다음 단계는 외부
  workflow 리뷰와 r3 전용 release/runner 구현이다.

부분 `.dict`만 보고 완료로 판단하지 않는다. 입력·출력·동결 모델 SHA가 묶인
shard 보고서가 있어야 완료다. r3 실행 명령은
`C:\Users\ari30\research\2026_summer_research\scripts\
run_common_pron_mfa_r3_g2p_candidates.ps1`이며, 새 대화에서는 먼저 상태판을
실행한 뒤에만 재개한다. 사용자에게 주는 명령은 현재 PowerShell 위치와 무관한
절대경로를 사용한다.

### 2026-08-08 agreement Gate 이후 재개점

G2P 13 shard는 완료됐으며 다시 실행하지 않는다. 이어서 수행한 ordered
broad-Roman 전수 비교와 읽기 전용 감사도 완료됐다.

```text
대상 exact 96,284 / mismatch 214,321
source exact 출현 1,676,283 / mismatch 출현 2,796,609
canonical selection false / adoption false / annual MFA false / TextGrid 변경 false
```

agreement mismatch 214,321 target과 215,184 source형의 ordered edit 진단도
완료됐다. source 불일치 출현 중 60.310%는 길이·활음의 model 표상 동등성
후보이고 38.447%는 실질 차이 후보다. 2,625개 패턴은 출현의 92.620%를
포괄하는 56행 결정표로 축약됐으나 자동 승인·canonical 선택은 하지 않았다.

새 대화에서는
`docs/decisions/RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`와
`outputs/reports/AUDIT_common_pron_r3_g2p_mismatch_diagnostics_20260808.json`을
먼저 확인한다. 상태판의 `success_candidates_not_selected`를 보고 G2P와
agreement Gate를 재실행하지 않는다. 다음 일은 반복 패턴의 model 표상 계약과
규칙 projection 정책을 코드로 고정한 뒤 canonical 선택·adoption Gate를 만드는
것이다. 새 대규모 청취 검토로 돌아가지 않는다.

### 2026-08-08 model projection 이후 재개점

위 다음 단계 가운데 model 단위화·exact 문맥 projection 후보 생성과 독립 감사는
이미 완료됐다. 다시 실행하지 않는다.

```text
target 후보 가능 264,906 / 보류 45,699
출현 후보 가능 3,744,243 / 보류 728,649
source 사전 근거 동시 일치 후보 5,948형
canonical selection false / adoption false / annual MFA false / TextGrid 변경 false
```

정본 manifest는 `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
06_model_projection_candidates\PROJECTION_CANDIDATES_MANIFEST.json`이고, 독립
감사는 `outputs/reports/AUDIT_common_pron_r3_projection_candidates_20260808.json`
이다. 새 대화에서는 이 둘과
`docs/decisions/RESULT_common_pron_r3_model_projection_candidates_20260808.md`를
먼저 확인한다. 다음 일은 projection 재실행이나 56행 전수 청취가 아니라
canonical 선택 우선순위·zero-fallback·사전 projection·adoption Gate 구현이다.

### 2026-08-08 selection-readiness 이후 재개점

881,237형 전수 readiness와 독립 감사도 완료됐다. 정본은
`D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
07_canonical_selection_readiness\SELECTION_READINESS_MANIFEST.json`이다.

```text
candidate 준비 749,779형 / zero-fallback 보류 131,434형
candidate 출현 coverage 93.289%
canonical selection false / adoption false / MFA false / TextGrid 변경 false
```

새 대화에서 같은 07 행렬이나 Jamo G2P를 다시 실행하지 않는다. 다음 후보 단계는
canonical exact-rule 382,891형 전역 donor projection이며, 기존 06 후보와의
변경 비교를 반드시 남긴다.

### 2026-08-08 전역 donor·09 readiness 이후 재개점

위 전역 donor 단계까지 완료됐다. 정본은 다음 두 manifest다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  08_global_projection_candidates\GLOBAL_PROJECTION_MANIFEST.json
  09_global_selection_readiness\SELECTION_READINESS_MANIFEST.json
```

```text
candidate 준비 752,270형 / zero-fallback 보류 128,932형
target projection 미해결 43,428형 / no-rule 미대상 85,504형
canonical selection false / adoption false / MFA false / TextGrid 변경 false
```

08·09 독립 감사가 모두 `passed_read_only`다. 같은 G2P, 06 projection, 07
readiness를 다시 실행하지 않는다. 다음은 no-rule 85,504형을 별도 신분으로
다루는 candidate-only 계약 설계이며, 곧바로 최종 선택하거나 MFA를 실행하지
않는다. 상세 결과는
`docs/decisions/RESULT_common_pron_r3_global_projection_v2_20260808.md`다.

### 2026-08-08 no-rule 85,504형 특성화 이후 재개점

no-rule 보류형의 전수 특성화와 독립 감사까지 완료됐다. 정본은 다음이다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  10_no_rule_hold_characterization\NO_RULE_HOLD_CHARACTERIZATION_MANIFEST.json
outputs/reports/AUDIT_common_pron_r3_no_rule_hold_characterization_20260808.json
outputs/reports/REPORT_common_pron_r3_no_rule_hold_characterization_20260808.json
```

```text
85,504형 / 1,140,107회 / 모두 완성형 한글
canonical selection false / adoption false / MFA false / TextGrid 변경 false
```

새 대화에서 stage 10, 같은 G2P, 08 projection, 09 readiness를 다시 실행하지
않는다. `no_rule`은 언어학적으로 규칙이 없다는 뜻이 아니다. 상세 결과는
`docs/decisions/RESULT_common_pron_r3_no_rule_hold_characterization_20260808.md`다.

### 2026-08-08 규칙·MFA phone coverage 감사 이후 재개점

stage 11 읽기 전용 감사와 독립 재계산이 완료됐다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  11_rule_phone_coverage_audit\RULE_PHONE_COVERAGE_MANIFEST.json
outputs/reports/AUDIT_common_pron_r3_rule_phone_coverage_20260808.json
outputs/reports/REPORT_common_pron_r3_rule_phone_coverage_20260808.json
```

```text
all optional place assimilation: 36,568형 / 525,747회
non-overlap all exact frozen dictionary: 811형 / 229,177회
some optional only: 82형 / 16,271회
unresolved: 48,043형 / 368,912회
candidate selection false / adoption false / MFA false / TextGrid 변경 false
```

첫 stage 11 결과는 비일대일 phone 포함을 해결 사유로 과잉분류해
`archive_intermediate\11_rule_phone_coverage_audit_v1_overbroad_noninjective_20260808`
로 이동했다. 수정본은 비일대일성을 경고 표지로만 쓴다. 새 대화에서 stage 11을
다시 실행하지 않는다. stage 12는 검증된 37,379형을 정렬용 candidate-only로
추가했고 독립 감사를 통과했다. 수의적 위치동화를 의무 표준발음 규칙에 넣지
않고, phone을 실제 실현 또는 확정 음소로 해석하지 않는다. 정본 결과는
`docs/decisions/RESULT_common_pron_r3_rule_phone_coverage_audit_20260808.md`다.

### 2026-08-08 selection-readiness v2 이후 재개점

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  12_selection_readiness_v2\SELECTION_READINESS_V2_MANIFEST.json
outputs/reports/AUDIT_common_pron_r3_selection_readiness_v2_20260808.json
```

```text
candidate ready: 789,649형 / 26,952,517회
zero-fallback hold: 91,553형 / 894,388회
policy decision: 35형 / 163회
canonical selection false / adoption false / MFA false / TextGrid 변경 false
```

새 대화에서 stage 12 이하를 다시 실행하지 않는다. 잔여 패턴 요약도
`outputs/reports/REPORT_common_pron_r3_readiness_v2_residual_priorities_20260808.json`
으로 완료됐다. 다음은 frozen 기본사전의 단어·음절·이차조음 문맥 donor를 만들고
기존 donor와 합의·충돌을 읽기 전용으로 대조하는 것이다. 정본은
`docs/decisions/RESULT_common_pron_r3_selection_readiness_v2_20260808.md`다.

### 2026-08-08 문맥 donor·selection-readiness v3·phone 변경 감사 이후 재개점

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  13_contextual_dictionary_donor_audit\CONTEXTUAL_DICTIONARY_DONOR_AUDIT_MANIFEST.json
  14_selection_readiness_v3\SELECTION_READINESS_V3_MANIFEST.json
  15_unanimous_phone_change_audit\UNANIMOUS_PHONE_CHANGE_AUDIT_MANIFEST.json
  16_morph_context_evidence\MORPH_CONTEXT_EVIDENCE_MANIFEST.json
  17_attested_full_sequence_projection\ATTESTED_FULL_SEQUENCE_PROJECTION_MANIFEST.json
  18_selection_readiness_v4\SELECTION_READINESS_V4_MANIFEST.json
outputs/reports/AUDIT_common_pron_r3_contextual_dictionary_donor_20260808.json
outputs/reports/AUDIT_common_pron_r3_selection_readiness_v3_20260808.json
outputs/reports/AUDIT_common_pron_r3_unanimous_phone_change_20260808.json
outputs/reports/AUDIT_common_pron_r3_morph_context_evidence_20260808.json
outputs/reports/AUDIT_common_pron_r3_attested_full_sequence_projection_20260808.json
outputs/reports/AUDIT_common_pron_r3_selection_readiness_v4_20260808.json
```

```text
candidate ready: 795,790형 / 27,043,061회
zero-fallback hold: 85,412형 / 803,844회
new phone-unchanged secondary candidates: 6,141형 / 90,544회
unanimous but phone-change hold classified: 4,453형 / 72,030회 / 4,900 issue
Stage 16 exact surface linked: 68,285회
Stage 16 safe morph/POS linked: 60,292회
Stage 17 attested full-sequence candidate-only: 14형 / 200회
readiness v4 candidate: 795,804형 / 27,043,261회
readiness v4 zero-fallback hold: 85,398형 / 803,644회
canonical selection false / adoption false / MFA false / TextGrid 변경 false
```

Stage 19–21까지 완료됐으므로 새 대화에서 Stage 13–21을 다시 실행하지 않는다.
정본은 다음이다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\19_pre_adoption_routing\PRE_ADOPTION_ROUTING_MANIFEST.json
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\20_safe_body_candidate\SAFE_BODY_CANDIDATE_MANIFEST.json
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\21_targeted_regression_2022\TARGETED_REGRESSION_AUDIT.json
outputs/reports/AUDIT_common_pron_r3_adoption_readiness_20260808.json
```

safe body는 4,384,992발화, follow-up은 718,364발화다. Stage 20 후보 사전은
795,804형·796,061변이이며 역사적 `NOT_ADOPTED` 상태로 보존한다. 이를 byte-exact
물질화한 `common_pron_mfa_r3_20260809` release는 production Gate에서 채택됐다.
연구자는 표적 네 발화의 경계와
2020–2025 pronunciation-safe pool의 정렬 가능 집합 전체 신규 r3 정렬을
승인했다. 기술적 제외는 exact-ID로 별도 회계한다. r2 interval은 최종 r3에
재사용하지 않으며 follow-up은 exact-ID 별도 shard로 보존한다. 외부 workflow
리뷰, r3 전용 release/runner, 정책 감사 v2와 2020 preflight 18/18은 완료됐다.
이 단락은 r3 채택 당시의 근거다. 이후 2020–2022 신규 r3 정렬·6-tier·독립
QC가 완료됐다. 2022→2023 전환 Gate와 2023 조합검색·연구 DB·runner preflight도
통과했다. Stage 13–21이나 2020–2022 runner를 다시 실행하지 않고, 현재는 2023
exact-ID 494,580건의 장시간 runner만 시작한다. r2 label 제자리 치환은 계속
금지한다.

## 새 대화에 붙일 최소 프롬프트

```text
C:\Users\ari30\research\2026_summer_research의 작업을 이어가자.
먼저 AGENTS.md와 docs/environment/PROJECT_START_HERE.md,
PROJECT_CURRENT_STATE.md, docs/RUNBOOK_production_2020_2025.md,
CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md를 읽어라.
2020–2022 r3 완성본과 원본 WAV/CSV를 변경하지 말고, 현재 실행 프로세스·lock·
manifest를 읽기 전용으로 확인한 뒤 재시작 여부를 판단하라. 2022 QC checkpoint와
통과한 2022→2023 Gate를 보존하고, 2023 marker/DB가 없으면 이미 통과한 preflight의
exact-ID 494,580건 runner부터 진행하라. 현재 Git commit과 실제 D: 상태를 대화
기억보다 우선하라.
```

## 계정 한도에 관한 운영 원칙

OpenAI 안내상 Codex 사용 한도는 플랜에 따라 다르며, 한도 도달 뒤에는 사용
페이지에 표시되는 크레딧·리셋·업그레이드 선택지 또는 한도 초기화를 따른다.
새 계정 생성은 이 프로젝트의 재개 절차가 아니다.

공식 안내:
<https://help.openai.com/en/articles/11369540-codex-in-chatgpt-faq>
