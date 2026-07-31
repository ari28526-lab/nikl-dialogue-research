# 프로젝트 현재 상태 정본

최종 갱신: 2026-07-31 KST

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
  - 전수 MFA는 연구자 수용 전까지 시작하지 않음

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
- 6개년 MFA 뒤 TextGrid에서 `pron_mfa`, `n_spn`, `align_status` 등을 만드는
  post-MFA 보조 레이어를 전수 생성·검증해야 한다.
- KOINA, stitch, wav2vec2, 연구자 판정은 선택 후보에만 별도 산출물로 추가한다.

## 바로 다음 작업

1. Dropbox의 12발화 수정본에서 연결·양끝 경계·`[MORPH]` 가독성·
   `[MORPH_R]` 검색 가능성을 확인한다.
2. 작성된 `REVIEW.xlsx`를 기계 gate와 결합해 인프라 승인 보고서를 만든다.
3. 승인 뒤 2020 r2 전수 MFA를 시작하고 같은 검색 표를 연도 단위로 만든다.
4. 2020의 정렬·phone inventory·검색 표·연구자 표본 QC를 모두 통과한 뒤
   2021로 넘어간다.
5. 2022–2025도 동일 계약과 한 연도씩의 gate로 진행한다.

전수 MFA는 아직 시작하지 않는다. 연구자가 확인한 전역 출력·검색 문제는
코드와 60발화 재수출에서 수정됐고 기계 검증도 통과했다. 이제 수정본
12발화를 사람이 수용하는 단계다.

## 2020 실행 인터페이스의 안전장치

`run_pre_mfa_bulk_safe.ps1`은 한 번에 한 연도만 허용한다. 2020·2021은
상위 wrapper와 하위 runner 모두에서 `-AllowBaselineCommonPronRerun`이 있어야
r2 재실행이 가능하다. 다른 연도나 공통사전 없는 실행에서 이 플래그를 쓰면
차단한다.

실제 명령은 12발화 연구자 수용 뒤
`WORKFLOW_r2_MFA_research_data_contract_20260730.md`의 11절에서 가져온다.
첫 실행에는 cleanup을 넣지 않는다.

## 세션 복구 절차

1. 이 파일을 끝까지 읽는다.
2. `docs/environment/linguistics-research-environment-master-notes.md`를 읽는다.
3. `git status`와 최근 decision/work history를 확인한다.
4. r2 dashboard와 D:/E: manifest를 읽기 전용으로 대조한다.
5. 문서와 실제 상태가 다르면 명령을 먼저 제안하지 말고 상태 정본을 갱신한다.
6. 한 단계가 완료되면 이 파일, work history, 관련 decision을 함께 갱신한다.
