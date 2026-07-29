# 공통발음사전 r2 연구자 검토표

현재 검토본은
`common_pron_r2_researcher_review_20260729_v5.xlsx`이다.

`v5`는 비교용 깨끗한 template이므로 직접 덮어쓰지 않는다. Excel에서
열자마자 **다른 이름으로 저장**을 선택해
`common_pron_r2_researcher_review_20260729_FILLED.xlsx` 같은 별도
파일을 만든 뒤, 그 사본의 R·S·U열만 입력한다.

- `v5`: 최종 검토본. 생성기·근거를 고정한 깨끗한 Git commit
  `093ce31`에서 다시 생성해 manifest의 `git_commit`과 실제 코드
  기준점을 일치시킴
- `v4`: IPA 전용 Noto Sans, 안내문 전체 표시, 생성기
  SHA/openpyxl 버전 manifest를 검증한 QA 기준판
- `v3`: 생성기 provenance를 추가했으나 안내문의 목적·주의 문장이
  좁은 열에서 잘리는 것을 시각 QA에서 발견
- `v2`: IPA 폰트를 적용한 중간판
- 버전 표기가 없는 파일: 최초 openpyxl 생성판

각 XLSX와 같은 이름의 `.manifest.json`은 입력·출력 SHA256, 모델 계약,
행 수와 구조 검증 결과를 담는다. 이전 파일은 시행착오 기록과 재현
감사를 위해 보존한다. 연구자 결정은 `v5`에서 만든 `FILLED` 사본에만
입력한다.

이 workbook은 승인 인터페이스이며 저장만으로 D:의 shard, 사전,
원자료를 수정하지 않는다.

작성본은
`scripts/python/validate_common_pron_researcher_review_xlsx.py`로
검증한다. 이 도구는 template과 비교해 R·S·U 이외의 셀·수식·링크·
병합·표·데이터검증이 바뀌면 거부한다. 27건이 모두 승인되고 동결
107-phone inventory를 통과할 때만 정규화 결정표 27행과 correction
registry 2행을 만들며, 이 단계에서도 D: 원장이나 shard는 수정하지
않는다.
