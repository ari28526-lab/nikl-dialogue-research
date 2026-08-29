# 바른 v3.1 형태소 이후 TextGrid·문맥 WSD 계획

작성일: 2026-08-29 KST

상태: **형태소-only 전수·감사 완료, TextGrid 12건 파일럿 통과, 전수는 용량 확보 대기**

## 결정

현재 실행 중인 바른 v3.1 형태소-only 전수를 중단하지 않는다. 전수 결과가
`bulk_csv_v1`로 승격되고 receipt/SHA 독립 감사를 통과한 뒤, 다음 두 후속층을
서로 분리해 만든다.

1. 기존 r3 MFA 시간 정렬을 이용한 새 버전 TextGrid 표시층
2. 우리말샘·공식 WSD gold·문맥 donor로 호출 범위를 줄인 의미번호층

MFA는 WSD의 입력이나 선행조건이 아니다. 형태소·WSD는 전체 텍스트
5,103,356발화를 대상으로 유지하고, MFA TextGrid는 정렬이 존재하는 발화를
실제 음성 시간축에 연결해 검색·청취·연구자 판정할 때 사용한다.

## 최종 외장하드 동결 목표

최종 동결본은 외장하드 안의 다음 다섯 자산군을 하나의 release manifest와
`utt_id` 교차표로 결속한 연구 말뭉치다.

1. 원본 WAV
2. 원본 JSON
3. 바른 v3.1 형태소 분석열 CSV
4. WSD 분석 시도·근거·결과열 CSV
5. 기존 표시 수준을 유지하면서 새 형태소를 반영한 TextGrid

WAV·JSON은 이미 외장하드에 있는 정본을 이동하거나 복제하지 않고 읽기 전용으로
동결한다. 파생 CSV와 TextGrid만 별도 versioned root에 생성한다. 최종 manifest는
드라이브 문자에만 의존하지 않도록 volume 식별자와 상대경로, 파일 수·크기·SHA,
생성 계약·코드 commit을 기록한다.

WSD CSV는 성공한 의미번호만 모으는 표가 아니다. 대상 occurrence를 zero-drop으로
보존하고 최소한 다음 상태를 구별한다.

- `not_target`
- `urimalsaem_monosemous`
- `ml2025_direct_gold`
- `exact_context_unanimous`
- `bareun_wsd_resolved`
- `unresolved_no_donor`
- `donor_conflict`
- `alignment_conflict`
- `api_attempt_failed`

각 행에는 `sense_id`, `candidates`, `method`, `source_corpus`, `donor_count`,
`confidence`, `attempt_status`, `error_class`, `engine_version`, 입력·응답 receipt/SHA를
남긴다. WSD 미시도·실패·미확정은 누락이나 빈 성공값으로 숨기지 않는다.

동결 교차표는 각 `utt_id`에 대해 WAV·JSON·형태소 CSV·WSD CSV·TextGrid의 경로와
존재/제외/미정렬 상태를 한 행에 기록한다. MFA가 없는 발화도 형태소·WSD 범위에서
삭제하지 않고 `no_mfa_alignment`로 회계한다.

## MFA TextGrid를 사용하는 시점과 방법

형태소 전수 final 감사 직후 기존 r3 MFA DB/TextGrid를 읽기 전용 시간축으로
사용한다. 기존 TextGrid와 WAV는 수정하지 않고 새 run root에 새 TextGrid를
생성한다.

- `words`, `phones_mfa`, `phoneme_r_auto`, `utterance`,
  `utterance_orth_r`의 시간·label은 현 r3 정본과 byte/semantic 동등하게 보존한다.
- 기존 6-tier의 발화 수준 `morph_analysis_utt` label만 새 바른 v3.1 형태소열로
  갱신한다. 형태소마다 근거 없는 음향 시간 경계를 새로 만들지 않는다.
- 조인은 `utt_id`와 어절 좌표를 사용한다. 새 형태소 어절 수와 MFA `words`
  좌표가 맞지 않으면 추정 보정하지 않고 `alignment_conflict` 또는
  `no_mfa_alignment`으로 sidecar에 보존한다.
- MFA가 없거나 보류된 발화도 형태소·WSD CSV에서 제외하지 않는다. 나중에 정렬이
  생기면 같은 `utt_id`로 연결한다.
- 의미번호는 기본 6-tier에 전수 복제하지 않는다. CSV/Parquet sidecar를 정본으로
  두고, 연구 후보를 열 때만 선택적 `sense` tier 또는 reviewer 표시로 주입한다.

즉, MFA TextGrid는 **WSD를 결정하는 도구가 아니라**, 새 형태소·의미 결과로
찾은 후보를 실제 WAV의 word/phone 구간으로 이동시켜 사람이 듣고 판정하는
도구다.

### 최소 표시 수용 기준

새 TextGrid는 sidecar만 생성하고 끝내지 않는다. 기존 r3 생산 TextGrid에서
연구자가 확인할 수 있었던 다음 6-tier를 실제 TextGrid 안에 모두 표시하는 것을
최소 기준으로 한다.

1. `words`
2. `phones_mfa`
3. `phoneme_r_auto`
4. `utterance`
5. `utterance_orth_r`
6. `morph_analysis_utt` — 새 바른 v3.1 결과로 갱신

앞의 다섯 tier는 기존 정본과 시간·label 의미가 같아야 하고, 여섯 번째 tier는
새 형태소 final과 정확히 일치해야 한다. 기존 tier 삭제, 이름 변경, 빈 tier로의
대체는 허용하지 않는다. 검증된 의미번호를 TextGrid에도 표시할 필요가 생기면
이 최소 6-tier 위에 선택적 `sense_analysis_utt`를 추가할 수 있지만, WSD 완료를
기다리느라 새 형태소 6-tier 갱신을 막지는 않는다.

## WSD 호출 범위 축소 순서

새 형태소 occurrence마다 다음 우선순위를 적용한다.

1. 조사·어미·기호 등 WSD 비대상은 `not_target`으로 보존한다.
2. 동결한 우리말샘 목록에서 `(형태소 기본형, 품사)`의 의미 후보가 하나면
   `urimalsaem_monosemous`로 확정한다.
3. 다층위 2025 구어부와 동일 `utt_id`인 발화는 그 안의 공식 `WSD` 주석을
   `ml2025_direct_gold`로 직접 연결한다.
4. 다층위 2025 문어·구어 전체와 LS 2020에서 다음 exact donor를 순서대로 찾는다.
   - 완전 동일 문장과 target 좌표
   - `target 형태소 + 품사 + target 표면 어절 + 앞 2어절 + 뒤 2어절 + 문장경계`
5. 같은 exact key의 모든 donor가 같은 의미번호일 때만
   `exact_context_unanimous`로 전이한다. 하나라도 충돌하면 자동 확정하지 않는다.
6. 위 단계 뒤에도 남은 다의어가 있는 발화만 전체 문맥을 보존해 바른 WSD에
   보낸다. 동일 정규화 문장과 엔진/옵션 조합은 SHA 기반으로 한 번만 호출한다.
7. 바른 WSD 응답의 새 형태소열·품사·어절 좌표가 형태소-only 정본과 정확히
   같을 때만 의미번호를 병합한다. 불일치는 `alignment_conflict`로 보류한다.

모든 의미 occurrence에는 최소한 `sense_id`, `method`, `source_corpus`,
`donor_count`, `confidence`, `candidates`, `conflict_status`, `engine_version`을
남긴다. 다의어에 최빈 의미나 사전 첫 번호를 강제로 넣지 않는다.

국립국어원의 별도 `어휘 의미 분석 말뭉치 2025`를 추가로 확보하면, 다층위
2025의 WSD 층과 문서 ID·문장·SHA를 먼저 비교한다. 동일 자료를 별도 donor로
중복 계산하지 않고 실제 추가 범위만 등록한다.

## 실행 순서

1. [완료] 형태소-only 전수의 final 승격과 전수 receipt/SHA 감사를 완료한다.
2. [완료] 새 형태소 결과에서 TextGrid 예상 용량과 출력 파일 수를 표본으로 추정한다.
3. [기계 감사 완료·사용자 3건 확인 대기] 6개년 균형 표본으로 새
   `morph_analysis_utt` TextGrid와 sidecar 조인을 만들고
   기존 five-tier 시간·label 불변, 새 형태소 label, mismatch 회계를 독립 감사한다.
4. D:에 예상 완성 크기와 15 GiB 안전 여유가 모두 확보될 때만 별도 versioned
   root로 전수 TextGrid를 생성한다. WAV를 복사하거나 MFA를 재실행하지 않는다.
5. 새 형태소 전수에서 `WSD_SCOPE_INVENTORY`를 만들어 무호출·gold·donor·잔여
   Bareun WSD 발화/토큰/어절 수와 예상 시간을 먼저 보고한다.
6. 다층위 2025 직접 gold와 exact-context donor 파일럿을 독립 검증한다.
7. 사용자가 잔여 요청량을 확인한 뒤에만 checkpoint·receipt·자동 냉각을 갖춘
   잔여 Bareun WSD 전수를 실행한다.
8. WAV·JSON 원본 inventory와 새 형태소/WSD CSV·TextGrid inventory를 `utt_id`로
   전수 결속하고 release manifest 및 독립 SHA 감사를 통과시켜 외장하드 동결본으로
   승격한다.

## 중지 조건

- 형태소 final 감사 실패
- 원본 또는 기존 r3 TextGrid/WAV 변경 탐지
- TextGrid 예상 완성 뒤 D: 여유가 15 GiB 미만
- `utt_id`·어절 좌표 불일치를 추정으로 덮어야만 진행 가능한 경우
- donor 의미번호 충돌을 자동 확정해야만 진행 가능한 경우
- 별도 WSD 2025와 다층위 WSD의 중복 여부가 확인되지 않은 상태에서 합산하는 경우
- WAV·JSON·형태소·WSD·TextGrid 교차표에서 누락을 상태 없이 삭제해야만 수량을
  맞출 수 있는 경우

이 계획은 대화 기억이 아니라 이 문서와 실행 manifest를 정본으로 삼는다.
