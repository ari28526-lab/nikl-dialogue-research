# 공통발음 r3 Stage 21 — 2022 표적 회귀 정렬 결과

날짜: 2026-08-08 KST
자동 검사: `passed_automatic_checks_pending_researcher_audio_review`
생산 MFA·adoption: 시작하지 않음

## 왜 네 발화만 다시 확인했는가

2022 공식 표본에서 이미 연구자가 문제를 지적한 `있지`, `놨던`, `슬프겠지만`,
`없는` 네 사례는 r2 입력 phone과 r3 후보 phone의 차이를 실제 정렬 경계에서
확인할 수 있는 기존 회귀 표본이다. 광범위 파일럿을 다시 만들지 않고, 이 네
발화만 새 raw TextGrid로 정렬했다. 기존 r2 TextGrid는 읽기 전용 비교물로
보존했다.

| 검토 | 표면형 | r2 phone | r3 후보·정렬 phone |
|---:|---|---|---|
| 08 | 있지 | `iː s͈ dʑ i` | `iː t̚ tɕ͈ i` |
| 09 | 놨던 | `n w ɐ tʰː ʌ n` | `n w ɐ d t͈ ʌ n` |
| 15 | 슬프겠지만 | `sʰ ɨ ɭ pʰ ɨ ɡ e tɕʰː i m ɐ n` | `sʰ ɨ ɭ pʰ ɨ ɡ e t̚ tɕ͈ i m ɐ n` |
| 24 | 없는 | `ʌː p ɕ͈ n ɨ n` | `ʌː m n ɨ n` |

자동 검사는 후보 phone exact 4/4, phone interval 연속 4/4, word–phone 바깥
경계 일치 4/4, `spn` 0으로 통과했다. 이는 “MFA가 입력한 phone열과 일치하게
정렬했다”는 검사이지 실제 음성 실현의 정답 판정이 아니다.

## 연구자 최소 검토

검토 묶음은 한 폴더에 모았다.

```text
C:\Users\ari30\Dropbox\REVIEW_r3_TARGETED_4_20260808
```

WAV와 같은 번호의 `_r3.TextGrid`를 열어 목표 어절의 word·phone 경계가 소리와
비교해 심하게 몰리거나 누락되지 않았는지만 확인한다. 실제 음운 실현형을 확정할
필요는 없다. `REVIEW.csv`의 `decision`에 `승인` 또는 `문제`를 기록하고,
문제가 있을 때만 `notes`를 쓴다.

## 실행 비용과 보존

4개 정렬은 약 15분 38초가 걸렸다. 대부분은 79만형 후보 사전의 MFA graph
compile 비용이었고, 네 음성의 alignment 자체가 병목은 아니었다. 따라서 다음
단계가 승인되면 소수 파일마다 같은 대형 사전을 반복 compile하지 않고 연도·shard
단위로 묶는다.

정본 root는
`D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\21_targeted_regression_2022`,
자동 감사는 `TARGETED_REGRESSION_AUDIT.json`이다. 기존 r2 결과, 원 WAV/LAB,
생산 TextGrid는 변경하지 않았다.
