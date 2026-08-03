# 2023 WAV ID 복구 층화 청취 검토

목적: 길이 연속열이 제안한 고신뢰 재매핑이 실제 음성과 전사에서도 맞는지 확인합니다.
원본 WAV는 수정하지 않았고, 이 폴더에는 해시 검증한 복사본만 있습니다.

각 번호에서 다음 순서로 확인합니다.

1. 아래의 `확인할 전사`를 읽습니다.
2. `A_PROPOSED`를 듣습니다. 이 음성이 확인할 전사와 맞는지 판단합니다.
3. 필요할 때만 `B_CURRENT`를 들어 현재 같은 ID의 음성과 비교합니다.
4. 대화창에 `번호 / A 맞음`, `번호 / 불확실`, 또는 `번호 / A 틀림`으로 알려주세요.

A가 맞는다는 것은 재매핑 규칙을 지지할 뿐이며, 곧바로 원본을 덮어쓴다는 뜻은 아닙니다.

## 검토 순서

### 01. SHORT_3_10 / START

- 확인할 전사: 가능할까라는 생각도 사실 저도 많이 하긴 했었거든요.
- 원문 전사: 가능할까라는 생각도 사실 저도 많이 하긴 했었거든요.
- 대상 ID: SDRW2300000022.1.1.189
- 제안: `audio/01_A_PROPOSED_SDRW2300000022.1.1.189__FROM_SDRW2300000022.1.1.190.wav`
- 현재: `audio/01_B_CURRENT_SDRW2300000022.1.1.189.wav`
- 근거: 연속 일치 3개, ID 오프셋 +1
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 02. SHORT_3_10 / END

- 확인할 전사: 듣고 보니 어
- 원문 전사: 듣고 보니 어~
- 대상 ID: SDRW2300000022.1.1.191
- 제안: `audio/02_A_PROPOSED_SDRW2300000022.1.1.191__FROM_SDRW2300000022.1.1.192.wav`
- 현재: `audio/02_B_CURRENT_SDRW2300000022.1.1.191.wav`
- 근거: 연속 일치 3개, ID 오프셋 +1
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 03. SHORT_3_10 / START

- 확인할 전사: 좀 보수적인 회사면은 염색이 쪼끔 안 좋게 보일 수 있겠지만
- 원문 전사: 쫌 보수적인 회사면은 염색이 쪼끔 안 좋게 보일 수 있겠지만
- 대상 ID: SDRW2300000498.1.1.105
- 제안: `audio/03_A_PROPOSED_SDRW2300000498.1.1.105__FROM_SDRW2300000498.1.1.104.wav`
- 현재: `audio/03_B_CURRENT_SDRW2300000498.1.1.105.wav`
- 근거: 연속 일치 4개, ID 오프셋 -1
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 04. SHORT_3_10 / END

- 확인할 전사: 당연하지.
- 원문 전사: 당연하지.
- 대상 ID: SDRW2300000498.1.1.108
- 제안: `audio/04_A_PROPOSED_SDRW2300000498.1.1.108__FROM_SDRW2300000498.1.1.107.wav`
- 현재: `audio/04_B_CURRENT_SDRW2300000498.1.1.108.wav`
- 근거: 연속 일치 4개, ID 오프셋 -1
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 05. SHORT_3_10 / START

- 확인할 전사: 좀 싼 값에
- 원문 전사: 쫌 싼 값에
- 대상 ID: SDRW2300001376.1.1.159
- 제안: `audio/05_A_PROPOSED_SDRW2300001376.1.1.159__FROM_SDRW2300001376.1.1.134.wav`
- 현재: `audio/05_B_CURRENT_SDRW2300001376.1.1.159.wav`
- 근거: 연속 일치 6개, ID 오프셋 -25
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 06. SHORT_3_10 / END

- 확인할 전사: 이제 나폴리를 가면 좀 실망할 수가 있는데
- 원문 전사: 이제 나폴리를 가면 좀 실망할 수가 있는데
- 대상 ID: SDRW2300001376.1.1.164
- 제안: `audio/06_A_PROPOSED_SDRW2300001376.1.1.164__FROM_SDRW2300001376.1.1.139.wav`
- 현재: `audio/06_B_CURRENT_SDRW2300001376.1.1.164.wav`
- 근거: 연속 일치 6개, ID 오프셋 -25
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 07. SHORT_3_10 / START

- 확인할 전사: 크리티컬스트라이크도 해 봤고
- 원문 전사: 크리티컬스트라이크도 해 봤고
- 대상 ID: SDRW2300001939.1.1.198
- 제안: `audio/07_A_PROPOSED_SDRW2300001939.1.1.198__FROM_SDRW2300001939.1.1.197.wav`
- 현재: `audio/07_B_CURRENT_SDRW2300001939.1.1.198.wav`
- 근거: 연속 일치 10개, ID 오프셋 -1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 08. SHORT_3_10 / END

- 확인할 전사: 크리티컬스트라이크도 해 봤고
- 원문 전사: 크리티컬스트라이크도 해 봤고
- 대상 ID: SDRW2300001939.1.1.198
- 제안: `audio/08_A_PROPOSED_SDRW2300001939.1.1.198__FROM_SDRW2300001939.1.1.197.wav`
- 현재: `audio/08_B_CURRENT_SDRW2300001939.1.1.198.wav`
- 근거: 연속 일치 10개, ID 오프셋 -1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 09. MEDIUM_11_80 / START

- 확인할 전사: 웃으면서 얘기할 수 있는 추억들이 좀 있어요.
- 원문 전사: 웃으면서 얘기할 수 있는 추억들이 좀 있어요.
- 대상 ID: SDRW2300000030.1.1.395
- 제안: `audio/09_A_PROPOSED_SDRW2300000030.1.1.395__FROM_SDRW2300000030.1.1.396.wav`
- 현재: `audio/09_B_CURRENT_SDRW2300000030.1.1.395.wav`
- 근거: 연속 일치 11개, ID 오프셋 +1
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 10. MEDIUM_11_80 / END

- 확인할 전사: 가다가 너무 답답하니깐 내려서 인도를 막 걸어가요.
- 원문 전사: 가다가 너무 답답하니깐 내려서 인도를 막 걸어가요.
- 대상 ID: SDRW2300000030.1.1.405
- 제안: `audio/10_A_PROPOSED_SDRW2300000030.1.1.405__FROM_SDRW2300000030.1.1.406.wav`
- 현재: `audio/10_B_CURRENT_SDRW2300000030.1.1.405.wav`
- 근거: 연속 일치 11개, ID 오프셋 +1
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 11. MEDIUM_11_80 / START

- 확인할 전사: 그냥 나는 아니 텔레비전 자체에 관심도 없고 그렇습니다.
- 원문 전사: 그냥 나는 아이 테레비 자체에 관심도 없고 건햄수다.
- 대상 ID: SDRW2300001452.1.1.104
- 제안: `audio/11_A_PROPOSED_SDRW2300001452.1.1.104__FROM_SDRW2300001452.1.1.106.wav`
- 현재: `audio/11_B_CURRENT_SDRW2300001452.1.1.104.wav`
- 근거: 연속 일치 14개, ID 오프셋 +2
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 12. MEDIUM_11_80 / END

- 확인할 전사: 예를 들어 그래 뭐
- 원문 전사: 에를 들어 그래 뭐~
- 대상 ID: SDRW2300001452.1.1.111
- 제안: `audio/12_A_PROPOSED_SDRW2300001452.1.1.111__FROM_SDRW2300001452.1.1.113.wav`
- 현재: `audio/12_B_CURRENT_SDRW2300001452.1.1.111.wav`
- 근거: 연속 일치 14개, ID 오프셋 +2
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 13. MEDIUM_11_80 / START

- 확인할 전사: 대리님도 이제 같은 속기사시니까
- 원문 전사: 대리님도 이제 같은 속기사시니까
- 대상 ID: SDRW2300000214.1.1.33
- 제안: `audio/13_A_PROPOSED_SDRW2300000214.1.1.33__FROM_SDRW2300000214.1.1.34.wav`
- 현재: `audio/13_B_CURRENT_SDRW2300000214.1.1.33.wav`
- 근거: 연속 일치 22개, ID 오프셋 +1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 14. MEDIUM_11_80 / END

- 확인할 전사: 대리님도 이제 같은 속기사시니까
- 원문 전사: 대리님도 이제 같은 속기사시니까
- 대상 ID: SDRW2300000214.1.1.33
- 제안: `audio/14_A_PROPOSED_SDRW2300000214.1.1.33__FROM_SDRW2300000214.1.1.34.wav`
- 현재: `audio/14_B_CURRENT_SDRW2300000214.1.1.33.wav`
- 근거: 연속 일치 22개, ID 오프셋 +1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 15. MEDIUM_11_80 / START

- 확인할 전사: 저는 가장 기억에 남는 잔치가 돌잔치인데요.
- 원문 전사: 저는 가장 기억에 남는 잔치가 돌잔치인데요.
- 대상 ID: SDRW2300000659.1.1.263
- 제안: `audio/15_A_PROPOSED_SDRW2300000659.1.1.263__FROM_SDRW2300000659.1.1.265.wav`
- 현재: `audio/15_B_CURRENT_SDRW2300000659.1.1.263.wav`
- 근거: 연속 일치 80개, ID 오프셋 +2
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 16. MEDIUM_11_80 / END

- 확인할 전사: 가장 그 장면을 보는 게 행복하고
- 원문 전사: 가장 그 장면을 보는 게 행복하고
- 대상 ID: SDRW2300000659.1.1.269
- 제안: `audio/16_A_PROPOSED_SDRW2300000659.1.1.269__FROM_SDRW2300000659.1.1.271.wav`
- 현재: `audio/16_B_CURRENT_SDRW2300000659.1.1.269.wav`
- 근거: 연속 일치 80개, ID 오프셋 +2
- 증거 등급: A_ALL_SCALE_CONSENSUS

### 17. LONG_81_PLUS / START

- 확인할 전사: 이
- 원문 전사: 이
- 대상 ID: SDRW2300000847.1.1.263
- 제안: `audio/17_A_PROPOSED_SDRW2300000847.1.1.263__FROM_SDRW2300000847.1.1.265.wav`
- 현재: `audio/17_B_CURRENT_SDRW2300000847.1.1.263.wav`
- 근거: 연속 일치 82개, ID 오프셋 +2
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 18. LONG_81_PLUS / END

- 확인할 전사: 이
- 원문 전사: 이
- 대상 ID: SDRW2300000847.1.1.263
- 제안: `audio/18_A_PROPOSED_SDRW2300000847.1.1.263__FROM_SDRW2300000847.1.1.265.wav`
- 현재: `audio/18_B_CURRENT_SDRW2300000847.1.1.263.wav`
- 근거: 연속 일치 82개, ID 오프셋 +2
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 19. LONG_81_PLUS / START

- 확인할 전사: 내과의가 상주해 있는 병원이라도 굉장히 많이 뱅뱅뱅 도는 경우가 많거든요.
- 원문 전사: 내과의가 상주해 있는 병원이라도 굉장히 많이 뱅뱅뱅 도는 경우가 많거든요.
- 대상 ID: SDRW2300000980.1.1.107
- 제안: `audio/19_A_PROPOSED_SDRW2300000980.1.1.107__FROM_SDRW2300000980.1.1.108.wav`
- 현재: `audio/19_B_CURRENT_SDRW2300000980.1.1.107.wav`
- 근거: 연속 일치 89개, ID 오프셋 +1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 20. LONG_81_PLUS / END

- 확인할 전사: 내과의가 상주해 있는 병원이라도 굉장히 많이 뱅뱅뱅 도는 경우가 많거든요.
- 원문 전사: 내과의가 상주해 있는 병원이라도 굉장히 많이 뱅뱅뱅 도는 경우가 많거든요.
- 대상 ID: SDRW2300000980.1.1.107
- 제안: `audio/20_A_PROPOSED_SDRW2300000980.1.1.107__FROM_SDRW2300000980.1.1.108.wav`
- 현재: `audio/20_B_CURRENT_SDRW2300000980.1.1.107.wav`
- 근거: 연속 일치 89개, ID 오프셋 +1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 21. LONG_81_PLUS / START

- 확인할 전사: 메일을 보질 않아.
- 원문 전사: 메일을 보질 않아.
- 대상 ID: SDRW2300000977.1.1.237
- 제안: `audio/21_A_PROPOSED_SDRW2300000977.1.1.237__FROM_SDRW2300000977.1.1.236.wav`
- 현재: `audio/21_B_CURRENT_SDRW2300000977.1.1.237.wav`
- 근거: 연속 일치 103개, ID 오프셋 -1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 22. LONG_81_PLUS / END

- 확인할 전사: 메일을 보질 않아.
- 원문 전사: 메일을 보질 않아.
- 대상 ID: SDRW2300000977.1.1.237
- 제안: `audio/22_A_PROPOSED_SDRW2300000977.1.1.237__FROM_SDRW2300000977.1.1.236.wav`
- 현재: `audio/22_B_CURRENT_SDRW2300000977.1.1.237.wav`
- 근거: 연속 일치 103개, ID 오프셋 -1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 23. LONG_81_PLUS / START

- 확인할 전사: 맞아. 출산 전에 나도 언니처럼
- 원문 전사: 맞어. 출산 전에 나도 언니처럼
- 대상 ID: SDRW2300001307.1.1.435
- 제안: `audio/23_A_PROPOSED_SDRW2300001307.1.1.435__FROM_SDRW2300001307.1.1.436.wav`
- 현재: `audio/23_B_CURRENT_SDRW2300001307.1.1.435.wav`
- 근거: 연속 일치 239개, ID 오프셋 +1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET

### 24. LONG_81_PLUS / END

- 확인할 전사: 맞아. 출산 전에 나도 언니처럼
- 원문 전사: 맞어. 출산 전에 나도 언니처럼
- 대상 ID: SDRW2300001307.1.1.435
- 제안: `audio/24_A_PROPOSED_SDRW2300001307.1.1.435__FROM_SDRW2300001307.1.1.436.wav`
- 현재: `audio/24_B_CURRENT_SDRW2300001307.1.1.435.wav`
- 근거: 연속 일치 239개, ID 오프셋 +1
- 증거 등급: B_Q2_Q5_BRACKETED_SAME_OFFSET
