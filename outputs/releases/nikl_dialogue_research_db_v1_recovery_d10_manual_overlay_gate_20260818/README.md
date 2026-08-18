# D10 수동 전사·TextGrid overlay Gate

이 묶음은 D9 연구자 검토에서 `keep_separate_partial`로 판정된 16건만 다룬다.
원 WAV·LAB·D9 TextGrid를 수정하지 않고, 실제로 들린 문장을 별도 overlay로
작성하기 위한 작업 계약이다.

- 간단한 전사 삭제·국소 경계 수정: 9건
- 전체 word 경계 수동 재작성: 6건
- 단일어 수동 복구: 1건
- 기술 제외: 이 묶음의 실행 입력에서 제외
- D9 직접 승인 1건: 별도 enrichment/adoption Gate로 분리

현재 상태는 `passed_gate_closed_before_overlay_materialization`이다. 이 패키지
자체는 WAV·TextGrid를 복사하거나 수정하지 않고 DB에 어떤 행도 삽입하지 않는다.
