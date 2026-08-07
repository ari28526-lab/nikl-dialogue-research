# 프로젝트 시작 안내 — 현재 정본

최종 갱신: 2026-08-07 KST

> **현재 안전 정지점:** 공통발음 r2는 규칙 예상 발음층이 MFA 입력 사전에
> 배선되지 않은 문제가 확인되어 새 실행이 차단됐다. 기존 2020–2022 결과는
> 보존하되 정본으로 승격하지 않는다. r3 단일 발음 선택 계약 채택 전에는 MFA
> 장시간 명령을 실행하지 않는다.

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
  → 규칙·사전·형태소 근거와 MFA phone을 잇는 단일 r3 발음 선택표
  → 채택된 r3로 2020–2025 전부 MFA 신규 정렬
  → 6-tier TextGrid와 연도별 동반 CSV/Parquet
  → 우리말샘 후보·규칙 예상형·MFA phone을 분리한 발음 참조표와 파생 7번째 tier
  → 형태소·표기상 환경으로 후보 검색 및 WAV·TextGrid 수집
  → 선별 자료에 KOINA·이어붙이기·wav2vec2 보조층
  → 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA/G2P phone은 분절 인프라이지 실제 발음 판정값이 아니다. 형태소 정보도
검색·연결 정보이며 음향적 형태소 경계를 자동 주장하지 않는다.

## 현재 생산 계약

- acoustic phone inventory는 Korean MFA v3.3.0 기준으로 동결한다. 기존
  `common_pron_mfa_r2_20260728`은 보존 증거이며 새 실행에는 쓰지 않는다.
- 2020–2025는 채택될 단일 r3 발음 선택 계약으로 모두 다시 정렬한다.
- TextGrid 정본 형식은 6-tier다:
  `words / phones_mfa / phoneme_r_auto / utterance / utterance_orth_r /
  morph_analysis_utt`.
- 사전 발음 참조가 필요한 파생본에는 기존 6-tier를 그대로 보존하고 발화 수준
  `pron_reference_utt`를 7번째 tier로 추가한다. 상세 1:N 사전 후보와 품사·의미는
  동반 CSV가 정본이며 사전 발음에 가짜 음소 시간경계를 만들지 않는다.
- pre-MFA 검색층은 연도별 7표, post-MFA 동반층은 연도별 4표다.
- CSV, 원 WAV/JSON, 공통사전 r2 증거, 입력·승인·제외·모델 계약은 D: 또는 저장소에
  유지한다. 구 산출물은 E: 검증 archive로 이동한다.
- 과거 광범위 검토를 반복하지 않는다. r3는 이미 검토한 문제 발화와 음운현상별
  자동 회귀 표본만 통과시키고, 새 대규모 사람 파일럿은 만들지 않는다.
- 2020 r2 계산·6-tier·동반표·독립 감사·24표본 Gate B는 완료된 역사적 근거다.
  r3 채택 뒤 사람 검토는 재사용하되 정렬 계산은 같은 6개년 계약을 위해 다시 한다.
- 2021 r2 MFA·6-tier·동반표·독립 전수 감사와 연구자 24/24 검토, 7-tier
  1,371,883개 검증까지 완료돼 비교·회귀 자료로 보존한다.
- 2022 r2 MFA·6-tier·동반표·독립 기계 QC와 24표본 검토까지 완료됐고, 그
  표본이 공통 발음 입력 배선 공백을 발견했다. 현재는 새 청취 검토가 아니라 r3
  canonical 선택표와 사전 projection을 구현하는 단계다.

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
