# Bareun v3.1 morphology-only 전수 분석 줄바꿈 응답 불일치와 안전 재개

날짜: 2026-08-29 KST

## 결과

전수 분석은 12,671/17,156개 CSV, 4,122,537발화 완료 뒤
`single AnalyzeSyntax cardinality mismatch: 2/1`에서 fail-closed로 멈췄다.
완료 디렉터리와 파일별 receipt는 그대로 보존됐고 final 승격은 일어나지 않았다.

실패 지점은 다음 입력 파일의 156번째 발화에 포함된 단일 LF였다.

```text
NIKL_DIALOGUE_2024_v1.0/SDRW2400001393.csv
utt_id=SDRW2400001393.1.1.156
```

원문 내용은 이 문서에 기록하지 않는다. 원본 CSV의 SHA와 내용은 변경하지 않는다.

## 원인

CSV에서는 하나의 `form` 필드이지만 Bareun `AnalyzeSyntax`가 포함된 줄바꿈을
문장 경계로 해석해, 단건 요청에서 두 문장을 반환했다. 따라서 한 입력 발화와
한 응답 문장을 엄격히 대응시키는 zero-drop 계약이 정상적으로 실행을 중단했다.

## 채택한 처리

원본 `form`과 출력 `form`은 그대로 보존한다. API 요청용 메모리 복사본에서만
CR, LF, VT, FF, NEL, U+2028, U+2029를 각각 ASCII 공백 한 글자로 1:1 치환한다.
문자 길이가 변하지 않으므로 Bareun 응답의 UTF-32 위치 오프셋을 원문 위치와
대응시킬 수 있다. 치환된 발화 수와 문자 수는 새 파일 receipt와 최종 manifest에
기록하고 독립 감사에서 합계를 검증한다.

기존 완료 12,671개 파일은 재분석하지 않는다. 실패 파일의 `.building` 흔적은
기존 재개 로직이 `interrupted` 증거 폴더로 보존한 뒤 그 파일부터 다시 처리한다.

## 검증

- Python 단위 테스트: 원문 보존, 요청문 1:1 치환, 길이 보존 통과
- 실제 실패 batch: 요청 40개, 응답 40개 통과
- Windows PowerShell 5.1 안전성 검사 통과
- Windows PowerShell 5.1 runtime 호환성 검사 통과
- morphology resume preflight: `ready=true`, 17,156개 입력, 여유 공간 안전선 통과

첫 재개 시 기존 receipt를 검증하며 상태를 갱신하는 과정에서 Windows 외장하드의
`STATE.json.partial` 원자 교체가 순간적인 `Access denied`를 내어 다시
fail-closed로 멈췄다. 원자적 파일·디렉터리 승격은 Windows sharing violation
5 또는 32에 한해서만 최대 40회, 최대 0.5초 간격으로 제한 재시도하도록
보강했다. 다른 오류는 그대로 즉시 실패한다.

원본 CSV, 기존 Bareun/WSD 결과, TextGrid, WAV는 수정하지 않는다.
