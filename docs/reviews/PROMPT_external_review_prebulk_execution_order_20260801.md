# 외부 도구 전달용 프롬프트 — 전수 작업 순서 리뷰

아래 내용을 그대로 다른 도구에 전달한다. 도구는 이 저장소와 같은 로컬 폴더에서
작업한다고 가정한다.

---

당신은 한국어 언어학 연구 인프라의 **전수 작업 순서와 방법론적 정합성**을
검토하는 외부 리뷰어다. 코드 스타일 일반론보다, 입력자료→검색표→MFA→TextGrid→
최종 검색 DB→연구자 판정의 순서가 연구 목적에 맞고 불필요한 재계산과 검토를
막는지를 우선 평가하라.

프로젝트 루트:

```text
C:\Users\ari30\research\2026_summer_research
```

먼저 다음 파일을 순서대로 모두 읽어라.

```text
docs/environment/PROJECT_START_HERE.md
docs/environment/linguistics-research-environment-master-notes.md
docs/environment/PROJECT_CURRENT_STATE.md
docs/decisions/PROPOSAL_prebulk_execution_order_20260801.md
docs/decisions/DECISION_pre_MFA_combination_search_v3_20260801.md
docs/decisions/DECISION_incremental_unattended_year_MFA_20260801.md
docs/decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md
```

필요한 경우 실제 구현과 manifest를 읽어 제안서의 사실을 검증하되, 코드 품질
전체 리뷰로 범위를 넓히지 마라. 특히 다음 파일을 확인할 수 있다.

```text
config/paths.json
scripts/run_morph_search_year_safe.ps1
scripts/python/build_morph_search_year_sharded.py
scripts/prepare_mfa_year_exclusion_review.ps1
scripts/preflight_mfa_year_queue.ps1
scripts/run_mfa_year_queue_safe.ps1
scripts/run_eojeol_realign.ps1
scripts/python/export_mfa_db_research_6tier.py
scripts/python/audit_mfa_research_6tier_year.py
outputs/reports/EVIDENCE_morph_search_v3_regression_60_20260801.json
outputs/reports/PREFLIGHT_morph_search_v3_2020_shard1_20260801.json
```

연구 목적은 다음과 같다.

1. 형태소 또는 표기상 음운형태 환경을 CSV/Parquet에서 검색한다.
2. `utt_id`로 WAV·TextGrid·메타데이터를 모은다.
3. 선별 후보에만 KOINA, 이어붙이기, wav2vec2 보조 분석을 적용한다.
4. 실제 실현 여부는 연구자가 음성과 TextGrid를 보고 별도로 판정한다.

중요한 확정사항:

- 2020의 구 정렬을 다시 전수 검토하거나 재사용하지 않는다.
- 2020–2025를 공통 Jamo r2 사전과 동일 acoustic/G2P/phone 기준으로 새로 정렬한다.
- MFA/G2P phone은 자동 강제정렬 보조값이며 실제 실현 판정이 아니다.
- 형태소 시간경계를 자동으로 주장하지 않는다.
- 숫자·기호 후보 발음을 근거 없이 LAB 선택값으로 자동 승격하지 않는다.
- 우리말샘 복수 발음은 최종 검색용 1:N 보조표이며 MFA용 단일값으로 자동 채택하지 않는다.
- 2020 `morph_search.v3`은 실제 첫 shard 1/23만 성공했고 현재 정상 정지 상태다.
- 전수 MFA는 아직 시작하지 않았다.

반드시 다음 질문에 답하라.

1. 제안된 순서가 연구 목적과 산출물 활용 방식에 부합하는가?
2. 2020 신규 MFA 전에 반드시 동결·완료해야 하는 것과 정렬 뒤로 미뤄도 되는
   것을 올바르게 구분했는가?
3. `morph_search.v3 YEAR_MANIFEST=success`를 해당 연도 MFA의 hard gate로 해야
   하는가, 아니면 두 작업이 같은 동결 source/input contract를 가리키는지만
   확인하면 되는가? 방법론·복구·시간 비용을 함께 고려해 하나를 권고하라.
4. 2020을 첫 **생산 연도**로 완료하고 Gate B 뒤 2021–2025로 가는 방식이
   충분한가? 또 별도 파일럿이 필요한 경우만 구체적 위험과 함께 제시하라.
5. LAB/WAV 예외 후보의 연구자 승인을 제외하고 불필요한 반복 수동 검토가
   남아 있는가? 기계 QC와 연구자 판단의 경계가 적절한가?
6. 연도/shard/DB checkpoint가 일부 실패 때 전체 재시작을 충분히 막는가?
7. D: 실행 공간과 E:/추가 HDD archive를 고려한 중간물 보존·압축·정리 순서는
   적절한가?
8. pre-MFA 7표, post-MFA 4표, 6-tier TextGrid, 최종 Parquet/DuckDB와
   우리말샘 1:N 후보표의 결합 순서에 빠진 산출물이 있는가?
9. 논문에서 2020–2025가 동일한 phone 생성·정렬 기준을 사용했고 원자료,
   자동 파생값, 연구자 판정을 분리했다고 주장하기 위해 추가 증거가 필요한가?
10. 지금 당장 사용자가 실행해야 할 명령은 무엇이어야 하는가? 리뷰 수정 전에는
    아무 전수 명령도 실행하지 않는 편이 맞다면 그렇게 명시하라.

결과는 다음 형식으로 작성하라.

```text
# 외부 리뷰: 전수 작업 최종 실행 순서

## 1. 최종 판정
GO / GO AFTER FIXES / NO_GO

## 2. 연구 목적 부합성

## 3. BLOCKER
- ID, 문제, 근거 파일/행, 왜 전수 전에 필요한지, 최소 수정

## 4. HIGH / MEDIUM / LOW

## 5. 권장 최종 실행 순서
- 단계별 입력, 출력, gate, 실패 시 재개 지점

## 6. MFA 전 필수와 후행 가능 항목 표

## 7. 사람 검토 최소화 원칙

## 8. 저장공간·archive 순서

## 9. 논문 방법론 증거 체크리스트

## 10. 사용자가 다음에 할 한 가지
```

각 지적에는 가능한 한 저장소의 실제 파일과 행 번호를 근거로 달라. 단순한
“테스트를 더 하라”는 권고는 피하고, 어떤 실패를 막는 어떤 최소 검증인지
명시하라. 기존 표기를 유지하는 것 자체를 목표로 삼지 말고 연구 목적·검색성·
재현성·실패 복구를 우선하라.

결과를 다음 새 파일에 저장하라.

```text
docs/reviews/incoming/EXTERNAL_REVIEW_prebulk_execution_order_20260801.md
```

이 리뷰 동안 다음은 금지한다.

- D:/E:/H:의 대량 파일 생성·이동·삭제
- MFA, KOINA, wav2vec2 또는 전수 CSV 실행
- 연구자 제외 후보 자동 승인
- 코드·설계 문서 수정
- Git commit/push

리뷰 결과 Markdown 한 파일만 새로 작성하고 종료하라.

---
