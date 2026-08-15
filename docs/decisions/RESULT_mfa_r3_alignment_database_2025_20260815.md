# 2025 r3 정렬 DB·post-MFA 회계·6-tier·독립 QC 결과

작성일: 2026-08-15
상태: 정렬·6-tier·동반표·독립 QC 완료
적용 release: `common_pron_mfa_r3_20260809`

## 결정 요약

2025년은 앞선 다섯 연도와 같은 공통발음 r3, Korean MFA v3.3.0 음향모델,
동일 phone inventory와 6-tier schema로 전수 정렬했다. 보존 DB를 기준으로
post-MFA exact-ID를 회계했고, 성공한 정렬은 보존한 채 기술 미정렬만 별도 후속
범위로 이관했다. 2020–2024 완성본과 2025 MFA 계산은 다시 실행하지 않는다.

## 정렬 완료 근거

- alignment contract ID:
  `1b739d22d56c9ce91ce17486b89355558e17acc8364f88bb68a27acd16ba5f35`
- 완료 시각: `2026-08-14T23:32:44.5930142+09:00`
- 동결 MFA 입력: 458,413건
- 세션: 2,910개
- 보존 DB: `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\2025\2025.db`
- DB bytes: 6,702,276,608
- DB SHA-256:
  `5d7eab5a986dd39af2fc163d94bd0d8a378a891d242f984a2e536a24fcd5c0e6`
- 완료 marker SHA-256:
  `9905578ec4bacb59450ca213574d69857e1a14d96b2fcde916a4081cee2a36ca`
- MFA 계산 시간: 18,221.637초
- marker 불변조건: `status=passed`, `r3_full_realign=true`,
  `textgrid_materialized=false`, DB·temp 보존

`textgrid_materialized=false`는 실패가 아니라 built-in MFA export를 의도적으로
건너뛰고 보존 DB에서 연구용 6-tier를 별도 생성한다는 뜻이다.

## 실행 감시와 환경 판정

실행 중 한 시간마다 전체 상태를 확인하고, 그 사이에는 process·lock·heartbeat·
D: 여유 공간을 가볍게 감시했다. heartbeat 정체, 프로세스 비정상 종료, MFA 오류,
용량 임계 경보는 없었다. 제한된 Codex shell에서 D: export lock 쓰기가 한 번
거부됐으나 DB나 출력이 생성되기 전의 권한 차이였다. 정상 Windows 권한에서 같은
preflight를 재실행해 통과했으며 이를 코드·데이터 실패로 해석하지 않았다.

## post-MFA exact-ID 회계와 연구자 승인

```text
expected MFA input      458,413
database utterances     458,413
aligned utterances      457,611
technical unaligned         802
unknown/unapproved gap        0
```

802건은 모두 `mfa_alignment_missing`이며 301개 세션에 분포한다. 후보 identity는
`8077db66896e02b0333a85f76fd4f36bcda8aad1391c340639562084ef2a5646`다.
후보 생성기와 별도 DB checkpoint 검사기가 모두
`458,413 = 457,611 + 802`를 확인했다. 독립 DB 검사는 `quick_check=ok`, word와
phone 정렬 교집합 457,611, 미정렬 합집합 802, `spn=0`, coverage 99.825%였다.

연구자 `ari30`은 2026-08-15 11:38 KST에 다음 범위를 명시 승인했다.

> 2025 r3 post-MFA 미정렬 802건(candidate
> 8077db66896e02b0333a85f76fd4f36bcda8aad1391c340639562084ef2a5646)을
> alignment_and_analysis 범위의 후속 exact-ID로 이관하고, 성공한 457,611건은
> 보존 DB에서 6-tier로 수출하는 것을 승인한다. 승인자 ari30

- 승인문 SHA-256:
  `25ed1e7fe0d4d31df6d01ced6b54cb0d2156f4c0e54d4a8e458f07cb650b4ef7`
- 승인 CSV SHA-256:
  `d466a8f9f0095d6e8484387908a69d3f3d35bf591c6ecd1dc547f116fc565e6d`
- 승인 제외 계약 SHA-256:
  `0322e68a640f92e14c3e052b19ea71bd28996bb990815e3145a74dfb00845292`

이는 실제 음운 실현 판정이 아니라 정렬 산출물 존재 여부에 대한 기술적 분류다.
자동 승인, 원자료 수정, 성공한 정렬 삭제는 수행하지 않았다.

## 6-tier 수출과 경계 정규화

수출 preflight는 exact-ID 방정식, 미승인 차이 0, `spn=0`, 음향모델 밖 phone 0,
DB·사전·정렬 계약 SHA 일치를 확인했다. 실제 수출 결과는 다음과 같다.

```text
research 6-tier TextGrid      457,611
approved exclusions              802
utterance companion rows      457,611
word interval rows          5,287,036
phone interval rows        21,390,946
excluded companion rows          802
coverage                         100%
```

WAV 길이의 float32 표현으로만 설명되는 0·xmax 끝점 차이는 같은 WAV 길이의 가장
가까운 float32 값으로만 snap했다. 453,548발화의 907,096개 끝점이 해당했고 최대
조정은 약 0.000000916초였다. 이는 음운 경계를 재판정하거나 내부 phone 경계를
이동한 것이 아니라 파일 길이 표현 차이를 통일한 것이다. 검색 표시 label의
제어문자 정규화가 필요한 2025 발화는 0건이었다.

- 수출 보고서:
  `outputs/reports/EXPORT_mfa_r3_research_6tier_2025_20260815_114309.json`
- 수출 보고서 SHA-256:
  `c5d951dbaa7ee384254d4c20f71c13f32ce6bb19f6e479937c77bcabf138cfcb`
- 동반표 manifest SHA-256:
  `6ce432041216b77aeb0d511444a5fe71ef5725294b11ba8f5f0d3b7494a080f9`

## 독립 전수 QC

```text
TextGrid 전수                  457,611/457,611
coverage                                  100%
hard-failure categories                   0/25
DB re-export sample semantic              24/24
DB re-export sample byte                  24/24
```

25개 hard-failure 범주는 누락·추가·중복 ID, TextGrid 구문·tier·경계, `spn`,
음향모델 밖 phone, 동반표 키·정렬·계약·행 수, 승인 제외 ID 불일치를 포함한다.

- QC state:
  `outputs/reports/mfa_r3_research_qc_common_pron_mfa_r3_20260809/2025/QC_STATE.json`
- QC state SHA-256:
  `4f32d0b4993967ebef245a4672ea73e3738696f60981d58b0808484332cfb3b3`
- `status=passed`
- source mutation: 없음
- MFA recomputation: 없음
- full export repetition: 없음

따라서 2025 r3 MFA·6-tier·동반표·독립 QC는 완료 상태로 동결한다. 다음 생산
단계는 여섯 연도의 완료 state를 읽기 전용으로 묶는 같은-contract 교차 감사와,
본체와 분리해 보존한 pronunciation follow-up·기술 제외의 후속 shard 처리다.
