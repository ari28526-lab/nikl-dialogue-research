# 2022 r3 정렬·6-tier 수출·독립 QC 완료 결과

최종 갱신: 2026-08-12 KST

## 결론

2022년은 `common_pron_mfa_r3_20260809`의 동결된 발음·모델·입력 계약으로
새로 정렬했고, 보존 DB에서 6-tier TextGrid와 post-MFA 동반표 4종을 수출한 뒤
별도 감사기로 전수 검사했다. 최종 `QC_STATE.json`은 `passed`다. 기존 2022 r2
interval을 재사용하지 않았고, 2020·2021 r3 완료본과 원 WAV·LAB·CSV를
변경하거나 재실행하지 않았다.

## 동결 입력과 정렬 기준

- source: 866,359발화
- pronunciation-safe: 752,591발화
- 발음 follow-up: 113,768발화
- safe 집합 안의 pre-MFA 기술 제외: 870발화
- 실제 r3 MFA 입력: 751,721발화, 2,651세션
- input contract ID:
  `9da932e4480b7e109b44b43f27c335b78c17e6f4466aad5a5d8acd0390facea2`
- alignment contract ID:
  `f53b6c2be25fc4e694796ae123c005258ee9913a4b6bf4cf6625220dec4113cb`
- acoustic model: Korean MFA v3.3.0, SHA-256
  `94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c`
- Jamo G2P provenance: v3.2.0, SHA-256
  `4df7c5fa90da1f401e7a44af360be56158a581a54202e38baedeca53cfed38ff`
- 채택 사전 SHA-256:
  `84a047ccd87d93033057f185c2ea7708bd712aa613fcb921635a92c8152a514a`

이 계약은 2020·2021 r3와 같은 release·acoustic phone inventory·Jamo G2P·
TextGrid schema를 사용한다. MFA phone은 강제정렬용 예측 분절이며 실제 음운
실현의 연구자 판정값으로 취급하지 않는다.

## 실행과 DB checkpoint

- 연도 runner 시작: 2026-08-11 15:05 KST
- MFA 본 계산 시작: 17:02 KST
- MFA 자체 계산 시간: 16,654.460초
- `ALIGN_DONE_2022.json` 완료: 21:41 KST
- 보존 DB:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\2022\2022.db`
- DB bytes: 7,146,942,464
- DB SHA-256:
  `610054531403f0ca13292194b13f6e63e509434435864aec9f7118d888bfe5b2`
- alignment marker SHA-256:
  `bfb797a024fc4ea6a03657688d67ca3b7e535e412e550fde7956a9a0f3861e3a`

MFA는 exit 0과 `Done`을 기록했다. 실행 중 corpus·temp·DB checkpoint를
삭제하지 않았으며 성공 DB를 보존한 채 다음 단계로 넘겼다.

## post-MFA exact-ID 회계와 승인

SQLite `quick_check`와 입력–DB exact-ID 전수 대사는 통과했다.

- expected MFA input = DB utterance: 751,721
- word·phone 정렬 성공: 751,383
- post-MFA 기술적 미정렬: 338
- 사유: `mfa_alignment_missing` 338
- 후보 세션: 183
- 후보 identity SHA-256:
  `272bcc134776548df77b244d547b1e922ff287fa9d8f8505c31740e3b2357b7a`
- 미정렬률: 0.044963%

과거 r2 미정렬 438건과 비교하면 318건은 공통, 120건은 r3에서 회수됐고
20건은 r3에서 새로 미정렬됐다. 따라서 새 정렬 기준은 순 100건을 더 회수했지만,
정렬기의 기술적 성공 여부가 발음 모델에 따라 개별 ID 수준에서 달라질 수 있음을
함께 기록한다. 이 비교는 r2 interval을 r3에 섞는 근거가 아니다.

연구자 `ari30`은 2026-08-11 23:24 KST에 338건을
`alignment_and_analysis` 범위의 후속 exact-ID로 이관하고 성공한 751,383건을
수출하는 것을 명시 승인했다. 자동 승인은 없었다. 승인 manifest SHA-256은
`4fae408afdf208534e4e15f3a7b20b747d45e4cbacb27fc01180338e697a1034`다.

## 6-tier와 동반표 수출

수출 preflight는 exact-ID 차이, 미승인 누락, `spn`, acoustic inventory 밖
phone이 모두 0임을 확인했다. 실제 수출은 2026-08-11 23:36부터
2026-08-12 01:12 KST까지 5,773.853초 수행됐다.

6-tier 이름은 다음과 같다.

1. `words`
2. `phones_mfa`
3. `phoneme_r_auto`
4. `utterance`
5. `utterance_orth_r`
6. `morph_analysis_utt`

수출 결과는 다음과 같다.

- TextGrid: 751,383개
- 승인 제외: 338개
- coverage: 100%
- utterance 동반표: 751,383행, SHA-256
  `4a1ff283504b7f2d01c4e9e8945f8de047d1a9ce606a30fe77a62754c4dcceff`
- word 동반표: 5,882,284행, SHA-256
  `2b03512d08ce5fe5c6586014b19a1d436c1af25d6bf1fb08711f48f5406948b8`
- phone 동반표: 21,857,009행, SHA-256
  `0da11a4a82e49c4f1619d473a74b924cf006267d2fb661976c275eb4a2032911`
- excluded 동반표: 338행, SHA-256
  `763ed9febe3f9ed65229f87368de11757e02cc833780364ab5eb13b71d13a0d4`
- export 보고서 SHA-256:
  `9156ac9e2cc725b8489cc2ac7d89910a8a44fbd64737dc56a6bafab960354754`

WAV frame duration과 MFA DB의 float32 표현으로 설명되는 0/xmax 미세 차이만
동일 시각으로 snap했다. 720,888발화·1,441,776경계가 해당했고 최대 조정은
`4.5776367230132564e-07`초다. 이는 음향 경계를 새로 추정하거나 내부 phone
경계를 이동한 것이 아니라 동일 WAV 종단시각의 수치 표현을 정규화한 것이다.

## 독립 전수 QC

수출기와 다른 감사 경로가 2026-08-12 01:40–02:10 KST에 다음을 확인했다.

- TextGrid 751,383/751,383 전수 파싱
- coverage 100%
- duplicate/missing/extra/invalid TextGrid: 모두 0
- `spn`: 0
- acoustic inventory 밖 phone: 0
- 네 동반표의 ID·복합키·순서·계약 ID·manifest 수량 오류: 모두 0
- 승인 제외 338과 excluded table 338: exact-ID 일치
- 보존 DB에서 독립 재수출한 24세션: semantic 24/24, byte 24/24

전수 감사 시간은 1,743.629초, DB 표본 검사는 57.907초다. 최종 QC checkpoint
ID는
`7cf3af24c5da8f58126837742902495724f4dc69140a00b6ea6d162a9eda7c89`,
`QC_STATE.json` SHA-256은
`7f0fd1a706ccc6a33f8a07ce2df8664eb64f4ccbb32dcd3cbc109161fad10ba5`다.
state는 `source_mutation_performed=false`, `mfa_recomputed=false`,
`full_export_repeated=false`를 명시한다.

## 운영 중 발견한 표시 문제

감시 중 구 heartbeat 상태판을 새 r3 heartbeat에 사용해 과거 run의 진행 필드가
표시됐고, 별도 수동 점검에서는 완료 marker를 release root에서 찾는 실수가
있었다. 실제 runner는 처음부터 `markers\ALIGN_DONE_2022.json`에 정상 marker를
작성했고 MFA·DB에는 영향이 없었다. r3 전용 상태판을 최신 heartbeat의
`FileShare.ReadWrite/Delete` 공유 읽기와 `-AsJson` 출력으로 보강했으며,
PowerShell 5.1 safety/runtime 검사를 통과했다. 이후 r3 연도 감시에는
`show_mfa_r3_year_status.ps1`만 사용한다.

## 다음 안전 정지점

2022 r3는 이 marker·DB·6-tier·동반표·QC state를 동결한다. 2022 MFA·전수
수출·QC를 다시 실행하지 않는다. 다음 생산 단계는 이 완료 SHA를 입력으로 한
2022→2023 전환 Gate와 2023 한 연도의 입력 계약·preflight이며, 2023 MFA는 그
Gate가 통과한 뒤에만 시작한다.
