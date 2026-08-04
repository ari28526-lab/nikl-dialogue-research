# 2021 TextGrid 종단 경계 19건 표적 복구와 checkpoint 재개 결정

상태: 생산 복구 계약 — 표적 복구 적용·해시 재검증 완료, checkpoint 재개 직전

적용 범위: 2021 공통 Jamo r2 direct-DB 6-tier 부분 산출물

## 사건

2021 v5는 보존 MFA DB에서 4,139개 세션을 끝까지 검사하여 다음을 확인했다.

- DB 발화: 1,372,394
- 정렬·분석 대상: 1,371,883
- 승인된 DB 내 비활성 제외: 511
- 기존 파일 검증 통과: 1,371,858
- v4에서 만들지 못했던 파일 생성: 6
- 기존 파일 검증 실패: 19
- `spn`: 0
- exact-ID reconciliation: 통과

19건 때문에 동반표 생성 전 안전 중단됐고 2022는 시작되지 않았다. 12.7GB DB,
부분 TextGrid, 원본 WAV/CSV, 2020 완성본은 보존됐다.

## 원인 증명

`outputs/reports/DIAG_2021_v5_textgrid_mismatches_20260805.json`에서 19건을 현재
DB·검색표로 재구성해 비교했다.

- 19/19가 commit `f205d32` 이전의 TextGrid 생성 규칙으로 정확히 재현됐다.
- 모든 어절·phone·음소·발화·로마자·형태소 라벨이 보존됐다.
- 차이는 발화 종단의 float32 DB 시간과 WAV frame 기반 xmax 사이
  0.000000656–0.000006714초뿐이다.
- 구규칙은 이 차이를 짧은 빈 종단 interval로 물질화했다. 신규 규칙은 같은
  WAV 길이의 float32 표현으로 증명되는 경우에만 정확한 xmax로 맞춘다.
- 19개는 2021 v4가 01:20–02:41 KST에 생성한 기존 파일이며, MFA 정렬 내용이나
  공통사전·음향모델·phone 기준의 차이가 아니다.

따라서 이 사건은 정렬 재계산 대상이 아니라 파생 TextGrid 직렬화 정책 전환에서
생긴 기존/신규 산출물 혼합이다.

## 결정

1. 2021 MFA를 다시 계산하지 않는다.
2. 19개 기존 TextGrid를 각각 SHA-256과 상대경로를 보존해
   `D:\mfa_eojeol\repair_archive\2021_float32_terminal_roundoff_20260805`에
   먼저 복사·검증한다.
3. 같은 DB interval과 동결 검색표에서 새 6-tier를 임시 파일로 만들고 검증한
   뒤, 해당 19개 파생 TextGrid만 원자적으로 교체한다.
4. 실패한 v5 전수 보고서의 1,371,858개 통과와 6개 생성 증거, 19개 repair
   manifest의 exact-ID·해시·검증 증거가 모두 일치할 때만 동반표 단계부터
   재개한다.
5. 이 checkpoint 재개는 독립 전수 감사를 생략하지 않는다. 연도 폴더 승격 뒤
   `audit_mfa_research_6tier_year.py`가 모든 최종 TextGrid를 다시 검사하고,
   DB 표본 24개 재수출 비교를 별도로 수행한다.
6. 독립 감사와 표본 검토 전에는 2022를 시작하지 않는다.

## 안전 불변식

- 2020 완성본, 원본 WAV, 원본/검색 CSV, MFA DB는 수정하지 않는다.
- repair 대상은 실패 보고서의 완전한 19개 집합과 정확히 같아야 한다.
- 실패 목록이 100개 예시 한도를 넘어 잘렸거나 중복·빈 ID가 있으면 재개를
  거부한다.
- 이전 실패 보고서, 정렬 계약, input contract, 음향모델, DB, search root,
  output root, repair 후 파일, archive 파일의 fingerprint가 하나라도 다르면
  재개를 거부한다.
- 기존 파일 전체를 자동 덮어쓰거나 `--clean` MFA를 수행하지 않는다.
- 복구 도중 중단되면 파일별 archive와 진행 manifest로 이미 완료된 19개 중
  일부를 판별해 재개한다.

## 보고 수치 해석

`float32_boundary_normalization.utterances_adjusted`는 DB 종단값을 예상 산출물로
구성하면서 메모리 안에서 정확한 xmax로 맞춘 발화 수다. 기존 파일 전체를
덮어썼다는 뜻이 아니다. 최종 보고서에는 이 측정 범위와 실제 표적 교체 파일 수
19를 별도로 기록한다.

## 검증

- 표적 복구·checkpoint 단위/통합 검사: 20/20 통과
- Python 전체 회귀검사: 347/347 통과
- PowerShell 안전검사: 46개 파일 통과
- Windows PowerShell 5.1 실행 호환검사: 55개 스크립트 통과
- 실제 데이터 mutation 전 preflight: 19건, 12세션, 최대 6.713867µs, `READY`

## 적용 결과 (2026-08-05 05:22 KST)

- 실패 보고서의 완전한 19개 집합만 표적 복구했다.
- 이전 파생 TextGrid 19개는 원래 상대경로를 유지해
  `D:\mfa_eojeol\repair_archive\2021_float32_terminal_roundoff_20260805`에
  먼저 보관했다.
- 교체 후 19/19가 신규 경계 정책 검증을 통과했고 repair manifest 상태는
  `success`다.
- manifest 기록을 다시 읽어 보관본 SHA-256 19/19와 현재 교체본 SHA-256
  19/19를 실제 파일에서 재계산했으며 불일치는 0건이었다.
- 변경 범위는 부분 산출물 TextGrid 19개뿐이다. 2021 MFA DB, 원본 WAV/CSV,
  검색표, 2020 완성본은 변경하지 않았다.
- 적용 증거는
  `outputs/reports/REPAIR_2021_float32_terminal_roundoff_20260805.json`이다.

다음 실행은 전수 MFA나 전수 TextGrid 재생성이 아니라 v5 전수 통과 증거와 위
repair manifest를 재검증한 뒤 동반표 생성부터 재개한다. 이후 독립 연도 전수
감사와 DB 표본 24개 재수출은 예정대로 수행한다.
