# 2020–2025 대화 음원 품질 감사

이 폴더는 원자료와 MFA 산출물을 변경하지 않은 읽기 전용 감사 결과다.

먼저 `SUMMARY_2020_2025.csv`와 `SUMMARY_2020_2025.json`을 본다. 각 연도 폴더에는
전체 JSON 구조 감사와 세션 층화 WAV 표본 감사가 있다. 2022의
`04_FOCUS_PROFILE_438_PLUS_CONTROLS`는 post-MFA 미정렬 438건과 aligned control
4건을 exact-ID로 결합한 표다.

주의:

- `boundary_abut_review`는 잘림 확정이 아니다.
- noise proxy는 SNR이나 자동 제외 기준이 아니다.
- 모든 `researcher_decision`은 `pending`이다.
- 자동 승인·원자료 수정·MFA DB 수정은 0건이다.
- `<=44B` 전수 검사는 2021 68개, 2023 75개의 header-only WAV를 찾았다.
  2023의 75개와 2021의 현재 입력 53개는 기존 `audio_pairing_unresolved`
  승인에 포함된다. 2021의 나머지 15개는 현 search master·LAB에 없으므로
  디스크 inventory로만 남기고 현재 MFA 후보로 세지 않는다.

방법과 열 설명:

- `docs/decisions/DECISION_dialogue_audio_quality_gate_2020_2025_20260807.md`
- `docs/DATA_DICTIONARY_dialogue_audio_quality_2020_2025.md`
