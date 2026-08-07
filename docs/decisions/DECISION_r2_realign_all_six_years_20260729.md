# 결정: 2020–2025 여섯 연도 전부 r2 기준으로 재정렬

결정일: 2026-07-29
상태: 폐기된 역사 결정(2026-08-07 r2 Gate 차단과 r3 선택 재사용 계약으로 대체)

> 이 문서는 2026-07-29 당시 판단의 시행착오 기록이다. 현재 실행 지침이 아니다.
> r2 신규 실행은 차단됐으며, 현행 정책은
> `DECISION_common_pron_r3_candidate_resolution_20260807.md`를 따른다.

## 결정

구 2020·2021 결과와 r2 공통발음사전의 차이가 작거나 0에 가까워도
구결과를 최종 생산본으로 재사용하지 않는다.

2020, 2021, 2022, 2023, 2024, 2025 여섯 연도를 모두 다음 하나의
동결 기준으로 다시 MFA 정렬한다.

- 공통사전 r2 SHA256:
  `24c406604c86a5df833a7e47d809f252d6fc39dc566a6d3818b3d3ffeb04fb86`
- acoustic v3.3.0 SHA256:
  `94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c`
- Jamo G2P v3.2.0 SHA256:
  `4df7c5fa90da1f401e7a44af360be56158a581a54202e38baedeca53cfed38ff`
- base dictionary SHA256:
  `49e223fddb518bc441baa4cb9fec1a108e80dae9a2b54e5834dbff30e89c7d34`

## difference inventory의 지위

2020·2021 difference inventory는 구결과 재사용 여부를 결정하는
검사가 아니다. 다음만을 위한 전환 감사다.

1. 구방식과 새 방식의 차이를 원인별로 기록한다.
2. 과거 `spn`, coverage, 구조, 기본사전, G2P 차이를 수량화한다.
3. 구결과를 폐기·archive하고 전면 재정렬한 이유를 연구 방법론에
   투명하게 남긴다.

따라서 mismatch가 적다는 이유로 2020·2021 재정렬을 면제할 수 없고,
mismatch가 많다는 이유로 구기준에 새 사전을 맞추지도 않는다.

## 최종 생산본의 조건

- 여섯 연도 alignment contract가 위 공통사전·acoustic·Jamo G2P와
  동일 adoption contract SHA를 가리켜야 한다.
- 각 연도는 TextGrid 수, tier/boundary, DB integrity,
  missing/extras, `spn=0`, phone inventory를 독립 QC한다.
- 마지막에 2020–2025 cross-year contract 감사를 통과해야 한다.
- 구 2020·2021 TextGrid와 DB는 최종 분석 입력이 아니라 비교·감사
  baseline으로 archive한다.

이 결정은 처리시간 절약보다 연구의 연도 간 방법론적 일관성을
우선한다.
