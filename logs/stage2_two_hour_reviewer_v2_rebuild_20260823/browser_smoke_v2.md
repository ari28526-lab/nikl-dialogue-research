# Stage 2 reviewer v2 browser smoke — 2026-08-23 KST

Target: `researcher_review_package_v2` final code, tested before candidate promotion
under the byte-identical `researcher_review_package_v2_candidate_after_canplay_fix`
name.

## START_HERE

- Seven links rendered with these labels:
  - PT: 합성어 경음화(사잇소리 관련 포함)
  - NAN: ㄴ 앞 비음화
  - NAL: ㄹ 앞 비음화
  - NI: ㄴ삽입
  - LLN: ㄴㄹ·ㄹㄴ 연쇄(유음화·비음화 복합형)
  - VH: 모음조화
  - HIA: 모음충돌 회피
- Praat criterion, selected recheck criterion, and six procedure rules were visible.

## Runtime interactions

- Phenomenon dropdown PT → NAN:
  - URL: `?phenomenon=NAN`
  - position: `1/12 · NAN`
  - progress: `ㄴ 앞 비음화 · 저장된 청취 0/12`
- Shuffled mode recheck banner: visible
- Browser console errors: 0

## Target jump (Range-capable local test server)

| sample_id | expected target_xmin | measured currentTime | seekable | result |
|---|---:|---:|---:|---|
| P2H-PT-2022-02 | 2.070 | 2.069999 | 0–3.120 | pass |
| P2H-PT-2024-01 | 0.430 | 0.430000 | 0–2.992438 | pass |
| P2H-PT-2024-02 | 1.910 | 1.910000 | 0–2.992438 | pass |

Python's default static server exposed no usable WAV byte range (`seekable=0`),
so it was not a valid seek acceptance surface. A Python-standard-library-only
Range server in `work/stage2_two_hour_reviewer_v2_rebuild_20260823/` supplied
`Accept-Ranges`/206 responses for this test. All temporary servers and
agent-created tabs were closed afterward.

No reviewer form or literature-note value was entered in the real browser, so
no pilot record was created and no test localStorage cleanup was required.
