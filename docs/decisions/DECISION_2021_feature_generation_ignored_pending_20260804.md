# 2021 MFA feature-generation 실패 24건의 후속 처리 결정

작성일: 2026-08-04 KST

상태: MFA·exact-ID 재확인 완료, 연구자 승인 전

대상 run: `eojeol_commonpron_2021_20260804_114223`

## 관찰

MFA는 1,416,216개 WAV를 읽은 뒤 feature 생성 문제로 43,822개 발화를
무시했다고 경고했다. 입력 계약과 MFA DB를 읽기 전용으로 대조한 결과는
다음과 같이 정확히 합계가 맞는다.

```text
검색표 밖 WAV-only                    42,296
연구자 승인에 따라 LAB를 분리한 발화   1,502
LAB·비어 있지 않은 전사가 있으나
feature 생성에 실패한 초단시간 발화        24
-------------------------------------------
MFA 경고 합계                         43,822
```

24개 WAV의 길이는 0.01–0.099875초이며, MFA DB에서 `ignored=1`,
`num_frames=NULL`, `features=NULL`이었다. 전체 목록과 실행 근거는
`outputs/reports/OBSERVATION_2021_mfa_feature_generation_20260804.json`에
기록했다.

## 결정과 이유

1. 현재 MFA를 중단하거나 처음부터 다시 실행하지 않는다. 이 24건은 이미
   feature를 만들 수 없는 입력으로 판정되었고, 재시작만으로 개선될 근거가
   없다.
2. 24건을 자동 승인하거나 조용히 누락시키지 않는다. 현재 상태는
   `pending_post_mfa_exact_reconciliation`이다.
3. MFA 완료 DB를 체크포인트로 보존한다. 6-tier export 전에 exact-ID
   reconciliation을 실행하여 같은 24건이 정렬 결과에 없음을 다시 증명한다.
4. 재확인된 항목은 `mfa_feature_generation_failed`라는 별도 사유의 연구자
   승인 후보표로 제시한다. 승인 뒤에만 2021 생산 제외 계약에 결합한다.
5. 승인으로 계약이 갱신되더라도 완료된 MFA DB는 재사용하고 export부터
   재개한다. 따라서 2021 MFA 전체를 다시 계산하지 않는다.

## 연구 방법론상 의미

이 처리는 데이터 손실을 숨기지 않으면서도 계산 완료분을 보존한다. 모든
연도에서 동일한 입력 계약, 공통 Jamo r2 사전, acoustic model, phone inventory,
사유 코드와 승인 절차를 적용하며, feature 생성이 물리적으로 불가능한 극단적
단시간 음원은 본체 결과와 구분된 후속 자료로 남긴다.

## 다음 게이트

- MFA 프로세스 exit 0 확인(완료)
- 완료 DB와 `direct_db_ready` 보존(완료)
- export exact-ID reconciliation에서 24건의 집합 동등성 확인(완료)
- 연구자 승인 후보표 생성(완료) 및 승인 대기
- 승인 계약 결합 후 6-tier·동반표 export 재개

## 종료 후 재확인 결과

- MFA는 2026-08-04 20:53:45 KST에 exit 0으로 종료됐다.
- DB checkpoint는 source 1,372,394, word·phone interval이 모두 있는
  발화 1,371,883, `spn` 0을 기록했다.
- exact-ID 대조에서 feature 생성 실패 24건이 모두
  `mfa_feature_generation_failed`로 재확인됐다. 별도로 DB에는 들어왔으나
  word/phone interval을 만들지 못한 511건을 `mfa_alignment_missing`으로
  분리했다.
- 두 사유의 535건은 하나의 post-MFA 검토 패키지에 들어 있으며,
  자동 승인은 0건이다. 20건 후보와 4건 정상 대조군의 WAV/LAB
  표본을 검토한 뒤 연구자가 명시 승인해야 한다.
