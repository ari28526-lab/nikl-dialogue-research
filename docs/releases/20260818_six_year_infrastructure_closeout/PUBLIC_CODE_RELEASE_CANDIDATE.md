# 향후 GitHub 선별 공개 후보 규칙

기준일: 2026-08-19 KST

상태: **공개 후보 설계만 완료, 공개·저장소 전환·라이선스 미승인**

향후 A단계 코드 재현 부분만 GitHub에 공개할 가능성을 고려한 준비 문서다. 현재
작업 저장소 전체를 공개해도 된다는 승인이나 실제 GitHub 작업을 뜻하지 않는다.

## 공개 단위 원칙

전체 저장소의 denylist 복사보다 작은 allowlist package를 새로 만드는 방식을
사용한다. 공개 후보는 다음 범주로 제한한다.

- `scripts/`의 A단계 현행 생성기·감사기와 그 직접 의존 모듈
- `tests/`의 A단계 안전·회귀 검사와 비식별 최소 fixture
- 비밀과 개인 절대경로를 제거한 설정 예시
- A단계 RUNBOOK, schema, data dictionary, closeout 방법·한계 문서
- 원자료를 복원할 수 없는 작은 수량·contract·감사 예시
- 배포 시점의 commit, 파일 SHA와 공개 allowlist manifest

다음은 기본 제외한다.

- 원 음성·전사·TextGrid·CSV/Parquet·DB·압축 원자료
- `outputs/reviews`, `outputs/approvals`, 개인 메모와 청취 bundle
- API key, secret 경로, Dropbox·사용자명·드라이브 위치가 남은 로그
- 재배포권이 확인되지 않은 사전·빈도 자료, 모델 cache와 논문 PDF
- `docs/archive`, 과거 workspace snapshot, 대형 repo snapshot
- 2단계 query·후보·G5–G8 코드와 결과

## 공개 전 필수 Gate

1. 공개할 코드의 라이선스와 제3자 코드 고지를 연구자가 결정한다.
2. NIKL·외부 사전·빈도 자료의 이용조건을 파일 범주별로 확인한다.
3. allowlist 전 파일에 secret·개인정보·절대경로·원문 전사 검사를 수행한다.
4. 깨끗한 별도 폴더에서 공개 package만으로 설치·최소 fixture smoke test를 한다.
5. 실행 예시가 원자료 다운로드를 자동화하거나 접근통제를 우회하지 않는지 확인한다.
6. 공개 manifest의 파일 수·bytes·SHA와 실제 package를 독립 감사한다.
7. 연구자가 공개 후보 commit과 manifest SHA를 명시 승인한다.

현재 저장소에는 코드 라이선스 파일이 없고, 내부 재현성을 위해 개인 PC의 절대
경로를 기록한 문서·설정이 다수 있다. 따라서 현 상태의 전체 저장소 또는 기존
`repo_snapshot_*.zip`은 공개 후보가 아니다.

## 공개 후에도 유지할 경계

- GitHub release에는 코드와 문서만 두고 원자료 다운로드 링크·절차는 제공기관의
  공식 경로를 안내하는 수준으로 제한한다.
- 사용자가 자기 권한으로 받은 입력은 공개 저장소 밖에 둔다.
- 동일 수량을 얻지 못하면 자동으로 계속하지 않고 입력판과 manifest 차이를 남긴다.
- A단계 공개 후 특정 현상 검색 코드는 별도 범위 결정과 새 release로 다룬다.
