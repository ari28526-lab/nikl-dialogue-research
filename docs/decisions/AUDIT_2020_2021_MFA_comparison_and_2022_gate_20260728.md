# 2020·2021 MFA 비교와 2022 진입 결정

작성일: 2026-07-28
상태: **2020·2021 사후 감사 완료, 2022 기술 gate 통과, 전량 실행 보류**

## 결정 요약

1. 2020과 2021 final 4-tier는 모두 구조 감사에 통과했으므로 baseline
   결과로 보존한다.
2. 2021 direct DB 경로는 2020 raw export+merge 경로보다 final 생성 시간을
   약 17시간 40분에서 1시간 46분으로 줄였다.
3. 2021은 DB integrity와 DB 재추출 동등성까지 확보했다. 2020은 temp와 DB가
   이미 없어 같은 수준의 재현 증거를 추가로 만들 수 없다.
4. 2022는 직전 연도 QC gate와 자체 환경 preflight를 모두 통과했다.
5. 그러나 2020–2025 공통 발음사전/G2P cache와 우리말샘 예외 발음 정책을
   먼저 파일럿할지 결정하기 전에는 2022 전량을 시작하지 않는다.
6. 2021 temp의 31.365GiB는 정리 후보로만 확정했고, 사용자 승인 전에는
   실제 삭제하지 않는다.

## 같은 감사 기준으로 본 결과

| 항목 | 2020 | 2021 |
|---|---:|---:|
| LAB | 869,840 | 1,373,521 |
| 원천 음성 사용 불가 제외 | 14 | 1,109 |
| 분석 가능 LAB | 869,826 | 1,372,412 |
| final 4-tier | 866,196 | 1,371,868 |
| 유효 final 4-tier | 866,196 | 1,371,868 |
| invalid 4-tier | 0 | 0 |
| 분석 가능 정렬 실패 | 3,630 | 544 |
| 분석 가능 coverage | 99.5827% | 99.9604% |
| DB 보존 | 없음 | 12,455,149,568바이트 |
| DB integrity | 불가능 | `ok` |
| DB 재추출 표본 | 불가능 | 24세션 24/24 exact |

2021은 자료량이 약 1.58배인데도 분석 가능 정렬 실패 절대수는 3,630에서
544로 줄었다. 실패율은 약 0.4173%에서 0.0396%로 약 10.5배 낮아졌다.
이는 2021 direct export가 정렬 자체를 개선했다는 뜻만은 아니다. 입력계약,
LAB 검증, source 결함 분리, runner 재시도·회계가 함께 달라졌으므로
“파이프라인 전체 개선 효과”로 해석해야 한다.

## 2020에서 확인된 한계

2020 final 866,196개는 모두 유효하지만 다음 한계가 남는다.

- `D:\mfa_tmp\2020`과 `2020.db`가 이미 없음
- DB integrity·direct 재추출 검증 불가능
- CSV–WAV duration 대응 실패 59세션
- residual mismatch 15,074행
- search master에서 기대한 WAV 없음 544건
- 2020 WAV의 평면/세션 구조 이력 때문에 현재 strict preflight와 구조가 다름
- 정렬 실패 3,644건 중 원천 결함 제외 14, 분석 가능 난정렬 3,630

따라서 2020 final은 연구용 baseline으로 보존하되, 공통 발음사전 release로
재정렬할 때는 현재 2021 안전 절차를 처음부터 적용한다.

## 속도 비교

2020 구 경로:

```text
MFA raw 2-tier TextGrid export 약 15시간 57분
  + 별도 4-tier merge 약 1시간 43분
  = final 생성 후처리 약 17시간 40분
```

2021 direct 경로:

```text
SQLite word/phone interval
  → 기존 형태소 경계+동결 form 결합
  → final 4-tier 직접 생성 6,360.292초
  = 약 1시간 46분
```

final 생성 단계만 비교하면 약 10배 빠르고, 약 15시간 54분을 줄였다.
이것이 현재 코드에서 가장 큰 확정적 가속이다.

반면 2021 MFA 본 계산은 62,149.774초, 약 17시간 16분이었다. 주요 병목은
G2P, MFCC/feature, graph, alignment, interval collect/DB 적재다. direct
export는 이 계산을 없애지 않으며, raw TextGrid를 썼다가 다시 읽는 중복 I/O를
없앤 것이다.

사후 QC도 비용이 있다.

| 사후 단계 | 2020 | 2021 |
|---|---:|---:|
| readiness | 1,341.858초 | 1,302.552초 |
| 4-tier 전수 감사 | 1,738.805초 | 2,178.632초 |
| SQLite full integrity | 불가능 | 4,255.2초 |
| DB 재추출 표본 | 불가능 | 106.628초 |

2020 4-tier 감사에서는 여러 구간에 2분 안팎 I/O 장기 꼬리가 있었다.
2021 감사의 최종 누적 처리율 약 630개/초보다 2020은 약 498개/초로
느렸다. 소형파일 배치와 디렉터리 접근 지연도 별도 병목이다.

## tier 경계 결정

두 연도 모두 모든 tier가 0초부터 WAV `xmax`까지 gap·overlap 없이 연속이다.
따라서 tier 자체의 처음/끝 경계 누락은 없다.

모든 운영본에 50ms 이상의 눈에 보이는 빈 경계를 강제하지는 않는다. 실제
WAV에 그만큼의 무음이 없으면 TextGrid 시간만 늘릴 수 없기 때문이다.

연결 청취·연구자 검토용 사본에서는 다음처럼 처리한다.

```text
원 WAV와 canonical TextGrid 읽기 전용
  → WAV 좌우 0.05초 padding
  → 모든 tier 시간 동시 이동
  → review bundle에만 가시적 빈 경계 보장
```

canonical 운영본과 padded review 사본을 섞지 않는다.

## 2022 기술 gate

직전 연도 결합 gate:

```text
outputs/reports/PREFLIGHT_2022_after_2021_QC_20260728.json
status=passed
20/20 checks passed
```

2022 환경 preflight:

```text
logs/preflight_20260728_070125.log
FAIL 0 / WARN 0
```

확인한 내용:

- MFA 3.4.0 프로젝트 패치 10/10
- acoustic/dictionary/G2P `korean_mfa` 모델 존재
- D: 라벨 `DATA_SSD`
- D: 여유 264.1GB
- 2022 WAV 세션 구조 정상
- 동결 search master build success
- 2022 CSV 세션 2,654/2,654
- reference-form 필수 열 존재
- 2022 temp/output/marker 없음

## 방법론 gate: 공통 발음 자원

기술 gate와 방법론 gate를 구분한다.

현재 baseline 명령을 바로 실행하면 2022도 기본 `korean_mfa` 사전과
연도별 residual G2P를 사용한다. 반면 공통 어휘/G2P cache와 우리말샘 예외
발음 파생사전을 채택하면 다음 장점이 있다.

- 2020–2025의 같은 OOV를 연도마다 다시 G2P하지 않음
- 예외 발음의 출처·품사·의미·사전 ID를 versioned 정본으로 보존
- 연도 간 동일한 발음 후보 집합과 model/dictionary fingerprint 사용
- 긴 G2P 꼬리 감소 가능

다만 예외 발음 후보가 달라지면 2020·2021과 2022 이후가 서로 다른
발음사전 release를 쓰게 된다. 방법론 일관성을 중시하면 먼저 공통 사전
A/B 파일럿을 하고, 채택 시 2020·2021도 새 release로 재정렬해야 한다.

상세 설계:

```text
docs/decisions/DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md
```

따라서 현재 판정은 다음과 같다.

```text
기술 상태: GO
방법론 상태: HOLD — 공통 발음사전 파일럿 여부 사용자 결정 대기
2022 전량: 시작하지 않음
```

## 승인 뒤 baseline 2022 명령

공통 발음사전 파일럿을 먼저 하지 않고 현재 baseline으로 2022를 실행하기로
확인한 경우에만 아래 명령을 사용한다.

```powershell
Set-Location "C:\Users\ari30\research\2026_summer_research"

$gate = Get-Content `
  ".\outputs\reports\PREFLIGHT_2022_after_2021_QC_20260728.json" `
  -Raw -Encoding UTF8 | ConvertFrom-Json
$integrity = Get-Content `
  ".\outputs\reports\SQLITE_integrity_2021_pre_mfa_v1_20260728.json" `
  -Raw -Encoding UTF8 | ConvertFrom-Json
$sample = Get-Content `
  ".\outputs\reports\VERIFY_db_4tier_sample_2021_20260728.json" `
  -Raw -Encoding UTF8 | ConvertFrom-Json

if (
  $gate.status -ne "passed" -or
  $gate.prior_year -ne "2021" -or
  $gate.next_year -ne "2022" -or
  $integrity.status -ne "success" -or
  $integrity.result -ne "ok" -or
  $sample.status -ne "success"
) {
  throw "2021 QC gate가 완전하지 않아 2022를 시작하지 않음"
}

& "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "pre_mfa_v1_20260725" `
  -Years 2022 `
  -PreferD `
  -UseDirectDbExport `
  -SkipSearchMasterBuild

if ($LASTEXITCODE -ne 0) {
  throw "2022 MFA가 실패 또는 안전 차단됨(exit=$LASTEXITCODE)"
}
```

의도적으로 넣지 않은 옵션:

- `-CleanupDirectDbAfterMerge`: DB를 QC 전에 지우지 않음
- 다년 `-Years`: 한 연도만 실행
- 정본 자동 승격: staging 전수 QC 전에는 하지 않음

## 2021 저장공간 정리

dry-run:

```text
outputs/reports/PLAN_2021_cleanup_dry_run_20260728.json
status=ready_for_user_review
```

| 분류 | 파일 | 바이트 | GiB |
|---|---:|---:|---:|
| 정리 후보 | 63 | 33,677,552,748 | 31.365 |
| DB critical 보존 | 1 | 12,455,149,568 | 11.600 |
| 재현 근거 보존 | 41 | 986,843,928 | 0.919 |
| 합계 | 105 | 47,119,546,244 | 43.883 |

가장 큰 후보는 네 개의 `alignment/fsts.korean_mfa.*.ark`
각 약 4.34–4.38GiB, `phone_intervals.csv` 약 3.12GiB, 네 개의
`final_features.*.ark` 각 약 1.04GiB다.

dry-run 도구는 삭제 기능이 없고 실제 삭제도 0건이다. 정리 후보 manifest를
사용자가 확인하고 명시적으로 승인하기 전에는 파일을 이동하거나 삭제하지
않는다.

## 코드 검증

최종 후속 변경 전체에 대해 다음을 통과했다.

```text
Python unittest             88 tests, OK
PowerShell safety           5 files, PASS
git diff --check            PASS
20260728 QC JSON parse      10/10
```
