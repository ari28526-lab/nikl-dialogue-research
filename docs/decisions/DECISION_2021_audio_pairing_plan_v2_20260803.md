# 2021 음원 대응 불량과 WAV 복구계획 v2 결정

결정일: 2026-08-03 KST

상태: 2021 연구자 승인 대기

적용 범위: 2021 MFA 입력 후보표 준비

## 연구 목적

MFA 정렬 결과를 음운 실현의 자동 판정값으로 쓰지 않는다. 연구자가 형태·철자
환경으로 후보를 찾고 실제 WAV와 TextGrid를 함께 확인할 수 있도록, 정렬 전에
CSV 발화와 WAV가 같은 음성 구간인지 보장하는 것이 이 단계의 목적이다.

## 관측 사실

- search master: 4,143 CSV, 1,373,920행
- 기존 LAB 내용 일치: 1,373,521
- LAB 신규/불일치 재작성/WAV 누락: 0/0/0
- 빈 발음참조: 399
- 미해결 기호 inventory: 17,394
- WAV 전수: 1,416,216, 44 bytes 미만 0
- duration/header audio pairing issue: 1,005
- 영향 세션: 12

4개 세션은 원본 PCM과 개별 WAV가 거의 모두 0.1초 또는 0초이고, 나머지는
개별 0초·header 불량이다. 길이 연속성으로 다른 WAV ID에 대응시킬 수 있는
고신뢰 remap은 0건이다. 따라서 이 1,005건을 다른 발화 음원으로 추정 복구하지
않는다.

## v1에서 발견한 위험

구 계획기는 영향 세션 전체에 `SequenceMatcher`를 적용했다. 일부 WAV만 불량인
세션에서도 정상 same-ID 파일이 연속성 matching에 잡히지 않으면
`target_unresolved`로 확대될 수 있었다. 최초 2021 dry-run은 실제 issue보다
많은 발화를 제외 후보로 만들 수 있어 채택하지 않았다.

## 채택한 v2 규칙

1. 입력 감사의 audio issue ID 집합을 정본으로 사용한다.
2. 감사에서 문제로 지목되지 않은 발화는 same-ID WAV를 우선 보존한다.
3. 실제 issue ID에만 연속 길이 remap 탐색을 허용한다.
4. issue가 아닌 발화가 unresolved/ambiguous로 확대되면 계획 생성을 실패시킨다.
5. issue가 계획에서 누락돼도 실패시킨다.
6. 고신뢰 remap은 자동 적용하지 않고 별도 음성 표본 검토·원본 archive 계약을
   요구한다.
7. unresolved/ambiguous는 후보표에 `alignment_and_analysis` 제외 후보로만
   기록하며 자동 승인하지 않는다.

2021 v2 결과는 issue 1,005, `target_unresolved` 1,005, 고신뢰 remap 0,
issue 밖 오제외 0이다.

## 현재 후보표

총 1,468행이며 다음 세 범주다.

- `audio_pairing_unresolved`: 1,005
- `empty_reference_unresolved_symbol`: 399
- `text_duration_impossible`: 64

연구자가 범주와 근거를 확인해 명시 승인하기 전에는 2021 MFA를 시작하지 않는다.
승인되더라도 제외 사실과 사유는 동반표·manifest에 남겨 분석 모집단과 정렬
모집단의 차이를 추적한다.

## 근거 파일

- `outputs/reports/PLAN_2021_wav_duration_recovery_20260803.json`
- `outputs/reports/PLAN_2021_wav_duration_recovery_20260803.csv`
- `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2021_2025_20260803/2021/01_input_audit_unapproved.json`
- `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2021_2025_20260803/2021/03_RESEARCHER_REVIEW_MANIFEST.json`
- `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2021_2025_20260803/2021/03_RESEARCHER_REVIEW.csv`

이 결정은 2020 완성본, 공통 Jamo r2 사전, acoustic model, phone inventory 또는
원본 WAV를 변경하지 않는다.
