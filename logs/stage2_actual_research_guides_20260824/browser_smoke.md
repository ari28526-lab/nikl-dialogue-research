# Stage2 실제 연구 안내서 브라우저 스모크

- 시작 화면에 PT·NAN·NAL·NI·LLN·VH·HIA 카드 7개가 표시됨
- 각 카드에 `먼저 안내서`와 `바로 연구` 링크가 표시됨
- 일반 viewport에서 카드·candidate 경고·공통 안내서 링크 배치 정상
- NI 안내서 제목 `ㄴ삽입`, `candidate_pending_researcher_adoption`, 범위표 9행,
  열린 질문 섹션 확인
- NI 안내서의 reviewer 링크가
  `STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html?phenomenon=NI`로 연결됨
- reviewer 진행 표시 `1/12 · NI`, 내장 samples 84 확인
- 원격 전달본 최상위 `00_START_RESEARCH.html`에서 실제 연구 안내서 시작 화면으로
  이동하고 카드 7개 코드가 `PT,NAN,NAL,NI,LLN,VH,HIA`인지 확인
- 콘솔 error 0
- localStorage 입력·JSONL 다운로드·연구 판정 작성 0
- 임시 읽기 전용 서버와 브라우저 탭 종료 확인

전체 페이지 screenshot의 브라우저 스크롤 결합 렌더링은 산출물 판정에 사용하지
않았다. 일반 viewport와 DOM 구조를 기준으로 확인했다.
