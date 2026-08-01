# CLAUDE.md — 프로젝트 실행 안내

## 연구와 언어

한국어 일상대화 말뭉치(NIKL 2020–2025, 약 510만 발화)의 형태음운 환경과
실현을 연구한다. 사용자에게는 한국어로 설명한다.

연구 흐름은 다음과 같다.

```text
CSV/Parquet에서 형태소·표기 환경 검색
  → utt_id로 WAV·TextGrid 수집
  → 선별 후보에 KOINA/stitch/wav2vec2 보조층 추가
  → 연구자가 실제 실현 여부 판정
```

MFA/G2P phone을 실제 실현 판정값으로 취급하지 않는다.

## 새 세션의 유일한 진입점

1. `docs/README.md`
2. `docs/environment/PROJECT_CURRENT_STATE.md`
3. `docs/RUNBOOK_production_2020_2025.md`
4. 실제 위치가 필요할 때 `docs/ASSETS_LEDGER.md`

`TODO_A단계.md`, `WORKFLOW.md`, 과거 HANDOFF/RUNBOOK은 역사 기록이며 현재
실행 정본이 아니다.

## 고정 환경

- 프로젝트: `C:\Users\ari30\research\2026_summer_research`
- 데이터 정본·대형 산출물: D:
- pipeline Python: `C:\Users\ari30\miniforge3\envs\mfa\python.exe`
- MFA conda: `C:\Users\ari30\miniforge3`
- 현재 생산 모델: Korean MFA acoustic v3.3.0 + Jamo G2P v3.2.0
- 경로: `config/paths.json`과 `scripts/python/paths.py`
- Bareun 비밀: 프로젝트 밖 `C:\Users\ari30\Documents\Codex\_secrets\bareun`

## 불변 안전 규칙

1. `D:\00_RAW` 원자료를 수정하지 않는다.
2. 2020–2025를 같은 r2 계약으로 새로 정렬한다. 구 2020/2021을 최종으로
   재사용하지 않는다.
3. 장시간 작업은 연도·shard checkpoint와 manifest로 재개 가능해야 한다.
4. partial, 실패 DB, 로그를 자동 삭제하거나 full-clean 재실행하지 않는다.
5. 승인 제외 후보를 자동 승인하지 않는다.
6. D: 배치 중에는 다른 D: 대량 I/O를 겹치지 않는다.
7. 상태는 기억이 아니라 manifest·보고서를 읽어 확인한다.
8. 사용자가 실행할 명령은 저장소의 단일 목적 wrapper로 제공한다.
9. 방법·출력 계약이 바뀌지 않는 한 새 파일럿·외부 설계 리뷰를 열지 않는다.
10. 결정과 오류·수정 근거를 `docs/decisions`, 리뷰 조치를 `docs/reviews`,
    시간 이력을 `docs/WORK_HISTORY_*.md`에 남긴다.

## 동결 출력

- TextGrid 6-tier:
  `words / phones_mfa / phoneme_r_auto / utterance / utterance_orth_r /
  morph_analysis_utt`
- pre-MFA `morph_search.v3`: 연도별 7표
- post-MFA: 연도별 gzip 4표
- 최종 점검 슬라이드:
  `outputs/presentations/MFA_research_infrastructure_final_prebulk_20260801.pptx`

스크립트 역할은 `scripts/SCRIPTS_INDEX.md`, 결정 상태는
`docs/decisions/_INDEX.md`를 사용한다.
