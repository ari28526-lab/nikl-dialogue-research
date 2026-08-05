# 프로젝트 시작 안내 — 현재 정본

최종 갱신: 2026-08-05 KST

이 저장소에서 새 작업을 시작할 때는 아래 문서만 순서대로 읽는다.

1. [PROJECT_CURRENT_STATE.md](PROJECT_CURRENT_STATE.md) — 지금 완료된 것과 다음 한 단계
2. [../RUNBOOK_production_2020_2025.md](../RUNBOOK_production_2020_2025.md) — 전수 생산의 유일한 실행 절차
3. [../RUNBOOK_pronunciation_reference_layer_2020_2025.md](../RUNBOOK_pronunciation_reference_layer_2020_2025.md) — 사전 발음 참조표·7번째 파생 tier의 실행 절차
4. [../ASSETS_LEDGER.md](../ASSETS_LEDGER.md) — D:/E:/저장소 자산의 현재 위치
5. [../decisions/_INDEX.md](../decisions/_INDEX.md) — 현행 방법론 결정과 역사 기록의 구분

Codex 리밋, 앱 종료, 계정 재로그인 또는 새 대화 뒤에는
[CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md](CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md)를
추가로 읽고, 실행 중인 로컬 작업을 재시작하기 전에 상태판을 확인한다. 새 계정을
만드는 절차가 아니다.

프로젝트 root는 다음이다.

```text
C:\Users\ari30\research\2026_summer_research
```

## 연구 흐름

```text
동결 CSV·형태소/Roman 검색층
  → 공통 Jamo r2로 2020–2025 전부 MFA 신규 정렬
  → 6-tier TextGrid와 연도별 동반 CSV/Parquet
  → 우리말샘 후보·규칙 예상형·MFA phone을 분리한 발음 참조표와 파생 7번째 tier
  → 형태소·표기상 환경으로 후보 검색 및 WAV·TextGrid 수집
  → 선별 자료에 KOINA·이어붙이기·wav2vec2 보조층
  → 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA/G2P phone은 분절 인프라이지 실제 발음 판정값이 아니다. 형태소 정보도
검색·연결 정보이며 음향적 형태소 경계를 자동 주장하지 않는다.

## 현재 생산 계약

- 2020–2025 모두 같은 Korean MFA acoustic v3.3.0, Jamo G2P v3.2.0,
  `common_pron_mfa_r2_20260728`로 다시 정렬한다.
- TextGrid 정본 형식은 6-tier다:
  `words / phones_mfa / phoneme_r_auto / utterance / utterance_orth_r /
  morph_analysis_utt`.
- 사전 발음 참조가 필요한 파생본에는 기존 6-tier를 그대로 보존하고 발화 수준
  `pron_reference_utt`를 7번째 tier로 추가한다. 상세 1:N 사전 후보와 품사·의미는
  동반 CSV가 정본이며 사전 발음에 가짜 음소 시간경계를 만들지 않는다.
- pre-MFA 검색층은 연도별 7표, post-MFA 동반층은 연도별 4표다.
- CSV, 원 WAV/JSON, 공통사전 r2, 입력·승인·제외·모델 계약은 D: 또는 저장소에
  유지한다. 구 산출물은 E: 검증 archive로 이동한다.
- 새 파일럿이나 과거 검토를 반복하지 않는다. 생산 계약 자체가 바뀔 때만 새
  설계 검토를 연다.
- 2020은 신규 MFA, 6-tier·동반표 export, 독립 전수 감사, 24개 생산 표본 연구자
  확인 및 Gate B까지 완료됐다. Gate B는 16/16 core check, 실패 0으로
  `passed`다. 구 2020 MFA·export 명령은 다시 실행하지 않는다.
- 2021은 신규 MFA·6-tier·동반표·독립 전수 감사까지 완료됐고 연구자가 20개
  표본의 연결·분절을 확인했다. 이 검토에서 확인된 사전 발음 배선 공백은
  2020–2025 공통 파생 레이어로 교정했으며 2020·2021 정규화 표가 전수 검증됐다.
  다음은 2021 7-tier 전수 파생·독립 검증이며 2022 MFA는 아직 시작하지 않았다.

## 문서 사용 규칙

- MFA·6-tier 생산 명령은 `RUNBOOK_production_2020_2025.md`, 사전 발음
  참조표·7번째 파생 tier 명령은
  `RUNBOOK_pronunciation_reference_layer_2020_2025.md`만 따른다.
- `docs/archive`, `docs/reviews`, `WORK_HISTORY_*`, 구 `PLAN/RUNBOOK/MONITOR/PILOT`
  문서는 오류·시행착오·방법론 근거다. 현재 다음 단계로 해석하지 않는다.
- 현재 상태 문서는 누적 일지가 아니다. 상태가 바뀌면 짧게 교체하고, 상세 과정은
  `WORK_HISTORY_2026-08.md`에 남긴다.
- 대량 파일 이동·삭제는 archive manifest, 파일 수·바이트, CRC/SHA 검증 뒤에만
  수행한다.

## 환경

- 파이프라인 Python: `C:\Users\ari30\miniforge3\envs\mfa\python.exe`
- MFA conda: `C:\Users\ari30\miniforge3\Scripts\conda.exe`
- R: `C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe`
- Quarto: `C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd`
- Bareun secret은 프로젝트 밖 `C:\Users\ari30\Documents\Codex\_secrets\bareun`
  에만 둔다.

제한된 Codex shell에서 AppData Python이 보이지 않는 결과만으로 설치 부재를
판정하지 않는다. 필요하면 `scripts/check_python_environment.ps1`로 확인한다.
