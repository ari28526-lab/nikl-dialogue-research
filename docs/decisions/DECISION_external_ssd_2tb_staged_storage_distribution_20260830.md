# 2TB 외장 SSD 단계적 저장 분배 결정

작성일: 2026-08-30 KST

상태: **사용자 용량 결정 채택 — 실물 연결·배치·복사 전 Gate 유지**

## 결정

장기적으로 4TB가 현상별 자체 완결형 자료와 복수 버전 보존에 더 여유롭지만,
2026-08-30의 SSD 가격과 현재 연구비 부담을 고려해 다음 신규 SSD는 2TB로
정한다. 이는 모든 대형 자산을 한 볼륨에 영구 통합한다는 결정이 아니라, 현재
1TB D: 정본과 역할을 나누는 단계적 확장 결정이다.

신규 2TB SSD의 제품·실사용 용량·volume ID·드라이브 문자·USB 연결 속도는
아직 확정하지 않는다. 실물을 연결한 뒤 읽기 전용 인벤토리와 실제 포트 속도를
확인하고 별도 배치 Gate에서 기록한다.

## 현재 보호 자산과 즉시 금지 사항

- 현재 D:는 약 953.854 GiB 볼륨이며 기록 시점에 약 919.7 GiB가 사용 중이다.
- D:의 원본 WAV, 원본 JSON, 2020–2025 r3 MFA DB·6-tier TextGrid, 정본 CSV와
  reference는 계속 읽기 전용 정본으로 취급한다.
- 실행 중인 Bareun v3.1 형태소 TextGrid 전수와 자동 독립 SHA 감사가
  `passed_pending_external_consolidation`에 도달하기 전에는 D:/C: 생성물,
  checkpoint, receipt, lock, 로그를 이동·삭제·수정하지 않는다.
- 신규 SSD를 연결하더라도 현재 runner를 재시작하거나 출력 경로를 실행 중에
  바꾸지 않는다.

## 잠정 두 볼륨 역할

실물 연결 뒤 다른 증거가 나오지 않는 한 다음을 기본 배치안으로 사용한다.

| 논리 역할 | 우선 볼륨 | 기본 자산 | 운영 성격 |
|---|---|---|---|
| `corpus_core_readmostly` | 현재 D: | 원본 WAV·JSON, r3 MFA, 기존 정본 CSV·reference | 읽기 중심, 변경 최소화 |
| `derived_phenomena_working` | 신규 2TB SSD | Bareun v3.1 파생 TextGrid, WSD sidecar, 현상별 후보·검토·Praat 작업본 | 버전형 생성·수정·감사 |
| `verified_archive` | 보유 HDD | 완료 release의 SHA 검증 백업·과거 버전 | 느린 보존 사본, 실행 작업 금지 |

이 표는 파일 이동 승인이 아니다. 새 SSD의 실제 사용 가능 용량, 기존 D:의
자산별 총 바이트, 완성 TextGrid의 D:/C: 분산량과 현상별 예상 증가량을 다시
계산한 뒤 확정한다.

## 현상별 자료의 용량 원칙

1. 현상별 작업본은 canonical WAV와 source TextGrid를 `utt_id`, volume ID,
   상대경로와 SHA로 참조하는 것을 기본으로 한다.
2. 화면 검토·Dropbox 전달·공동연구자 인계처럼 자체 완결형 묶음이 필요한
   경우에만 승인된 exact WAV와 read-only TextGrid를 복사한다.
3. source TextGrid와 `praat_work`를 같은 경로에서 덮어쓰지 않는다.
4. 같은 WAV를 현상별 폴더마다 무제한 복제하지 않고, 중복 바이트와 참조 수를
   manifest로 회계한다.
5. 신규 2TB SSD는 정상 작업 중 최소 여유 목표를 20%로 두되, 정확한 hard floor는
   실사용 용량과 workload 표본을 확인한 별도 Gate에서 확정한다.

## 신규 SSD 연결 후 Gate

1. 제품명·시리얼을 노출하지 않는 내부 volume ID, 실사용 GiB, 파일시스템,
   드라이브 문자와 포트 연결을 기록한다.
2. 미니 PC의 USB-A/USB-C 실제 5/10Gbps 지원과 UASP·S.M.A.R.T. 가시성을
   확인한다. 단자 모양이나 색깔만으로 속도를 추정하지 않는다.
3. 현재 D:, C: spill, 신규 SSD의 자산별 파일 수·총 바이트·SHA inventory를
   읽기 전용으로 만든다.
4. `corpus_core_readmostly`와 `derived_phenomena_working`의 실제 배치표와 복사 뒤
   예상 여유 공간을 사용자에게 제시한다.
5. 이동이 아니라 copy-first로 수행하고 파일 수·총 바이트·manifest·SHA를
   전수 검증한다.
6. 검증된 새 사본과 삭제 후보를 다시 제시하고, 별도 명시적 승인 뒤에만 기존
   파생 사본을 제거한다. 원본 WAV·JSON은 삭제 후보에 자동 포함하지 않는다.

## 장기 분업화

2TB가 현상별 자체 완결형 자료와 복수 버전에 부족해지는 시점에는 새 대량 복사를
즉시 시작하지 않는다. 먼저 `corpus_core_readmostly`와
`derived_phenomena_working`의 실제 증가율을 보고, 이후 SSD 가격과 예산에 따라
말뭉치 정본용과 현상별 작업용을 물리적으로 더 분리한다. 최종 release manifest는
단일 드라이브 문자가 아니라 volume ID와 상대경로로 두 볼륨을 결속한다.

## 현재 다음 한 단계

실행 중인 Bareun TextGrid 생성과 독립 SHA 감사를 계속 감시한다. 신규 2TB SSD가
도착하더라도 `passed_pending_external_consolidation` 전에는 통합을 시작하지 않는다.
