# MFA 체크포인트 감사 LAB 루트 계약 교정

## 결론

`resume_mfa_year_checkpoint_qc.ps1`에서 독립 연도 감사기에 전달하는
`--lab-root`는 연도 폴더가 아니라 연도 상위 WAV/LAB 루트여야 한다.
감사기는 받은 루트 아래에 `$Year`를 자체 결합한다. 이 규칙은 2021에만
해당하는 예외가 아니라 2021–2025 공통 생산 계약이다.

## 2020에서는 나타나지 않은 이유

2020 Gate B는 `run_eojeol_realign.ps1`의 본 생산 경로에서 독립 감사를
호출했다. 이 경로는 이미 상위 `$wavRoot`를 전달한다. 2021은 후처리 수리
뒤 완성 체크포인트만 승격하고 감사를 재개하기 위해 새로 추가한
`resume_mfa_year_checkpoint_qc.ps1`을 처음 사용했다. 이 재개 스크립트만
`$yearWavRoot`를 넘겨 감사기가 `...\2021\2021`을 조회하게 했다.

## 실패 증거와 판정

- 실패 시각: 2026-08-05 09:46 KST
- 감사 소요: 2,344.98초
- 잘못 조회한 경로: `D:\20_AUDIO\03_wav\individual\2021\2021`
- 오인 결과: active LAB 0건, TextGrid 1,371,883건 전부 `wav_missing`
- 동반표는 utterance 1,371,883행, word 10,572,619행,
  phone 39,296,691행, 승인 제외 2,037행으로 manifest와 일치했다.
- 표 SHA, 행 수, 중복 키, 키 순서, phone inventory, `spn` 검사에서는
  별도 오류가 없었다.

따라서 이것은 2021 MFA·TextGrid·CSV 산출물 결함이 아니라 독립 감사
호출부의 경로 계약 결함이다. 2021 정렬, 6-tier, 동반표를 다시 만들지
않고 감사와 DB 표본 24건만 재실행한다.

## 재발 방지

1. 재개 스크립트는 감사기에 공통 `$wavRoot`만 전달한다.
2. 실행 전 `$wavRoot\$Year`에서 실제 `.lab` 한 건을 읽지 못하면 즉시
   중단한다.
3. 감사기 자체도 연도 LAB이 0건이면 TextGrid 137만 건을 읽기 전에
   작은 `lab_year_empty` 실패 보고서를 남기고 끝낸다.
4. 감사기의 콘솔 출력은 전체 ID 목록 대신 상태·개수·보고서 경로만
   보여준다.
5. PowerShell 안전성 검사에서 `--lab-root $yearWavRoot` 회귀를 금지한다.

## 보존 범위

2021 완료 checkpoint, MFA DB, 6-tier, 동반표는 보존되었다. 원본 WAV/CSV와
2020 완성본은 변경하지 않았다. 실패 요약은
`outputs/reports/FAIL_2021_checkpoint_audit_lab_root_contract_20260805.json`
에 기록한다.
