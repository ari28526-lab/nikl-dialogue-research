# CLAUDE.md — 프로젝트 안내 (Claude Code용)

## 프로젝트
한국어 일상대화 말뭉치(NIKL 2020-2025, 발화 510만)의 **형태음운 변이 ×
빈도 효과** 연구. 사용자는 한국어 언어학 강사 (음성학·음운론·형태론).
한국어로 소통. 문서 색인: `docs/README.md`. 개요: `docs/PROJECT_SUMMARY.md`,
흐름: `docs/WORKFLOW.md`, 자료구축 코드 이해: `docs/자료구축_코드해설.md`.

## 3거점 구조 (데이터는 리포에 없음)
| 위치 | 내용 |
|---|---|
| **이 리포** (`C:\Users\ari30\research\2026_summer_research`) | 코드·문서·설정 (정본) |
| **D:** (외장하드) | 데이터 전부: `00_RAW`(원본·참조) `10_LAYERS`(분석 레이어·빈도사전) `20_AUDIO`(wav 585만+TextGrid) `30_PHENOMENA`(현상별) `90_ARCHIVE` |
| **G:** (Google Drive) | Colab 셔틀 (`DATA_2026/prosody_pilot` 등). 1기 검색 코드 참고 사본은 리포 `reference/colab_search/` |

모든 데이터 경로는 `config/paths.json` 하나로 관리 (`scripts/python/paths.py`
로더). 새 스크립트는 반드시 이를 사용.

## 실행 환경
- Python 3.13 시스템 + 바른 전용 venv:
  `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\.venv`
- MFA: conda env `mfa` (`C:\Users\ari30\miniforge3`), 모델 korean_mfa v3.0
- 바른 API 키: `C:\Users\ari30\Documents\Codex\_secrets\bareun\` (리포 밖!)
- PC: 저사양(8GB RAM, N200) + USB 외장하드 → 대용량 작업은 밤샘 배치

## 필수 규칙
1. **D:\00_RAW은 불변** — 원본·참조자료 수정 금지
2. **대량 작업 전 파일럿** — 소표본 검증 후 전체 실행
3. 장시간 배치는 **체크포인트·재개 가능**하게 (기존 스크립트 패턴 참조)
4. 모든 절차·수치·결정은 **문서에 기록** — 방법론은
   `docs/decisions/METHODS_bareun_dialogue_reanalysis.md` (논문 인용 수준)
5. 파일 인코딩 utf-8; Windows 콘솔 cp949 대비
   `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` 패턴 사용
6. 비밀(API 키)·대용량·저작권물(논문 PDF, KoFREN)은 커밋 금지 (.gitignore 확인)
7. MFA 실행 중 등 D: 배치가 돌 때는 D:를 읽는 다른 작업 금지 (경합)

## 스크립트
`scripts/SCRIPTS_INDEX.md`에 전체 색인 (파이프라인 순서·상태 포함).
Colab용은 `scripts/colab/`.

## 현재 상태 (2026-07-15)
- **A단계(자료 구축) 완료**: 형태소(바른, F1 0.929 검증)·의미번호(76.4%)·
  빈도사전 5종·메타데이터·음성 TextGrid 585만(표준 3-tier 통일)·
  gold 레이어(다층위 16,439발화)·운율 파일럿 500발화
- **B단계(현상 분석) 직전**: 첫 현상 ㄴ삽입 —
  `phenomena/34_n_insertion/definition.md` (사용자 검토 대기)
- 남은 일·결정 대기: `docs/TODO_A단계.md` 참조
- 작업 이력 전체: `docs/WORK_HISTORY_2026-07.md`

## 사용자와의 협업 방식
- 스크립트 작성·검증은 Claude, 장시간 실행은 사용자가 자기 콘솔에서
- 언어학적 판단(환경 정의, 청취 검증, 임계값)은 반드시 사용자에게
- 진행 상황을 `docs/`의 WORKFLOW·TODO·WORK_HISTORY에 갱신 유지
  (철 지난 과정 문서는 `docs/archive/`)
