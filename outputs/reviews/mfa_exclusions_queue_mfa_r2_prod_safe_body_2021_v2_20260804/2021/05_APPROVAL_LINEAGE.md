# 2021 safe-body 제외 승인 계보

## 선행 승인

- 대상: 최초 1,488건
- 승인자: `ari30`
- 승인 시각: 2026-08-04 10:02 KST
- 기록:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_safe_body_2021_2025_20260803/2021/04_RESEARCHER_APPROVAL.json`
- SHA-256:
  `dac909cca93bf48572cbc1ac2747b8d9287c7c2b8dd1c70dc6b021a62260b760`
- 승인 범주: `audio_pairing_unresolved`,
  `empty_reference_unresolved_symbol`, `text_duration_impossible`

## 보충 승인

- 대상: 후속 입력감사에서 새로 발견한 CSV 분절시간 `0.0` 14건
- 승인자: `ari30`
- 명시 문구:

> 2021의 CSV 분절시간 0.0인 14건을 audio_pairing_unresolved 보충 후보로
> 안전 본체 MFA에서 제외하고 후속 shard로 넘기는 것을 승인한다. 승인자 ari30.

## 결합 계약

- 총 승인 행: 1,502
- 범주별 수: audio 1,039 / empty reference 399 / time impossible 64
- 새 승인 기록: `04_RESEARCHER_APPROVAL.json`
- 새 승인 기록 SHA-256:
  `c54cbd4cca344960911ac44d3903ee6c4d2f0ced8bb9a465891ddf1368e9c227`
- 실행 계약: `approved_exclusions.json`
- 실행 계약 SHA-256:
  `ca60cbd3111a4c6d120229d7822e536ea41fe8d6bad0b08f8126cfb429d1f356`

기존 1,488행 pending/승인 snapshot은 수정하지 않았다. 새 1,502행 계약은 두
승인 근거를 결합하며 원본 WAV/CSV의 삭제·변경을 승인하지 않는다. 승인된
`alignment_and_analysis` 발화의 파생 LAB만 가역 보존한 뒤 안전 본체 MFA에서
분리하고, 회수 가능한 발화는 같은 Jamo r2·음향모델의 후속 shard에서 처리한다.
