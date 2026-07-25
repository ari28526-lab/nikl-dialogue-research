# TextGrid tier 표준 v2 (2020-2025 통일) — 2026-07-11 확정 (슬림 표준)

원칙: 발화 단위 1파일. **시간 정렬이 본질인 정보만 tier로**, 텍스트 정보는
utt_id로 레이어(10_LAYERS CSV) 조인. 통일 파일을 정본으로 물리 보유하고
구버전은 90_ARCHIVE로 이동(추후 압축).

## 표준 tier (슬림 4-tier)

| # | tier | 형식 | 내용 | 출처 |
|---|---|---|---|---|
| 1 | words | Interval(시간) | 형태소 단위 정렬 | MFA (불변) |
| 2 | phones | Interval(시간) | IPA 음소 정렬 (**필수**) | MFA (불변) |
| 3 | utterance | 단일구간 | 발화 원문(form) | 원본 JSON |
| 4 | prosody | Interval(시간) | KOINA 기반 IP/AP 경계 (**온디맨드** — 분석 대상 발화에만) | KOINA+판정 |

## tier에 넣지 않는 것 (레이어 조인 + 주입 유틸)
- 형태소(바른)·의미번호·original_form·로마자 발음열·화자 속성 등은
  utt_id 조인으로 사용. Praat에서 봐야 할 때는 **주입 유틸**
  (`inject_tiers.py`, 작성 예정)로 선택 발화의 TextGrid에 임시/영구 추가
- 근거: 중복 관리 방지, 파일 경량화, 레이어가 단일 진실 원천(single source)

## 정렬 모델 (논문 기재용, 2026-07-11 검증)
- korean_mfa 음향 모델 **v3.0** (GMM-HMM, 2024-02-17 학습) + korean_mfa 사전
- 전 연도 동일 파일(2026-02-18 다운로드본) 사용 확인 — METHODS 3.5절
- 화자 단위 = 세션 (2025: --speaker_characters 14, 구버전: 세션 폴더)

## 구현 순서
1. [ ] `merge_textgrid_v2.py` 작성: MFA 출력 + JSON form → 표준 TextGrid
2. [ ] 2025 MFA 완료 후 적용 → 20_AUDIO/06_textgrid_merged/2025/ + 표본 검증·표준 동결
3. [ ] 2020-2024 소급 재병합 (밤샘 배치 수일):
       05_mfa_output(원본 MFA 출력) + JSON → 표준 파일 신규 생성
4. [ ] 구 06_textgrid_merged(6-tier 구판) → 90_ARCHIVE로 이동(즉시),
       여유 시간에 연도별 zip 압축
5. [ ] `inject_tiers.py` 작성 (morphs/sense/original_form 온디맨드 주입)
6. [ ] 커버리지 인벤토리 갱신 + METHODS 기록

관련: PLAN_2026-07-09(음성연계), PLAN_KOINA(운율), METHODS 3.5절

## 2026-07-25 층화 MFA 파일럿 보완

이 문서의 2026-07-11 표는 당시 슬림 3-tier+prosody 구상 기록이다. 실제
층화 MFA 파일럿의 운영 정본은 `words / phones / morphemes / utterance`
4-tier이며, `prosody`는 KOINA 이후 온디맨드로 추가한다.

사용자 수동 검토에 따라 다음을 보완한다.

- 모든 IntervalTier는 0–xmax를 빈 interval까지 포함해 연속적으로 덮는다.
- `utterance`의 텍스트는 첫 유표 words 시작–마지막 유표 words 끝에 놓고
  근거 있는 앞뒤 padding을 빈 interval로 보인다.
- MFA `words/phones`의 시간·라벨은 이 표시 개선 때문에 바꾸지 않는다.
- `original_form`과 `pron_reference`는 전량 정본 tier가 아니라 연구자 점검
  사본에만 온디맨드로 주입한다.
- `pron_reference`는 원전사 우선 규칙 기반 기준선이며 사전 발음 또는 실제
  음향 실현값이 아니다.

세부 근거:
`REVIEW_MFA_pilot_manual_feedback_2026-07-25.md`.
