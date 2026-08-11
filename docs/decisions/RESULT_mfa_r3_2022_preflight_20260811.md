# 2022 r3 장시간 MFA 직전 GO 결과

기록일: 2026-08-11 KST

## 결론

2020·2021 완료본을 다시 계산하거나 수정하지 않고 2022 한 연도의 WAV source
snapshot, exact-ID 입력 계약, 발음 연구 DB, alignment contract와 실제 runner
preflight를 완료했다. 최종 preflight는 `status=go`, `failed_checks=[]`다. 이
시점에는 2022 corpus 물질화·MFA·TextGrid 수출을 시작하지 않았다.

## 2021 동결 근거

- 최종 완료 집계: `status=passed`, SHA-256
  `280dc379577f1c8d368e646b78e9141bb762501a63802a9a6721408e17ffbc7a`
- 최종 `QC_STATE.json`: SHA-256
  `b4b8dac11c3f7794a6579a7199faf4347a31e684ea17c56ed66cdc2e54a5c12a`
- `ALIGN_DONE_2021.json`: SHA-256
  `71412e455ad1bbd1f58904cb348573ba1e845c8d386f712c9320b264734c1c1c`
- 6-tier 1,206,862개, 승인 후속 437건, 전수 QC 100%, hard failure 0,
  DB 재수출 semantic·byte 24/24
- 이번 준비에서 2021 MFA·전수 수출·QC·원자료를 재실행하거나 수정하지 않았다.

## 2022 입력과 연구 DB

- source 발화: 866,359
- WAV source snapshot: 878,157개, source 밖 WAV 11,798개는 기록만 하고 입력으로
  암묵 선택하지 않음
- pronunciation-safe: 752,591
- pronunciation follow-up: 113,768
- safe 집합에 실제 적용된 pre-MFA 기술 제외: 870
- 장시간 MFA exact-ID 입력: 751,721
- source WAV 누락: 0
- 과거 r2 post-MFA 실패 438건 중 r3 입력 조건을 충족한 337건은 새 정렬에 재진입
- year input contract ID:
  `9da932e4480b7e109b44b43f27c335b78c17e6f4466aad5a5d8acd0390facea2`
- 발음 연구 DB: 866,359발화·4,504,375 reference-eojeol occurrence
- 결합 키: `(year, utt_id, reference_eojeol_idx)`
- 독립 감사: `passed`, unknown nonempty LAB token 0, 미회계 발화 0

## 정렬 계약과 preflight

- alignment contract ID:
  `f53b6c2be25fc4e694796ae123c005258ee9913a4b6bf4cf6625220dec4113cb`
- acoustic v3.3.0, Jamo G2P v3.2.0, r3 공통사전의 경로·크기·SHA를 2020·2021과
  같은 단일 release에 결속함
- 구 r2 DB·interval·marker 재사용: 금지
- PowerShell safety 68파일, Windows PowerShell 5.1 runtime 68스크립트 통과
- Python 전체 suite 556시험 통과
- 실제 runner preflight: `go`, 실패 검사 0
- 공간 산식: 필요 52.193 GiB, 관측 D: 여유 114.028 GiB
- 전환 Gate:
  `outputs/reports/GATE_mfa_r3_2021_TO_2022_20260811.json`

## 중단·재개 기록

연구 DB wrapper를 Codex 관찰 셸에서 실행했을 때 10분 관찰 제한에 도달했다. DB
builder는 이미 최종 manifest를 생성했고 wrapper와 독립 auditor는 계속 살아
있었다. 중복 실행·lock 이동·DB 재생성을 하지 않고 살아 있는 PID를 확인해 그대로
기다렸다. 13:33 KST에 감사 `passed`와 lock 정상 해제를 확인했다.

첫 runner preflight는 alignment audit의 **실행일** 파일명 `_20260811`을 사용해,
runner가 요구하는 **release 정본명** `_20260809`를 찾지 못하고 안전 중단됐다.
MFA·corpus·DB 변경은 없었다. 동일 통과 감사 결과를 release 정본 경로에 다시
기록하고 preflight만 재실행해 GO를 받았다. 이후 연도도 alignment audit 파일명은
실행일이 아니라 release ID의 날짜를 사용한다.

## 다음 허용 동작

연구자가 장시간 PowerShell 창에서 다음 단일 runner를 한 번 실행한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_year_safe_body.ps1" `
  -Year 2022 -NumJobs 4
```

동시에 같은 명령을 두 번 실행하지 않는다. 실패·중단 시 corpus·temp·DB를 지우지
않고 상태판과 로그를 먼저 확인한다. 2020·2021은 재실행하지 않는다.
