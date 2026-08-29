# 바른 v3.1 형태소-only CSV 전수 밤샘 운영 계획

작성일: 2026-08-28 KST

상태: **2026-08-29 전수 완료, final 승격 및 독립 감사 통과**

완료 수치와 장애·복구 기록은
`RESULT_bareun_morph_csv_full_completed_20260829.md`를 따른다.

## 결정

현재 `with_sense=false`로 진행 중인 5,103,356발화의 새 형태소 분석을
중단하지 않는다. 동형이의어 포함 전수의 API 병목을 피하기 위해 우선 새 버전
형태소 결과를 완성하고, WSD는 그 다음 별도 단계에서 점검한다.

실행 중 API의 `Gateway Timeout`, `ServiceUnavailable`, 429/502/503/504,
`DEADLINE_EXCEEDED`, 연결 reset과 같은 일시 장애가 발생하면 완료된 파일별
receipt와 SHA를 검증해 그대로 재사용하고 실패 중이던 파일만 새 `.building`에서
다시 만든다. 인증·입력 계약·무결성 오류는 자동 반복하지 않는다.

## 무인 복구 계약

- 현재 실행 PID가 살아 있는 동안 감시기는 API를 추가 호출하지 않는다.
- 새 재개 세션의 내부 API 재시도는 최대 6회이며 2·4·8·16·32초 backoff를 쓴다.
- 실행이 일시 API 오류로 끝나면 5분에서 시작해 10·20·40·60분으로 냉각한다.
- 진척 뒤 발생한 새 장애는 냉각을 5분으로 되돌린다.
- 진척 없는 장애는 최대 60분까지 늘리고 자동 재개는 총 24회로 제한한다.
- final이 없는데 `running` 또는 파일 이벤트 `completed` 상태에서 PID가 사라지면
  비정상 종료로 보아 `-Resume`한다.
- D: 여유가 15 GiB 미만이면 자동 재개하지 않는다.
- 원 CSV, 기존 Bareun/WSD, TextGrid, WAV는 수정·삭제·이동하지 않는다.
- 동일 감시기의 중복 실행은 Windows named mutex로 차단한다.

## 실행과 상태 확인

현재 전수 실행과 별도 PowerShell에서 다음 감시기를 한 번 실행한다.

```powershell
.\run_bareun_morph_csv_unattended.ps1 `
  -Execute `
  -ApprovedBy ari30 `
  -ApprovalToken BAREUN_MORPH_CSV_FULL_20260828
```

읽기 전용 상태 확인은 다음 명령을 쓴다.

```powershell
.\show_bareun_morph_csv_status.ps1
```

감시 기록은 `logs/bareun_morph_csv_unattended_20260828.jsonl`에 남는다.

## 완료 조건

1. 외장하드의 `bulk_csv_v1.building`이 `bulk_csv_v1`로 원자 승격된다.
2. 17,156개 receipt와 5,103,356발화 회계가 일치한다.
3. 원 CSV와 모든 압축 결과의 SHA-256 검증이 통과한다.
4. 형태소-only 계약에서 의미번호 수가 0이고 TextGrid·WAV 접근이 없음을 확인한다.
5. 독립 감사 보고서
   `outputs/reports/AUDIT_bareun_morph_csv_full_20260828.json`의
   `passed`가 `true`다.

이 완료 조건은 몇 시간 뒤 자동 만료되는 작업이 아니다. 현재 실측 ETA에
여유를 둔 첫 운영 창은 24시간으로 보되, goal은 위 다섯 조건을 만족할 때까지
유지한다.

형태소 final 감사 뒤의 MFA TextGrid 활용과 문맥 donor WSD 호출 축소는
`PLAN_post_bareun_morph_textgrid_context_wsd_20260829.md`를 따른다.
