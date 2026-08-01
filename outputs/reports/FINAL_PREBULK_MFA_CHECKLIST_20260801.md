# 2020–2025 전수 MFA 직전 최종 점검

- 판정 시각: 2026-08-01 13:47 KST
- 현재 판정: **NO_GO — 승인자료 생성 단계**
- 의미: 코드·공통사전·원자료 대응·저장공간은 통과했으나, 연구자가 확인한
  연도별 제외 계약이 아직 없어 전수 MFA를 시작하지 않는 것이 정상이다.

## 이미 통과한 항목

- 공통 Jamo 발음사전 r2와 adoption 실물 SHA 검증
- 동일 Korean MFA acoustic model, Jamo G2P, phone inventory 계약
- D: 볼륨 라벨 `DATA_SSD`, 여유 318.5 GiB
- 2020–2025 동결 search master와 원 WAV 세션 전수 대응
- live lock, stale temp/output, final staging 충돌 없음
- 60발화 6-tier 회귀: 60/60, 기존 word/phone 불일치 0, `spn=0`
- Python 287/287, PowerShell 안전검사 20/20
- PPTX 15장: 도형 범위·텍스트 넘침·슬라이드별 `[Sources]` 15/15 통과

## 현재 남은 hard blocker

| 연도 | 상태 | 다음 조치 |
|---:|---|---|
| 2020–2021 | lab 입력 계약 통과, 승인 제외 계약 없음 | pending 검토표 생성·연구자 승인 |
| 2022–2025 | lab 입력 계약 생성 전 | lab 전수 검증 → pending 검토표 → 연구자 승인 |

후보가 0건이어도 “0건을 확인했다”는 빈 승인 계약을 만들어야 한다. 자동 승인은
금지되어 있다.

## 지금 실행할 안전 단계

아래 명령은 6개 연도의 lab 입력을 전수 검증하고 승인 전 후보표를 만든다.
MFA 정렬, WAV 이동, 제외 자동 승인, 정본 승격은 하지 않는다.

```powershell
Set-Location "C:\Users\ari30\research\2026_summer_research"

& ".\scripts\run_mfa_year_queue_safe.ps1" `
  -CommonPronManifest "D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\00_contract\release_manifest.json" `
  -CommonPronAdoptionContract "D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\00_contract\adoption_contract.json" `
  -PrepareMissingReviews
```

검토자료 기본 위치:

```text
C:\Users\ari30\research\2026_summer_research\outputs\reviews\
  mfa_exclusions_queue_mfa_r2_full6y_20260801\<YEAR>\
```

각 연도 폴더의 `03_RESEARCHER_REVIEW.csv`에서 `decision=pending`을 실제 검토
결과로 바꾼 뒤, 그 파일과 manifest의 `input_contract_id`를 이용해
`mfa_exclusion_contract.py build`로 `approved_exclusions.json`을 만든다.

## 전수 시작 허용 순서

1. `-PrepareMissingReviews` 완료 및 6개 연도 후보표 실물 확인
2. 연구자 검토와 연도별 `approved_exclusions.json` 생성
3. `preflight_mfa_year_queue.ps1 -RunRepositoryTests` 재실행
4. 결과 JSON의 `status`가 정확히 `GO`인지 확인
5. 같은 Queue ID로 `run_mfa_year_queue_safe.ps1` 실행

승인 완료 뒤 최종 검사 명령:

```powershell
$approvalRoot = "C:\Users\ari30\research\2026_summer_research\outputs\reviews\mfa_exclusions_queue_mfa_r2_full6y_20260801"

& ".\scripts\preflight_mfa_year_queue.ps1" `
  -CommonPronManifest "D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\00_contract\release_manifest.json" `
  -CommonPronAdoptionContract "D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\00_contract\adoption_contract.json" `
  -ApprovedExclusionsRoot $approvalRoot `
  -RunRepositoryTests
```

위 보고서가 `GO`인 경우에만 실행할 전수 큐 명령:

```powershell
& ".\scripts\run_mfa_year_queue_safe.ps1" `
  -CommonPronManifest "D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\00_contract\release_manifest.json" `
  -CommonPronAdoptionContract "D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\00_contract\adoption_contract.json" `
  -ApprovedExclusionsRoot $approvalRoot
```

전수 큐는 한 연도 실패 시 temp·SQLite DB·로그·partial을 보존하고 다른 연도의
독립 처리를 계속한다. temp가 있는 재개 실패 뒤 자동 `--clean` 전면 재계산은 하지
않는다. 정렬 계산이 끝나고 출력/QC만 실패하면 `direct_db_ready`에서 재사용한다.

## 전수 중·후 확인

```powershell
& ".\scripts\show_mfa_year_queue_status.ps1" `
  -QueueId "mfa_r2_full6y_20260801"
```

- `mfa_failed_checkpoint_preserved`: 정렬 체크포인트를 보존한 실패
- `machine_qc_failed_outputs_preserved`: MFA DB는 재사용하고 출력/QC만 수정
- `machine_qc_passed_human_review_pending`: 기계 QC 통과, 연구자 표본 검토 대기
- 성공하더라도 정본 승격은 자동으로 하지 않는다.

## 연구 방법론 최종 경계

MFA/G2P/사전 phone은 실제 음운 실현의 판정값이 아니다. 전수 인프라는 형태소·
표기 환경으로 후보를 찾고 대응 WAV·6-tier TextGrid·동반표를 연결한다. KOINA,
이어붙이기, wav2vec2는 선별 후보에만 별도 보조층으로 붙이며, 실제 실현은 연구자가
청취·시각 검토해 별도 manual judgment 표에 기록한다.

## 근거 파일

- `PREFLIGHT_mfa_year_queue_mfa_r2_full6y_20260801.json`
- `PREFLIGHT_mfa_adoption_mfa_r2_full6y_20260801.json`
- `QA_MFA_research_infrastructure_final_prebulk_20260801.json`
- `docs/decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md`
- `docs/decisions/DECISION_incremental_unattended_year_MFA_20260801.md`
