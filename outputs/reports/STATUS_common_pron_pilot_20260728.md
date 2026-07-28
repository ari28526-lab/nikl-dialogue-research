# 공통 발음사전 파일럿 준비 현황

기준 시각: 2026-07-28 오전
release: `common_pron_pilot_full6y_20260728`

## 결론

2020–2025 전체 코퍼스를 대상으로 한 공통 발음사전 파일럿을 시작했다.
표본으로 사전을 만드는 것이 아니라 6개년 동결 CSV 전수에서 vocabulary를
만들었고, 소표본은 이후 정책 A/B 정렬 품질 검증에만 사용한다.

## 완료

- D: 격리 release와 10개 역할별 하위 폴더 생성
- 17,156개 세션 CSV, 5,103,356개 발화행 전수 스캔
- 전체 어절 출현 27,847,068개, 고유 어절 881,237개 확정
- enriched 1,165,157행과 legacy 1,296,777행 전수 감사
- enriched 무발음 664,596행의 legacy `urimal_id` fallback 100% 확인
- 실행 코드·입력·출력 SHA256과 Git commit 기록
- 기반 코드와 테스트를 `14cc43e`로 commit/push
- Python unittest 91개·PowerShell 안전성 6개 파일·JSON 파싱 통과

## 용량

- 시작 D: 여유 264.146GiB
- 현재 D: 여유 264.119GiB
- release 사용량 약 28.035MiB
- 2021 temp 실제 삭제 0건

현재 파일럿 준비에는 공간이 충분하다. 31.365GiB의 2021 정리 후보는
사용자 명시 승인 전까지 그대로 둔다.

## 다음 gate

과거 lexicon의 `*_roman_mfa`를 현재 MFA 사전에 바로 넣지 않는다. 현재
`korean_mfa` acoustic/dictionary phone set과 다르므로, 사전 한글 발음을
현재 G2P phone alphabet으로 옮기는 변환 동등성 검증이 먼저다.

그 뒤 전체 registry를 만들고, 동일한 WAV·lab에서 baseline A와 사전 변이
포함 B를 비교한다. 2022 전량은 이 방법론 gate가 끝날 때까지 시작하지 않는다.

상세 기록:

`docs/decisions/PILOT_common_pronunciation_full_corpus_20260728.md`

## 실행 순서 결정

현재 완료된 것은 공통 vocabulary와 사전 원천 감사이며, 실제 정책 A/B MFA
파생사전은 아직 생성 전이다. 따라서 2020 재실행과 2022 전량을 모두 잠시
보류하고 다음 순서로 진행한다.

```text
registry
  → 현재 MFA phone 변환 gate
  → 정책 A/B 사전
  → 동일 표본 MFA 파일럿
  → 자동 QC + 연구자 검토
  → 연도별 전량 결정
```

정책 A가 기존 2020·2021 phone 후보와 전수 동등하면 재실행 없이 2022로
진행할 수 있다. 정책 B가 사전 예외·대체 후보를 실제로 바꾸고 채택되면 기존
결과를 baseline으로 보존하고 2020·2021부터 새 release로 재정렬한 뒤
2022–2025를 진행한다.

wav2vec2 phone 모델은 A/B stress 표본의 별도 보조층으로만 사용하며 기존
MFA tier·CSV·TextGrid를 바꾸지 않는다.

상세 결정:

`docs/decisions/PLAN_common_pron_AB_then_year_order_20260728.md`

## A/B 실행기 준비

`scripts/run_common_pron_ab_pilot.ps1`을 추가했다. 기본 파일럿은 연도별 서로
다른 실제 화자 5명의 stress 1발화와 같은 화자·세션 control 1발화, 총
60발화이며 정책 A/B 각각 동일한 WAV·lab을 정렬한다.

전체 vocabulary registry는 전수로 만들되, 채택 전 계산 낭비를 막기 위해
파일럿 G2P는 표본에 필요한 어절·사전 발음에만 한정한다. 정책 A/B 채택 뒤
같은 계약으로 전체 파생사전을 만든다.

검증:

- Python unittest 96개 통과
- 신규 A/B 전용 합성시험 5개 통과
- PowerShell 안전성 검사 7개 파일 통과
- 실제 한국어 G2P 4단어 smoke test에서 1-best 옵션 필요성 확인
- Python·PowerShell 구문 및 `git diff --check` 통과

현재 상태는 **실제 A/B 6개년 소표본 실행 대기**이며 자동 정책 채택이나
2020/2021/2022 전량 실행은 아직 하지 않는다.

실행서:

`docs/decisions/RUNBOOK_common_pron_AB_pilot_20260728.md`
