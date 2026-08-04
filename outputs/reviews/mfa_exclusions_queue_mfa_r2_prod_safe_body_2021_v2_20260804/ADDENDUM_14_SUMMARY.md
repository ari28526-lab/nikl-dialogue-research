# 2021 MFA 안전 본체 보충 후보 14건

상태: **연구자 승인 완료 — 2026-08-04 11:21 KST**
자동 승인: 없음

## 발견 경위

2021 첫 장시간 실행은 LAB 전수 검증 뒤, 실제 MFA 정렬을 시작하기 전 독립
입력감사에서 안전 중단됐다. 감사가 원본 CSV 분절시간이 `0.0`인 14건을
발견했다. 시간 대응을 검증할 수 없으므로 이 14건을
`audio_pairing_unresolved / alignment_and_analysis` 보충 후보로 분류했다.

- 기존 immutable 후보: 1,488건
- 후속 감사 후보 중 기존과 중복: 1,424건
- 새 보충 후보: 14건
- 새 pending 후보표: 1,502건
- 원본 WAV/CSV 삭제·변경: 없음
- MFA DB/TextGrid 생성: 없음

기존 승인 snapshot은 덮어쓰지 않았다. 새 후보표는
`2021/03_RESEARCHER_REVIEW.csv`, 근거 manifest는
`2021/03_RESEARCHER_REVIEW_MANIFEST.json`이다.

## 새 14건

| utt_id | reason | 근거 |
|---|---|---|
| `SDRW2100000157.1.1.43` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100000224.1.1.148` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100000317.1.1.95` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100000329.1.1.318` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100000934.1.1.137` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100001359.1.1.161` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100001810.1.1.363` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100001983.1.1.76` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100002637.1.1.106` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100003394.1.1.334` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100003828.1.1.240` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100003988.1.1.327` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100004325.1.1.327` | `audio_pairing_unresolved` | CSV duration `0.0` |
| `SDRW2100004400.1.1.115` | `audio_pairing_unresolved` | CSV duration `0.0` |

## 승인 의미

승인은 파일 삭제가 아니다. 이 14건의 파생 LAB만 안전 본체 MFA 입력에서
가역적으로 분리한다. 원본 WAV/CSV는 그대로 두며, 향후 같은 공통 Jamo r2와
음향모델을 사용하는 후속 회수 shard에서 다시 다룰 수 있다.

연구자가 명시 승인한 문구:

> 2021의 CSV 분절시간 0.0인 14건을 audio_pairing_unresolved 보충 후보로
> 안전 본체 MFA에서 제외하고 후속 shard로 넘기는 것을 승인한다. 승인자 ari30.

근거 감사:
`outputs/reports/PREFLIGHT_mfa_input_integrity_2021_eojeol_commonpron_2021_20260804_102356.json`

결합 승인 계약:
`2021/approved_exclusions.json` — 1,502행, SHA-256
`ca60cbd3111a4c6d120229d7822e536ea41fe8d6bad0b08f8126cfb429d1f356`
