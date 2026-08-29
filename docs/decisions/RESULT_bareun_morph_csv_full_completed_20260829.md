# Bareun v3.1 형태소-only CSV 전수 재분석 완료

날짜: 2026-08-29 KST

## 결론

Bareun 서버 v3.1.0 이상 계약으로 전체 CSV를 새로 형태소 분석했다.
`with_sense=false`인 형태소-only 단계이며 기존 분석열을 재사용한 결과가 아니다.
외장하드의 작업 디렉터리는 `bulk_csv_v1` final로 원자 승격됐고
`bulk_csv_v1.building`은 남지 않았다.

독립 감사 보고서
`outputs/reports/AUDIT_bareun_morph_csv_full_20260828.json`은
`passed=true`, `errors=[]`로 통과했다.

## 최종 회계

- CSV 파일: 17,156개
- 발화: 5,103,356개
- 입력 어절 및 token: 27,646,899개
- 형태소: 51,280,814개
- 의미번호가 있는 형태소: 0개
- 압축 CSV 총량: 1,349,330,222 bytes
- receipt inventory: 17,156행
- receipt inventory SHA-256:
  `266f6a5a8dff573d863336ba90d84e3e4b4989a8ed18b8af508a1685244e864f`

감사기는 inventory SHA와 행 수를 먼저 확인한 뒤, 모든 receipt의 SHA,
모든 원본 CSV의 SHA, 모든 출력 파일의 존재·크기·SHA를 전수 검사했다.
receipt 합계는 final manifest의 파일·발화·어절·token·형태소 수 및 압축
byte 수와 일치했다.

## 원문 보존과 줄 구분자 처리

API가 입력 내부 줄 구분자를 별도 문장으로 해석하는 경우를 막기 위해
API 요청용 메모리 복사본에서만 줄 구분자 한 글자를 ASCII 공백 한 글자로
1:1 치환했다. 최종 전수 집계는 2발화, 2문자다.

- 원본 및 출력 `form`: 변경 없음
- 문자 길이와 위치 offset: 보존
- 원본 CSV SHA 전수 검증: 통과
- TextGrid 또는 WAV 접근: 없음
- 기존 Bareun/WSD 결과 수정: 없음

원문 내용은 저장소 문서나 로그에 기록하지 않았다.

## 장애와 복구

1. 12,671개 파일 완료 뒤 입력 내부 LF 때문에 Bareun 응답 문장 수가
   1대1 계약을 어겨 fail-closed로 중단됐다. 원본을 바꾸지 않는 메모리 전용
   1:1 치환을 적용한 뒤 기존 완료 receipt를 재사용해 이어서 처리했다.
2. 재개 중 Windows 외장하드의 순간적인 sharing violation 때문에 상태 파일의
   원자 교체가 한 번 중단됐다. Windows 오류 5와 32에만 제한 재시도를 적용하고
   다른 오류는 계속 fail-closed로 유지했다.
3. 최초 final 감사는 실제로 `passed=true`였지만 감독기의 PowerShell 함수가
   감사 JSON 출력과 종료코드를 함께 반환해 `final_audit_failed`로 잘못 기록했다.
   감사 출력은 host로만 전달하고 정수 종료코드 하나만 반환하도록 고쳤다.
   수정 뒤 같은 전수 감사를 다시 실행해 종료코드 0과
   `completed_and_audited`를 확인했다.

## 최종 검증

- Bareun 형태소 전수 분석: 완료
- `bulk_csv_v1` final 존재, `.building` 부재
- 독립 receipt/SHA 전수 감사: 통과
- Python 형태소 파이프라인 테스트: 4개 통과
- Windows PowerShell 5.1 안전성 검사: 74개 파일 통과
- Windows PowerShell 5.1 runtime 호환성 검사: 74개 스크립트 통과
- 외장하드 여유 공간: 안전선 15 GiB 이상

형태소 전수 결과는 여기서 동결한다. TextGrid 업데이트와 donor 자료를 이용한
WSD 호출 축소는 별도 후속 단계이며
`PLAN_post_bareun_morph_textgrid_context_wsd_20260829.md`의 gate를 따른다.
