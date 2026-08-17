# 연구 DB v1 recovery D8 원자료 회수 가능성 감사

기록일: 2026-08-17 KST

## 결론

D6의 계속 미정렬 19건과 0.1초 미만 no-run 25건을 원 JSON, 동결 pre-MFA
CSV, LAB, canonical WAV, r3 corpus WAV, H: 백업 WAV 및 과거 원 PCM 직접 실측
장부로 다시 대조했다. 결과는 다음과 같다.

| 분기 | 건수 | D8 판정 |
|---|---:|---|
| D5 이후 미정렬 | 19 | D9 한 차례 통제 parameter-retry 후보 |
| 0.1초 미만 feature failure | 25 | 원 음원 조각 자체가 너무 짧은 기술 제외 |

19건은 2020 2, 2021 5, 2022 3, 2023 5, 2024 3, 2025 1건이다. 25건의
H: 백업 WAV는 모두 현행 r3 WAV와 PCM payload가 같았고, 가장 긴 파일도
0.099875초였다. 따라서 동일 exact ID에 대해 재추출하거나 같은 입력 MFA를
반복해도 음성 정보가 늘어나지 않는다.

## 숫자·기호 전사의 판정 기준

초기 비교에서 19건 중 3건은 철자 원문의 숫자와 MFA용 읽기 전사가 달랐다.

- `9월`과 `구월`
- `1학년/4학년`의 읽기 전사
- `90년대`의 읽기 전사

이는 음성–전사 identity 오류가 아니라 이미 합의한 기호·숫자 읽기 정규화다.
따라서 D8은 LAB를 철자 원문과 억지로 동일하게 만들지 않고, D6에서 동결된
MFA normalized text와 비교했다. 세 건 모두 그 정규화 전사와 일치해 D9 후보로
유지했다. 철자 원문과 읽기 전사의 차이는 별도 검사값으로 계속 보존한다.

## 겹침과 연구 범위

19개 D9 후보 중 4건은 원 JSON note 또는 시간구간에서 발화 겹침이 확인됐다.
정렬 인프라 구축을 위한 통제 진단 후보에서는 삭제하지 않지만, 성공하더라도
단일 화자 음향분석에 자동 포함하지 않는다. 상태는 다음처럼 분리한다.

```text
alignment infrastructure candidate
!= single-speaker acoustic-analysis approval
```

25개 짧은 조각 중 21건에도 겹침 근거가 있고, 19건은 같은 화자의 같은 form이
세션 내 다른 ID에도 있다. 이는 상당수가 겹침 발화를 분할하며 생긴 매우 짧은
원자료 조각임을 뒷받침한다. 다만 다른 ID의 음성을 해당 exact ID에 임의로
복사하지 않는다.

## 저장·안전 상태

정본 package:

```text
outputs/releases/nikl_dialogue_research_db_v1_recovery_d8_feasibility_audit_20260817
outputs/reports/RESULT_db_v1_recovery_D8_20260817.json
```

- `D8_EXACT_ID_FEASIBILITY.json`: 44건 전체 증거와 판정
- `D8_RECOVERY_FEASIBILITY.sqlite`: 별도 조회용 로컬 DB
- `D8_GATE.json`: D9 승인 전 정지 Gate
- `INDEPENDENT_AUDIT.json`: 44건 JSON/SQLite/파일 해시 독립 감사

이번 단계에서 MFA 실행, 새 recovery WAV 생성, r3 본체·6-tier·DB v1 수정,
자동 병합, 원자료 삭제는 모두 0건이다. 독립 감사 상태는 다음이다.

```text
passed_read_only_feasibility_gate_closed
```

## 다음 한 단계

D9는 19건만 새 namespace에 복사해 기본과 구분되는 통제 parameter 설정으로 딱
한 차례 실행한다. 25건은 D9 입력에서 제외하고
`final_technical_exclusion_source_fragment_too_short`로 DB v1 RC1 overlay에
넘긴다. D9 성공 결과도 자동 병합하지 않고, TextGrid 존재·경계 감사 뒤 별도
채택 결정을 거친다.
