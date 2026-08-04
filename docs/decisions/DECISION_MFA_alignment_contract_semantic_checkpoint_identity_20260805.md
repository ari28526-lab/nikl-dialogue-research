# MFA 정렬 계약의 의미 ID와 checkpoint 재개 파일 지문 정책

상태: 현행 생산 계약

적용 범위: 2021 v6 복구와 이후 2022–2025 정렬 계약 재사용

## 사건

2021 v6는 입력 전수 검증, WAV 1,416,216개 손상 검사, 12.7GB MFA DB
checkpoint 검증까지 통과한 뒤 2026-08-05 06:16:46 KST에
`alignment_contract_file` 지문 불일치 하나로 안전 중단됐다.

- 과거 v5 보고서의 계약 파일: 4,050바이트,
  SHA-256 `52176e384d635db7665e12c5ad76d14a1dd527acfc8ff95808d4ecdc7aeca662`
- v6가 재구성한 계약 파일: 4,050바이트,
  SHA-256 `a495bc78849de150ea986c45a1a6e26124355e21a4979c32f9dccd30276a7b9e`
- 현재 `recorded_at`: `2026-08-05T05:41:55+09:00`
- 저장된 정렬 계약 ID와 생성식으로 독립 재계산한 ID:
  `5ff1865744c85d982fc43708d7666f9af061cad833aa7fde04a09bef3238d5dd`
- 입력 ID, Python/MFA/Pynini 판본, acoustic/dictionary/G2P 내용 SHA,
  공통 발음 adoption, 정렬 제외 승인 계약은 모두 동일하다.

원인은 정렬 계약 생성기가 같은 의미 계약에도 실행 시각 `recorded_at`을 새로
쓰는 반면, 표적 복구 재개기가 과거 파일 전체 SHA의 동일성을 요구한 데 있다.
`recorded_at`은 설계상 정렬 계약 ID에 참여하지 않으므로 두 요구는 서로
모순됐다. MFA·phone·사전·입력·제외 기준 변화가 아니다.

## 결정

1. 같은 의미의 정렬 계약이 이미 있으면 파일을 다시 쓰지 않는다. 따라서
   재실행 시각만으로 계약 파일 SHA와 mtime을 바꾸지 않는다.
2. checkpoint 재개에서는 과거 계약 경로가 현재 계약 경로와 같은지 확인하고,
   현재 JSON에서 정렬 계약 생성기의 canonical identity를 독립 재구성한다.
3. canonical identity에는 연도, LAB 입력 계약, Python/MFA/Pynini 판본, 동결
   모델 묶음, pronunciation mode, 공통 발음 adoption, 정렬 제외 승인 SHA,
   acoustic/dictionary/G2P 이름·크기·내용 SHA가 모두 포함된다.
4. 위 identity의 SHA-256이 과거 실패 보고서·repair manifest·현재 파일의
   `alignment_contract_id`와 모두 같아야만 재개한다.
5. `recorded_at`, 모델 경로·mtime처럼 원래 ID 생성식에서 제외된 감사 필드는
   checkpoint 동일성 판정에서도 제외한다. 현재·과거 파일 지문은 최종 재개
   보고서에 함께 남긴다.
6. 저장 ID만 신뢰하지 않는다. 현재 문서의 canonical identity를 재계산해
   일치하지 않으면 fail-closed한다.

## 검증

- `recorded_at`만 바꿔 파일 SHA가 달라진 회귀 fixture: 재개 허용
- acoustic 의미 필드를 바꾸고 저장 ID를 그대로 둔 fixture: 재개 차단
- 의미 계약이 같은 두 번째 write: 기존 파일 byte 보존
- 실제 2021 계약: `semantic_match=true`, 저장 ID=재계산 ID=`5ff186…`
- 관련 시험 8/8, Python 전체 348/348 통과
- PowerShell 안전 46파일, Windows PowerShell 5.1 호환 55스크립트 통과

## 재개 범위

v6 실패는 동반표 생성 전 계약 gate에서 발생했다. 원본 WAV/CSV, 검색표,
2020 완성본, 2021 DB와 1,371,883개 6-tier partial은 변경하지 않았다. 다음
실행은 MFA나 6-tier 전수 생성을 반복하지 않고 v5 전수 checkpoint+19개 repair
manifest를 다시 검증한 뒤 동반표부터 재개한다. 독립 연도 전수 감사와 DB
표본 24개 재수출은 그대로 남는다.
