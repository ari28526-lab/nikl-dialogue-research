# 2020–2025 연구 인프라 전수 생산 RUNBOOK

최종 갱신: 2026-08-08 KST

이 문서는 현재 생산 순서의 정본이다. 2021 완료 전의 상세 명령·시행착오는
`docs/archive/pre_2022_refresh_20260806/RUNBOOK_production_2020_2025_pre_2022_20260806.md`에
보존한다.

> **2026-08-07 발음 입력 안전 중단:** `common_pron_mfa_r2_20260728`은 기존
> 규칙 예상 발음층을 실제 MFA 입력 사전에 일관되게 전달하지 않았음이 2022
> 연구자 표본과 881,237 표면형 전수 감사에서 확인됐다. r2 산출물은 삭제·수정하지
> 않고 방법론 증거로 보존하되, r2를 이용한 새 MFA와 2023 진입은 금지한다.
> 현재 다음 단계는 `config/common_pronunciation_resource_contract_v3_draft.json`에
> 따른 단일 발음 선택표·r3 사전의 채택이다. 채택 뒤 2020–2022는 발음 변이가
> 달라진 화자/세션 적응 단위만 재정렬하고, 완전히 동일한 단위는 엄격한 동등성
> 증명 아래 재사용한다. 2023–2025는 r3로 한 번만 정렬한다. 이미 수행한
> 광범위한 파일·tier 검토와 2022 24표본
> 청취는 반복하지 않고 표적 회귀 자료로 재사용한다.

## 1. 완료 산출물

연도마다 다음 core를 완성한다.

1. pre-MFA `morph_search.v3` 7표와 source contract
2. 채택된 단일 공통 발음 계약 기준 MFA
3. 보존 DB와 exact-ID 미정렬 회계
4. 6-tier TextGrid
5. post-MFA gzip 동반표 4개
6. 입력·정렬·출력·DB 동등성 감사
7. 한 번의 연구자 인프라 표본 Gate
8. 공통 대화 음원 품질층과 연도별 동반표 결합

이후 파생층으로 우리말샘 occurrence·규칙/사전/MFA 비교표와 선택적 7번째
`pron_reference_utt` tier를 만든다. 파생층은 실제 음운 실현 판정이 아니며 다음
연도 MFA를 미루기 위한 새 gate가 아니다.

## 2. 절대 규칙

- 2020 Gate B의 광범위한 사람 검토를 반복하지 않는다. 기존 결과는 r3 표적
  회귀검사 입력으로 재사용한다.
- 기존 2020–2022 r2 MFA·DB·TextGrid·동반표는 읽기 전용 비교 증거로 보존한다.
- `common_pron_mfa_r2_20260728`로 새 MFA를 실행하지 않는다. 프로젝트 release
  gate가 fail-closed로 차단한다.
- r3 채택 뒤 2020–2022는 LAB token별 r2/r3 발음 변이 집합을 전수 비교한다.
  하나라도 달라진 화자/세션 적응 단위만 전체 재정렬한다. 모두 같은 단위는 WAV·
  LAB·모델·설정·기존 QC와 표본 경계 동등성까지 확인한 뒤 재사용한다.
- 2023–2025는 같은 acoustic phone inventory와 r3 계약으로 한 번만 정렬한다.
  구 TextGrid의 phone label만 바꾸는 방식은 어떤 경우에도 금지한다.
- 한 번에 한 연도만 실행한다.
- 직전 연도 연구자 Gate와 당해 연도 source contract가 없으면 시작하지 않는다.
- 승인 제외·post-MFA 미정렬은 삭제하지 않고 ID·사유·계약을 보존한다.
- 겹침·소음·잘림 의심처럼 정렬 가능한 품질 문제는 MFA 본체에서 자동 제외하지
  않는다. 정렬 결과를 보존하고 연구자 승인 뒤 `analysis_only`로 표시한다.
- `<=44B`, 대응 불명, 불가능 시간처럼 정렬 자체가 성립하지 않는 항목만
  `alignment_and_analysis` 계약으로 본체에서 분리한다.
- 실패 시 전체 연도를 지우지 않고 DB·세션·stage checkpoint에서 재개한다.
- 장시간 명령을 주기 전에 PowerShell 안전·5.1 검사와 가능한 preflight를 먼저
  통과시킨다.

## 3. 현재 시작점

```text
2020–2022 r2 계산·export·기계 감사·기존 연구자 검토 보존
  → 2022 표본에서 MFA 발음 입력 불일치 발견
  → 881,237 표면형 r2 규칙 일관성 전수 감사
  → r2 신규 실행 fail-closed 차단
  → G2P–규칙 mismatch 전수 진단·반복 패턴 축약 완료
  → model 표상·exact 문맥 projection 후보·독립 감사 완료
  → 881,237형 selection-readiness·독립 감사 완료
  → canonical exact donor 전역 projection·비교  ← 현재
  → 단일 canonical 선택 계약·zero-fallback·adoption Gate
  → r3 채택
  → 2020–2022 영향 inventory·변경 세션 delta 재정렬
  → 2023–2025 동일 r3 계약으로 최초 정렬
```

### 3.1 r3 후보 생성 완료 checkpoint

2026-08-08 현재 canonical inventory 881,237형, exact-Roman donor 후보 346형,
규칙 목표형 310,605개·13 shard의 G2P 1-best 생성과 읽기 전용 독립 감사가
완료됐다. no-path·`spn`·중복·입력 밖 key·acoustic inventory 밖 phone은 모두
0이다. 이 출력은 최종 발음 선택이 아니며 독립 규칙 Roman과 정확히 일치하는
후보만 다음 단계로 넘긴다.

후보 생성 완료 상태는 다음 읽기 전용 명령으로 확인한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_common_pron_mfa_r3_g2p_status.ps1"
```

재현·국소 재개용 실행기는
`C:\Users\ari30\research\2026_summer_research\scripts\
run_common_pron_mfa_r3_g2p_candidates.ps1`이다. 완료 SHA 보고서가 있는 shard만
재사용하므로 중단 뒤 같은 명령으로 국소 재개한다. 이 단계가 끝나도 최종 사전
adoption이나 연도별 MFA로 자동 진입하지 않는다.

완료 증거는
`docs/decisions/RESULT_common_pron_r3_g2p_candidate_phase_20260808.md`와
`outputs/reports/AUDIT_common_pron_mfa_r3_g2p_candidates_20260808.json`이다.
이 실행기는 다시 돌리지 않는다. 후속 exact broad-Roman Gate의 완료 상태는
아래 checkpoint를 따른다.

### 3.2 r3 G2P–규칙 Roman 전수 Gate 완료 checkpoint

2026-08-08에 310,605개 후보 phone을 고정 broad-Roman 단위로 바꾸고 독립 규칙
목표와 순서·길이까지 exact 비교했다. 대상형 exact는 96,284개(30.999%),
mismatch는 214,321개(69.001%)다. source 기준 사전 근거 일치 exact는 3,078형,
사전 충돌 exact는 14형, 독립 근거 없는 exact는 94,134형, mismatch는
215,184형이다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
04_g2p_rule_agreement_gate\G2P_AGREEMENT_GATE_MANIFEST.json
```

별도 감사 보고서
`outputs/reports/AUDIT_common_pron_r3_g2p_agreement_gate_20260808.json`은
`passed_read_only`다. `EVIDENCE_SAMPLE.csv` 75행은 승인표가 아니므로 이
checkpoint에서 사용자 검토를 요구하지 않는다.

다음 단계는 별도 canonical 선택 계약이다. exact 후보도 자동 선택하지 않고 사전
근거와 형태음운 보류를 보존한다. adoption manifest가 통과하기 전에는 r3 MFA,
TextGrid materialization, 기존 r2 label 치환을 시작하지 않는다.

### 3.3 r3 G2P mismatch 전수 진단 완료 checkpoint

agreement mismatch 214,321 target·215,184 source형에 대해 후보–규칙 Roman의
순서 보존 편집, acoustic-model phone의 장음·이차조음 표상, 사전·형태소·연도
근거를 결합했다. source 불일치 출현 2,796,609회 중 표상 동등성 후보는
1,686,625회(60.310%), 실질 차이 후보는 1,075,211회(38.447%)다.

표상 동등성 후보도 자동 승인하지 않는다. 전체 2,625개 반복 패턴 중 빈도 상위·
각 class 대표·회귀 패턴 56행이 2,590,212회(92.620%)를 포괄한다. 이 결정표는
adoption 승인표가 아니며, 지금 사용자에게 21만여 개 어휘나 56행 전체 청취를
요구하지 않는다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
05_g2p_mismatch_diagnostics\G2P_MISMATCH_DIAGNOSTICS_MANIFEST.json

outputs/reviews/common_pron_r3_g2p_mismatch_diagnostics_20260808/
PATTERN_DECISION_TABLE.csv
```

독립 감사 보고서는
`outputs/reports/AUDIT_common_pron_r3_g2p_mismatch_diagnostics_20260808.json`이며
`passed_read_only`다. 다음 구현은 반복 패턴에서 model 표상 동등성 계약과
규칙·사전 projection 정책을 먼저 코드화하고, 자동으로 해소하지 못한 소수만
연구자 판단으로 올리는 canonical 선택 단계다.

### 3.4 r3 model 표상·exact 문맥 projection 완료 checkpoint

좁은 model 단위화 관계와 exact-agreement donor 문맥을 코드 계약으로 고정했다.
장음 및 `Y/W` 흡수만 기술적 단위화 관계로 인정하고, substitution·candidate-only·
기타 rule-only 차이는 자동 승인하지 않았다. 실질 차이는 최소 2개 target type과
phone 완전 일치를 갖는 동일 문맥에서만 projection했다. mode·첫 변이·수기 phone·
기본사전 fallback은 금지했다.

결과는 target 310,605개 중 후보 가능 264,906개(85.287%), 보류 45,699개
(14.713%)다. 출현 기준 후보 가능은 3,744,243회(83.710%)다. source에서
projection과 독립 사전 근거가 함께 일치한 것은 5,948형·349,689회이며, 아직
최종 선택은 아니다. `있는`은 model 장음 단위화 후보, `있지`는 실제 donor 지지
부족으로 보류됨을 회귀검사했다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
06_model_projection_candidates\PROJECTION_CANDIDATES_MANIFEST.json

outputs/reports/AUDIT_common_pron_r3_projection_candidates_20260808.json
outputs/reviews/common_pron_r3_projection_residual_handoff_20260808.csv
```

독립 감사는 exact donor context와 798개 사용 evidence를 포함해 target/source
전수를 재계산했고 `passed_read_only`다. 잔여 1,799패턴을 모두 검토하지 않고
95.136% 출현과 각 범주 대표를 포괄하는 56행 handoff로 축약했다. 이 표는
승인표가 아니다.

다음 한 단계는 canonical inventory에 모든 근거를 연결한 최종 선택 우선순위와
zero-fallback 계약을 구현하는 것이다. 선택 phone 누락·`spn`·inventory 밖 phone
0, 표적 회귀, 단일 adoption Gate가 모두 통과하기 전에는 MFA를 시작하지 않는다.

### 3.5 r3 전수 selection-readiness 완료 checkpoint

canonical 881,237형에 r2·surface donor·사전·06 projection을 한 행씩 연결해
candidate 준비 749,779형(출현 93.289%), 복수 변이 정책 24형, zero-fallback
보류 131,434형을 분리했다. 독립 감사는 전수 route와 phone 관계를 다시 계산해
`passed_read_only`로 통과했다.

보류 중 no-rule 실질 불일치 85,504형의 83,922형은 이미 같은 동결 Jamo G2P
1-best 출처다. 같은 G2P 장시간 실행을 반복하지 않는다. 다음 단계는 06의 제한된
96,284 exact target donor 대신 canonical 382,891 exact-rule 형을 donor로 사용한
projection v2와 기존 후보 유지·변경 비교다. 상세 근거는
`docs/decisions/RESULT_common_pron_r3_selection_readiness_20260808.md`를 따른다.

## 4. 2021 Gate 종료 — 완료

현행 2021 생산 queue는 다음이다.

```text
mfa_checkpoint_qc_2021_20260805_retry1
```

정본 검토 파일:

```text
outputs/reviews/
  mfa_production_2021_mfa_checkpoint_qc_2021_20260805_retry1/
    03_RESEARCHER_REVIEW.csv
    03_RESEARCHER_REVIEW_MANIFEST.json
```

연구자는 1–20번과 21–24번 총 24개 표본을 확인했다. 승인 절차는 CSV 수동
편집을 요구하지 않는다. 승인자·명시 문장·정확한 행 수를 받은 뒤 아래 단일
명령이 원 pending CSV를 바이트 동일 보존하고, identity를 검증한 뒤 승인 CSV와
결정·승인 JSON을 원자적으로 만든다.

모든 행이 기록된 뒤에만 다음 승인기를 사용한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\approve_production_year_sample_review.ps1" `
  -Year "2021" `
  -ApprovedBy "ari30" `
  -ApprovalStatement "2021 생산 표본 24개를 직접 확인했으며 연결·6-tier·정렬·검색 정보가 대체로 적절함을 승인한다. 실제 음운 실현 판정은 수행하지 않았다." `
  -ExpectedRowCount 24 `
  -ExecutionQueueId "mfa_checkpoint_qc_2021_20260805_retry1"
```

이 명령은 연구자 결정을 기록할 뿐 자동으로 승인 여부를 추론하지 않는다. 같은
인자로 재실행해도 승인 CSV·원 pending archive SHA가 바뀌지 않는다.

승인 보고서 생성 뒤 다음 읽기 전용 Gate가 `passed`여야 한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\preflight_production_next_year_gate.ps1" `
  -PriorYear "2021" `
  -ExecutionQueueId "mfa_checkpoint_qc_2021_20260805_retry1"
```

2021은 2026-08-06에 이 Gate를 실패 검사 0으로 통과했다. Gate는 일반
`direct_db_research_6tier_v1`과 동일 schema의 checkpoint-resume 실행 mode를
함께 인정하고, 보존 DB 완료는 같은 계약의 `direct_db_ready` marker로 확인한다.

## 5. 2022 post-MFA 완료 절차

2022 r2 MFA 계산은 완료됐고 `D:\mfa_tmp\2022\2022.db`를 보존했다. 활성 LAB
865,128개 중 864,690개가 정렬됐으며 interval이 없는 438개는 exact-ID 검토
집합이다. 이 r2 DB에서 export·검토를 반복하지 않는다. r3가 채택되면 기존 DB를
수정하지 않고 별도 경로에서 발음 변이가 달라진 적응 단위만 재정렬한다. 전부
동등한 단위는 계약·QC·표본 경계 동등성 증명 뒤 최종 index로 재사용한다.

1. 438개와 aligned control의 연결·구조·음향 근거표를 확정했다.
2. 연구자는 438건의 기술적 미정렬 exact-ID 범위를 명시 승인했다.
3. 승인 materialization과 결합 승인 preflight가 통과했다.
4. 보존 DB에서 direct export를 재개한다.
5. 6-tier·동반표·독립 전수 감사·한 번의 연구자 표본 Gate를 완료한다.
6. 품질 플래그는 동반표에 결합하되 실제 실현 여부를 자동 판정하지 않는다.

2026-08-07 실행 queue
`mfa_r2_prod_safe_body_2022_20260806_postmfa`는 보존 DB를 재사용해 6-tier
864,690개와 동반표 4종을 생성했다. 독립 전수 감사는 coverage 100%, hard
failure 0, DB 재수출 표본 semantic·byte 24/24 일치로 통과했다. 공식 연구자
24표본도 검토됐고 그 과정에서 발음 입력 불일치가 발견됐다. 따라서 이 결과는
r3 표적 회귀 입력이며 r2 최종 승인 Gate로 더 진행하지 않는다.

재개 명령은 `resume_year_export_after_post_mfa_review.ps1`을 사용한다. 이 명령은
기존 1,231건과 새 438건을 결합한 계약을 만든 뒤 같은 `direct_db_ready` DB에서
export부터 시작하도록 만든 역사적 r2 복구 명령이다. 현재 발음 Gate가 닫혔으므로
새 실행에 사용하지 않는다.

실행 queue ID와 장시간 명령은 위 검사 직후 현재 값으로 고정해 사용자에게 한 줄로
제공한다. 문서에 날짜가 지난 queue ID를 미리 복사해 두지 않는다.

## 6. 연도별 반복 절차

2020–2025 r3는 다음 순서만 반복한다.

```text
직전 연도 Gate
  → 당해 morph_search.v3/source contract
  → 공통 음원 구조 감사·음향 표본·<=44B 전수 inventory
  → 승인 제외·LAB·모델 preflight
  → MFA·보존 DB
  → post-MFA exact-ID 회계
  → 6-tier·동반표
  → 독립 전수 감사·DB 표본
  → 연구자 표본 1회
  → 다음 연도 Gate
```

2023의 승인 제외 103,930건은 이미 결정된 안전 본체 계약이다. main MFA에 억지로
섞지 않고 후속 회수 shard와 계속 분리한다. 2023의 header-only WAV 75건은 이
승인 집합에 전부 포함돼 있으므로 같은 후보 승인을 반복하지 않는다. 2024·2025는
전수 `<=44B` WAV가 0건이다. 구조 겹침과 noise proxy는 자동 제외가 아니라
동반표의 검토 열이다.

## 7. 발음 참조 파생층

각 연도 6-tier 뒤 다음을 같은 계약으로 생성한다.

1. 형태소 occurrence–사전 group 연결표
2. 원 표기 어절 규칙/사전/MFA 비교표
3. 발화 index
4. 필요 시 7-tier backfill

정본은 `docs/RUNBOOK_pronunciation_reference_layer_2020_2025.md`다. 2020과
2022–2025의 물리적 7-tier 전수 backfill은 core MFA와 D: I/O가 겹치지 않는
시간에 수행하며 다음 연도 진입을 막지 않는다.

## 8. 사용자에게 요청하는 경우

사용자 행동은 다음 두 경우로 제한한다.

- 공식 표본 중 실제로 남은 소수 행의 WAV·TextGrid 확인 또는 정확한 exact-ID
  기술 제외 집합의 명시 승인
- 안전검사와 preflight가 통과한 장시간 PowerShell 시작

이미 승인한 제외 범주, 통과한 표본, 완료 연도는 반복 검토하지 않는다.
