# nikl-dialogue-research

국립국어원 2020–2025 한국어 일상대화 말뭉치 5,103,356발화의 자료구축과
형태음운 연구를 위한 코드·문서 저장소다.

## 현재 배포 가능한 범위

자료구축 1단계의 기계적 분석·MFA 인프라는 완료·동결됐다. 전 발화의 범용
형태소 검색층과 exact-ID 상태 회계가 있으며, 같은 r3 계약으로 정렬한
4,286,046발화의 6-tier TextGrid가 독립 QC를 통과했다.

이번 배포 범위에는 특정 음운 현상의 후보 검색, 검토 bundle, 실제 실현 판정과
통계 분석이 포함되지 않는다. 자세한 범위와 두 전달 방식은
[RELEASE.md](RELEASE.md)를 먼저 읽는다.

## 어디서 시작하나

- 배포 범위·D: 인계·코드 재현: [RELEASE.md](RELEASE.md)
- 프로그램을 모르는 독자를 위한 안내: [비전공자용 HTML](outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html)
- 문서 색인: [docs/README.md](docs/README.md)
- 연구의 현재 상태: [docs/environment/PROJECT_CURRENT_STATE.md](docs/environment/PROJECT_CURRENT_STATE.md)
- 1단계 closeout: [docs/releases/20260818_six_year_infrastructure_closeout/README.md](docs/releases/20260818_six_year_infrastructure_closeout/README.md)
- 생산·재현 기록: [docs/RUNBOOK_production_2020_2025.md](docs/RUNBOOK_production_2020_2025.md)
- 자료구축 코드 해설: [docs/자료구축_코드해설.md](docs/자료구축_코드해설.md)

## 데이터와 저장소의 경계

| 위치 | 내용 |
|---|---|
| 이 저장소 | 코드·계약·문서·작은 manifest와 감사 결과 |
| D: 동결본 | 허가 대상 원자료, 분석 레이어, 음성, 공통발음 release, MFA DB와 최종 6-tier |
| 수령자 로컬 환경 | 코드 재현판 사용자가 자기 권한으로 직접 확보한 NIKL 원자료와 외부 자원 |

원 음성·전사·TextGrid, 대형 파생 자료, 논문 PDF, 재배포권이 불명확한 빈도
규준과 API key는 코드 저장소에 포함하지 않는다.

향후 GitHub에는 전체 작업 저장소가 아니라 A단계 재현에 필요한 파일만 선별해
공개할 수 있다. 공개 여부와 코드 라이선스는 아직 확정되지 않았다.

## 폴더
```
scripts/     현행 파이프라인 코드 + 역사 코드 archive + SCRIPTS_INDEX.md
config/      paths.json (경로 중앙관리)
docs/        문서 — 개요·이력·방법론·환경·결정 기록 (docs/README.md 색인)
phenomena/   현상별 정의 (B단계: ㄴ삽입부터)
data/ outputs/ logs/   로컬 작업 자리 (내용물은 대부분 gitignore)
```
> `reference/colab_search/`(1기 코랩 검색 코드 참고 사본)는 혼동 방지를 위해
> **로컬 전용**이며 리포에 추적하지 않는다. 재작성한 검색 코드만 `scripts/`에 커밋한다.
