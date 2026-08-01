# 2020 CSV–WAV 발화 ID 대응 복구 결정

결정일: 2026-08-01 KST
상태: `MFA BLOCKED — MINIMAL LISTENING REVIEW READY`

## 연구 목적과 위험

MFA는 형태소·표기 환경 검색 결과를 실제 WAV와 TextGrid에 연결하는 인프라다.
같은 `utt_id`의 CSV 전사와 WAV가 다른 발화라면 MFA가 정상 종료하고 tier 구조가
맞더라도 연구 자료의 내용은 잘못된다. 이 문제는 phone 정확도 문제가 아니라
입력 자료의 동일성 문제이므로 정렬 전에 차단한다.

## 발견 경위

2020 승인 후보표 준비 중 입력 전수 감사가 다음을 확인했다.

- search 행: 870,437
- 길이 잔차 불일치: 15,074발화, 126세션
- WAV 누락: 544발화
- 세션 폴더 누락: 1세션
- 기존 세션 통과율 기준에서 실패한 세션: 59개

`SDRW2000000108.1.1.11`은 JSON/CSV 길이가 0.941초지만 같은 ID의 배포
PCM과 변환 WAV는 3.015초다. 이어지는 PCM 길이는 JSON의 뒤 발화 길이와 한 칸
밀린 상태로 장구간 일치한다. D: JSON과 H: 음원 배포본 안의 JSON SHA-256은
같았으므로 CSV 생성 오류가 아니라 배포 PCM/WAV ID 대응 오류로 판정했다.

## 잘못된 승인 후보표의 폐기 판정

최초 14행 후보는 구형 `06_textgrid_merged`의 형태소 TextGrid 누락에서
생성되었다. 확정 6-tier의 `morph_analysis_utt`는 `morph_search.v3`/search
CSV에서 만들므로 이 14행은 현행 정렬 제외 사유가 아니다. 자동 승인하지 않고
다음 위치에 원문 그대로 archive했다.

```text
outputs/reviews/archive/
  mfa_exclusions_queue_mfa_r2_prod_2020_20260801_legacy_morph_gate/
```

## 복구 원칙

1. 원 JSON·PCM·기존 D: WAV는 직접 수정하지 않는다.
2. 세션 내부 발화 순서를 보존한 채 `WAV 길이 - 0.010초`와 CSV 길이의
   밀리초 token을 비교한다.
3. 3개 이상 연속으로 정확히 일치하는 구간만 고신뢰 재매핑 후보로 삼는다.
4. 1–2개 일치, 원음 미확인, 고아 source는 자동 적용하지 않는다.
5. 고신뢰 후보도 음성 표본 확인과 원본 archive/manifest 뒤 별도 적용한다.
6. 적용 후 전수 감사를 다시 실행하고, 남은 발화만 연구자 승인 제외 계약에
   넣는다.

읽기 전용 계획 결과:

- `identity_high_confidence`: 35,210
- `remap_high_confidence`: 14,221
- `ambiguous_short_match`: 92
- `target_unresolved`: 1,742
- `source_orphan`: 1,254
- 영향 세션: 129, 계획 행: 52,519
- 고신뢰 remap의 연속 일치 길이: 최소 3, 평균 76.13, 최대 448

근거:

```text
outputs/reports/PLAN_2020_wav_duration_recovery_20260801.csv
outputs/reports/PLAN_2020_wav_duration_recovery_20260801.json
```

## 2026-08-02 최소 청취 검토

고신뢰라는 표현이 길이열 알고리즘의 판정에만 머물지 않도록 실제 음성과 전사를
대조하는 최소 표본을 만들었다. 표본은 연속 일치 길이 3–10, 11–80, 81 이상을
각각 두 블록씩 선택하고, 각 블록의 재매핑 구간 시작·끝을 한 건씩 뽑아 총
12건·6세션으로 구성했다.

- A: 길이열이 대상 전사에 대응한다고 제안한 다른 ID의 WAV 복사본
- B: 현재 대상 ID와 같은 이름의 WAV 복사본
- 원본 D: WAV 변경: 0
- 복사본: 24개, 복사 전후 SHA-256 불일치 0
- 전체 묶음: 약 1.51 MiB

검토 정본과 provenance:

```text
outputs/2020_wav_id_recovery_review_20260802/00_READ_ME_FIRST.md
outputs/2020_wav_id_recovery_review_20260802/REVIEW_MANIFEST.json
```

사람은 각 대상 전사를 읽고 우선 A가 맞는지만 판정한다. B는 필요할 때 현재
오대응을 비교하기 위한 보조다. `A 맞음`은 고신뢰 복구 적용 단계로 진행할
근거이지 원본 덮어쓰기 승인이 아니다. 불확실·불일치는 해당 블록의 자동 적용을
확대하지 않고 재계획 대상으로 돌린다.

## 코드 안전 수정

- PowerShell 5.1에서 `[ordered]` 후보 record를 `Measure-Object -Property`로
  합산하던 요약 오류를 명시적 정수 합산으로 교체했다.
- 현행 6-tier direct-DB 경로는 구형 형태소 TextGrid 감사를 사용하지 않는다.
- CSV–WAV gate는 세션 평균 98%만 보는 것이 아니라 승인 제외 후 남은 모든
  발화의 길이 잔차·누락·깨진 header가 0이어야 통과한다.
- 기존 검토표가 구형 형태소 감사 또는 실패한 음원 gate에 근거하면 재사용을
  거부한다.
- `alignment_and_analysis` 승인 발화의 WAV+LAB가 활성 코퍼스에 함께 남아 있으면
  MFA가 그대로 정렬할 수 있으므로, 승인 뒤 실제 격리되기 전에는 실행 gate가
  통과하지 않는다.

## 다음 순서

```text
고신뢰 remap 최소 음성 표본 12건 확인
  → H:에 영향 세션 원본 archive+hash manifest
  → 고신뢰 remap만 적용
  → 2020 CSV–WAV 전수 재감사
  → unresolved/ambiguous만 새 제외 후보표
  → 연구자 승인
  → 2020 공통 Jamo r2 MFA
```

이 복구는 새 tier 파일럿이 아니라 전수 정렬 입력의 동일성을 회복하는 필수
전처리다. 2020을 구 기준으로 재사용하거나 2021로 건너뛰지 않는다.
