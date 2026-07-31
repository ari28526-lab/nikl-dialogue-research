# TextGrid tier 표준 변천과 현재 활성 표준

이 문서는 2026-07-11 이후의 시행착오를 시간순으로 보존한다. 이전 절의
“표준” 표현은 당시 판정을 뜻하며, 새 전수 출력에는 문서 맨 아래의
**2026-07-31 연구 검색 표준 v5**를 적용한다.

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

## 2026-07-25 점검 사본 v3 — 검증 후 기본본에서 대체됨

운영 4-tier와 연구자 점검 사본을 구분한다. 운영본의 원시간은 바꾸지 않는다.
점검 사본은 가시적인 양끝 경계와 provenance를 위해 WAV 좌우에 0.05초 무음을
추가하고 모든 TextGrid 시간을 +0.05초 이동한다.

점검 tier:

```text
words
phones_mfa
morphemes_legacy
morph_analysis
original_form
pron_reference
utterance
```

- `phones_mfa`: MFA/G2P 분절이며 실제 실현이 아님
- `morphemes_legacy`: 구형 형태소 분절
- `morph_analysis`: 현재 Bareun 형태소열을 어절 시간에 표시; 형태소 내부
  음향 경계가 아님
- 원시간 환산: `source_time = review_time - review_edge_padding_left_seconds`
- KOINA·candidate·human judgment는 선택 후보에만 이후 추가

60발화 전수에서 7개 tier 모두 좌우 가시적 빈 interval과 0–xmax 연속성을
통과했다.

v3는 출처를 분리해 비교하는 실험판으로는 유효하지만, Praat 점검 화면에
발화 수준 정보를 여러 tier로 반복해 기본본이 지나치게 복잡했다. 파일은
시행착오 기록으로 보존하되 기본 점검 표준으로 사용하지 않는다.

## 2026-07-25 최소 점검 사본 v4 — 현재 기본 표준

기본 점검본은 다음 4-tier로 줄인다.

```text
words
phones_mfa
morph_analysis
utterance_info
```

- `utterance_info` 단일 label에 `[UTT]`, `[FORM]`, `[ORTH_R]`,
  `[RULE_H]`, `[RULE_R]`를 둔다.
- `original_form` 또는 숫자·기호 보완용 `reference_form`이 form과 다를
  때만 `[ORIG]`, `[REF_FORM]`, `[REF_ORTH_R]`를 추가한다.
- 형태소별 철자 로마자, 사전 예외 발음, 의미번호, 음운·형태 경계 검색은
  CSV/Parquet이 정본이다.
- `morphemes_legacy`, `candidate`, `pron_dict`, `prosody_koina`,
  `human_judgment`는 해당 비교·분석이 필요한 사본에만 주입한다.
- `RULE_H/R`과 `phones_mfa`는 실제 실현 판정값이 아니다.

60발화 전수 검증:

- 4-tier 스키마와 전 tier 좌우 가시적 빈 interval: 60/60
- 원 WAV 중앙 PCM 보존과 좌우 무음: 60/60
- 원 `words/phones` 의미 대조: 120/120
- 발화 검색 표지 `UTT/FORM/ORTH_R/RULE_H/RULE_R`: 각 60/60

전량 운영 TextGrid는 CSV 검색 정본과 중복을 줄이기 위해 장기적으로
`words/phones_mfa/utterance` 3-tier를 권장한다. 다만 현재 4-tier 전량
파이프라인과의 호환 검증 전에는 기존 `morphemes`를 삭제하거나 이름만
일괄 변경하지 않는다.

## 2026-07-31 연구 검색 표준 v5 — 현재 활성 표준

v3와 v4는 시행착오와 비교 근거로 보존하되 새 전수 출력의 활성 표준은
다음 4-tier로 교체한다.

```text
words
phones_mfa
utterance
utterance_search
```

- `words`와 `phones_mfa`는 보존 MFA DB에서 직접 내보내며 시간·라벨을
  표시 편의를 위해 바꾸지 않는다.
- `utterance`는 사람이 읽는 `form`을 첫 유표 word부터 마지막 유표
  word까지 표시한다.
- `utterance_search`에는 `[UTT]`, `[ORTH_R]`, `[MORPH]`, `[MORPH_R]`를
  넣고 `align_warn`가 있을 때만 `[NOTE]`를 추가한다.
- 형태소의 음향 경계를 주장하는 `morph_analysis` tier는 활성 표준에서
  제거한다. 정밀 위치 검색의 정본은 `morph_tokens`, `morph_units`,
  `morph_boundaries`와 선택 파생표 `orth_components`다.
- 규칙·사전 발음, KOINA, wav2vec2, 연구자 실제 실현 판정은 기본 tier에
  합치지 않는다.

보존 DB·CSV를 사용한 60발화 재수출에서 새 TextGrid 60/60,
DB의 기존 word/phone과 의미 동등성 60/60, CSV와
`[MORPH]/[MORPH_R]` 동등성 60/60을 통과했다. 연구자 점검 사본 12개는
WAV에 좌우 0.05초 무음을 붙이고 모든 tier를 함께 이동해 양끝 빈
interval을 12/12 보장한다. 운영 원시간 파일에는 존재하지 않는 무음을
임의로 만들지 않는다.

세부 정정과 실측 근거:
`docs/reviews/RESOLUTION_design_review_morph_roman_position_schema_20260731.md`.
