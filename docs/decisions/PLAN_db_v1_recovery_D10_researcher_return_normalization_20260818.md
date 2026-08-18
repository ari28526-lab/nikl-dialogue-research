# 연구 DB v1 recovery D10 연구자 반환본 동결·정규화 계획

기록일: 2026-08-18 KST

## 목적

연구자가 Dropbox에서 직접 수정한 16개 `*.manual_working.TextGrid`를 원본 그대로
보존하면서, 연구용 채택 전에 구조와 변경 이력을 검증한 별도 D: 동결본을 만든다.
이 단계는 수동 경계를 r3 본체·최종 6-tier·DB v1에 넣는 adoption이 아니다.

## 입력과 불변 자료

- D10 초기 작업본:
  `D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_MANUAL_OVERLAY_0001`
- 연구자 반환본:
  `C:\Users\ari30\Dropbox\04_MFA_배치결과\DB_V1_RECOVERY_D10_MANUAL_OVERLAY_16_20260818\work_flat`
- 대상 exact ID: D10 Gate가 동결한 16건
- 불변 tier: `words_d9_reference`, `phones_d9_reference`
- 불변 항목: 발화 길이, exact ID, D9 참고 경계, 원 WAV·LAB, r3 본체,
  최종 6-tier, DB v1

## 검사 결과에 따른 정규화 규칙

16개 반환본의 길이·tier 순서·전구간 경계·D9 참고 tier를 전수 확인한다.

1. 1–4번은 연구자가 만든 단어 경계와 label이 `words_manual_working`이 아니라
   `transcript_proposed`에 저장되어 있다. 정보 손실이나 재작업 없이 그 interval을
   `words_manual_working`으로 옮기고, `transcript_proposed`는 동결 제안 문장 한
   interval로 복구한다.
2. 그 밖의 반환본은 연구자가 저장한 `words_manual_working`의 label과 경계를
   바꾸지 않는다.
3. 제안 전사와 다른 연구자 판정은 오류로 덮어쓰지 않고 두 값을 모두 장부에 둔다.
   현재 대상은 6번 `공무원이→공무원`, 8번 문두 `근데` 추가, 9번 `적이→적`,
   14번 `이제→인제`, 15번 불필요한 `뭐` 하나 삭제의 5건이다.
4. 11번 `노래였구나를→노래였구나 | 를`은 문자열 변경이 아니라 음향 경계에 따른
   단어 분절 차이로 별도 분류한다.

## 보존 구조

출력 예정 경로는 다음과 같다.

```text
D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_RESEARCHER_RETURN_0001
```

- `raw_return`: Dropbox 반환 16개의 byte-exact 사본
- `normalized`: 위 규칙만 적용한 16개 정규화 TextGrid
- `state/D10_RESEARCHER_RETURN_QUEUE.json`: proposed와 최종 manual 단어열,
  분류, 원본 SHA를 포함한 장부
- `state/FINAL_AUDIT.json`: 구조·SHA·불변 tier 전수 감사
- `state/FROZEN_DONE.json`: adoption 전 동결 완료 표지

## 안전 Gate

- 반환본 16/16이 아니거나 예상하지 않은 반환 파일이 있으면 중단한다.
- D9 reference tier, 발화 길이 또는 exact ID가 바뀌면 중단한다.
- 예상 분류 수량 `층위 위치 교정 4 / 완전 일치 6 / 문자 동일·분절 차이 1 /
  연구자 수정 전사 5`가 달라지면 중단한다.
- 이 단계에서 MFA를 실행하지 않으며 r3·6-tier·DB v1에 자동 병합하지 않는다.
- 다음 단계는 동결 반환본을 읽어 파생 word overlay와 provenance를 설계하는 별도
  adoption Gate다. phone tier는 D9 참고값을 수동 정답으로 승격하지 않는다.
