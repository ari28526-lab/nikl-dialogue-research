# 2021 r3 정렬 DB 완료·post-MFA exact-ID 회계 결과

기록일: 2026-08-11 KST
상태: MFA·보존 DB·437건 승인·6-tier·동반표·독립 전수 QC 완료

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

## 연구자 승인과 수출 preflight

연구자 `ari30`은 2026-08-11 08:16 KST에 후보 identity를 명시 승인했다. 승인
계약은 437행, `automatic_approval_performed=false`, 원 DB 변경 `false`다. 437건은
`alignment_and_analysis` 범위의 후속 shard로 보존하고, 성공한 1,206,862건만
보존 DB에서 6-tier TextGrid와 gzip 동반표 4개로 수출한다. 이 사유로 2021 전체
MFA를 다시 실행하지 않는다.

필요한 승인 문장은 다음과 같다.

> 2021 r3 post-MFA 미정렬 437건(candidate
> 5a4c3de672f824b2b8a00026b443efb838e76d23fe846650ad07ab4be6a7be35)을
> alignment_and_analysis 범위의 후속 exact-ID로 이관하고, 성공한 1,206,862건은
> 보존 DB에서 6-tier로 수출하는 것을 승인한다. 승인자 ari30.

첫 export preflight는 materialization 전에 안전 중단됐다. 기존 r3 검증식이
`expected input = ignored=0 DB`를 요구해, MFA가 feature 생성 실패로 `ignored=1`
처리한 승인 24건을 DB 결손으로 오판했기 때문이다. DB·승인·MFA 결과를 고치지
않고 검증식을 다음 두 식으로 분리했다.

```text
1,207,299 expected input
  = 1,207,275 exportable DB + 24 approved feature failures

1,207,275 exportable DB
  = 1,206,862 aligned + 413 approved DB-unaligned
```

새 회귀검사를 포함한 관련 30테스트가 통과했다. 실제 재 preflight도 미승인 차이,
검색·LAB·입력 차이, quarantine, `spn`, acoustic inventory 밖 phone을 모두 0으로
확인해 `preflight_passed`를 기록했다. 실패 preflight와 통과 preflight는 각각
`outputs/reports/PREFLIGHT_mfa_r3_research_6tier_2021_20260811_081715.json`,
`outputs/reports/PREFLIGHT_mfa_r3_research_6tier_2021_20260811_082459.json`에
보존한다.

## 6-tier·동반표 수출 완료

보존 DB 기반 수출은 2026-08-11 08:30–11:00 KST에 완료됐다. MFA와 DB는
재계산하지 않았고, release 전용 출력 경로에만 새 연구용 산출물을 만들었다.

- 성공 상태: `success`
- 6-tier TextGrid: 1,206,862개
- 승인 기술 제외: 437개
  - exportable DB 안의 미정렬: 413개
  - feature 생성 단계에서 DB 밖으로 분리된 항목: 24개
- utterance 동반표: 1,206,862행
- word 동반표: 8,926,793행
- phone 동반표: 32,776,584행
- `spn`: 0
- 출력 schema: `research_textgrid.v2`
- 수출 시간: 9,001.299초

동반표의 `excluded_utterances=437`은 위 두 기술 실패 집합의 합집합이다. 반면
export 보고서의 `counts.approved_excluded=413`은 실제 exportable DB 안에 있으나
정렬 interval이 없는 발화만 센다. 두 수는 서로 다른 분모이며 exact-ID 식으로
합쳐 1,207,299건 전체를 닫는다.

완료 보고서는
`outputs/reports/EXPORT_mfa_r3_research_6tier_2021_20260811_083053.json`, 출력은
`D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\research_6tier\2021`에 있다.

## 독립 전수 QC와 DB 재수출 동등성

첫 QC preflight는 TextGrid나 DB를 바꾸기 전에 안전 중단됐다. 수출기에는 이미
24건과 413건을 분리한 새 exact-ID 식이 반영됐지만 QC wrapper가 구식
`export.accounted = expected_mfa_input` 식을 남겨 둔 것이 원인이었다. QC도 다음을
각각 검증하도록 고쳤다.

```text
expected input = exportable DB + approved pre-DB feature failures
exportable DB = aligned DB + approved DB-unaligned
approved total = approved feature failures + approved DB-unaligned
```

PowerShell 5.1 안전 68파일과 runtime 68스크립트 검사를 다시 통과한 뒤 실제
`-PreflightOnly`가 TextGrid 1,206,862·승인 제외 437로 통과했다. 이 수정은
커밋 `90ac3e7`로 먼저 푸시했다.

독립 QC는 2026-08-11 11:05–11:58 KST에 완료됐다.

- 전수 TextGrid: 1,206,862/1,206,862
- coverage: 100.0%
- hard failure 합계: 0
- 전수 감사 시간: 3,083.476초
- 동반표 전 행·manifest identity/SHA: 일치
- 보존 DB 재수출 표본: 24세션
- semantic 동등: 24/24
- byte 동등: 24/24
- `source_mutation_performed=false`
- `mfa_recomputed=false`
- `full_export_repeated=false`

최종 checkpoint는
`outputs/reports/mfa_r3_research_qc_common_pron_mfa_r3_20260809/2021/QC_STATE.json`의
`status=passed`, `qc_input_checkpoint_id=b22e7e2b8a5cb93d801d72f0a6d50529b754e42427b46c4ac2789598df837648`다.
완료 뒤 같은 `-PreflightOnly`를 다시 호출했을 때 `resume: audit=True,
sample=True`가 확인돼 전수 감사와 표본 검사를 모두 반복하지 않는 checkpoint임을
입증했다.
따라서 2021 MFA·전수 수출·QC를 다시 실행하지 않고 이 state를 SHA로 동결한 뒤
2022 한 연도만 준비한다.
