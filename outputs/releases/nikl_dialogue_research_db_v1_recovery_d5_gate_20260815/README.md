# DB v1 recovery D5 execution gate

- D4 55건을 바이트·WAV 헤더·공통사전으로 다시 감사했다.
- 25건은 기존 WAV가 0.1초 미만이며 실제 feature-generation 실패군이므로 동일 입력 MFA를 반복하지 않는다. 원 음원 길이 회수 대상으로 보존한다.
- 나머지 alignment-missing 30건만 `D5_ALIGNMENT_DIAGNOSTIC_0001`로 고정했다.
- LAB는 정상 UTF-8 한글이며, 사용 어휘는 고정 공통사전에 모두 존재한다.
- 승인 전에는 `D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D5_ALIGNMENT_DIAGNOSTIC_0001`를 만들지 않고 MFA도 실행하지 않는다.
- 실행 결과는 진단 자료이며 r3 본체나 DB v1에 자동 병합하지 않는다.
