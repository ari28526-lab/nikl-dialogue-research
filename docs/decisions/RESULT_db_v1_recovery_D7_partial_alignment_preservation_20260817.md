# 연구 DB v1 recovery D7 부분 정렬 보존 결정

기록일: 2026-08-17 KST

## 결론

연구자가 Dropbox 검토표에 남긴 11건의 메모를 exact-ID 결정으로 구조화했다.
11건 모두 r3 본체의 정렬 성공 및 `alignment_and_analysis` 범위에서는 제외한다.
그러나 제외를 삭제와 동일시하지 않고 D5 진단 WAV·LAB·2-tier TextGrid를 그대로
보존하며, 6건은 `partial_alignment_available`로 별도 검색 가능하게 유지한다.

| 연구 사용 상태 | 건수 | 처리 |
|---|---:|---|
| `partial_alignment_available` | 6 | 본체 제외, 별도 recovery DB에서 검색·참조 가능 |
| `noise_hold` | 3 | 잡음 사유로 본체 제외, 진단 자료만 보존 |
| `transcript_segment_missing` | 1 | 누락 전사 회수 뒤 새 exact-ID Gate 후보 |
| `transcript_correction_candidate` | 1 | 전사 수정 뒤 통제 재정렬 후보 |

모든 행은 `main_body_status=excluded_not_adopted`,
`diagnostic_alignment_status=diagnostic_2tier_preserved_unadopted`다. 본체 성공 수에
포함하지 않고 자동 병합도 허용하지 않는다.

## 권위 자료

```text
outputs/releases/nikl_dialogue_research_db_v1_recovery_d7_partial_alignment_gate_20260817
outputs/reports/RESULT_db_v1_recovery_D7_20260817.json
```

- `RESEARCHER_REVIEW_SOURCE.csv`: Dropbox 검토표의 바이트 동일 증거 사본
- `D7_EXACT_ID_DECISIONS.json`: 11건의 권위 구조화 결정
- `D7_PARTIAL_ALIGNMENT_PRESERVATION.sqlite`: 본체와 분리된 검색용 recovery DB
- `D7_GATE.json`: 무병합·무삭제 정지 Gate
- `INDEPENDENT_AUDIT.json`: JSON/SQLite/파일 해시·분류 전수 감사

공식 spreadsheet loader가 현재 작업에 없어 새 CSV를 임의 라이브러리로 만들지
않았다. 연구자가 편집한 CSV는 원형 그대로 보존하고, 기계 처리 정본은 JSON과
SQLite로 만들었다.

## 안전성과 방법론

- r3 본체, 연구용 6-tier, DB v1 변경: 0건
- D5/D6 WAV·LAB·TextGrid 삭제: 0건
- 11건을 본체 정렬 성공으로 계산: 0건
- 후속 자동 재정렬·자동 병합: 0건
- 미래 채택 또는 수정 재정렬: 별도 exact-ID 승인 필요

독립 감사 상태는 다음이다.

```text
passed_excluded_from_main_body_partial_artifacts_preserved
```

이는 “정렬 실패 자료를 성공으로 간주”한 것이 아니다. 정렬 가능한 일부 구간이
남아 있다는 기술 정보를 잃지 않으면서, 본체의 방법론적 일관성을 지키기 위한
분리 보존이다.
