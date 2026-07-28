# 공통 발음사전 정책 A/B MFA 파일럿 실행서

작성일: 2026-07-28
상태: **실행기 구현·합성 검증 완료, 실제 6개년 소표본 실행 대기**

## 목적

정책 A와 B를 동일한 WAV·lab에 적용해 사전 예외·대체 발음의 추가가 MFA
phone열과 경계에 어떤 차이를 만드는지 확인한다.

- 정책 A: 기본 `korean_mfa.dict` + 표본 OOV의 현재 G2P 1-best
- 정책 B: 정책 A + exact-word로 연결된 `pron_1/2` 사전 발음

정책 B는 기존 발음을 교체하지 않고 복수 발음 후보로 **추가만** 한다.
기존 2020·2021 TextGrid·DB·marker와 canonical CSV를 수정하지 않는다.

## 전체 vocabulary와 소표본의 역할

6개년 전체 881,237어절을 대상으로 registry seed를 만든다. 그러나 A/B
정렬 전에 전체 OOV를 모두 G2P하지는 않는다. 파일럿에서 선택된 발화에
필요한 어절과 사전 한글 발음만 current G2P로 phone encoding한다.

이는 파일럿 전 불필요한 수시간 계산을 피하기 위한 것이다. 정책을 채택한
뒤 같은 계약으로 6개년 전체 파생사전을 별도 release로 만든다.

표본은 연도마다 다음 구조다.

```text
서로 다른 실제 화자 5명
  ├── 사전 발음 후보가 철자와 다른 stress 발화 1개
  └── 같은 화자·세션의 비대상 control 발화 1개
```

따라서 기본값은 6개년 × 5화자 × 2발화 = 60발화이며 A/B 각각 같은
60발화를 정렬한다. A와 B corpus의 WAV·lab SHA256은 manifest에서
byte-identical임을 검사한다.

## 실행 전 조건

- D:가 `DATA_SSD`
- D: 여유 40GiB 이상
- 다른 대량 MFA lock 없음
- Dropbox 대량 복사·KOINA·다른 MFA 동시 실행 없음
- `common_pron_pilot_full6y_20260728` release 존재
- MFA 설치 패치 검증 통과

## PowerShell 명령

새 PowerShell 창에서 다음을 그대로 실행한다.

```powershell
cd "C:\Users\ari30\research\2026_summer_research"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  ".\scripts\run_common_pron_ab_pilot.ps1" `
  -ReleaseId "common_pron_pilot_full6y_20260728" `
  -RunId "ab_stress_control_20260728_01" `
  -SpeakersPerYear 5 `
  -NumJobs 4
```

창을 닫거나 컴퓨터를 절전하지 않는다. 실패하거나 중단됐을 때는 같은 명령,
같은 `RunId`로 다시 실행한다. 완료 marker는 검증 후 재사용하고, marker가
없는 부분 출력은 run 폴더 안 `archive_failed`로 이동한 뒤 재시도한다.

동시에 두 개의 A/B 러너를 실행하지 않는다. 새로운 독립 파일럿이 필요할
때만 새 `RunId`를 쓴다.

## 단계

1. 전수 vocabulary–사전 exact-word registry seed
2. 연도별 stress/control 표본 및 A/B 동일 corpus
3. 표본 어절 current G2P 1-best
4. 사전 한글 발음→current MFA phone encoding
5. 정책 A/B 표본 파생사전과 phone inventory gate
6. A/B MFA align과 각각의 표준 4-tier/QC
7. phone열·경계 자동 비교와 수동 검토 묶음

MFA 3.4 inline G2P와 맞추기 위해 `num_pronunciations=1`과
`strict_graphemes=True`를 사용한다. 사전 한글 발음이 현재 phone으로
변환되지 않거나 phone inventory 밖 기호를 만들면 정책 B에 조용히 넣지 않고
제외 사유와 함께 기록한다.

## 완료 후 먼저 볼 파일

```text
D:\mfa_common_pron\releases\
  common_pron_pilot_full6y_20260728\
  06_ab_results\
  ab_stress_control_20260728_01\
  comparison\
  RESULTS.md
```

발화별 A/B WAV·TextGrid 경로와 자동 비교값:

```text
comparison\ab_utterance_comparison.csv
```

사전 추가 후보와 출처:

```text
04_mfa_lexicons\pilots\
  ab_stress_control_20260728_01\
  policy_B_added_variants.csv
```

## 연구자 검토

1. `sample_role=stress`를 먼저 본다.
2. 같은 발화의 A/B TextGrid와 WAV를 나란히 연다.
3. 사전 발음 추가가 해당 어절의 phone열·경계를 개선했는지 기록한다.
4. control에서 불필요한 경계 이동이나 오정렬이 늘지 않았는지 본다.
5. 정렬 성공률·`spn`·phone 변화와 수동 청취를 함께 판단한다.

자동 비교는 정책 B를 승격하지 않는다. 연구자 검토 뒤 정책 A가 baseline과
동등한 cache인지, 정책 B를 공통 release로 채택할지를 결정한다.

wav2vec2 phone 후보는 이 A/B 결과를 고치지 않는다. 후속 소표본에서 별도
append-only 열 또는 연구자 점검 사본의 별도 tier로만 추가한다.

## 2026-07-28 최초 실행 중단과 수정

최초 실행은 registry와 60발화 A/B 입력을 만든 뒤 표본 어절 G2P의
`Generating pronunciations...`에서 중단됐다. G2P 317개는 독립 실행에서
`num_jobs=1`과 `4` 모두 약 64초에 317/317행을 정상 생성했다.

원인은 Windows PowerShell 5.1에서 네이티브 stderr를 `ErrorRecord`로
바꾸는 동작과 전역 `$ErrorActionPreference='Stop'`의 결합이었다.
MFA의 정상 progress가 오류로 오인됐다. 실행기는 MFA 호출 경계에서만
`Continue`를 쓰고 실제 process exit code를 즉시 보존하도록 수정했다.

새 RunId는 필요 없다. 위와 같은 명령을 같은
`ab_stress_control_20260728_01`로 재실행하면 완료 marker가 있는 단계는
검증 후 재사용하고, marker 없는 G2P temp는 `archive_failed`에 보존한 뒤
다시 시작한다. 자세한 실측은
`MONITOR_common_pron_AB_pilot_20260728.md`에 기록한다.
