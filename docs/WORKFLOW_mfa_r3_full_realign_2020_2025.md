# 2020–2025 공통발음 r3 전수 재정렬 workflow

최종 갱신: 2026-08-13 KST
상태: 구현·생산 정본; 2020–2023 완료, 다음은 2023→2024 전환 Gate

## 1. 목표와 범위

연구 인프라의 최종 강제정렬본은 2020–2025 모두 같은 공통발음 r3, Korean MFA
v3.3.0 acoustic phone inventory, TextGrid 6-tier schema를 사용한다. 기존 r2
DB·TextGrid는 비교 증거로 보존하지만 최종 r3에 섞지 않는다.

현재 단계적 발음 범위는 모든 관측 어휘가 아니라 **pronunciation-safe body**다.

| 연도 | 원 발화 | r3 safe body | follow-up |
|---:|---:|---:|---:|
| 2020 | 870,437 | 784,390 | 86,047 |
| 2021 | 1,373,920 | 1,208,236 | 165,684 |
| 2022 | 866,359 | 752,591 | 113,768 |
| 2023 | 677,262 | 582,389 | 94,873 |
| 2024 | 728,257 | 595,743 | 132,514 |
| 2025 | 587,121 | 461,643 | 125,478 |
| 합계 | 5,103,356 | 4,384,992 | 718,364 |

follow-up은 실패·폐기가 아니다. 발음 후보가 아직 불충분한 발화를 exact ID와
근거를 유지해 후속 release에서 처리하는 별도 shard다.

여기서 `safe body`는 Stage 19의 **발음 coverage 기준 safe body**다. 이는 r3
전수 정렬의 대상 pool이지 4,384,992건 모두가 물리적으로 정렬 가능하다는
뜻은 아니다. 과거
pre-MFA 음원·CSV 대응 감사에서 사용한 “안전 본체 4,120,627”과 이름은 비슷하지만
정의와 분모가 다르므로 서로 대체하지 않는다. 연도 입력 계약에서는
`pron_safe_body`, `pre_mfa_exclusion`, `post_mfa_unaligned`, `analysis_only`를
별도 열과 별도 수량으로 보존한 뒤 실제 MFA 입력 ID의 교집합을 명시한다.

```text
전체 source = pronunciation-safe pool + pronunciation follow-up
pronunciation-safe pool = MFA 입력 + pre-MFA 기술 제외
MFA 입력 = r3 정렬 성공 + post-MFA 기술 미정렬
```

따라서 “safe-body 전수 r3 정렬”은 **정렬 가능한 safe-body를 r2 재사용 없이 모두
새로 정렬하고, 정렬 불가능 exact ID는 숨기지 않고 별도 보존한다**는 뜻이다.

## 2. 거시 workflow

```text
G0 이미 완료된 공통 근거 동결
  → G1 연구자 승인 ledger
  → G2 거시·미시 workflow와 구현 gap 동결
  → G3 외부 workflow/code review
  → G4 staged r3 release·adoption·전용 runner 구현
  → G5 독립 adoption 감사·PowerShell 5.1 검사
  → 2020 preflight
  → 2020 전수 r3 MFA·export·감사·확정
  → 2021 전수 r3 MFA·export·감사·확정
  → 2022 → 2023 → 2024 → 2025
  → 6개년 같은-contract 교차 감사
  → follow-up 별도 개선·정렬
```

2020부터 순서대로 확정한다. 다음 연도는 직전 연도의 hard audit가 통과하고
completion manifest가 생성된 뒤에만 시작한다. 그러나 국소 오류 때문에 같은
연도의 이미 완료된 계산을 자동 `--clean`으로 지우지 않는다.

## 3. 전역에서 한 번만 하는 일

다음 산출물은 입력 fingerprint가 바뀌지 않는 한 다시 만들지 않는다.

| 단계 | 동결 산출물 | 재실행 조건 |
|---|---|---|
| Stage 01–18 | 881,237형 canonical·readiness v4 | source 또는 발음 정책 변경 |
| Stage 19 | 5,103,356발화 safe/follow-up 라우팅 | pre-MFA master 또는 tokenizer 변경 |
| Stage 20 | 795,804형·796,061변이 후보 사전 | readiness 또는 acoustic inventory 변경 |
| Stage 21 | 2022 표적 네 발화 회귀 | 사전·acoustic·MFA 설정 변경 |
| 연구자 Gate | 네 경계·단계적 범위 승인 | 승인 범위 자체가 변경될 때만 |

완료 manifest와 독립 감사 SHA가 모두 맞으면 stage를 건너뛴다. 단순히 날짜나
실행 프로세스가 달라졌다는 이유로 재실행하지 않는다.

## 4. 연도별 미시 workflow

### Y00 — 연도 진입 확인

- 직전 연도 completion manifest 확인
- 실행 중 lock·중복 MFA process 확인
- D: volume label·여유 공간 확인
- r3 release/adoption/dictionary/acoustic SHA 확인
- 해당 연도 기존 r3 output이 있으면 계약 ID부터 비교

출력을 보지 않고 다시 시작하는 행위와 자동 stale 삭제를 금지한다.

### Y01 — 연도 입력 계약

동결 pre-MFA master를 다시 형태소 분석하거나 G2P하지 않는다. Stage 19의 blocked
exact-ID 집합을 빼서 safe body ID 목록을 만든다. 다음 식을 반드시 만족한다.

```text
source utterances = safe body utterances + follow-up utterances
intersection(safe, follow-up) = 0
unknown utterances = 0
```

계약에는 source CSV fingerprint, 실제 LAB tokenizer 버전, safe/follow-up 목록
SHA, r3 adoption contract ID를 기록한다. 숫자·기호는 원 표기를 잃지 않고
`original_token / normalized_spoken_form / normalization_type / source / status`로
분리한다. 예를 들어 `2→둘` 같은 변환은 빈 발음칸을 메우기 위한 숨은 치환이
아니라 출처와 규칙을 추적할 수 있는 별도 정규화 기록이어야 한다.

### Y02 — MFA corpus 물질화

- 원 WAV·JSON·검색 CSV는 수정하지 않는다.
- 2020은 승인된 WAV-ID recovered corpus를 사용한다.
- safe body의 WAV와 LAB만 release별 새 corpus root에 준비한다.
- LAB text는 동결 `pron_reference_form` tokenizer의 byte-equivalent 결과여야 한다.
- 세션·발화 수, WAV duration, 빈 LAB, `<=44B`, 중복 ID를 전수 확인한다.

오류 발화는 exact ID와 원인을 follow-up 보충표에 넣으며 다른 발화를 막지 않는다.

### Y03 — 생산 preflight

MFA를 시작하지 않는 읽기 전용 검사다.

- release·adoption·dictionary·acoustic·G2P model fingerprint
- year input contract와 승인 제외/follow-up 회계
- corpus 세션 구조와 화자 단위
- 이전 r2 DB/output과 다른 새 r3 output root
- checkpoint/lock 소유권
- 저장공간·절전 방지·PowerShell 5.1 runtime
- repository tests와 target script `-PreflightOnly`

한 항목이라도 hard failure면 MFA를 시작하지 않는다.

### Y04 — MFA 계산과 DB 보존

- 연도마다 하나의 동결 alignment contract ID를 사용한다.
- output/temp/DB/log는 release ID와 연도를 경로에 포함한다.
- 중단 시 같은 DB와 checkpoint에서 재개한다.
- 자동 `--clean`, 기존 DB 덮어쓰기, r2 marker 재사용을 금지한다.
- heartbeat·dashboard 쓰기 실패는 재시도하고 MFA process를 종료하지 않는다.

개별 파일 오류와 전체 프로세스 실패를 구분한다. 개별 오류는 exact-ID
reconciliation으로 넘기고, 실행 중단은 DB 상태를 검사한 뒤 같은 단계에서
재개한다.

### Y05 — post-MFA exact-ID 회계

MFA DB의 정렬 성공·미정렬·누락을 year input contract와 전수 대조한다.

- 성공: TextGrid export 대상
- 기술 미정렬: 원 WAV/LAB/DB를 보존한 follow-up exact ID
- 입력에 없던 DB 발화 또는 중복: hard failure

미정렬 몇 건 때문에 성공 DB를 버리거나 연도를 재정렬하지 않는다.

### Y06 — 연구용 6-tier TextGrid export

새 r3 DB에서만 다음 tier를 생성한다.

```text
words
phones_mfa
phoneme_r_auto
utterance
utterance_orth_r
morph_analysis_utt
```

모든 tier는 `0–xmax`를 연속적으로 덮으며 앞뒤 빈 interval을 보존한다.
`phones_mfa`는 MFA 입력 후보에 따른 시간 정렬층이고 실제 실현 정답이 아니다.
`phoneme_r_auto`는 `phones_mfa`의 결정론적 넓은 Roman 대응이며 기저형 복원이
아니다. 형태소 tier는 발화 수준 검색 정보이며 음향적 형태소 경계를 주장하지
않는다.

export는 DB 계산과 분리한다. tier 이름·경계·검색 label 문제는 DB를 다시 돌리지
않고 Y06부터 재생성한다.

### Y07 — 동반 CSV/Parquet

TextGrid와 `utt_id`로 직접 연결되는 정본 동반표를 만든다.

- utterance index와 WAV/TextGrid/source CSV 경로
- word interval과 표기·철자 Roman·규칙 발음 Roman
- phone interval과 `phoneme_r_auto`
- 발화 수준 형태소/POS 분석
- 사전 1:N 발음 후보·품사·의미·출처
- 숫자·기호 원문, 발음용 정규화형, 변환 유형·근거·미해결 상태
- safe/follow-up·audio/alignment 품질 상태
- release/adoption/alignment/TextGrid contract ID

사전 발음에 가짜 시간경계를 만들지 않는다. 사전 상세 정보는 동반표가 정본이다.
CSV 문제는 Y07만 다시 실행한다.

### Y08 — 독립 전수 감사

생성기와 다른 코드 경로로 다음을 다시 센다.

- year input, DB, TextGrid, 동반표 exact-ID coverage
- safe + follow-up = source, 교집합 0
- tier 6개, 0–xmax 연속, word–phone containment
- phone inventory 밖 label·`spn`·빈 필수 label
- TextGrid–동반표 interval/label 동등성
- 모든 산출물의 같은 r3 contract ID·dictionary SHA
- `.partial`, 임시 canonical, r2 final 경로 혼입 0

### Y09 — 표본과 연도 확정

2022 네 발화 표적 회귀는 이미 승인됐으므로 다시 하지 않는다. 2020 r3는 첫
생산 연도이므로 deterministic infrastructure sample을 한 번 만들되, 기존 r2
광범위 파일럿을 반복하지 않는다. 2021–2025도 같은 표본 패키지를 자동 생성하되
사람 검토를 매년 의무화할지, 자동 전수 감사의 flag가 있을 때만 요구할지는 외부
리뷰에서 최종 결정한다.

연도 completion manifest에는 입력·사전·DB·TextGrid·동반표·감사 SHA와 성공·
미정렬·follow-up 수를 기록한다. 이 manifest가 있어야 다음 연도에 진입한다.

### Y10 — 다음 연도 Gate

직전 연도 hard failure 0, contract identity 일치, completion manifest 유효,
현재 연도 lock 없음일 때만 다음 연도를 시작한다. 연도별 output과 DB는 서로
덮어쓰지 않는다.

## 5. 오류별 재처리 범위

| 문제 | 다시 하는 범위 | 다시 하지 않는 것 |
|---|---|---|
| 공통 사전·phone inventory·acoustic 모델 변경 | 새 contract의 영향 연도 MFA | 원 CSV·형태소 분석 |
| pre-MFA tokenizer·safe/follow-up 분류 오류 | Y01–Y10 | Stage 01–18의 근거가 같다면 그 단계 |
| 숫자·기호 정규화 누락·오류 | Y01부터 영향 ID·완전 적응 단위 | 무관한 연도·세션, 원 표기 |
| 일부 WAV 누락·손상·ID 불일치 | 해당 exact ID/세션 corpus와 follow-up | 다른 세션 MFA |
| MFA process 중단 | 보존 DB/checkpoint에서 Y04 재개 | 연도 `--clean` 재시작 |
| 일부 정렬 미생성 | Y05 follow-up 이관 | 성공한 DB 정렬 |
| TextGrid tier·바깥 경계·label 오류 | Y06–Y09 | MFA 계산·DB |
| 동반 CSV 열·조인·Roman 오류 | Y07–Y09 | MFA·TextGrid, 시간값 |
| 국소 발음형 오류 | 새 point contract + token→세션 영향 단위 | 영향 없는 r3 세션 |
| heartbeat/dashboard 파일 잠금 | sidecar 재시도 | MFA process |
| 용량 부족 | 안전 정지·archive 확인 뒤 같은 checkpoint 재개 | 검증된 결과 삭제·자동 clean |

국소 발음 수정도 phone label을 기존 TextGrid에 덮어쓰지 않는다. 영향받은 완전한
MFA 적응 단위를 새 DB에서 재정렬하고 최종 index를 갱신한다.

## 6. 반복 방지 장치

모든 stage manifest는 다음을 가져야 한다.

- `schema_version`, `status`, `contract_id`, `git_commit`
- 입력 path·bytes·mtime·SHA-256
- 출력 path·행/파일 수·bytes·SHA-256
- 시작/완료 시각과 실행 인자
- 이전 checkpoint 재사용 여부와 근거
- 실패 시 마지막 완결 단위와 partial 경로

재호출 시 manifest와 실물이 일치하면 `unchanged/resume`로 종료한다. 불일치하면
기존 결과를 덮어쓰지 않고 새 partial 또는 새 point release로 격리한다.

## 7. 현재 구현·생산 상태

외부 workflow 검토 뒤 staged r3 release/adoption builder, 독립 validator, 연도별
exact-ID 계약 builder, r3 전용 preflight·runner·dashboard, direct-DB 6-tier
exporter, 독립 전수 QC와 전환 Gate를 구현했다. r2 신규 실행은 fail-closed이며
`common_pron_mfa_r3_20260809`만 production Gate에서 채택됐다.

2020–2023은 Y01–Y10을 다음 수량으로 완료했다.

| 연도 | r3 입력 | 정렬 성공 | 승인 후속 | 6-tier | 독립 QC |
|---:|---:|---:|---:|---:|---|
| 2020 | 782,715 | 782,432 | 283 | 782,432 | passed, DB 표본 24/24 |
| 2021 | 1,207,299 | 1,206,862 | 437 | 1,206,862 | passed, DB 표본 24/24 |
| 2022 | 751,721 | 751,383 | 338 | 751,383 | passed, DB 표본 24/24 |
| 2023 | 494,580 | 494,228 | 352 | 494,228 | passed, DB 표본 24/24 |

이 네 연도의 MFA·전수 수출·QC를 반복하지 않는다. 현재 다음 단계는 2023 marker·
DB·QC state SHA를 검증하는 2023→2024 전환 Gate다. Gate가 통과한 뒤 2024 한
연도만 같은 순서로 준비하며 2020–2023 완료본을 입력이나 임시 폴더로 재사용하지
않는다.
