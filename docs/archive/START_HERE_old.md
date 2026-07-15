# 000_2026_summer_research 시작 안내

이 폴더는 2026년 여름 언어학 연구 작업을 모아두는 프로젝트 폴더입니다.

새 Codex 세션이나 VS Code에서 이 폴더를 열었을 때는 먼저 아래 파일을 확인하세요.

1. `AGENTS.md`
2. `docs/environment/PROJECT_START_HERE.md`
3. `docs/environment/linguistics-research-environment-master-notes.md`

## 기본 원칙

- 원자료, 특히 모두의 말뭉치처럼 큰 외장하드 자료는 이 폴더로 통째로 복사하지 않습니다.
- 이 폴더에는 분석 스크립트, 작은 pilot 샘플, 중간 산출물, TextGrid, 보고서, 로그를 둡니다.
- API key나 비밀번호는 이 폴더에 저장하지 않습니다.
- 큰 자동 처리 전에는 항상 작은 pilot subset으로 먼저 검증합니다.

## 자주 쓰는 작업 위치

```text
data/00_external_paths      외장하드 원자료 위치 기록
data/01_pilot_samples       작은 실험용 샘플
data/02_intermediate        정규화 전사, 중간 CSV/JSON
data/03_analysis_ready      분석 직전의 정리된 데이터
scripts/R                   R 스크립트
scripts/python              Python 스크립트
qmd                         Quarto 문서
work/mfa-pilot              MFA 정렬 실험
work/bareun                 바른 형태소 분석 실험
work/praat-textgrid         Praat/TextGrid 작업
outputs                     최종 표, 그림, 보고서
logs                        실행 로그
```

