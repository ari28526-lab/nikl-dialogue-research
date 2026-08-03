# 2020–2025 연구 인프라 전수 생산 RUNBOOK

최종 갱신: 2026-08-03 KST

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

## 현재 시작점 — 2020 보존 DB export

2020 신규 MFA 계산은 이미 끝났다. 보존 DB의 실제 미정렬 363 ID를 원 후보표와
전수 대조했고, pre-MFA 1,887건과 post-MFA 363건을 합친 2,250건 승인 계약도
완성했다. 따라서 아래 A–C는 완료 이력이며 **다시 실행하지 않는다.** 지금은
다음 한 줄로 시작한다.

먼저 읽기·검증만 수행한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\resume_2020_export_after_post_mfa_review.ps1" `
  -ApprovedBy "ari30" `
  -ApprovePostMfa363 `
  -PreflightOnly
```

결과가 `GO`이면 `-PreflightOnly`만 빼고 실행한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\resume_2020_export_after_post_mfa_review.ps1" `
  -ApprovedBy "ari30" `
  -ApprovePostMfa363
```

이 wrapper는 `D:\mfa_eojeol\done\2020.direct_db_ready`와
`D:\mfa_tmp\2020\2020.db`의 입력·정렬 계약을 다시 확인한다. 같은 checkpoint면
MFA를 건너뛰고 6-tier·동반표 export와 후속 기계 QC부터 재개한다. full clean,
전수 재정렬, 자동 정본 승격, 2021 자동 진입은 하지 않는다.

2026-08-03 첫 실제 재개는 구 입력 gate가 post-MFA 승인 363건의 LAB·WAV
존재를 잘못 차단해 export 전에 종료됐다. DB와 checkpoint는 보존됐고 출력은
생성되지 않았다. 현재 코드는 같은 checkpoint와 DB 미정렬 exact-ID를 함께
검증하도록 교정됐으므로 위 실제 실행 명령을 그대로 다시 사용한다. 구 큐 폴더나
DB를 삭제하지 않는다.

## 3. 단계별 사용자 행동

### A. 2020 검색표

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

### D. 2020 생산 표본 연구자 확인

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

2020 연구자 보고서가 승인되면 Gate B를 통과시킨 뒤 2021–2025 제외 후보표를
준비한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_remaining_mfa_approval_reviews.ps1"
```

남은 연도의 제외 후보를 확인해 승인한 뒤 다음 wrapper를 사용한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\start_remaining_mfa_after_2020_gate.ps1" -ApprovedBy "ari30"
```

Gate B는 2020 audit, align/merge marker, retained DB, DB 표본 동등성, 연구자
확인, input/alignment/source contract, 모델·방법 계약을 대조한다. 실패하면
2021을 시작하지 않고 보고서만 남긴다.

2021–2025에서는 연도별 실패 상태·partial·DB를 보존하고 다음 조치를 분리한다.
full-clean 재실행이나 정본 승격은 자동으로 하지 않는다.

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
