# 연도별 10발화·5화자 MFA 파일럿 실행서

작성일: 2026-07-24
대상: NIKL 일상대화 2020–2025
실행 ID: `pilot_year10_speaker5_20260724`

## 1. 목적

전량 MFA를 시작하기 전에 6개년 각각에서 작은 표본을 처음부터 끝까지
통과시켜 다음 인프라를 검증한다.

1. 형태소/검색 CSV의 발화가 올바른 WAV와 연결되는가
2. 한 화자에 편중되지 않고 실제 화자 여러 명을 MFA가 구분하는가
3. 어절 lab, G2P MFA 원출력, 표준 4-tier TextGrid가 누락 없이 생성되는가
4. WAV와 TextGrid의 길이 및 tier·시간 경계가 유효한가
5. 실패 로그와 중간 산출물을 보존한 채 같은 명령으로 재개할 수 있는가

이 파일럿의 MFA `phones`는 연구자가 음성 구간을 찾기 위한 대략적 분절이다.
ㄴ 삽입 등 음운 현상의 실제 실현 여부를 자동 판정하지 않는다.

## 2. 표본 단위와 층화

- 연도별 발화: 10개
- 실제 화자: CSV `speaker_id` 기준 정확히 5명
- 화자당 발화: 2개
- 원 세션: 정확히 5개(각 세션에서 화자 한 명만 선택)
- 연도: 2020–2025
- 총계: 60발화, 연도-화자 조합 30개

과거의 “세션 폴더=화자” 가정과 실제 대화 참여자 ID를 구분한다. MFA 입력은
`corpus/{연도}/{speaker_id}` 구조로 만들어 MFA도 실제 화자 5명을 인식하게
한다. 원 세션 ID는 manifest에 별도로 보존한다.

선정은 `speaker5_year10_v1` seed와 SHA256 정렬을 사용한다. 파일시스템 열거
순서에 의존하지 않으므로 같은 입력과 seed에서는 같은 발화가 선택된다. 선택
가능 조건은 다음과 같다.

- `form`에서 비어 있지 않은 어절 lab을 만들 수 있음
- WAV가 존재하고 PCM WAV 헤더·길이가 유효함
- 기존 형태소 TextGrid가 존재함
- 바른 CSV와 search master에서 같은 `utt_id`를 찾을 수 있음
- 선택 화자의 `_speakers.csv` 메타데이터가 존재함

이는 모집단 대표성을 추정하는 통계 표본이 아니라 파일 연결과 정렬 인프라를
시험하는 층화 smoke test다.

## 3. 산출 폴더

```text
D:\mfa_eojeol\pilots\year10_speaker5\
└─ pilot_year10_speaker5_20260724\
   ├─ selection_manifest.csv
   ├─ selection_manifest.json
   ├─ corpus\{year}\{speaker_id}\          WAV + 어절 lab
   ├─ csv\{year}\
   │  ├─ bareun_selected.csv              형태소 분석 선택행 10개
   │  ├─ search_master_selected.csv       검색 마스터 선택행 10개
   │  └─ speaker_metadata_selected.csv    실제 화자 메타 5개
   ├─ mfa_raw\{year}\{speaker_id}\         MFA 원 TextGrid
   ├─ textgrid_4tier\{year}\{speaker_id}\  최종 표준 4-tier
   ├─ qc\                                  발화별 CSV + 연도별 JSON
   ├─ state\                               단계별 검증 완료 마커
   ├─ temp\                                MFA 재현·진단용 temp
   ├─ logs\                                단계별 stdout/stderr
   ├─ pilot_summary.json
   └─ RESULTS.md
```

`D:\00_RAW`, `D:\10_LAYERS`, `D:\20_AUDIO\06_textgrid_eojeol`,
`D:\20_AUDIO\07_textgrid_eojeol_g2p_staging`은 수정하지 않는다. 이 파일럿은
완전히 별도 폴더에서만 생성된다.

관련 search master CSV는 2026-07-23 전량본에서 선택한 현재 상태의 행이다.
따라서 7/24 감사에서 확인한 것처럼 lexicon 예외 발음과 coverage가 아직
미반영된 스냅숏이다. 파일 대응 파일럿에는 사용할 수 있지만 “최종 교정 CSV”로
해석하지 않는다.

## 4. 실행

PowerShell에서 다음 한 줄을 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\ari30\research\2026_summer_research\scripts\run_stratified_mfa_pilot.ps1" -RunId pilot_year10_speaker5_20260724
```

2020은 2026-07-24 실제 시험에서 이미 통과했다. 같은 명령을 실행하면 완료
마커를 검증한 뒤 2020을 건너뛰고 2021–2025를 계속한다.

중단되거나 한 연도에서 실패하면 같은 명령을 다시 실행한다. 검증된 완료
연도는 건너뛰고, 미완료 MFA 원출력은 삭제하지 않고 해당 run 폴더의
`archive_failed`로 이동한 뒤 재시도한다. 손상된 완료 마커는 자동으로
신뢰하지 않고 중단한다.

## 5. 실제 시행착오: `mfa validate`

첫 2020 시험에서 `mfa validate`는 다음 이유로 실패했다.

- MFA 3.4 `validate`에는 `align`의 `--no_tokenization` 옵션이 없다.
- 한국어 사전을 지정하면 별도 `python-mecab-ko` 설치를 요구했다.
- 본 정렬 경로는 이미 `--no_tokenization`을 사용하도록 설계되어 있다.

새 의존성을 설치하면 파일럿과 본 파이프라인의 전처리 경로가 달라진다. 따라서
다음과 같이 수정했다.

```text
층화 표본 구성 시 입력 전수 QC
→ 실행기에서 연도별 10발화·5실제화자 재검증
→ mfa align --no_tokenization --g2p_model_path korean_mfa
→ 4-tier 병합 및 전수 QC
```

실패 로그는 run 폴더의 `logs\2020.validate.log`에 보존했다. 데이터나 기존
정렬 레이어는 변경되지 않았다.

## 6. 2020 실제 시험 결과

실행 시각: 2026-07-24 21:54 KST

| 항목 | 결과 |
|---|---:|
| 입력 발화 | 10 |
| 실제 화자 | 5 |
| 원 세션 | 5 |
| MFA가 보고한 화자 | 5 |
| MFA 원 TextGrid | 10/10 |
| 최종 4-tier | 10/10 |
| 발화별 QC 통과 | 10/10 |
| 누락/추가 TextGrid | 0/0 |
| `spn` interval | 0 |
| MFA align 소요 | 34.249초 |
| 동일 RunId 재실행 | 세 단계 모두 skip, 4.3초 종료 |

표본 TextGrid의 tier 순서는 정확히 다음과 같다.

```text
words
phones
morphemes
utterance
```

`spn=0`은 G2P가 파일럿의 OOV 어절에 정렬용 발음을 공급했다는 운영 지표다.
현상의 실제 실현이 올바르게 판정됐다는 뜻은 아니다.

## 7. 다음 날 확인

1. `RESULTS.md`의 전체 판정이 `PASSED`인지 확인한다.
2. 연도별 행이 모두 실제 화자 5, 원 세션 5, 발화 10, QC 통과 10인지 본다.
3. `qc\{year}_utterance_qc.csv`에서 `failure_reason`, 길이 차이, `spn`을 본다.
4. 각 연도에서 적어도 몇 건은 WAV와 `textgrid_4tier`를 Praat에서 직접 열어
   어절 위치 찾기 용이성과 대략적 phones 경계를 청취 검수한다.
5. 이 수동 검수 전에는 전량 MFA로 넘어가지 않는다.

실패하면 화면의 마지막 오류와 `logs\{year}.align.log`,
`qc\{year}_summary.json`을 함께 확인한다.
