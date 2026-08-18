# 연구 DB v1 recovery D10 연구자 반환본 동결·정규화 결과

기록일: 2026-08-18 KST

## 결론

연구자가 Dropbox에 직접 저장한 D10 수동 TextGrid 16개를 모두 확인하고 다음
별도 D: 경로에 동결했다.

```text
D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_RESEARCHER_RETURN_0001
```

`raw_return`에는 반환 16개를 byte-exact로 보존하고, `normalized`에는 연구용
채택 전에 사용할 16개 정규화본을 두었다. 최종 상태는
`frozen_researcher_return_pending_adoption_gate`다. 이 결과는 아직 r3 본체·
최종 6-tier·DB v1에 들어가지 않았다.

## 14번 확인

마지막 반환본인 14번 `SDRW2300000169.1.1.115`도 정상 수신했다. 길이는
3.686초이고 D9 word/phone 참고 tier는 초기 작업본과 같았다. 연구자 작업 단어열은
`그 | 여름이다 | 보니까 | 인제 | 보양식 | 같은 | 경우 | 문어 | 낙지 | 그런`이며,
제안 전사의 `이제`를 청취 결과 `인제`로 수정한 연구자 판정으로 보존했다.

## 반환본 분류와 처리

| 분류 | 건수 | 처리 |
|---|---:|---|
| 작업 tier 위치만 다름 | 4 | 1–4번의 연구자 interval을 `words_manual_working`으로 옮기고 제안 문장 tier 복구 |
| 제안 단어열과 일치 | 6 | 수동 label·경계를 그대로 보존 |
| 문자 동일·어절 분절만 다름 | 1 | 11번 `노래였구나 | 를`의 음향 분절을 그대로 보존 |
| 연구자 수정 전사 | 5 | proposed와 최종 manual 값을 모두 provenance에 보존 |

연구자 수정 전사는 6번 `공무원이→공무원`, 8번 문두 `근데` 추가, 9번
`적이→적`, 14번 `이제→인제`, 15번 불필요한 `뭐` 한 항목 삭제다. 이 다섯
판정은 자동 제안으로 되돌리지 않았다.

## 감사 결과

- 반환 파일 16/16, raw 사본 16/16, 정규화본 16/16
- 발화 길이와 네 tier의 0–끝 전구간 연속성 통과
- `words_d9_reference`와 `phones_d9_reference` 16/16 불변
- 1–4번 외 수동 word label·경계 변경 0
- 전체 37파일, 328,579 bytes
- 최종 감사 SHA-256:
  `08b41eda5dbb88082d54d1c481eb1be5994d64ba12710196bd674e5d36a6cfde`

프로젝트 내부 smoke materialization과 재감사 뒤 임시본을 제거하고, 커밋
`db6c9d2`의 동일 코드로 D: 정본을 생성했다. 기계 결과 요약은
`outputs/reports/RESULT_db_v1_recovery_D10_researcher_return_20260818.json`,
발화별 proposed/manual 단어열과 파일 SHA 정본은 D:의
`state/D10_RESEARCHER_RETURN_QUEUE.json`에 있다.

## 안전 정지점과 다음 단계

Dropbox 반환본, D10 초기 작업본, 원 WAV·LAB, r3 본체, 최종 6-tier, DB v1은
바꾸지 않았고 MFA도 실행하지 않았다. D9 phone tier는 참고 증거로만 남겨 수동
정답 phone으로 승격하지 않았다.

다음은 이 16건의 최종 수동 word 경계·전사를 exact ID 기반 파생 overlay로
연결하고 원본–D9–수동본 provenance를 DB에 기록하는 별도 adoption Gate다.
adoption Gate가 만들어지고 승인되기 전에는 기존 정본을 덮어쓰지 않는다.
