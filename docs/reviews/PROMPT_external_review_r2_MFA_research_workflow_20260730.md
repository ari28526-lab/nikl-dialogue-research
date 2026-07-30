# 외부 도구용 리뷰 프롬프트 — r2 MFA 연구 자료 흐름

아래 내용을 저장소 주소와 함께 외부 리뷰 도구에 그대로 전달한다.

---
한국어 언어학 연구 파이프라인의 **읽기 전용 리뷰**를 요청합니다. 코드를
수정하거나 PR을 만들지 말고, 저장소 전체를 읽은 뒤 증거 기반 보고서만
작성해 주세요.

저장소:
`https://github.com/ari28526-lab/nikl-dialogue-research.git`

리뷰 브랜치:
`agent/harden-pre-bulk-pipelines`

먼저 실제로 체크아웃해 읽은 branch와 HEAD commit SHA를 보고서 첫머리에
기록하세요. 해당 브랜치가 없거나 문서를 읽지 못하면 추정 리뷰를 하지 말고
`HOLD`로 보고하세요.

## 연구 목적

연구자는 CSV/Parquet에서 특정 형태소 또는 표기상 음운 환경을 검색하고,
해당 WAV와 TextGrid를 모은 뒤 선택 발화에 KOINA 운율 분석을 수행합니다.
최종 실현 여부는 연구자가 음성과 TextGrid를 직접 보고 듣고 판정합니다.
MFA/G2P phone은 대략적 정렬 보조 정보이며 실제 실현 판정값이 아닙니다.

2020–2025년 전부를 같은 최신 Jamo 공통사전, acoustic model, G2P, phone
inventory, adoption contract로 다시 MFA할 예정입니다. 2020·2021 구결과는
재사용하지 않고 차이 inventory만 전환 감사 증거로 보존합니다.

## 반드시 먼저 읽을 문서

1. `docs/environment/PROJECT_START_HERE.md`
2. `docs/environment/PROJECT_CURRENT_STATE.md`
3. `docs/environment/linguistics-research-environment-master-notes.md`
4. `docs/decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md`
5. `docs/decisions/DESIGN_search_master_layer.md`
6. `docs/decisions/DESIGN_pronunciation_environment_search_2026-07-25.md`
7. `docs/decisions/STANDARD_textgrid_tiers.md`
8. `docs/decisions/DECISION_r2_realign_all_six_years_20260729.md`
9. `docs/decisions/METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md`

그 뒤 다음 실행 경로와 관련 테스트를 추적하세요.

- `scripts/run_pre_mfa_bulk_safe.ps1`
- `scripts/run_eojeol_realign.ps1`
- `scripts/preflight_eojeol_realign.ps1`
- `scripts/python/build_mfa_alignment_contract.py`
- `scripts/python/export_mfa_db_4tier.py`
- `scripts/python/audit_mfa_4tier_year.py`
- `scripts/python/preflight_next_year_after_qc.py`
- `scripts/python/audit_mfa_cross_year_contracts.py`
- `scripts/python/build_search_master.py`
- `scripts/python/build_common_pron_mfa_adoption.py`
- `tests/`

## 리뷰의 중심

코드 스타일보다 **연구 목적에 맞는 입력자료·중간 산출물·출력자료의 형식,
출처, 연결 방식, 실패 복구, 방법론적 일관성**을 우선 검토하세요.

다음 질문에 각각 증거로 답하세요.

1. 동결 pre-MFA 입력과 최종 연구 검색 CSV가 개념·경로·완료 보고에서
   충분히 분리되어 있는가?
2. `form`, `original_form`, 규칙 발음, 우리말샘 발음, r2 사전 phone,
   MFA phone, wav2vec2 phone, 연구자 실현 판정이 혼동되거나 덮어써질
   경로가 없는가?
3. 형태소별·어절별 철자 로마자와 형태소/품사/어절 index를 이용해
   음운형태적 환경을 재현 가능하게 검색할 수 있는가?
4. `utt_id`, `session_id`, speaker ID, dialogue participant/co-speaker ID,
   `eojeol_index`가 WAV/TextGrid/CSV 사이에서 손실 없이 조인되는가?
5. r2 공통사전이 6개년 모두에 실제로 강제되고, inline G2P나 구사전으로
   조용히 돌아갈 가능성이 없는가?
6. 2020·2021 전수 재실행이 명시적으로 허용되면서도, 구 done marker·temp·
   output을 새 r2 성공으로 오인하지 않는가?
7. 운영 TextGrid의 `words/phones/morphemes/utterance`가 정확히 4-tier이며,
   모든 tier가 `0–xmax`를 빈 interval까지 포함해 연속적으로 덮는가?
   `phones`가 의미상 `phones_mfa`이고 `morphemes`가 legacy 출처라는
   provenance가 downstream에서 유지되는가?
8. direct DB export가 MFA DB의 word/phone 시간과 라벨을 보존하며, 수백만
   파일 I/O를 줄이는 대신 연구 자료를 잃지 않는가?
9. 부분 성공, 누락, quarantine, 재시도, 프로세스 중단, 오래된 lock,
   coverage 부족이 전부 추적되고 거짓 성공이 차단되는가?
10. 한 연도씩 QC하고 D: 공간을 정리·archive한 뒤 다음 연도로 넘어가는
    저장 정책이 실제 코드와 일치하는가?
11. 후보 bundle, KOINA, 이어붙이기, wav2vec2 보조 phone, 연구자 판정이
    canonical MFA 결과를 바꾸지 않는 별도 층으로 유지되는가?
12. 6개년 완료 후 동일 acoustic/G2P/dictionary/adoption/phone inventory를
    논문에서 입증할 충분한 SHA·contract·감사 산출물이 남는가?
13. 정렬 품질을 낮추지 않으면서 줄일 수 있는 실제 병목이 있는가?
    SAT 비활성화 같은 품질 변화는 단순 속도 개선으로 권하지 마세요.
14. 현재 문서가 “이미 구현된 것”과 “필수이나 아직 구현되지 않은 것”을
    정확히 구분하는가?

특히 `WORKFLOW_r2_MFA_research_data_contract_20260730.md`의 입력/출력 계약이
코드 실물과 어긋나는 부분을 찾아 주세요. 문서에만 있고 구현되지 않은
필수 출력도 finding으로 보고하세요.

## finding 형식

각 finding은 아래 필드를 모두 포함하세요.

- `ID`: `MFA-###` 또는 `CSV-###`
- `Severity`: `P0`, `P1`, `P2`, `P3`
- `Evidence`: 정확한 `path:line`과 관련 함수/파라미터
- `Violated contract`: 위반한 연구·입력·출력·재현성 계약
- `Research impact`: 검색 누락, 잘못된 조인, 방법론 불일치, 거짓 성공,
  재실행 범위 등에 미치는 영향
- `Minimal fix`: 가장 작은 안전 수정
- `Rerun scope`: 코드만/2020만/해당 연도/6개년/CSV 전량 등
- `Required test`: 재발 방지 테스트

근거 없는 일반론은 제외하고, finding이 없으면 어떤 경로와 불변식을
확인했는지 명시하세요. 비밀값이나 대용량 외부 데이터 실물은 요구하지
마세요. 저장소에 없는 D:/E: 결과는 계약·manifest 처리 코드를 기준으로
검토하고, 실물 검증이 필요한 항목은 `requires local evidence`로 구분하세요.

## 최종 판정

보고서 마지막에 다음 중 하나만 선택하세요.

- `GO`: 현재 상태로 2020 r2 전수 MFA 시작 가능
- `GO AFTER FIXES`: 명시한 P0/P1 수정·검증 뒤 시작 가능
- `HOLD`: 입력/출력 또는 방법 계약이 불충분해 시작하면 안 됨

그 아래에 2020을 시작하기 전 필수 조건을 체크리스트로 적고, 가장 위험한
세 가지와 예상 재실행 비용을 요약하세요.

Markdown 보고서만 반환하세요. 리뷰 결과는 사용자가 다시 Codex에 전달해
수정 여부와 실행 결정을 내릴 예정입니다.

---
