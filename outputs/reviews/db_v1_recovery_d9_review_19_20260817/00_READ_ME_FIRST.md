# D9 회수 19건 검토

각 번호는 같은 발화의 WAV, LAB, 2-tier MFA TextGrid 한 세트입니다.

1. WAV를 재생해 LAB 문장과 같은 발화인지 확인합니다.
2. WAV와 TextGrid를 Praat에서 함께 열어 words와 phones 경계를 봅니다.
3. 허용 판정은 `approve_recovery_alignment`, `keep_separate_partial`, `reject_technical`입니다.
4. `source_overlap=true` 네 건은 정렬이 좋아도 단일 화자 음향분석 자동 승인이 아닙니다.

현재 19건은 모두 본체 미채택 상태입니다. 이 폴더의 파일을 고쳐도 r3 본체에는 자동 반영되지 않습니다. 원문·형태소·시간·검토 입력란은 `00_REVIEW_19.json`에 있습니다.
