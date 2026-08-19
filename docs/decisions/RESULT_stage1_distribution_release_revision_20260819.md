# 자료구축 1단계 배포 release 개정 결과

작성일: 2026-08-19 KST

## 목적

자료구축 1단계의 기계적 분석·MFA 인프라만 배포하도록 기존 공유 안내를
정리했다. 특정 현상 검색과 연구자 실현 판정은 이후 별도 논의로 남기고, 다음 두
전달 경로를 분리했다.

1. 말뭉치 이용 권한을 확인한 수령자에게 D: 동결 드라이브를 읽기 전용으로 인계
2. 수령자가 같은 원자료를 자기 권한으로 직접 확보하는 코드 재현판

코드 재현판은 향후 GitHub 선별 공개 가능성을 고려했지만 공개 여부와 코드
라이선스는 승인하지 않았다.

## 범위 결정

- 포함: 기계 형태소·의미번호·빈도·발음 참조, 범용 `morph_search.v3`, 공통발음
  r3 계약, 4,286,046건 6-tier, 5,103,356건 RC0/RC1 zero-drop 회계
- 제외: 2단계 G1–G8, ㄴ 삽입 후보 941,903행, occurrence 문맥 연결, 검토 bundle,
  실현 판정, 통계·논문 결론
- 공개 후보 제외: 원 음성·전사·TextGrid·대형 DB/CSV, 개인 검토·승인 payload,
  secret·절대경로 로그, 재배포권 미확정 외부 자원, 전체 저장소 snapshot

범용 검색층은 자료구축 1단계의 완성 기계 인프라이므로 포함한다. 특정 현상의
query 결과는 포함하지 않는다.

## D: 물질화 결과

- 새 package:
  `D:\30_RELEASES\stage1_infrastructure_distribution_20260819`
- 최신 인계 안내:
  `D:\30_RELEASES\00_공유안내_20260819.md`
- 독립 감사 사본:
  `D:\30_RELEASES\AUDIT_stage1_distribution_package_20260819.json`
- payload: 비전공자용 HTML·QMD·HTML 감사 포함 56파일
- 누락 0, 예상 밖 0, SHA mismatch 0, 금지 범주 0
- `stage2_payload_included=false`
- `repository_snapshot_included=false`
- 감사 상태: `passed`

기존 `stage1_infrastructure_closeout_20260818`과 2026-08-18 안내는 삭제·수정하지
않았다. 새 날짜 namespace가 A단계 배포 진입점을 대체한다. D:의 동결 원자료·
검색층·MFA DB·6-tier도 변경하지 않았다.

## 정본 파일

- `RELEASE.md`
- `outputs/releases/stage1_infrastructure_distribution_20260819/RELEASE_SCOPE.json`
- `docs/releases/20260818_six_year_infrastructure_closeout/DISTRIBUTION_D_DRIVE.md`
- `docs/releases/20260818_six_year_infrastructure_closeout/DISTRIBUTION_CODE_ONLY.md`
- `docs/releases/20260818_six_year_infrastructure_closeout/PUBLIC_CODE_RELEASE_CANDIDATE.md`
- `outputs/reports/AUDIT_stage1_distribution_package_20260819.json`
- `outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html`
- `outputs/reports/AUDIT_stage1_distribution_guide_for_nontechnical_readers_20260819.json`

GitHub 공개를 실제로 진행하려면 allowlist package, code license, secret·개인정보·
절대경로 검사, 깨끗한 환경 smoke test와 연구자 manifest SHA 승인을 별도 Gate로
통과해야 한다.
