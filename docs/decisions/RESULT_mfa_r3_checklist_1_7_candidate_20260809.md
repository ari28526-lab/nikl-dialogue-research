# MFA r3 2020 실행 전 체크리스트 1–7 완료 후보

날짜: 2026-08-09 KST

상태: 체크리스트 1–7 통과, 연구자 release Gate 승인 전 안전 정지

## 결론

외부 기술·프로세스 리뷰 §7의 2020 실행 전 최소 체크리스트 1–7을 순서대로
구현하고 검증했다. 2020 실제 경로를 사용한 마지막 `-PreflightOnly`에는 18개
검사가 있으며, 17개가 통과하고 아직 수행하지 않은 8번
`production_release_gate`만 실패했다. 따라서 이는 실행 실패가 아니라 연구자
결정 직전의 의도된 `NO_GO`다. MFA 계산, r3 corpus 물질화, TextGrid 수출은
시작되지 않았다.

정본 기계 판독 보고서는
`outputs/reports/AUDIT_mfa_r3_checklist_1_7_candidate_20260809.json`이다.

## 항목별 결과

| # | 구현·검증 결과 | 판정 |
|---:|---|---|
| 1 | v3.1 staged adoption 계약과 불변 연구자 승인·append-only provenance sidecar 분리 | 통과 |
| 2 | 795,804형·796,061변이 staged r3 release와 byte projection·phone inventory 독립 감사 | 통과 |
| 3 | 2020 pronunciation-safe·follow-up·pre-MFA 기술 제외의 exact-ID 계약과 독립 감사 | 통과 |
| 4 | release·routing·연도 입력·사전·acoustic·G2P를 묶은 alignment contract ID | 통과 |
| 5 | r3 전용 이름공간·lock·절전·공간 산식·checkpoint runner와 실자료 preflight | 비-Gate 검사 통과 |
| 6 | 기존 6-tier를 유지하면서 r3 manifest 10필드·DB SHA·`phoneme_r_auto` 독립 재계산 | 통과 |
| 7 | PowerShell 전수 BOM/parse·안전성·PS5.1 호환성·전체 Python suite의 runner 내부 배선 | 통과 |

## 마지막 실자료 사전점검

- release: `common_pron_mfa_r3_20260809`
- 실제 검사 코드 커밋: `b7f2241b7cf28039c9b133d5ee62c27fc0839928`
- alignment contract ID:
  `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`
- 2020 예상 MFA 입력: 782,715발화
- D: 라벨: `DATA_SSD`
- 필요한 여유 공간: 53.726 GiB
- 관측 여유 공간: 194.869 GiB
- live lock 문제: 0
- PowerShell safety: 64파일 통과
- PowerShell runtime compatibility: 64스크립트 통과
- Python: 540테스트 통과
- 유일한 실패 검사: `production_release_gate`

Gate 파일은 계속
`status=blocked_pending_r3_staged_contract_implementation_review`,
`allowed_release_ids=[]`다. 이 문서는 Gate를 열지 않는다.

## 이번 단계에서 잡힌 시행착오

runner가 저장소 검사를 함수 안에서 실행할 때 외부 프로세스의 표준출력이
PowerShell 성공 파이프라인으로 흘러, 반환할 단일 영수증 객체와 함께 배열로
풀렸다. 그 결과 `powershell_safety_passed` 속성을 읽지 못하고 MFA 전에 안전
중단됐다. 검사 출력은 `Out-Host`로 보내고 함수 반환값을 영수증 객체 하나로
고정했다. 수정 후 같은 실제 preflight에서 세 검사 묶음과 비-Gate 17개 검사가
모두 통과했다. D: 자료와 생산 산출물에는 영향이 없다.

## 변경하지 않은 범위

- Stage 01–21 재실행·수정 없음
- D: 원 WAV·CSV·JSON 수정 없음
- r2 DB·TextGrid·CSV·완성본 수정 없음
- 기존 승인 6-tier 이름·경계 계약 변경 없음
- 718,364 follow-up exact-ID shard 폐기·임의 G2P 대체 없음
- production Gate 개방과 MFA 실행 없음

## 다음 한 단계

연구자가 이 체크리스트 1–7 완료 후보를 확인한 뒤에만 8번 release Gate를 단일
편집으로 연다. 그 다음 9번 2020 `-PreflightOnly`가 18/18 `GO`인지 확인하고,
그때 처음 장시간 MFA 실행 명령을 제공한다.
