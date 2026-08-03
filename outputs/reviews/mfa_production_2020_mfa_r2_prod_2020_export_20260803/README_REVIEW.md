# 2020 production MFA 최소 연구자 검토

이 폴더는 2020년 전수 결과가 연구 인프라로 사용 가능한지 확인하는 24개 표본 묶음이다.
실제 음운 현상의 실현 여부를 판정하는 단계가 아니다.

## 검토 순서

1. 번호가 같은 `.wav`, `.lab`, `.TextGrid`를 연다.
2. WAV와 LAB 문장이 같은 발화인지 확인한다.
3. TextGrid가 같은 발화이며 6개 tier가 모두 있는지 확인한다.
4. tier가 0부터 파일 끝까지 이어지고, word·phone 정렬과 Roman·형태소 정보가
   연구용 검색·연결에 사용할 수 있을 정도로 정상인지 확인한다.
5. 해당 search-master 원행은 `REVIEW_CONTEXT.csv`의 같은 `review_order`에서 본다.
6. 문제가 없으면 `03_RESEARCHER_REVIEW.csv`의 해당 행에서 `decision`만
   `approved`로 바꾼다. 문제가 있으면 `pending`을 유지하고 `notes`에 적는다.

## 편집 주의

- Gate B가 읽는 공식 파일은 `03_RESEARCHER_REVIEW.csv`이다.
- `review_order`, `year`, `session`, `speaker_id`, `utt_id`, 세 경로 열은 바꾸지 않는다.
- `decision`과 `notes`만 편집한다.
- 24행 모두 확인한 뒤 저장하고 Codex에 완료 사실을 알린다.

`REVIEW_CONTEXT.csv`에는 검토용 복사본 경로, 원본/복사본 SHA-256과 해당
search-master 원행의 열이 포함된다. 검토용 복사본은 D: 원자료를 변경하지 않는다.
