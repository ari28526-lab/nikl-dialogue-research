# 2020–2025 전체 코퍼스 공통 발음사전 파일럿 착수 기록 (역사 기록)

작성일: 2026-07-28
상태: **6개년 전수 vocabulary·사전 원천 감사 완료, registry·A/B 사전 생성 전**

관련 설계:

- `DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md`
- `DESIGN_pronunciation_environment_search_2026-07-25.md`
- `AUDIT_2020_2021_MFA_comparison_and_2022_gate_20260728.md`

## 1. 파일럿 범위 재확인

공통 발음 자원의 모집단은 소표본이 아니라 **2020–2025 연도별 전체 동결
코퍼스**다.

```text
6개년 동결 pron_reference_form 전수
  → MFA lab과 같은 규칙으로 전체 어휘 추출
  → 기본 MFA 사전·고정 G2P·사전 발음 후보를 출처별 registry로 결합
  → 공통 MFA 파생사전 A/B
```

소표본은 공통 사전을 만드는 데 쓰지 않는다. 기존 6개년 층화 표본과 발음
stress 표본은 정책 A/B의 **정렬 품질을 검증할 때만** 사용한다. 정책을
채택하면 같은 release를 2020–2025 전체에 적용한다.

## 2. 격리 release와 보존 정책

release:

```text
D:\mfa_common_pron\releases\common_pron_pilot_full6y_20260728
```

구조:

```text
00_contract       입력·release 계약
01_vocabulary     6개년 전수 어휘
02_source_audit   사전 원천 감사
03_registry       출처 보존 발음 registry
04_mfa_lexicons   정책 A/B 파생사전
05_ab_corpus      동일 WAV·lab 파일럿 코퍼스
06_ab_results     정렬·자동 QC 결과
07_review         연구자 검토 사본
logs              실행 로그
archive           같은 release 안의 구판 보존
```

정책:

- 원 JSON·WAV·동결 CSV와 2020·2021 baseline은 읽기 전용
- 기존 TextGrid·DB·marker 자동 덮어쓰기 금지
- 파일럿 결과의 canonical 자동 승격 금지
- 대형 산출물은 D:에 두고 Git에는 코드·작은 manifest·보고서만 저장
- 기존 release ID 재사용·덮어쓰기 금지

## 3. 6개년 전체 vocabulary 실측

입력:

```text
D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725
```

MFA lab 생성과 같은
`realign_eojeol_build_corpus.form_to_lab()`으로
`pron_reference_form` 5,103,356행을 전수 토큰화했다.

| 연도 | 세션 CSV | 발화행 | 어절 출현 | 고유 어절 | 빈 lab 행 | 미해결 기호 행 |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 2,232 | 870,437 | 3,053,363 | 229,899 | 53 | 6,220 |
| 2021 | 4,143 | 1,373,920 | 6,642,222 | 327,135 | 399 | 17,394 |
| 2022 | 2,654 | 866,359 | 4,500,448 | 274,360 | 253 | 10,106 |
| 2023 | 1,973 | 677,262 | 3,626,227 | 252,084 | 107 | 5,039 |
| 2024 | 3,227 | 728,257 | 5,137,438 | 294,919 | 22 | 12,945 |
| 2025 | 2,927 | 587,121 | 4,887,370 | 312,305 | 14 | 3,494 |
| **전체** | **17,156** | **5,103,356** | **27,847,068** | **881,237** | **848** | **55,198** |

산출물:

```text
01_vocabulary\common_vocabulary_2020_2025.csv
bytes=29,383,023
sha256=3a6ecbe3a18508dd6807e6d5c8b3ced2179420e2e9fa93967a085daecce25319
```

전수 스캔과 쓰기는 291.159초가 걸렸다. manifest가 기록한 실행 코드
commit은 `14cc43eebfab7246f5bcb29f1a0648e01f911b79`다.

## 4. 사전 원천 전수 감사

| 원천 | 전체 행 | `pron_1` | `pron_2` | `pron_g2p` |
|---|---:|---:|---:|---:|
| enriched v2 | 1,165,157 | 500,561 | 38,340 | 사용하지 않음 |
| legacy 1기 | 1,296,777 | 613,441 | 41,237 | 683,336 |

enriched에서 `pron_1/2`가 모두 없는 664,596행은 모두 같은
`urimal_id`의 legacy `pron_g2p` 하나에 연결됐다.

```text
미대응 enriched urimal_id       0
fallback당 legacy 발음 1개      664,596
fallback당 legacy 발음 2개 이상 0
```

해석은 다음처럼 고정한다.

- enriched `pron_1/2`: 사전 연계 발음 후보, 품사·의미·사전 ID 보존
- legacy `pron_g2p`: 과거 기계 생성 보완 후보
- `pron_g2p`를 우리말샘 등재 발음으로 부르거나 합치지 않음
- 다의어의 가장 작은 의미번호를 대표 발음으로 자동 선택하지 않음

## 5. 새로 확인한 phone 체계 gate

enriched의 `pron_1_roman_mfa`·`pron_2_roman_mfa`는 `G I - iEO k`과
같은 과거 프로젝트 로마자 기호다. 현재 MFA 3.4.0의
`korean_mfa.dict`는 `k ɐ tɕʰ i`와 같은 현재 모델용 IPA phone을 쓴다.

따라서 과거 `*_roman_mfa`를 현재 MFA 파생사전에 그대로 삽입하지 않는다.
다음 변환 검증을 먼저 통과해야 한다.

1. 현재 acoustic model phone inventory를 fingerprint와 함께 추출
2. 사전 한글 발음 `pron_1/2`를 현재 `korean_mfa` G2P로 phone encoding
3. 기본 사전에 같은 표제어가 있는 표본에서 phone열과 전수 대조
4. phone set 밖 기호 0건
5. 변환 때문에 사전 발음 자체가 다시 바뀌는 사례와 장음·복수 변이 별도 목록
6. 변환 코드·모델 hash·parameter를 registry 후보에 기록

이는 `pron_1/2`의 발음을 G2P가 새로 결정하게 한다는 뜻이 아니다. 사전이
제시한 한글 발음 문자열을 현재 음향모델이 받는 phone alphabet으로 표현하는
변환 단계이며, 그 동등성을 먼저 검증한다.

## 6. 용량과 정리 결정

초기 D: 여유:

```text
264.146GiB
```

전수 vocabulary·사전 감사 뒤:

```text
264.119GiB
release 실파일 9개, 약 28.035MiB
```

현재 파일럿 준비 산출물은 약 28MiB에 불과하다. 따라서 2021 temp의
31.365GiB 정리 후보를 서둘러 삭제할 필요가 없다.

- 2021 DB·로그·재현 근거: 계속 보존
- 재계산 가능한 63파일/31.365GiB: 기존 dry-run 후보 그대로
- 이번 작업에서 실제 삭제·이동: 0건
- 실제 정리는 exact manifest에 대한 사용자 명시 승인 뒤에만 수행

## 7. GitHub 상태

- 작업 브랜치: `agent/harden-pre-bulk-pipelines`
- 기반 코드·테스트 중간 커밋: `14cc43e`
- 원격 push: 완료
- 원격 브랜치에서 신규 vocabulary builder 존재 확인
- 열려 있는 PR: 0
- 연구와 무관한 `Microsoft/Windows/PowerShell/ModuleAnalysisCache`는
  삭제하지 않고 `.gitignore`로만 제외

## 8. 다음 실행 순서

1. 881,237개 전체 vocabulary 중심의 출처 보존 registry 생성
2. 기본 MFA 사전 exact match, `pron_1`, `pron_2`, legacy `pron_g2p`,
   residual G2P를 서로 다른 후보 행으로 유지
3. 현재 MFA phone encoding 변환 파일럿과 phone inventory gate
4. 사전–G2P 불일치·복수 발음·다의·품사 충돌·조사/어미·미해결 기호를
   포함한 stress 표본 선정
5. 같은 WAV·lab·음향모델에서 정책 A와 B 정렬
6. 자동 QC와 연구자 청취·TextGrid 검토
7. 채택 정책과 재실행 범위를 결정한 뒤에만 2022 전량 또는
   2020·2021 새 release 재정렬

현재 2022 전량은 계속 방법론 HOLD다.
