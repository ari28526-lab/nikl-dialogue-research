# MFA phone-only silence word interval 정규화 결정

결정일: 2026-08-05 KST

## 문제

2021 6-tier 전수 TextGrid 생성은 완료됐으나 동반표 최종 계약에서 19발화가
각각 두 오류를 냈다.

- `lab_word_count_mismatch`: LAB 기준보다 MFA word가 정확히 1개 많음
- `word_label_sequence_mismatch`: 실제 마지막 어절 뒤에 같은 어절이 한 번 더 붙음

19건을 SQLite interval과 연결 phone까지 전수 대조한 결과, 추가 word interval은
모두 실제 마지막 lexical word 뒤부터 WAV 끝까지 이어졌고 연결된 phone은 오직
`sil`이었다. MFA DB가 후행 무음 구간의 `word_id`에 마지막 lexical word ID를
남긴 저장 형태이지, 추가 발화·추가 어절·phone 정렬 실패가 아니다.

## 결정

다음 조건을 모두 만족하는 word interval만 비언어 무음으로 정규화한다.

1. 연결된 phone interval이 하나 이상 있다.
2. 연결 phone이 무음 inventory로 정규화된 뒤 전부 빈 표지다.
3. word 표지는 비어 있지 않다.

이때 word interval의 시작·끝, phone interval의 시작·끝과 표지는 바꾸지 않고
word 표지만 빈칸으로 만든다. 따라서 `phones_mfa`와 `phoneme_r_auto`는 의미상
불변이다. `utterance`, `utterance_orth_r`, `morph_analysis_utt`의 텍스트도
바꾸지 않으며, 유표 구간의 끝만 교정된 마지막 lexical word 끝에 맞춘다. 파일의
나머지 구간은 빈 interval로 0–xmax 연속성을 유지한다.

이 값은 실제 발음 판정이 아니다. MFA 강제정렬 인프라에서 lexical label과 무음
구간을 분리해 검색 결과의 시간 범위가 후행 무음 전체로 잘못 늘어나지 않게 하는
기계적 정규화다.

## 적용과 가역성

- 대상: 2021 direct-export partial의 정확한 19개 파생 TextGrid
- 적용 manifest:
  `outputs/reports/REPAIR_2021_phone_only_silence_word_20260805.json`
- 구 파일 보관:
  `D:\mfa_eojeol\repair_archive\2021_phone_only_silence_word_20260805`
- 불변: 2021 MFA DB, 원본 WAV, LAB, 검색 CSV, 원본 CSV, 2020 완성본
- 결과: preflight 19/19, archive 후 원자 교체 19/19, phone tier 변경 0

동반표 재개는 2026-08-05 08:00–09:02 KST에 수행돼 exit 0으로 끝났다.
1,371,883발화, 10,572,619 word interval, 39,296,691 phone interval과 승인 제외
2,037행이 최종 gzip으로 원자 승격됐다. LAB count·word sequence mismatch와 spn은
0이며 `phone_only_silence_word_intervals_normalized=19`다. 성공 보고서는
`D:\mfa_eojeol\logs\direct_db_export_2021_eojeol_commonpron_2021_20260805_phone_sil_fix.json`이다.

앞선 float32 종단 repair와 대상이 겹치는 경우 두 manifest의
`destination_after → destination_before → destination_after` SHA 사슬을 검증한다.
기존 manifest를 덮어쓰지 않는다. 어느 fingerprint나 계약 ID가 다르면 동반표
재개를 차단한다.

## 재발 방지

- 6-tier exporter와 동반표 writer가 같은 DB 정규화 함수를 사용한다.
- 최종 보고서의 `phone_only_silence_word_intervals_normalized`에 수량을 남긴다.
- 동반표 계약 실패 시 최종 gzip으로 승격하지 않고 `TABLES_FAILURE.csv/json`과
  닫힌 partial을 보존한다.
- 재개는 MFA·LAB·전체 TextGrid를 다시 만들지 않고, 검증된 checkpoint와 repair
  사슬을 결합해 동반표부터 수행한다.
- 성공 뒤에도 독립 연도 전수 감사와 DB 표본 재수출을 생략하지 않는다.
