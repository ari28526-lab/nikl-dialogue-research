# 연도별 10발화·5화자 MFA 파일럿 실행서

작성일: 2026-07-24
대상: NIKL 일상대화 2020–2025
현재 실행 ID: `pilot_year10_speaker5_v2_20260724`

> `pilot_year10_speaker5_20260724`(v1)는 2023에서 CSV–WAV 발화 대응 오류를
> 발견해 중단·보존했다. 재실행하지 않는다.

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

v2 선정은 `speaker5_year10_v2_duration_guard` seed와 SHA256 정렬을 사용한다. 파일시스템 열거
순서에 의존하지 않으므로 같은 입력과 seed에서는 같은 발화가 선택된다. 선택
가능 조건은 다음과 같다.

- `form`에서 비어 있지 않은 어절 lab을 만들 수 있음
- WAV가 존재하고 PCM WAV 헤더·길이가 유효함
- 기존 형태소 TextGrid가 존재함
- 바른 CSV와 search master에서 같은 `utt_id`를 찾을 수 있음
- 선택 화자의 `_speakers.csv` 메타데이터가 존재함
- 세션 전체에서 같은 `utt_id`의 CSV 시간과 WAV 길이가 일관되게 대응함
- 세션별 일관된 앞뒤 padding을 제거한 발화별 길이 잔차가 0.025초 이하임

이는 모집단 대표성을 추정하는 통계 표본이 아니라 파일 연결과 정렬 인프라를
시험하는 층화 smoke test다.

## 3. 산출 폴더

```text
D:\mfa_eojeol\pilots\year10_speaker5\
└─ pilot_year10_speaker5_v2_20260724\
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
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\ari30\research\2026_summer_research\scripts\run_stratified_mfa_pilot.ps1" -RunId pilot_year10_speaker5_v2_20260724 -Seed speaker5_year10_v2_duration_guard
```

v2 2020은 2026-07-24 실제 시험에서 이미 통과했다. 같은 명령을 실행하면 완료
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
| MFA align 소요 | 33.080초 |

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

## 8. v1 2023 부분 성공과 v2 duration 대응 가드

v1은 2023에서 MFA가 alignment 10개를 계산한 뒤 word/phone alignment를
9개만 수집·export하고도 exit 0으로 종료했다. 러너의 산출물 수량 가드가
`TextGrid=9/10`을 검출해 완료 마커와 후속 병합을 차단했다.

누락 발화:

```text
SDRW2300000130.1.1.235
```

이 발화는 CSV상 12어절·3.622초인데 같은 ID WAV가 2.333초였다. 같은 화자의
`SDRW2300000130.1.1.273`은 CSV상 1어절·0.613초인데 WAV가 4.610초였다.
세션 전체 감사 결과는 다음과 같다.

- CSV: 428행
- WAV: 436개
- 같은 ID 길이 차이 0.02초 초과: 363/428
- WAV에만 있는 ID: `.429`–`.436` 8개

여러 WAV 길이가 바로 앞이나 몇 발화 전 CSV 길이와 일치했다. 과거 음성 분절
또는 말뭉치 판본 간 발화 번호 대응 오류 가능성이 높으며, beam을 넓혀 해결할
정렬 난도가 아니다.

v2는 표본 후보 세션마다 전체 발화의 `WAV 길이 - CSV dur` 중앙값을 일관된
padding으로 추정한다. 2024–2025에는 약 `+0.4초`가 일관되므로 정상 padding으로
허용한다. 다음 조건을 모두 만족해야 세션과 발화를 선택한다.

- 세션 padding: -0.025–0.5초
- padding 제거 후 길이 잔차 0.025초 이내인 발화: 세션의 98% 이상
- 실제 선택 발화의 길이 잔차: 0.025초 이하

v2 60발화의 선택 결과:

- 매년 10발화·5실제화자·5세션
- 세션 duration 대응률 최저 99.5%
- 선택 발화 잔차 실패 0
- 2020 실제 G2P MFA/4-tier/QC 10/10, `spn=0`

v1 폴더와 2023 실패 로그·9개 TextGrid는 원인 증거로 그대로 보존한다.

v2 실행에서는 duration 대응이 정상인
`SDRW2300001955.1.1.164`도 기본 beam 10/40에서 정렬되지 않아 9/10으로
중단됐다. 이 발화는 CSV와 WAV 모두 3.025초이고 세션 duration 대응률도
99.5868%여서 자산 불일치가 아닌 난정렬로 분리했다. 같은 10개를 별도 폴더에서
beam 100/retry_beam 400으로 재시도한 결과 10/10을 회수했다.

러너는 이제 다음 순서를 자동 수행한다.

1. 기본 beam 10/40 실행
2. TextGrid 수가 입력보다 적으면 exit 0이어도 부분 성공으로 판정
3. 기본 원출력·temp·로그를 run 내부 `archive_failed`에 보존
4. 자산 대응 검증을 이미 통과한 같은 표본만 beam 100/400으로 1회 재시도
5. 그래도 수량이 모자라면 모든 증거를 보존하고 실패 종료

확대 beam은 CSV–WAV가 잘못 연결된 자료를 억지로 맞추는 용도로 사용하지 않는다.
duration 대응 가드가 먼저 통과한 난정렬에만 제한한다.

## 9. v2 최종 실행 결과

`pilot_year10_speaker5_v2_20260724`는 2026-07-24 22:42:34 KST에
`PASSED`로 완료됐다.

| 연도 | 실제 화자 | 원 세션 | 입력 | QC 통과 | spn | align mode |
|---:|---:|---:|---:|---:|---:|---|
| 2020 | 5 | 5 | 10 | 10 | 0 | 기존 완료 marker(필드 추가 전) |
| 2021 | 5 | 5 | 10 | 10 | 0 | 기존 완료 marker(필드 추가 전) |
| 2022 | 5 | 5 | 10 | 10 | 0 | 기존 완료 marker(필드 추가 전) |
| 2023 | 5 | 5 | 10 | 10 | 0 | `retry_beam_100_400` |
| 2024 | 5 | 5 | 10 | 10 | 0 | `default_beam_10_40` |
| 2025 | 5 | 5 | 10 | 10 | 0 | `default_beam_10_40` |

전체 60/60 발화가 4-tier와 발화별 QC를 통과했고 `spn` interval은 0이다.
2020–2022는 `align_mode` 필드를 도입하기 전에 완료되었으므로 기존 marker에
해당 필드가 없지만, 원 TextGrid 수량과 최종 QC는 재검증했다. 재현 기록의
사후 변조를 피하기 위해 marker를 다시 쓰지 않았다.

최종 판정은 run 루트의 `RESULTS.md`와 `pilot_summary.json`, 상세 판정은
`qc\{year}_utterance_qc.csv`에서 확인한다. 자동 재시도 이전의 2023
부분 출력·temp·로그는 `archive_failed`에 남아 있다.
