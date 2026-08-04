# 2020–2025 연구 인프라 전수 생산 RUNBOOK

최종 갱신: 2026-08-04 KST

이 문서가 전수 작업의 유일한 실행 정본이다. 구 RUNBOOK·MONITOR·PILOT의
명령이 이 문서와 다르면 이 문서가 우선한다.

## 1. 목적과 완료 산출물

전수 작업은 실제 음운 실현을 자동 판정하는 과정이 아니다. 연구자가 후보를
찾고 음성·TextGrid를 연결해 판단할 수 있는 인프라를 만든다.

연도마다 다음을 완성한다.

1. pre-MFA `morph_search.v3` 7표
2. 공통 Jamo r2 기준 신규 MFA
3. 6-tier TextGrid
4. post-MFA gzip 동반표 4개
5. 입력·정렬·출력·DB·표본 동등성 manifest
6. 승인 제외 기록과 연구자 표본 확인 기록

## 2. 절대 순서

```text
workflow 수정·시험
  → 2020 검색표 완주
  → 2020 CSV–WAV ID 대응 복구·전수 재감사
  → 2020 제외 후보 검토·승인
  → 2020 신규 MFA·6-tier·동반표·기계 QC
  → 2020 생산 표본 연구자 확인
  → Gate B
  → 2021–2025 연도별 체크포인트 큐
  → 7표+4표 join/Parquet·DuckDB
  → 우리말샘 1:N 보조표
  → 실제 연구 후보 bundle·KOINA/보조모델·수동 판정
```

2020 Gate B 전에는 2021–2025 MFA를 시작하지 않는다. 검색표 계산은 D: I/O와
겹치지 않는 때에 별도로 할 수 있으나 MFA를 미루기 위한 새 gate로 삼지 않는다.

## 현재 시작점 — 2021 post-MFA 승인 완료, export 재개 전

2020은 신규 공통 Jamo r2 MFA, 6-tier 868,187개, gzip 동반표 4개, 독립 전수
감사, DB 재생성 표본 24/24, 연구자 생산 표본 24/24 및 Gate B까지 완료됐다.
Gate B의 16개 core check는 모두 통과했고 `allow_remaining_years=true`다.
2020 계산·export·검토 명령은 **다시 실행하지 않는다.** 2021–2025 최초
safe-body 후보 112,292건은 연구자 `ari30`이 승인했다. 2021 첫 실행은 LAB
전수 검증 뒤, 실제 MFA 계산에 들어가기 전 입력감사에서 안전 중단됐다.

2021 진입 전 구 결과·상태 정리도 완료됐다. 구 2021–2025 TextGrid와 2021
MFA DB/temp는 E:의 기존 검증 archive에 있고 D: 연도 결과 폴더는 0개다. D:에
남았던 구 2021 로그·완료표시·입력계약 9개도 E:에 CRC·SHA 검증 보관했다.
기존 2021 `.lab`은 입력 재사용을 위해 남겼지만 구 완료표시는 제거했으므로 아래
정상 실행에서 전수 내용 검증 후 일치분만 재사용한다. 과거 정렬 완료 상태를 새
Jamo r2 결과로 오인해 건너뛰지 않는다.

중단 원인은 두 가지다.

1. 최초 승인 계약을 검사했지만 승인된 1,488건의 파생 LAB를 실제 MFA 입력에서
   분리하지 않은 구현 누락이 있었다. 감사가 active WAV+LAB 1,089쌍을 발견했다.
2. 원본 CSV 분절시간이 `0.0`인 14건이 최초 후보 snapshot에 없었다.

MFA DB·TextGrid는 생성되지 않았고 원본 WAV/CSV와 2020 완성본은 그대로다.
실패 queue는 checkpoint로 보존했으므로 지우지 않는다. 승인 LAB는 원본 WAV를
건드리지 않고 계약별 archive로 옮기며, 그 계약 SHA를 alignment identity에
결속하도록 코드를 보강했다.

현행 승인 정본은 다음 **승인 1,502행**이다.

```text
outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_safe_body_2021_v2_20260804/
  2021/03_RESEARCHER_REVIEW.csv
  2021/03_RESEARCHER_REVIEW_MANIFEST.json
  2021/04_RESEARCHER_APPROVED.csv
  2021/approved_exclusions.json
```

기존 1,488건은 변경하지 않았고 새 14건만 `audio_pairing_unresolved`로 더했다.
연구자 `ari30`은 11:21 KST에 이 14건의 안전 본체 제외와 후속 shard 이월을
명시 승인했고, 총 1,502행 `approved_exclusions.json`을 만들었다. 승인·코드·문서
커밋과 Windows PowerShell 5.1 검사, 새 queue의 `-PreflightOnly`는 11:27 KST에
모두 통과했다. 이전 queue ID는 재사용하지 않는다. 아래 명령은 11:42:13 KST에
이미 실행됐고 2021 MFA·DB checkpoint까지 완료했으므로
**다시 입력하지 않는다.** 현재 재개 지점은 아래 E-1의 post-MFA 승인·export다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\start_remaining_mfa_after_2020_gate.ps1" -ApprovedBy "ari30" -ApprovalQueueId "mfa_r2_prod_safe_body_2021_v2_20260804" -ExecutionQueueId "mfa_r2_prod_safe_body_2021_v2_20260804" -Year "2021"
```

이 명령은 2021 한 연도만 시작한다. 승인된 1,502건의 파생 LAB를 먼저 가역
보존하고, 같은 계약의 입력감사가 통과한 뒤에만 MFA가 시작된다. 실패한 구 queue와
그 checkpoint는 삭제하지 않는다.

실행 실측: 파생 LAB 1,103개 가역 보관, 활성 LAB 없음 399개로 승인 1,502건이
모두 적용됐다. 승인 반영 뒤 입력감사는 안전 본체 1,372,418건, 승인 active pair
0, duration 잔여 불일치 0으로 통과했다. 실제 MFA는 12:07:23에 시작됐다.
11:42–12:42 집중 점검에서 오류·watchdog 중단 신호 없이 코퍼스 적재가 진행됐다.
근거는 `outputs/reports/MONITOR_2021_mfa_first_hour_20260804.json`이다. MFA는
20:53:45에 exit 0으로 종료됐고 21:08:22에 동일 입력·정렬 계약의
`2021.direct_db_ready`를 생성했다. direct export 전 exact-ID 대조에서
535건(정렬 interval 없음 511, feature 생성 실패 24)을 분리했고
DB를 보존한 채 fail-closed했다. 이 집합은 자동 승인하지 않았다.
2021 export·독립 감사·DB 표본·연구자 표본 승인 전에는 2022 명령을
실행하지 않는다.

연구자 `ari30`은 21:35 KST에 post-MFA 535건을 안전 본체에서 기술적으로
제외하고 후속 회수 대상으로 보존하는 것을 명시 승인했다. 24개
WAV/LAB 청취는 2021 최종 Gate 전으로 유예했다. 승인 작업본은
535/535 `approved`, pending 0이고 immutable 필드 변경 0을 확인했다.
결합 2,037건 계약·DB·후보 identity `-PreflightOnly`는 통과했으며
결합 계약은 생성됐다. 첫 실행은 이 결합 계약을 정렬 provenance에도 전달해
기존 `alignment_contract_id=5ff186…`와 달라졌고, 자동 재정렬 금지 gate에서
6-tier 생성·MFA 재실행 전에 안전 중단됐다. DB는 보존됐다.

현행 재개 경로는 두 계약을 분리한다. 정렬 identity에는 정렬 당시 승인
1,502건을 유지하고, 결합 2,037건은 LAB 재정돈·export·독립 감사에만 쓴다.
실패한 `..._postmfa` queue ID는 재사용하지 않고 새 execution queue로
`PreflightOnly`를 다시 통과한 뒤 같은 DB에서 export만 재개한다.

두 wrapper 모두 2020을 실행 범위에 다시 포함하지 않는다. 2020 완료 근거는
`outputs/reports/GATE_B_2020_TO_2021.json`과
`docs/decisions/DECISION_2020_production_complete_gate_b_20260803.md`에 고정했다.

## 3. 단계별 사용자 행동

### A. 2020 검색표 — 완료 이력, 재실행 금지

코드·시험이 커밋된 뒤 다음 wrapper 하나만 실행한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\resume_2020_morph_search.ps1"
```

기존 성공 shard 1은 SHA 검증 후 재사용한다. 완료 기준은
`annual_tables\YEAR_MANIFEST.json`의 `status=success`와 source contract 일치다.

### B. 2020 CSV–WAV 대응 복구와 제외 후보 준비

2026-08-01 전수 감사에서 배포 PCM/WAV의 발화 번호 밀림이 확인되었다. 복구
결정과 dry-run 수량은
`docs/decisions/DECISION_2020_CSV_WAV_ID_recovery_20260801.md`를 따른다.
2026-08-02 10:24 KST 복구 코퍼스 apply와 독립 전수 계수가 통과했다. 최종
계약 ID는 `eb64f80d9106d14c7b2a267811cdf2dc2fe29e890cc335a7029a8cca24a7375f`다.
고신뢰 remap 청취 검토는 12/12 통과했고, 복구 코퍼스 dry-run도 통과했다.
원본 `D:\20_AUDIO\03_wav\individual`은 수정하지 않는다. 먼저 다음 명령으로
E: 독립 archive와 D: 파생 코퍼스를 만든다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\run_2020_wav_id_recovery.ps1" -Apply -ApprovedBy "ari30"
```

위 명령은 현재 완료됐다. 최종 계약 검증 없이 재생성할 때만 다시 사용한다.
아래 `prepare_2020_mfa_approval_review.ps1`도 2026-08-02 전수 검증을 완료한
이력 명령이며 지금 다시 실행하지 않는다.

이 명령은 영향 129세션 중 원음 폴더가 있는 128세션을 E:에 세션별 ZIP+SHA
manifest로 보존하고, 원음 폴더 자체가 없는 `SDRW2000000176`은 513발화 전부를
제외 검토 대상으로 유지하면서 `verified_absent` manifest를 남긴다. 이어서
2020 MFA 전용 파생 코퍼스를 D:에 만든다. 영향 없는 파일은 검증된 NTFS
hardlink, 영향 세션은 독립 복사본을 사용한다. 모호·미해결 1,834건은 파생
코퍼스에서 제외해 다음 연구자 제외 검토로 보낸다. 중단되면 완료 세션을 검증해
재사용하므로 처음부터 다시 만들지 않는다. apply가 실행되는 동안 Windows
시스템 절전을 억제하고 종료 시 원래 실행 상태로 복원한다. 화면은 꺼져도 된다.

읽기 전용 상태판:

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\show_2020_wav_id_recovery_status.ps1"
```

복구 계약이 `passed`가 된 뒤에만 제외 후보를 만든다. 기존 14행 표와 미해결
기호 53건이 빠진 첫 1,834건 표는 승인하지 않는다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_2020_mfa_approval_review.ps1"
```

이 명령의 전수 검증은 2026-08-02 완료됐다. **지금 다시 실행하지 않는다.**
검증 결과를 다시 계산하지 않고 결합한 최종 활성본은 다음이다.

```text
outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_20260801/2020/
```

최종 후보는 음원 미대응 1,834건과 빈 LAB 미해결 기호 53건, 합계 1,887건이다.
부분 한글 LAB이 남은 미해결 기호 6,158건은 제외하지 않고
`pron_reference_status=unresolved_symbol` 경고를 연결 CSV에 보존한다. 자세한
근거는
`docs/decisions/DECISION_2020_MFA_exclusion_symbol_accounting_20260802.md`다.
두 제외 범주 1,887건은 2026-08-02 연구자 `ari30`이 명시 승인했고, 원 pending
표와 별도 승인본·승인 기록·입력 계약 결속 제외 계약을 보존했다. 자동 승인은
하지 않았다. 후보표 재생성 명령을 다시 실행하지 않는다. 다음 사용자 행동은
아래 C단계의 2020 단일 시작 wrapper 한 줄이다.

### C. 2020 최초 신규 MFA 시작 — 완료 이력, 재실행 금지

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\start_2020_mfa_after_review.ps1" -ApprovedBy "ari30"
```

이 wrapper는 2026-08-02 최초 계산에 사용한 이력 명령이다. 현재는 위의
`resume_2020_export_after_post_mfa_review.ps1`만 사용한다. 최초 wrapper는 내부에서
2020 검색표 완료, 같은 `_build_meta` SHA, 승인 계약,
공통사전, 저장공간, repository test를 먼저 확인한다. 정확히 `GO`일 때만 2020
한 연도를 시작하고, 하나라도 실패하면 MFA를 시작하지 않고 보고서만 남긴다.
`-PreflightOnly`는 진단만 따로 반복해야 할 특별한 경우의 선택 옵션이지 정상
생산 절차의 별도 필수 단계가 아니다.

완료 상태 `machine_qc_passed_human_review_pending`은 기계 QC가 통과했지만 아직
정본 승격이나 다음 연도 허가가 아니라는 뜻이다.

### D. 2020 생산 표본 연구자 확인 — 완료 이력, 재실행 금지

기계 QC 완료 뒤 검토표를 만든다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_2020_production_sample_review.ps1"
```

기계가 선택한 최소 5세션 표본에서 다음만 확인한다.

- WAV·LAB·TextGrid·CSV가 같은 `utt_id`인가
- 6개 tier 이름·내용·0–xmax 경계가 계약과 맞는가
- 검색용 Roman·형태소 정보가 읽히고 원자료와 연결되는가
- 재수출/제외가 필요한 명백한 인프라 오류가 있는가

여기서는 ㄴ 삽입 등 실제 실현 여부를 판정하지 않는다. 같은 전역 이슈를 행마다
반복해서 쓰지 않고 issue code 한 번과 적용 범위를 기록한다.

모든 행을 확인해 `decision=approved`로 저장한 뒤 승인 보고서를 만든다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\approve_2020_production_sample_review.ps1" -ApprovedBy "ari30"
```

### E. Gate B와 2021–2025

2020 연구자 보고서 승인과 Gate B는 2026-08-03 완료됐다. 최종 상태는
`passed`, 실패 0, `allow_remaining_years=true`다. 2021–2025 제외 후보표와
5행 범주 요약도 준비됐다. 아래 명령은 완료 이력이며 반복하지 않는다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_remaining_mfa_approval_reviews.ps1"
```

5개년 세 범주의 개수와 뜻을 확인해 명시 승인한 뒤 다음 wrapper를 사용한다.
현행 wrapper는 의도적으로 **2021 한 연도만** 처리한다. 2021의 기계 QC·생산
표본 연구자 승인·다음 연도 gate가 끝나기 전 2022를 받지 않는다.

승인과 별개로, 각 연도 MFA 전에 연구 검색용 `morph_search.v3` 7표와 source
contract가 완료돼야 한다. 이는 동결 pre-MFA search master에서 파생되며 원본을
바꾸지 않는다. 현재 2021–2025는 미생성 상태이므로 2021부터 실행한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_production_year_before_mfa.ps1" -Year "2021"
```

진행 확인은 별도 창에서 다음 읽기 전용 상태판을 사용한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\show_production_year_pre_mfa_status.ps1" -Year "2021"
```

MFA가 실제 계산에 들어간 뒤의 phase·정렬 수·오류·watchdog·자원은 다음
공유 읽기 상태판으로 본다. 활성 heartbeat를 일반 `Get-Content`로 직접 열지
않는다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\show_active_mfa_progress.ps1" -Year "2021"
```

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\start_remaining_mfa_after_2020_gate.ps1" -ApprovedBy "ari30"
```

Gate B는 2020 audit, align/merge marker, retained DB, DB 표본 동등성, 연구자
확인, input/alignment/source contract, 모델·방법 계약을 대조한다. 실패하면
2021을 시작하지 않고 보고서만 남긴다.

2021–2025에서는 연도별 실패 상태·partial·DB를 보존하고 다음 조치를 분리한다.
full-clean 재실행이나 정본 승격은 자동으로 하지 않는다.

#### E-1. 예외적 post-MFA exact-ID 중단 처리

MFA 계산 완료 뒤 queue 상태가 `post_mfa_export_failed_db_preserved`이면 MFA를
다시 시작하지 않는다. 이는 direct exporter가 active LAB 중 word/phone 정렬이
없는 ID를 숨기지 않고 멈춘 상태다. 먼저 다음 준비기로 DB·실패 보고서·기존
승인 계약을 대조한 pending 검토표와 소수 WAV/LAB 표본을 만든다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_post_mfa_exact_reconciliation_review.ps1" `
  -Year "2021" `
  -SourceQueueId "mfa_r2_prod_safe_body_2021_v2_20260804"
```

`02_RESEARCHER_DECISIONS.csv`는 생성 근거이므로 수정하지 않는다. 연구자는
`04_RESEARCHER_APPROVAL.csv`의 후보·사유·표본을 확인하고 승인하는 행만
`decision=approved`로 바꾼다. `SUMMARY.json`의 `required_approval_token`을
확인한 뒤 아래 재개기를 사용한다. 실제 token과 승인 문구 없이 실행할 수 없다.

시간상 WAV/LAB 표본을 즉시 청취하지 못하는 경우, exact-ID·DB 분류·
길이 근거로 **기술적 제외 방침**만 명시 승인해 export를 재개할 수
있다. 이때는 승인 문구에 `청취 검토 유예`를 기록하고, 유예된 표본
검토를 2021 최종 Gate에 결합한다. 청취 검토가 끝나기 전에는 2022를
시작하지 않는다. 이 승인은 음운 실현이나 원자료 오류를 판정하는 것이 아니라,
현 MFA에서 interval이 없는 자료를 본체 분석에서 분리하고 후속 회수 대상으로
보존하는 운영 승인이다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\resume_year_export_after_post_mfa_review.ps1" `
  -Year "2021" `
  -SourceQueueId "mfa_r2_prod_safe_body_2021_v2_20260804" `
  -ApprovedBy "ari30" `
  -ApprovalToken "SUMMARY_JSON의_TOKEN" `
  -ApprovalStatement "검토한 exact post-MFA 후보를 분석·정렬 본체에서 제외하고 보존 DB에서 export를 재개한다" `
  -ApprovePostMfaExactReconciliation
```

이 명령은 새 결합 승인 계약을 만들고 같은 `direct_db_ready` DB에서 export만
재개한다. DB·입력·정렬 계약이나 후보 identity가 달라지면 중단한다. 결과가
성공해도 아래 F단계의 독립 감사·표본 연구자 확인 전에는 다음 연도로 가지 않는다.

### F. 2021 이후 한 연도씩 전진

실행 queue는 연도별로 분리한다.
`mfa_r2_prod_safe_body_<YEAR>_20260803` 형식이며, 5개년 제외 승인 root와는
별개다. 현 연도 기계 QC가 성공하면 먼저 다음 표본 준비기를 사용한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_production_year_sample_review.ps1" -Year "2021"
```

연구자는 생성된 표에서 같은 발화의 WAV·LAB·6-tier 연결, 정렬의 전반적 사용
가능성, 6개 tier와 검색 정보의 이해 가능성을 확인한다. 실제 음운 실현 여부는
판정하지 않는다. 모든 표본 확인 뒤 승인 기록을 만든다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\approve_production_year_sample_review.ps1" -Year "2021" -ApprovedBy "ari30"
```

그 다음에만 2022 한 연도를 시작할 수 있다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\start_next_mfa_year_after_gate.ps1" -Year "2022" -ApprovedBy "ari30"
```

2022→2023, 2023→2024, 2024→2025도 연도 숫자만 바꾸어 같은 순서로 처리한다.
시작기는 직전 연도 gate를 내부에서 다시 실행한다. 실패하면 다음 MFA는 시작하지
않고 source/core/composite gate 보고서를 남긴다.

각 다음 연도도 MFA 시작 전에 같은 준비기로 검색표·source contract를 먼저
완료한다. 예를 들어 2022는 다음과 같다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_production_year_before_mfa.ps1" -Year "2022"
```

## 4. 정지·재개 원칙

- 콘솔 창이 닫혔으면 먼저 상태판과 lock/process를 읽고 같은 wrapper를 재실행한다.
- 성공 shard, LAB contract, MFA DB, export partial은 검증 후 재사용한다.
- 일부 누락 때문에 연도 전체를 처음부터 자동 재계산하지 않는다.
- 실패 파일은 승인 제외 또는 국소 재처리 목록으로 분리한다.
- D: 공간 정리는 QC·보존 목록·dry-run·사용자 승인 뒤에만 한다.

## 5. 방법론 보고 범위

논문에는 2020–2025가 같은 acoustic model, 공통 Jamo G2P, phone inventory,
입력 정규화, 6-tier exporter, QC 계약으로 처리되었다고 보고할 수 있다.
MFA phone을 실제 발음 또는 실현 판정이라고 쓰지 않는다. `phoneme_r_auto`도
MFA phone을 기계적으로 넓게 Roman화한 보조층이며 기저형 분석이 아니다.

## 6. 동결 형식 변경 절차

6-tier 이름, Roman 구분자·대소문자, 7표/4표 schema, phone 기준을 바꾸려면
생산을 멈추고 새 결정문·회귀시험·migration 영향을 기록한다. 그 외 단순 오류
복구는 새 파일럿이나 외부 설계 리뷰 없이 checkpoint에서 수정·재개한다.
