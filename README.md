# nikl-dialogue-research

한국어 일상대화 말뭉치(국립국어원 2020–2025, 발화 510만)의
**형태음운 변이 × 빈도 효과** 연구 — 코드·문서 저장소.

파이프라인: 형태소 분석(바른) → 의미번호(우리말샘) → 빈도사전 →
MFA 강제정렬 → 표준 TextGrid → (예정) 운율 주석 → R 통계.

## 어디서 시작하나
- **문서 색인** → [docs/README.md](docs/README.md) *(여기서 시작)*
- 연구 개요 1페이지 → [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)
- 자료구축 코드 이해 → [docs/자료구축_코드해설.md](docs/자료구축_코드해설.md)
- Claude Code 작업 안내 → [CLAUDE.md](CLAUDE.md)

## 3거점 구조 (데이터는 이 리포에 없음)
| 위치 | 내용 |
|---|---|
| **이 리포** | 코드·문서·설정 (정본). 경로는 [config/paths.json](config/paths.json) 하나로 중앙관리 |
| **D:** (외장하드) | 데이터 전부 — 원본·분석 레이어·음성(TextGrid 585만) |
| **G:** (Google Drive) | 1기 Colab 검색 작업 (원본은 [reference/colab_search/](reference/colab_search/)에 참고 사본) |

대용량 데이터·논문 PDF·빈도 규준·API 키·개인 파일럿 산출물은
`.gitignore`로 제외한다 (private 리포).

## 폴더
```
scripts/     파이프라인 코드 (python 22개 + colab + SCRIPTS_INDEX.md)
config/      paths.json (경로 중앙관리)
docs/        문서 — 개요·이력·방법론·환경·결정 기록 (docs/README.md 색인)
phenomena/   현상별 정의 (B단계: ㄴ삽입부터)
reference/   외부 작업 참고 사본 (colab_search — 읽기 전용)
data/ outputs/ logs/   로컬 작업 자리 (내용물은 대부분 gitignore)
```
