# 2024 r3 TextGrid 표시 label 내장 줄바꿈 안전 중단과 복구

작성일: 2026-08-14
상태: 복구·회귀시험·독립 전수 QC 완료

## 사건

2024 r3 MFA는 정상 완료됐지만 연구용 6-tier 수출 593,530건 중 두 발화의 검색
원문 `form`에 포함된 U+000A가 TextGrid label에 그대로 전달되어 수출이 안전
중단됐다. 실패 발화는 `SDRW2400001393.1.1.156`과
`SDRW2400002782.1.1.226`이다. 이는 MFA 정렬 오류, 음향모델 오류 또는 CSV
레코드 파싱 오류가 아니라, 유효한 multiline CSV 필드와 단일행 TextGrid 표시
label 사이의 표현 계약 누락이었다.

## 복구 원칙

1. 원 CSV와 동반표는 원문을 그대로 보존한다.
2. 파생 TextGrid의 `utterance`·`morph_analysis` 표시 label에서만 LF, CR, NEL,
   U+2028, U+2029를 ASCII 공백 하나로 바꾼다.
3. TAB 등 승인되지 않은 제어문자는 hard failure로 남긴다.
4. 실패 보고서·DB SHA·exact-ID·원문 fingerprint가 맞는 두 누락 파일만 만든다.
5. 이미 성공한 593,528개 TextGrid는 다시 생성하거나 덮어쓰지 않는다.
6. MFA, DB, WAV, LAB, 원 CSV, 2020–2023 완성본은 변경하지 않는다.

## 구현과 증거

- 공통 label 함수: `scripts/python/research_textgrid_v2.py`
- 표적 복구기: `scripts/python/repair_mfa_textgrid_search_label_controls.py`
- checkpoint 최종화: `scripts/python/finalize_mfa_db_research_6tier_repair.py`
- PowerShell 진입점: `scripts/run_mfa_r3_research_export.ps1 -ResumeFailedReport`
- 초기 실패:
  `outputs/reports/EXPORT_mfa_r3_research_6tier_2024_20260814_104221.json`
- exact-ID 복구:
  `outputs/reports/REPAIR_label_controls_EXPORT_mfa_r3_research_6tier_2024_20260814_104221.json`
- 복구 완료:
  `outputs/reports/EXPORT_RECOVERED_mfa_r3_research_6tier_2024_20260814_124518.json`
- 독립 QC:
  `outputs/reports/mfa_r3_research_qc_common_pron_mfa_r3_20260809/2024/QC_STATE.json`

최종 TextGrid 593,530개와 승인 제외 874건이 입력 594,404건을 100% 회계했고,
25개 hard-failure 범주는 모두 0이었다. 보존 DB 재수출 표본은 semantic·byte
모두 24/24 일치했다.

## 재발 방지와 방법론 기록

향후 모든 연도와 후속 shard에서 같은 표시 정규화를 적용하되 원 데이터 정규화와
혼동하지 않는다. 논문 방법 각주에는 “원문 CSV의 내장 줄바꿈은 보존하고, Praat
TextGrid의 단일행 표시 호환성을 위해 파생 표시 tier에서만 공백으로 정규화했으며,
기존 정렬과 시간 경계는 재계산하지 않았다”고 기록한다.
