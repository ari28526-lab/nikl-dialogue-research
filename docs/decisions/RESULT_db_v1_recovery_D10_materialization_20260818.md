# 연구 DB v1 recovery D10 격리 수동 작업본 생성 결과

기록일: 2026-08-18 KST

## 결과

D9 연구자 검토에서 음성 보존 가치가 있지만 자동 정렬을 그대로 채택할 수 없다고
판정한 exact-ID 16건만 아래 D: 격리 경로에 materialize했다.

```text
D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_MANUAL_OVERLAY_0001
```

구성은 국소 수정 9건, 전체 수동 재정렬 6건, 단일어 수동 복구 1건이다. 각 건에
번호가 같은 WAV, 원 D9 LAB, 연구자 청취 기반 제안 LAB, D9 참고 TextGrid,
수동 작업 TextGrid를 두었다. 데이터 작업 파일은 16세트×5종=80개이고 안내·상태·
감사 파일을 포함한 전체는 85개, 1,730,225 bytes다.

## 수동 TextGrid 계약

수동 작업 TextGrid는 다음 네 tier만 가진다.

1. `words_d9_reference`: D9 word 경계의 읽기 전용 참고본
2. `phones_d9_reference`: D9 phone 경계의 읽기 전용 참고본
3. `transcript_proposed`: 이번 청취 검토에서 확정한 제안 전사
4. `words_manual_working`: 실제 연구자가 경계를 수정할 작업 tier

국소 수정 9건은 대체로 맞았던 D9 word 경계를 작업 초안으로 복사했다. 전체
재정렬 6건과 단일어 복구 1건은 실패한 D9 경계를 정답처럼 재사용하지 않도록
`words_manual_working`을 빈 전구간 interval로 시작했다. D9 phone은 참고 증거일
뿐 수동 작업 tier로 자동 복제하지 않았다.

## 감사

생성 전에는 D10 Gate manifest, D9 연구자 결정 SHA, 16개 exact-ID와 세 분류의
수량, 원 WAV·LAB·TextGrid의 파일 SHA, WAV–TextGrid 길이와 `words`·`phones`
tier를 확인했다. 생성 후에는 다음을 다시 전수 검사했다.

- 다섯 파일 유형 각각 16개
- 복사된 WAV·원 LAB·D9 TextGrid의 source SHA 동등성
- 제안 LAB과 `transcript_proposed`의 문장 동등성
- 모든 수동 TextGrid의 0–WAV 끝 범위와 네 tier 순서
- D9 reference word·phone interval의 불변성
- 국소 수정은 D9 word 초안과 동등, 전면/단일어 작업 tier는 유표 label 0개

최종 감사 상태는 `passed_materialization_pending_researcher_manual_overlay`이고
`MATERIALIZED_DONE.json`이 가리키는 최종 감사 SHA도 재확인했다.

## 방법론적 의미와 안전 정지점

이 단계는 “넓은 beam에서 TextGrid가 생성되었다”와 “연구에 사용할 수 있는
전사·경계다”를 분리한다. 실제 음성과 LAB가 달랐던 사례를 전체연도 재정렬이나
자동 채택으로 해결하지 않고, exact-ID 수정 전사와 수동 overlay로 보존한다.

원 WAV·LAB·D9 TextGrid, r3 본체, 최종 6-tier, DB v1은 바꾸지 않았고 MFA도
실행하지 않았다. 따라서 이 16건은 아직 연구 DB v1의 alignment/analysis 범위에
복귀하지 않았다. 연구자가 `words_manual_working`을 수정한 뒤 경계 연속성·길이·
단어열·provenance를 검사하고 별도 adoption Gate를 통과해야만 파생 6-tier와 DB
overlay에 반영할 수 있다.

정본 기계 결과는
`outputs/reports/RESULT_db_v1_recovery_D10_materialization_20260818.json`, D:의
상세 감사는 `state/MATERIALIZATION_AUDIT.json`이다.
