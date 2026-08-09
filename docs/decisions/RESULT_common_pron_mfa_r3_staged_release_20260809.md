# 공통발음 MFA r3 staged release 물질화·독립 감사 결과

날짜: 2026-08-09 KST

상태: release와 독립 감사 통과, Production Gate는 닫힘

## 결과

v3.1 단계적 채택 계약에 따라 Stage 20 후보 실물을 수정하지 않고 새
release-scoped 경로에 selected projection과 MFA 사전을 물질화했다.

- release ID: `common_pron_mfa_r3_20260809`
- pronunciation contract ID:
  `58226aeded930a5b09985c7a1ad870effbfb39fbbfd7d89229f84578cd3402af`
- release root:
  `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809`
- manifest SHA-256:
  `6292c92f3de9433d69bc1e9558c6c6d544608fc84d516c1080be6e9e9c58b416`
- selected projection SHA-256:
  `c0ed7d6d798d3dbab04f00b4afa9b30e806acffd767783a2ff285f1bdb2a9361`
- MFA dictionary SHA-256:
  `84a047ccd87d93033057f185c2ea7708bd712aa613fcb921635a92c8152a514a`

## 전수 회계

| 항목 | 수 |
|---|---:|
| canonical 관측 표면형 | 881,237 |
| staged selected 표면형 | 795,804 |
| selected canonical 출현 | 27,043,261 |
| MFA 사전 변이 행 | 796,061 |
| zero-fallback hold형 | 85,398 |
| 명시적 policy형 | 35 |
| pronunciation-safe 발화 | 4,384,992 |
| follow-up 발화 | 718,364 |

## 독립 감사

`audit_common_pron_mfa_r3_staged_release.py`가 후보 projection, selected
projection, MFA 사전 796,061행을 서로 독립적으로 전수 대조했다.

- Stage 19·20 실물과 감사 보고서 SHA pin: 통과
- 승인 JSON SHA 및 provenance sidecar 결속: 통과
- candidate→selected phone·Roman·출처·연도별 수량 보존: 통과
- 새 MFA 사전과 Stage 20 후보 사전의 byte 동일성: 통과
- selected projection과 사전의 행별 token·phone 동일성: 통과
- 동결 acoustic inventory 밖 phone: 0
- lexical `sil`/`spn`: 0
- full-corpus completion 주장: 없음
- production MFA 허용: false
- TextGrid 물질화 허용: false
- release Gate: 닫힘

감사 보고서는
`outputs/reports/AUDIT_common_pron_mfa_r3_staged_release_20260809.json`에
기록했다.

## 의미

Stage 20의 `candidate_only=true, final_selection=false` 행을 제자리에서
고치지 않았다. 새 release projection에서만
`candidate_only=false, final_selection=true, adopted=false`로 명시적으로
승격했다. 따라서 candidate와 selection의 provenance가 분리되며, `adopted`는
향후 단일 Gate 편집 전까지 계속 false다.

이 사전은 MFA의 동일 입력 발음 기준을 제공하지만 실제 음성 실현을 판정하지
않는다. 2020–2025는 이 동일 release와 동결 acoustic phone inventory를 연도별
alignment contract에 결속한 뒤 새로 정렬한다.

## 보존·비변경 사항

- Stage 01–21 산출물 변경 없음
- D: 원자료 변경 없음
- 기존 r2 release·DB·TextGrid 변경 없음
- Stage 20 후보 projection·`NOT_ADOPTED` 사전 변경 없음
- Production Gate와 `allowed_release_ids=[]` 변경 없음

## 다음 단계

체크리스트 3에서 연도별 safe exact-ID 목록과 pre-MFA 기술 제외의 교집합을
물질화하고, 2020 복구 WAV corpus 계약을 `YEAR_INPUT_CONTRACT_2020.json`에
결속한다.
