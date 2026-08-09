# 결정: r3 발음사전과 검색 CSV·MFA 결과의 정규화 연결 계약

결정일: 2026-08-09
상태: 채택, 2020 전수 MFA 전 필수 Gate

## 왜 이 결정이 필요한가

`common_pron_mfa_r3_20260809`에는 795,804개 선택 어형과 796,061개 발음 변이행이
있지만, 기존 연도별 형태소 검색 CSV는 철자·규칙 예상 발음 중심으로 만들어졌다.
따라서 새 사전이 MFA에 사용되더라도 “어느 발화의 몇 번째 참조 어절이 r3 사전의
어느 어형을 사용했는가”를 직접 연결하는 정본 표가 없었다. 이 상태로 정렬하면
TextGrid는 만들 수 있어도 검색 DB와 정렬 결과가 동일한 발음 계약을 사용했다는
사실을 행 수준에서 입증하기 어렵다.

이 누락은 원 CSV를 새 발음값으로 덮어쓰는 방식으로 해결하지 않는다. 철자,
형태소, 규칙 예상 발음, 사전 발음 후보, MFA 입력 발음, 시간 정렬 phone은 서로
다른 연구 변인이며 한 열로 합치면 출처와 해석이 사라지기 때문이다.

## 채택한 구조

1. `pronunciation_type_catalog.csv.gz`
   - 관측 표층 어형 1개당 1행, 총 881,237행이다.
   - 철자 Roman, 규칙 예상형, 우리말샘 후보와 출처, r2 근거, r3 선택·보류·정책
     상태를 분리 보존한다.
   - 1:N 최종 발음 변이는 기존
     `selected_pronunciation_projection.csv.gz`와 연결한다.
2. `utterance_pronunciation_scope.csv.gz`
   - 발화 1개당 1행이다.
   - `r3_safe_body_input`, `pre_mfa_excluded`, `pronunciation_followup`을 구분하고
     보류 어형 및 기술적 제외 사유를 보존한다.
3. `pronunciation_occurrences.csv.gz`
   - `pron_reference_form`의 원 참조 어절 1개당 1행이다.
   - 정본 키는 `(year, utt_id, reference_eojeol_idx)`다.
   - 기호 제거 전 참조 어절 번호와 제거 후 `mfa_word_idx`를 분리한다.
   - 철자·형태소 어절 수가 같을 때만 해당 좌표를 연결한다. 수가 다르면 빈칸과
     `reference_only_no_silent_index_guess`를 기록하며 위치를 추측하지 않는다.
4. post-MFA 동반표
   - 기존 `word_intervals_mfa`와 `phone_intervals_mfa`의
     `reference_eojeol_idx`를 이용해 occurrence 표와 결합한다.
   - 큰 발음·사전 정보를 interval 행마다 복제하지 않는다.
   - export manifest에는 occurrence 표·발화 scope·독립 감사의 SHA-256과 결합 키를
     고정한다.

## 실행·복구 계약

- 기존 형태소 검색 CSV, r3 사전, 원 WAV/JSON, r2 DB/TextGrid를 수정하지 않는다.
- 연도별 표는 기존 형태소 검색 shard 단위로 checkpoint한다. 중단 시 통과한 shard는
  SHA가 같을 때만 재사용하며 연도 전체를 처음부터 만들지 않는다.
- builder와 독립 auditor를 분리한다. auditor는 원 참조형에서 어절을 다시 만들고
  전 행의 키·값·분할 산식·SHA를 대조한다.
- 2020 전수 MFA runner는 해당 연도의 감사가 `passed`가 아니면 fail-closed한다.
- CSV/export 오류는 보존 MFA DB에서 CSV만 다시 만들며 정렬을 반복하지 않는다.

## 연구 해석

- 규칙 예상 발음과 사전 후보는 연구용 참조 정보다.
- r3 선택 phone은 강제정렬 입력 가설이다.
- `phones_mfa`는 그 입력과 음향모델에 따른 시간 정렬 결과이지 실제 실현의 자동
  판정값이 아니다.
- 실제 실현 여부, ㄴ 삽입 등 음운 현상, 운율은 선별된 WAV·TextGrid·KOINA와
  연구자 판단 단계에서 별도로 판정한다.

구현 계약은 `config/mfa_r3_research_database_v1.json`에 고정한다.
