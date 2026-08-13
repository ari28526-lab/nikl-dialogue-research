# 프로젝트 시작 안내 — 현재 정본

최종 갱신: 2026-08-13 KST

> **현재 생산 진입점:** 2020·2021·2022·2023은 동일
> `common_pron_mfa_r3_20260809` 계약으로 신규 정렬, post-MFA exact-ID 회계,
> 6-tier·동반표 수출과 독립 전수 QC까지 완료해 SHA를 동결했다. 2023은 입력
> 494,580 중 494,228 정렬, 승인 기술 미정렬 352이며 DB 재수출 표본은
> semantic·byte 24/24다. D: 여유는 48.604 GiB이므로 **다음 한 단계는 삭제 없는
> 2020–2023 r3 temp 용량 inventory**다. DB·최종 6-tier를 보존한 정리와 2024
> capacity Gate가 끝난 뒤 2023→2024 전환 Gate를 연다. 2020–2023 MFA·전수
> 수출·QC, Stage 01–21, D: 원자료, r2 완성본과 광범위 파일럿은 다시 실행하지
> 않는다.

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
