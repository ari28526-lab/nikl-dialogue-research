# 2023 r3 정렬 DB 완료·post-MFA exact-ID 회계 결과

최종 갱신: 2026-08-13 KST
현재 상태: MFA·보존 DB·exact-ID 회계 완료, 연구자 승인과 6-tier 수출 전

## 결론

2023 안전 본체는 2020–2022와 동일한 `common_pron_mfa_r3_20260809`의
동결 발음사전·음향모델·Jamo G2P·phone inventory로 새로 정렬됐다. 기존 r2
interval이나 TextGrid는 재사용하지 않았고 2020–2022 r3 완료본, 원 WAV·LAB·CSV,
형태소 검색표를 변경하거나 다시 실행하지 않았다.

동결 입력 494,580건과 MFA 보존 DB 발화 494,580건은 exact-ID로 일치한다. 이 중
word·phone interval이 모두 있는 발화는 494,228건이며, 기술적으로 완전한 interval이
없는 352건은 삭제하지 않고 승인 전 후속 exact-ID 후보로 고정했다. 현 단계는 실제
음운 실현을 판정하거나 음성을 일일이 청취하는 단계가 아니다.

## 동결 입력과 방법론적 동일성

- source 발화: 677,262
- pronunciation-safe: 582,389
- 발음 follow-up: 94,873
- safe 집합 안의 pre-MFA 기술 제외: 87,809
- 실제 r3 MFA 입력: 494,580발화, 1,656세션
- input contract ID:
  `04d82d422460341ea853fa06767237bbfb823896814381caacc2c7fb5134bfa0`
- alignment contract ID:
  `2b16d0309aa11731b6d1e520850c359aa67783004fbd5dea80758b416a7d61eb`
- release: `common_pron_mfa_r3_20260809`
- acoustic model: Korean MFA v3.3.0
- Jamo G2P: v3.2.0

따라서 2020–2023은 연도별 표본을 임의로 다르게 처리한 것이 아니라 같은 release,
같은 사전, 같은 음향모델, 같은 phone 기준과 6-tier 수출 계약을 적용했다. MFA
`phones_mfa`는 이 동결 발음열을 음향에 강제정렬한 예측 분절이며 실제 실현 여부를
대신하는 연구자 판정값이 아니다.

## 실행과 보존 DB checkpoint

- 연도 runner 시작: 2026-08-12 20:25 KST
- MFA 본 계산 시작: 2026-08-12 21:35 KST
- MFA 자체 계산 시간: 10,692.122초
- `ALIGN_DONE_2023.json` 완료: 2026-08-13 00:34 KST
- 완료 marker 상태: `passed`
- 보존 DB:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\2023\2023.db`
- DB bytes: 4,829,962,240
- DB SHA-256:
  `3c6695ac2033612d514e6ca57711d006d2505c6ddb25124b666865df8c315108`
- alignment marker SHA-256:
  `f40a0ea5f3e384f46d8640a8374bfb4888439eda125c86fdae5c7e7706acea71`

MFA는 `Done! Everything took 10692.122 seconds`를 기록했다. 프로젝트 direct-DB
정책에 따라 MFA 내장 TextGrid 대량 수출은 생략하고, 정렬 DB를 먼저 SHA-256으로
동결했다. corpus·temp·DB checkpoint는 삭제하지 않았다.

## 100% 이후 장시간 후처리의 해석

네 정렬 job은 494,579/494,579건을 처리해 100%에 도달했다. 그러나 그 시점은
완료 marker 시점이 아니었다. 이후 MFA는 다음을 계속 수행했다.

1. 네 `get_phone_ctm` job에서 phone 시간 구간 추출
2. 수백만 word·phone interval의 SQLite DB 적재
3. DB transaction commit과 journal 정리
4. DB fingerprint 고정과 완료 marker 작성

네 CTM 로그는 모두 `Finished extraction`을 기록했고, DB는 약 2.316GB에서 최종
4.830GB로 증가했다. 이 동안 Python CPU와 heartbeat가 계속 갱신돼 정체가 아님을
확인했다. 따라서 정렬 진행률 100%만 보고 PowerShell이나 MFA를 종료하지 않은 것은
성공 산출물 보존을 위한 필수 조치였다.

## post-MFA exact-ID 회계

완료 marker의 DB fingerprint를 다시 검증하고 SQLite `quick_check`, 입력–DB
exact-ID 전수 대사, word·phone interval 존재 여부를 독립 회계했다.

- expected MFA input: 494,580
- database utterances: 494,580
- complete word+phone alignments: 494,228
- post-MFA technical candidates: 352
- `mfa_alignment_missing`: 351
- `mfa_feature_generation_failed`: 1
- 후보가 있는 세션: 66
- candidate identity SHA-256:
  `e6716a3694124c656f040491ebb7b9bb7b5bd66947926fc6bccf0543eb878b3b`
- 미정렬률: 0.071171%

다음 식이 exact-ID로 성립한다.

```text
494,580 expected input
  = 494,228 complete word+phone alignments
  + 351 DB 내 alignment-missing candidates
  + 1 feature-generation-failed candidate
```

후보표는
`outputs/reviews/mfa_r3_post_mfa_reconciliation_common_pron_mfa_r3_20260809_2023/`
에 원자적으로 생성했다. 352행은 모두 고유 ID, `decision=pending`,
`exclusion_scope=alignment_and_analysis`이며 자동 승인은 수행하지 않았다. pending
후보표 SHA-256은
`238576df23557abc2e8b8684e45f2696af8fc0bc7188a80a118a212a2e38a088`,
review summary SHA-256은
`0512a47f37cc30992955004a31834bcfb389c5597a30a458ca4b7c39532a5c88`다.

## 승인 전 안전 정지점

현재 352건은 전체 연도를 다시 정렬하라는 뜻이 아니다. 성공한 494,228건과 보존
DB를 그대로 유지하면서 기술적 미정렬 exact-ID만 후속 shard로 넘기기 위한
승인 후보다. 수출기는 다음 연구자 문장이 후보 연도·건수·scope·digest·승인자를
모두 포함할 때만 별도 승인 계약을 생성한다.

> 2023 r3 post-MFA 미정렬 352건(candidate e6716a369412)을
> alignment_and_analysis 범위의 후속 exact-ID로 이관하고, 성공한 494,228건은
> 보존 DB에서 6-tier로 수출하는 것을 승인한다. 승인자 ari30.

승인 전에는 6-tier materialization을 시작하지 않는다. 승인 뒤에는 먼저 수출
preflight로 `expected = aligned + approved technical candidates`, `spn=0`, acoustic
inventory 밖 phone=0을 확인한 다음, 보존 DB에서 성공 494,228건만 수출한다.

## 감시 중 시행착오와 재발 방지

- 선택된 1,656세션을 원 source 디렉터리 전체 수와 직접 비교하면 분모가 달라
  누락처럼 보일 수 있다. 세션·발화 수는 source 디렉터리가 아니라 동결 alignment
  contract의 expected exact-ID와 비교해야 한다.
- 실행 중 로그 파일 크기는 buffering 때문에 Explorer나 일반 속성 조회에서 0으로
  보일 수 있다. 진행 판단에는 `FileShare.ReadWrite/Delete` 공유 읽기와 r3 전용
  상태판을 사용한다.
- 범용/구버전 MFA 상태판은 release-scoped r3 heartbeat를 읽지 못한다. 2023 감시는
  `show_mfa_r3_year_status.ps1 -Year 2023`만 사용했다.
- 읽기 전용 보조 진단에서 한 차례 명령 표기 오류와 D: 메타데이터 조회 timeout이
  있었으나 runner·MFA·DB에는 쓰기나 중단이 없었다. 진단 실패를 MFA 실패로
  해석하거나 재실행하지 않았다.
- 완료 기준은 progress bar 100%가 아니라 `ALIGN_DONE_2023.json status=passed`,
  child/wrapper 정상 종료, lock·DB journal 해제, DB fingerprint 일치의 결합이다.

## 다음 단계

연구자 명시 승인 뒤 다음 순서를 지킨다.

1. 후보 identity에 결속된 승인 CSV·제외 계약 생성
2. 6-tier·동반표 수출 preflight
3. 보존 DB에서 494,228건 6-tier와 동반표 4종 수출
4. 별도 감사기로 전수 TextGrid·동반표·exact-ID 검사
5. 보존 DB 24세션 독립 재수출의 semantic·byte 동등성 검사
6. 최종 `QC_STATE.json`을 통과시킨 뒤 문서·GitHub를 완료 상태로 갱신
