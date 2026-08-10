# 2020 r3 post-MFA exact-ID 회계 결과

기록일: 2026-08-09 KST
상태: 연구자 범주 승인·실제 export preflight 통과, TextGrid 미생성

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
`materialization_started=false`이며 TextGrid는 만들지 않았다. 다음 단계에서 같은
wrapper로 782,432건의 6-tier와 gzip 동반표를 만든다. 독립 연도 감사가 끝나기
전에는 2021로 넘어가지 않는다.

승인 기록:
`outputs/reviews/mfa_r3_post_mfa_reconciliation_common_pron_mfa_r3_20260809_2020/06_RESEARCHER_APPROVAL.json`

preflight 보고서:
`outputs/reports/PREFLIGHT_mfa_r3_research_6tier_2020_20260810_090806.json`
