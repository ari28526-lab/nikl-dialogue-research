# 2023 완료 뒤 저장공간 정리와 2024 진입 계획

최종 갱신: 2026-08-13 KST
상태: 읽기 전용 inventory 실행 전; 실제 이동·삭제 미승인

## 결론

2023 r3의 정렬·6-tier 수출·독립 QC가 완료됐으므로 다음 단계는 곧바로 2024
MFA가 아니다. 먼저 완료본을 동결하고 D:에서 재생성 가능한 중간물의 정확한
회수량을 계산해야 한다.

2026-08-13 관측값은 다음과 같다.

| 드라이브 | 역할 | 여유 |
|---|---|---:|
| D: `DATA_SSD` | 원자료·현재 생산 | 48.604 GiB |
| E: | 읽기 전용 archive 후보 목적지 | 1,834.453 GiB |
| H: `SAMSUNG` | 과거 전체 백업 | 93.036 GiB |

D: 48.604 GiB는 과거 r3 runner 보수적 요구량 53.726 GiB보다도 작다. 2024의
실제 요구량은 2024 exact-ID 입력 계약을 만든 뒤 같은 capacity formula로 다시
계산해야 하지만, 현재 상태에서 장시간 MFA를 먼저 시작하는 것은 허용하지 않는다.

## 절대 보존 대상

다음은 용량 정리 대상이 아니다.

- 원 WAV·JSON·형태소 CSV와 7개 조합검색표
- 채택 공통발음 r3 release·사전·모델·Stage 01–21 계약과 감사 증거
- 2020–2023 `ALIGN_DONE` marker, 입력·정렬·승인 계약과 로그
- 2020–2023 보존 SQLite DB
- 최종 r3 6-tier TextGrid와 gzip 동반표 4종
- post-MFA 제외 exact-ID와 독립 QC state·보고서
- 2020–2023 완료 SHA를 입력으로 하는 다음 연도 전환 Gate 증거

최종 DB와 6-tier는 2020–2025 교차 감사가 끝나기 전에는 D:에서 옮기거나
삭제하지 않는다.

## 정리 우선순위

### 1순위 — 완료 연도 r3 temp의 재생성 가능한 계산 중간물

`D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\YEAR`에서 DB는 보존하고,
독립 QC 뒤 재생성 가능한 `.ark`, `.scp`, interval 중간 CSV만 후보로 분류한다.
모델·dictionary·tree·log·yaml과 미분류 파일은 자동 정리하지 않는다.

현재 단계는 삭제 기능이 없는 inventory만 수행한다. DB SHA가 각 연도
`QC_STATE.json`과 일치하고 SQLite transaction 파일이 없을 때만
`ready_for_user_review`가 된다.

### 2순위 — 완료 연도 r3 corpus와 QC scratch

1순위만으로 공간이 충분하지 않을 때 검토한다. corpus WAV가 원 WAV의 hardlink라면
링크 제거로 WAV 본문 용량은 거의 회수되지 않을 수 있으므로, LAB·메타데이터와
hardlink 수를 분리해 산정해야 한다. `qc_scratch`는 최종 QC state와 표본 보고서가
동결된 뒤의 재생성 가능 후보지만 아직 inventory 범위에 넣지 않았다.

### 3순위 — r2·구 7-tier 역사 산출물

2020–2022 r2 DB·TextGrid와 2021 구 7-tier는 현행 r3 생산 입력이 아니라 비교·
시행착오 증거다. 필요하면 E:에 압축 archive를 만들고 7-Zip test·파일 수·원본
bytes·SHA manifest를 검증한 뒤 D: 사본 제거를 별도 승인한다. 기존 E: archive와
중복인지 먼저 대조하며, 중복 아카이브를 또 만들지 않는다.

## 단계별 Gate

```text
A. 읽기 전용 temp inventory
  → B. 연도별 DB SHA·QC·transaction·미분류 0 확인
  → C. 예상 회수량과 2024 요구량 비교
  → D. exact allowlist archive/apply 계획 작성
  → E. 연구자 명시 승인
  → F. E: archive 생성·검사
  → G. manifest의 정확한 후보만 D:에서 제거
  → H. D: 여유와 2020–2023 DB·6-tier·계약 재검증
  → I. 2023→2024 전환 Gate
```

어느 단계에서도 드라이브 root, release root, 연도 상위 폴더를 통째로 재귀
삭제하지 않는다. 실패하면 원본을 유지하며 자동 clean이나 다음 후보 확장을 하지
않는다.

## 현재 실행 명령

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\prepare_mfa_r3_storage_cleanup_review.ps1"
```

이 명령은 2020–2023 DB SHA와 temp 파일 목록을 읽고 저장소에 JSON 보고서만
만든다. D:/E: 삭제·이동·압축은 0건이며 실제 정리 기능도 없다.

## 다음 결정

inventory 결과의 연도별 후보 GiB와 blocker를 확인한 뒤 결정한다.

1. 1순위 temp 후보만으로 2024 MFA·수출·QC에 충분한가
2. 부족하면 corpus/QC scratch 또는 r2 역사 산출물 중 무엇을 E:로 옮길 것인가
3. 2024 진입 전 확보해야 할 여유는 2024 exact-ID 계약의 실제 capacity formula에
   후속 6-tier 수출·QC 여유를 더해 확정한다.

