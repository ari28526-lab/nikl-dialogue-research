# MFA float32 종단 경계 정규화 결정

상태: 현행 생산 계약

적용 범위: 2021–2025 공통 Jamo r2 direct-DB 6-tier export와 동반표

## 발견 경위

2021 v4 direct export는 2026-08-05 02:56 KST에 4,139세션 전부를 순회한 뒤
1,371,883개 분석 대상 중 6개를 `0-xmax` 범위 초과로 안전 차단했다. 보존 MFA
DB, 이미 만든 1,371,877개 부분 TextGrid, 원본 WAV/CSV, 2020 완성본은 변경되지
않았고 2022도 시작되지 않았다.

실패한 6개의 word와 phone 마지막 `end`는 WAV 길이보다 1.2207–6.7139µs 컸다.
모두 16kHz WAV였으므로 차이는 0.0195–0.1074샘플이며, 각 값은 같은 WAV
길이를 IEEE-754 float32로 표현한 값과 정확히 일치했다. 이는 음성 경계의 언어학적
차이나 정렬 실패가 아니라 MFA interval 저장 정밀도와 WAV 프레임 기반 double
duration 사이의 표현 차이다. 전수 근거는
`outputs/reports/DIAG_2021_float32_terminal_roundoff_20260805.json`에 보존한다.

## 확정 정책

1. 일반적인 시간 허용오차를 넓히지 않는다.
2. 각 WAV duration의 가장 가까운 float32 표현과 정확한 duration의 차이에
   0.1µs 비교 여유를 더한 값만 그 파일의 동적 허용치로 사용한다. 최소 허용치는
   기존과 같은 1µs다.
3. begin이 위 허용치 안에서 0에 가깝거나 end가 위 허용치 안에서 xmax에 가까운
   경우에만 각각 정확한 0 또는 xmax로 정규화한다.
4. 위 동적 허용치를 넘는 음수 begin 또는 xmax 초과 end는 계속 hard failure다.
   내부 overlap과 gap 검사 기준도 바꾸지 않는다.
5. TextGrid와 `word_intervals_mfa.csv.gz`·`phone_intervals_mfa.csv.gz`는 동일하게
   정규화된 경계를 사용한다. 서로 다른 시간값을 연구 자료로 배포하지 않는다.
6. 최종 exporter 보고서는 조정 발화 수, 경계 수, 최대 조정량, 허용치와 예시 ID를
   `float32_boundary_normalization`에 기록한다. 조정은 숨겨진 수정이 아니다.

## 채택하지 않은 처리

- 6개를 기술적 제외로 넘기지 않는다. 실제 정렬 interval이 존재하고 WAV와의 차이가
  1샘플보다 훨씬 작으며 원인이 수치 표현으로 증명됐기 때문이다.
- 2021 MFA를 다시 정렬하지 않는다. 음향모델·공통사전·phone·정렬 경계의 문제가
  아니다.
- 0.1ms 같은 고정 광역 tolerance를 사용하지 않는다. 파일별 float32 표현으로
  설명되지 않는 실제 범위 오류까지 통과시킬 수 있기 때문이다.

## 재개 조건

- 실제 6개가 새 정책으로 정확한 WAV xmax에 대응함을 확인한다.
- 관련 단위·통합 테스트와 Python 전체 테스트를 통과한다.
- Windows PowerShell 5.1 안전·호환 테스트와 새 queue `-PreflightOnly`를 통과한다.
- 같은 `input_contract_id=1bda84ba…`,
  `alignment_contract_id=5ff18657…`, 12.7GB 보존 DB에서 export만 재개한다.
- 재개 실행 번호는 출력·로그를 덮어쓰지 않기 위한 queue 실행판 번호일 뿐,
  Jamo r2·음향모델·phone·6-tier 연구 계약의 새 버전이 아니다.
