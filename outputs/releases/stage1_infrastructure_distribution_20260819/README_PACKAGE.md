# 자료구축 1단계 배포 패키지 (2026-08-19)

이 폴더는 2020–2025 기계적 분석·MFA 인프라의 A단계 배포 진입점이다. 기존
`stage1_infrastructure_closeout_20260818`을 덮어쓰지 않고 새 namespace로 만든다.

## 포함 범위

- 5,103,356발화 범용 기계 검색층과 exact-ID 상태 회계
- 4,286,046발화 r3 MFA·6-tier 완료 근거
- RC0/RC1/active-view manifest와 zero-drop 장부
- 1단계 closeout 보고서, 방법·한계, 두 배포 방식 안내

특정 현상 query·후보·G5–G8·실현 판정은 포함하지 않는다. 드라이브의 다른
`stage2_*` 폴더가 존재하더라도 이 package의 일부가 아니다.

## 읽는 순서

1. `outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html`
2. `RELEASE.md`
3. `docs/releases/20260818_six_year_infrastructure_closeout/DISTRIBUTION_D_DRIVE.md`
4. 같은 폴더의 `DISTRIBUTION_CODE_ONLY.md`
5. `outputs/reports/six_year_infrastructure_report_20260818.html`
6. `outputs/reports/SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json`
7. RC0 `QA_REPORT.json`과 `BASE_RELEASE_MANIFEST_2020_2025.json`

## 두 배포판

- D: 인계판은 허가 대상 원자료와 완성 파생층을 포함하므로 수령자의 NIKL 이용
  권한을 확인한 뒤 읽기 전용으로 인계한다.
- 코드 재현판은 원자료를 포함하지 않으며, 수령자가 같은 입력판을 자기 권한으로
  직접 확보한다. 향후 GitHub 선별 공개 가능성만 기록했으며 아직 공개·라이선스가
  승인된 것은 아니다.

`PACKAGE_MANIFEST.json`은 이 파일을 포함한 package payload의 source/destination
SHA-256을 기록한다. manifest 자신은 생성 순환을 피하기 위해 payload 목록에서
제외한다.
