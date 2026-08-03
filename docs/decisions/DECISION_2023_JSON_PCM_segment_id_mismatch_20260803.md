# 2023 JSON–PCM/WAV 분절 ID 불일치 원인 판정

결정일: 2026-08-03 KST

상태: 대표 세션 원인 확정, 전수 복구 계약·연구자 표본 승인 대기

적용 범위: 2023 MFA 입력의 `audio_pairing_*` 후보와 파생 WAV 복구 코퍼스

## 판정 요약

2023의 대량 음원 대응 문제는 형태소 CSV 생성이나 로컬 PCM→WAV 변환 때문에
생긴 것이 아니다. 배포 JSON이 세는 발화와 배포 PCM/WAV가 세는 음성 조각의
번호가 일부 지점에서 달라지는 **원자료 묶음 내부의 분절 ID 불일치**다.

대표 세션에서는 발화 사이 약 0.052초 공백 조각이 독립 PCM/WAV 파일로 번호를
차지하지만 JSON 발화 배열에는 독립 발화로 들어가지 않았다. 이 지점부터 뒤의
PCM/WAV ID가 JSON 발화 ID보다 1씩 밀린다. 다른 영향 세션에는 여러 국소 offset이
관측되므로, 2023 전체를 단순 `+1`로 고치는 방식은 금지한다.

## 대표 증거: `SDRW2300000022`

- JSON 발화 수: 332
- 배포 PCM 파일 수: 333
- 배포 WAV 파일 수: 333
- JSON 87번 종료–88번 시작 공백: 0.051810초
- `88.pcm`: 1,664 bytes = 16 kHz·16 bit mono 기준 0.052초
- `88.wav`: 1,708 bytes = 같은 PCM payload + 44-byte WAV header
- JSON 88번 길이: 4.919790초, 실제 `89.pcm/.wav`: 4.920초
- JSON 89번 길이: 4.163340초, 실제 `90.pcm/.wav`: 4.163초
- JSON 90번 길이: 0.868450초, 실제 `91.pcm/.wav`: 0.868초

87–91번 PCM과 배포 WAV의 payload SHA-256을 비교해 모두 같음을 확인했다.
현재 `D:\20_AUDIO\03_wav\individual\2023\SDRW2300000022`의 WAV도 H: 배포
WAV와 파일 SHA-256이 모두 같다. 따라서 WAV 변환·복사 과정은 해당 불일치를
만들지 않았다.

## 자료 층위별 책임 판정

1. **형태소/검색 CSV**: 직접 원인 아님. 대표 발화의 ID·시작·종료·form은 원본
   JSON과 일치한다.
2. **JSON**: 파일 자체가 깨진 것은 아니지만, JSON 발화 ID 체계가 음원 파일의
   모든 분절 조각을 세지 않는다.
3. **PCM/WAV 원자료 묶음**: 음성 payload 자체는 상당수 정상이나, JSON에 없는
   짧은 조각이 파일 번호를 차지해 JSON과의 ID 대응이 어긋난다. 일부에는 실제
   결손·극단적으로 짧은 조각·빈 참조 등 다른 예외도 함께 있을 수 있다.
4. **로컬 PCM→WAV/복사**: 대표 증거상 원인 아님. 배포 PCM payload, 배포 WAV,
   D: WAV가 동일하다.

따라서 이 문제를 단순히 “CSV 오류” 또는 “PCM 손상”이라고 쓰지 않는다. 논문과
작업 기록에는 **배포 JSON 발화 분절과 배포 개별 음원 분절의 식별자 불일치**로
기술한다.

## 2023 전체 관측과 안전 규칙

- 입력 감사의 audio pairing issue: 66,459
- q1/q2/q5 길이 양자화에서 모두 같은 고신뢰 대응: 42,240
- q2/q5가 같고 동일 offset의 양쪽 anchor로 둘러싸인 대응: 5,997
- 채택 후보 합계: identity 184, remap 48,053
- 보수적으로 미해결 유지: 18,222
- 선택 계획에서 한 source WAV의 중복 배정: 0

영향 세션 중 다수는 한 세션 안에서도 offset이 여러 번 바뀐다. 그러므로 파일명
정수에 일괄 offset을 더하는 복구는 허용하지 않는다. 길이 다중 해상도 합의,
세션 내부 양방향 anchor, source 유일성, 층화 음성 표본 검토를 모두 통과한
대응만 파생 staging 코퍼스에 적용한다. 미해결 행은 원본을 억지로 붙이지 않고
연도별 제외 계약과 동반표에 남긴다.

## 연구 방법상 의미

MFA는 이 대응을 고치는 도구가 아니다. MFA 전에 CSV 발화와 실제 WAV가 같은
분절인지 확정해야 한다. 복구는 원본 PCM/WAV/JSON을 수정하지 않고, 해시와
mapping provenance가 있는 파생 코퍼스에서만 수행한다. 이후 모든 2020–2025
정렬은 동일 Jamo r2 사전·동일 acoustic model·동일 phone inventory를 사용한다.

## 근거 파일

- `work/2023_wav_recovery_consensus_q1_q2_q5.json`
- `work/2023_wav_recovery_topology.json`
- `work/2023_wav_recovery_consensus_strong_plan.json`
- `work/2023_wav_recovery_consensus_strong_scan.json`
- `outputs/reviews/2023_wav_recovery_consensus_review_20260803/`
- `scripts/python/compare_wav_recovery_plans.py`
- `scripts/python/analyze_wav_recovery_topology.py`
- `scripts/python/build_wav_recovery_consensus_plan.py`
- `scripts/python/scan_wav_recovery_plan.py`
