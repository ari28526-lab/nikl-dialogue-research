# 2022 post-MFA exact-ID 검토 안내

## 왜 검토하는가

2022년 전수 MFA 계산은 완료되었지만, 활성 LAB 865,128건 가운데 438건은
MFA 데이터베이스에 발화·음향 특징이 정상 등록된 뒤에도 word/phone 정렬 구간이
생성되지 않았다. 전수 계산이나 원자료를 다시 만들지 않고, 이 438건만 안전 본체
산출물에서 명시적으로 제외한 뒤 보존 DB에서 export를 재개하기 위한 검토이다.

이 검토는 실제 음운 실현이나 정렬 품질을 판정하는 작업이 아니다.

## 이번에 확인할 한 가지

`03_AUDIO_LAB_PILOT_REVIEW.csv`의 20행을 번호순으로 보면서, 같은 번호의 WAV를
듣고 LAB의 `normalized_text`가 실제 발화와 대응하는지만 확인한다.

- 1–16번: 정렬 구간이 생성되지 않은 후보 표본
- 17–20번: 후보가 많이 나온 `SDRW2200002739` 세션의 정상 정렬 대조군
- 확인 결과가 맞으면 `decision`에 `match`를, 문제가 있으면 `mismatch`를 적고
  `notes`에 들린 내용이나 문제를 간단히 남긴다.

## 파일 역할

- `01_CANDIDATE_DETAILS.csv`: 438건의 DB 기술 근거
- `02_RESEARCHER_DECISIONS.csv`: 생성 당시의 변경 금지 pending 원본
- `03_AUDIO_LAB_PILOT_REVIEW.csv`: 연구자가 실제로 확인할 20건 표본
- `04_RESEARCHER_APPROVAL.csv`: 명시 승인 후 파이프라인이 소비할 작업본
- `SUMMARY.json`: 후보 수, identity SHA, 승인 token 및 재개 조건
- `pilot_files`: 20건의 WAV와 LAB

## 주의

- `02_RESEARCHER_DECISIONS.csv`는 수정하지 않는다.
- 438건을 자동 승인하지 않는다.
- 표본 확인 뒤 연구자가 438건의 안전 본체 제외에 동의해야만
  `04_RESEARCHER_APPROVAL.csv`를 승인 상태로 만들고 export를 재개한다.
- 승인하더라도 438건의 원 WAV/LAB이나 보존 MFA DB는 삭제·수정하지 않는다.
- 이 438건은 필요하면 후속 targeted recovery shard의 입력으로 다시 사용할 수 있다.
