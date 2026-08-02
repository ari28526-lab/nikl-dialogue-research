# 2020 MFA 제외표의 미해결 기호·빈 LAB 회계 결정

결정일: 2026-08-02 KST
상태: 현행 2020 생산 계약

## 문제

2020 WAV ID 복구 뒤 첫 승인 후보표에는 음원 대응을 확정할 수 없는
1,834발화만 들어갔다. 후속 LAB 보고서를 대조하니 WAV가 있는 발화 가운데
`pron_reference_status=unresolved_symbol`인 6,211발화가 있었고, 그중 53발화는
기호를 근거 없이 읽지 않는 정책 때문에 정렬할 한글 문자열이 전혀 남지 않아
LAB이 생성되지 않았다. 이 53발화는 첫 후보표에 들어가지 않아, 그대로 승인하면
“승인 제외도 아니고 MFA 입력도 아닌” 암묵적 누락이 된다.

이는 2020 전수 LAB/WAV를 다시 계산해야 하는 문제가 아니라, 이미 생성된 두
검증 결과를 승인 회계에서 결합하지 않은 코드 문제다.

## 동결 증거

- 입력 계약 ID:
  `7b52204cdb2119b057e5d961ecd75ab33858a3f5a1323d5018d9649e24f53840`
- LAB 보고서:
  `D:\mfa_eojeol\logs\lab_build_2020_latest.json`
- 미해결 기호 인벤토리:
  `D:\mfa_eojeol\logs\lab_build_2020_7b52204cdb21_unresolved_symbols.csv`
- 검색 행: 870,437
- 복구 파생 WAV 누락: 1,834
- 생성 LAB: 868,550
- LAB 단계 미해결 기호: 6,211
  - 부분 LAB 있음: 6,158
  - 빈 LAB: 53
- 검색표 전체의 미해결 기호는 6,220이며, LAB 단계 6,211과의 차이 9건은
  1,834건의 음원 미대응 집합에 이미 포함된다.

보고서·인벤토리·감사표·복구계획은 경로뿐 아니라 SHA-256으로 최종 manifest에
묶었다.

## 결정

1. `audio_pairing_unresolved` 1,834건은
   `alignment_and_analysis` 제외 후보로 유지한다.
2. WAV는 있으나 LAB이 비어 있는 53건을
   `empty_reference_unresolved_symbol`이라는 별도
   `alignment_and_analysis` 제외 후보로 추가한다.
3. 부분 한글 LAB이 있는 6,158건은 전체 발화를 제외하지 않는다. 기호를
   임의 발음으로 바꾸지 않은 현재 LAB으로 정렬하되,
   `pron_reference_status=unresolved_symbol`을 post-MFA
   `utterance_alignment.csv.gz`까지 그대로 전달한다.
4. `2=둘` 같은 전역 치환은 하지 않는다. 문맥에 따라 `이/둘/두` 등이 될 수
   있으므로, 원 JSON·원전사·사전 등 출처가 확인된 경우만 국소적으로 해소한다.
5. 후일 출처가 확보된 발화는 해당 발화만 LAB 교정·국소 재정렬한다. 이 때문에
   2020 연도 전체를 처음부터 다시 정렬하지 않는다.

따라서 최종 연구자 승인 후보는 정확히
`1,834 + 53 = 1,887`건이다. 6,158건은 승인 제외 후보 수에 더하지 않는다.

## 반복 방지와 활성본

첫 1,834건 검토 root는 삭제하지 않고 다음으로 이동했다.

```text
outputs/reviews/archive/
  mfa_exclusions_queue_mfa_r2_prod_2020_20260801_pre_symbol_accounting_20260802/
```

2020년의 유일한 활성 승인표는 다음이다.

```text
outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_20260801/2020/
  00_READ_ME_FIRST.md
  00_CATEGORY_SUMMARY.json
  03_RESEARCHER_REVIEW.csv
  03_RESEARCHER_REVIEW_MANIFEST.json
  04_RESEARCHER_APPROVED.csv
  04_RESEARCHER_APPROVAL.json
  approved_exclusions.json
```

활성본은 전수 LAB 생성, WAV 스캔, MFA를 다시 실행하지 않았다. 기존 검증 증거를
읽기 전용으로 결합하는
`scripts/finalize_2020_mfa_review_from_verified_evidence.ps1`로 한 번 생성했고,
동일 폴더에 결과가 있으면 덮어쓰지 않고 중단한다.

## 방법론적 보고

논문에는 숫자·영문·기호가 포함된 발화에서 기계적 발음 추정을 연구자의 실제
실현 판정으로 간주하지 않았다고 쓴다. 한글 부분이 남는 경우에는 그 부분만 MFA
입력으로 사용하고 미해결 상태를 동반표에 보존했으며, 정렬 입력이 완전히 비는
경우에는 명시적 제외 계약으로 회계했다고 보고할 수 있다.

2026-08-02 13:27 KST에 연구자 `ari30`이 “두 범주 모두 승인”이라고 명시했다.
원 `pending` 후보표는 변경하지 않고 별도 승인 CSV를 만들었으며, 승인자·시각·
문구·두 범주 합계·후보/승인 SHA를 `04_RESEARCHER_APPROVAL.json`에 기록했다.
`approved_exclusions.json`은 이 승인본과 입력 계약 ID에 결속됐다. 이는 자동
승인이 아니며 MFA는 아직 수행하지 않았다.
