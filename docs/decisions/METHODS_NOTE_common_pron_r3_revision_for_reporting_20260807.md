# 논문 보고용 공통발음 파이프라인 중간 수정 이력

- 기록일: 2026-08-07 KST
- 대상: 2020–2025 대화 코퍼스의 공통발음사전·MFA 입력·TextGrid 생산
- 성격: 논문 연구방법 본문 및 각주 작성용 provenance

## 1. 수정이 필요했던 이유

초기 r2 생산 계약은 Korean MFA acoustic v3.3.0과 Jamo G2P v3.2.0을 동결하고,
기본 MFA 사전에 없는 표면형을 G2P 1-best로 채우는 방식이었다. 그러나 2022
연구자 표본에서 `있지`, `있는`, `없는`, `어쨌든` 등 일부 표면형의 MFA 입력
phone이 별도로 계산해 둔 음운규칙 예상형과 일치하지 않는 사례가 발견됐다.

이는 `phones_mfa`가 실제 실현 발음의 정답이 아니라는 일반적 한계와 구분된다.
문제는 음향모델의 시간 경계 추정 이전에, 규칙 예상형 정보가 r2 MFA 입력사전으로
일관되게 전달되지 않았다는 입력 배선 문제였다. r2 생성기는 기본 MFA 사전의
발음을 무조건 보존하고 OOV에만 Jamo G2P를 적용했으므로, 검색·참조 CSV에 있던
규칙 예상형이 실제 정렬 후보에 반영되지 않는 경우가 있었다.

## 2. 표본 문제를 전수 문제로 확장해 확인한 절차

표본 몇 개만 국소 수정하지 않고 2020–2025 관측 표면형 전체를 감사했다.

- 감사 단위: 관측 표면형 881,237개
- 총 출현: 27,847,068회
- r2 phone과 규칙 예상형의 broad Roman이 같은 유형:
  382,891개·19,765,802회
- 규칙 적용 대상이면서 불일치한 유형:
  312,756개·4,718,489회
- 규칙 변화가 없는데도 broad class가 불일치한 유형:
  185,590개·3,362,777회

불일치 유형은 모두 오류로 자동 판정하지 않았다. 형태소·동음이의어·사전
1:N 변이·선택 규칙·어절 경계 효과가 섞일 수 있으므로 screening 후보로
분류했다. 다만 불일치가 모든 연도에 걸쳐 나타났기 때문에 r2를 이용한 신규
연도 정렬은 방법론적으로 중단했다.

전수 감사 정본:

```text
D:\mfa_common_pron\audits\common_pron_r2_rule_audit_20260807
```

## 3. 중간에 변경한 생산 정책

### 3.1 r2의 안전 중단

- r2 release를 프로젝트 Gate에서 fail-closed로 차단했다.
- 2020–2022 r2 DB·TextGrid·동반표는 삭제하거나 phone 문자만 바꾸지 않고
  읽기 전용 방법론 증거와 회귀 자료로 보존했다.
- 2023–2025를 r2로 계속 정렬하지 않았다.

### 3.2 후보와 최종 선택의 분리

r3에서는 관측 표면형 한 유형을 한 행으로 하는 canonical 표를 만들고 다음을
서로 다른 열로 보존한다.

- 표기형과 철자 Roman
- 규칙 예상형 한글·Roman 및 적용 규칙
- 우리말샘 등 사전 후보, 품사·의미·출처
- 기존 r2 phone과 출처
- 새 donor/G2P backend phone 후보
- 최종 선택 phone과 선택 이유·결정 ID

사전 후보나 G2P 1-best가 존재한다는 이유만으로 최종 phone을 자동 선택하지
않는다. 실제 음성에서의 실현 여부도 이 단계에서 판정하지 않는다.

### 3.3 r3 후보 생성의 단계화

1. 881,237형 canonical inventory를 만들었다.
2. 규칙 목표 Roman과 정확히 같은 기존 표면형 phone만 donor 후보로 연결했다.
   결과는 346형·245,597회이며 아직 최종 선택이 아니다.
3. donor로 해결되지 않은 규칙 민감 source 312,410형·4,472,892회를 규칙 목표
   한글형 310,605개로 중복 제거하고 13개 G2P shard로 만들었다.
4. 동결 Jamo G2P 1-best 출력은 독립적으로 계산한 규칙 목표 Roman과 정확히
   일치할 때만 후속 선택 후보로 승격한다.
5. `spn`, acoustic inventory 밖 phone, 입력 밖 key, 중복 1-best key, 임의
   fallback은 허용하지 않는다.

G2P target inventory SHA-256:

```text
65b51abc7a76ca5a84bf41379422c4d21333d0781ef150dba2be1c5d91408fde
```

## 4. 재정렬 범위에 관한 중간 결정 수정

초기에는 연도 간 동일성을 위해 2020–2025를 모두 처음부터 재정렬하는 방안을
채택했으나, r2 입력 자체의 문제를 확인한 뒤 이 결정은 폐기했다. 최종 r3 정책은
계산량만 줄이는 임의 재사용이 아니라 다음의 증명 기반 선택 재사용이다.

- 2020–2022: 전체 화자/세션 적응 단위의 모든 LAB token에 대해 r2/r3 발음
  변이 집합을 비교한다. 하나라도 다르면 해당 적응 단위 전체를 r3로 재정렬한다.
- 완전히 같은 단위: WAV·LAB·모델·feature/alignment 설정·기존 QC가 동일하고,
  층화 표본을 r3로 재실행한 경계·label 동등성 검사를 통과할 때만 기존 결과를
  `reused_r2_equivalent`로 사용한다.
- 2023–2025: 최종 정렬 전이므로 r3로 한 번만 정렬한다.
- 최종 발화 index에는 `alignment_origin`, r3 contract ID, MFA 사전 SHA,
  equivalence proof SHA를 기록한다.

따라서 논문에서는 여섯 연도가 동일한 발음 선택 계약과 acoustic phone
inventory를 사용했다고 보고할 수 있고, 동시에 불필요한 전년 전체 재계산을
피한 근거도 제시할 수 있다.

## 5. 중단·재개 방식의 수정

장시간 G2P는 25,000개 단위 shard로 실행한다. 실행 창이 닫혀 부분 `.dict`만
남은 경우 이를 완료로 오인하지 않는다. MFA G2P가 exit 0으로 끝난 뒤 생성된
입력·출력·음향모델 SHA 보고서가 함께 있을 때만 완료 shard로 재사용한다.
부분 산출물은 삭제하지 않고 `archive_interrupted`에 보존하고 해당 shard만
재계산한다.

### 5.1 후보 생성 완료와 독립 감사

수정 뒤 본 실행은 2026-08-07 20:51:40 KST에 시작해 2026-08-08 02:42:10
KST에 정상 종료됐다. 13개 shard의 입력 310,605개 전부에 대해 Jamo G2P
1-best 후보가 생성됐고, no-path·`spn`·입력 밖 key·shard 내부 및 전체 shard 간
중복·acoustic inventory 밖 phone은 모두 0이었다. 후보 phase manifest의
SHA-256은
`b8772dcd5fb5923b7653cce1aead6a7ca3528b0058081a3c5d239066876bd8f6`이다.

완료 직후에는 실행기가 쓴 집계만 재사용하지 않고 읽기 전용 독립 감사를 한 번
더 수행했다. 각 입력·출력·보고서·음향모델 SHA, 전체 key 집합 동등성, 전역
중복, phone inventory를 다시 계산했으며 모두 통과했다. 감사 보고서는
`outputs/reports/AUDIT_common_pron_mfa_r3_g2p_candidates_20260808.json`이다.
이 단계에서는 canonical 최종 선택, 사전 adoption, 연도별 MFA, TextGrid 생성·
수정을 수행하지 않았다.

2026-08-07 20:43 KST에는 사용자가 `C:\Users\ari30`에서 상대경로
`.\scripts\show_common_pron_mfa_r3_g2p_status.ps1`를 실행해 상태판 파일을
찾지 못했다. 이는 상태 조회 명령의 작업 디렉터리 문제였으며 G2P는 시작되지
않았고 자료 변경도 없었다. 이후 사용자용 장시간 실행·상태판 명령은 현재
디렉터리에 의존하지 않는 프로젝트 절대경로로 기록하도록 수정했다.

이어 20:44:58 KST 본 실행은 정적 preflight를 통과했으나 Windows PowerShell
5.1이 절전 방지 flag `0x80000001`을 음수 `Int32`로 먼저 해석한 뒤 `UInt32`로
변환하지 못해 첫 shard 전에 중단됐다. lock은 해제됐고 완료·부분 G2P shard는
0개였으며 원자료·TextGrid·candidate inventory 변경도 없었다. flag를
`Convert.ToUInt32`의 16진수 변환으로 수정하고, 이후 `-PreflightOnly`가 절전
방지 활성화와 정상 복원까지 실제 호출하도록 확대했다. 정적 회귀검사에는
PowerShell 5.1에서 실패하는 `[uint32]0x8........` 형식을 금지하는 조건을
추가했다.

### 5.2 G2P 후보–규칙 목표 전수 비교 결과

2026-08-08에는 G2P 계산 성공을 발음 타당성으로 간주하지 않고, 후보 phone을
고정 acoustic-model broad-Roman 단위로 변환해 독립 규칙 목표 Roman과 순서·길이까지
전수 exact 비교했다. 대상형 310,605개 중 96,284개(30.999%)만 exact였고
214,321개(69.001%)는 mismatch였다. source 출현 4,472,892회 기준 exact는
1,676,283회(37.476%), mismatch는 2,796,609회(62.524%)였다.

exact도 최종 선택으로 해석하지 않았다. 사전 근거가 일치한 3,078 source형만
후속 선택 우선 후보로 두고, 사전 충돌 14형과 독립 사전 근거가 없는 exact
94,134형을 별도 보류했다. mismatch 215,184형은 G2P 자동 선택 대상에서 제외했다.
여섯 연도는 같은 후보·규칙·Roman mapping·exact 함수로 비교하고 연도별 출현만
별도로 합산했다. 이 단계에서는 canonical selection, adoption, MFA, TextGrid 변경,
실제 실현 발음 판정을 수행하지 않았다.

전수 결과와 독립 재감사 근거는
`RESULT_common_pron_r3_g2p_agreement_gate_20260808.md`와
`outputs/reports/AUDIT_common_pron_r3_g2p_agreement_gate_20260808.json`에 기록했다.

### 5.3 mismatch의 model 표상 차이와 실질 차이 분리

agreement mismatch 214,321 target을 모두 잘못된 발음으로 판정하지 않았다.
후보 broad Roman과 규칙 Roman 사이의 순서 보존 편집을 계산하고, acoustic-model
phone 하나가 장음 또는 `Y/W` 활음성을 함께 나타내는 경우를 좁은 표상 동등성
후보로 분리했다. 이때도 자동 동등성 승인은 하지 않았다.

source 불일치 출현 2,796,609회 기준 결과는 다음과 같다.

- 장음·활음 표상 동등성 후보: 1,686,625회(60.310%)
- 근거가 불완전한 표상 추가 검토: 106회(0.004%)
- 같은 acoustic-model group 내부 대조 검토: 34,667회(1.240%)
- 실제 규칙 예상형과 다른 후보로 볼 실질 차이: 1,075,211회(38.447%)

여섯 연도의 표상 후보 비율은 59.397–60.618%, 실질 차이 후보 비율은
38.059–39.325%였다. 따라서 특정 연도에 임시 예외를 넣지 않고 같은 target,
model inventory, Roman mapping, 편집·근거 routing을 적용한다.

전체 2,625개 편집 패턴은 빈도·class 대표·회귀 표본을 기준으로 56행으로
축약했으며, 불일치 출현의 92.620%를 포괄한다. 이는 연구자 승인표가 아니라
canonical 선택 정책을 만들기 위한 handoff다. 먼저 model 표상 동등성과
규칙·사전 projection을 코드 계약으로 결정하고, 자동 해소할 수 없는 잔여만
연구자 판단으로 올린다.

감사기의 첫 실행은 agreement 입력과 진단 출력의 행 순서가 같다고 가정해 즉시
안전 중단됐다. ID 기반 exact join으로 수정한 뒤 편집거리·편집경로·분류·연도
집계·회귀 예시를 독립 재계산해 `passed_read_only`로 통과했다. canonical 선택,
adoption, MFA, TextGrid 변경은 수행하지 않았다. 상세 결과는
`RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`에 기록했다.

### 5.4 model 단위화 관계와 exact 문맥 projection

진단 결과의 표상 동등성 후보를 곧바로 승인하지 않고 별도 코드 계약을 만들었다.
comparison key exact, 장음 phone의 인접 동일 단위 흡수, 인접 phone의 명시적·
고유 구개성에 의한 `Y` 흡수, 명시적 원순화에 의한 `W` 흡수만 model 단위화
관계로 인정했다. 이 관계는 실제 음성 실현이나 언어학적 발음 동등성을 주장하지
않는다.

실질 차이의 phone 후보는 규칙 Roman exact이면서 model input rewrite가 없는
target만 donor로 사용했다. `±2단위+경계`, `±1단위+경계`, `해당 단위+경계`
순으로 탐색하되 서로 다른 target type 최소 2개와 phone 완전 일치를 요구했다.
빈도 mode, 첫 변이, 수기 phone, 기본사전 membership fallback은 허용하지 않았다.
전체 projected phone 열이 다시 model 단위화 관계를 만족할 때만 후보로 남겼다.

target 310,605개 중 264,906개(85.287%), 출현 3,744,243회(83.710%)에 후보를
마련했다. 45,699개·728,649회는 donor 부재 또는 candidate-only 삭제 문제로
보류했다. source에서 projection과 독립 사전 근거가 함께 일치한 것은
5,948형·349,689회지만 이 역시 최종 선택 전 후보다. 잔여 1,799패턴은 출현의
95.136%와 각 범주 대표를 포괄하는 56행 handoff로 축약했다.

별도 감사기는 exact donor 96,284 target·1,000,388 unit과 query context,
798개 사용 evidence, target/source 전수 경로, acoustic inventory와 회귀 예시를
다시 계산해 `passed_read_only`로 통과했다. 이 단계에서도 canonical selection,
adoption, MFA, TextGrid 변경은 수행하지 않았다. 상세 결과는
`RESULT_common_pron_r3_model_projection_candidates_20260808.md`에 기록했다.

### 5.5 881,237형 selection-readiness와 중복 G2P 방지

규칙 민감 source만의 projection 결과를 전체 공통사전으로 곧바로 일반화하지
않고 canonical 881,237형에 r2 exact, surface donor, 사전 지지 예외, 감사된
의무 규칙 projection, no-rule model 단위화 관계를 다시 연결했다. 규칙·사전
충돌 24형은 임의 first variant가 아니라 복수 변이 후보로 남겼다.

candidate 준비는 749,779형(85.083%)·25,978,186회(93.289%), zero-fallback
보류는 131,434형·1,868,756회였다. no-rule 보류 85,504형 중 83,922형이 이미
같은 동결 Jamo G2P 1-best 출처임을 확인해 동일 G2P 반복을 차단했다. 다음 후보
단계는 canonical exact-rule 382,891형을 전역 donor로 쓰는 문맥 projection이다.

첫 전수 실행의 열 이름 오류와 종료검사 오류는 각각 원자료 변경 전 안전 중단과
완성 partial 전수 검증·국소 승격으로 처리했다. 881,237행 계산을 처음부터
반복하지 않았고 복구 사실을 manifest에 기록했다. 별도 감사기는 전수 route를
재계산해 `passed_read_only`로 통과했다. 상세 결과는
`RESULT_common_pron_r3_selection_readiness_20260808.md`에 기록했다.

### 5.6 전역 exact donor 재검증과 fail-closed 후보 회수

제한 donor의 우연한 unanimity를 피하기 위해 canonical exact-rule 382,891형의
모든 exact phone 변이를 donor pool로 사용해 기존 310,605 G2P target을 다시
비교했다. 출현 빈도 다수결이나 first variant 선택은 하지 않았다. 그 결과 새
후보 13,172형을 얻었지만, 더 넓은 donor에서 변이가 드러난 기존 후보
10,799형은 보류로 되돌렸다. phone 후보가 바뀐 것은 78형이었다.

전역 결과를 881,237형에 재연결한 09 readiness는 candidate 준비 752,270형·
26,197,593회, zero-fallback 보류 128,932형·1,649,312회다. 생성기와 독립
감사기가 08 projection과 09 readiness를 각각 전수 재계산해 통과했다. 같은
G2P를 재실행하지 않았고 canonical selection, adoption, MFA, TextGrid 변경도
수행하지 않았다. 상세 결과는
`RESULT_common_pron_r3_global_projection_v2_20260808.md`에 기록했다.

### 5.7 no-rule 보류형과 규칙·phone 매핑 coverage 분리

09 readiness의 no-rule 실질 불일치 85,504형·1,140,107회를 문자 구성, 사전
근거, r2 발음 출처, 편집 signature로 전수 특성화했다. 이 집합은 숫자·기호·
라틴 문자·낱자 자모가 아니라 모두 완성형 한글이었다. 따라서 기호 정규화 문제와
발음 규칙 coverage 문제를 같은 fallback으로 처리하지 않았다.

비배타적 진단 표지는 비음 조음 위치·경계 54,073형, 분절 수·탈락 35,703형,
활음·모음 단위화 22,168형, 후두 대립·phone 매핑 13,550형이었다. `한번`,
`친구가`, `공부를` 같은 고빈도형은 조음 위치 동화가 현재 broad-Roman 목표에
충분히 표현되지 않았을 가능성을 보였다. `왜`, `돼`는 활음·모음 단위화,
`어차피` 같은 B/P 대립은 acoustic phone과 연구용 넓은 로마자 사이의 매핑을
먼저 점검해야 한다. 이 진단 family는 규칙 정답이 아니며 서로 겹칠 수 있다.

독립 감사기는 85,504행을 원 입력에서 다시 계산해 `passed_read_only`로
통과했다. 일괄 projection, canonical selection, adoption, MFA, TextGrid 변경은
수행하지 않았다. 다음 단계는 고빈도 signature부터 표준 발음·우리말샘·형태소
경계·acoustic inventory를 대조해 명시된 규칙/매핑만 candidate-only 계약에
추가하는 coverage 감사다. 상세 결과는
`RESULT_common_pron_r3_no_rule_hold_characterization_20260808.md`에 기록했다.

## 6. 논문 각주용 축약문 초안

아래 문안은 방법론 방향을 고정하기 위한 초안이다. 현재 G2P·agreement·mismatch
진단·model projection·전역 donor 재검증·881,237형 readiness와 no-rule 보류형
전수 특성화까지 완료됐지만,
canonical 최종 선택·r3 adoption·재정렬·TextGrid materialization은 미완료다.
따라서 논문에 완료형으로 그대로 사용하지 않는다. 최종 각주에는
manifest에서 확인한 다음
실측값을 채운 뒤에만 완료형으로 확정한다.

- G2P 생성 후보·no-path·규칙 Roman 정확 일치·불일치·보류 유형 수
- canonical r3 최종 선택 유형·변이 수와 최종 사전 SHA
- 2020–2022 `reused_r2_equivalent` 및 `realigned_r3` 적응 단위·발화 수
- 2023–2025 r3 최초 정렬 발화·제외·후속 회수 수
- 연도별 최종 6-tier TextGrid 및 동반표 행 수
- 여섯 연도 공통 r3 contract ID·acoustic inventory SHA·사전 SHA
- 기존 TextGrid phone label 제자리 치환 0건 확인

> 초기 강제정렬 결과의 연구자 표본 점검에서 일부 표면형의 규칙 예상 발음이
> MFA 입력사전에 일관되게 반영되지 않은 사실을 확인하였다. 이에 신규 정렬을
> 중단하고 2020–2025 관측 표면형 881,237개를 전수 감사한 뒤, 표기·규칙
> 예상형·사전 후보·G2P 후보·최종 선택을 분리한 r3 공통발음 계약으로 수정하였다.
> 기존 2020–2022 결과는 적응 단위별 r2/r3 발음 변이 집합과 경계 동등성이
> 입증된 경우에만 재사용하고, 차이가 있는 단위는 재정렬하였다.

더 짧은 각주:

> 표본 검토에서 규칙 예상 발음의 MFA 입력 배선 누락을 발견하여 881,237개
> 표면형을 전수 감사하고 발음 선택 계약을 r3로 수정하였다. 후보 발음과 최종
> 선택을 분리했으며, 기존 정렬은 발음·경계 동등성이 입증된 단위에 한해
> 재사용하였다.

### 최종 각주 확정 Gate

각주를 확정하기 전에 다음을 모두 확인한다.

1. r3 adoption manifest가 `passed`이고 선택 phone 누락·`spn`·inventory 밖 phone이
   모두 0이다.
2. 2020–2025 최종 발화 index의 모든 행이 `reused_r2_equivalent` 또는
   `realigned_r3`로 해소됐다.
3. 모든 연도 TextGrid·동반표 manifest가 같은 r3 contract ID와 사전 SHA를
   기록한다.
4. 실제 manifest의 수치를 위 목록과 각주에 옮기고 두 값이 일치한다.
5. 실제 실현 발음 판정과 강제정렬 입력 발음 후보를 같은 값으로 서술하지 않는다.

## 7. 재현성 근거

| Git commit | 기록 내용 |
|---|---|
| `e8013c3` | r2 불일치 확인과 신규 실행 fail-closed 차단 |
| `3aa2d7e` | 881,237형 r3 inventory와 선택 재사용 계약 |
| `59a135e` | donor/G2P 후보 단계, 재개 가능한 runner, 상태판, 방법론 문서 |
| `f0a826e` | 완료 후보를 원본 무변경으로 전수 재검증하는 read-only 감사 |
| `a89debb` | G2P–규칙 목표 ordered broad-Roman 전수 Gate·연도별 회계·독립 감사 |
| `93e52a9` | mismatch 편집·model 표상·사전/형태소/연도 근거 전수 진단과 56행 handoff·독립 감사 |
| `534eeb4` | 좁은 model 단위화 계약, exact 문맥 donor projection, 잔여 56행 축약과 독립 전수 감사 |
| `b6bc12d` | 881,237형 selection-readiness, zero-fallback 회계, partial 국소 복구와 독립 감사 |
| 현 변경 묶음 | canonical exact donor 전역 projection, 후보 획득·상실 비교, 09 readiness와 독립 감사 |

상세 결정은 다음 문서를 함께 참조한다.

- `DECISION_2022_pronunciation_input_gate_hold_20260807.md`
- `DECISION_common_pron_r3_candidate_resolution_20260807.md`
- `RESULT_common_pron_r3_g2p_agreement_gate_20260808.md`
- `RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`
- `RESULT_common_pron_r3_model_projection_candidates_20260808.md`
- `RESULT_common_pron_r3_selection_readiness_20260808.md`
- `RESULT_common_pron_r3_global_projection_v2_20260808.md`
- `../environment/PROJECT_CURRENT_STATE.md`
- `../RUNBOOK_production_2020_2025.md`
- `../WORK_HISTORY_2026-08.md`
