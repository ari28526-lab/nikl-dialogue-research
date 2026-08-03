# nikl-dialogue-research

한국어 일상대화 말뭉치(국립국어원 2020–2025, 발화 510만)의
**형태음운 변이 × 빈도 효과** 연구 — 코드·문서 저장소.

파이프라인: 형태소 분석(바른) → 의미번호(우리말샘) → 빈도사전 →
MFA 강제정렬 → 표준 TextGrid → (예정) 운율 주석 → R 통계.

## 어디서 시작하나
- **문서 색인** → [docs/README.md](docs/README.md) *(여기서 시작)*
- 연구 개요·현재 상태 → [docs/environment/PROJECT_CURRENT_STATE.md](docs/environment/PROJECT_CURRENT_STATE.md)
- 자료구축 코드 이해 → [docs/자료구축_코드해설.md](docs/자료구축_코드해설.md)
- Claude Code 작업 안내 → [CLAUDE.md](CLAUDE.md)

현재 안전 정지점은 **2020 신규 r2 MFA·6-tier·독립 QC·연구자 승인·Gate B
완료, 2021 미시작**이다. 구 2021–2025 결과·상태는 E: 검증 archive와 대조해
활성 작업공간에서 정리했고 기존 2021 LAB은 다음 실행에서 전수 재검증한다.
다음 명령은 반드시
[생산 RUNBOOK](docs/RUNBOOK_production_2020_2025.md)을 따른다.

## 3거점 구조 (데이터는 이 리포에 없음)
| 위치 | 내용 |
|---|---|
| **이 리포** | 코드·문서·설정 (정본). 경로는 [config/paths.json](config/paths.json) 하나로 중앙관리 |
| **D:** (외장하드) | 원본·분석 레이어·음성·연도별 신규 r2 TextGrid/동반표 |
| **G:** (Google Drive) | 1기 Colab 검색 작업. 참고 사본은 로컬 `reference/colab_search/`에만 보관(추적 제외) — 재작성본만 `scripts/`에 커밋 |

대용량 데이터·논문 PDF·빈도 규준·API 키·개인 파일럿 산출물은
`.gitignore`로 제외한다 (private 리포).

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
