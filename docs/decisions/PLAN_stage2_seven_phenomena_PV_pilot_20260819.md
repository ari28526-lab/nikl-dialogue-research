# PLAN: 일곱 현상 공통 검색·검토 파이프라인 — PV 파일럿 (2026-08-19)

상태: **PV-A 구현·독립 감사 및 reviewer v2.1 사용자 최소 화면 Gate 완료**.
이 문서의 §5 작업은 사용자 GO 뒤 구현됐고, 2020–2025 각 30개·합계 180개
패키지가 생성됐다. 후속 연도별 30개 batch 구현은 아직 승인되지 않았다.

2026-08-22 후속 결정: 현재 reviewer의 `핵심/탐색` 표시는 일반적 형태론 환경과
저보고 탐색 환경의 연구 우선순위를 충분히 나타내지 못한다. 따라서 새 batch나
query 변경 전에 일곱 현상 전체의 직접 선행연구와 형태론 환경 분류를 먼저
정리한다. 같은 형태소 조합·표면 단어별 1차 묶음, 불확실 항목 재검토, 1–5
확신도는 이 근거 정리 뒤 별도 설계 Gate에서 확정한다. 진행 중인 Cowork 문헌
산출물은 승인 전까지 Git 밖 `work/`에 두며 본 계획의 동결 조건을 자동으로
바꾸지 않는다.

같은 날 추가한 후속 필수 요구사항: 청취 뒤 후보별 수동 TextGrid 조정과
사례별 가변 정보 보강 단계를 별도 Gate로 두고, `TextGrid 검토 필요/불확실`을
표시하면 같은 HTML 화면에서 read-only TextGrid 패널이 자동으로 펼쳐지는 것을
목표 사용성으로 한다. 원본 6-tier는 수정하지 않고 exact-ID overlay와 감사 뒤
정식 ledger에 반영하며, 현상별 공개 파생본을 재생성할 provenance를 보존한다.
구현 범위·정지선은
`REQUIREMENT_stage2_manual_textgrid_and_phenomenon_release_20260822.md`가 정본이다.

전제 문서:
- `PLAN_stage2_target_query_and_realization_design_20260818.md` (2단계 G0–G8 정본)
- ㄴ삽입 G1–G4 완료: 6개년 후보 941,903행, 연도별 독립 감사 6/6 passed
  (`RESULT_stage2_G4_full_six_year_candidates_20260818.md`)
- 검토 화면·표본·KOINA 원칙: 2026-08-19 계획 세션(본 문서 §1의 결정 기록)

## 1. 확정된 연구자 결정 (2026-08-19)

| ID | 결정 |
|---|---|
| D1 | ㄴ삽입 본검토 표본: **3축 층화(경계유형×어원분류×연도, 60칸) × 600건**. 희소층(sino_internal 등) 과표집, RC1 curated 6건 강제 포함. 빈도는 층이 아니라 분석 공변량. |
| D2 | 학기 완주 목표(실현 판정 ledger까지): **ㄴ삽입 → ⑤ ㄴㄹ·ㄹㄴ 연쇄** 2개 현상. |
| D3 | **개강 전 PV 스윕**: 일곱 현상 전부, 현상별 20건(부족하면 30–50건으로 증분) 미리듣기. |
| D4 | PV 표본은 **연도 혼합**(2020–2025 결정적 배분) — 연도별 자료 문제를 조기 발견. |
| D5 | **파일 간 문맥 포함**: `dialogue_id` 기준으로 다른 session 파일의 앞뒤 발화도 문맥 manifest에 보존하고, 원본 무수정 stitched 미리듣기 클립을 생성해 함께 청취. |
| D6 | ①경음화 ②ㄴ앞 비음화 ③ㄹ앞 비음화 ⑤ㄴㄹ·ㄹㄴ의 **형태소 내부 환경도 포함**하되 `environment_scope`(`morph_internal` / `intra_eojeol` / `inter_eojeol`)로 구분 표시. |
| D7 | PV의 목표는 **최종 CSV/JSON 필드의 확정**. 검토를 **PV-A(현재 자산만) / PV-B(KOINA·wav2vec2 등 보조층 활용 검증)** 2단계로 분리. |
| D8 | 질문 4·5·6(⑥⑦ 표면형/표제어형 기준·범주 목록·방언형 포함)은 **PV 관찰 항목으로 이관**. 문맥 창 기본 ±2 발화. KOINA·wav2vec2는 PV-B에서 소량만. 저장 정책(gzip/Parquet/D: 미러)은 대형 현상(① 등) 착수 전 결정. |

PV 청취 기록은 **탐색 전용**이며 정식 실현 판정 ledger(G7)와 절대 섞지 않는다.

## 2. PV-A 설계 — 현재 자산만으로

### 2.1 대상·규모·배분

7현상 × 20건 = 약 140건. 연도 혼합. 현상별 초안 배분(부족 칸은 인접 칸으로
재배분하고 결과를 manifest에 기록):

| 현상(PV 코드) | morph_internal | intra_eojeol 경계 | inter_eojeol | 비고 |
|---|---:|---:|---:|---|
| ① 경음화 (PT) | 6 | 7 | 7 | ㅎ·ㄶ·ㅀ 종성 제외(격음화 환경) — 관찰 후 확정 |
| ② ㄴ앞 비음화 (NAN) | 4 | 8 | 8 | ㅁ 앞 포함 여부는 관찰 메모 |
| ③ ㄹ앞 비음화 (NAL) | 8 | 8 | 4 | 한자어 단일어(격려류)가 내부형 핵심 |
| ④ ㄴ삽입 (NI) | — | 10 | 10 | 동결 후보 CSV에서 추출, RC1 curated 1건 포함 시도 |
| ⑤ ㄴㄹ·ㄹㄴ (LLN) | 8 | 8 | 4 | 내부 ㄴㄹ(신라류) 6 · ㄹㄴ 2 |
| ⑥ 모음조화 (VH) | — | 16 | — | 아계 8·어계 8 + 축약 보조 4(아래) |
| ⑦ 모음충돌 (HIA) | — | 12 | — | 비축약 12 + 축약 보조 8(아래) |

현상 번호 체계(`34_n_insertion`식)의 공식 부여는 각 현상 F0 정의 문서에서
확정한다. PV 코드는 임시 slug다.

### 2.2 draft query — 비동결·PV 전용

기존 선언형 schema(`nikl_dialogue_target_query_set.v1`)와 builder
(`scripts/python/build_db_v1_target_manifest.py`)를 **무수정 재사용**한다.
config는 `config/target_queries/pv_preview_*_20260819.json`로 저장하되:

- `query_role`은 `preview_environment_sweep` 계열 값으로 명시(생산 후보 아님)
- occurrence ID 충돌 방지를 위해 query_id에 `PV_` 접두
- 자체 SHA는 기록하지만 **동결(freeze) 승인 아님**을 `freeze_status`에 명시
- `max_occurrences_per_year` 상한으로 조기 중단(전수 스캔 회피)

경계형(`morph_boundaries`) 조건 초안 — 전부 draft이며 F1 동결과 무관:

- 공통: `left_unit_type=hangul`, `right_unit_type=hangul`
- PT: `left_coda_jamo in {ㄱ,ㄲ,ㅋ,ㄳ,ㄺ,ㄷ,ㅅ,ㅆ,ㅈ,ㅊ,ㅌ,ㅂ,ㅍ,ㅄ,ㄼ,ㄿ}`
  + `right_onset_jamo in {ㄱ,ㄷ,ㅂ,ㅅ,ㅈ}`; scope별 query 분리
- NAN: 같은 좌측 집합 + `right_onset_jamo = ㄴ`
- NAL: 같은 좌측 집합 + `right_onset_jamo = ㄹ`
- LLN: (a) `left_coda_jamo=ㄴ` + `right_onset_jamo=ㄹ` (b) `left_coda_jamo=ㄹ` + `right_onset_jamo=ㄴ`
- VH: `boundary_scope=intra_eojeol` + `left_pos regex ^V` + `right_pos regex ^E`
  + `right_onset_zero` + `right_nucleus_jamo in {ㅏ,ㅓ}`
- HIA: VH 조건에서 `left_coda_jamo eq ""`(빈 종성)
- VH/HIA 축약 보조: `orth_eojeol_tokens`에서
  `orth_eojeol_form regex (봐|봤|와|왔|줘|줬|해|했|돼|됐)$` 소량 —
  Bareun이 축약형을 어떻게 분절하는지 보는 P0 실측 겸용 표본

주의: builder의 상한은 파일 순서 선두 N건이므로 세션 편중이 생긴다.
→ 상한을 넉넉히(예: 연도당 200) 잡고, **표본기가 결정적 간격(stride)으로
연도·scope 할당량까지 축소**하는 2단 추출로 구현한다.

### 2.3 D1-lite 내부형 표본기

`morph_units`를 연도별 스트리밍하여 **같은 형태소 안의 인접 음절쌍** 중
좌 음절 coda·우 음절 onset이 현상 집합과 일치하는 발화를 상한 도달 시까지만
수집한다(읽기 전용, 조기 중단). 산출 행은 경계형과 같은 증거 열 체계 +
`environment_scope=morph_internal`.

구현 전 필수: `morph_units.csv.gz` 실제 헤더를 실측해(2020 1행)
인접쌍 키(형태소 내 unit 순서 열)를 확정할 것. 본 계획은 열 이름을 추정하지
않는다.

### 2.4 대화 문맥 manifest (±2, 파일 간 보존)

입력: `utterance_master_v2`(실측 확인 열: `dialogue_id, session_id, utt_seq,
start, end, dur, speaker_id, co_speaker_ids, has_wav …`) + RC0 ledger의
`textgrid_available/primary_status`.

occurrence×문맥발화 1행 schema(초안):

```text
pv_id, target_utt_id, relation(target|before_1|before_2|after_1|after_2),
year, dialogue_id, session_id, utt_id, speaker_id, utt_seq,
source_start, source_end, source_dur, same_file_as_target,
wav_status, textgrid_status, alignment_family, form(문맥 표시용)
```

다른 파일의 발화도 행으로 보존하고 상태만 표시한다. 삭제 금지.

### 2.5 bundle·미리듣기·검토기

- 번호순 flat: `NNN__현상__연도__utt_id/` 아래 `target.wav`,
  `context_pm2.wav`(±2 stitched, `stitch_session.py` 재사용·역환산 manifest
  필수), 대상 발화 6-tier TextGrid **사본**(읽기 전용 표기), `row.csv`(근거).
- `INDEX.html`: 오디오 재생 + 문맥 텍스트(파일 간 상태 표시) + 환경 근거 +
  관찰 메모 입력(localStorage 저장, JSONL 내보내기). 동일 내용의
  `REVIEW.csv` 병행 생성(Excel 폴백). 도구 사용감 자체가 PV 관찰 항목.

### 2.6 PV 기록 schema (탐색 전용, append-only)

```text
pv_id, phenomenon_code, pv_query_id, environment_scope, year, utt_id,
occurrence_ref, listened, env_impression(env_ok|env_wrong|unsure),
realization_impression(자유 기술), audio_quality_note,
context_sufficient(yes|need_more_before|need_more_after|need_other_file),
missing_info_note(최종 schema에 필요한 정보 제안),
schema_field_suggestion, tool_note, reviewer, reviewed_at
```

### 2.7 산출물 경로

`outputs/pilots/pv_seven_phenomena_20260819/` 아래
`samples/ context/ bundle/ audit/ PV_MANIFEST.json`.
기존 출력 비덮어쓰기, `.partial` 원자 승격, 파일 SHA manifest.

### 2.8 감사·합격 기준 (독립 감사기)

- 표본 수 회계: 배분표 대비 현상·scope·연도별 정확 일치(재배분 기록 포함)
- 경계형 조건 전수 재평가(draft config 재적용) / 내부형 자모 재검증
- 문맥 manifest: dialogue_id 내 utt_seq 연속·중복 0, 파일 간 발화 보존 확인
- stitch 역환산: 클립 길이 = Σ원구간 + 경계 무음(허용오차 내)
- 동결층·원자료 쓰기 0, MFA·KOINA·wav2vec2 실행 0
- 합격 = 감사 JSON `passed` + 사용자 청취 개시 가능

## 3. PV-B 설계 — 보조층 활용 검증 (이번 구현 범위는 "환경 점검 문서"까지)

- 대상: PV-A 표본의 부분집합(현상별 5–10건; 어절 간 후보와 ⑥⑦ 우선).
- 목적: KOINA·wav2vec2·(필요시 Praat 측정)가 **최종 CSV/JSON에 기여할 열**,
  값의 신뢰도·비용, 후보 지위 표시 방식 확인. 실현 판정 아님.
- 선행 조건(U4): 2026-07-15 KOINA Colab 파일럿 산출물(prosody_utts.csv,
  TextGrid 500) 실물 위치 확인, KOINA v1.1.0·Momel(Linux 전용) 재현 절차,
  임계값 v0 기록. wav2vec2는 후보 모델·라이선스·로컬 실행 가능성 조사만.
- 산출 후보 열(그룹 7 초안): `koina_f0_targets_json`, `koina_word_auto_*`,
  `prosody_ap_ip_candidate(+confidence, rule_version)`,
  `w2v_phone_candidates_json(+model_id)`, 음향 측정 long-form 표 참조
  (`DECISION_post_search_acoustic_measurement_tooling_20260814.md` schema 재사용).
- 실행은 별도 승인. 대량 음성 처리 금지 유지.

## 4. 최종 산출물 필드 골격 v0 (PV가 검증·확정할 대상)

```text
[1 식별]    phenomenon_id, target_occurrence_id, query_sha, year, utt_id,
            dialogue_id, session_id, speaker_id
[2 환경]    environment_scope, 좌·우 형태소/품사/자모 근거, match_evidence
[3 표기]    form/original_form 대조 신호, pron_pred(의무규칙 예상형),
            pron_reference(사전 참조)
[4 의미어원] sense 상태·후보·사람 선택(ledger), etym_type, 빈도(코퍼스/LS)
[5 문맥]    ±N 발화(파일 간 상태 포함), 원 시간 좌표, stitch 역환산 참조
[6 시간자산] word 문맥 span, WAV/TextGrid 존재 상태
[7 보조층]  koina_*, w2v_*, 음향 측정 — 도구·버전·후보 지위 명시 (PV-B 확정)
[8 판정]    A(환경)/B(실현)/C(제외) 분리 + 근거·supersedes·reviewer·시각
[9 사회변수] sex, age_norm, category_norm(사용역) 등
```

JSON은 세션 JSON 설계(`PLAN_post_production_recovery_target_manual_session_json_20260814.md`)를
상속한 교환용 view이며 CSV가 분석 정본이다.

## 5. 구현 작업 목록 (외부 도구 대상, 사용자 GO 후)

| # | 산출물 | 핵심 명세 |
|---|---|---|
| 1 | `config/target_queries/pv_preview_boundary_20260819.json` (+축약 보조) | §2.2 draft 조건, PV 전용 표시 |
| 2 | `scripts/python/build_pv_preview_samples.py` | builder 재사용 호출 + ㄴ삽입 완성본 stride 추출 + 배분표 축소, zero-drop 회계 |
| 3 | `scripts/python/scan_pv_morph_internal_lite.py` | §2.3 D1-lite, 헤더 실측 선행, 조기 중단 |
| 4 | `scripts/python/build_pv_context_manifest.py` | §2.4, 파일 간 보존 |
| 5 | `scripts/python/build_pv_review_bundle.py` | §2.5, stitch 재사용, HTML+CSV 병행 |
| 6 | `scripts/python/audit_pv_preview.py` | §2.8, 생성기와 분리 |
| 7 | `run_pv_preview_pilot.ps1` | UTF-8 BOM, PS 5.1, detached+로그, `-PreflightOnly` |
| 8 | `docs/decisions/RESULT_pv_preview_build_20260819.md` 초안 | 실측 수치·감사 결과 기록 |
| 9 | PV-B 환경 점검 노트(문서만) | §3 선행 조건 확인 결과 |

## 6. 안전 규칙 (요약 — CLAUDE.md 전문이 우선)

1. `D:\00_RAW`·검색 7표·RC0/RC1·r3 DB·동결 6-tier·동반표·ㄴ삽입 G1–G4
   산출물은 읽기 전용. 수정·삭제·이동 금지.
2. MFA·KOINA·wav2vec2 실행 금지(PV-A 범위 밖). 전수 스캔 대신 상한 조기 중단.
3. 신규 출력은 `outputs/pilots/pv_*` 아래에만. 기존 출력 비덮어쓰기,
   `.partial` 원자 승격, manifest+SHA.
4. 자동 실현 판정 금지. PV 기록은 탐색 전용으로 분리.
5. `.ps1` UTF-8 BOM 필수, Windows PowerShell 5.1 호환,
   Python은 `C:\Users\ari30\miniforge3\envs\mfa\python.exe`.
6. 변경마다 py_compile·구문 검사·대표 시나리오 dry test, 로그 파일 보존.
7. 커밋은 사용자 지시 시에만. D: 대량 I/O를 다른 D: 작업과 겹치지 않기.

## 7. 미결 사항 (PV 관찰로 확정)

- ⑥⑦ 표면형 vs 표제어형 기준, 활음화·탈락·축약 범주 목록, 방언형 포함(질문 4·5·6)
- 문맥 창 ±2의 적정성, stitched 미리듣기 형식
- 검토 도구 기본안(HTML vs Excel) 확정
- 보조층 열의 최종 채택(PV-B), ①경음화 등 대형 현상의 저장 정책
- 현상 번호·slug 공식 부여(F0), ㄴ삽입 600건 본검토 세부 층화표
