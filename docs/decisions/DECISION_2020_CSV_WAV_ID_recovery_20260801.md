# 2020 CSV–WAV 발화 ID 대응 복구 결정

결정일: 2026-08-01 KST
상태: `RECOVERY APPLIED AND VERIFIED — MFA EXCLUSION REVIEW NEXT`

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

연구자 청취 결과는 12/12 모두 `A_MATCHES_TARGET`이었다. 첫 두 건은 개별로,
3–12번은 각 확인 문장과 같다는 일괄 응답으로 기록했다. 판정 파일은 다음과
같고 Dropbox 검토 묶음에도 같은 SHA의 사본을 두었다.

```text
outputs/2020_wav_id_recovery_review_20260802/REVIEW_DECISIONS.json
outputs/2020_wav_id_recovery_review_20260802/REVIEW_DECISIONS.md
```

방법론적 해석 범위는 `연속 일치 길이 3–10, 11–80, 81+의 6개 블록에서
재매핑 구간 양끝 12건 모두 음성–전사 일치`다. 이를 고신뢰 후보 14,221건의
전수 수동 검수라고 쓰지 않는다.

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

## 복구 코퍼스 계약과 dry-run

원본을 이름 변경하거나 덮어쓰는 방식은 폐기하고 별도 파생 코퍼스를 만들기로
확정했다.

- 원본(읽기 전용): `D:\20_AUDIO\03_wav\individual`
- 파생 코퍼스: `D:\20_AUDIO\04_wav_id_recovered_staging\individual\2020`
- 독립 archive: `E:\READ_ONLY_ARCHIVE\2026_summer_research\wav_id_recovery_2020_<contract>`
- 최종 계약: `D:\20_AUDIO\04_wav_id_recovered_staging\contracts\2020.json`

실자료 전수 dry-run 결과는 다음과 같다.

- 검색 발화: 870,437, 세션: 2,232
- 파생 코퍼스 예정 발화: 868,603
- 연구자 제외 검토 예정: 1,834 (`ambiguous` 92 + `unresolved` 1,742)
- 영향 세션 archive: 129세션, 50,777 WAV, 비압축 3.148 GiB
- 파생 코퍼스 논리 크기: 53.96 GiB
- 사용자 청취 결정: 12/12 `A_MATCHES_TARGET`
- 원본 변경: 0, 최종 apply 완료: 아직 0

영향 없는 세션은 같은 D: 볼륨의 NTFS hardlink로 물리 중복을 줄인다. 영향
세션은 E: ZIP의 WAV를 SHA-256으로 다시 읽어 검증한 뒤 수정 ID의 독립
복사본을 만든다. 중단 시 세션별 checkpoint를 검증해 재개하며, 불완전 출력은
삭제하지 않고 stale 영역으로 이동한다. 원본이 불변이므로 rollback은 파생
코퍼스를 격리하는 것이며 원본 복원 작업은 필요 없다.

dry-run 증거:

```text
outputs/reports/PREFLIGHT_2020_wav_recovery_corpus_20260802.json
```

첫 apply는 기존 계약에서 10/129세션 archive를 검증 완료한 뒤
`SDRW2000000176` 원음 폴더 누락에서 안전 중단됐다. 이 세션의 513발화는 모두
이미 `target_unresolved`이며 파생 코퍼스 포함 대상은 0건이다. dry-run은 이를
올바르게 제외했지만 archive 함수가 모든 영향 세션에 물리 ZIP이 있다고 가정한
구현 오류였다. D: 원본 변경 0, E: 완료 ZIP 10개/약 176 MiB는 그대로 보존했다.

수정 계약은 원음이 존재하는 128세션만 ZIP으로 보존하고, 위 1세션에는
`verified_absent`, file_count 0, ZIP 없음이 명시된 manifest를 만든다. 누락
세션에 포함 대상이 한 건이라도 있으면 계속 fail-closed한다. builder SHA가
달라져 새 contract ID를 발급하며 구 계약의 ZIP 10개는 실패 근거로 자동
삭제하거나 새 계약에 무근거 재사용하지 않는다.

## 최종 적용 결과

수정 계약 apply는 2026-08-02 09:58–10:24 KST에 완료됐다.

- final contract: `passed`
- contract ID: `eb64f80d9106d14c7b2a267811cdf2dc2fe29e890cc335a7029a8cca24a7375f`
- 파생 WAV: 계약 868,603 / 독립 파일 계수 868,603
- 파생 세션 디렉터리: 2,232
- E: archive: ZIP 128개, manifest 129개
- `verified_absent`: 1개 (`SDRW2000000176`)
- 연구자 제외 검토 이월: 1,834
- 원본 변경: 0, 종료 lock: 0
- 2020 MFA resolver: `Recovered=True`, 새 파생 root 선택

증거:

```text
outputs/reports/APPLY_2020_wav_recovery_corpus_20260802.json
D:/20_AUDIO/04_wav_id_recovered_staging/contracts/2020.json
```

## 다음 순서

```text
고신뢰 remap 최소 음성 표본 12건 확인(완료)
  → E:에 영향 세션 원본 archive+hash manifest
  → D: 별도 파생 코퍼스에 고신뢰 remap 적용
  → 2020 CSV–WAV 전수 재감사
  → unresolved/ambiguous만 새 제외 후보표
  → 연구자 승인
  → 2020 공통 Jamo r2 MFA
```

이 복구는 새 tier 파일럿이 아니라 전수 정렬 입력의 동일성을 회복하는 필수
전처리다. 2020을 구 기준으로 재사용하거나 2021로 건너뛰지 않는다.
