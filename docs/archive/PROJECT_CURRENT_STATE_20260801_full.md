# 프로젝트 현재 상태 정본 (2026-08-01 workflow reset 이전 전체본)

최종 갱신: 2026-08-01 KST

## 2026-08-01 최신 정지점 — 전체 workflow 리셋 외부 리뷰 대기

- 단순 실행 순서 리뷰를 전체 workflow·반영 추적·검수 가치·archive 구조 감사로
  확대했다.
- 2020 `morph_search.v3`은 1/23 성공 상태로 정지했고 신규 r2 MFA는 미시작이다.
- 외부 리뷰 전에는 추가 파일럿, shard 2 이후, LAB 전수, MFA를 실행하지 않는다.
- 리뷰어는 결정→문서→config/schema→runner→test→실물의 반영 사슬을 감사하고,
  각 검수를 유지/통합/기계화/조건부/폐지로 판정한다.
- archive는 지금 실행하지 않는다. 기존 링크·entrypoint를 조사한 이동표와 새
  `PROJECT_CURRENT_STATE` 초안을 받은 뒤 manifest·`git mv`·link 검증으로 적용한다.

리뷰 브리프:
`docs/reviews/BRIEF_external_review_workflow_reset_20260801.md`

외부 도구 프롬프트:
`docs/reviews/PROMPT_external_review_workflow_reset_20260801.md`

## 2026-08-01 최신 정지점 — 전수 순서 외부 리뷰 대기

- 2020 `morph_search.v3` 실제 첫 shard 1/23은 성공했고 lock 없이 정상 정지했다.
- 사용자가 코드보다 전수 작업의 입력·출력·실행 순서를 먼저 외부 리뷰하기로 했다.
- 리뷰가 끝날 때까지 shard 2 이후, LAB 전수 생성, MFA 전수 실행을 시작하지 않는다.
- MFA 전에 동결해야 하는 정렬 영향 입력과, 정렬 뒤에도 재생성할 수 있는 검색·
  사전 보조 레이어를 구분한 제안서를 작성했다.
- 현재 확인된 workflow 쟁점은 `morph_search.v3`와 MFA 연도 큐가 별도 runner라는
  점이다. 연도 검색 manifest를 hard gate로 할지 동일 source contract 확인만
  요구할지 외부 리뷰에서 판정한다.

제안서:
`docs/decisions/PROPOSAL_prebulk_execution_order_20260801.md`

외부 리뷰 프롬프트:
`docs/reviews/PROMPT_external_review_prebulk_execution_order_20260801.md`

## 2026-08-01 최신 정정 — 2020 구 정렬을 다시 보지 않는다

- 2020–2025는 모두 공통 Jamo r2 기준으로 **새 MFA 정렬**한다.
- 기존 2020 TextGrid/phone을 전수 검토·승인·재사용하는 단계는 없다.
- 현재 새로 만드는 2020 전수 산출물은 정렬 전 조합검색 CSV.gz와 LAB 입력이다.
- 연구자가 확인할 수 있는 것은 새 입력에서 자동 분류된 예외 후보뿐이며,
  전수 발화나 구 정렬을 다시 보는 검토가 아니다.
- `morph_search.v3`은 철자 어절과 형태소 분석 어절 좌표를 분리하고,
  숫자·기호를 occurrence별 별도 표로 보존한다.
- 6개년 60발화 자동 회귀검사에서 42개 gzip SHA 재현성, 기호 26건 coverage,
  어절 좌표 mismatch 보존이 모두 통과했다. MFA는 실행하지 않았다.
- 다음 계산: 2020 `morph_search.v3` 신규 전수 생성 → 신규 LAB 계약 →
  r2 신규 MFA → 6-tier/TextGrid 동반표/QC.

결정 정본:
`docs/decisions/DECISION_pre_MFA_combination_search_v3_20260801.md`

회귀 근거:
`outputs/reports/EVIDENCE_morph_search_v3_regression_60_20260801.json`

이 문서는 세션 전환이나 context compaction 뒤에도 확정된 결정과 바로 다음
작업을 잃지 않기 위한 단일 상태 정본이다. 새 작업은 최근 대화만 보고
명령을 제안하지 말고 이 문서와 실제 manifest를 먼저 대조한다.

## 연구 목적

1. CSV/Parquet에서 특정 형태소 또는 표기상 음운 환경을 검색한다.
2. 해당 발화의 WAV와 TextGrid를 같은 `utt_id`로 모은다.
3. 선택 후보에 KOINA 운율 분석과 필요 시 이어붙이기를 수행한다.
4. 연구자가 음성과 TextGrid를 보고 실제 실현 여부를 별도 판정한다.

MFA/G2P phone은 대략적인 자동 정렬 보조 정보이며 실제 실현 판정값이 아니다.
우리말샘 발음, 규칙 발음, MFA phone, wav2vec2 phone, 연구자 판정을 서로
다른 열·tier·산출물로 보존한다.

## 저장장치 원칙

- `D:\`: 메인 실행·대용량 산출물 드라이브
- `E:\`: 검증된 압축 archive
- 원시 JSON/WAV와 기존 정본은 읽기 전용
- MFA와 D: 대량 archive/KOINA/stitch를 동시에 실행하지 않음
- 한 연도씩 MFA → QC → archive/정리 → 다음 연도

## 확정된 r2 방법 기준

- acoustic: Korean MFA v3.3.0
- G2P: Jamo v3.2.0, `unicode_decomposition=true`
- 공통사전 release: `common_pron_mfa_r2_20260728`
- 공통사전 SHA256:
  `24c406604c86a5df833a7e47d809f252d6fc39dc566a6d3818b3d3ffeb04fb86`
- adoption SHA256:
  `611f021bb2c051fb21cfffe9dd948f15dd980cd4c2566e29cc363f6bc6c9c081`
- acoustic SHA256:
  `94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c`
- G2P SHA256:
  `4df7c5fa90da1f401e7a44af360be56158a581a54202e38baedeca53cfed38ff`
- `spn=0`, 관측 OOV missing=0, phone inventory 이탈=0
- 27개 예외는 연구자가 권고 발음으로 승인했고 r2에 적용됨
- 2020–2025 전부를 같은 r2·acoustic·G2P·adoption으로 다시 정렬할 계획이며,
  전수 완료 전에는 완료 사실로 쓰지 않음
- 2020/2021 difference inventory는 구결과 재사용 승인이 아니라 전환 감사

## 완료 상태

### 공통사전과 adoption

- r2 final manifest: `success`
- G2P shard: 35/35, OOV 866,692
- 2020/2021 difference inventory: 완료
- researcher approval v2: 통과
- adoption v3:
  `status=passed`, `allow_yearly_mfa=true`,
  `legacy_inline_g2p_default=false`

실물:

```text
D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\
  00_contract\release_manifest.json
  00_contract\researcher_approval.json
  00_contract\adoption_contract.json
  03_equivalence\common_pron_mfa_difference_inventory_2020_2021.json
```

### E: 압축 archive와 D: 정리

archive manifest:

```text
E:\READ_ONLY_ARCHIVE\2026_summer_research\
  pre_jamo_compressed_20260728\archive_manifest.json
```

상태는 `success`이며 다섯 묶음 모두 CRC, 원 파일 수·bytes, DB SHA와 archive
SHA 검증을 통과했다. 원 약 55.883 GiB를 약 12.294 GiB archive로 보존했다.

사용자 명시 승인 뒤 아래 구 pre-Jamo/실패 산출물만 D:에서 정리했다.

```text
D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2020
D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2021
D:\mfa_tmp\2021
D:\mfa_eojeol\archive_stale_temp
D:\mfa_common_pron\models\official_hf_korean_mfa_v3.3.0_20260728
```

삭제 보고서:
`outputs/reports/PRUNE_pre_jamo_after_compressed_archive_20260730.json`

D: 사후 여유 공간은 약 323.56 GiB였다. 원시 corpus는 건드리지 않았다.

## 현재 실행 상태

### 2026-08-01 최신 상태 — 외부 리뷰 HIGH 수정·최종 회귀 진행

- r2 기준 2020–2025 전수 MFA는 **아직 시작하지 않았다**.
- 연구자가 승인한 새 기본 표시는
  `words/phones_mfa/phoneme_r_auto/utterance/utterance_orth_r/
  morph_analysis_utt` 6-tier다.
- 외부 리뷰 판정 `GO AFTER FIXES`의 HIGH 2건을 구현했다.
  승인 제외 계약 없이는 실행할 수 없고, 승인 밖 누락은 1건도 허용하지 않는다.
  6-tier 연도 전수 감사·보존 DB 표본 재수출·다음 연도 gate를 새 계약에
  배선했다.
- 기존 r2 DB에서 연도당 10발화, 총 60발화를 MFA 재실행 없이 최종 schema로
  다시 출력했다. 연도별 `utterance/word/phone/excluded` gzip 4종이다.
- duration·word·phone은 기존 4-tier와 60/60 동일했고, 혼합 표기 2건의
  `utterance_orth_r`만 의도적으로 개선했다. 다른 tier 불일치 0,
  word 479, phone 1,801, actual `spn=0`이다.
- 결정적 gzip 두 번 재생성 SHA 24/24, Parquet 24표 값·dtype·행 순서
  왕복 24/24가 통과했다. 1만 합성 발화 exporter 벤치는 최초 87.7초,
  재개 38.4초, Python 추적 메모리 정점 9.2MiB였다.
- `SARW2500000414.1.1.2`의 `2사람이`(원 1어절) →
  `두 사람이`(MFA reference 2 word) 사례를 발견해 원 형태소 어절,
  reference 어절, MFA word 좌표계를 분리했다.
- 출력 schema 실패 때 비싼 MFA까지 재실행하지 않도록
  `direct_db_ready`를 추가했다. 이는 정렬 계산 재사용 표시이지
  TextGrid 출력/분석 승인이 아니다.
- 현재 판정은 **외부 리뷰 수정 구현·소규모/합성 회귀 통과, 전체 단위시험과
  문서·commit/push 마감 중**이다. 이 마감과 2020 승인 제외 검토표 확인 전에는
  전수 MFA를 시작하지 않는다.
- 최신 설계:
  `docs/decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md`
- 외부 리뷰 결과:
  `docs/reviews/incoming/EXTERNAL_REVIEW_full_production_TextGrid_CSV_20260801.md`
- 기계 증거:
  `outputs/reports/EVIDENCE_research_6tier_post_review_20260801.json`

- r2 기준 2020–2025 전수 MFA: **아직 시작하지 않음**
- r2 인프라 수용 파일럿:
  **6개년 기계 검증 완료, 전역 수정 2건 확인 후 개별 검토 진행 중**
  - 범위: 2020–2025, 연도당 10발화·5화자·5세션
  - D: 실행 루트:
    `D:\mfa_eojeol\pilots\r2_infrastructure\mfa_r2_infra_pilot_20260730`
  - 2020–2025: 연도별 machine marker 6/6 통과
  - 모든 연도 실제 `spn=0`, 허용 inventory 밖 phone 0
  - 6개년 방법 교차 감사: `passed`, 방법 불일치 0,
    동일 phone 생성 기준·허용 inventory 참
  - Dropbox 검토본:
    `C:\Users\ari30\Dropbox\MFA_R2_INFRA_PILOT_20260730`
  - 평면 파일 246개, 60발화, payload 240개,
    `REVIEW.xlsx` 링크 240/240 검증
  - 연구자 인프라 검토: 1/60 상세 확인
  - 전역 `G-TIER-01`: legacy 시간분할 `morphemes`를 `0–xmax` 단일
    `morph_analysis` tagging tier로 교체 필요
  - 전역 `G-CSV-01`: 형태소 첫/끝·좌우 환경의 구조화
    `morph_tokens/morph_boundaries` 파생표 필요
  - `REVIEW.xlsx` 2–60번에 전역 코드 사전입력 완료;
    남은 개별 검토는 연결과 경계
- 외부 workflow 리뷰 판정: `GO AFTER FIXES`
- TextGrid 발화 수준 검색 tier 외부 리뷰:
  `words/phones_mfa/utterance/utterance_search` 4-tier 권장
- 외부 형태소·로마자 위치 검색 리뷰는 필수 정정을 반영해 triage 완료
- 현재 단계: **검색 스키마·새 4-tier의 60발화 기계 gate 통과,
  12발화 연구자 수용 검토 대기**.
  - 구조화 검색 정본:
    `morph_tokens/morph_units/morph_boundaries`, 선택 파생
    `orth_components`
  - 60발화: 새 TextGrid 60/60, DB word/phone 의미 동등성 60/60,
    CSV–TextGrid 형태소 label 동등성 60/60
  - Dropbox:
    `C:\Users\ari30\Dropbox\MFA_RESEARCH_SCHEMA_REVIEW_12_20260731`
  - 첫 수동 검토에서 일부 tier의 명시적 0.05초 padding endpoint 누락을
    발견해 v2로 교정. 네 tier의 좌우 endpoint 12/12 재검증, 기존판은
    `MFA_RESEARCH_SCHEMA_REVIEW_12_v1_ARCHIVE_20260731`에 보존
  - 단순 표시 검토만으로 승인하지 않도록 60발화 구조화 표의 실제 조합
    검색 Q1–Q7을 실행한 `COMBINED_SEARCH_DEMO.xlsx` 추가. 전체 적중 수와
    대표 13행, WAV/TextGrid/CSV 링크 39개, 파일 SHA 검증 통과
  - MFA IPA를 없애지 않고 검색용 로마자로 보조하는 post-MFA 파일럿 완료.
    동결 phone 107개 전수 매핑, 실제 60발화 1,625구간, 선택적
    `phoneme_r_auto` 5-tier 60/60과 기존 네 tier 불변 검증 통과.
    Dropbox의 `PHONEME_ROMAN_PILOT.xlsx`와 12개 새 5-tier는 연구자
    수용 검토 대기이며 기본 운영 tier는 아직 4개다.
  - 전수 MFA는 연구자 수용 전까지 시작하지 않음

### 서울 코퍼스 참조 TextGrid v2 결정과 최소 파일럿

- 2026-08-01 연구자가 차기 연구 표시 6-tier를 승인했다.
  `words / phones_mfa / phoneme_r_auto / utterance /
  utterance_orth_r / morph_analysis_utt` 순서다.
- `phoneme_r_auto`는 `phones_mfa`만으로 만드는 broad Roman이며,
  철자·규칙·사전 발음으로 기저형을 역복원하지 않는다.
- `utterance_orth_r`는 현행 `form_roman`과 ` | ` 어절 구분자를 쓰고,
  `morph_analysis_utt`는 한글 `형태소/POS`를 발화 전체 span에 표시한다.
  형태소 시간경계를 주장하지 않는다.
- KOINA는 선별 후보의 별도 파생 산출물이다. 연결본에는
  `source_utt_id/speaker`와 원시간 manifest를 추가하지만, 인공 seam을
  가로지르는 AP/IP 해석은 금지한다.
- 새 코드는 기존 v5 생성기를 바꾸지 않고 `research_textgrid_v2.py`로
  분리해 구 4/5-tier 코드와 실물을 보존했다.
- 최소 파일럿은 다음에 생성했으며 독립 verification이 `success`다.

```text
C:\Users\ari30\research\2026_summer_research\outputs\
  textgrid_6tier_mini_pilot_20260801
```

- 실물 범위: 2020 단일 발화 1건(6-tier), 같은 2022 세션·같은 화자의
  비인접 2발화 `review` 연결본 1건(기본 6-tier+
  `source_utt_id/speaker`). KOINA는 실행하지 않았다.
- 전수 생성과 전수 MFA runner 연결은 이 최소본을 연구자가 확인한 뒤로
  유지한다.

상세 정본:

- `docs/decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md`
- `docs/decisions/GUIDE_mfa_r2_infrastructure_review_columns_20260730.md`
- `docs/decisions/DECISION_mfa_r2_review_global_issues_20260730.md`
- `docs/reviews/PROMPT_external_review_TextGrid_utterance_search_tier_20260730.md`
- `docs/reviews/RESULT_design_review_TextGrid_utterance_search_tier_20260731.md`
- `docs/reviews/PROMPT_external_review_morph_roman_position_schema_20260731.md`
- `docs/reviews/RESULT_design_review_morph_roman_position_schema_20260731.md`
- `docs/reviews/RESOLUTION_design_review_morph_roman_position_schema_20260731.md`
- `docs/reviews/PROMPT_external_review_r2_MFA_research_workflow_20260730.md`

## 중요한 미완료 항목

- 동결 pre-MFA search master는 LAB/MFA 입력에는 충분하지만 최종 연구 검색
  CSV가 아니다.
- 최종 검색 CSV/Parquet에는 형태소 정보, 형태소별·어절별 철자 로마자,
  규칙 발음, 우리말샘 보조 발음, 화자/대화 참여자, 파일 coverage가 필요하다.
- 6개년 MFA 뒤 TextGrid에서 `pron_mfa`, `n_spn`, `align_status`와
  phone-derived `phoneme_r_auto`를 만드는 post-MFA 보조 레이어를 전수
  생성·검증해야 한다. 철자·예측발음 대응은 진단 CSV로만 분리한다.
  로마자 음소층의 연도 runner 배선은 아직이다.
- KOINA, stitch, wav2vec2, 연구자 판정은 선택 후보에만 별도 산출물로 추가한다.

## 바로 다음 작업

1. `run_mfa_year_queue_safe.ps1 -PrepareMissingReviews`로 6개년 입력을
   감사하고 연도별 pending 제외 후보표를 만든다. 이 단계는 MFA를 시작하지 않는다.
2. 연구자가 후보를 승인/기각하고 각 input contract에 묶인 승인 JSON을 만든다.
3. `preflight_mfa_year_queue.ps1 -RunRepositoryTests`의 `status=GO`를 확인한다.
4. 같은 queue를 다시 실행해 2020–2025 계산과 독립 machine QC를 연도별로
   진행한다. 성공 연도도 연구자 검토 전에는 정본으로 승격하지 않는다.

무인 연도 큐는 재개 실패 뒤 연도 전체 `--clean`을 자동 수행하지 않는다.
temp·SQLite DB·interval·로그를 보존하며, 일부 문제가 있는 연도만 상태표에
차단된 것으로 남기고 다른 연도의 독립 준비/계산을 계속할 수 있다.

전수 MFA는 승인 계약과 최종 preflight `GO` 전에는 시작하지 않는다. 연구자가
확인한 전역 출력·검색 문제는 코드와 60발화 재수출에서 수정됐고 기계 검증도
통과했다.

## 2020 실행 인터페이스의 안전장치

`run_pre_mfa_bulk_safe.ps1`은 한 번에 한 연도만 허용한다. 2020·2021은
상위 wrapper와 하위 runner 모두에서 `-AllowBaselineCommonPronRerun`이 있어야
r2 재실행이 가능하다. 다른 연도나 공통사전 없는 실행에서 이 플래그를 쓰면
차단한다.

기존 `WORKFLOW_r2_MFA_research_data_contract_20260730.md` §11의 명령은
현재 사용하지 않는다. 외부 리뷰·필수 수정 통과 후 새 계약으로
2020 명령을 다시 만들며, 첫 실행에는 cleanup을 넣지 않는다.

## 세션 복구 절차

1. 이 파일을 끝까지 읽는다.
2. `docs/environment/linguistics-research-environment-master-notes.md`를 읽는다.
3. `git status`와 최근 decision/work history를 확인한다.
4. r2 dashboard와 D:/E: manifest를 읽기 전용으로 대조한다.
5. 문서와 실제 상태가 다르면 명령을 먼저 제안하지 말고 상태 정본을 갱신한다.
6. 한 단계가 완료되면 이 파일, work history, 관련 decision을 함께 갱신한다.
