# 000_2026_summer_research

2026년 여름 언어학 연구를 위한 작업 폴더입니다.

이 폴더는 다음 작업을 염두에 두고 구성했습니다.

- 모두의 말뭉치 대화 자료 기반 TextGrid 생성
- Montreal Forced Aligner 기반 forced alignment
- Praat, TextGrid, 음성/음운 분석
- 바른 형태소 분석기 기반 한국어 형태소 분석
- R 기반 통계, brms/Stan, XAI/SHAP, LDA 분석
- Python 기반 전처리, 자동화, 파일 변환
- Quarto 기반 분석 보고서 작성

## 처음 열었을 때

Codex나 VS Code에서 이 폴더를 열면 먼저 `000_START_HERE.md`와 `AGENTS.md`를 확인하세요.

Codex에게는 이렇게 말하면 됩니다.

```text
이 폴더의 AGENTS.md와 docs/environment/PROJECT_START_HERE.md를 먼저 읽고,
언어학 연구 환경 설정을 기준으로 작업해줘.
```

## 자료 관리

외장하드의 원자료는 이 폴더에 통째로 복사하지 말고 `data/00_external_paths`에 위치만 기록합니다.
실제 작업은 작은 샘플부터 `data/01_pilot_samples`에 복사해서 시작합니다.

