# 외부 도구용 리뷰 프롬프트 — 전수 TextGrid·CSV 생산 계약

아래 프롬프트는 **같은 로컬 작업 폴더를 읽을 수 있는 외부 리뷰
도구**에 전달한다.

---

한국어 음운·형태·음향 연구 인프라의 **외부 설계·코드 리뷰**를
요청합니다. 코드 스타일보다 연구 방법의 타당성, 출처 추적,
입력–중간–출력 자료 계약, 510만 발화 운영 안전성을 우선해 주십시오.

작업 폴더:
`C:\Users\ari30\research\2026_summer_research`

중요: 현재 체크아웃된 branch/HEAD를 그대로 읽으세요. `git pull`, checkout,
reset, merge를 하지 마세요. 코드·문서·D:/E:/H:/Dropbox/원 corpus를
수정하지 마세요. MFA, KOINA, 대량 생성 스크립트를 실행하지 마세요.
리뷰 결과 파일 하나만 아래 위치에 새로 작성하세요.

```text
docs/reviews/incoming/
  EXTERNAL_REVIEW_full_production_TextGrid_CSV_20260801.md
```

## 연구 목적

1. CSV/Parquet에서 특정 형태소 또는 표기상 음운 환경을 검색합니다.
2. `utt_id`로 해당 WAV·TextGrid·CSV를 모읍니다.
3. 선별 후보에만 KOINA, 필요 시 이어붙이기·wav2vec2 보조 분석을
   추가합니다.
4. 실제 실현 여부는 연구자가 음성과 TextGrid를 직접 보고 들어
   별도로 판정합니다.

MFA/G2P phone, 규칙 발음, 사전 발음, wav2vec2 phone은 실제 실현
판정값이 아닙니다.

## 먼저 읽을 문서

1. `AGENTS.md`
2. `docs/environment/PROJECT_START_HERE.md`
3. `docs/environment/PROJECT_CURRENT_STATE.md`
4. `docs/environment/linguistics-research-environment-master-notes.md`
5. `docs/decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md`
6. `docs/decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`
7. `docs/reviews/RESOLUTION_design_review_morph_roman_position_schema_20260731.md`
8. `docs/decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md`
9. `outputs/reports/RESULT_research_6tier_candidate_60_20260801.md`

8번 문서의 4-tier 부분은 역사적 설계입니다. 5번이 현재 외부 리뷰
대상 최신 제안인지 반드시 확인하세요.

## 반드시 추적할 코드

- `scripts/run_pre_mfa_bulk_safe.ps1`
- `scripts/run_eojeol_realign.ps1`
- `scripts/preflight_eojeol_realign.ps1`
- `scripts/python/export_mfa_db_research_6tier.py`
- `scripts/python/inspect_mfa_db_checkpoint.py`
- `scripts/python/research_textgrid_v2.py`
- `scripts/python/morph_schema.py`
- `scripts/python/build_morph_position_tables.py`
- `scripts/python/realign_eojeol_build_corpus.py`
- `scripts/python/build_search_master.py`
- `scripts/python/phoneme_roman.py`
- 관련 `tests/`

로컬 회귀 실물이 존재하면 읽기 전용으로 표본 확인하세요.

```text
work/research_6tier_candidate_60_20260801
```

없다면 문서의 수치를 추정으로 재생성하지 말고 `evidence unavailable`로
표시하세요.

## 리뷰 질문

각 항목에 파일과 행 번호 근거를 대세요.

1. 연구자가 붙인/확정한 정보, 국립국어원 원자료, 형태소 분석,
   규칙·사전·G2P·MFA·phone Roman 파생값, 추후 수동 판정이
   schema·값·provenance에서 명확히 드러나는가?
2. 이 출처 계층과 자동값의 한계를 논문 방법론에서 올바르고
   재현 가능하게 설명할 수 있는가? 과장·거짓 정밀성은 없는가?
3. `words/phones_mfa/phoneme_r_auto/utterance/utterance_orth_r/
   morph_analysis_utt` 6-tier가 Praat 검토·간단 검색과 510만 파일
   운영 사이에서 타당한가? 어떤 tier를 전수에 물리 저장하지 말고
   후보 bundle에서 파생해야 한다면 근거를 제시하라.
4. 형태소 시간경계를 만들지 않고 발화 전체 span에 `tagged`를 두는
   설계가 연구 목적과 일치하는가?
5. `form/tagged` 원 어절, `pron_reference_form` 어절, MFA word의
   좌표계가 충분히 분리되었는가? `2사람이 → 두 사람이` 같은
   1:N 정규화에서 잘못된 형태소–phone 연결을 막는가?
6. 연도별 gzip 세 표가 510만 발화의 logical sidecar로 타당한가?
   후속 Parquet/DuckDB, row key, dtype, schema evolution, 대량 스트리밍 측면에서
   필수 수정은 무엇인가?
7. 동일 `utt_id`를 중심으로 형태소 표·어절 표·TextGrid·WAV·MFA
   word/phone·대화/화자·사전 후보·KOINA·manual judgment를 추후
   안전하게 조인할 수 있는가?
8. 우리말샘/표준국어대사전의 다의어·복수 발음을 1:N 보조표로
   붙이려면 어떤 키·sense·POS·variant 계약이 필요한가?
9. r2 공통사전·acoustic·G2P·phone inventory가 2020–2025 모두에
   실제로 강제되고, legacy inline G2P/4-tier로 조용히 돌아가지 않는가?
10. `direct_db_ready`가 출력 코드 실패 시 비싼 MFA 재실행을 막으면서도,
    정렬 계산 재사용 가능과 분석 승인을 잘못 합치지 않는가?
11. partial·marker·final staging·DB 보존 순서가 오류, 창 종료, 디스크 부족,
    파일 lock에서도 이미 끝난 정렬을 잃지 않고 거짓 성공을 막는가?
12. 예상되는 자료 사용 불가·MFA 미정렬을 exporter의 전체 실패로만
    처리할지, 명시적 inventory·승인 계약으로 분류할지 구체안을 제시하라.
13. 연도 1개 실행 후 다음 연도를 허용할 독립 QC·연구자 표본
    검토·저장공간 gate가 충분한가?
14. 현재 60발화 검사가 증명하지 못한 것은 무엇이며, 2020 전수 전에
    추가 새 MFA 파일럿 대신 보존 DB/정적 fixture/스토리지 벤치마크로
    확인할 최소 항목은 무엇인가?

## 보고서 형식

1. 최종 판정 하나: `GO`, `GO AFTER FIXES`, `STOP`
2. 논문 방법론 타당성 요약
3. 자료·tier·표별 provenance 누락/혼동
4. 심각도별 발견 사항: `BLOCKER/HIGH/MEDIUM/LOW`
   - ID
   - 증거 `file:line`
   - 510만 전수 또는 연구 해석에 미치는 영향
   - 재현 방법
   - 구체적 수정안
5. 전수 실행 전 필수 수정 체크리스트
6. 실행 후 연도별 gate 체크리스트
7. 연구자에게만 받아야 하는 결정과 코드로 결정 가능한 사항의 분리
8. 논문에 쓸 수 있는 방법 서술 수정안과, 아직 쓰면 안 되는 미완료 주장
9. 불확실한 사항은 `UNVERIFIED`로 표시

추상적 조언보다 현재 코드·schema·실물 수치에 직접 연결된
리뷰를 작성해 주십시오.
