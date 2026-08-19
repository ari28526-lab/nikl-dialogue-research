# 배포판 2 — 원자료 직접 확보형 코드 재현판

기준일: 2026-08-19 KST

상태: **선별 배포 설계 완료, GitHub 공개 여부 미확정**

이 방식은 원자료나 완성 TextGrid를 전달하지 않는다. 수령자가 국립국어원에서
자기 이용 권한으로 같은 자료를 직접 확보하고, 선별된 코드·계약·manifest를
사용해 자료구축 1단계를 자기 환경에서 재현하는 방식이다.

## 전달하는 것과 전달하지 않는 것

전달 후보:

- A단계 생성기·감사기·PowerShell 안전 검사
- 환경·경로 설정 예시와 고정 contract
- 생산 RUNBOOK과 1단계 closeout 방법 문서
- 수량·schema·SHA 필드가 있는 작은 manifest와 감사 예시
- 원자료를 포함하지 않는 최소 테스트 fixture

전달하지 않는 것:

- NIKL 원 음성·전사·참조 자료와 이를 복제한 TextGrid
- 대형 CSV/Parquet, MFA DB, 모델 cache와 로컬 작업 산출물
- API key, 개인 Dropbox·로컬 로그·검토 bundle
- 재배포권이 확인되지 않은 빈도 규준과 논문 PDF
- 2단계 G1–G8 query·후보·검토·실현 판정 산출물

전체 작업 저장소 snapshot을 그대로 공개본으로 사용하지 않는다. 향후 GitHub
공개 시에는 [선별 공개 후보 규칙](PUBLIC_CODE_RELEASE_CANDIDATE.md)의 allowlist를
별도 검토한다.

## 같은 입력판을 직접 준비한다

다음 폴더명은 현재 A단계 입력 계약이 사용한 판을 기록한 것이다.

| 연도 | 대화 말뭉치 폴더 |
|---:|---|
| 2020 | `NIKL_DIALOGUE_2020_v1.4` |
| 2021 | `NIKL_DIALOGUE_2021_v1.1` |
| 2022 | `NIKL_DIALOGUE_2022_v1.0_JSON` |
| 2023 | `NIKL_DIALOGUE_2023_v1.1` |
| 2024 | `NIKL_DIALOGUE_2024_v1.0` |
| 2025 | `NIKL_DIALOGUE_2025_v1.0` |

참조 자원은 우리말샘/사전 자료, 형태 분석 말뭉치 MP v1.1, 어휘 의미 말뭉치
LS, 2025 다층위 말뭉치 v1.0 등 현재 `config/paths.json`과 input contract가
가리키는 판을 수령자가 직접 확보한다. 바른 형태소 분석 API, Korean MFA 모델,
Python·MFA·Pynini 버전과 외부 빈도 자원도 각각 이용조건을 확인해 준비한다.

자료 제공기관이 파일을 갱신하면 폴더명이 같아도 byte가 달라질 수 있다. 원자료
SHA가 input contract와 다르면 기존 수량을 강제로 맞추지 말고 새 input release로
기록한다.

## 재현 순서

1. 선별 코드 release를 별도 작업 폴더에 푼다.
2. `config/paths.json`의 절대경로를 자기 환경에 맞게 설정한다. 현재 저장소의
   로컬 경로는 설치 기본값이 아니라 원 실행의 provenance다.
3. Python·R·Quarto·MFA 환경을 `docs/environment`의 버전 기록에 맞춰 확인한다.
4. 원자료를 읽기 전용으로 배치하고 연도별 파일 수·ID·SHA를 먼저 진단한다.
5. Windows PowerShell 5.1 안전·runtime tests와 각 runner의 `-PreflightOnly`를
   통과한다.
6. `docs/RUNBOOK_production_2020_2025.md`의 계약 순서를 따르되 한 연도씩 실행한다.
7. 생성기와 별도 감사기를 실행하고, 최종 수량을
   `SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json`과 대조한다.
8. 입력판·외부 서비스·runtime이 다르면 “동일 release 재현”이 아니라 새 파생
   release로 보고 차이를 기록한다.

현재 RUNBOOK에는 완료된 로컬 생산의 checkpoint와 절대경로가 함께 남아 있다.
따라서 공개 후보를 실제 배포하기 전에는 설치자용 상대경로 예시, 외부 자원 목록,
최소 fixture와 깨끗한 환경 smoke test를 별도 통과시켜야 한다.

## 재현 수준을 구분한다

- **방법 재현**: 같은 계약·코드·검증 순서를 적용한다.
- **수량 재현**: 동일 입력판에서 연도별 발화와 상태 회계가 같은지 확인한다.
- **byte 재현**: 원자료, 외부 서비스 응답, 모델·runtime과 모든 입력 SHA가 같을
  때만 주장한다.

코드만 공개했다는 사실은 byte-identical 재현을 자동으로 보장하지 않는다.
불일치는 숨기거나 자동 보정하지 않고 manifest 차이로 보고한다.

이 코드 재현판은 A단계까지만 다룬다. 특정 음운 현상 검색은 별도 release와
연구자 결정 뒤에 추가한다.
