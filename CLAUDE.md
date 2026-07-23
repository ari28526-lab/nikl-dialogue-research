# CLAUDE.md — 프로젝트 안내 (Claude Code용)

## 프로젝트
한국어 일상대화 말뭉치(NIKL 2020-2025, 발화 510만)의 **형태음운 변이 ×
빈도 효과** 연구. 사용자는 한국어 언어학 강사 (음성학·음운론·형태론).
한국어로 소통. 문서 색인: `docs/README.md`. 개요: `docs/PROJECT_SUMMARY.md`,
흐름: `docs/WORKFLOW.md`, 자료구축 코드 이해: `docs/자료구축_코드해설.md`,
**자산 위치 정본: `docs/ASSETS_LEDGER.md`(실측 기반)**.

## 3거점 구조 (데이터는 리포에 없음)
| 위치 | 내용 |
|---|---|
| **이 리포** (`C:\Users\ari30\research\2026_summer_research`) | 코드·문서·설정 (정본) |
| **D:** (**외장 SSD**, 7/20 HDD에서 이전) | 데이터 정본: `00_RAW`(원본·참조) `10_LAYERS`(분석 레이어·빈도사전) `20_AUDIO`(wav 585만+TextGrid) `30_PHENOMENA`(현상별) — ★단 **reference 4종·90_ARCHIVE는 미이전, 구 HDD 유일본** (ASSETS_LEDGER 참조) |
| **구 HDD** | 7/20 시점 전체 상 + 유일본(reference·90_ARCHIVE). 역방향 백업 겸용 |
| **G:** (Google Drive) | **선택적·되도록 미사용** Colab 셔틀. 1기 enriched CSV 원본 위치. 이 기기 연결 확인(2026-07-23) |

**클라우드 연산 방침**: gdrive는 되도록 안 씀. 클라우드가 필요하면 GitHub
Codespace를 우선(단 **Codespace는 CPU 전용**, 2025-08 GPU 폐기 / 그리고
**D: 로컬 외장하드를 못 봄** → 소규모 자립형 파일럿만 데이터 동봉). 운율
작업(F0·길이·강도, Parselmouth)은 CPU 계산이라 GPU·클라우드 불필요 → **로컬
우선**. 진짜 GPU가 필요해지면 그때 Colab 등 별도 검토.

모든 데이터 경로는 `config/paths.json` 하나로 관리 (`scripts/python/paths.py`
로더). 새 스크립트는 반드시 이를 사용.

## 실행 환경
- Python 3.13 시스템 + 바른 전용 venv:
  `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\.venv`
- MFA: conda env `mfa` (`C:\Users\ari30\miniforge3`), 모델 korean_mfa v3.0
- 바른 API 키: `C:\Users\ari30\Documents\Codex\_secrets\bareun\` (리포 밖!)
- PC: 저사양(8GB RAM, N200) + USB 외장 SSD → 대용량 작업은 밤샘 배치

## 필수 규칙
1. **D:\00_RAW은 불변** — 원본·참조자료 수정 금지
2. **대량 작업 전 파일럿** — 소표본 검증 후 전체 실행
3. 장시간 배치는 **체크포인트·재개 가능**하게 (기존 스크립트 패턴 참조)
4. 모든 절차·수치·결정은 **문서에 기록** — 방법론은
   `docs/decisions/METHODS_bareun_dialogue_reanalysis.md` (논문 인용 수준)
5. 파일 인코딩 utf-8; Windows 콘솔 cp949 대비
   `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` 패턴 사용.
   **`.ps1`은 반드시 UTF-8 BOM 포함** — PS5.1은 BOM 없으면 ANSI로 읽어
   한글 주석이 다음 줄을 삼킴(7/20 dialogue_json 줄 증발 사고, 실증됨)
6. 비밀(API 키)·대용량·저작권물(논문 PDF, KoFREN)은 커밋 금지 (.gitignore 확인)
7. MFA 실행 중 등 D: 배치가 돌 때는 D:를 읽는 다른 작업 금지 (경합)
8. **자산 이동·이전은 '전량'이 기본** — 부분 이전(선별)은 **미이전 목록을
   `docs/ASSETS_LEDGER.md`에 명시하고 사용자 확인**을 받은 경우에만.
   (7/20 SSD 이전에서 reference가 조용히 빠져 7/23에야 발견된 사고의 재발 방지)
9. **상태 선언은 실측으로만** — "있다/이전 완료/정렬 완료"는 검증 스크립트
   보고서(예: `preflight_search_master.py` → `logs/`)를 근거로만 쓰고,
   ASSETS_LEDGER를 갱신한다. 기억·추정으로 상태를 쓰지 않는다.
10. **사용자 콘솔에 한 줄 명령 지시 금지** — 점검·작업은 리포에 커밋된
    스크립트(전체 경로 한 줄 실행)로 만들고, 결과는 `logs/` 파일로 남겨
    Claude가 직접 읽는다. (인용부호·인코딩·경로 오류로 사용자를 소모시키지 않기)

## 스크립트
`scripts/SCRIPTS_INDEX.md`에 전체 색인 (파이프라인 순서·상태 포함).
Colab용은 `scripts/colab/`.

## 현재 상태 (2026-07-23)
- **A단계(자료 구축) 완료**: 형태소(바른, F1 0.929)·의미번호(76.4%)·빈도사전
  5종·메타데이터·표준 TextGrid 585만·gold 16,439발화·운율 파일럿 500발화
- **어절 4-tier 재정렬**: 2021 완료. ★G2P 부재 발견(phones spn 30~75%)으로
  2022~2025 **보류** — G2P 파일럿 검증 후 재개 (TODO_A단계 최우선, 독립 트랙)
- **검색 마스터 레이어**: 설계 확정(`docs/decisions/DESIGN_search_master_layer.md`),
  사전점검 통과(7/23) — **파일럿 직전**. 새 세션은
  `docs/HANDOFF_pilot_search_master.md`부터 읽고 시작
- ★reference 4종(사전 v2·MP·LS·다층위) SSD 미이전 — HDD 유일본, 회수 대기
- 남은 일·결정 대기: `docs/TODO_A단계.md` / 이력: `docs/WORK_HISTORY_2026-07.md`

## 사용자와의 협업 방식
- 스크립트 작성·검증은 Claude, 장시간 실행은 사용자가 자기 콘솔에서
- 언어학적 판단(환경 정의, 청취 검증, 임계값)은 반드시 사용자에게
- 진행 상황을 `docs/`의 WORKFLOW·TODO·WORK_HISTORY에 갱신 유지
  (철 지난 과정 문서는 `docs/archive/`)
- 사용자가 지쳐 있을 때일수록: 작업 단위를 줄이고, 한 번에 되는 것을
  우선하며, 실패 가능성이 있는 지시는 내지 않는다
