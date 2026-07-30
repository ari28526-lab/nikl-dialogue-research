# MFA r2 6개년 인프라 수용 파일럿 결과

- 실행일: 2026-07-30
- 기계 판정: 통과
- 연구자 인프라 검토: 대기
- 전수 MFA: 시작 전
- 실제 음운 실현 판정: 수행하지 않음

## 연구 목적과 이번 판정 범위

최종 연구 흐름은 검색 CSV에서 형태소·표기 환경 후보를 찾고, 해당 WAV와
TextGrid를 모아 KOINA 등 운율 정보를 결합한 뒤 연구자가 음성과 TextGrid를
직접 보고 실현 여부를 판정하는 것이다.

이번 파일럿은 그 연구가 가능한 인프라를 검증했다. MFA `phones`는 정렬·검색
보조 분절이며 실제 실현 판정값이 아니다.

## 표본과 고정 방법

- 2020–2025, 연도당 10발화
- 연도당 실제 화자 5명·서로 다른 세션 5개, 화자당 2발화
- 선택 세션 CSV aggregate SHA256:
  `c9de8400588339dc1962d9f6a3758220ff23b9501572f4d75f71723baa3be655`
- 공통사전 SHA256:
  `24c406604c86a5df833a7e47d809f252d6fc39dc566a6d3818b3d3ffeb04fb86`
- acoustic SHA256:
  `94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c`
- 허용 phone inventory: 109개
- 허용 inventory SHA256:
  `da65d15ff9e98496b688747d268b87d77639d961d46009e1adb568088880944b`
- 발음 모드: `common_pron_mfa_r2_latest_jamo`
- 정렬 중 inline G2P: 사용하지 않음
- LAB 정본: `pron_reference_form`

## 기계 결과

| 연도 | machine QC | TextGrid | 실제 spn | 허용 밖 phone |
|---|---:|---:|---:|---:|
| 2020 | 통과 | 10/10 | 0 | 0 |
| 2021 | 통과 | 10/10 | 0 | 0 |
| 2022 | 통과 | 10/10 | 0 | 0 |
| 2023 | 통과 | 10/10 | 0 | 0 |
| 2024 | 통과 | 10/10 | 0 | 0 |
| 2025 | 통과 | 10/10 | 0 | 0 |

2020은 direct DB 4-tier 10/10, 독립 구조 감사 invalid 0,
DB→TextGrid 표본 5세션 tier/byte exact 5/5도 확인했다. 같은 gate가
2021–2025 marker에도 결합됐다.

6개년 교차 감사:

- schema: `mfa_cross_year_method_consistency.v1`
- status: `passed`
- 기대/관측 연도: 6/6
- 연도 간 방법 계약 불일치: 0
- 같은 phone 생성 기준: 참
- 같은 허용 phone inventory: 참
- 허용 inventory 밖 관측 phone: 0

관측 phone 집합 자체는 각 표본 어휘가 다르므로 동일할 필요가 없다. 논문에서
쓸 수 있는 동일 기준 근거는 같은 모델·사전·G2P/adoption·입력/tier 계약과
같은 허용 inventory를 사용했고 각 연도 관측 phone이 그 부분집합이라는
결합이다.

## 산출물

D: 실행 루트:

```text
D:\mfa_eojeol\pilots\r2_infrastructure\mfa_r2_infra_pilot_20260730
```

Dropbox 연구자 검토 루트:

```text
C:\Users\ari30\Dropbox\MFA_R2_INFRA_PILOT_20260730
```

최종 전달 감사:

- 평면 파일: 246개
- 발화: 60개
- WAV/TextGrid/LAB/행별 CSV: 각 60개, payload 240개
- `REVIEW.xlsx`: 60행·15열, `검토입력`·`안내` 시트
- 상대 파일 링크: 240/240
- dropdown validation: 2개
- bundle schema: `mfa_r2_flat_review_bundle.v2`
- payload 목적지와 원본 SHA 불일치: 0
- 연구자 검토 상태: `pending`

기계가독 근거:

- `outputs/reports/RECOVER_mfa_r2_pilot_bundle_20260730.json`
- `outputs/reports/AUDIT_mfa_r2_pilot_review_delivery_20260730.json`
- D: `logs\cross_year_method_audit.json`
- D: `state\2020.machine_done.json` … `2025.machine_done.json`

코드 회귀검증:

- Python unittest: 222개 통과
- PowerShell 안전검사: 16개 파일 통과
- 핵심 Python 스크립트 compile: 통과
- `git diff --check`: 통과

## 시행착오와 교정

실행 중 다음 문제를 안전 중단으로 잡았다.

1. 숨은 PowerShell CP949의 IPA 출력 실패
2. 러너 제어 폴더를 부분 표본으로 잘못 감지
3. PowerShell 5.1의 정상 MFA stderr INFO 오류 승격
4. 미사용 예약 `<unk> → spn` pronunciation을 실제 interval로 오인
5. Dropbox가 완성 partial의 마지막 rename을 잠금
6. v1 bundle manifest가 rename 뒤 낡을 partial 절대경로를 기록

1–4는 실제 프로세스 exit와 사용된 DB interval을 기준으로 고쳤다. 5–6은
완성 partial의 244개 파일·현재 원본·기계 근거를 전수 재해시한 뒤 상대경로
v2 manifest로 정규화해 복구했다. 원시 corpus, 공통사전, 기존 정본과 D:
정렬 결과는 수정하지 않았다.

## 다음 gate

사용자는 Dropbox의 `REVIEW.xlsx`에서 다음만 검토한다.

1. 같은 접두사의 WAV/TextGrid/LAB/CSV 연결
2. 4-tier 구조와 처음·끝 경계 사용성
3. CSV가 형태소·표기 환경 검색과 파일 수집에 충분한지

구체적 음운 실현 여부는 이 표에서 판정하지 않는다. 작성 workbook을
검증기로 회수해 `approved` 보고서가 만들어진 뒤에만, 최종 동결 commit으로
2020 r2 전수 MFA를 시작한다.
