# 2020 생산 완료와 Gate B 통과 결정

결정일: 2026-08-03 KST
적용 범위: 2020 공통 Jamo r2 신규 정렬, 연구 6-tier, 동반표, 2021 진입 gate

## 결정

2020은 다음 계약을 모두 만족해 완료로 판정한다.

- 동일 생산 기준: Korean MFA acoustic v3.3.0, Jamo G2P v3.2.0,
  `common_pron_mfa_r2_20260728`
- 입력: active LAB 868,550개, 승인 제외 2,250건
- 정렬·출력: 868,187개 6-tier TextGrid, post-MFA 미정렬 363건은 승인 제외표에
  사유를 보존
- 동반표: utterance 868,187, word 4,973,795, phone 19,101,192,
  excluded 2,250행
- 독립 전수 감사: 하드 실패 0
- 보존 DB 재생성 표본: semantic 24/24, byte 24/24
- 연구자 생산 표본 검토: 24행·24세션·24화자 모두 승인
- Gate B: 16/16 core check 통과, `failed_checks=[]`,
  `allow_remaining_years=true`

연구자 검토는 WAV·LAB·TextGrid의 동일 발화, 정렬의 전반적 타당성, 6개 tier,
검색 정보의 이해 가능성을 확인한 인프라 QC다. 실제 음운 실현 판정은 수행하지
않았으며 MFA/phoneme 보조층을 실현 정답으로 승격하지 않는다.

## 파일 가장자리 경계 해석

발화의 유표 구간이 0초나 `xmax`와 같으면 Praat에서는 파일 테두리가 경계라서
별도 내부 세로선이 보이지 않을 수 있다. 검토 표본 네 건을 실제 TextGrid 값으로
확인한 결과 모든 6개 tier는 빈 interval을 포함해 0–xmax를 연속적으로 덮고,
세 검색 tier의 유표 span은 `words`와 정확히 같았다. 시간정보 손실이나 검색
결함이 아니므로 인공 경계를 추가하지 않는다.

## 근거

- `outputs/reports/GATE_B_2020_TO_2021.json`
- `outputs/reports/GATE_B_2020_core.json`
- `outputs/reports/GATE_B_2020_source.json`
- `outputs/reports/mfa_year_queue_mfa_r2_prod_2020_export_20260803/2020/01_year_audit.json`
- `outputs/reports/mfa_year_queue_mfa_r2_prod_2020_export_20260803/2020/02_db_sample.json`
- `outputs/reviews/mfa_production_2020_mfa_r2_prod_2020_export_20260803/04_RESEARCHER_APPROVAL.json`

## 후속 안전 정지점

2020 계산·export·검토 wrapper는 정상 절차에서 다시 실행하지 않는다. 2021은
아직 시작하지 않았다. 다음 단계는 Gate B를 입력으로 하는
`prepare_remaining_mfa_approval_reviews.ps1`이며, 후보 승인 전에는 MFA를
시작하지 않는다.
