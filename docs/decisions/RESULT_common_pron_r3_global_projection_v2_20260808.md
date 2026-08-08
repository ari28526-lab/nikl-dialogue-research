# 공통발음 r3 전역 exact donor projection v2 결과

- 날짜: 2026-08-08 KST
- 범위: 기존 G2P target 310,605형·source 312,410형, canonical exact donor 382,891형
- 상태: candidate-only 전역 projection·독립 감사·881,237형 readiness 재연결 완료
- 미수행: 같은 G2P 재실행, canonical 최종 선택, adoption, MFA, TextGrid 변경

## 1. 왜 다시 계산했는가

앞 단계의 projection은 G2P target 가운데 exact였던 96,284형만 donor로 사용했다.
그 결과는 후보를 만드는 데 유용했지만, 전체 canonical inventory에서 이미 exact
근거를 가진 382,891형을 쓰지 않았기 때문에 문맥별 phone 변이를 과소평가할 수
있었다. 좁은 donor에서 우연히 unanimous였던 문맥을 그대로 채택하면 여섯 연도
공통 기준의 근거가 약해진다.

따라서 이미 생성한 G2P 후보는 그대로 동결하고, donor pool만 canonical exact
전체로 넓혀 기존 310,605 target을 모두 다시 비교했다. 출현 빈도로 다수결하지
않았고, 같은 문맥의 exact donor phone이 하나로 완전히 일치하며 서로 다른
target type이 2개 이상일 때만 후보를 냈다. 복수 발음 donor 103형은 임의 첫
변이를 고르지 않고 모든 변이를 unanimity 검사에 넣었다.

## 2. 전역 projection 결과

| 범주 | 유형 수 | 출현 수 |
|---|---:|---:|
| 기존 결과와 완전히 동일 | 286,556 | 4,000,557 |
| 새 후보 획득 | 13,172 | 345,783 |
| 기존 후보 상실·보류 복귀 | 10,799 | 126,339 |
| 후보 phone 변경 | 78 | 213 |

전역 donor 적용 후 target 후보 상태는 다음과 같다.

| 상태 | 유형 수 | 출현 수 |
|---|---:|---:|
| exact gate 유지 | 96,284 | 1,676,283 |
| model 단위화 동등 유지 | 124,564 | 1,686,625 |
| exact 문맥 projection 후보 | 46,431 | 600,779 |
| donor 비일치 보류 | 42,738 | 506,404 |
| candidate-only 삭제 정책 보류 | 588 | 2,801 |

후보 상실은 계산 실패가 아니다. donor를 넓히자 같은 broad-Roman 문맥에서 서로
다른 acoustic phone이 관측되어 unanimity 조건을 더 이상 만족하지 않은 경우다.
예를 들어 `업꼬`는 좁은 donor에서 `[ʌ p̚ k͈ o]` 후보였지만 전역 donor에서는
phone 변이가 드러나 보류로 돌아갔다. 반대로 `읻꼬`, `읻찌` 계열은 더 넓은 exact
근거에서 종성 `[t̚]` 후보가 회수됐다. 따라서 좁은 donor 후보를 자동 채택하지
않고 전역 검사를 먼저 한 것이 방법론적으로 필요했다.

## 3. 881,237형 readiness 갱신

감사된 전역 source 결과를 canonical 881,237형에 다시 연결한 09 readiness는
다음과 같다.

| 범주 | 07 제한 donor | 09 전역 donor | 변화 |
|---|---:|---:|---:|
| candidate 준비 유형 | 749,779 | 752,270 | +2,491 |
| candidate 준비 출현 | 25,978,186 | 26,197,593 | +219,407 |
| 복수 변이 정책 유형 | 24 | 35 | +11 |
| zero-fallback 보류 유형 | 131,434 | 128,932 | -2,502 |
| zero-fallback 보류 출현 | 1,868,756 | 1,649,312 | -219,444 |

잔여 보류는 두 갈래다.

- 기존 G2P target projection 미해결: 43,428형·509,205회
- no-surface-rule 실질 불일치: 85,504형·1,140,107회

후자는 아직 projection target으로 만든 적이 없는 범위다. 동일 Jamo G2P를 다시
실행해서는 새 근거가 생기지 않는다. 다음 단계는 이 85,504형을 “사전 예외일 수
있는 no-rule 대상”이라는 별도 신분으로 보존하면서 candidate-only target 설계를
먼저 확정하는 것이다. 기존 규칙 민감 target과 섞어 자동 선택하지 않는다.

## 4. 회귀 표면형

- `있지`: 전역 exact donor로 `[iː t̚ tɕ͈ i]` 후보 회수
- `있는`: `[i nː ɨ n]` model 단위화 동등 후보 유지
- `없는`: `[ʌː m n ɨ n]` exact target 유지
- `놨던`: `[n w ɐ d t͈ ʌ n]` exact target 유지
- `어쨌든`: `[ʌ tɕ͈ ɛː t̚ t͈ ɨ n]` exact·사전 일치 경로 유지

이는 실제 음성 실현 판정이 아니라 MFA 입력 후보의 기술·규칙 근거다. 실제
실현 여부는 추후 선별된 WAV·TextGrid·KOINA 결과를 연구자가 판단한다.

## 5. 독립 감사와 시행착오

생성기와 별도의 감사기가 다음을 전수 재계산해 두 단계 모두
`passed_read_only`로 통과했다.

- 382,891 exact donor와 382,994 phone 변이의 문맥 색인
- 310,605 target 편집 정렬·evidence 선택·후보 획득/상실/변경
- 312,410 source의 사전 근거 route
- 881,237 canonical readiness의 후보·정책·zero-fallback 회계
- phone inventory와 표적 회귀

첫 시도는 제한 실행 환경에서 D: 새 폴더 생성 권한이 없어 출력 전 안전
중단됐다. 두 번째 시도는 CSV의 고정 fieldnames와 Python dictionary 삽입 순서를
혼동한 과도한 자체 검사에서 첫 행에 안전 중단됐다. 기존 자료는 변경되지 않았고,
343B·192B partial은 다음 위치에 보존했다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\archive_intermediate\
  08_global_projection_failed_field_order_20260808_1301
```

검사는 field 집합 계약으로 바로잡고 단위 테스트 후 전수 재실행했다. 최종 결과는
partial이 아닌 원자 승격된 08·09 폴더다.

## 6. 실물과 SHA-256

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  08_global_projection_candidates
  09_global_selection_readiness

outputs/reports/AUDIT_common_pron_r3_global_projection_v2_20260808.json
outputs/reports/AUDIT_common_pron_r3_global_selection_readiness_20260808.json
outputs/reports/REPORT_common_pron_r3_global_projection_v2_20260808.json
```

| 실물 | SHA-256 |
|---|---|
| 08 manifest | `2edc1ca871424bbe95659a176615961bcdbeccc86c28301f558733963525f90f` |
| 08 독립 감사 | `5f8be1446c02aa3ced9a9e7dee4210beb0c0a2a9a276c593a105b69bea9d006f` |
| 09 manifest | `187b726c0c9bfc46c2cb232bbe22f586cab71fa8caf76562c4cde4e01f541502` |
| 09 독립 감사 | `cb517a05f92eef57fd5fcd80d433337f262413c01632687d17f68fd00cd7cb5d` |
| 요약 보고서 | `646b19f59c385f6e1418af5333f436ad4bf051b389fc47c39c60596a8e787cc5` |

## 7. 다음 Gate

1. no-rule 85,504형의 별도 target 계약을 설계한다.
2. 사전 예외·기호·숫자·외래어를 broad context projection과 구분한다.
3. candidate-only 생성·독립 감사 후 09 readiness와 비교한다.
4. 그 뒤에만 35형 복수 변이 정책과 zero-fallback 최종 처리로 간다.
5. canonical selection·adoption Gate 통과 전에는 MFA나 TextGrid를 변경하지 않는다.

현재 사용자 청취 검토나 장시간 PowerShell MFA는 필요하지 않다.
