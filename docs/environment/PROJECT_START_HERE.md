# 프로젝트 시작 메모

이 문서는 `C:\Users\ari30\Dropbox\000_2026_summer_research` 폴더를 잊지 않고 다시 사용할 수 있도록 만든 안내서입니다.

## 이 폴더의 역할

이 폴더는 실제 연구 프로젝트의 중심 폴더입니다. 기존 Codex 설정 폴더는 설치 기록과 검증 기록을 남겨둔 장소이고, 이 Dropbox 폴더는 앞으로 분석 파일과 프로젝트 산출물을 모아둘 장소입니다.

## 폴더 구조

```text
000_2026_summer_research
├─ 000_START_HERE.md
├─ AGENTS.md
├─ README.md
├─ docs
│  ├─ environment
│  ├─ decisions
│  └─ references
├─ data
│  ├─ 00_external_paths
│  ├─ 01_pilot_samples
│  ├─ 02_intermediate
│  └─ 03_analysis_ready
├─ scripts
│  ├─ R
│  ├─ python
│  └─ powershell
├─ qmd
├─ notebooks
├─ work
│  ├─ bareun
│  ├─ mfa-pilot
│  ├─ praat-textgrid
│  ├─ r
│  └─ python
├─ outputs
│  ├─ figures
│  ├─ tables
│  └─ reports
├─ logs
└─ archive
```

## 다음에 Codex에게 시킬 때 첫 문장

```text
C:\Users\ari30\Dropbox\000_2026_summer_research 폴더에서 작업해줘.
먼저 AGENTS.md와 docs/environment/PROJECT_START_HERE.md를 읽고,
언어학 연구 환경 설정을 기준으로 시작해줘.
```

## 외장하드 자료를 연결했을 때

1. 외장하드의 실제 경로를 `data/00_external_paths/external-data-paths.md`에 기록합니다.
2. 원자료는 건드리지 않습니다.
3. 작은 pilot 샘플만 `data/01_pilot_samples`에 복사합니다.
4. 전사 정규화 결과는 `data/02_intermediate`에 둡니다.
5. 분석 직전의 정리된 표는 `data/03_analysis_ready`에 둡니다.
6. TextGrid, MFA 결과, 그림, 표, 보고서는 `outputs`나 `work`에 둡니다.

## 아직 비워둔 것

- 실제 연구 질문
- 외장하드 자료 경로
- Bareun API key
- 모두의 말뭉치 파일 구조
- 첫 pilot 샘플

이 항목들은 자료가 준비되면 하나씩 채우면 됩니다.

