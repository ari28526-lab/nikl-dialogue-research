# 2021 post-MFA exact-ID 검토 안내

현재 상태: 기술적 제외 승인 완료, 청취 검토 유예, export 재개 전

## 무엇을 분리했는가

- `mfa_alignment_missing`: 511건. MFA DB에 발화는 있지만 word/phone
  interval이 없다.
- `mfa_feature_generation_failed`: 24건. 모두 0.01–0.10초의 초단시간
  WAV이며 usable acoustic feature가 없다.
- 전체 후보: 535건. 자동 승인 0건.

이 분류는 실제 음운 실현, 발화의 언어학적 타당성, 원자료 오류를
판정하는 것이 아니다. 현 MFA 계약에서 정렬·6-tier 산출이 불가능한 자료를
안전 본체에서 분리하는 기술 분류다. 모든 ID와 근거는 후속 회수용으로
보존한다.

## 파일

- `01_CANDIDATE_DETAILS.csv`: DB 근거·길이·사유 포함 535건 상세표
- `02_RESEARCHER_DECISIONS.csv`: immutable pending 원본. 수정 금지
- `04_RESEARCHER_APPROVAL.csv`: 명시 승인 후 편집하는 작업본
- `03_AUDIO_LAB_PILOT_REVIEW.csv`: 제외 후보 20건+정상 대조군 4건
- `03_AUDIO_LAB_PILOT_REVIEW/`: 표본 WAV·LAB 24쌍
- `SUMMARY.json`: 후보 identity SHA·승인 token·파일 fingerprint

## 선택 1 — 지금 표본 검토

24개 표본에서 WAV와 LAB가 같은 발화인지, 집중 세션
`SDRW2100004234`의 미정렬과 정상 대조군이 체계적 엇매핑 징후를
보이지 않는지 확인한다. 이상이 없으면 두 사유의 기술적 제외·
후속 회수 이월을 명시 승인한다.

## 선택 2 — 청취 검토 유예

지금 시간이 없으면 exact-ID·DB 분류·길이 근거로 기술적 제외 방침을
승인하고 export를 재개할 수 있다. 이 경우 승인 기록에 `24개 WAV/LAB
청취 검토를 2021 최종 Gate 전으로 유예`했음을 명시한다. 유예 검토가
끝나기 전에는 2022를 시작하지 않는다.

2026-08-04 21:35 KST에 연구자 `ari30`이 이 선택을 명시 승인했다.
535건은 후속 회수 대상으로 보존하며, 24개 표본 청취는 2021 최종
Gate 전에 실시한다.

## 안전 재개 조건

승인 시 DB, 입력·정렬 계약, 후보 535건 identity SHA, 실패 보고서 SHA,
기존 1,502건 제외 계약, 승인 token을 모두 재검증한다. 하나라도 다르면
중단한다. 통과하면 보존 DB에서 6-tier·동반표 export만 재개하며
MFA는 다시 실행하지 않는다.
