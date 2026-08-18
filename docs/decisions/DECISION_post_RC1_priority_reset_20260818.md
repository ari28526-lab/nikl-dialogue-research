# RC1 이후 우선순위 재설정: 전체 조회 인프라 우선

기록일: 2026-08-18 KST

## 점검 배경

RC1 채택 직후 curated 16건의 형태소·phone/phoneme enrichment를 곧바로
구현하려 했으나, 전체 5,103,356발화와 앞으로의 표적 추출·세션 JSON·공동연구
재사용성을 기준으로 비용 대비 효과를 다시 점검했다.

## 결정

curated 16건은 RC1에 이미 수동 word 경계, 최종 한글 전사, 철자 Roman,
TextGrid SHA와 active pointer가 보존돼 있다. 따라서 다음 순서를 따른다.

1. RC0는 전 발화의 기본값으로 유지한다.
2. `(year, utt_id)`가 RC1 curated pointer에 있을 때만 수동 annotation을 우선한다.
3. diagnostic TextGrid는 증거일 뿐 active annotation으로 승격하지 않는다.
4. D9 phone은 계속 참고 전용으로 둔다.
5. 16건의 형태소·phone/phoneme 보완은 해당 발화가 실제 연구 표적으로 추출될
   때 exact-ID enrichment Gate로 수행한다.
6. 지금은 위 precedence를 target manifest, 검토 bundle, 세션 JSON이 공통으로
   사용할 수 있게 만드는 일이 우선이다.

이 결정은 enrichment를 폐기하는 것이 아니라 지연 처리하는 것이다. 작은 예외
16건 때문에 510만 행을 다시 생성하거나 전수 MFA·D7–D10 검토를 반복하지 않는다.

## 구현 결과

`nikl_dialogue_research_db_v1_active_view_contract_v1_20260818`은 RC0 전체를
복제하지 않고 예외 55건만 담는다. 이 중 curated pointer는 16건이며 나머지
39건은 RC0를 보존한다. 독립 감사는 exact-ID 중복 0, curated 16, base 보존
39와 D9 phone 비채택을 확인했다.

다음 구현 단위는 이 계약을 읽는 범용 target query/manifest v1과 작은 검색
표본이다. 실제 음성 실현 여부는 자동 판정하지 않는다.
