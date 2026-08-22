---
title: "외부 설계 검토: 2단계 일곱 현상 PV 파일럿"
subtitle: "계획 §2–§6 · 구현 전 Gate"
date: "2026-08-19"
lang: ko
format:
  html:
    toc: true
    toc-depth: 3
    number-sections: true
    embed-resources: true
    theme: cosmo
    smooth-scroll: true
---

<style>
body { max-width: 1180px; margin: 0 auto; padding: 2rem; line-height: 1.62; }
table { display: block; overflow-x: auto; border-collapse: collapse; }
th, td { padding: .45rem .65rem; border: 1px solid #d9dee3; vertical-align: top; }
th { background: #f4f6f8; }
code { overflow-wrap: anywhere; }
blockquote { border-left: 4px solid #b42318; padding-left: 1rem; color: #4a1d18; }
@media (max-width: 720px) { body { padding: 1rem; } }
</style>

# 검토 결론

**판정: 조건부 NO-GO — 아래 P0 네 항목을 계획 문서에 반영하기 전에는 구현을
시작하지 않는 것이 안전하다.**

검토 대상은
`docs/decisions/PLAN_stage2_seven_phenomena_PV_pilot_20260819.md` §2–§6이며,
검토한 파일의 SHA-256은
`da11f54d8419ad0b56849766b53cf1f474716a07776e202cff99ffbff9b1b0f2`다.
검토 시각은 2026-08-19 14:49 KST다.

계획의 큰 방향은 적절하다. 특히 PV 기록을 정식 실현 ledger와 분리하고,
현재 자산만 쓰는 PV-A와 보조층을 검증하는 PV-B를 분리하며, ㄴ삽입 G1–G4
산출물을 재사용하는 원칙은 유지할 가치가 있다. 그러나 현재 문안대로는 다음
네 문제가 구현 단계에서 안전 중단 또는 잘못된 합격을 일으킨다.

| 우선순위 | 결론 | GO 전에 필요한 최소 수정 |
|---|---|---|
| P0-1 | `max_occurrences_per_year`만으로는 희귀 query의 전수 스캔을 막지 못함 | `max_rows_scanned_per_year` hard cap과 종료 상태를 계약에 추가 |
| P0-2 | 결정적 연도 배분 규칙이 없고, 선두 N건 뒤 stride는 세션 편중을 해소하지 못함 | 현상×scope×연도 할당 알고리즘과 세션당 상한을 사전 고정 |
| P0-3 | 현재 `dialogue_id`와 `stitch_session.py`로는 “다른 session 파일” 문맥을 만들 수 없음 | 동일 session 내 문맥으로 범위를 좁히거나 별도 cross-file chain key를 제공 |
| P0-4 | 선택행의 word 시간 연결 단계가 작업 목록에 없고 기존 linker가 PV role을 거부함 | 선택행 전용 time-link 규칙을 작업 4 또는 5에 명시 |

위 수정은 계획 §5의 작업 1–9 안에서 처리할 수 있다. 새 연구 단계나 대량 처리를
추가할 필요는 없다.

# P0: 구현 전 반드시 고칠 항목

## P0-1. occurrence 상한은 스캔 상한이 아니다

계획 §2.2는 `max_occurrences_per_year`로 조기 중단해 전수 스캔을 피한다고
기술한다. 실제 builder는 일치 건수가 상한에 도달할 때만 중단한다
(`scripts/python/build_db_v1_target_manifest.py:198–210`). 희귀 query가 상한에
못 미치면 gzip 끝까지 읽는다. 연도별 0건이면 끝까지 읽은 뒤 오류를 낸다.

2026-08-19에 각 연도 `morph_boundaries.csv.gz`를 **최대 200,000행까지만** 읽은
probe에서 NAL 경계형 일치 건수는 다음과 같았다.

| 연도 | NAL intra_eojeol | NAL inter_eojeol |
|---:|---:|---:|
| 2020 | 0 | 4 |
| 2021 | 0 | 9 |
| 2022 | 7 | 1 |
| 2023 | 0 | 19 |
| 2024 | 4 | 33 |
| 2025 | 3 | 43 |

따라서 “연도당 200건”은 NAL에서 조기 중단 조건이 아니라 전수 스캔 유발
조건이 될 가능성이 높다. `morph_units`도 같은 위험이 있다. 2020 실측 행 수는
8,581,967행이다.

최소 수정안은 두 상한을 분리하는 것이다.

```text
max_hits_per_query_year
max_rows_scanned_per_table_year
```

종료 상태도 `quota_met`, `row_cap_reached_with_shortfall`, `source_exhausted`로
구분하고, 부족분은 manifest의 재배분 장부에 남겨야 한다. builder 본체를
수정하지 않으려면 `build_pv_preview_samples.py`가 query 조건 평가 함수만
재사용하고, PV용 bounded scanner를 소유하는 편이 단순하다.

## P0-2. 연도 배분 규칙이 없고 stride는 세션 편중을 고치지 못한다

D4는 2020–2025의 “결정적 배분”을 확정했지만 §2.1에는 scope 총량만 있고
연도별 할당표 또는 알고리즘이 없다. 반면 §2.8 감사기는 현상·scope·연도별
정확 일치를 요구한다. 구현기가 임의로 배분 규칙을 발명하지 않고는 이 감사를
통과시킬 수 없다.

또한 파일 순서 선두 200건을 받은 뒤 stride를 적용해도 모집단 전체로 퍼지지
않는다. 실제로 §2.2 조건을 재현하여 각 query의 첫 200건을 측정한 결과, 밀집
query의 고유 session 수는 다음과 같았다.

| 연도 | PT intra 첫 200 | VH 첫 200 | HIA 첫 200 | morph-internal PT 첫 200 |
|---:|---:|---:|---:|---:|
| 2020 | 3 | 2 | 2 | 6 |
| 2021 | 3 | 2 | 2 | 4 |
| 2022 | 3 | 1 | 2 | 3 |
| 2023 | 3 | 2 | 2 | 4 |
| 2024 | 3 | 2 | 3 | 4 |
| 2025 | 4 | 4 | 5 | 8 |

즉 stride는 “초기 1–8개 session 내부”에서만 간격을 벌린다. 현상별 20건짜리
PV라도 화자·session·초기 파일 편중이 너무 커서 연도별 자료 문제를 보는 D4
목적을 약화한다.

더 단순한 수정안은 다음 세 규칙을 계획에 고정하는 것이다.

1. 현상별 20건의 연도 quota를 명시한다. 예: `[4,4,3,3,3,3]`을 현상별로
   회전해 여섯 연도를 모두 포함한다.
2. 각 scope quota 안에서 `max_samples_per_session=1`을 우선 적용하고, 부족할
   때만 2로 완화한다. 완화 이유를 manifest에 기록한다.
3. hit cap과 별도로 row cap을 두고, `min_distinct_sessions` 충족 여부를
   합격 기준에 넣는다.

대표성이 목적이 아닌 PV라면 이 표본을 “통계 표본”으로 포장할 필요는 없다.
다만 `sampling_frame=head-bounded_preview`와 남은 편향을 manifest에 명시해야
한다.

## P0-3. `dialogue_id` 기반 cross-session 문맥은 현재 자산으로 성립하지 않는다

계획 D5와 §2.4는 같은 `dialogue_id`의 앞뒤 발화를 다른 `session_id`에서도
보존한다고 한다. 현재 master와 생성 코드는 다음 구조다.

- `build_search_master.py`는 session JSON 파일 하나를 열고 그 안의
  `document[].id`를 `dialogue_id`로 저장한다(`:145–176`).
- 2020 첫 행은 `session_id=SDRW2000000001`,
  `dialogue_id=SDRW2000000001.1`이다.
- 각 연도 master 선두 20,000행씩, 합계 120,000행을 제한 probe한 결과
  `dialogue_id`의 prefix와 `session_id`가 다른 행은 0건, 하나의
  `dialogue_id`가 둘 이상의 `session_id`에 걸친 경우도 0건이었다.
- `stitch_session.py`는 `--around`의 첫 점 앞 문자열을 session으로 삼고,
  그 session의 CSV 하나만 정렬한다(`:151`, `:198–210`). manifest 입력이나
  cross-session 모드는 없다.

따라서 현재 계약에서 `dialogue_id`는 cross-session 연결 키로 검증되지 않았다.
이 상태로 “파일 간 보존” 감사를 만들면 항상 0건을 성공으로 보거나, 존재하지
않는 관계를 추정하게 된다.

GO 전 사용자 결정이 필요한 최소 선택지는 둘 중 하나다.

- **권장 단순안:** PV-A는 `dialogue_id` 안의 실제 행 순서 ±2, 즉 현재 실측상
  동일 session 내부 문맥으로 제한한다. 대화 처음/끝의 없는 slot은 상태행으로
  보존한다.
- **D5 유지안:** cross-file 대화를 정의하는 검증된 `context_chain_id`와
  session 간 순서표를 별도 입력으로 지정한다. 현재 계획에는 이 자산이 없다.

## P0-4. 선택행 시간 연결 계약이 빠져 있다

ㄴ삽입 G1–G4 joined CSV의 `target_xmin`, `target_xmax`는 실측 첫 행에서 모두
빈 문자열이고 `timing_status=pending_textgrid_interval_link`다. 기존
`link_db_v1_target_intervals.py`는 `candidate_environment_pilot`만 처리하며,
계획이 새로 쓰려는 `preview_environment_sweep`와 ㄴ삽입의
`production_candidate_environment`는 `pending_unsupported_query_role`로
보낸다(`:128–136`).

추가로 축약 보조 query의 `orth_eojeol_tokens` 증거에는 linker가 기대하는
`left_eojeol_idx/right_eojeol_idx`가 없고, 내부형은 별도 `morph_units` 증거다.
그런데 §5 작업 목록에는 linker 확장 또는 선택행 time-link 작업이 없다.

최소 수정안은 G5 전수 적용을 여는 것이 아니라, 선택된 약 140행에만 다음 규칙을
작업 4 또는 5 안에 넣는 것이다.

| 표본 종류 | review word span 규칙 |
|---|---|
| boundary | `left_eojeol_idx..right_eojeol_idx` |
| morph_internal | 해당 `eojeol_idx` 한 interval |
| orthographic contraction probe | `orth_eojeol_idx` 한 interval |
| TextGrid 없음/불일치 | 행 유지 + 명시적 pending 상태 |

이 선택행 linker는 좁은 음운 경계를 주장하지 않으며, 원 TextGrid SHA와 사용한
tier 이름을 함께 기록해야 한다.

# P1: 설계 정확성·감사 가능성 위험

## P1-1. §2.4의 열 이름과 실제 source가 다르다

2020 `utterance_master_v2.csv.gz` 헤더는 `dialogue_id, session_id, utt_seq,
start, end, dur, speaker_id, co_speaker_ids, has_wav`를 포함한다. 그러나
`has_wav` 첫 행 값은 `미계산`이며 실제 자산 상태로 쓸 수 없다.

RC0 ledger 실제 열은 다음과 같다.

```text
primary_status, status_family, textgrid_available, followup_required,
alignment_scope, evidence_key
```

계획 schema의 `alignment_family`는 두 입력 어디에도 없다. `status_family`를
그 이름으로 명시 매핑할지, 출력 열도 `status_family`로 유지할지 고정해야 한다.
`wav_status`는 master의 `has_wav`가 아니라 후보 manifest의 실제 path 검사와
RC0/RC1 provenance로 파생해야 한다.

## P1-2. “대상 발화 6-tier TextGrid 사본”은 RC1 curated와 충돌한다

ㄴ삽입 G4에는 RC1 curated 발화 6건이 포함되며 PV는 그중 1건 포함을 시도한다.
실제 curated active TextGrid 한 건의 tier는 다음 네 개였다.

```text
words_d9_reference / phones_d9_reference /
transcript_proposed / words_manual_working
```

반면 r3 base TextGrid는 고정 6-tier다. recovery curated 발화는 base 6-tier가
없을 수 있으므로 bundle 계약을 “active TextGrid 사본 + `textgrid_family`와
tier inventory”로 바꿔야 한다. base와 curated가 둘 다 있으면 역할을 붙여 둘
다 복사할 수 있지만, curated 4-tier를 6-tier라고 표시하면 안 된다.

## P1-3. 기존 stitcher는 zero-drop이 아니다

`stitch_session.py`는 WAV 부재 또는 채널·표본률·표본폭 불일치 시 행을
`continue`로 건너뛰고 `skipped` 총계만 출력한다(`:238–250`). 입력 context 행별
상태와 사유가 manifest에 남지 않는다. 이는 “입력 = 출력 + 상태” 규칙과
충돌한다.

CLI를 그대로 호출하기보다 작업 5의 bundle builder가 확정 context manifest를
입력으로 받아 exact 행만 잇고, 모든 slot에 `stitch_status`와 이유를 쓰는 편이
단순하다. 기존 stitcher에서는 WAV write·gap·좌표 역산 helper만 재사용할 수 있다.

## P1-4. `utt_seq`의 숫자 연속성은 실제 불변식이 아니다

§2.8은 `dialogue_id` 내 `utt_seq` 연속을 요구한다. 각 연도 20,000행 제한
probe에서 숫자 gap이 있는 dialogue는 2021년 34/63, 2022년 23/60이었다.
예를 들어 `SDRW2100000001.1`은 139 다음이 141이고, 155 다음이 157이다.

문맥 ±2는 `utt_seq±1/±2`가 아니라 **같은 dialogue의 실제 존재 행을 숫자순으로
정렬한 뒤 target의 rank 앞뒤 두 행**으로 정의해야 한다. 감사도 숫자 차이 1이
아니라 rank, 유일성, same-dialogue, relation 방향을 확인해야 한다.

## P1-5. VH와 HIA 표본 중복 정책이 없다

계획 조건상 HIA는 VH의 부분집합이다. 같은 occurrence가 두 현상 quota에 동시에
들어갈 수 있지만, 140건이 현상별 review event 수인지 고유 음성 수인지 정의가
없다. `pv_id`, `occurrence_ref`, 최종 `target_occurrence_id`의 관계도 고정되지
않았다.

PV에서 가장 단순한 정책은 다음 중 하나를 명시하는 것이다.

- 고유 occurrence는 하나만 materialize하고 `phenomenon_memberships_json`으로
  VH/HIA 복수 소속을 기록한다.
- 도구 사용감 비교를 위해 현상별 review event를 둘 만들되
  `source_occurrence_key`가 같음을 명시하고 고유 음성 수를 별도 보고한다.

축약 보조 regex는 `와/왔/해/돼` 등의 동형어를 포함할 수 있다. 이를 환경
판정으로 취급하지 말고 `surface_regex_probe`로 이름 붙여 Bareun 분절 관찰용임을
audit에 명시해야 한다.

## P1-6. 여섯 현상의 언어학적 draft 계약이 부족하다

현재 `phenomena/` 아래 정의 문서는 `34_n_insertion` 하나뿐이다. PT/NAN/NAL/LLN/
VH/HIA는 공식 F0 정의 전이며, PT·NAN·NAL이 같은 철자 coda 집합을 공유하는
근거와 겹받침 처리 원칙도 아직 없다. 생성기와 audit가 같은 draft config만
재평가하면 “config대로 뽑힘”은 증명해도 현상 조작화의 타당성은 증명하지 못한다.

구현 작업 1의 config에 최소한 다음을 넣으면 새 문서를 추가하지 않고도 위험을
줄일 수 있다.

```text
linguistic_scope_note
orthographic_candidate_only=true
known_false_positive_classes
known_false_negative_classes
positive_and_negative_hand_cases
```

## P1-7. localStorage는 append-only ledger가 아니다

브라우저 localStorage는 같은 key를 덮어쓸 수 있고 브라우저·경로별로 분리되며,
삭제될 수 있다. `REVIEW.csv`도 사용자가 직접 편집하면 append-only provenance가
없다.

PV 기록의 정본을 “HTML이 내보내는 event JSONL”로 한정하고 다음 열을 추가하는
것이 안전하다.

```text
pv_schema_version, review_event_id, supersedes_event_id,
bundle_manifest_sha256, exported_at
```

`REVIEW.csv`는 빈 Excel 폴백 template 또는 JSONL의 파생 view로 표시해야 한다.
PV 기록을 정식 G7 ledger와 분리한다는 원칙은 그대로 유지한다.

## P1-8. 독립 감사와 실패 산출물 보존을 구현 규칙으로 명시해야 한다

기존 G3 audit는 query 조건 재평가 때 builder 모듈을 import한다. PV audit는
계획대로 생성기와 독립이어야 하므로 query matcher, 내부형 인접성, 문맥 rank,
stitch 길이 식을 생성기에서 import하지 않고 다시 구현해야 한다.

또한 기존 builder와 linker는 예외 때 `.partial`을 삭제한다. CLAUDE.md의 실패
증거 보존 원칙을 PV에서는 우선해야 한다. 실패 시 `.partial`을 자동 삭제하지
말고 `FAILED.json`과 로그를 남기며, 재실행은 기존 partial을 발견하면 중단하도록
계약을 명확히 해야 한다.

## P1-9. PV-B의 역사 산출물은 provenance 복구 전 재사용하면 안 된다

로컬에는 `scripts/colab/prosody_pilot_colab.py`와 실행 안내가 있지만, 현재
파일시스템에 G: 드라이브가 마운트되어 있지 않아 2026-07-15의
`prosody_utts.csv`와 TextGrid 500개 실물을 확인하지 못했다.

추가로 실행 안내는 KOINA 저장소의 특정 tag/commit이 아니라 기본 branch를
clone한다. 스크립트는 KOINA import가 실패해도 Parselmouth-only로 계속하고,
CSV에는 KOINA 사용 여부·commit·도구 버전·규칙 버전을 행별로 기록하지 않는다.
따라서 기존 파일 이름만 보고 KOINA v1.1.0 결과라고 확정할 수 없다.

작업 9의 환경 점검 노트는 다음을 확인하기 전까지 `not_verified`로 닫는 것이
맞다.

- 실물 root, 500 TextGrid와 CSV 행 수, 파일 SHA manifest
- KOINA exact commit/tag, Momel 실행 여부, Python/package 버전
- v0 임계값과 스크립트 SHA
- 실패·누락 0인지 또는 입력 = 출력 + 상태 회계
- wav2vec2 후보 모델의 model ID·revision·license·phone inventory

이번 구현 범위에서는 문서 확인까지만 하고 KOINA·wav2vec2를 실행하지 않는다.

# 더 단순한 승인안

현재 §5 작업 1–9를 유지하면서 다음 흐름으로 축약하는 것을 권장한다.

```text
1. draft query config + 고정 quota/row cap/session cap
2. boundary 표 1-pass bounded scan + 기존 ㄴ삽입 bounded head frame
3. morph_units 1-pass bounded scan
4. 단일 PV_SAMPLES.csv로 zero-drop 통합
5. 선택행만 master/RC0/RC1 + word span + dialogue-rank ±2 연결
6. manifest-driven stitch + active TextGrid family 보존 bundle
7. 독립 audit
8. wrapper preflight
9. RESULT 초안 + PV-B 환경 점검 노트
```

중간 정본은 `PV_SAMPLES.csv` 하나로 두고, 이후 context/bundle은 이 표를
append-only로 확장한다. boundary, internal, contraction helper마다 서로 다른
중간 폴더 계약을 만들 필요가 없다. 모든 행에는 다음 공통 상태를 둔다.

```text
selection_status
selection_shortfall_reason
asset_status
timing_status
context_status
stitch_status
bundle_status
```

이렇게 하면 zero-drop 식을 단계별로 동일하게 유지할 수 있다.

# 실측 근거

## 동결 ㄴ삽입 산출물

대형 CSV를 다시 전수 스캔하지 않았다. 각 로컬 build/join manifest, 연도별 독립
audit JSON, D: mirror의 50파일 `source_match=true`와 `sha_mismatches=0`을 실제로
열어 대조했다.

| 연도 | joined 행 | joined CSV SHA-256 | audit status | audit JSON SHA-256 |
|---:|---:|---|---|---|
| 2020 | 101,638 | `c6f7e38870dede95e2fbf2156f0b0a1d4f858b09fcf5e36a455a844639ecb428` | passed | `431ea4c3c46ef8caef8070e03eeff2cde78138f4c55a577bcede461103722239` |
| 2021 | 206,037 | `c4b2852555ffd972832a843003c4d559244c277aa928e2f9d3b04e9f6543c83e` | passed | `96bae5a85b16bb3e3b882fb7821bc3ffd485be653a769e414aa2a2de210d53ff` |
| 2022 | 141,966 | `f998a7576f5dde4075e9ff46d8f07ec89ee86354ac33b7d437b2d34e6eba0aef` | passed | `7bf224dc6e173b652b85d41273ee79dd8570869f5d56bbc04c76b36eef04e5f2` |
| 2023 | 123,381 | `bb6f6f11a692a731c0825754243ecce2db580ebb6b7512f482e0edc8d3e862fe` | passed | `da23904ba00c03f401e0719a050c4df9ff8ec9431a14fe77c44efe8dc6af46a7` |
| 2024 | 185,401 | `65be77ced62ea988db839ea3c61267dd200e3a828bc823e50d06e3e17152c2c5` | passed | `60d5c7b1532b497e419e1952b04a4f77be67352bf264afa8e043c5782138246e` |
| 2025 | 183,480 | `3810bae23fda87f3c0baf1c3cd4ee5baee9b9ae8e15c58dcb40ac6a6a61e652b` | passed | `c1ff2ba9da07a0354c49db3f4f77d9615f41f255d823987d582133baaf07fb2e` |
| **합계** | **941,903** | — | **6/6 passed** | — |

정본 위치는
`outputs/candidates/n_insertion_v1_<year>_g3|g4_joined_20260818/`이고,
감사는 `outputs/reports/AUDIT_stage2_g3|g4_n_insertion_<year>_20260818.json`이다.

D: mirror manifest:

```text
D:\30_RELEASES\stage2_n_insertion_candidates_20260818\PACKAGE_MANIFEST.json
files=50
total_bytes=5,289,809,900
sha_mismatches=0
manifest_sha256=292822164bebdb136d07379f6504f002ef1b0eeb7a5aa854ad4ece75cfb6c3e0
```

동결 config 실제 SHA:

```text
config/target_queries/n_insertion_production_v1_20260818.json
744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6

config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json
12d811632a9c440e33fd76f814620c65e47113bdfda4ea058581b5e476c44050
```

## 2020 gzip 헤더 1행 실측

입력 root:
`D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801\2020\annual_tables`

| 표 | manifest 행 | gzip bytes | manifest SHA-256 | 이번 설계에 필요한 실제 열 |
|---|---:|---:|---|---|
| `morph_units.csv.gz` | 8,581,967 | 167,800,831 | `1b93635cdd837cac5965e7732d220d757a29f498bbd22ce624fdb684e333c2f8` | `eojeol_idx, morph_idx_in_eojeol, unit_idx_in_morph, unit_count_in_morph, unit_type, onset_jamo, coda_jamo` |
| `morph_boundaries.csv.gz` | 4,897,069 | 92,216,281 | `540c0fc86d2db02730585fcdd938c371bdf28b482c6362250f3e96f59869d6eb` | `boundary_scope, left/right_eojeol_idx, left/right_pos, left/right_unit_type, left_coda_jamo, right_onset_jamo, right_onset_zero, right_nucleus_jamo` |
| `utterance_master_v2.csv.gz` | 870,437 | 156,887,318 | `d1075693a74e140ec6e81ca62d2de51e4232de85961ce2cee7a79017fce87cfb` | `dialogue_id, session_id, utt_seq, start, end, dur, speaker_id, co_speaker_ids, form` |
| `orth_eojeol_tokens.csv.gz` | 3,042,451 | 43,788,850 | `3d04dd8ccf0f8e91795826f206ebc38cce572c942f6ff4b1069fc947822a33e5` | `orth_eojeol_idx, orth_eojeol_form, linked_morph_eojeol_idx, morph_link_status` |

`morph_units`의 형태소 내부 인접쌍 키는 추정이 아니라 다음으로 확정할 수 있다.

```text
(utt_id, eojeol_idx, morph_idx_in_eojeol) 동일
unit_type == hangul 양쪽
right.unit_idx_in_morph == left.unit_idx_in_morph + 1
```

RC0 2020 ledger는 870,437행, SHA-256
`dd68cae7a8b29784628d9f69b766f1d1f614d4b0b559ba1eeca6694ecca9cd43`이며,
manifest는
`outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/ledgers/2020_LEDGER_MANIFEST.json`
이다.

# GO 후 구현 전 preflight에서 다시 확인할 항목

다음은 설계 검토에서 확인했거나, 구현 직전 실제 자산으로 재확인해야 할 항목이다.

| 항목 | 확인 방법 | 합격 기준 |
|---|---|---|
| 출력 보호 | final root와 모든 `.partial` 존재 검사 | 둘 다 부재; 있으면 FileExistsError |
| 동결 입력 결속 | query/join SHA와 연도 manifest SHA 확인 | 위 동결 SHA 일치, annual status success |
| 6개년 헤더 | 각 연도 gzip 헤더+1행 | 필요한 열 전부 존재; 2020 추정 확장 금지 |
| bounded scan | query별 rows read/hits/sessions 기록 | hard row cap 초과 0; `source_exhausted`를 성공으로 위장 0 |
| 표본 quota | 사전 고정 year×scope matrix 대조 | 원 quota = selected + shortfall/reallocated |
| 세션 다양성 | query pool과 최종 sample 집계 | 사전 `min_distinct_sessions` 충족 또는 명시적 shortfall |
| occurrence identity | PV/boundary/internal/helper 키 재계산 | 중복 0; VH/HIA 중복 정책과 일치 |
| 문맥 | dialogue 실제 rank 재계산 | target 1, relation 중복 0, 없는 slot도 상태 보존 |
| 자산 상태 | RC0+RC1+실제 path | 조용한 삭제 0; active/base family 구분 |
| TextGrid | tier inventory·길이·SHA | family 허용목록 일치; word span 실패는 pending 보존 |
| stitch | WAV frame 수로 독립 재계산 | 출력 길이 = 유효 clip frame 합 + gap frame 합 |
| PV 기록 | JSONL event validation | schema/version/event ID 필수; G7 ledger와 경로 분리 |
| PV-B | 역사 산출물 실물·provenance | 확인 전 `not_verified`; 모델 실행 0 |
| PowerShell | safety/runtime tests + BOM 3바이트 | Windows PowerShell 5.1 통과, `EF BB BF` |

# 미해결 질문

GO 전에 사용자가 확정해야 하는 질문은 세 가지다.

1. D5를 현재 자산에 맞춰 **동일 session의 dialogue-rank ±2**로 제한할지,
   아니면 별도 cross-file `context_chain_id` 자산을 제공할지.
2. 20건의 연도 quota를 어떤 결정적 규칙으로 배분할지. 권장 기본값은 여섯
   연도 모두 포함 + 현상별 `[4,4,3,3,3,3]` 회전이다.
3. VH/HIA가 겹치는 occurrence를 하나의 음성·복수 membership으로 볼지,
   현상별 독립 review event로 볼지.

이 세 질문과 P0 수정이 계획 정본에 반영되면 구현 GO가 가능하다. 그 전에는
코드, wrapper, PV 출력, 실제 청취를 시작하지 않는다.
