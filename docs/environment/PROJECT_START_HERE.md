# 프로젝트 시작 안내 — 현재 정본

최종 갱신: 2026-08-03 KST

이 저장소에서 새 작업을 시작할 때는 아래 문서만 순서대로 읽는다.

1. [PROJECT_CURRENT_STATE.md](PROJECT_CURRENT_STATE.md) — 지금 완료된 것과 다음 한 단계
2. [../RUNBOOK_production_2020_2025.md](../RUNBOOK_production_2020_2025.md) — 전수 생산의 유일한 실행 절차
3. [../ASSETS_LEDGER.md](../ASSETS_LEDGER.md) — D:/E:/저장소 자산의 현재 위치
4. [../decisions/_INDEX.md](../decisions/_INDEX.md) — 현행 방법론 결정과 역사 기록의 구분

프로젝트 root는 다음이다.

```text
C:\Users\ari30\research\2026_summer_research
```

## 연구 흐름

```text
동결 CSV·형태소/Roman 검색층
  → 공통 Jamo r2로 2020–2025 전부 MFA 신규 정렬
  → 6-tier TextGrid와 연도별 동반 CSV/Parquet
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
- pre-MFA 검색층은 연도별 7표, post-MFA 동반층은 연도별 4표다.
- CSV, 원 WAV/JSON, 공통사전 r2, 입력·승인·제외·모델 계약은 D: 또는 저장소에
  유지한다. 구 산출물은 E: 검증 archive로 이동한다.
- 새 파일럿이나 과거 검토를 반복하지 않는다. 생산 계약 자체가 바뀔 때만 새
  설계 검토를 연다.
- 2020 MFA 계산은 끝났고 결합 제외 2,250건도 승인됐다. 현재는
  `resume_2020_export_after_post_mfa_review.ps1`로 보존 DB의 6-tier·동반표
  export부터 재개한다. 구 2020 MFA 시작 명령은 다시 실행하지 않는다.

## 문서 사용 규칙

- 현재 실행 명령은 `RUNBOOK_production_2020_2025.md`만 따른다.
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
