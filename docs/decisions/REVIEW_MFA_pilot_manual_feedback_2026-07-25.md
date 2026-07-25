# MFA 층화 파일럿 수동 검토 반영

작성일: 2026-07-25  
대상 run: `pilot_year10_speaker5_v2_20260724`  
사용자 검토 자료:
`C:\Users\ari30\Dropbox\000_2026_summer_research\work\pilot_review_v2_20260724\6_review`

## 1. 수동 검토 결과

사용자가 연도별 핵심 발화 7개를 Praat에서 검토했다.

- 전반적인 MFA words/phones와 형태소 TextGrid 품질은 나쁘지 않았다.
- 검색과 향후 이어붙이기를 위해 tier 처음·끝 경계를 더 명확히 볼 필요가 있다.
- `SDRW2300000891.1.1.331`의 숫자 `1`이 MFA words에서 빈 구간으로
  표시되고 기존 CSV의 `form_roman`·`pron_pred_*`에서는 `∅`가 되어 정보가
  소실됐다.
- 연도·화자 하위폴더와 연도별 통합 CSV를 오가며 발화를 찾는 과정이
  번거로웠다.
- `SDRW2300001955.1.1.164`는 처음에는 corpus에서 찾지 못했다고
  보고됐다.

스크린샷 6개와 메모 `확인.txt`는 사용자가 만든 `6_review`에 보존한다.

## 2. 회수 발화의 존재 확인

`SDRW2300001955.1.1.164`는 누락되지 않았다. D: 원본과 Dropbox 점검본
양쪽에서 다음 세 파일을 확인했다.

```text
corpus\2023\SD2302149\SDRW2300001955.1.1.164.wav
corpus\2023\SD2302149\SDRW2300001955.1.1.164.lab
textgrid_4tier\2023\SD2302149\SDRW2300001955.1.1.164.TextGrid
```

CSV에서도 `bareun_selected.csv`와 `search_master_selected.csv`에 한 행씩
존재한다. 파일 누락이 아니라 실제 화자 폴더를 알아야 하고 CSV가 발화별 파일이
아닌 연도별 통합 파일이라 생긴 탐색성 문제다.

## 3. TextGrid 외곽 경계 해석과 수정

모든 tier는 TextGrid 구조상 이미 `xmin=0`, `xmax=WAV 길이`를 가진다. Praat의
바깥 테두리는 내부 경계선처럼 보이지 않으므로 구조적 경계가 빠진 것과 화면에서
빈 interval 경계가 보이지 않는 것을 구분해야 한다.

실제 개선점은 `utterance`가 앞뒤 무음을 포함해 0부터 xmax까지 한 구간으로
작성된 점이다.

수정 원칙:

1. `words`, `phones`, `morphemes`의 원 시간과 라벨은 변경하지 않는다.
2. TextGrid 작성기는 모든 IntervalTier가 0부터 xmax까지 빈 구간을 포함해
   연속 coverage를 갖게 한다.
3. `utterance`의 유표 구간은 첫 유표 words 시작부터 마지막 유표 words
   끝까지로 하고, 근거 있는 앞뒤 padding만 빈 interval로 표시한다.
4. 근거가 없는 1ms 인공 경계나 음향 실현값은 만들지 않는다.
5. 점검용 사본에는 같은 speech span 경계를 원 tier에 분할 경계로 추가하되
   기존 라벨은 그대로 보존한다.

원 v2 TextGrid는 수정하지 않는다. 변경된 표시 방식은 새 점검 사본과 이후
생성되는 TextGrid에만 적용한다.

## 4. 숫자·혼합표기의 발음 정보 손실

목표 발화:

```text
utt_id: SDRW2300000891.1.1.331
form: 무조건 1층으로 된 집에서 살고 싶어.
original_form: 무조건 일 층으로 된 집에서 살고 싶어.
기존 pron_pred_hangul: 무조건 ∅ 된 지베서 살고 시퍼
```

기존 예측기는 숫자가 들어간 어절 전체를 `∅`로 바꾸므로 숫자뿐 아니라
`층으로`까지 소실했다. 숫자 `1`을 항상 `일`로 바꾸는 것도 안전하지 않다.
문맥에 따라 `일`, `하나`, `한`, `첫` 등이 가능하기 때문이다.

채택한 규칙:

1. 기존 form 기반 `form_roman`·`pron_pred_*`는 감사용으로 보존한다.
2. form 기반 결과에 `∅`가 있을 때만 `original_form`을 대체 입력으로 시험한다.
3. 원전사가 placeholder 수를 실제로 줄일 때만 새 reference 열에 채택한다.
4. 출처와 상태를 별도 열에 기록한다.
5. 원전사에도 읽기 근거가 없으면 임의 추측하지 않고
   `pron_reference_status=unresolved_symbol`로 명시한다.
6. 이 reference는 규칙 기반 검색 기준선이며 lexicon 사전 등재 발음이나
   연구자가 판정한 실제 실현값이 아니다.

추가 CSV 열:

```text
pron_reference_form
pron_reference_form_roman
pron_reference_hangul
pron_reference_roman
pron_reference_ipa
pron_reference_source
pron_reference_status
pron_reference_n_eojeol
```

목표 발화의 새 결과:

```text
pron_reference_form: 무조건 일 층으로 된 집에서 살고 싶어.
pron_reference_hangul: 무조건 일 층으로 된 지베서 살고 시퍼
pron_reference_source: original_form_placeholder_resolution
pron_reference_status: resolved_original_form
```

## 5. 실제 CSV 격리 파일럿

`SDRW2300000891` 세션을 새 스키마로 프로젝트 `work` 아래에 격리 재생성했다.

- 입력·출력: 371/371행
- 메타 결측: 0
- 화자 결측: 0
- JSON 결측: 0
- 어절 수 불일치: 0
- 목표 숫자 발화: 원전사로 회복
- 미해결 특수 전사: 1행
  (`((x잖아.))`; 근거 없이 읽지 않고 `unresolved_symbol`)
- 판정: 통과

기존 전량 search master는 수정하지 않았다. 이 코드는 전량본을 새 run으로
재생성할 때 기존본 archive와 함께 적용한다. lexicon 사전 예외 발음 층은 여전히
별도 미완료 과제다.

## 6. 연도별 점검 묶음

신규 스크립트 `build_stratified_mfa_review_bundle.py`는 원 v2 run을 읽기만 하고
연도별 평면 폴더를 만든다.

```text
연도\
  utt_id.wav
  utt_id.lab
  utt_id.TextGrid
  utt_id.csv
  INDEX.csv
```

점검 TextGrid는 다음 6개 tier를 갖는다.

```text
words
phones
morphemes
original_form
pron_reference
utterance
```

합성·실자료 검증:

- 2020–2025 각 10발화
- WAV 60, lab 60, TextGrid 60, 발화 CSV 60
- 숫자·기호 reference 회복: 3발화
- 점검 표본 내 미해결 숫자·기호: 0
- 추가 tier 어절별 정렬: 56/60
- 웃음 표지·복잡 분할 4건: 잘못된 1:1 정렬 대신 발화 전체 구간 폴백과 경고

## 7. 시행착오

첫 실제 bundle 검증은 `speaker_metadata_selected.csv`의 키를 `speaker_id`로
가정해 중단됐다. 실제 열은 `id`였다. 출력 폴더를 승격하기 전 실패하여 원본과
정식 점검본은 변하지 않았다. 코드는 `id`와 `speaker_id`를 명시적으로 지원하게
수정한 뒤 60발화 생성에 통과했다.

## 8. 연구적 해석 제한

- `pron_reference`: 원전사 우선 규칙 기반 기준 발음
- 향후 `morph_pron_dict_*`: lexicon 사전 등재 발음
- `phones`: MFA/G2P 대략적 시간 분절
- 실제 실현: 연구자가 WAV와 TextGrid를 보고 별도 판정

네 층은 서로 덮어쓰지 않는다.

## 9. 대화 상대 화자 ID 추가

사용자 후속 요청에 따라 search master와 발화별 점검 CSV에 다음 열을 추가했다.

```text
dialogue_id
dialogue_speaker_ids
n_dialogue_speakers
co_speaker_ids
n_co_speakers
```

원본 JSON에는 발화별 `speaker_id`는 있지만 직접 수신자(addressee)는 없다.
따라서 `co_speaker_ids`는 발화가 속한 같은 document에 등장하는 화자 중 현재
발화자를 제외한 공동 참여자이며, 특정 발화의 직접 수신자로 해석하지 않는다.
다자대화는 ID를 ` | `로 연결해 모두 보존한다.

2023 목표 세션 371행 격리 재생성 결과:

- 대화 참여자 연결 오류: 0
- 목표 발화 현재 화자: `SD2310934`
- 목표 발화 전체 참여자: `SD2300935 | SD2310934`
- 목표 발화 공동 참여자: `SD2300935`

60발화 점검 bundle의 document 화자 수 분포는 1명 2발화, 2명 52발화,
3명 2발화, 4명 4발화였다. 1명 document 두 발화는 공동 참여자가 없는 것이
정상이며 결측으로 취급하지 않는다.
