# 공통발음사전 Jamo G2P no-path 보완 결정

작성일: 2026-07-28
적용 release:
`D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728`

## 결론

동결한 `korean_mfa` Jamo G2P v3.2.0이 지원 grapheme로 이루어진
표층 어절을 입력받고도 FST 경로를 찾지 못해 exit code 0과 함께 그
어절을 출력에서 누락할 수 있다. 이를 성공이나 `spn`으로 간주하지 않는다.

다음의 제한된 보완만 허용한다.

1. 표층형과 표준 발음 재철자의 대응을 명시적인 후보표에 기록한다.
2. 재철자를 **같은 동결 Jamo G2P v3.2.0**에 넣어 MFA phone 후보를
   만든다.
3. 표층형–재철자–phone의 정확한 한 후보를 연구자가 승인한다.
4. 직접 모델 출력에서 실제로 누락된 표층 키만 추가한다.
5. 같은 shard에서 모델이 이미 생성한 모든 행은 byte-level 의미에서
   발음열을 바꾸지 않는다.
6. 보완 전 partial shard, 승인 당시 검토행, 입력·출력·모델·코드 SHA와
   완전성 재검증 결과를 보존한다.

새 후보가 미승인이어도 장시간 계산 전체를 즉시 끝내지는 않는다.
그 shard의 partial을 보존하고 다음 shard를 계산한다. 다만 모든 미승인
누락이 해결되기 전에는 final 공통사전과 연도별 MFA adoption을 금지한다.

## 발견 경위

- 2026-07-28 shard 5에서 MFA G2P는 25,000개 입력을 처리한 뒤
  `Done`과 exit code 0을 반환했다.
- 독립 완전성 검사는 출력이 24,999행임을 발견하고
  `missing=1, extras=0`으로 안전 중단했다.
- 누락 표층형은 Unicode codepoint
  `U+C74A U+C5B4`, 즉 `읊어`였다.
- `읊어`만 동결 모델에 다시 입력해도 exit code 0, 출력 0바이트가
  재현됐다. 일시적 I/O 실패가 아니라 deterministic FST no-path이다.
- 1–4번 shard 100,000행은 각각 missing=0, extras=0, spn=0,
  acoustic phone inventory 이탈=0으로 이미 검증됐고 재계산하지 않는다.
- 5번의 24,999행 출력과 log도 삭제·archive 이동 없이 원 위치에
  보존했다.

## `읊어` 후보의 근거와 승인 범위

- 국립국어원 공식 답변은 표준 발음을 `읊어[을퍼]`로 제시한다.
  <https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=216&pageIndex=1&qna_seq=312938&searchCondition=&searchKeyword=>
- 프로젝트의 독립 규칙 예측 열도 `읊어 → 을퍼`로 일치했다.
- 같은 동결 Jamo G2P에 `을퍼`를 입력한 결과는
  `ɨ ɭ pʰ ʌ`이며 acoustic v3.3.0 phone inventory 안에 있다.
- 2026-07-28 사용자는 이 정확한 후보
  `읊어 → 을퍼 → ɨ ɭ pʰ ʌ`를 명시적으로 승인했다.
- 이 승인은 다른 `읊-` 활용형이나 다른 no-path 단어에 대한 포괄
  승인이 아니다.

## 포괄 자동 승인을 하지 않는 이유

전수 vocabulary에서 관측된 `읊-` 계열 30개를 별도 진단했을 때
동결 모델은 24개 표층형에서 no-path를 보였다. 프로젝트 규칙 예측으로
만든 재철자 24개는 모두 phone 출력을 얻었지만, 예를 들어
`읊고 → 읍꼬`의 출력에는 장음 표지가 포함되어 연구 목적에 맞는지 별도
검토가 필요했다. 따라서 “규칙 예측이 존재한다”는 사실만으로 후보를
자동 채택하지 않는다.

## 2026-07-29 실제 추가 no-path 후보

야간 전수 계산에서 다음 세 표층형이 실제로 추가 누락됐다.

| shard | 표층형 | 표준 발음 재철자 후보 | 같은 동결 모델 phone | 상태 |
|---:|---|---|---|---|
| 8 | 읊을 | 을플 | `ɨ ɭ pʰ ɨ ɭ` | pending |
| 12 | 읊는 | 음는 | `ɨ m n ɨ n` | pending |
| 15 | 읊은 | 을픈 | `ɨ ɭ pʰ ɨ n` | pending |

국립국어원 표준 발음법 제18항 공식 예시는 `읊는[음는]`을 직접
제시한다.
<https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=261&pageIndex=1&qna_seq=317050>

국립국어원 공식 연수 교재 검색 근거에는 `읊은[을픈]`이 제시된다.
`읊을[을플]`은 제14항의 겹받침 뒤 모음 시작 어미 연음 규칙 적용
후보이다. 이 근거와 모델 phone이 일치하더라도 세 후보는 사용자의
명시적 승인 전까지 production shard에 추가하지 않는다.

08:28 shard 29의 저빈도 구간에서 나머지 20개 후보도 실제 no-path로
확인됐다. 따라서 전수 상태는 다음과 같다.

- 승인·보수 완료: `읊어` 1개
- 연구자 검토 대기: `읊을`, `읊는`, `읊은`과 shard 29의 20개,
  합계 23개
- 후보 원장 밖 미등록 누락: 0개
- 계산 중단: 없음; shard 30으로 계속

이 결과는 사전 진단한 24개 후보 집합이 실제 전수 누락 집합과 정확히
일치함을 뜻한다. 그러나 후보 집합 일치는 발음 적합성의 증거가 아니다.

특히 `읊고`는 다음 두 판단을 분리해야 한다.

1. **표준 발음 판단:** 국립국어원 한국어 어문 규범의 표준 발음법
   제11항은 `읊고[읍꼬]`를 직접 제시한다. 따라서 `읊고→읍꼬`라는
   표층형–재철자 대응 자체에는 공식 규범의 직접 근거가 있다.
   <https://korean.go.kr/kornorms/regltn/regltnView.do?regltn_code=0002>
2. **MFA phone 변환 판단:** 동결 Jamo G2P에 재철자 `읍꼬`를 넣어 얻은
   후보 `ɨː m k͈ o`는 종성 [ㅂ]이 아니라 `m`을 내고 장음까지 포함한다.
   이는 공식 표준 발음 대응이 맞다는 사실과 별개로, 해당 재철자 입력의
   모델 phone이 연구용 사전에 채택 가능한지를 반증하는 신호다.

그러므로 `읊고`의 공식 발음을 의심하는 방식으로 해결하지 않는다.
전수 계산이 끝난 뒤 같은 동결 모델에 최소 대체 재철자를 넣어
`[읍꼬]`의 phone 구조를 보존하는 후보가 있는지 비교하고, 원 모델
버전·phone inventory·후보별 출력·채택 이유를 함께 기록한다. 이 검사가
끝나기 전에는 `읊고`를 승인하지 않으며, 다른 22개도 공식 규칙 근거와
모델 phone 적합성을 각각 확인한 뒤 승인 범위를 정한다.

## 2026-07-29 연구자 검토표 예비 선별

전수 G2P를 그대로 실행하면서
`03_review/g2p_no_path_researcher_review.csv`의 24행을 읽기 전용으로
전수 확인했다. 이는 승인 판정이 아니라, 계산 종료 뒤 필요한 검토의
우선순위를 정하기 위한 예비 선별이다.

- 승인 완료 1개: `읊어→을퍼→ɨ ɭ pʰ ʌ`
- 명백한 보류 1개: `읊고→읍꼬→ɨː m k͈ o`
- 나머지 pending 22개: 재철자의 자모 연쇄와 모델 phone이 첫 구조
  점검에서는 대응했다. 예를 들어 `읊는→음는→ɨ m n ɨ n`,
  `읊은→을픈→ɨ ɭ pʰ ɨ n`, `읊어서→을퍼서→ɨ ɭ pʰ ʌ sʰ ʌ`이다.

이 22개를 자동 승인하지 않는 이유는 다음과 같다.

1. 활용형 전체의 규범 발음을 직접 예시, 규칙 적용, 프로젝트 독립
   예측 가운데 어느 근거가 지지하는지 구분해야 한다.
2. `b`, `bʷ`, `sʰ`, `nː`, `ɲ`, `ɾʲ` 같은 기호는 동결 acoustic/G2P
   phone 체계의 문맥 변이일 수 있으므로, 다른 정상 단어의 같은 문맥과
   비교해야 한다.
3. `읊으는`처럼 표층 형태 자체가 규범적 활용인지 의심되는 코퍼스
   전사도 있다. 이는 사전에서 임의 삭제할 문제가 아니다. 원문
   JSON/form/original과 음성을 확인하고, **관측 전사 정렬용 항목**인지
   **규범 발음 근거 항목**인지 provenance에서 구분해야 한다.

따라서 계산 종료 후 검토 순서는 (a) `읊고` 최소 재철자 대조,
(b) 22개 phone 문맥 대조, (c) 원문 전사 확인이 필요한 표층형 확인,
(d) 연구자 명시 승인, (e) partial shard만 원자적으로 복구 순이다.

## 산출물과 감사 경로

- 후보 원장:
  `config/common_pron_g2p_no_path_exceptions.csv`
- 생성·검토·보수 코드:
  `scripts/python/common_pron_no_path_review.py`
- 실제 연구자 검토표:
  `03_review\g2p_no_path_researcher_review.csv`
- `읊어` 승인 기록:
  `03_review\decisions\eulp-eo_20260728.json`
- shard별 시도·partial backup·승인행 snapshot·보수 manifest:
  `_state\no_path_repairs\<shard>\`
- final 방법론 supplement:
  `00_contract\g2p_no_path_method_supplement.json`

실제 D: 경로의 앞부분은 위 release root이다.

finalizer는 보수 manifest, 원 partial SHA backup, 승인 snapshot, 최종
shard, 후보 재철자 raw G2P, 동결 acoustic·Jamo G2P·model pin SHA를 다시
검증한다. `g2p_cache.csv`에서는 승인 보수된 정확한 행의 `pron_source`만
`researcher_approved_standard_respelling` 계열로 교정한다. phone열과
최종 MFA dictionary는 바꾸지 않는다. 기존 prepare contract ID를
보존하면서 supplement SHA를 포함한 별도 production contract ID를
만들고, adoption contract가 이를 다시 검증해야 연도별 MFA를 허용한다.

## 방법론 문장 초안

> 2020–2025년 공통 어절 사전의 OOV 발음은 동결된 한국어 Jamo G2P
> v3.2.0의 1-best 출력으로 생성하였다. 모델이 정상 종료했으나 특정
> 표층형에 대해 유한상태 경로를 산출하지 못한 경우에는, 공식 규범 및
> 독립 규칙 예측으로 근거가 확인된 표준 발음 재철자를 동일한 동결
> 모델에 입력해 phone 후보를 생성하였다. 연구자가 표층형–재철자–phone
> 대응을 승인한 경우에만 누락 키를 추가했으며, 모델이 직접 생성한
> 기존 발음은 변경하지 않았다. 모든 예외는 입력, 모델, 코드, 원 partial,
> 승인 snapshot 및 최종 shard SHA와 함께 기록하였다.

이 문장은 r2 final method supplement와 2020–2025 cross-year contract가
모두 통과한 뒤에만 최종 연구 방법으로 사용한다.
