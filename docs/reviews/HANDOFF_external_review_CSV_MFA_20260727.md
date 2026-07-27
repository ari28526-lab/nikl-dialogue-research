# 외부 코드리뷰 인계 — 전체 CSV·MFA 파이프라인

작성일: 2026-07-27  
저장소: <https://github.com/ari28526-lab/nikl-dialogue-research>  
대상 브랜치: `agent/harden-pre-bulk-pipelines`

이 문서는 다른 AI 도구 또는 제3자 리뷰어에게 GitHub 주소와 함께 전달할
읽기 전용 리뷰 요청문이다. 저장소가 private이면 리뷰 도구에도 별도 GitHub
접근 권한이 있어야 한다. 원자료·API key·D: 산출물은 공유하지 않는다.

## 1. 리뷰 시작 시 고정할 것

리뷰어는 먼저 다음을 답변 첫머리에 적는다.

```text
repository:
branch:
reviewed_commit_sha:
reviewed_at:
files_actually_inspected:
tests_or_static_checks_actually_run:
unavailable_data_or_assumptions:
```

브랜치는 리뷰 중 바뀔 수 있으므로 URL만 보고 검토하지 말고
`git rev-parse HEAD`의 전체 SHA를 기록한다. 피드백은 그 SHA와 함께 원문
그대로 다시 전달한다.

## 2. 리뷰 목적과 연구 흐름

이 저장소는 국립국어원 2020–2025 일상대화 약 510만 발화를 다음 흐름으로
처리한다.

```text
원본 JSON + Bareun 형태소 + 메타데이터
    → 검색용 CSV/search master
    → 형태소·철자 로마자 + 사전·규칙 발음
    → WAV + lab 입력계약
    → 공통 발음사전/G2P + MFA
    → SQLite DB + 4-tier TextGrid
    → 후보 수집 + KOINA
    → 연구자 직접 청취·실현 판정
```

MFA phones는 대략적인 음성 분절과 위치 탐색용이며 실제 음운현상 실현의
자동 판정값이 아니다. 리뷰에서는 이 연구적 경계가 코드·열 이름·문서에서
무너지지 않는지도 확인한다.

## 3. 먼저 읽을 문서

1. `README.md`
2. `docs/PROJECT_SUMMARY.md`
3. `docs/자료구축_코드해설.md`
4. `scripts/SCRIPTS_INDEX.md`
5. `docs/decisions/DESIGN_safe_pre_bulk_pipeline_2026-07-24.md`
6. `docs/decisions/DESIGN_pronunciation_environment_search_2026-07-25.md`
7. `docs/decisions/DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md`
8. `docs/decisions/RUNBOOK_pre_MFA_bulk_safe_2026-07-25.md`
9. `docs/decisions/AUDIT_pre_bulk_MFA_CSV_2026-07-24.md`
10. `docs/decisions/AUDIT_remaining_MFA_years_and_direct_DB_export_2026-07-26.md`

문서의 주장만 신뢰하지 말고 실제 코드·시험이 그 주장을 보장하는지 역추적한다.

## 4. 코드리뷰 범위

### 4.1 CSV·search master 전체

실제 runner에서 호출되는 경로를 기준으로 다음을 연결해 본다.

- `scripts/run_search_master.ps1`
- `scripts/python/preflight_search_master.py`
- `scripts/python/build_search_master.py`
- `scripts/python/pipeline_common.py`
- `scripts/python/predict_pron.py`
- `scripts/python/build_metadata_index.py`
- `scripts/python/audit_search_master.py`
- `scripts/python/bareun_dialogue_full.py`
- 형태소·의미·빈도 계층과 연결되는 활성 스크립트
- 관련 `tests/`

검토 질문:

1. 세션·발화·화자 ID와 행 순서가 JSON–Bareun–CSV–WAV 사이에서 조용히
   어긋날 수 있는가?
2. `form`, `original_form`, 숫자·기호 회복, 형태소, 철자 로마자, 규칙 발음,
   사전 발음의 출처가 열별로 보존되는가?
3. lexicon 중복 조인으로 행이 늘거나, 다의어의 첫 의미가 임의 선택되거나,
   품사 불일치를 무시한 잘못된 발음 결합이 가능한가?
4. 510만 행 대량 처리에서 checkpoint·resume·원자 교체·기존본 archive·실패
   manifest가 부분 성공을 정본으로 오인하지 못하게 하는가?
5. schema, 수량, ID 집합, fingerprint, 재현성 검증이 runner와 실제 builder
   사이에서 우회될 수 있는가?
6. CSV와 정규화 Parquet로 옮길 때 검색 가능한 형태소·철자 로마자·발음 후보와
   provenance가 손실되지 않는가?

### 4.2 MFA 전체

- `scripts/run_pre_mfa_bulk_safe.ps1`
- `scripts/preflight_eojeol_realign.ps1`
- `scripts/run_eojeol_realign.ps1`
- `scripts/python/realign_eojeol_build_corpus.py`
- `scripts/python/patch_mfa_export_queue.py`
- `scripts/python/patch_mfa_skip_export.py`
- `scripts/python/verify_mfa_install.py`
- `scripts/python/export_mfa_db_4tier.py`
- `scripts/python/realign_eojeol_merge_output.py`
- `scripts/python/compare_textgrid_tiers.py`
- `scripts/python/audit_mfa_year_readiness.py`
- `scripts/python/audit_mfa_4tier_year.py`
- `scripts/python/preflight_next_year_after_qc.py`
- 파일 수집·연결 검증용 `locate_utt.py`, `fetch_audio_for_search.py`,
  `stitch_session.py`, `build_stratified_mfa_review_bundle.py`
- 관련 PowerShell·Python tests

검토 질문:

1. CSV→lab→WAV→MFA DB→TextGrid의 ID·경로·수량 계약이 끝까지 같은가?
2. MFA exit 0, 일부 TextGrid, stale temp/marker를 거짓 성공으로 승격할 수 있는
   경로가 남아 있는가?
3. 중단·재시작·연도 전환 때 원자료, 기존 DB, partial, 로그가 보존되는가?
4. dictionary, G2P, acoustic model, MFA 설치 patch의 fingerprint가 정렬
   입력계약에 충분히 포함되는가?
5. direct DB 4-tier export가 built-in export와 실제로 동등하며 실패·누락을
   숨기지 않는가?
6. 모든 tier가 0–xmax를 연속 coverage하고, label·WAV duration·중복·누락을
   전수 gate가 잡는가?
7. 4-core Windows·외장 SSD·100만 파일 규모에서 교착·queue·작은 파일 I/O·
   메모리·디스크 병목을 더 안전하게 줄일 방법이 있는가?

### 4.3 2020–2025 공통 발음 자원

다음 설계를 특히 비판적으로 검토한다.

- G2P model·parameter·기본 사전·phone mapping의 정확한 version/fingerprint
- 우리말샘 `pron_1/2`와 과거 `pron_g2p`의 출처 구분
- 사전 대표·대체 발음과 G2P 후보의 비파괴 보존
- 다의·품사·용언 어간·조사·어미의 안전한 조회
- search CSV용 정본과 MFA `.dict` 파생물의 분리
- 복수 발음 후보가 정렬을 악화시킬 위험
- 공통 release를 채택할 때 2020·2021 재실행과 baseline archive 정책

단순한 “dictionary override” 제안보다, 어떤 후보를 왜 포함했는지 재현할 수
있는 provenance와 A/B 검증 설계를 우선한다.

## 5. 리뷰 시 지켜야 할 제약

- 원자료와 D: corpus는 저장소에 없으며 수정 대상이 아니다.
- API key·개인정보·원자료 업로드를 요구하지 않는다.
- 실행 증거가 없으면 추정과 확인된 사실을 구분한다.
- 대량 작업을 실제로 시작하거나 GitHub에 push하지 않는다.
- destructive command, 기존 산출물 overwrite, broad delete를 제안하지 않는다.
- “테스트가 있다”는 이유만으로 안전하다고 결론내지 말고 그 시험의 범위를
  확인한다.
- legacy/폐기 스크립트와 현재 runner가 호출하는 활성 경로를 구분한다.

## 6. 원하는 피드백 형식

각 지적은 다음 형식으로 작성한다.

```markdown
## [P0|P1|P2|P3]-NN 짧은 제목

- 범위: CSV | pronunciation | MFA | TextGrid | recovery | performance | docs
- 위치: `path/to/file.py:line`
- 확신도: high | medium | low
- 확인한 근거:
- 재현 방법 또는 실패 시나리오:
- 연구 결과/자료 무결성 영향:
- 권장 수정:
- 반드시 추가할 시험:
- 대량 재실행 필요 여부:
- 다른 finding과의 의존성:
```

심각도:

- `P0`: 원자료·정본 손상, 광범위 잘못된 연구 결과, 복구 불가능
- `P1`: 거짓 성공, 대량 누락·오정렬, 재개/계약 파손, 연구 해석 혼동
- `P2`: 제한적 정확도·재현성·성능 문제
- `P3`: 유지보수·문서·가독성 개선

마지막에는 반드시 다음 표를 붙인다.

| 항목 | 내용 |
|---|---|
| 실제 검토한 파일 | 경로 목록 |
| 실행한 검사 | 명령과 결과 |
| P0/P1/P2/P3 수 | 각각의 수 |
| 먼저 고칠 5개 | 의존순서 |
| 추가 데이터가 있어야 판단할 항목 | 필요한 최소 read-only 통계 |
| 현재 대량 실행을 막아야 하는가 | yes/no와 근거 |

일반적인 칭찬이나 스타일 취향보다, 실제 실패 경로와 연구 방법에 영향을 주는
지적을 우선한다.

## 7. 사용자 전달용 짧은 요청문

별도 파일을 첨부하지 않는다. 다음 브랜치 주소 하나와 아래 프롬프트만 다른
도구에 붙여 넣으면 된다. 필요한 설명·범위·양식은 모두 저장소 안의 이 문서에
있다.

```text
https://github.com/ari28526-lab/nikl-dialogue-research/tree/agent/harden-pre-bulk-pipelines
```

```text
위 GitHub 브랜치를 읽기 전용으로 코드리뷰해줘. 별도 첨부자료는 없어.
저장소 안의 docs/reviews/HANDOFF_external_review_CSV_MFA_20260727.md를 먼저
끝까지 읽고, 그 문서에 적힌 연구 목적·코드 범위·제약·출력 형식을 그대로
따라줘.

범위는 일부 파일이 아니라 전체 CSV 구축 및 MFA 파이프라인이야. 특히
CSV–WAV–lab–TextGrid ID 연동, 형태소·철자 로마자, 사전/규칙/G2P 발음의
provenance, 2020–2025 공통 발음 자원, 대량 처리의 원자성·archive·재개,
거짓 성공·누락·교착·성능 병목을 실제 runner에서 호출되는 코드 경로를 따라
검토해줘. 문서의 주장과 코드·시험이 일치하는지도 역추적해줘.

답변 첫머리에 reviewed_commit_sha, 실제로 본 파일, 실제로 실행한 검사를
적어줘. 각 finding은 P0–P3 심각도, 정확한 파일:행, 확인 근거, 재현 가능한
실패 시나리오, 연구 자료/해석에 미치는 영향, 권장 수정, 반드시 추가할 시험,
대량 재실행 필요 여부를 포함해줘. 실행 증거가 없으면 사실과 추정을 구분해줘.

코드·GitHub·데이터는 수정하거나 push하지 말고, 리뷰 결과만 완전한
Markdown 원문으로 반환해줘.
```

## 8. 다시 Codex에 전달할 때

리뷰 결과를 요약하지 말고 원문 Markdown 전체와 `reviewed_commit_sha`를 함께
전달한다. 길면 `.md` 파일을 이 저장소의 `docs/reviews/incoming/`에 저장하고
파일 경로를 알려도 된다. Codex는 각 finding을 현재 HEAD에서 다시 재현한 뒤
`수용 / 일부 수용 / 기각 / 추가 증거 필요`로 분류하고, 사용자 승인 범위 안의
수정만 별도 commit으로 반영한다.
