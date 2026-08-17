# D7 이후 recovery 종료와 연구 인프라 진입 순서

기록일: 2026-08-17 KST

## 원칙

recovery 자체를 연구의 종착점으로 만들지 않는다. 2020–2025 r3 본체는 이미 같은
계약으로 완료됐다. 남은 항목은 exact-ID로 한 번만 통제 회수하고, 회수되지 않으면
사유가 있는 기술 제외로 확정한 뒤 표적 추출·수동 판정 인프라로 이동한다.

전체연도 MFA, D5 전체, 이미 검토한 11건을 다시 실행하지 않는다.

## 다음 작업 순서

### D8 — 19+25건 회수 가능성 확정

먼저 MFA를 실행하지 않고 원자료를 읽기 전용으로 조사한다.

1. 미정렬 19건: 원 세션 음원·CSV start/end·현재 WAV/LAB identity와 무음·발화
   coverage를 비교해 재분절 가능한 exact-ID만 고른다.
2. 0.1초 미만 25건: 연결된 외장하드·archive에서 원 배포 PCM/세션 음원을 찾고,
   찾은 경우에만 원 CSV 시간으로 새 후보 WAV를 만든다.
3. 후보는 원본을 바꾸지 않고 새 recovery namespace에 복사하며 파일·시간·전사
   SHA를 고정한다.
4. 회수 후보만 한 차례 통제 MFA를 허용하는 별도 Gate에서 정지한다.

### D9 — 한 차례 exact-ID 통제 재정렬과 최종 기술 상태

- 회수 후보만 재정렬한다. 전체연도·전체 D5 재실행은 금지한다.
- 성공하면 새 TextGrid를 다시 연구자 검토하고, 채택은 별도 승인한다.
- 실패하면 `unresolved_technical_exclusion`로 확정하고 원자료·시도 로그를 보존한다.
- D7의 부분 정렬 6건은 재정렬 성공 수와 섞지 않는다.

### D10 — DB v1 RC1 상태 통합

본체 DB를 직접 고치지 않고 기존 5,103,356발화 상태 장부에 recovery 결과를
append-only overlay로 결합한다. 최소 상태는 다음을 구분한다.

- `aligned_main_body`
- `excluded_partial_alignment_preserved`
- `excluded_transcript_recovery_candidate`
- `unresolved_alignment`
- `audio_recovery_required`
- `pronunciation_followup`

모든 상태는 exact ID, 사유, 계약, 원/수정 파일 SHA, 연구자 결정을 추적한다.

### D11 — 실제 연구용 표적 추출과 수동 수정 overlay

DB v1 RC1 뒤에는 형태소·표기·Roman·발음 환경으로 target을 추출하고 WAV·TextGrid·
동반 CSV를 묶는다. 연구자가 TextGrid를 수정하면 원본을 덮어쓰지 않고
`manual_overlay`에 수정자·시각·사유·before/after SHA를 기록해 전체 DB와 다시
연결한다. 여기서부터 KOINA, 이어붙이기, wav2vec2 보조층을 선택적으로 적용한다.

### D12 — 재현 가능한 공개·공동연구 자산

- CSV/MFA/표적 추출 과정을 예시 중심 HTML manual로 정리한다.
- 동일 세션 대화를 복원하는 JSON schema를 설계한다.
- 원본·자동산출·수동수정·배포본을 분리하고 라이선스에 따라 공유 가능 범위를
  manifest에 표시한다.

## 즉시 다음 한 단계

다음 실행은 D8의 **읽기 전용 19+25건 원자료 회수 가능성 감사**다. 아직 MFA나
본체 병합을 시작하지 않는다. 외장하드가 연결된 상태에서 경로·파일을 조사하고,
회수 후보와 미회수 후보의 exact-ID 장부를 만든 뒤 사용자에게 별도 Gate를
제시한다.
