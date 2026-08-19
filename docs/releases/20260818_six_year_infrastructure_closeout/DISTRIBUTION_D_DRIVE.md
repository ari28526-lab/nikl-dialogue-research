# 배포판 1 — D: 동결 드라이브 인계

기준일: 2026-08-19 KST

이 방식은 수령자가 해당 국립국어원 말뭉치의 이용 권한을 보유하고 있을 때,
자료구축 1단계의 원자료와 파생층이 함께 있는 D: 드라이브를 읽기 전용 연구
자산으로 인계하는 방식이다. 공개 웹 배포 방식이 아니다.

## 인계 범위

| 위치 | 역할 | 인계 후 원칙 |
|---|---|---|
| `D:\00_RAW` | 2020–2025 원 전사와 참조 자원 | 수정 금지 |
| `D:\20_AUDIO\03_wav` | 발화 음성 | 수정 금지 |
| `D:\10_LAYERS` | 형태소·의미번호·빈도·발음 참조·범용 검색층 | 정본은 읽기 전용 |
| `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809` | 공통발음·모델·계약 | 수정 금지 |
| `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809` | 보존 MFA DB와 최종 6-tier | 수정 금지 |
| `D:\30_RELEASES` | closeout, 수량·감사, 읽는 순서 | 최초 진입점 |

이 인계판에는 범용 `morph_search.v3`가 포함된다. 그러나 특정 음운 현상 query,
2단계 후보표, 검토 bundle과 실제 실현 판정은 A단계 release에 포함하지 않는다.
`D:\30_RELEASES\stage2_*`가 드라이브에 별도로 존재하더라도 이번 인계판의 정본
목록과 성과 주장에 포함하지 않는다.

## 인계 전 확인

1. 수령자의 NIKL 말뭉치 이용 권한과 허용 범위를 별도로 확인한다.
2. `D:\30_RELEASES`의 A단계 package manifest와 실제 파일 SHA-256을 대조한다.
3. 장시간 실행 중인 MFA·export·archive 작업이 없는지 확인한다.
4. 동결 자산을 복사하거나 운반하되 원본 폴더를 재배열하거나 이름을 바꾸지 않는다.
5. 인계 날짜, 매체 식별자, package manifest SHA와 인계자를 별도 기록한다.

이 확인은 이용조건에 대한 법률 판단을 대신하지 않는다. 원 음성·전사·TextGrid를
허가 없는 제3자나 공개 저장소로 다시 배포하지 않는다.

## 수령자가 읽는 순서

1. `D:\30_RELEASES\00_공유안내_20260819.md`
2. `D:\30_RELEASES\stage1_infrastructure_distribution_20260819\README_PACKAGE.md`
3. 같은 package의
   `outputs\reports\stage1_distribution_guide_for_nontechnical_readers_20260819.html`
4. 같은 package의 `RELEASE_SCOPE.json`
5. `outputs\reports\six_year_infrastructure_report_20260818.html`
6. `outputs\reports\SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json`
7. RC0 `QA_REPORT.json`과 `BASE_RELEASE_MANIFEST_2020_2025.json`

새 날짜 package를 만들기 전까지는 2026-08-18 closeout package를 근거로 쓸 수
있지만, 그 package에 들어 있는 2단계 계획 문서는 A단계 배포 범위 밖의 참고
자료로 취급한다.

## 수령자 사용 원칙

- 원자료와 동결 파생층을 직접 수정하지 않는다.
- 변경이 필요하면 별도 작업 루트와 새 release ID를 사용한다.
- 5,103,356건 전체 검색 가능과 4,286,046건 6-tier 정렬 완료를 구분한다.
- MFA phone을 실제 발음·실현 판정으로 사용하지 않는다.
- 후속 817,310건을 누락 자료로 삭제하지 않고 RC0/RC1 상태로 보존한다.

인계 후 특정 현상 검색을 시작하는 절차는 이 문서의 범위가 아니다.
