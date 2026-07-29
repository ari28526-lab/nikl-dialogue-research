# 공통발음사전 r2 연구자 검토표

현재 검토본은
`common_pron_r2_researcher_review_20260729_v4.xlsx`이다.

- `v4`: 최종 검토본. IPA 전용 Noto Sans, 안내문 전체 표시, 생성기
  SHA/openpyxl 버전 manifest 포함
- `v3`: 생성기 provenance를 추가했으나 안내문의 목적·주의 문장이
  좁은 열에서 잘리는 것을 시각 QA에서 발견
- `v2`: IPA 폰트를 적용한 중간판
- 버전 표기가 없는 파일: 최초 openpyxl 생성판

각 XLSX와 같은 이름의 `.manifest.json`은 입력·출력 SHA256, 모델 계약,
행 수와 구조 검증 결과를 담는다. 이전 파일은 시행착오 기록과 재현
감사를 위해 보존하며, 연구자 결정은 반드시 `v4`에만 입력한다.

이 workbook은 승인 인터페이스이며 저장만으로 D:의 shard, 사전,
원자료를 수정하지 않는다.
