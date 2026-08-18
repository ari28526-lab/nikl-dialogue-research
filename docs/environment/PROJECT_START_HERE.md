# 프로젝트 시작 안내 — 현재 정본

최종 갱신: 2026-08-18 KST

> **현재 진입점 — 2026-08-18 RC1 이후 우선순위 재설정·active view 완료:**
> curated 16건의 형태소·phone enrichment를 지금 별도 장기 단계로 만들지 않는다.
> RC0는 5,103,356발화의 기본값, RC1 curated exact-ID 16건만 우선하는 exception
> 계약을 생성했고 독립 감사가 통과했다. 예외표는 55행뿐이며 전체 base 복사 0,
> curated 16, base 보존 39다. 다음은 이 precedence를 사용하는 범용 target
> query/manifest의 작은 검증이며 실제 음성 실현을 자동 판정하지 않는다.

> **현재 진입점 — 2026-08-18 DB v1 RC1 recovery sidecar 채택 완료:**
> 연구자 승인 SHA에 결속해 D7–D10 exact-ID 55건의 후속 상태와 D10 수동
> word·전사 16건의 curated snapshot/active pointer를 RC0 불변 sidecar로
> 채택했다. 독립 감사가 55/55·16/16, RC0 5,103,356행, 잔여 recovery
> 817,255건 회계를 통과했다. D9 phone은 참고 전용이고 형태소·phoneme은 보완
> 대기다. RC0·r3·최종 6-tier·TextGrid 변경과 MFA는 0건이다. 이 기록의 다음
> 단계는 위 우선순위 재설정으로 대체됐다.

> **현재 진입점 — 2026-08-18 D10 연구자 반환 16건 동결 완료·채택 전:**
> Dropbox에서 수정한 TextGrid 16/16을 회수해 D:의 별도
> `D10_RESEARCHER_RETURN_0001`에 raw 사본 16개와 정규화본 16개로 동결했다.
> 1–4번은 잘못 선택된 작업 tier 위치만 기계 교정했고, 나머지 수동 label·경계와
> 연구자 수정 전사 5건, 분절 차이 1건은 그대로 보존했다. 길이·전구간 경계·D9
> 참고 tier 불변성 감사가 통과했다. 원본·r3·6-tier·DB v1 변경과 MFA는 0건이다.
> 다음은 `docs/decisions/RESULT_db_v1_recovery_D10_researcher_return_20260818.md`를
> 따라 exact-ID 수동 word overlay의 별도 adoption Gate를 설계하는 것이다.

> **현재 진입점 — 2026-08-18 D10 격리 수동 작업본 생성 완료:** D9에서
> 수정 전사·수동 overlay 대상으로 판정한 16 exact ID만 D:의 별도
> `D10_MANUAL_OVERLAY_0001`에 번호순으로 materialize했다. 국소 수정 9건은
> D9 word 경계를 초안으로, 전체 재정렬 6건과 단일어 1건은 빈 작업 tier로
> 시작한다. 각 수동 TextGrid는 D9 word/phone 참고, 제안 전사, 실제 수정할
> `words_manual_working`의 4-tier다. 원본·r3·최종 6-tier·DB v1은 바뀌지 않았고
> MFA도 실행하지 않았다. 다음은
> `docs/decisions/RESULT_db_v1_recovery_D10_materialization_20260818.md`를 따라
> `words_manual_working`만 수동 보정한 뒤 별도 adoption Gate를 만드는 것이다.

> **현재 진입점 — 2026-08-18 D10 수동 overlay Gate 준비 완료:** D9 부분
> 보존 16건을 국소 수정 9, 전체 수동 재정렬 6, 단일어 복구 1로 분리하고 연구자
> 청취 결과에 따른 제안 전사와 비언어음·배경음 표지를 exact ID에 결속했다.
> 기술 제외 2와 직접 승인 1은 별도 경로로 유지한다. 자동 감사가 D9 판정과
> 19/19 일치함을 확인했으며 WAV 복사·LAB/TextGrid 수정·MFA·6-tier/DB 변경은
> 0건이다. 다음은 `docs/decisions/PLAN_db_v1_recovery_D10_manual_overlay_20260818.md`
> 에 따라 16건의 격리 작업 사본만 materialize하는 별도 Gate다.

> **현재 진입점 — 2026-08-18 D9 연구자 검토 완료:** 새 TextGrid 19건을
> WAV·LAB와 한 건씩 확인해 직접 승인 1, 수정 전사·수동 overlay 16, 기술 제외
> 2로 exact-ID 판정을 닫았다. 넓은 beam의 19/19 생성은 기술 회수 성공이지만
> 18건은 실제 음성과 LAB 범위 불일치 또는 음질 문제로 그대로 사용할 수 없었다.
> 원본·r3·6-tier·DB v1 자동 변경은 0건이며 전체연도 MFA를 다시 하지 않는다.
> 다음은 `docs/decisions/RESULT_db_v1_recovery_D9_researcher_review_20260818.md`를
> 따라 16건만 별도 D10 수동 전사·TextGrid overlay 묶음으로 만드는 것이다.

> **현재 진입점 — 2026-08-17 D9 실행·검토 묶음 완료:** D8 identity 확인
> 미정렬 19건만 동일 모델·공통발음 r3·LAB을 유지하고 `beam=100`,
> `retry_beam=400`으로 한 차례 격리 재정렬해 TextGrid 19/19, 누락 0으로
> 끝났다. 이는 탐색 폭 민감성의 증거이며 자동 언어학적 채택은 아니다. 번호가
> 같은 WAV·LAB·2-tier TextGrid 검토 묶음과 독립 감사가 완성됐고 원음원 겹침
> 4건을 표시했다. r3 본체·6-tier·DB v1·원자료 변경은 0건이다. 다음은
> `docs/decisions/RESULT_db_v1_recovery_D9_completed_20260817.md`에 따라 19건만
> 검토한 뒤 별도 채택 Gate를 여는 것이다. 전체연도와 0.1초 미만 25건은 다시
> 실행하지 않는다. 개인 검토용 19세트는 승인 범위대로
> `C:\Users\ari30\Dropbox\DB_V1_RECOVERY_D9_REVIEW_19_20260817`에 복사했고
> 61개 파일의 SHA-256 전수 검증이 통과했다. 외부 공유는 설정하지 않았다.

> **현재 진입점 — 2026-08-17 D9 실행 승인·preflight 완료:** D8 identity 확인
> 잔여 19건만 `beam=100`, `retry_beam=400`으로 한 차례 재시도하는 exact-ID
> package·재개 runner·무병합 감사기를 고정했고 연구자 `ari30`의 해시 결속
> 승인을 기록했다. PowerShell 5.1 검사와 승인 포함 `-PreflightOnly`가
> `passed_ready_to_execute`로 통과했으며 D: 출력은 아직 생성하지 않았다.
> 0.1초 미만 25건, 전체연도, 기존 r3·6-tier·DB v1은 범위 밖이다. 다음은
> `docs/decisions/RESULT_db_v1_recovery_D9_gate_20260817.md`의 단일 D9 runner를
> 실행하는 것이다.

> **현재 진입점 — 2026-08-17 D8 회수 가능성 감사 완료:** D6의 계속 미정렬
> 19건은 원 JSON·동결 CSV·LAB·canonical/r3/H WAV identity를 확인해 D9의 한
> 차례 통제 parameter-retry 후보로 고정했다. 0.1초 미만 25건은 H 백업 WAV도
> r3 payload와 같고 최대 0.099875초라 같은 입력 회수 불가 기술 제외로 판정했다.
> 숫자·기호 읽기 3건은 철자 원문이 아니라 동결 MFA normalized text와 비교해
> 정상으로 보존했다. 다음은 19건만 별도 exact-ID D9 Gate로 실행하는 것이며,
> 25건·전체연도·D5 전체는 다시 실행하지 않는다. 먼저
> `docs/decisions/RESULT_db_v1_recovery_D8_feasibility_20260817.md`를 읽는다.

> **현재 진입점 — 2026-08-17 D7 부분 정렬 보존 완료:** 연구자 검토 11건은
> 모두 r3 본체 정렬 성공에서 제외했다. 진단 WAV·LAB·TextGrid는 삭제하지 않았고,
> 6건은 `partial_alignment_available`, 3건은 잡음 보존, 2건은 전사 회수·수정
> 후보로 별도 JSON·SQLite에 기록했다. 독립 감사는
> `passed_excluded_from_main_body_partial_artifacts_preserved`다. 다음 한 단계는
> MFA가 아니라 19+25건 원자료 회수 가능성 읽기 전용 감사다. 먼저
> `docs/decisions/RESULT_db_v1_recovery_D7_partial_alignment_preservation_20260817.md`와
> `docs/decisions/PLAN_after_D7_recovery_to_DB_v1_RC1_20260817.md`를 읽는다.

> **현재 진입점 — D6 사후 분기 Gate 완료:** D5 성공 11건은 한 폴더의
> WAV·LAB·2-tier TextGrid와 검토 CSV로 모았고, 미정렬 19건은 보존 DB에서
> feature 존재·word/phone interval 0임을 확인해 새 통제 진단 대상으로 남겼다.
> 0.1초 미만 25건은 24개 원 PCM 짧음·1개 PCM 없음 증거와 원 CSV 시간 경로를
> 결속하고 같은 입력 MFA를 계속 금지했다. 독립 감사 상태는
> `passed_gate_closed_pending_researcher_review_and_separate_approval`이다.
> r3 본체·6-tier·DB v1 병합은 0건이다. 다음 작업 전
> `docs/decisions/RESULT_db_v1_recovery_D6_gate_20260815.md`를 먼저 읽는다.

> **현재 진입점 — D5 격리 진단 완료:** `D5_ALIGNMENT_DIAGNOSTIC_0001` 30건을
> 승인 범위대로 격리 실행해 MFA TextGrid 11건을 회수했고 19건은 계속 미정렬이다.
> 성공·미정렬 exact-ID 합계는 누락·중복 없이 30건이다. feature-generation 실패
> 25건은 모두 0.1초 미만이라 같은 입력 MFA를 반복하지 않고 원 음원 길이 회수
> 장부에 보존했다. 상태는 `completed_diagnostic_no_merge`이며 r3 본체·연구용
> 6-tier·DB v1 자동 병합은 하지 않았다. 다음 작업 전
> `docs/decisions/RESULT_db_v1_recovery_D5_gate_20260815.md`를 먼저 읽는다.

> **현재 진입점 — D0–D4 완료:** 817,310건 reason별 recovery 장부와 기술
> 98,946건 회수 가능성 감사, 발음 85,433유형 축약, 55건 첫 진단 shard가
> 독립 감사까지 끝났다. 현재 Gate는 `passed_gate_closed`이며 실제 recovery
> 파일 생성·MFA는 시작하지 않았다. 다음 행동은
> `docs/decisions/RESULT_db_v1_recovery_D0_D4_20260815.md`를 확인하고 55건
> exact shard의 별도 실행 승인 여부를 결정하는 것이다. 기존 r3 본체나 연도별
> 전수 MFA를 다시 실행하지 않는다.

> **현재 생산 진입점:** 2020–2025 공통발음 r3 안전 본체의 신규 정렬, 연구용
> 6-tier TextGrid, 동반표 4종과 독립 전수 QC가 여섯 연도 모두 완료됐다. 2025는
> 동결 입력 458,413건을 정렬해 성공 457,611건과 연구자 승인 기술 미정렬 802건을
> exact-ID로 완전 회계했다. QC는 coverage 100%, hard failure 0, 보존 DB 재수출
> semantic·byte 24/24로 `passed`다. **현재 장시간 PowerShell 작업은 없으며,
> 2020–2025 MFA·전수 수출·QC를 다시 실행하지 않는다. 다음은 완료 state를
> 변경하지 않는 여섯 연도 교차 감사와, 본체와 분리된 pronunciation follow-up·
> 기술 제외 후속 shard의 설계·처리다.**

> **2026-08-15 D단계 용량 Gate 완료:** 연구자 승인 아래 2024–2025 QC 완료
> MFA temp에서 재생성 가능한 exact allowlist 126개(35.987 GiB)만 삭제했다.
> 2024·2025 DB SHA는 A–C 정본과 다시 일치했고 최종 6-tier·원자료·로그·모델·
> 계약·재현성 파일은 보존됐다. D: 여유는 64.184 GiB다. 다음은 대량 MFA가 아니라
> D0 입력 계약과 817,310건 이유별 recovery routing 장부다.

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
  → 2020–2025 pronunciation-safe와 정렬 가능 집합의 교집합을 동일 r3 계약으로 연도별 신규 정렬
  → 미해결 718,364발화는 exact-ID follow-up shard로 보존
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
- 2020–2025 pronunciation-safe pool 중 독립 음원·CSV·정렬 가능성 Gate를 통과한
  발화는 모두 같은 r3 사전·acoustic model·실행 설정으로 새 DB에 정렬한다.
  기술적 제외는 exact-ID로 별도 회계하고, 2020–2022 r2 interval/TextGrid는
  최종 r3에 섞지 않는다.
- follow-up 718,364발화는 어절을 부분 삭제하지 않고 exact-ID·사유·원 입력
  fingerprint를 유지한 별도 shard로 보존한다. 이는 코퍼스 전체 완료와 구분한다.
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
  사람 검토 결과는 회귀 근거로 재사용하되, 최종 r3 시간 interval은
  pronunciation-safe 중 정렬 가능 집합 전체를 새로 계산한다.
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
  발음의 정답으로 간주하지 않는다. 이 37,379형만 candidate-only readiness v2에
  추가했고, 일부 변이만 해당하는 82형과 미해결 48,043형은 보류했다.
  비일대일 phone 표지만으로는 후보를 승격하지 않는다. adoption 전 MFA·TextGrid
  변경은 금지한다.
- frozen 기본사전의 단어·음절·국소 분절·이차조음 문맥 inventory를 만들고
  readiness v2 hold 91,553형을 기존 canonical donor와 전수 대조했다. 단일 근거
  10,594형, 복수 근거 22,171형, 출처 충돌 48,780형, 근거 없음 10,008형이다.
  단일 근거 중 기존 phone·Roman을 바이트 그대로 유지하는 이차조음 onset+glide
  6,141형만 readiness v3의 candidate-only로 추가했다. v3는 candidate
  795,790형·27,043,061회, zero-fallback hold 85,412형·803,844회다. 남은
  단일 근거 4,453형도 분절 삽입·직접 치환·ㅢ 규칙이 섞여 자동 승격하지 않는다.
  Stage 15에서 이 집합의 4,900 issue를 ㅢ·활음·`ng`·종성 삽입, 후두 대립·
  비음/종성·모음·이차조음 치환, 혼합 편집으로 전수 분류하고 독립 감사를
  통과했다. Stage 16은 이 4,453형을 동결 검색 master와 연결해 exact 표면
  68,285회, 안전한 형태소·품사 문맥 60,292회를 확보했다. 비1:1 Bareun 분석은
  억지로 위치 대응하지 않았다. 후보 생성은 여전히 0형이고 4,453형 모두 hold다.
  Stage 17은 사전·규칙 exact 141형 중 실제 `pron_1/2` 등재 65형만 전체 phone열로
  재구성해 14형·200회를 candidate-only로 준비하고, legacy 기계발음 76형과
  복수·충돌 51형을 hold했다. Stage 18 readiness v4는 이 14형만 병합했으며
  candidate 795,804형, hold 85,398형이다. Stage 19는 실제 pre-MFA tokenizer로
  5,103,356발화를 전수 라우팅해 safe body 4,384,992발화와 follow-up
  718,364발화를 고정했고, Stage 20 후보 사전의 796,061변이도 독립 감사를
  통과했다. Stage 21의 기존 문제 표본 네 발화는 자동 회귀 검사와 연구자 경계
  승인 4/4를 통과했다. 단계적 safe-body와 6개년 신규 r3 정렬 범위도 승인됐다.
  r3 release·runner·exporter·독립 감사 구현, 체크리스트 1–7, 단일 production
  Gate 채택 뒤 r3 사전–CSV occurrence 연결 Gate를 추가했다. 이 계약으로
  2020–2023의 corpus·DB·6-tier·동반표·독립 QC를 완료했다. 다음 연도도 직전
  완료 SHA를 동결한 전환 Gate 뒤 한 연도만 같은 순서로 수행한다.

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

GitHub HTTPS 인증도 같은 원칙을 적용한다. 이 컴퓨터의 Git 2.52.0과 Git
Credential Manager 2.6.1, `credential.helper=manager` 설정은 정상이다. 제한된
Codex shell은 Windows Credential Manager(`wincredman`) 접근이 차단되어
`Unable to persist credentials` 또는 `SEC_E_NO_CREDENTIALS`를 낼 수 있지만,
권한 있는 shell에서는 저장된 자격증명 조회와 `git push`가 정상 동작한다.
이 결과만으로 자격증명을 삭제·재등록하거나 Git/PowerShell을 재설치하지 말고,
인증이 필요한 Git 네트워크 작업만 권한 있는 실행으로 수행한다. 사용자명·토큰은
로그나 채팅에 출력하지 않는다.
