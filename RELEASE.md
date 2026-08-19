# 자료구축 1단계(A단계) 배포 안내

기준일: 2026-08-19 KST

상태: **기계적 분석·MFA 인프라 완료본 배포 가능**

프로그램을 모르는 독자는 먼저
[비전공자용 HTML 안내서](outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html)를
읽으면 된다. 인터넷 연결 없이 열리는 단일 파일이다.

여기서 A단계는 RC0 문서의 세부 절 `A–C` 중 A만을 뜻하지 않는다. 이 문서에서
A단계는 2020–2025 자료구축 1단계 전체, 즉 기계적 분석과 동결된 MFA 정렬
인프라를 뜻한다.

## 배포 범위

포함 범위는 다음과 같다.

- 원천 발화 5,103,356건의 exact-ID 상태 회계
- 바른 형태소 분석, A2 의미번호, A3 빈도사전, 발음 참조층
- 전 발화 5,103,356건의 범용 `morph_search.v3` 기계 검색층
- `common_pron_mfa_r3_20260809` 공통발음 계약
- 독립 QC를 통과한 4,286,046건의 6-tier TextGrid
- 기술·발음 후속 817,310건의 zero-drop 장부와 RC1 append-only 보정
- 생성 코드, 계약, manifest, 감사 보고서와 재현 문서

`morph_search.v3`는 A단계에서 이미 만든 범용 기계 인프라이므로 포함한다. 반면
특정 음운 현상의 query, 후보표, occurrence→TextGrid 연결, 검토 bundle, 실제
실현 판정은 포함하지 않는다. 따라서 2단계 G1–G8 산출물과 ㄴ 삽입 후보
941,903행은 이 배포의 대상이 아니다.

## 두 배포 방식

| 방식 | 전달물 | 수령자 조건 | 결과 |
|---|---|---|---|
| D: 드라이브 인계 | 허가 대상 원자료와 완성 파생층을 포함한 동결 드라이브 | 해당 NIKL 말뭉치 이용 권한을 수령자가 보유 | 재계산 없이 A단계 자산을 읽기 전용으로 사용 |
| 코드 재현판 | 선별된 코드·설정 예시·계약·작은 manifest·문서 | 수령자가 같은 원자료와 외부 자원을 자기 권한으로 직접 확보 | 자기 환경에서 A단계를 재현하고 manifest로 검증 |

세부 절차:

1. [D: 드라이브 인계판](docs/releases/20260818_six_year_infrastructure_closeout/DISTRIBUTION_D_DRIVE.md)
2. [코드 재현판](docs/releases/20260818_six_year_infrastructure_closeout/DISTRIBUTION_CODE_ONLY.md)
3. [향후 GitHub 선별 공개 후보 규칙](docs/releases/20260818_six_year_infrastructure_closeout/PUBLIC_CODE_RELEASE_CANDIDATE.md)

## 해석 한계

- 5,103,356건 전체가 범용 검색 가능하다는 주장과 4,286,046건만 최종 6-tier를
  갖는다는 주장을 구분한다.
- MFA phone과 `phoneme_r_auto`는 실제 발음 또는 음운 현상 실현의 정답이 아니다.
- 이 release를 “6개년 음운 현상 분석 결과”라고 부르지 않는다.
- D: 인계판은 허가 없는 제3자에게 재배포하지 않는다.
- 코드 재현판은 아직 GitHub 공개가 확정되지 않았다. 공개 전에는 별도 allowlist,
  경로·개인정보·비밀 검사와 코드 라이선스 결정이 필요하다.

정본 수량과 방법은
[closeout README](docs/releases/20260818_six_year_infrastructure_closeout/README.md)와
[`SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json`](outputs/reports/SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json)에서
확인한다.
