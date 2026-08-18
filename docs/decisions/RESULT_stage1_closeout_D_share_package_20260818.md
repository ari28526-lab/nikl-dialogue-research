# 1단계 closeout D: 공유 패키지 생성 결과

작성일: 2026-08-18 KST

## 목적

자료구축 1단계 종료(`DECISION_stage1_data_infrastructure_closure_20260818.md`)
후, D: 드라이브를 "연구자료 공유용 외장하드"로 건넬 수 있도록 closeout 문서·
release manifest·종합 보고서·저장소 snapshot을 D:에 자체 포함 사본으로
배치했다. D:의 기존 정본(00_RAW, 10_LAYERS 검색층, mfa_eojeol\r3 보존
DB·6-tier, mfa_common_pron\releases)과 합치면 드라이브 하나로 자료구축 전체가
설명된다.

## 결과 (실측)

- 위치: `D:\30_RELEASES\stage1_infrastructure_closeout_20260818\`
- 구성: 저장소 상대경로 미러 — closeout 해설 6종, RC0(장부 포함 20파일)·
  RC1·active view release, 종합 HTML 보고서+qmd, 수량 정본·독립감사 JSON,
  1단계 종료 결정·2단계 설계·B1 생산 계획·파일럿 결과 2종·연구자 승인 JSON,
  `README_PACKAGE.md`(읽는 순서·라이선스 주의), 저장소 snapshot
  `repo_snapshot_7160432.zip`(7,122,194 bytes, commit `7160432` HEAD)
- 검증: 총 48파일 SHA-256을 원본과 전수 대조해 **mismatch 0**.
  `PACKAGE_MANIFEST.json`에 파일별 relpath·bytes·sha256·source_match 기록.
- 안전: 실행 전 읽기 전용 진단으로 D: 여유 62.7GB·실행 중 배치 0건 확인.
  D:\00_RAW 등 기존 자산은 접근하지 않았고 신규 폴더만 생성했다. 목적지
  기존재 시 중단하는 가드 포함.
- 실행 스크립트·로그:
  `C:\Users\ari30\.claude-server-commander\build_d_share_package_20260818.ps1`
  (구문검사 0오류 후 실행), 같은 폴더 `.log`.

## 주의

- 이 패키지는 읽기 전용 사본이다. 수정은 저장소에서 하고 재수출한다.
- 드라이브 공유 시 NIKL corpus 라이선스에 따라 수령자의 이용 권한을 별도
  확인해야 하며, 원 음성·전사는 공개 저장소에 올리지 않는다.
- 이후 저장소 정본이 갱신되면(예: 2단계 산출물) 같은 스크립트 패턴으로 새
  날짜 폴더를 만들며, 기존 패키지 폴더를 덮어쓰지 않는다.
