# 2020 MFA 제외 최종 승인표

이 폴더가 2020년 승인 검토의 유일한 활성본이다.
기존 1,834건 표는 미해결 기호 빈 LAB 53건이 빠져 archive했다.

- `audio_pairing_unresolved`: 1,834건
- `empty_reference_unresolved_symbol`: 53건
- 최종 승인 후보: 1,887건
- 부분 LAB 보존·경고: 6,158건(승인 제외 후보가 아님)

전수 WAV/LAB 검사는 다시 수행하지 않았다. 기존 보고서와 인벤토리의
계약 ID·합계·SHA-256을 검증한 뒤 결합했다.

2026-08-02 13:27 KST에 연구자 `ari30`이 “두 범주 모두 승인”이라고
명시 승인했다. 원 `03_RESEARCHER_REVIEW.csv`는 1,887행 `pending` 증거로
변경하지 않았고 다음을 별도로 생성했다.

- `04_RESEARCHER_APPROVED.csv`: 1,887행 승인본
- `04_RESEARCHER_APPROVAL.json`: 승인자·시각·문구·범주·SHA 기록
- `approved_exclusions.json`: 입력 계약에 결속된 MFA 제외 계약

자동 승인, MFA 정렬, WAV 이동, 정본 승격은 수행하지 않았다. 다음 단계는
2020 MFA 시작 전 preflight다.
