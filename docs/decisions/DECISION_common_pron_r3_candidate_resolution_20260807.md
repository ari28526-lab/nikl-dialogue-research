# 공통발음 r3 후보 생성·선택·정렬 반영 결정

- 결정일: 2026-08-07 KST
- 상태: G2P 후보 생성·규칙 Roman 전수 Gate 완료, 아직 canonical 선택·adoption 전
- 적용 범위: 2020–2025 전체 관측 표면형 881,237개

> **2026-08-09 후속 결정:** 이 문서의 후보 생성·선택·phone 보존 규칙은 계속
> 유효하지만, 아래의 r2 interval 선택 재사용 방안은 폐기됐다. 최종 생산은
> `DECISION_common_pron_r3_full_realign_2020_2025_20260809.md`에 따라
> 2020–2025 safe-body 전체를 새 r3 DB에 정렬하며 r2 interval은 최종 r3에
> 재사용하지 않는다.

## 목적

r2 공통사전은 일부 표면형에서 이미 계산된 음운규칙 예상형을 MFA 입력에
연결하지 못했다. r3의 목적은 특정 예시만 고치는 것이 아니라, 여섯 연도에
동일한 발음 선택 기준을 적용하고 그 선택이 최종 MFA 사전과 TextGrid까지
추적되도록 만드는 것이다.

`phones_mfa`는 실제 실현 발음의 정답이 아니다. 선택된 사전 발음 후보를
음향모델이 시간축에 강제 정렬한 결과이다. 실제 실현 여부는 이후 연구 단계에서
WAV, TextGrid, KOINA 결과 등을 보고 연구자가 판정한다.

## 정본 표와 후보의 구분

1. 정본의 단위는 2020–2025에서 관측된 표면형 한 유형이다.
2. 표기형 Roman, 규칙 예상형 한글·Roman, 사전 후보·품사·출처, r2 phone,
   후보 phone, 최종 선택 phone과 근거를 분리해 기록한다.
3. 사전 후보와 G2P 출력은 모두 보조 근거다. 생성되었다는 이유만으로 정본에
   자동 채택하지 않는다.
4. 최종 선택되지 않은 후보도 provenance와 함께 보존해 CSV 검색·후속 연구에
   재사용한다.

## 2026-08-07 단계별 실물

### 1. canonical inventory

- 경로: `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\01_canonical_inventory`
- 전수 범위: 881,237형, 27,847,068회 출현
- r2와 규칙형이 정확히 같은 provisional 유지 대상: 382,891형,
  19,765,802회
- 나머지 498,346형은 근거별 후보 또는 보류 상태로 남겼다.

### 2. 표면형 donor 후보

- 경로: `...\02_surface_donor_candidates`
- 규칙 예상 Roman과 정확히 같은 기존 표면형 phone만 donor 후보로 허용했다.
- 결과: 346형, 245,597회 출현
- 이 단계 역시 후보 생성이며 최종 선택이 아니다.

### 3. 규칙 목표형 Jamo G2P 후보

- 경로: `...\03_g2p_rule_targets_1best`
- source 유형: 312,410형, 4,472,892회 출현
- 중복 제거한 규칙 목표 한글형: 310,605개
- 25,000개 단위 13 shard
- 동결 모델: Korean MFA acoustic v3.3.0 및 Jamo G2P v3.2.0
- 1-best 출력은 후보일 뿐이다. 독립적으로 계산한 규칙 목표 Roman과 정확히
  일치할 때만 후속 선택 후보로 승격한다.
- 2026-08-08 02:42 KST에 13/13 shard가 정상 종료됐다. 입력 310,605개와
  후보 310,605개가 1:1로 대응했고 no-path·`spn`·입력 밖 key·전체 shard 간
  중복·acoustic inventory 밖 phone은 모두 0이었다.
- 완료 manifest SHA-256은
  `b8772dcd5fb5923b7653cce1aead6a7ca3528b0058081a3c5d239066876bd8f6`이다.
  이 수치는 후보 계산 완료 근거이며 최종 선택 완료를 뜻하지 않는다.

## 장시간 실행 안전 계약

- 각 shard는 MFA G2P가 exit 0으로 끝난 뒤에만 검증 보고서를 만든다.
- 재개 시 `.dict`만 존재하는 부분 출력은 완료로 인정하지 않는다.
- 입력·출력·음향모델 SHA가 일치하는 완료 보고서가 있을 때만 shard를 재사용한다.
- 중단 산출물은 삭제하지 않고 `archive_interrupted`로 이동한다.
- `spn`, acoustic inventory 밖 phone, 입력 밖 key, 중복 1-best key는 즉시
  실패시킨다.
- 소수의 FST no-path는 누락 목록으로 기록할 수 있지만, 한 shard의 1%를
  넘으면 실행 이상으로 보고 중단한다.
- 이 단계는 최종 사전 생성, adoption, 연도별 MFA, TextGrid 변경을 하지 않는다.

## 최종 선택과 6개년 정렬

1. 전체 유형에서 선택 phone 누락 0, `spn` 0, acoustic inventory 밖 phone 0을
   만족한다.
2. canonical 선택표와 출력 MFA 사전의 byte/fingerprint 동등성을 검증한다.
3. 이미 검토한 2022 문제 표본과 음운현상별 표적 회귀를 통과한 뒤 r3를
   adoption한다. 같은 계약이면 광범위 파일럿을 반복하지 않는다.
4. 2023–2025는 r3로 한 번 정렬한다.
5. 2020–2022는 전체 적응 단위별 r2/r3 발음 변이 집합을 비교한다. 완전히 같은
   단위만 WAV·LAB·모델·설정·기존 QC와 층화 경계 동등성 증거를 갖추어
   `reused_r2_equivalent`로 보존하고, 하나라도 다른 단위는 `realigned_r3`로
   재정렬한다.
6. 기존 r2 TextGrid의 phone 문자를 제자리에서 바꾸는 방식은 금지한다.
7. 최종 발화 index는 모든 TextGrid에 r3 contract ID, 사전 SHA,
   `alignment_origin`, equivalence proof를 기록한다.

이 계약은 이미 끝난 정렬을 무조건 처음부터 반복하지 않으면서도, 논문에서
2020–2025가 동일한 발음 선택 기준과 동일한 acoustic phone inventory를
사용했다고 입증하기 위한 기준이다.

## 2026-08-08 전수 agreement Gate 후속 결정

310,605개 후보와 독립 규칙 목표를 ordered broad-Roman으로 전수 비교한 결과,
exact는 96,284개(30.999%), mismatch는 214,321개(69.001%)였다. 따라서
`G2P exit 0`, no-path 0, `spn` 0은 후보 생성 완결성 근거일 뿐 발음 선택 근거로
사용하지 않는다.

- 사전 근거 일치 exact source 3,078형은 후속 canonical 선택 우선 후보로만 둔다.
- 사전 충돌 exact 14형과 독립 사전 근거 없는 exact 94,134형은 서로 다른 보류
  상태를 유지한다.
- mismatch source 215,184형은 G2P 후보를 자동 선택하지 않는다.
- exact 여부와 최종 선택 여부를 별도 열·manifest로 유지한다.
- 별도 adoption Gate 전에는 연도별 MFA와 TextGrid materialization을 시작하지 않는다.

수치와 SHA 근거는 `RESULT_common_pron_r3_g2p_agreement_gate_20260808.md`를 따른다.

## 2026-08-08 mismatch 진단 후속 결정

mismatch 214,321 target을 단순 오류로 묶지 않고 acoustic-model phone 표상과
실질 규칙 차이로 전수 분해했다. source 불일치 출현 중 60.310%는 장음·활음
표상 동등성 후보, 38.447%는 실질 차이 후보였다.

- 표상 동등성 후보도 자동 승인하지 않는다.
- 실질 차이 후보는 G2P 1-best 자동 선택을 거부하고 규칙·사전 projection을 찾는다.
- 같은 model group 내부 대조는 연구 기준상 보존 여부를 별도로 판단한다.
- 2,625개 패턴을 그대로 사람에게 넘기지 않고 56행 handoff로 축약한다.
- canonical 선택 전에 model 표상 계약과 projection 정책을 코드·회귀검사로 먼저
  고정하고, 자동 해소가 불가능한 잔여만 연구자에게 올린다.
- 이 결정으로 adoption, MFA, TextGrid 변경을 허용하지 않는다.

수치·분류·감사 근거는
`RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`를 따른다.
