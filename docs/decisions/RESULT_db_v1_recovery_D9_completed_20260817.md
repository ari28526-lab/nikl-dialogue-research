# 연구 DB v1 recovery D9 통제 재정렬 완료

기록일: 2026-08-17 KST

## 결론

D8에서 원자료 identity가 확인된 미정렬 19건만 `beam=100`,
`retry_beam=400`으로 한 차례 격리 재정렬했고, 19건 모두 `words`·`phones`
TextGrid가 생성됐다. 미정렬은 0건이며 MFA 실행시간은 707.031초였다.

음향모델, 공통발음 r3 사전, G2P provenance와 LAB는 바꾸지 않았다. 따라서 이
결과는 해당 19건의 D5 실패가 적어도 탐색 폭에 민감했음을 보여준다. 그러나
TextGrid 생성 성공이 경계의 언어학적 타당성이나 단일 화자 음향분석 적합성을
자동으로 보장하지는 않는다.

## 범위와 안전성

- 실행 exact ID: 19건(2020 2, 2021 5, 2022 3, 2023 5, 2024 3, 2025 1)
- 생성 TextGrid: 19건, 누락 0건
- 원음원 겹침 표지: 4건
- 0.1초 미만 25건: 실행하지 않음
- 전체연도와 D5 성공 11건: 재실행하지 않음
- r3 본체·연구용 6-tier·DB v1 자동 병합: 0건
- 원자료 수정·삭제: 0건

실행 증거는 다음 격리 root에 보존한다.

```text
D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D9_CONTROLLED_BEAM_RETRY_0001
```

완료 marker와 실행 감사 SHA-256은 각각
`8ee6e78613c3619a532025df16548082cee49bdd43cec6466c8c5408798b454a`,
`56ca39bdcdd7894390244f5266e77e47dcd9dc87c1b4cc206bab91bf90ea5803`다.

## 검토 묶음

19개 WAV·LAB·2-tier TextGrid를 번호가 같은 한 폴더에 모았다.

```text
outputs/reviews/db_v1_recovery_d9_review_19_20260817
```

독립 감사는 파일 수 19/19/19, exact-ID 19건, WAV–TextGrid 길이,
`words`·`phones` tier와 복사 SHA를 재검사해
`passed_flat_review_bundle_no_adoption`으로 끝났다. 검토 정본은
`00_REVIEW_19.json`이고, 4개 겹침 표지는 따로 표시된다.

현재 공식 spreadsheet 의존성 loader가 제공되지 않아 XLSX를 임의 라이브러리로
우회 생성하지 않았다. 이는 데이터 실패가 아니라 검토 UI 제약이며, JSON과
manifest가 권위 기록이다.

연구자 `ari30`은 D9의 19개 WAV와 대응 LAB·TextGrid·메타데이터를 개인 검토
목적으로만 다음 로컬 Dropbox 동기화 폴더에 복사하도록 승인했다.

```text
C:\Users\ari30\Dropbox\DB_V1_RECOVERY_D9_REVIEW_19_20260817
```

61개 파일·1,780,531 bytes를 복사하고 파일명·크기·SHA-256을 전수 비교했다.
원본·목적지 파일집합 SHA는 모두
`ab250065a827b109afc1d6cf8cecb6f9d9a69c3a46ed428afe9abe80a59e4b60`로
일치한다. 공유 링크 생성·외부 공유 설정 변경은 하지 않았다. 이 검사는 로컬
Dropbox 폴더까지의 복사를 보증하며 다른 컴퓨터에서 보기 전 Dropbox 클라이언트의
동기화 완료 표시는 별도로 확인한다.

## 다음 Gate

연구자가 19개 WAV–LAB 일치와 `words`·`phones` 경계를 검토한 뒤 각 exact ID를
`approve_recovery_alignment`, `keep_separate_partial`, `reject_technical` 중
하나로 판정한다. 이 결정 전에는 6-tier 생성이나 DB v1 편입을 하지 않는다.

## 논문 방법론 기록 요지

기본 탐색 폭에서 정렬 결과가 생성되지 않은 발화 가운데 원자료와 전사 identity,
음성 길이가 확인된 19건만 동일한 모델·발음사전·전사를 유지한 채 탐색 폭을
10/40에서 100/400으로 한 차례 확장했다. 전부 정렬됐지만 결과는 본체에 자동
편입하지 않고 수동 경계 검토 대상으로 분리했으며, 0.1초 미만 원 조각 25건은
알고리즘 실패와 구분해 기술 제외 장부에 보존했다.
