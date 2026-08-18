# 2단계 6개년 후보 D: 미러 결과

작성일: 2026-08-18 KST

## 결과 (실측)

`D:\30_RELEASES\stage2_n_insertion_candidates_20260818\`에 6개년 후보
release 전체를 저장소 상대경로 미러로 배치했다.

- 구성: 동결 query·join 계약·승인 JSON, 연도별 후보/joined CSV 12폴더
  (총 5.29GB), 독립 감사 6종, 2단계 설계·G1~G4 결과 문서, README.
- 검증: 총 50파일 SHA-256을 C: 정본과 전수 대조해 **mismatch 0**
  (`PACKAGE_MANIFEST.json`). 복사+해싱 약 1분(SSD).
- 스크립트·로그: `build_d_stage2_package_20260818.ps1` (기존재 시 중단
  가드, detached 실행), 같은 폴더 `.log`.
- 이로써 후보 CSV는 C: 정본 + D: 이중 사본 체제가 됐다.

## 원칙 재확인

- 이 폴더는 읽기 전용 사본이며 덮어쓰지 않는다. 갱신은 저장소에서 하고
  새 날짜 폴더로 재수출한다.
- 1단계 패키지(`stage1_infrastructure_closeout_20260818`)와 별도 폴더로
  단계별 이력을 보존한다.
