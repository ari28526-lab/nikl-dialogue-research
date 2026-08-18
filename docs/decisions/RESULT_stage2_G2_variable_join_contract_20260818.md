# 2단계 G2 결과: 의미번호·어원·빈도 join 계약 동결

작성일: 2026-08-18 KST
전제: G1 query v1 동결(`RESULT_stage2_G1_query_freeze_20260818.md`), 연구자
G2 진행 지시(같은 날 세션).

## 결과

`config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json`을
동결했다.

- 계약 SHA-256:
  `12d811632a9c440e33fd76f814620c65e47113bdfda4ea058581b5e476c44050`
- G1 query SHA(`744bd8cb…`)에 결속. 이 계약은 join 규칙의 동결이며 실행
  승인이 아니다(G3부터 별도 GO).

## A3·A2 정본 위치 확정 (기존 미결 결정 ② 해소)

- **A3 빈도사전**: `D:\10_LAYERS\03_freq_dictionaries\` —
  `morpheme_freq_dictionary.csv`(165,920행, `etym_type/etym_origin` 포함),
  `eojeol_freq_dictionary.csv`, `sense_freq_dictionary.csv`,
  층화/분산도 표. ASSETS_LEDGER에 없던 위치를 실측으로 확정했다(대장 갱신은
  후속 정리 항목).
- **A2 의미번호 층**: `D:\10_LAYERS\02_sense_annotated\NIKL_DIALOGUE_<연도>_<판>\`
  세션 파일별 CSV, 스키마 `utt_id, word_idx, morph_idx, morph, tag,
  sense_id, confidence, method, candidates`.

## 핵심 실측 (계약의 근거)

1. **index 대응 검증**: A2 `(utt_id, word_idx, morph_idx)` ≡ 후보 표
   `(utt_id, eojeol_idx, morph_idx_in_eojeol)` — 2020 표본 세션의 경계행
   13개 좌·우 26위치 전부 표면형·품사까지 일치(26/26, 1-based 동일).
   토큰화 동일성 확인으로 join 키가 성립한다.
2. **A3 커버리지 probe**: 표본 경계 형태소 16/16이 사전에 존재.
   `etym_type` 빈값(용언류 등)과 `etym_origin` 후보 나열식
   (예: 여행→勵行|厲行|女行) 실측 → 계약에서 빈값은 `etym_unknown` 상태로
   보존, `etym_origin`은 참고 전용으로 고정.

## 계약 요지

- **sense join**: 위치 키 + 표면형·품사 동등성 가드. 불일치는 값 대체가
  아니라 상태(`morph_tag_mismatch`)로 기록. method 신뢰 규칙 내장
  (monosemous/lex_mono만 고신뢰, ls_*/lex_first는 MFS 주의 — 다의 표적의
  per-token sense로 자동 확정 금지, METHODS 신뢰도 지도 준거).
- **etym·freq join**: `(morph, tag)` 정확 일치. freq_* 코퍼스 카운트가 주
  변수, 외부 규준은 비교용. `boundary_etym_class` 파생 규칙(양측 한자어
  intra → `sino_internal_candidate` 등)으로 G1의 `etym_check_needed`를
  라우팅하되, 최종 분류는 연구자 확인 대상.
- **어절 빈도·층화·분산도**: 분석 단계의 2차 join으로 문서화(후보 생성
  단계 비포함).
- **G3 커버리지 감사 사양**: join률(상태·method별), etym 분포, zero-drop
  회계, 실패 조건을 계약에 명시.

## 다음 Gate

**G3** — 2020 단일 연도 생산 감사. 선행 조건: builder `--years` 런타임 필터
최소 추가 + 이 계약의 join 열을 후보 표에 붙이는 join 단계 구현(별도 파생
스크립트, builder 본체 무수정 원칙 유지 검토). 수량·열·상태만 감사, 새 청취
파일럿 금지. 실행은 연구자 GO 후.

## 안전 확인

MFA 0, D: 쓰기 0(읽기 전용 헤더·표본 probe만), A2/A3 원본 수정 0,
원자료·RC0/RC1·6-tier 수정 0.
