# 바른 WSD 전면 재분석 환경 Gate 결과

검증일: 2026-08-28

결론: **환경 Gate E0 통과, bulk Gate B1 닫힘**

## 사용자 결론

동형이의어 의미번호를 반환하는 바른 2.1.0 전용 환경과 키 비노출
사전점검기를 준비했다. API를 쓰지 않는 CSV 전수 회계와 한 문장 라이브 WSD
스모크가 모두 통과했다. 전수 분석은 시작하지 않았다.

외장하드의 완결 CSV·TextGrid·WAV는 읽기 전용 정본으로 유지한다. 새 WSD
대용량 결과도 외장하드의 별도 versioned root에만 저장한다. GitHub에는 코드,
설정, 문서와 작은 manifest만 둔다.

## 검증 결과

| 검사 | 결과 |
|---|---|
| `bareunpy` | 2.1.0 |
| 공식 Git commit | `8107424892d76ac855918c20a0fb82faa877e530` |
| 입력 CSV | 17,156개, 일치 |
| 입력 발화 | 5,103,356개, 일치 |
| 입력 공백 어절 | 27,646,899개, 일치 |
| 필수 열 누락 파일 | 0 |
| API 키 | 외부 secret file에서 확인, 값 출력·저장 0 |
| 라이브 요청 | `다리를 건넜다.` 한 문장 |
| WSD 응답 | 6형태소 중 2형태소에 의미번호·확률 반환 |
| 전수 API 호출 | 0 |
| D: 여유 | 57.675 GiB |
| 환경 준비 | `true` |
| bulk 준비 | `false` |

라이브 응답에서는 `다리`에 의미번호 5와 확률 약 0.6361, `건너-`에 의미번호
1과 확률 약 0.9960이 왔다. 이는 API schema와 연결 확인 결과이지 정답 판정이
아니다.

## 자동 검사

- `python -m unittest tests.test_preflight_bareun_wsd_environment -v`:
  3개 통과
- `preflight_bareun_wsd_environment.py --full-input-scan`: 통과
- `preflight_bareun_wsd_environment.py --full-input-scan --live-api`: 통과
- Git diff whitespace 검사: 통과

사전점검 보고서는 키 값과 의미 설명을 기록하지 않는다. 라이브 요청 수는
항상 1문장으로 보고한다.

## B1이 닫힌 이유

설정한 bulk 최저 여유는 80 GiB인데 D: 실측 여유가 57.675 GiB다. 따라서 현재
상태에서 `--require-bulk-ready`는 실패해야 한다. 저장공간 확보와 P1 파일럿,
사용자 명시 승인이 모두 끝나기 전에는 bulk runner를 실행할 수 없다.

## 다음 단계

사용자가 P1을 승인하면 소규모 WSD 파일럿으로 발화당 출력 크기, batch 1:1,
offset, sense 필드 완전성, 재개 동작을 계측한다. 이후 PowerShell 5.1 bulk
runner와 상태판을 준비해 테스트하고, 대량 작업은 사용자가 그 명령을 직접
실행할 때만 시작한다.
