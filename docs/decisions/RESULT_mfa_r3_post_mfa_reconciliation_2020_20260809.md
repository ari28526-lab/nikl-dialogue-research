# 2020 r3 post-MFA exact-ID 회계 결과

기록일: 2026-08-09 KST
상태: 연구자 범주 승인·export·완료 artifact 감사 통과

## 결론

2020 r3 MFA를 다시 돌릴 필요는 없다. 동결 입력과 보존 DB는 exact-ID 782,715건으로
전수 동일하며, word·phone interval이 모두 있는 782,432건과 그렇지 않은 283건으로
완전히 회계된다. 283건은 모두 `mfa_alignment_missing`이고 77개 세션에 분포한다.
성공 정렬, 원 WAV/LAB, DB는 변경하지 않았다.

## 왜 이 단계를 두는가

MFA가 exit 0이어도 일부 발화에는 최종 interval이 없을 수 있다. 이를 무시하면
TextGrid 수량이 조용히 부족해지고, 반대로 연도 전체를 재정렬하면 이미 성공한
782,432건과 수 시간의 계산을 불필요하게 반복한다. 따라서 실패 exact-ID만 후속
shard로 분리하고 성공 DB를 직접 수출한다.

r3에서는 전체 검색 master를 MFA 분모로 쓰지 않는다. 검색 master에는 발음
follow-up과 pre-MFA 제외도 남아 있기 때문이다. 생산식은 다음과 같다.

```text
expected_mfa_input_ids
  = database_utterance_ids
  = active_lab_ids
  = aligned_database_ids ⊎ approved_post_mfa_alignment_exclusions
```

전체 검색 master에는 `expected_mfa_input_ids`가 모두 포함되어야 하지만, 그 밖의
후속 항목이 존재하는 것은 정상이다.

## 고정 결과

- release: `common_pron_mfa_r3_20260809`
- alignment contract:
  `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`
- input contract:
  `d75fa5bc50cc31c3912220d1cb292eb74ab8e9da4216988926dbaa89c34919ce`
- expected / DB: 782,715 / 782,715
- aligned / post-MFA candidate: 782,432 / 283
- reason: `mfa_alignment_missing` 283
- candidate identity:
  `065c2cd1d1dd74831ec483786a485a379556c9694536ca5f06cea172a9969906`
- source DB SHA-256:
  `e2fec7300f9a70a6553f0f9d81d9c7a3c5cdfbc514b77cc7b6de87f933d7f991`

## 다음 Gate

연구자 `ari30`은 2026-08-10 09:07 KST에 동결 283건을
`alignment_and_analysis` 범위의 기술적 후속 exact-ID로 이관하고 성공한
782,432건을 보존 DB에서 수출하는 것을 명시 승인했다. 자동 승인은 없었다.

09:08 KST에 시작한 `run_mfa_r3_research_export.ps1 -PreflightOnly`는 159.109초
뒤 `preflight_passed`를 기록했다. ALIGN_DONE·DB SHA·입력·LAB·search·승인 ID가
일치했고 모든 hard inventory는 0, `spn` 0, acoustic inventory 밖 phone 0이다.
`materialization_started=false`이며 이 preflight 자체는 TextGrid를 만들지 않았다.
그 뒤 같은 wrapper의 full mode를 실행해 아래와 같이 수출을 완료했다.

승인 기록:
`outputs/reviews/mfa_r3_post_mfa_reconciliation_common_pron_mfa_r3_20260809_2020/06_RESEARCHER_APPROVAL.json`

preflight 보고서:
`outputs/reports/PREFLIGHT_mfa_r3_research_6tier_2020_20260810_090806.json`

## 수출 완료

full export는 2026-08-10 09:19 KST에 시작해 10:43 KST에 성공했다. 보존 DB에서
2,231세션·6-tier TextGrid 782,432개를 생성하고 승인 제외 283건은 별도 gzip
표에 남겼다. 원 DB·WAV·LAB·검색표는 변경하지 않았다.

- export report: `success / ready_with_approved_exclusions`
- coverage: 100%
- TextGrid: 782,432
- 동반표: 발화 782,432, word 4,315,723, phone 16,458,699, 제외 283
- 실패·정렬 누락·검색 누락·fallback·`spn`·미승인 누락: 모두 0
- 잔여 `.partial`: 0
- gzip 4개 SHA: manifest와 4/4 일치
- 종료 상태: lock 없음, wrapper/Python 종료

완료 증거는
`outputs/reports/VERIFY_mfa_r3_research_6tier_export_2020_20260810.json`에 고정했다.
이는 artifact 수출 완료 감사이며, 독립 연도 semantic QC는 다음 Gate로 별도
실행한다. 그 QC 전에는 2021로 넘어가지 않는다.

2026-08-10 11:47 KST에 재개형 독립 QC wrapper의 실제 `-PreflightOnly`가
`preflight_passed`를 기록했다. 현재 r3 export report·table manifest·ALIGN_DONE·
alignment/승인 계약의 SHA와 DB path/size가 결속됐고, TextGrid 782,432개와 승인
제외 283개를 확인했다. 이 preflight는 source를 수정하지 않았고 MFA·전수 export·
감사·표본 물질화를 시작하지 않았다. 본 실행은 전수 감사와 24세션 DB 재수출만
수행하며, 후반 표본 단계가 중단돼도 통과한 전수 감사 SHA checkpoint를 재사용한다.

Preflight 보고서:
`outputs/reports/PREFLIGHT_mfa_r3_research_qc_2020_20260810_114748.json`

## 독립 연도 내용·계약 QC 완료

2026-08-10 12:28 KST에 782,432개 전수 audit가 1,510.689초로 성공했다. coverage
100%, hard failure 25범주 모두 0이며, active LAB 782,715는 TextGrid 782,432와
승인 alignment 제외 283으로 완전히 회계됐다. gzip 4표의 ID·key·행 수·SHA와 r3
provenance도 모두 통과했다.

직후 24세션 DB 재수출 검사에서 verifier가 r3 input contract의 nested identity를
읽지 못하는 코드 호환 오류가 발생했다. 이는 표본 검사 진입 전 오류이며 원 DB·WAV·
LAB·TextGrid·동반표를 수정하지 않았다. 구 `lab_input_contract_id`와 r3
`identity.year_input_contract_id`를 모두 명시 지원하고 상충·누락은 거부하도록
수정·회귀 고정했다. 재개 preflight는 `audit=True, sample=False`였고, 통과한 전수
audit SHA를 재사용해 표본만 55.524초 실행했다. 최종 semantic·byte 결과는 24/24,
`QC_STATE.json`은 `passed`다. MFA와 전수 export는 반복하지 않았다.

최종 QC 상태:
`outputs/reports/mfa_r3_research_qc_common_pron_mfa_r3_20260809/2020/QC_STATE.json`

오류·수정·재개 증거:
`outputs/reports/INCIDENT_mfa_r3_research_qc_2020_input_identity_20260810.json`

다음 Gate는 2020을 동결하고 2021 한 연도만 동일 r3 계약으로 준비하는 것이다.
