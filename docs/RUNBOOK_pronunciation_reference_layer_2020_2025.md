# 2020–2025 사전 발음 참조 레이어 RUNBOOK

최종 갱신: 2026-08-05 KST

> **2026-08-07 상태 변경:** 이 v1 레이어는 r2의 규칙·사전·MFA 차이를 발견하게
> 한 읽기 전용 진단 자산으로 보존한다. 그러나 MFA 입력과 의도적으로 분리한 탓에
> 규칙 예상형 개선이 실제 정렬 사전에 전달되지 않았다. 지금은 v1 전수 backfill을
> 더 실행하지 않는다. r3에서는 같은 근거 열을 단일 canonical 발음 선택표가
> 소비하고, 채택된 phone projection과 검색 동반표가 같은 contract ID를 가져야 한다.

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

2020 Gate B를 다시 수행하는 절차가 아니다. 기존 r2 정렬과 참조 레이어는 읽기
전용 증거이며, r3 채택 전에는 새 연도 실행이나 전수 backfill 입력으로 쓰지 않는다.

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
| 2021 | 12,015,453행 전수 검증 완료 | 6,610,698행 / 1,373,920발화 완료 | 4,139세션·1,371,883개 전수 검증 완료 | 6-tier 동반표 완료 |
| 2022 | v1 생성 중단 | v1 생성 중단 | v1 생성 중단 | r3 canonical 표로 대체 |
| 2023 | v1 생성 금지 | v1 생성 금지 | v1 생성 금지 | r3 채택 뒤 새 계약 사용 |
| 2024 | v1 생성 금지 | v1 생성 금지 | v1 생성 금지 | r3 채택 뒤 새 계약 사용 |
| 2025 | v1 생성 금지 | v1 생성 금지 | v1 생성 금지 | r3 채택 뒤 새 계약 사용 |

## 현재 안전 정지점과 다음 실행

2026-08-06 현재 2020·2021 정규화 표는 모두 생성·독립 검증됐다. 2020의
2세션 914건 구현 파일럿이 같은 schema·tier 순서·코드 계약으로 통과했으므로,
계약이 바뀌지 않는 한 2021 파일럿을 반복하지 않는다.

2021 `-Mode Full`은 2026-08-05 21:20 KST에 독립 전수 검증까지 완료됐다.
기존 6-tier 의미 변경 0, 7번째 tier 경계·label 오류 0이다. 다시 실행하지 않는다.

2021 공식 연구자 24/24 승인과 당시 `2021 → 2022` Gate도 완료됐다. 이후 2022
표본이 r2 발음 입력 배선 문제를 발견했으므로, 2020 전수 7-tier와 2022–2025 v1
파생층은 더 실행하지 않는다. 이미 만든 자료는 r3 선택표·회귀검사의 입력 근거로
재사용한다.

비채택 v1과 폐기된 좌표 파일럿은 E: 읽기 전용 archive에 보존됐으며, 다시
생산 입력으로 사용하지 않는다. 위치와 SHA는
`outputs/reports/ARCHIVE_pronunciation_reference_pre_adoption_20260805.json`을
정본으로 한다.

2026-08-08 r3 no-rule 보류형 85,504개를 전수 특성화한 결과 모두 완성형 한글
어절이었다. 이 집합은 사전 발음 참조층의 숫자·기호 처리 대상이 아니며, 비음
동화·활음/모음 단위화·후두 대립 phone 매핑·분절 수 차이를 섞은 채 자동
발음으로 채우지 않는다. 상세 결과는
`docs/decisions/RESULT_common_pron_r3_no_rule_hold_characterization_20260808.md`를
따른다. 후속 coverage 감사에서는 수의적 위치동화를 의무 규칙에 추가하지 않고,
`pʲ`처럼 phone에서 연구용 음소를 일대일 복원할 수 없는 경우를 명시적으로
보류했다. 따라서 `phoneme_r_auto`는 phone 기반 넓은 표시일 뿐 확정 음소나
실현 전사가 아니다. 정본 해석은
`docs/decisions/RESULT_common_pron_r3_rule_phone_coverage_audit_20260808.md`를
따른다. r3 adoption이 끝날 때까지 2022–2025 발음 참조 파생층과 MFA를 실행하지
않는다.

후속 문맥 donor 감사에서는 frozen 기본사전의 단어·음절·이차조음 문맥을
보존해 기존 canonical donor와 합의·복수·충돌·근거 없음으로 분리했다. 이 중
기존 phone·Roman을 바꾸지 않는 onset+glide 단위화 6,141형만 readiness v3의
정렬 후보가 됐다. `중에서`의 `ng`, `걔`류 glide, `저희·너희`류 ㅢ처럼 새
분절을 넣거나 기존 phone을 바꾸는 경우는 계속 보류한다. 사전 참조층이 이 값을
실제 발음이나 표준발음으로 덮어쓰지 않도록 한다. 정본 결과는
`docs/decisions/RESULT_common_pron_r3_contextual_dictionary_donor_audit_20260808.md`와
`docs/decisions/RESULT_common_pron_r3_selection_readiness_v3_20260808.md`다.

Stage 15는 그중 phone 변경이 필요한 4,453형·72,030회를 4,900개 issue로
전수 분류했다. ㅢ `EU_G`, `Y/W` 활음, `ng`, 종성 삽입과 후두 대립·비음/종성·
모음·이차조음 치환은 각각 다른 근거 감사가 필요하다. 자동 후보는 0형이며
사전 참조층과 TextGrid에는 아직 반영하지 않는다. 정본 결과는
`docs/decisions/RESULT_common_pron_r3_unanimous_phone_change_audit_20260808.md`다.
