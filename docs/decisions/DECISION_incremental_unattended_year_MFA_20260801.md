# 결정: 연도 내부 계산을 보존하는 무인 MFA 연도 큐

- 결정일: 2026-08-01
- 범위: 공통 Jamo 발음사전 r2로 2020–2025를 다시 정렬하는 계산 단계
- 목적: 며칠간 연구자가 계속 지켜보지 못해도 계산을 진행하되, 일부 오류 때문에
  같은 연도의 이미 끝난 계산을 처음부터 반복하지 않는다.

## 연구 목적과 운영 원칙

이 큐의 목적은 실제 음운 실현을 자동 판정하는 것이 아니다. 동결 CSV를 바탕으로
검색 가능한 발화를 찾고, 대응 WAV·6-tier TextGrid·동반표를 일관된 phone 기준으로
확보하는 연구 인프라를 계산하는 것이다. KOINA, 이어붙이기, wav2vec2 보조열,
연구자의 실현 여부 판정은 후속 선별 연구 레이어로 남긴다.

자동화와 연구자 판단은 다음처럼 분리한다.

1. 입력·모델·MFA DB·TextGrid·동반표의 기계적 정합성은 자동 검사한다.
2. 제외 발화는 연구자가 승인한 계약만 허용한다. 후보를 자동 승인하지 않는다.
3. 기계 QC가 통과해도 `human_review_pending`이며 정본으로 자동 승격하지 않는다.
4. 한 연도가 막혀도 다른 연도는 독립 staging에서 준비·계산할 수 있다.

## 연도 전체 재계산을 막는 변경

기존 러너에는 동일 입력의 temp 재개가 실패하면 temp를 지우고 `--clean`으로 연도
전체를 다시 계산하는 2차 폴백이 남아 있었다. 이 경로를 기본 금지했다.

- 첫 실행에서 temp가 없을 때만 MFA 초기화를 위한 `--clean`을 사용한다.
- temp가 있으면 같은 입력·alignment 계약을 검증한 뒤 `--clean` 없이 한 번 재개한다.
- 재개가 실패하면 temp, SQLite DB, interval CSV, heartbeat, stderr를 보존하고 중단한다.
- 전체 재계산은 연구자가 원인을 확인한 뒤 `-AllowFullCleanRetry`를 명시할 때만
  허용한다. 이때도 기존 temp는 삭제하지 않고 stale archive로 이동한다.
- 무인 연도 큐는 이 스위치를 의도적으로 전달하지 않는다.

MFA 자체가 단일 연도 SQLite 작업공간을 쓰므로 모든 내부 연산을 발화 단위로 완전히
재개한다고 주장할 수는 없다. 대신 실제로 재사용 가능한 코퍼스 로딩, MFCC, 학습
그래프, 정렬 interval, DB 체크포인트를 보존한다. DB 계산이 끝난 뒤 6-tier 수출이나
QC만 실패한 경우에는 정렬을 다시 하지 않고 출력/QC 단계만 재실행한다.

## 연도 큐의 상태

`run_mfa_year_queue_safe.ps1`은 연도마다 별도 상태를 원자적으로 기록한다.

| 상태 | 의미 | 재실행 시 행동 |
|---|---|---|
| `researcher_exclusion_review_required` | pending 제외 후보표 생성 완료 | 승인 계약을 만든 뒤 MFA 시작 |
| `mfa_failed_checkpoint_preserved` | MFA 또는 재개 실패 | temp·DB·로그를 유지하고 같은 지점에서 재개 시도 |
| `machine_qc_failed_outputs_preserved` | 정렬은 끝났으나 독립 감사/표본 재수출 실패 | 정렬 없이 QC·수출만 수정·재실행 |
| `machine_qc_passed_human_review_pending` | 계산과 기계 QC 통과 | 화자 5명 이상 연구자 표본 검토 대기 |

전체 상태는 다음에 기록한다.

```text
D:\mfa_eojeol\year_queue\<queue_id>\queue_state.json
```

읽기 전용 상태판은 `show_mfa_year_queue_status.ps1`이다.

전수 시작 직전에는 `preflight_mfa_year_queue.ps1`이 다음을 한 번에 검사한다.

- 공통 발음사전 r2/adoption 실물 SHA와 `allow_yearly_mfa`
- D: `DATA_SSD` 라벨과 55 GiB 이상 여유
- MFA/G2P/연도 큐 live lock
- 동결 search master와 6개 연도 세션 coverage
- stale temp·완료 marker·final staging 충돌
- 각 연도의 lab input contract와 그 ID에 묶인 연구자 승인 제외 계약
- PowerShell 정적 안전검사, 선택적 Python 전체 테스트, 추적 코드 커밋 여부

보고서의 `status=GO`일 때만 계산 큐를 시작한다. 이 preflight도 MFA 실행,
제외 승인, WAV 이동, 정본 승격을 수행하지 않는다.

## 실행 단계

### 1. 승인 후보표가 아직 없을 때

큐에 `-PrepareMissingReviews`를 주면 동결 search master를 준비하고 2020–2025의
입력 전수 감사·불량 WAV dry-run·pending 검토표를 만든다. 이 단계는 MFA를
자동 시작하거나 WAV를 이동하지 않는다.

### 2. 연구자 승인 계약이 준비된 뒤

연도별 승인 JSON을 다음 중 하나로 둔다.

```text
<ApprovedExclusionsRoot>\2020\approved_exclusions.json
<ApprovedExclusionsRoot>\approved_exclusions_2020.json
```

큐를 다시 실행하면 이미 성공한 단계는 marker와 실물을 재검증해 재사용한다. 각
성공 연도에 대해 독립 6-tier 전수 감사와 보존 DB의 24발화/5세션 이상 표본
재수출을 수행한다.

## 논문에서 주장할 수 있는 범위

이 설계는 2020–2025가 같은 동결 search master, 공통 발음사전, 음향모델,
phone inventory, alignment contract 생성 규칙, 6-tier schema, QC 규칙을 사용했다는
재현 근거를 만든다. 문제 발화를 자동으로 삭제하거나 성공으로 간주하지 않고 연도별
제외표와 상태표에 남긴다. 다만 자동 정렬 phone은 실제 음운 실현 판정이 아니며,
최종 연구 판정은 음성·TextGrid를 보는 연구자 절차에서 수행한다.
