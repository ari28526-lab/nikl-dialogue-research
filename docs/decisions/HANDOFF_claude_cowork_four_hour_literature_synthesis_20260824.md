# Claude Cowork 인계 — 4시간 연구자 중심 선행연구 종합

## 목적

연구자가 약 4시간 동안 기존 연구에 관해 떠오르는 생각을 자유롭게 종합한다.
Claude는 생각을 대신 결정하지 않고, 연구자의 메모가 근거 장부·현상별 요인
지도·범위/표본 계약·Codex 코드 초안으로 이어지게 정리한다.

## 4시간 진행

1. **0:00–0:30 자유 회상**: 수정하거나 평가하지 말고 연구자 표현 그대로 기록.
2. **0:30–1:30 근거 지도**: 직접 주장, 반례, 적용 조건, 한계, 원문 미확인을 분리.
3. **1:30–2:30 7현상 요인 지도**: 음운입력·형태론/POS·어휘·운율·화자·담화·측정 요인과 상호작용 갱신.
4. **2:30–3:15 공백과 우선순위**: 반드시 원문을 확인할 것, 새 표본/대조, 세미나에 없던 필수 환경 결정.
5. **3:15–4:00 코드 인계**: 확정하지 말고 후보 scope card, sampling frame, query/reviewer 변경 요구로 번역.

## 필수 경계

- 자유 메모 원문과 Claude의 정규화·추론을 분리한다.
- 주장마다 출처·페이지·직접/인접/방법론/미확인·확신도·`does_not_establish`를 둔다.
- 원문을 확인하지 못한 기억은 `researcher_recall_unverified`로 둔다.
- PT는 저해음 뒤 경음화, 합성어 경음화, 사이시옷을 각각 판정하고 복수 membership을 보존한다.
- NAN은 어절 내부 저해음+/ㄴ·ㅁ/ 기준층과 어절 간 운율 탐색층을 합치지 않는다.
- 필수 환경은 형태소 경계와 좌우 POS를 층화한다.
- 연구자 승인 전 동결 query/config, 원자료, 정식 realization ledger를 바꾸지 않는다.

## 산출물

- `RESEARCHER_FREE_NOTES_YYYYMMDD.md`
- `CLAIM_LEDGER_PATCH_CANDIDATE.jsonl`
- `FACTOR_MAP_PATCH_CANDIDATE.json`
- `SCOPE_AND_SAMPLING_DECISIONS_CANDIDATE.md`
- `CODE_HANDOFF_TO_CODEX.md`

## Codex로 되돌릴 때 쓸 프롬프트

> Claude Cowork의 4시간 문헌 종합 산출물을 읽고, 연구자 원문과 Claude 추론을
> 분리 감사해줘. 승인된 결정만 후보 config/claim ledger/query/reviewer 초안에
> 반영하고, v1/v2와 기존 JSONL은 보존해. PT/NAN 모집단 분리, 복수 membership,
> 형태소·POS 층화가 테스트되는지 확인한 뒤 변경 내역·미확인 근거·다음 연구자
> 결정을 보고해줘. commit/push 전에는 diff와 감사 결과를 먼저 보여줘.
