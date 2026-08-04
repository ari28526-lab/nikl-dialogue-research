# MFA direct-export 성공 checkpoint의 비재계산 승격 정책

상태: 현행 생산 계약

적용 범위: 2021 복구와 이후 2022–2025의 동일한 direct-DB export 중단 복구

## 문제

2021은 MFA 계산과 6-tier TextGrid 전수 생성이 끝난 뒤에도 동반표·완료 marker
단계의 오류 때문에 여러 차례 안전 중단됐다. 이때 기존 연도 runner를 그대로
재실행하면 원본이나 정렬 결과를 바꾸지는 않더라도 137만 LAB 내용 검사, 입력
감사, 12.7GB DB 검증을 다시 수행한다. 이는 안전성에 새로운 근거를 거의 더하지
않으면서 재개 시간을 늘리고, 사용자가 같은 작업이 반복된다고 느끼게 한다.

반대로 성공 보고서만 보고 폴더를 바로 옮기면 입력·정렬 계약, 보존 DB,
exact-ID 대사 또는 동반표가 바뀐 상태를 놓칠 수 있다. 따라서 “재검사 전부 반복”과
“무검증 이동” 사이에 명시적인 checkpoint 승격 계약이 필요하다.

## 결정

1. direct exporter가 `status=success`, 6개 tier, coverage 100%, 실패·누락·`spn`
   0, `exact_id_reconciliation.status=passed`, `full_year_gate=true`를 기록한 경우에만
   checkpoint 승격 후보로 본다.
2. 현재 정렬 계약 JSON에서 builder canonical identity를 다시 계산한다. 저장된
   정렬 ID, export 보고서, `direct_db_ready`, 입력 감사 보고서의 입력·정렬 ID와
   보존 DB가 모두 같아야 한다.
3. 동결 search master 경로도 export·DB checkpoint·입력 감사 사이에서 같아야
   하며, 입력 감사의 execution·analysis-ready gate가 모두 통과해야 한다.
4. 네 gzip 동반표와 `TABLES_MANIFEST.json`은 크기와 SHA-256을 실제 파일에서
   다시 계산한다. manifest와 report가 다르거나 `.partial` 파일이 하나라도 남으면
   승격하지 않는다.
5. partial 연도 폴더와 최종 staging 연도 폴더는 같은 드라이브여야 한다. 최종
   경로가 비어 있을 때 연도 디렉터리 하나만 원자적으로 rename한다. 둘 다 있으면
   자동 병합하거나 덮어쓰지 않는다.
6. 폴더 이동 뒤 동일 입력·정렬 ID의 `align_done`과 `merge_done`을 원자적으로
   쓴다. 이동 뒤 marker 쓰기에서 중단돼도 최종 staging을 다시 검증해 marker만
   재생성할 수 있도록 멱등적으로 만든다.
7. 이 marker는 정본 승격 허가가 아니다. 곧바로 독립 6-tier 연도 전수 감사와
   보존 DB 표본 24건 재수출 검사를 수행하고, 연구자 표본 확인이 끝날 때까지 다음
   연도와 정본 승격을 허용하지 않는다.

## 구현과 검증

- 구현: `scripts/python/promote_mfa_direct_export_checkpoint.py`
- 회귀시험: `tests/test_promote_mfa_direct_export_checkpoint.py`
- 정상 승격과 이동 후 재개, 동반표 변조 차단, 정렬계약 의미 변조 차단을 시험한다.
- 승격 보고서에는 export·정렬계약·DB checkpoint·입력 감사·동반표의 경로와
  SHA-256을 기록한다.

## 보존 범위

이 절차는 versioned `08_textgrid_research_v2_staging` 안의 해당 연도 폴더만
옮긴다. 원본 WAV/CSV, search master, MFA DB, 2020 완성본과 정본
`06_textgrid_eojeol`은 수정하거나 삭제하지 않는다.
