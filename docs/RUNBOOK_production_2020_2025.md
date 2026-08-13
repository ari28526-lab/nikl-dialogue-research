# 2020–2025 연구 인프라 전수 생산 RUNBOOK

최종 갱신: 2026-08-13 KST

이 문서는 현재 생산 순서의 정본이다. 2021 완료 전의 상세 명령·시행착오는
`docs/archive/pre_2022_refresh_20260806/RUNBOOK_production_2020_2025_pre_2022_20260806.md`에
보존한다.

> **2026-08-09 r3 production Gate 개방:** `common_pron_mfa_r2_20260728`은 기존
> 규칙 예상 발음층을 실제 MFA 입력 사전에 일관되게 전달하지 않았음이 2022
> 연구자 표본과 881,237 표면형 전수 감사에서 확인됐다. r2 산출물은 삭제·수정하지
> 않고 방법론 증거로 보존하되, r2를 이용한 새 MFA와 2023 진입은 금지한다.
> Stage 19 발화 라우팅과 Stage 20 후보 사전 감사, Stage 21 표적 회귀까지
> 완료됐다. 연구자는 표적 네 발화와 2020–2025 pronunciation-safe pool의
> 정렬 가능 발화를 r3로 새로 정렬하는 단계적 채택을 승인했다. 기술적 제외는
> exact-ID로 별도 회계하며 기존 r2 interval은 최종 r3에 재사용하지
> 않는다. 광범위한 파일·tier 검토와 2022 24표본 청취는 반복하지 않고 회귀
> 근거로 보존한다. 연구자 `ari30`은 체크리스트 1–7을 확인하고
> `common_pron_mfa_r3_20260809`의 단일 production release Gate와 2020 안전
> 본체 782,715발화를 승인했다. 이후 r3 사전과 형태소 검색 CSV 사이에 발화·어절
> occurrence 연결 정본이 빠진 것을 실제 MFA 전에 발견했다. 이 연결표와 독립
> 감사가 통과해야만 장시간 runner가 열리도록 Gate를 보강했다. 원 CSV와 사전은
> 덮어쓰지 않는다.
> 2020 r3는 6-tier 782,432개·동반표 4개·독립 전수 QC·DB 재수출 표본 24/24까지
> 완료되어 SHA 동결했다. 2021은 exact-ID 1,207,299건으로 새 r3 DB를 완료했다.
> 성공 정렬은 1,206,862건이고 post-MFA exact-ID 후보는 437건이다. 연구자가
> identity를 승인했고, feature 실패 24·DB 내 미정렬 413을 분리한 preflight 뒤
> 6-tier 1,206,862개와 동반표 4개를 수출했다. 독립 전수 QC는 coverage 100%·
> hard failure 0, 보존 DB 표본 semantic·byte 24/24로 완료됐다. 2022도 source
> 866,359발화를 safe 752,591·follow-up 113,768로 분할하고 pre-MFA 제외 870을
> 적용한 exact-ID 751,721을 동일 r3로 새로 정렬했다. 성공 751,383·승인 기술
> 미정렬 338을 완전 회계한 뒤 6-tier 751,383개·동반표 4개를 수출했다. 독립
> 전수 QC는 coverage 100%·hard failure 0, 보존 DB 표본 semantic·byte 24/24다.
> 2020–2022는 동결한다. 2023도 exact-ID 494,580건을 같은 r3로 새로 정렬해
> 성공 494,228·승인 기술 미정렬 352로 회계했고, 6-tier 494,228개·동반표 4개·
> 독립 전수 QC·DB 재수출 표본 24/24를 완료했다. 2020–2023은 재실행하지 않는다.
> 다음 생산 동작은 2023 완료 SHA를 입력으로 한 2023→2024 전환 Gate다.

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
- 2020–2025 pronunciation-safe 4,384,992발화와 독립 정렬 가능성 계약의
  교집합을 같은 acoustic phone inventory와 r3 계약으로 연도별 새 DB에
  정렬한다. 기술적 제외는 exact-ID로 따로 보존하며 2020–2022 r2 interval·
  TextGrid는 최종 r3에 재사용하지 않는다.
- follow-up 718,364발화는 정확 ID·사유·원 입력 fingerprint를 보존한 별도 shard로
  유지한다. 구 TextGrid의 phone label만 바꾸거나 발화 안의 문제 어절만 삭제하는
  방식은 금지한다.
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
  → canonical exact donor 전역 projection·09 readiness·독립 감사 완료
  → no-rule 잔여 85,504형 candidate-only 계약
  → 단일 canonical 선택 계약·zero-fallback·adoption Gate
  → Stage 19 routing·Stage 20 후보 사전·Stage 21 표적 회귀 완료
  → 연구자 단계적 safe-body·6개년 전체 신규 정렬 승인
  → 외부 workflow 리뷰와 r3 전용 release/runner 구현
  → 체크리스트 1–7 확인·단일 release Gate 채택·정책 감사 통과
  → 2020 발음 연구 DB 870,437발화·3,056,807 occurrence 감사 passed
  → 2020 exact-ID 782,715발화 보강 preflight 19/19 GO
  → 2020 r3 정렬 DB 완료: 782,432 정렬·283 post-MFA 미정렬
  → 2020 exact-ID 회계·6-tier export·독립 QC·SHA 동결
  → 2021 exact-ID 1,207,299·발음 연구 DB·alignment 감사·preflight GO
  → 2021 r3 DB 완료: 1,206,862 정렬·437 post-MFA 후보
  → 2021 명시 승인·6-tier 1,206,862·동반표 4개 수출
  → 2021 독립 QC·DB 표본 24/24·SHA 동결
  → 2022 exact-ID 751,721·발음 연구 DB·alignment 감사·preflight GO
  → 2022 r3 정렬·승인·6-tier·독립 QC·SHA 동결
  → 2023 exact-ID 494,580·발음 연구 DB·alignment 감사·preflight GO
  → 2023 r3 정렬 494,228·승인 미정렬 352·6-tier·독립 QC·SHA 동결
  → 2023→2024 전환 Gate  ← 다음
  → 2024·2025도 직전 연도 Gate 뒤 연도별 신규 정렬
  → follow-up 718,364 exact-ID 후속 shard 보존·별도 회수
```

### 3.0 r3 발음사전–검색 CSV 연결 DB 생성

연도별 전수 MFA 전에 한 번 실행한다. 2020은 기존 형태소 검색 23 shard를
checkpoint로 재사용하며 23/23 완료했다. 이 명령은 MFA·WAV·TextGrid를 만들거나
수정하지 않는다. 이미 통과한 연도에는 입력 SHA가 달라지지 않는 한 반복 실행할
필요가 없다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_research_database.ps1" `
  -Year 2020
```

완료 조건은
`D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\05_research_database\2020\AUDIT_RESEARCH_DATABASE_2020.json`의
`status=passed`다. `pronunciation_type_catalog`, 발화 scope, occurrence 표와 SHA가
모두 고정된다. 2020 실측은 발화 870,437개·occurrence 3,056,807개이며 scope
782,715 + 1,675 + 86,047 = 870,437로 정확히 회계됐다. 이 파일이 없거나 달라지면
다음 runner는 자동으로 NO-GO한다.

### 3.1 2020 r3 전수 MFA 완료 checkpoint

2020 입력은 exact-ID 782,715발화이며 release ID는
`common_pron_mfa_r3_20260809`, alignment contract ID는
`3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`다.
Gate-adopted 정책 감사, 2020 occurrence DB 독립 감사와 보강된 preflight 19/19가
모두 통과했다. 아래 명령이 유일한 장시간 생산 진입점이다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_year_safe_body.ps1" `
  -Year 2020 -NumJobs 4
```

장시간 창은 그대로 열어 둔다. 상태는 별도 PowerShell 창에서 다음 읽기 전용
명령으로 확인한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_mfa_r3_year_status.ps1" `
  -Year 2020
```

첫 단계는 WAV hardlink와 LAB 782,715쌍을 release 전용 corpus에 checkpoint로
물질화하므로 MFA child PID가 나타나기 전에도 시간이 걸릴 수 있다. 이때 상태판의
`corpus_materializing_or_mfa_starting`은 정상이다. 중단되면 corpus·temp·DB를
삭제하지 말고 같은 명령을 한 번만 다시 실행한다. 동시에 두 개를 실행하지 않는다.
이 명령은 MFA DB 계산까지가 본체이며 TextGrid와 동반표 export는 DB 완료 marker
`ALIGN_DONE_2020.json`을 확인한 뒤 별도 단계에서 수행한다.

2026-08-09 완료값은 입력 782,715, word·phone interval 모두 존재 782,432,
post-MFA 미정렬 283, `spn` 0이다. 보존 DB SHA와 SQLite 무결성은 독립 감사에서
통과했다. 이 283건은 다음 exact-ID 회계 대상으로 넘기며 2020 전량을 다시
정렬하지 않는다. 완료 결과는
`docs/decisions/RESULT_mfa_r3_alignment_database_2020_20260809.md`를 따른다.

### 3.1.1 2020 post-MFA exact-ID 승인과 보존 DB 수출

정렬 DB를 다시 돌리지 않는다. 읽기 전용 감사에서 동결 입력 782,715건과 DB ID
782,715건의 전수 동등성을 확인했고, word·phone interval이 모두 있는 782,432건과
그렇지 않은 283건을 분리했다. 283건은 모두 `mfa_alignment_missing`이며
`alignment_and_analysis` 후속 처리 후보다. 실제 음운 실현 판단이 아니므로 전량
청취를 요구하지 않지만, 자동 승인은 금지하고 연구자의 명시적 범주 승인을 받는다.

연구자 `ari30`은 2026-08-10에 동결 후보 digest `065c2cd1d1dd...`의 283건을
명시 승인했다. 다음 명령의 `-PreflightOnly`도 2026-08-10에 통과했다. preflight는 TextGrid를
만들지 않고 ALIGN_DONE marker·DB SHA·동결 입력·활성 LAB·검색표·승인 exact-ID를
대사한다. r3의 분모는 전체 검색표가 아니라 `expected_mfa_input_ids`이며, 발음
follow-up·pre-MFA 제외를 누락으로 잘못 세지 않는다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_research_export.ps1" `
  -Year 2020 -Workers 4 -PreflightOnly
```

실측은 159.109초였고 모든 exact-ID hard set 0, `spn` 0, acoustic inventory 밖
phone 0이었다. full mode는 2026-08-10 09:19–10:43 KST에 완료됐다. 2,231세션의
6-tier 782,432개와 연도별 gzip 동반표 4개를 만들었고 coverage 100%, 실패·누락·
partial 0이다. 동반표 행은 발화 782,432, word 4,315,723, phone 16,458,699,
제외 283이며 manifest SHA와 4/4 일치한다. 전체 MFA는 재실행하지 않았다.
다음 단계였던 독립 연도 내용·계약 audit도 아래와 같이 완료했다.

### 3.1.2 2020 r3 독립 연도 semantic QC

전수 export 완료와 내용 감사는 분리한다. 아래 QC는 782,432개 6-tier의 tier·경계·
label·phone inventory와 gzip 동반표 전 행을 독립 대사하고, 보존 DB의 서로 다른
24세션을 새 scratch로 다시 수출해 현재 TextGrid와 semantic·byte 동등성을 확인한다.
MFA, 전수 TextGrid export, 원 DB·WAV·LAB·검색표는 다시 만들거나 수정하지 않는다.

`run_mfa_r3_research_qc.ps1`은 전수 감사 성공과 표본 검사를 별도 SHA checkpoint로
기록한다. 표본 단계에서 중단되면 같은 명령을 다시 실행하되 통과한 전수 감사는
재사용한다. 2026-08-10 실제 `-PreflightOnly`는 TextGrid 782,432, 승인 제외 283,
현재 audit/sample checkpoint 없음으로 통과했다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_research_qc.ps1" `
  -Year 2020 -Workers 4 -SampleSize 24
```

2026-08-10 첫 본 실행의 전수 audit는 1,510.689초에 성공했다. TextGrid
782,432/782,432, coverage 100%, hard failure 25범주 전부 0이고, gzip 표는 발화
782,432·word 4,315,723·phone 16,458,699·제외 283행으로 일치했다.

뒤이은 표본 검사에서 verifier가 구 r2 `lab_input_contract_id`만 읽고 r3의
`identity.year_input_contract_id`를 읽지 않는 호환 오류가 발생했다. 원 DB·TextGrid·
동반표에는 영향이 없었다. 두 schema를 명시 지원하고 상충·누락 identity를 거부하는
회귀검사를 추가한 뒤 preflight에서 `audit=True, sample=False`를 확인했다. 같은
명령은 성공한 전수 audit를 다시 수행하지 않고 표본만 재개해 semantic·byte 24/24를
55.524초에 통과했다. 최종 `QC_STATE.json`은 `status=passed`다.

따라서 위 명령은 현재 2020에 다시 실행하지 않는다. 다음 Gate는 2020 완료 state를
동결한 뒤 2021 한 연도만 준비하는 것이다. 오류·수정·재개 증거는
`outputs/reports/INCIDENT_mfa_r3_research_qc_2020_input_identity_20260810.json`에 있다.

### 3.1.3 2021 장시간 MFA 완료·post-MFA 승인·수출

2020 완료 state를 다시 계산하지 않고 SHA로 결속했다. 2021 원천 1,373,920발화는
pronunciation-safe 1,208,236과 follow-up 165,684로 정확히 분할됐고, 승인된
pre-MFA 기술 제외 937건을 빼 실제 입력 1,207,299건을 고정했다. recovered WAV
snapshot 1,416,216개 중 source WAV 누락은 0이며, source 밖 42,296개는 입력으로
암묵 선택하지 않는다.

발음 연구 DB는 1,373,920발화·6,648,515 occurrence를 회계했고 독립 감사가
`passed`다. alignment contract ID는
`e072d4a74ce1ade7d175e4988b6113977711852d491b8b72438744400bea3f95`다.
PowerShell 안전·5.1 runtime 68/68, Python 전체 555테스트, 실제 preflight의
20개 검사가 모두 통과했다. 필요 74.733 GiB, D: 여유 167.081 GiB다.

다음 장시간 명령은 2026-08-10 14:26 KST에 한 번 실행했고, 2026-08-11 00:19
KST에 `ALIGN_DONE_2021.json`을 생성하며 정상 완료됐다. 다시 실행하지 않는다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_year_safe_body.ps1" `
  -Year 2021 -NumJobs 4
```

완료 상태판은 다음과 같이 확인할 수 있다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_mfa_r3_year_status.ps1" `
  -Year 2021
```

입력·DB는 1,207,299건으로 일치한다. 성공 정렬은 1,206,862건이고, 437건은
`mfa_alignment_missing` 413건과 `mfa_feature_generation_failed` 24건이다.
candidate identity
`5a4c3de672f824b2b8a00026b443efb838e76d23fe846650ad07ab4be6a7be35`는
연구자가 승인했다. feature 실패 24건은 export 가능한 DB 밖의 승인 기술 제외,
413건은 DB 내 승인 미정렬로 분리해 합계 437건을 회계한다. 실제 preflight의
미승인·누락 inventory는 모두 0이다. 동시에 두 runner를 실행하지 않고, 2020과
2021 MFA는 재실행하지 않는다.

### 3.1.4 2021 6-tier 수출·독립 연도 QC 완료 checkpoint

보존 DB 수출은 2026-08-11 08:30–11:00 KST에 완료됐다. 6-tier TextGrid는
1,206,862개이고 동반표는 발화 1,206,862·word 8,926,793·phone 32,776,584·제외
437행이다. `spn`·미승인 exact-ID·inventory 밖 phone은 모두 0이다. 완료 보고서는
`outputs/reports/EXPORT_mfa_r3_research_6tier_2021_20260811_083053.json`이다.

첫 QC preflight는 구식 `export.accounted = expected_mfa_input` 검사가 feature 실패
24건을 반영하지 못해 materialization 전에 안전 중단됐다. 수출기와 같은 두 단계
exact-ID 식으로 QC를 보강하고 PowerShell 5.1 안전·runtime 검사를 통과한 뒤,
TextGrid 1,206,862·승인 제외 437로 preflight를 재통과했다. DB·TextGrid·승인
계약은 변경하지 않았고 전수 수출도 반복하지 않았다.

독립 QC는 11:05–11:58 KST에 완료됐다. 전수 coverage 100%·hard failure 0,
동반표 전 행과 manifest identity/SHA가 일치하며, 보존 DB 24세션 재수출은
semantic·byte 모두 24/24다. 최종 state는
`outputs/reports/mfa_r3_research_qc_common_pron_mfa_r3_20260809/2021/QC_STATE.json`의
`status=passed`다. 이 명령은 2021에 다시 실행하지 않는다. 다음 단계는 이 state와
`ALIGN_DONE_2021.json`을 SHA로 결속해 2022 한 연도만 준비하는 것이다.

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

### 3.6 r3 전역 donor projection·09 readiness 완료 checkpoint

canonical exact donor 382,891형을 사용해 기존 310,605 G2P target을 전수
재비교했다. 새 후보 13,172형을 얻었고, 좁은 donor에서만 unanimous였던 기존
후보 10,799형은 보류로 되돌렸다. 이는 오류가 아니라 전역 변이를 반영한
fail-closed 결과다. 생성기와 별도 감사기가 모두 통과했다.

09 readiness는 candidate 준비 752,270형·26,197,593회, 복수 변이 정책 35형,
zero-fallback 보류 128,932형·1,649,312회다. 다음은 아직 projection target이
아닌 no-rule 85,504형의 별도 후보 계약이다. 동일 G2P 재실행, canonical 자동
선택, MFA·TextGrid 변경은 금지한다. 상세 근거는
`docs/decisions/RESULT_common_pron_r3_global_projection_v2_20260808.md`를 따른다.

### 3.7 r3 no-rule 보류형 특성화 완료 checkpoint

no-rule 실질 불일치 85,504형·1,140,107회를 전수 분류하고 독립 감사했다.
모두 완성형 한글이며 숫자·기호·라틴 문자·낱자 자모는 없다. 비음 조음 위치,
활음·모음 단위화, 후두 대립 phone 매핑, 분절 수·탈락 차이가 함께 포함돼
있으므로 한 가지 fallback으로 자동 투사하지 않는다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
10_no_rule_hold_characterization\NO_RULE_HOLD_CHARACTERIZATION_MANIFEST.json
```

manifest 상태는 `success_characterized_not_candidate`, 별도 감사 상태는
`passed_read_only`다. 다음 한 단계는 고빈도 signature에 대한 표준 발음·
우리말샘·형태소 경계·acoustic inventory의 읽기 전용 coverage 감사다. 그
결과로 명시된 규칙/매핑만 candidate-only 계약에 추가한다. 85,504형 일괄
projection, canonical selection, adoption, MFA, TextGrid 변경은 금지한다.
상세 근거는
`docs/decisions/RESULT_common_pron_r3_no_rule_hold_characterization_20260808.md`를
따른다.

### 3.8 r3 규칙·MFA phone coverage 감사 완료 checkpoint

stage 11은 no-rule 85,504형·85,741변이를 동결 기본사전·acoustic inventory와
다시 대조했다. 모든 변이가 수의적 위치동화로만 다른 36,568형과, 그 집합과
겹치지 않으면서 모든 변이가 frozen 기본사전에 정확히 있는 811형을 분리했다.
전자는 의무 표준발음 규칙이 아니며 후자도 표준발음 정답이 아니라 MFA 정렬용
model-compatible 근거다. 일부 변이만 해당하는 82형과 나머지 48,043형은
계속 보류한다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
11_rule_phone_coverage_audit\RULE_PHONE_COVERAGE_MANIFEST.json
```

manifest는 `success_audited_not_candidate`, 독립 감사기는 `passed_read_only`다.
stage 12는 37,379형의 기존 r2 phone 변이를 정렬용 candidate-only로 09
readiness에 추가했다. `rule_pron_roman`은 표준 참조로 그대로 보존했다.
canonical selection·adoption·MFA·TextGrid 변경은 금지한다.
비일대일 phone 포함 여부만으로 후보를 승격하지 않는다. 상세 근거는
`docs/decisions/RESULT_common_pron_r3_rule_phone_coverage_audit_20260808.md`다.

### 3.9 r3 selection-readiness v2 완료 checkpoint

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
12_selection_readiness_v2\SELECTION_READINESS_V2_MANIFEST.json
```

candidate 준비는 789,649형·26,952,517회, zero-fallback hold는
91,553형·894,388회다. 별도 정책 결정 35형·163회는 유지한다. 독립 감사기는
881,237행을 v1과 대조해 새 후보 37,379행의 허용 planning 필드 외 변화가 없고,
모든 의무 규칙 참조가 보존됐음을 확인했다.

다음 단계는 hold_target_projection_unresolved 43,428형과
hold_no_surface_rule_substantive_mismatch 48,125형을 분리해, 이미 생성된 사전·
donor·편집 진단으로 회수 가능한 반복 패턴만 candidate-only로 제안하는 것이다.
같은 G2P 재실행, r2 일괄 fallback, canonical 자동 선택, MFA·TextGrid 변경은
금지한다. 상세 근거는
`docs/decisions/RESULT_common_pron_r3_selection_readiness_v2_20260808.md`다.

잔여 반복 패턴 요약까지 완료됐다. 다음 구현은 frozen 기본사전에서 단어·음절·
이차조음 문맥을 보존한 donor inventory를 만든 뒤 기존 canonical donor와의
unanimous·multiple-supported·conflict·no-donor를 재계산하는 읽기 전용 감사다.
phone 하나를 음소 하나로 전역 매핑하지 않는다. 상세 우선순위는
`docs/decisions/RESULT_common_pron_r3_readiness_v2_residual_priorities_20260808.md`다.

### 3.10 r3 문맥 보존 frozen 사전 donor 감사 완료 checkpoint

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
13_contextual_dictionary_donor_audit\CONTEXTUAL_DICTIONARY_DONOR_AUDIT_MANIFEST.json
```

동결 사전 20,978개 변이에 단어·음절·앞뒤 단위·이차조음 onset+glide 문맥을
보존했고, readiness v2 hold 91,553형을 기존 canonical donor와 전수 대조했다.
단일 근거 10,594형, 복수 근거 22,171형, 출처 충돌 48,780형, 근거 없음
10,008형이다. 전역 phone→음소 치환, 빈도 다수결, 후보 생성은 하지 않았다.
독립 감사는
`outputs/reports/AUDIT_common_pron_r3_contextual_dictionary_donor_20260808.json`이며
`passed_read_only`다. 상세 해석은
`docs/decisions/RESULT_common_pron_r3_contextual_dictionary_donor_audit_20260808.md`를
따른다.

### 3.11 r3 selection-readiness v3 완료 checkpoint

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
14_selection_readiness_v3\SELECTION_READINESS_V3_MANIFEST.json
```

단일 근거 중 모든 issue가 이차조음 onset+glide 관계이고 기존 r2 phone·Roman을
바이트 그대로 유지하는 6,141형·90,544회만 정렬용 candidate-only로 추가했다.
candidate 준비는 795,790형·27,043,061회, zero-fallback hold는
85,412형·803,844회다. 독립 감사는 881,237행을 v2와 전수 비교해 phone·Roman
변화 0과 비대상 필드 변화 0을 확인했다.

다음은 남은 단일 근거 4,453형을 ㅢ 규칙, 분절 삽입/삭제, 후두 대립·종성 교체로
분리하는 좁은 읽기 전용 감사다. `중에서`의 `ng`처럼 새 phone 삽입이 필요한
경우는 단일 donor만으로 승격하지 않는다. 상세 결과는
`docs/decisions/RESULT_common_pron_r3_selection_readiness_v3_20260808.md`를 따른다.
canonical selection·adoption 전에는 MFA·TextGrid 작업을 시작하지 않는다.

### 3.12 r3 단일 문맥 근거·phone 변경 필요형 감사 완료 checkpoint

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
15_unanimous_phone_change_audit\UNANIMOUS_PHONE_CHANGE_AUDIT_MANIFEST.json
```

Stage 15는 4,453형·72,030회의 미지지 issue 4,900개를 분절 삽입 2,826개,
직접 치환 2,047개, 이차조음 결합 치환 27개로 분리했다. ㅢ `EU_G`, `Y/W`
활음, `ng`, 종성 삽입과 후두 대립·비음/종성·모음·이차조음 치환을 별도 경로로
회계했다. 자동 후보는 0형이고 모든 형은 기존 hold를 유지한다. 정본은
`docs/decisions/RESULT_common_pron_r3_unanimous_phone_change_audit_20260808.md`다.

Stage 16은 이 4,453형을 검색 master 5,103,356발화와 전수 대조해 표면 exact
68,285회, 안전한 형태소·품사 문맥 60,292회를 연결했다. Bareun group과 표면
어절이 1:1이 아닌 행은 위치를 추정하지 않는다. Stage 16도 후보·selection·
adoption·MFA·TextGrid를 만들거나 바꾸지 않는다.

다음 단계는 사전·규칙 Roman exact인 좁은 집합의 전체 phone열을 문맥 donor로
완전 재구성할 수 있는지 감사하는 것이다. Stage 15·16을 다시 실행하거나 사용자가
4,453형을 전수 청취하지 않는다. 부분 phone 교정은 허용하지 않는다. canonical
선택과 adoption 전에는 MFA·TextGrid를 변경하지 않는다.

이 감사(Stage 17)는 실제 사전 등재 `pron_1/2` exact 65형 중 14형·200회만 전체
phone열을 완전·단일하게 구성했다. legacy 기계 `pron_g2p` 76형은 사전 등재
근거에서 제외했고, 복수·충돌 51형은 기술 hold로 남겼다. Stage 18 readiness v4는
14형만 candidate-only로 병합했으며 비대상 행 변화는 0이다. 현재 사용자가 51형을
청취하거나 승인하지 않는다.

Stage 19는 동결 pre-MFA root의 `pron_reference_form`을 실제 LAB tokenizer로
전수 라우팅했다. 발화 안에 hold/policy/unknown/empty가 하나라도 있으면 발화
전체를 follow-up으로 보내고 어절을 부분 삭제하지 않는다. 결과는 safe body
4,384,992발화, follow-up 718,364발화, unknown 0이다. Stage 20의 후보 사전은
795,804형·796,061변이이며 Stage 20 자체는 역사적 `NOT_ADOPTED` 후보로 보존한다.
이 후보를 byte-exact projection한 별도 `common_pron_mfa_r3_20260809` release가
현재 production Gate에서 채택됐으며 Stage 폴더를 직접 입력으로 쓰지 않는다.

Stage 21 표적 네 발화의 자동 회귀 검사는 통과했고 연구자는 네 경계를 모두
승인했다. 또한 4,384,992 pronunciation-safe 발화를 대상 pool로 삼고, 독립
정렬 가능성 Gate를 통과한 발화를 2020–2025 전 연도에서 새 r3 DB로 정렬하며
718,364 follow-up 발화를 별도 shard로 보존하는 것을 승인했다. 이를
전체 코퍼스 완료로 보고하지 않는다. 승인 계약은
`outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json`
이다. 외부 workflow 리뷰, r3 release/adoption materialization, 전용 runner,
자동검사와 2020 occurrence DB 감사가 완료된 뒤 현재 실행은 3.1절의 단일
명령만 따른다.

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

## 5. 2022 r2 역사와 r3 완료 상태

2022 r2 MFA 계산은 완료됐고 `D:\mfa_tmp\2022\2022.db`를 보존했다. 활성 LAB
865,128개 중 864,690개가 정렬됐으며 interval이 없는 438개는 exact-ID 검토
집합이다. 이 r2 DB에서 export·검토를 반복하지 않는다. r3 생산에서는 기존 DB를
수정하지 않고 별도 경로에서 2022 pronunciation-safe 중 정렬 가능 집합 전체를
새로 정렬한다. 기술적 제외는 exact-ID로 보존한다. r2 DB와
TextGrid는 비교·회귀·시행착오 근거로만 보존한다.

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
export부터 시작하도록 만든 역사적 r2 복구 명령이다. r3 Gate 상태와 무관하게 새
실행에 사용하지 않는다. 현재 열린 Gate는 r3 release
하나만 허용하며 이 r2 복구 명령을 다시 허용하지 않는다.

2022 r3는 2026-08-12에 다음 상태로 완료·동결했다.

- exact-ID 입력 751,721 = 정렬 성공 751,383 + 승인 기술 미정렬 338
- DB SHA-256
  `610054531403f0ca13292194b13f6e63e509434435864aec9f7118d888bfe5b2`
- 후보 identity
  `272bcc134776548df77b244d547b1e922ff287fa9d8f8505c31740e3b2357b7a`
- 6-tier 751,383개, 동반표 utterance 751,383·word 5,882,284·phone
  21,857,009·excluded 338행
- 독립 QC coverage 100%, hard failure 0, DB 재수출 semantic·byte 24/24
- 최종 `QC_STATE.json` checkpoint
  `7cf3af24c5da8f58126837742902495724f4dc69140a00b6ea6d162a9eda7c89`

2022 runner·수출·QC는 재호출하지 않는다. 2022 marker와 QC state SHA를 묶은
2022→2023 전환 Gate는 통과했고, 이어 2023 장시간 runner·post-MFA 회계·승인·
6-tier 수출·독립 QC까지 완료했다. 아래 명령은 역사적 재현 기록이며 다시 실행하지
않는다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_year_safe_body.ps1" `
  -Year 2023 -NumJobs 4
```

입력은 exact-ID 494,580건이며 2020–2022를 재호출하지 않았다. 상세 근거는
`docs/decisions/RESULT_mfa_r3_alignment_database_2022_20260812.md`와
`docs/decisions/RESULT_mfa_r3_2023_preflight_20260812.md`,
`docs/decisions/RESULT_mfa_r3_alignment_database_2023_20260813.md`다.

### 5.1 2023 r3 완료 checkpoint

- exact-ID 입력 494,580 = 정렬 성공 494,228 + 승인 기술 미정렬 352
- DB SHA-256
  `3c6695ac2033612d514e6ca57711d006d2505c6ddb25124b666865df8c315108`
- 후보 identity
  `e6716a3694124c656f040491ebb7b9bb7b5bd66947926fc6bccf0543eb878b3b`
- 6-tier 494,228개, 동반표 utterance 494,228·word 3,832,921·phone
  14,781,191·excluded 352행
- 독립 QC coverage 100%, hard failure 0, DB 재수출 semantic·byte 24/24
- 최종 `QC_STATE.json` SHA-256
  `115b81f539d87eb30892df2ffb0052e5d569884569aa4ff9f30c0b39db91d958`

2023 runner·수출·QC는 재호출하지 않는다. 다음 단일 작업은 완료 marker·DB·QC
state SHA를 입력으로 한 2023→2024 전환 Gate다. Gate가 통과하기 전에는 2024
장시간 runner를 시작하지 않는다.

실행 queue ID와 장시간 명령은 위 검사 직후 현재 값으로 고정해 사용자에게 한 줄로
제공한다. 문서에 날짜가 지난 queue ID를 미리 복사해 두지 않는다.

## 6. 연도별 반복 절차

2020–2025 r3는
`docs/WORKFLOW_mfa_r3_full_realign_2020_2025.md`의 checkpoint 계약을 정본으로
삼고 다음 순서만 반복한다. 연도 전체를 지우고 처음부터 다시 시작하는 자동
경로는 두지 않는다.

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

2023에서는 승인 103,930건 중 pronunciation-safe와 교차하는 87,809건만 본체에서
제외했다. 나머지 16,121건은 이미 pronunciation follow-up에 있으므로 이중 계산하지
않는다. `677,262 = 494,580 + 94,873 + 87,809`가 전수 회계식이다.

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
