# 프로젝트 시작 안내 — 현재 정본

최종 갱신: 2026-08-08 KST

> **현재 안전 정지점:** 공통발음 r2는 규칙 예상 발음층이 MFA 입력 사전에
> 배선되지 않은 문제가 확인되어 새 실행이 차단됐다. 기존 2020–2022 결과는
> 보존하되 정본으로 승격하지 않는다. r3 단일 발음 선택 계약 채택 전에는 MFA
> 장시간 MFA 명령을 실행하지 않는다. r3 G2P 후보 310,605개 생성과 독립
> 규칙 Roman 전수 비교는 완료됐으나 exact 대상은 96,284개뿐이다. 이 출력은
> 자동 채택하지 않는다. mismatch 214,321개의 전수 편집 진단과 독립 감사도
> 완료됐으며, 60.310%의 출현은 길이·활음 표상 동등성 후보, 38.447%는 실질
> 규칙 차이 후보다. 둘 다 별도 canonical 선택·adoption Gate 전에는 MFA 사전이 아니다.
> 이후 좁은 model 단위화 관계와 exact 문맥 donor projection을 전수 적용해
> target 264,906개(85.287%)에 후보를 마련했고 45,699개는 근거 부족으로
> 보류했다. 독립 감사까지 통과했지만 이 후보도 아직 최종 선택이 아니다.
> 전역 donor 재검증 뒤 남은 no-rule 85,504형도 전수 특성화했다. 후속 규칙·
> phone coverage 감사에서 36,568형은 모든 변이가 수의적 위치동화로만 달랐고,
> 별도 811형은 frozen 기본사전과 정확히 일치했으며, 48,043형은 계속 보류됐다.
> 위치동화를 의무 표준발음 규칙에 추가하지 않았고 어떤 후보도 아직 채택하지
> 않았다. 다음 단계는 검증된 37,379형을 정렬용 candidate-only로 readiness에
> 추가하는 것이다.

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
  → 2020–2022 동등 단위 증명 재사용·변경 단위 재정렬, 2023–2025 최초 정렬
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
- 2020–2022는 채택될 r3와 발음 변이 집합이 달라진 화자/세션 적응 단위만 다시
  정렬하고, 완전히 같은 단위는 동등성 증명과 최종 index를 붙여 재사용한다.
  2023–2025는 같은 r3 계약으로 한 번만 정렬한다.
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
  r3 채택 뒤 사람 검토는 재사용하고, 적응 단위의 발음 변이 집합이 달라진
  부분만 r3로 재정렬한다. 동등 단위는 계약·경계 동등성 증거와 함께 재사용한다.
- 2021 r2 MFA·6-tier·동반표·독립 전수 감사와 연구자 24/24 검토, 7-tier
  1,371,883개 검증까지 완료돼 비교·회귀 자료로 보존한다.
- 2022 r2 MFA·6-tier·동반표·독립 기계 QC와 24표본 검토까지 완료됐고, 그
  표본이 공통 발음 입력 배선 공백을 발견했다. 현재는 새 청취 검토가 아니라 r3
  canonical 선택표와 사전 projection을 구현하는 단계다.
- r3 G2P 후보–규칙 목표 전수 비교는 대상형 exact 96,284개(30.999%), mismatch
  214,321개(69.001%)다. 사전 근거까지 일치하는 source 3,078형만 후속 선택
  우선 후보이며, 나머지 exact·mismatch는 근거별 보류 경로를 유지한다.
- mismatch 전수 진단은 2,625개 반복 패턴을 만들고, 불일치 출현의 92.620%를
  포괄하는 56행 결정표로 축약했다. 현재 사람 청취가 필요한 단계는 아니며,
  자동 동등성 승인·canonical 선택·adoption은 모두 `false`다.
- model 단위화·exact 문맥 projection 후보는 target 264,906개·출현
  3,744,243회에 마련됐다. 잔여 45,699개·728,649회는 임의 fallback 없이
  보류했고 56행 handoff가 95.136%를 포괄한다. 다음 단계는 이 표를 전부
  청취하는 일이 아니라 canonical 선택 우선순위·zero-fallback·adoption Gate를
  구현하는 것이다.
- canonical exact donor를 96,284형에서 382,891형으로 확장한 전역 projection과
  독립 감사를 완료했다. 새 후보 13,172형을 얻고, 전역 변이가 드러난 기존 후보
  10,799형은 보류로 되돌렸다. 갱신된 881,237형 readiness는 candidate 준비
  752,270형(출현 26,197,593회), zero-fallback 보류 128,932형이다.
- 같은 Jamo G2P를 반복하지 않는다. no-rule 85,504형의 규칙·phone coverage
  감사와 독립 재계산까지 완료했다. 수의적 위치동화 36,568형은 정렬용 변이일 뿐
  의무 표준발음 규칙이 아니며, 비중복 frozen 기본사전 정확 일치 811형도 표준
  발음의 정답으로 간주하지 않는다. 이 37,379형만 candidate-only readiness에
  추가할 수 있고, 일부 변이만 해당하는 82형과 미해결 48,043형은 보류한다.
  비일대일 phone 표지만으로는 후보를 승격하지 않는다. adoption 전 MFA·TextGrid
  변경은 금지한다.

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
