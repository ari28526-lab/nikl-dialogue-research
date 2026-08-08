# 공통발음 r3 규칙·MFA phone coverage 감사 결과

- 날짜: 2026-08-08 KST
- 입력: no-rule 보류 85,504형·1,140,107회, 동결 Korean MFA v3.3.0 사전·acoustic inventory
- 상태: 전수 읽기 전용 진단·독립 재계산·요약 완료
- 미수행: 발음 후보 채택, canonical selection, adoption, MFA, TextGrid 변경

## 1. 왜 이 감사를 했는가

앞 단계에서 `한번: H A M B EO N ↔ H A n _ B EO n`,
`친구: CH I NG G U ↔ CH I n _ G U` 같은 차이가 많이 발견됐다. 이를 곧바로
“표준발음 규칙 엔진의 비음 위치동화 누락”으로 고치면 정렬용 MFA 변이를
표준발음으로 오인할 수 있다. 반대로 모든 차이를 G2P 오류로 폐기하면 frozen
acoustic model과 함께 제공된 정렬용 발음 변이를 잃는다. 따라서 다음 세 층을
분리해 전수 감사했다.

1. 연구 검색용 의무적 표준발음 규칙형
2. 동결 Korean MFA 사전·G2P의 정렬용 phone 변이
3. MFA가 시간축에 정렬하는 phone 기호와 실제 음성 실현

국립국어원 표준발음법 제21항 해설은 `감기→강기`, `문법→뭄뻡` 같은 조음
위치동화를 수의적인 것으로 보며 표준발음으로 인정하지 않는다고 설명한다.
국립국어원 FAQ도 `친구`가 표준이고 `칭구`는 표준발음이 아니라고 명시한다.
따라서 이 현상을 의무 규칙 엔진에 추가하지 않았다.

- [한국어 어문 규범—표준발음법](https://www.korean.go.kr/kornorms/m/m_regltn.do?regltn_code=0002)
- [국립국어원 FAQ—‘친구’의 표준 발음](https://www.korean.go.kr/front/mcfaq/mcfaqView.do?mcfaq_seq=8184&mn_id=70)

Korean MFA 모델 카드도 이 모델을 강제정렬용으로 설명하고, 발음의 좋고 나쁨을
평가하거나 음성을 독립 전사하는 모델로 사용할 수 없다고 밝힌다. 그러므로
`phones_mfa`는 실제 실현 판정값이 아니다.

- [Montreal Forced Aligner Korean acoustic model](https://huggingface.co/MontrealCorpusTools/korean_mfa)

## 2. 전수 결과

주분류는 서로 중복되지 않게 계산했다.

| 주분류 | 유형 수 | 출현 수 | 해석 |
|---|---:|---:|---|
| 모든 r2 변이가 수의적 위치동화로만 다름 | 36,568 | 525,747 | 정렬용 변이 후보; 표준 규칙 아님 |
| 일부 변이만 수의적 위치동화 | 82 | 16,271 | 다른 변이가 섞여 보류 |
| 위치동화가 아니며 모든 변이가 frozen 기본사전과 정확 일치 | 811 | 229,177 | model-compatible 정렬 변이 근거; 표준발음 주장 아님 |
| 나머지 G2P·규칙·매핑 미해결 | 48,043 | 368,912 | 자동 채택 금지 |
| 합계 | 85,504 | 1,140,107 | — |

중복 근거로 세면 36,650형에 수의적 위치동화 변이가 하나 이상 있고, 1,582형의
모든 r2 변이가 동결 기본사전과 정확히 일치한다. 두 집합은 겹친다. 따라서
`36,650 + 1,582`를 단순 합산하지 않는다.

대표적인 수의적 위치동화 진단은 다음과 같다.

| 표면형 | 출현 수 | r2 phone Roman | 의무 규칙 Roman |
|---|---:|---|---|
| 한번 | 43,629 | `H A M B EO N` | `H A n _ B EO n` |
| 뭔가 | 36,666 | `M W EO NG G A` | `M WO n _ G A` |
| 정도 | 27,326 | `J EO N D O` | `J EO ng _ D O` |
| 친구 | 9,969 | `CH I NG G U` | `CH I n _ G U` |
| 공부를 | 7,005 | `G O M B U R EU l` | `G O ng _ B U _ R EU l` |

`중에서`처럼 r2 G2P phone에서 한 분절이 빠진 사례는 위치동화로 분류되지
않았다. `왜`, `돼`, `어차피`처럼 frozen 기본사전에 정확히 있는 phone열도
표준발음과 동일하다고 선언하지 않고, acoustic model에 맞는 정렬 변이 근거로만
남겼다.

## 3. phone→음소는 일대일이 아니다

동결 기본사전 17,946형·20,978변이에서 phone열과 현재 의무 규칙 Roman의 길이가
같은 위치만 기술적으로 대조했다. 이 대조는 직접 매핑을 학습하기 위한 것이
아니라, 직접 매핑이 불가능함을 확인하기 위한 진단이다. 107개 acoustic phone 중
33개가 두 개 이상의 규칙 비교키와 반복적으로 공존했다.

특히 `pʲ`는 기본사전에서 다음처럼 나타난다.

| MFA phone | 현재 넓은 표시 | 규칙키별 형태 수(동일 길이 위치 대조) | 예 |
|---|---|---|---|
| `pʲ` | `B` | B 132, P 137, PP 6, H 2 | `비`, `피`, `학비`, `넓히` |

따라서 `pʲ`를 TextGrid의 `phoneme_r_auto`에서 언제나 B 또는 언제나 P라고
해석할 수 없다. 이 감사에서 기존 TextGrid를 바꾸지는 않았지만, 후속 6-tier
생성 계약은 이런 phone을 “phone에서 기계적으로 복원한 확정 음소”라고 서술하면
안 된다. `phones_mfa` 원값, 규칙·철자 참조열, 비일대일 경고를 함께 보존해야 한다.

같은 이유로 기본사전에서 `나`에 `n ɐ`와 `d ɐ` 변이가 함께 있는 사실을
`d→N`이라는 보편 매핑으로 일반화하지 않았다. 첫 계산에서는 비일대일 phone이
포함된 47,851형을 하나의 해결 범주처럼 과잉분류했다. 이를 발견한 뒤 첫 결과를
다음 위치로 보존하고 주분류에서 비일대일 표지를 제거해 전수 재생성했다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\archive_intermediate\
  11_rule_phone_coverage_audit_v1_overbroad_noninjective_20260808
```

## 4. 다음 candidate-only 정책

이 결과가 허용하는 다음 단계는 다음 두 집합을 **MFA 정렬용 후보**로만
readiness에 추가하는 것이다.

1. 모든 변이가 수의적 위치동화로만 다른 36,568형
2. 위 집합과 겹치지 않으면서 모든 변이가 frozen 기본사전과 정확히 일치하는
   811형

총 37,379형이다. 이들의 r2 phone열을 그대로 보존하되 다음을 함께 기록한다.

- `rule_pron_roman`: 의무적 표준발음 참조
- candidate phone의 역할: frozen model과 함께 쓰는 정렬용 변이
- 표준발음 동일성 주장: `false`
- 실제 실현 판정: `not_performed`
- canonical 선택·adoption: `false`

일부 변이만 위치동화인 82형과 나머지 48,043형은 그대로 보류한다. 비일대일
phone 표지 하나만으로는 어떤 후보도 승격하지 않는다.

## 5. 산출물과 검증

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  11_rule_phone_coverage_audit\
    no_rule_variant_rule_phone_coverage.csv.gz
    frozen_dictionary_phone_rule_cooccurrence.csv
    RULE_PHONE_COVERAGE_MANIFEST.json

outputs/reports/AUDIT_common_pron_r3_rule_phone_coverage_20260808.json
outputs/reports/REPORT_common_pron_r3_rule_phone_coverage_20260808.json
```

| 산출물 | SHA-256 |
|---|---|
| stage 11 manifest | `d5f04dfb58b58ed2ca88afc6ff1757b887422b56d84b0c79626883923c7ac17f` |
| 독립 감사 | `f9b136dad0b97581f94e2f11ef46dcc86b13c6758b20c811071948c7ed3cf6c4` |
| 요약 보고서 | `3cb25af84b4c53b7a838b392854cc6e569a986fe633f8339b41c047edd3c0f97` |

독립 감사 상태는 `passed_read_only`다. 85,504형·85,741변이, frozen 기본사전
co-occurrence, 107 phone inventory, 주분류와 출현 수를 원 입력에서 다시
계산했다. 모든 mutation flag는 `false`다.
