# 2020–2025 사전 발음 참조 레이어 RUNBOOK

최종 갱신: 2026-08-05 KST

## 목적과 금지선

이 단계는 우리말샘 1:N·예외 발음을 형태소 occurrence에 연결하고, 표기·규칙
예상형·사전 후보·MFA phone을 함께 검색할 수 있게 만드는 파생 인프라다.

- `phones_mfa`는 강제정렬된 phone이며 실제 실현 정답이 아니다.
- 사전 후보는 독립형·등재형 참고값이며 문맥 실현 정답이 아니다.
- 기존 MFA DB, phone inventory, WAV, LAB, 6-tier TextGrid는 수정하지 않는다.
- 사전 후보 하나를 자동 정답으로 선택하지 않는다.
- 2020–2025는 모두 같은
  `config/pronunciation_reference_layer_v1.json` 계약을 사용한다.

## 연도별 순서

1. `morph_search.v3` 연도 manifest가 `success`인지 확인한다.
2. 해당 연도 6-tier 동반표 manifest가 `success`인지 확인한다.
3. 형태소 occurrence를 사전 `(표면형, 품사)` group에 연결한다.
4. 원 표기 어절 좌표로 규칙 예상형·사전 후보·MFA phone 비교표를 만든다.
5. 발화 수준 검색 label index를 만든다.
6. 필요하면 기존 6-tier와 별도 root에 7번째 `pron_reference_utt`를 backfill한다.
7. 각 단계 manifest·SHA와 독립 감사 보고서를 보존한다.

2020 Gate B를 다시 수행하는 절차가 아니다. 2020의 기존 정렬 정본은 읽기 전용
입력이고, 새 참조 레이어만 같은 계약으로 추가된다.

## 단일 실행기

읽기 전용 preflight:

```powershell
Set-Location "C:\Users\ari30\research\2026_summer_research"
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\run_pronunciation_reference_year.ps1" `
  -Year 2021 -Mode Tables -PreflightOnly
```

정규화 표까지만:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\run_pronunciation_reference_year.ps1" `
  -Year 2021 -Mode Tables
```

안정된 첫 2세션 7-tier 구현 파일럿:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\run_pronunciation_reference_year.ps1" `
  -Year 2021 -Mode Pilot -PilotSessions 2
```

연도 전수 7-tier backfill:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\run_pronunciation_reference_year.ps1" `
  -Year 2021 -Mode Full
```

전수는 세션 checkpoint 방식이다. 창이 닫혀도 같은 명령을 다시 실행하면 완료
세션을 건너뛴다. 연도 전체를 처음부터 다시 만들지 않는다.

## 출력 위치

```text
D:\10_LAYERS\10_pronunciation_reference\dictionary_pron_registry_v2_20260805\
  occurrences_v1\<YEAR>\
  compare_v2\<YEAR>\

D:\20_AUDIO\09_textgrid_pron_reference_v1_staging\<YEAR>\
  <SESSION>\*.TextGrid
  <SESSION>\pron_reference_utterance.csv.gz
  _checkpoints\<SESSION>.json
  _tables\pron_reference_utterance.csv.gz
  _tables\PRON_REFERENCE_BACKFILL_MANIFEST.json
```

2020 구현 파일럿은 전수 root와 분리한
`D:\20_AUDIO\09_textgrid_pron_reference_v1_pilot_20260805`에 있다.

## 실패와 재개 규칙

- annual gzip 표는 `.partial`을 닫고 검증한 뒤 최종 이름으로 승격한다.
- TextGrid는 세션별 임시 폴더에서 모두 검증한 뒤 세션 폴더로 승격한다.
- checkpoint contract ID가 다르면 기존 세션을 자동 덮어쓰지 않고 중단한다.
- 완료 세션과 파일 수가 맞으면 그 세션은 건너뛴다.
- 원 표기 어절과 형태소 어절 수가 다르면 추측 결합하지 않는다.
- 차이 flag만으로 MFA를 다시 돌리지 않는다. 실제 시간 경계 문제가 확인된
  발화만 별도 국소 shard 후보가 된다.

## 2020–2025 진행표

| 연도 | occurrence | 어절 비교/index | 7-tier | 전제 |
|---:|---|---|---|---|
| 2020 | 전수 검증 완료 | 전수 검증 완료 | 2세션 914건 구현 파일럿 통과 | 6-tier Gate B 완료 |
| 2021 | 12,015,453행 전수 검증 완료 | 6,610,698행 / 1,373,920발화 완료 | 전수 backfill 대기 | 6-tier 동반표 완료 |
| 2022 | 대기 | 대기 | 대기 | 해당 연도 MFA·6-tier 완료 뒤 |
| 2023 | 대기 | 대기 | 대기 | 해당 연도 MFA·6-tier 완료 뒤 |
| 2024 | 대기 | 대기 | 대기 | 해당 연도 MFA·6-tier 완료 뒤 |
| 2025 | 대기 | 대기 | 대기 | 해당 연도 MFA·6-tier 완료 뒤 |

## 현재 안전 정지점과 다음 실행

2026-08-05 현재 2020·2021 정규화 표는 모두 생성·독립 검증됐다. 2020의
2세션 914건 구현 파일럿이 같은 schema·tier 순서·코드 계약으로 통과했으므로,
계약이 바뀌지 않는 한 2021 파일럿을 반복하지 않는다.

다음 허용 단계는 **2021 `-Mode Full` 7-tier 파생 backfill**이다. 이 작업은
기존 6-tier를 읽고 별도 root에 7-tier를 만들며, MFA·DB·WAV·LAB·원 CSV는
변경하지 않는다. 완료 후 독립 검증과 2021 연구자 Gate를 닫기 전에는 2022
MFA를 시작하지 않는다.

비채택 v1과 폐기된 좌표 파일럿은 E: 읽기 전용 archive에 보존됐으며, 다시
생산 입력으로 사용하지 않는다. 위치와 SHA는
`outputs/reports/ARCHIVE_pronunciation_reference_pre_adoption_20260805.json`을
정본으로 한다.
