# 2026-07-28 공통사전·archive·MFA 작업 인계

작성 시점: 2026-07-28 16:45 KST

## 한 문장 현재 상태

외부 리뷰를 반영한 최신 Jamo r2 코드와 입력 준비는 끝났지만, **완성된
공통사전과 이를 사용한 2020–2025 MFA는 아직 없다.**

## 오늘 완료한 작업

1. 외부 리뷰 commit을 가져와 리뷰 원문을 저장소에 보존했다.
2. 공식 `MontrealCorpusTools/korean_mfa` commit
   `0091ffa1f1ef7df380a4f799b3fb5bc80c3f65cd`의 다음 세 실물을 실행
   직전 SHA로 고정했다.
   - acoustic v3.3.0:
     `94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c`
   - Jamo G2P v3.2.0:
     `4df7c5fa90da1f401e7a44af360be56158a581a54202e38baedeca53cfed38ff`
   - base dictionary:
     `49e223fddb518bc441baa4cb9fec1a108e80dae9a2b54e5834dbff30e89c7d34`
3. 공통사전 생략 시 구 inline G2P로 자동 복귀하던 동작을 차단했다.
   legacy 방식은 과거 재현용 명시 옵션에만 남겼다.
4. 구 2020·2021과 mismatch 0을 요구하던 잘못된 채택 기준을 폐기하고,
   모든 차이를 원인별로 기록하는 difference inventory와 연구자 승인
   계약으로 교체했다.
5. DB와 최종 TextGrid phone tier에서 `spn`이 한 건이라도 있으면 연도
   완료를 금지했다.
6. 직접 MFA 실행도 bulk lock을 사용하게 하고 공통 G2P와 양방향 동시
   실행을 막았다. 신규 MFA 작업 위치는 D:로 고정했다.
7. 전체 881,237 관측 어절을 최신 묶음으로 다시 준비했다.
   - 최신 기본사전 OOV: 866,692
   - 표준 Jamo G2P 대상: 866,688
   - 표준 shard: 35개, 각 최대 25,000어절
   - 미지원 grapheme: U+11B3 `ᆳ`을 포함한 정확히 4어절
8. 네 어절만 같은 Jamo 모델 입력에서 `ᆳ→ᆯ+ᆺ`으로 완전분해하고,
   원래 표층 어절 키를 복원했다. 4/4, `spn=0`, phone inventory
   이탈=0을 통과했다.
9. 2020–2025 여섯 연도의 acoustic·공통사전·Jamo G2P·런타임·채택
   계약 SHA가 동일한지 마지막에 증명하는 감사 코드를 추가했다.
10. 수백만 작은 파일의 loose copy를 중단하고 항목별 7z archive로
    바꿨다. 실패 clone 52파일·172,573,000바이트의 CRC, 내부 파일 수와
    바이트, archive SHA를 실제로 검증했다.
11. Python 테스트 145개와 PowerShell 안전성 검사 12개가 통과했다.
12. 리뷰 반영 코드를 commit `7c7e9d7`로 원격 브랜치에 푸시했다.

## 현재 D: r2 실측

- release:
  `D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728`
- runtime Git:
  `7c7e9d73cfad7af036b1922ac2dfa34b2ae7b5a7`
- release contract ID:
  `c6a877ff731e871310870afaffd34dbfed82a78fb43e4032561acfe68517ffcd`
- builder normalized SHA256:
  `6b3fcedc5141c09b667305f9c25d879d21e31e56cf6b0d1d2a661118d03462bc`
- verified 표준 shard: 0/35
- 공통사전 final manifest: 없음
- 2020·2021 difference inventory: 없음
- yearly MFA adoption contract: 없음
- 공통 G2P lock: 없음

커밋 전 후보는 삭제하지 않고 다음에 보존했다.

`D:\mfa_common_pron\archive_obsolete\common_pron_mfa_r2_20260728_pre_code_contract_20260728_1644`

## 연구자가 확인할 4행

검토표:

`D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\03_review\jamo_ls_researcher_review.csv`

현재 네 행의 `decision`은 모두 `pending`이다. 모델 후보를 자동 승인하지
않는다. 적절하면 `approved`, 부적절하거나 판단을 미루려면 `rejected`
또는 `pending`을 유지하고 `notes`에 이유를 적는다.

이 검토는 실제 음성 실현을 자동 판정하는 절차가 아니다. MFA 정렬용
사전 phone 후보 네 개가 ㄽ 환경에서 언어학적으로 받아들일 수 있는지를
확인하는 제한된 검토다.

## 남은 작업: 반드시 이 순서

1. 표준 Jamo G2P 35 shard 계산과 shard별 완전성 검증
2. 위 4행 연구자 검토
3. 4행 모두 승인되고 35 shard가 모두 검증됐을 때만 r2 final 생성
4. 구 2020·2021 결과와 r2의 전수 difference inventory 생성
5. 최종 연구자 승인과 adoption contract 생성
6. 동일 r2 사전·acoustic으로 2020부터 연도별 MFA 재실행
7. 매 연도 TextGrid 수·4-tier 경계·DB integrity·`spn=0` 독립 QC
8. 2020–2025 여섯 alignment contract의 방법론 동일성 감사
9. 검색용 CSV에 사전 발음·형태소/철자 로마자 보조열을 계속 정비
10. 후보 추출 뒤 필요 구간에만 wav2vec phone을 별도 보조 산출물로 추가

## archive 남은 상태

- E: 압축 archive 검증 완료: 실패 CRLF clone 1항목
- E: 압축 archive 미완료:
  - 구 2020 TextGrid
  - 구 2021 TextGrid
  - 2021 MFA DB/temp
  - stale temp
- 기존 E: loose-copy 폴더는 불완전 부분 사본이며 검증 archive가 아니다.
- D: 원본은 삭제·수정하지 않았다.
- 압축 archive와 G2P는 같은 D:를 읽으므로 동시에 실행하지 않는다.

## 실행 판단

밤사이 한 가지만 실행한다면 연구 진도상 r2 표준 G2P를 우선한다.
연구자 4행 승인이 없어도 35 shard 계산·검증은 가능하지만, 러너는
승인 전 final 생성을 자동으로 중단한다. archive는 G2P가 끝난 뒤 별도로
재개한다.

## 16:56 재실행 직전 수정

기존 4행 검토표와 새 후보가 다르다는 안전 중단이 한 번 발생했다.
실제 phone이나 파일이 달라진 것이 아니라 IPA 열에 NFKC를 적용해
`ʰ`·`ʲ` modifier가 ASCII `h`·`j`로 바뀐 내부 비교 버그였다. 표준
35 shard는 시작 전이었고 원본·후보 파일은 보존됐다. IPA phone 열에는
Unicode 정규화를 하지 않도록 수정하고 회귀검사를 추가했다.

## 17:08 이후 r2 실행 및 상태판 보정

- 현재 실행 release:
  `D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728`
- 실행 잠금은 2026-07-28 17:08:32에 PID 6668로 취득되었고 shard 1/35
  계산이 시작되었다.
- 실행 중인 G2P에는 손대지 않았으며, 읽기 전용 상태판이 verified shard
  0개 상태에서 `.Sum`을 읽다 실패하던 문제만 보정했다.
- 17:12 스냅샷은 generated 1,926/866,692(특수 4 포함), invalid report 0,
  D: free 263.15 GiB, lock process alive였다.
- 첫 shard 도중의 순간 처리율과 ETA는 초기화 비용과 작은 관측 구간 때문에
  확정값으로 보지 않는다. 최소 1개, 가능하면 2개 shard 검증 완료 후
  실측 wall time으로 병목과 남은 시간을 다시 판단한다.
