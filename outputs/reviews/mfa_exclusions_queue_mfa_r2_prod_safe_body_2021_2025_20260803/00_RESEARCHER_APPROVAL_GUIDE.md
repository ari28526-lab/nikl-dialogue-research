# 2021–2025 안전 본체 MFA 제외 범주 승인 안내

검토 대상은 112,292개 행을 하나씩 듣는 일이 아니다. 아래 세 원인 범주와
연도별 개수, 처리 원칙을 승인할지 확인한다.

1. `audio_pairing_unresolved`: 같은 ID의 WAV가 해당 CSV/JSON 발화라고 보장할
   수 없거나, duration session gate를 실패한 세션의 발화다. 안전 본체에서는
   제외하고 회수 가능한 것만 후속 shard로 처리한다.
2. `empty_reference_unresolved_symbol`: MFA 입력 발음 참조가 비어 있어 자동
   추측하지 않는다.
3. `text_duration_impossible`: 원전 분절 시간에 비해 전사량이 물리적으로
   불가능하다.

현행 정본 수량은 `CATEGORY_SUMMARY_2021_2025.md`와 같다.

- 검색 발화: 4,232,919
- 안전 본체: 4,120,627
- 승인 후보: 112,292
- 음원 대응: 111,425
- 빈 참조: 788
- 시간 불가능: 79

승인하려면 대화에서 다음 뜻을 명시한다.

> 2021–2025의 `audio_pairing_unresolved`,
> `empty_reference_unresolved_symbol`, `text_duration_impossible` 세 범주를
> 안전 본체 MFA에서 제외하고, 음원 회수 가능분은 후속 shard로 처리하는 것을
> 승인한다. 승인자 ari30.

승인은 실제 발음·음운 실현 판정이 아니다. 원본 WAV/CSV 삭제·변경도 아니며,
제외 ID와 사유는 승인 계약·동반표에 유지된다. 승인 후에도 2021 한 연도만 먼저
실행하고, 2021 기계 QC와 생산 표본 연구자 gate 전에는 2022를 시작하지 않는다.
