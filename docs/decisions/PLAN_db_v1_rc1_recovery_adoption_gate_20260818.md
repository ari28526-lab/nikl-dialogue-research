# DB v1 RC1 recovery 채택 Gate 계획

## 목적

이미 검토가 끝난 첫 recovery shard 55건을 다시 듣거나 다시 정렬하지 않고,
DB v1 RC0 위에 덧붙이는 append-only 상태 overlay 후보로 통합한다. RC0 장부,
r3 본체, 최종 6-tier는 불변으로 보존한다.

## 범위

- D7 연구자 판정 11건: 소음 보류 3, 전사 회수 후보 2, 부분 정렬 보존 6
- D8 0.1초 미만 25건: 원 음원 조각이 너무 짧은 기술 제외
- D9 통제 재정렬 19건: 기술 제외 2, D10 수동 overlay 16, 별도 정렬 후보 1
- 합계: 서로 겹치지 않는 exact-ID 55건

## 수동 overlay 원칙

D10 16건은 연구자가 확정한 `words_manual_working`과 그로부터 얻은 최종
전사·철자 Roman만 curated 후보로 기록한다. D9 phone은 경계 작업의 참고값일
뿐 실제 발음 판정이나 최종 phone으로 채택하지 않는다. 수정 전사에 대한 형태소
분석과 phone/phoneme 재구축은 별도 후속 Gate에서 수행한다.

## 산출물

`outputs/releases/nikl_dialogue_research_db_v1_rc1_recovery_adoption_gate_20260818`
아래에 55건 상태 후보, 16건 수동 annotation snapshot, 승인 템플릿, 닫힌
계약과 manifest를 생성한다. 독립 감사는 `outputs/reports`에 남긴다.

## 정지 조건

패키지 생성·감사만으로는 DB를 채택하지 않는다. exact 범위와 후보 SHA를 묶은
연구자 승인 뒤에만 RC1 sidecar를 materialize한다. 승인 전에는 MFA, TextGrid
교체, base ledger 덮어쓰기, 자동 형태소·phone 생성이 모두 금지된다.
