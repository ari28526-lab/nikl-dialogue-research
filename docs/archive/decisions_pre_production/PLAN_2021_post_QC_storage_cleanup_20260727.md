# 2021 MFA 완료 후 저장공간 정리 계획 (완료·대체된 기록)

작성일: 2026-07-27
최종 갱신: 2026-07-28
상태: **2021 산출 완료·전수 QC 진행 중 — 사용자 승인 전 삭제 금지**

## 현재 용량 기준선

2026-07-27 21:42, 실행 중 읽기 전용 확인:

```text
D: DATA_SSD
전체       953.85 GB
사용       661.00 GB
여유       292.85 GB
여유율      30.7%
```

2021 본 실행 및 direct DB 4-tier export를 마친 뒤 2026-07-28 04:26에
다시 확인한 여유 공간은 283,624,550,400바이트(약 264.15GiB)다. 2021
결과 자체는 수용했지만, 연도별 MFA 전체 temp를 계속 누적하면 2022–2025
수행 중 불필요하게 여유가 줄어든다.

기본 보존 정책은 다음과 같다.

> 현재 처리 중인 연도만 전체 resume temp를 유지하고, 전수 QC가 끝난 이전
> 연도는 재현 증거·SQLite DB·최종 결과를 남긴 compact 상태로 전환한다.

## 전수 QC 중 절대 정리하지 않는 이유

2021 MFA와 direct DB 4-tier export는 2026-07-28 완료됐다. 그러나 독립
4-tier 전수 감사, SQLite integrity 검사, DB-TextGrid 고정 표본 동등성 및
2022 선행 gate가 아직 남아 있다. 지금 `D:\mfa_tmp\2021`의 일부라도 지우면
감사 실패 원인을 추적하거나 direct export를 재현할 경로를 잃을 수 있다.

따라서 현재는 다음을 금지한다.

- `D:\mfa_tmp\2021` 안의 파일·하위 폴더 삭제·이동·압축
- SQLite DB vacuum·변경·복사 중 원본 교체
- `.ark`, `.scp`, graph, alignment 중간 파일의 선택 삭제
- align/merge marker를 미리 만들거나 수정
- final staging을 완료 결과로 간주한 수동 이동

## 반드시 보존할 자료

2021 QC가 끝난 뒤에도 다음은 정리 대상이 아니다.

1. 원 WAV와 원 코퍼스
2. 동결 pre-MFA search master와 `_build_meta.json`
3. 현재 입력계약의 `.lab`
4. 형태소 원천 TextGrid
5. final 4-tier `words/phones/morphemes/utterance` TextGrid
6. `2021.db`와 SHA256·크기·SQLite integrity 결과
7. lab·정렬 계약, temp contract, align/merge marker
8. MFA stderr·heartbeat·job log와 direct export 보고서
9. readiness·4-tier 전수 감사와 누락/분류 inventory
10. 사용한 Git commit·MFA/Pynini·모델 fingerprint

SQLite DB `D:\mfa_tmp\2021\2021.db`는 12,455,149,568바이트
(약 11.60GiB)이다. 작지 않은 파일이지만 raw 2-tier export 없이 baseline
4-tier를 다시 생성할 수 있는 핵심 증거이므로 보존 대상으로 고정한다.

## QC 뒤 정리 후보

정확한 파일은 완료 후 inventory에서만 확정한다. 현재 단계에서 wildcard나
경로명만 보고 삭제하지 않는다.

후보 범주는 다음처럼 **입력과 최종 결과에서 재계산 가능한 대형 중간물**이다.

- MFCC 및 final feature archive
- corpus split의 파생 feature 목록
- training graph archive
- first-pass/final alignment의 임시 archive
- 완료 뒤 더 이상 resume에 쓰지 않는 기타 Kaldi 작업 파일

DB, 계약, 로그, final TextGrid가 이 목록에 섞이면 정리를 중단한다.

## 실행 전 hard gate

다음 조건이 모두 충족돼야 dry-run을 만들 수 있다.

1. MFA process exit 0
2. direct export report `status=success`
3. 같은 입력·정렬 계약의 align/merge marker 존재
4. final 2021 staging 존재
5. 독립 4-tier 감사 coverage 99% 이상, hard failure 0
6. 누락·형태소 결측이 발화별 inventory와 분류표로 100% 설명
7. SQLite `PRAGMA integrity_check=ok`
8. DB에서 다시 뽑은 고정 표본과 final TextGrid의 tier·label·시간 동등
9. 보존 대상 SHA256 manifest 생성
10. 2022 선행 QC gate 통과

하나라도 실패하면 전체 temp를 그대로 보존한다.

## dry-run과 사용자 승인

완료 후 먼저 다음 보고서만 만든다.

```text
outputs/reports/INVENTORY_2021_post_mfa_storage_*.json
outputs/reports/PLAN_2021_cleanup_dry_run_*.json
```

이를 위해 삭제·이동 기능이 아예 없는
`scripts/python/inventory_mfa_storage.py`를 준비했다. 2021 독립 QC와 2022
선행 gate가 통과한 보고서를 입력으로 요구하며, 다음 조건에서는
`status=blocked`로 끝난다.

- QC gate가 없거나 `passed`가 아님
- gate의 prior year 또는 retained DB 경로가 현재 2021 temp와 다름
- `2021.db-journal`, WAL, SHM 등 활성 transaction 흔적이 남음
- 자동 정책에 없는 미분류 파일이나 symlink/reparse 경계가 있음
- retained `2021.db`가 없거나 0바이트임

통과해도 결과는 `ready_for_user_review`일 뿐이며
`deletion_performed=false`, `apply_supported=false`,
`authorization_required_for_any_cleanup=true`를 고정한다. 즉 이 도구만으로는
어떤 파일도 정리할 수 없다.

2021 QC와 2022 선행 gate가 끝난 뒤 실행할 명령:

```powershell
& "C:\Users\ari30\miniforge3\envs\mfa\python.exe" `
  ".\scripts\python\inventory_mfa_storage.py" `
  --year 2021 `
  --temp-year "D:\mfa_tmp\2021" `
  --qc-gate-report `
    ".\outputs\reports\PREFLIGHT_2022_after_2021_QC_20260727.json" `
  --output `
    ".\outputs\reports\PLAN_2021_cleanup_dry_run_20260727.json" `
  --hash-db

if ($LASTEXITCODE -ne 0) {
  throw "2021 저장공간 inventory가 정리 검토 가능 상태가 아님"
}
```

보고서는 파일별 또는 안전한 범주별로 다음을 명시한다.

- 절대경로
- 파일 수
- 현재 바이트
- 보존/정리 후보
- 재생성 근거
- 예상 회수 GB
- 삭제 뒤 남는 DB·계약·결과 경로

사용자가 목록과 예상 회수량을 승인하기 전에는 실제 정리 명령을 실행하지
않는다. 승인 뒤에도 workspace·드라이브 루트·연도 상위 루트를 재귀 삭제하지
않고, manifest에 적힌 정확한 2021 파생 경로만 검증한 후 처리한다.

## 연도별 운영 정책

2022부터는 다음 순서를 반복한다.

```text
한 연도 실행
  → direct export
  → 전수 QC
  → 다음 연도 GO gate
  → 사용자 승인
  → 직전 연도 temp compact
  → 다음 연도 시작
```

이 방식이면 모든 연도의 full temp를 동시에 쌓지 않고도 baseline DB와 연구
결과를 보존할 수 있다. 공통 발음사전 채택으로 2020·2021을 새 release로
재정렬하더라도 기존 final 결과·DB는 baseline으로 남기고, 새 run ID·계약과
섞지 않는다.

## 현재 결정

- 2021 전수 QC 중 정리: **금지**
- 2021 완료 직후 자동 정리: **금지**
- 완료·전수 QC·2022 선행 gate 후 inventory/dry-run: **실행**
- 실제 정리: **사용자 승인 뒤**

이 결정은 2026-07-28 사용자와 다시 확인했다. 현재 작업은 삭제가 아니라
보존 대상과 재계산 가능한 후보를 구분하는 인벤토리 준비까지만 포함한다.

## 2026-07-28 실제 dry-run 결과

2021 전수 QC, SQLite integrity, DB 재추출 표본 및 2022 선행 gate를
통과한 뒤 다음 보고서를 생성했다.

```text
outputs/reports/PLAN_2021_cleanup_dry_run_20260728.json
status=ready_for_user_review
deletion_performed=false
apply_supported=false
```

| 분류 | 파일 | 바이트 | GiB |
|---|---:|---:|---:|
| 정리 후보 | 63 | 33,677,552,748 | 31.365 |
| DB critical 보존 | 1 | 12,455,149,568 | 11.600 |
| 재현 근거 보존 | 41 | 986,843,928 | 0.919 |
| 합계 | 105 | 47,119,546,244 | 43.883 |

현재 D: 여유 264.146GiB를 기준으로 후보를 모두 정리하면 약 295.511GiB가
예상된다. 가장 큰 후보는 `alignment/fsts.korean_mfa.1–4.ark`,
`phone_intervals.csv`, `final_features.1–4.ark`다.

첫 dry-run에서 확장자 없는 `alignment/tree`가 미분류로 차단됐다. 실물을
확인해 Kaldi alignment model의 재현 근거로 보존하도록 exact-path 정책과
회귀시험을 추가했다. 콘솔 CP949가 긴 대시를 출력하지 못한 오류도 UTF-8
재설정과 간결 요약 출력으로 수정했다. 두 번째 실행은 blocker 0으로
끝났다.

2020에서는 `D:\mfa_tmp\2020`과 `2020.db`가 이미 없어 integrity·재추출
증거를 추가로 만들 수 없었다. 이 시행착오 때문에 2021 DB는 용량이
11.60GiB여도 보존한다.

아직 실제 파일을 삭제하거나 이동하지 않았다. exact 후보 manifest와
예상 회수량에 대한 사용자 명시 승인이 다음 단계다.
