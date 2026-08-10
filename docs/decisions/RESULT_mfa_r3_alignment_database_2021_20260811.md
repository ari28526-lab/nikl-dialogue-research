# 2021 r3 정렬 DB 완료·post-MFA exact-ID 회계 결과

기록일: 2026-08-11 KST
상태: MFA·보존 DB·완료 checkpoint 통과, 437건 연구자 승인 대기

## 결론

2021 안전 본체는 2020과 동일한 `common_pron_mfa_r3_20260809` 계약으로 새로
정렬됐다. 기존 r2 interval이나 TextGrid는 재사용하지 않았고, 2020 완료본과 원
WAV·LAB·CSV도 변경하지 않았다.

동결 입력 1,207,299건과 MFA DB 발화 1,207,299건은 exact-ID로 일치한다. 그중
word·phone interval이 모두 있는 발화는 1,206,862건이며, 437건은 삭제하지 않고
후속 exact-ID 후보로 분리했다.

## 실행·완료 증거

- release: `common_pron_mfa_r3_20260809`
- alignment contract:
  `e072d4a74ce1ade7d175e4988b6113977711852d491b8b72438744400bea3f95`
- 입력: 4,139세션·1,207,299발화
- MFA 계산 완료: 2026-08-11 00:19 KST
- MFA 내부 계산 시간: 24,808.364초
- 완료 marker:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\markers\ALIGN_DONE_2021.json`
- 보존 DB:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\2021\2021.db`
- DB bytes: 10,753,568,768
- DB SHA-256:
  `faaef1c2f7c8dd013f7e90dc1694d6514e9b5bdf8fdbe0e60b07d179925a7731`

MFA는 exit 0과 `Done`을 기록했다. 프로젝트 direct-DB 정책에 따라 MFA 내장
TextGrid 수출은 생략했고, DB SHA가 완료 marker에 고정된 뒤에만 후속 회계를
수행했다.

## post-MFA exact-ID 회계

회계 결과는 다음과 같다.

- expected MFA input: 1,207,299
- database utterances: 1,207,299
- aligned utterances: 1,206,862
- post-MFA candidates: 437
- `mfa_alignment_missing`: 413
- `mfa_feature_generation_failed`: 24
- 후보가 있는 세션: 300
- candidate identity SHA-256:
  `5a4c3de672f824b2b8a00026b443efb838e76d23fe846650ad07ab4be6a7be35`

따라서 다음 식이 성립한다.

```text
1,207,299 expected input
  = 1,206,862 complete word+phone alignments
  + 437 frozen post-MFA exact-ID candidates
```

후보표는
`outputs/reviews/mfa_r3_post_mfa_reconciliation_common_pron_mfa_r3_20260809_2021/`
에 있다. 후보 437건은 모두 고유 ID이고 자동 승인은 수행하지 않았다. 이 회계는
실제 음운 실현 판정이 아니며, 현재 단계에서 437개 음성을 일일이 듣는 절차도
아니다.

## 다음 Gate

연구자가 후보 identity를 명시 승인하면 437건을
`alignment_and_analysis` 범위의 후속 shard로 보존하고, 성공한 1,206,862건만
보존 DB에서 6-tier TextGrid와 gzip 동반표 4개로 수출한다. 승인 전에는 수출하지
않고, 이 사유로 2021 전체 MFA를 다시 실행하지 않는다.

필요한 승인 문장은 다음과 같다.

> 2021 r3 post-MFA 미정렬 437건(candidate
> 5a4c3de672f824b2b8a00026b443efb838e76d23fe846650ad07ab4be6a7be35)을
> alignment_and_analysis 범위의 후속 exact-ID로 이관하고, 성공한 1,206,862건은
> 보존 DB에서 6-tier로 수출하는 것을 승인한다. 승인자 ari30.
