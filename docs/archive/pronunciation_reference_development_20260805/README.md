# 발음 참조 레이어 개발 중간 산출물

2026-08-05 발음 참조 레이어 구현 과정의 중간 검증 보고서를 보존한다.

- `VERIFY_pron_reference_textgrid_backfill_pilot_2020_20260805.json`은 2020
  2세션 914개 파일럿의 첫 독립 감사다.
- 같은 914개에 대해 재실행 안정성까지 확인한 현재 정본 보고서는
  `outputs/reports/VERIFY_pron_reference_textgrid_backfill_2020_20260805.json`이다.
- `VERIFY_pron_reference_textgrid_backfill_diagnostic_2021_20260805.json`은 사용자
  PowerShell 시작 오류 뒤 첫 2021 세션 416개를 프로젝트 임시 root에서 재현한
  감사다. 416/416 통과 뒤 임시 TextGrid 419파일·3,598,599바이트는 제거했다.
  현재 2021 정본은 전수 보고서
  `outputs/reports/VERIFY_pron_reference_textgrid_backfill_2021_20260805.json`이다.
- 이 폴더의 보고서는 시행착오 추적용이며 현재 생산 상태를 판단할 때 사용하지
  않는다.
