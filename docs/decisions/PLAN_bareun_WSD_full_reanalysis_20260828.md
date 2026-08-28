# 바른 WSD 포함 형태소 전면 재분석 계획

작성일: 2026-08-28

상태: **P1 통과, CSV-only 전수 실행 사용자 PowerShell 대기**

대상: 2020–2025 대화 말뭉치 전체

## 1. 결정 요약

17,156개 CSV, 5,103,356발화 전체를 바른 형태소분석기의
`with_sense=true`로 새로 분석한다. 기존 결과를 교체하지 않고 새 staging
레이어에 형태소·동형이의어 의미번호·확률·사전 식별자·문자 offset을 함께
보존한다. 새 대용량 결과의 최종 저장소도 외장하드다. 의미번호는 기계
후보이며, 이후 WSD 표본 점검을 거쳐야 한다.

MFA 정렬 시간과 원 TextGrid는 바꾸지 않는다. 기본 연동은 `(year, utt_id)`
sidecar이고, 어절 좌표가 정확히 일치할 때만 word interval까지 연결한다.

## 2. 최상위 불변 보호 계약

외장하드에 존재하는 완결 CSV, TextGrid, WAV는 이번 작업의 정본 입력이다.

- 원 CSV·기존 Bareun CSV: 읽기 전용
- 완결 MFA DB·6-tier TextGrid: 읽기 전용
- 원 WAV·MFA용 WAV: 읽기 전용
- 기존 `01_bareun_raw`, `02_sense_annotated`, `03_freq_dictionaries`: 보존

금지 작업은 삭제, 이동, 이름 변경, 제자리 수정, 덮어쓰기, TextGrid tier의
직접 추가·교체, WAV 재인코딩, MFA 재정렬이다. 새 코드가 보호 경로를 출력
대상으로 받으면 fail-closed해야 한다.

## 3. 실측 범위와 비용 단위

| 항목 | 실측값 |
|---|---:|
| 입력 CSV | 17,156개 |
| 입력 발화 | 5,103,356개 |
| 입력 공백 어절 | 27,646,899개 |
| 형태소 API 과금 환산 | 약 2,764,690 어절 단위 |
| 완결 6-tier TextGrid | 4,286,046개 |

Business 구독 한도·추가 과금은 실행 직전 바른 계정의 현재 청구 화면과 다시
대조한다. 위 수치는 재현 가능한 입력 회계이며 실제 청구액 보장은 아니다.

## 4. 엔진·클라이언트·API 계약

- 분석 엔진: 클라우드 `api.bareun.ai`의 바른 서버 v3.1.0 이상
- 클라이언트: `bareunpy==2.1.0` — 서버 엔진 버전과 구분
- 공식 commit: `8107424892d76ac855918c20a0fb82faa877e530`
- endpoint: `api.bareun.ai:443`
- method: `AnalyzeSyntax` (`tags`), 실패 시 같은 순서의 `tag` 단건 폴백
- `with_sense=true`
- `auto_split=false`, `auto_spacing=true`, `auto_jointing=true`
- production batch: 40발화, worker: 1

새 서버가 형태소 분절·품사·확률을 전부 다시 계산하고 같은 응답에 WSD를
붙인다. 과거 CSV에서는 `utt_id`, `speaker_id`, `form`만 읽으며 `tagged`와
`n_morphs`는 새 분석 입력으로 사용하지 않는다. 과거 전수에서 검증된 `tags`
batch·`tag` 단건 폴백·파일 checkpoint 운영만 재사용한다. 배치 응답 수는
매번 입력과 1:1인지 확인하고, 합친 요청의 전역 offset은 각 sentence 시작점을
빼서 발화 내부 UTF-32 좌표로 정규화한다.

## 5. 새 산출물 구조

모든 새 대용량 파일은 외장하드의 run ID가 포함된 별도 root 아래에 둔다.
`.building`에서 작성하고 전수 감사 뒤 `final`로 승격한다. GitHub에는 아래
자료의 본체가 아니라 schema·코드·계획·작은 manifest만 둔다.

1. `utterance_manifest`: 연도·파일·`utt_id`·입력 SHA·처리 상태·시도 횟수
2. `morph_wsd`: 발화/어절/형태소 순서, 표면형, 품사, UTF-32 offset,
   `sense_no`, `urimal_target_id`, WSD probability
3. `sense_dictionary`: 반복되는 의미 설명을 식별자 조합으로 중복 제거
4. `legacy_diff`: 구 tagged 결과와 형태소·품사·분절 차이 요약
5. `run_manifest`: 코드·설정·클라이언트 commit·입출력 SHA·회계

원문 전체와 같은 대용량 반복 필드는 최소화하고, 재현과 감사에 필요한 정보는
잃지 않는다. 출력 형식과 예상 용량은 P1 파일럿 측정 뒤 동결한다.

## 6. MFA·TextGrid 연동

기본 연결키는 `(year, utt_id)`다.

- Bareun 발화 결과는 `morph_analysis_utt`와 같은 발화 범위의 sidecar로 연결
- TextGrid의 `words` 수와 Bareun 어절 수·표면형이 정확히 일치하는 경우에만
  위치 기반 interval link 생성
- 비 1:1, 교정 철자, 공백 변경, 빈 interval은 발화 수준 연결만 유지
- 불일치를 순서만으로 추측해서 맞추지 않음
- 원 6-tier TextGrid와 그 SHA는 변경하지 않음

필요하면 이후 별도 폴더에 파생 7-tier TextGrid를 요청 시 물질화한다. 새 tier는
`morph_sense_utt` 같은 짧은 참조 라벨만 담고, 긴 의미 설명은 sidecar에 둔다.
파생본도 원본과 hardlink를 공유한 채 수정하지 않으며 완전한 새 파일로 쓴다.
현재 SSD 여유 때문에 428만 개 파생본의 일괄 복제는 하지 않는다.

## 7. 단계별 Gate

| Gate | 범위 | 통과 조건 | 현재 |
|---|---|---|---|
| E0 | 환경 | 고정 client, 키 비노출, 입력·저장공간 사전점검 | 통과 |
| P1 | 소규모 파일럿 | 응답 1:1, schema, 출력 용량, 원 CSV SHA | 통과 |
| B1-CSV | 압축 CSV 전수 | P1 통과, 15 GiB 이상, PS5.1 runner, 사용자 직접 실행 | 준비 완료·미시작 |
| B1-ALL | TextGrid 등 추가 파생 | 80 GiB 이상, 별도 설계·승인 | 닫힘 |
| A1 | 전수 감사 | 입력 zero-drop, batch 회계, SHA, 실패 재처리 0 | 대기 |
| W1 | WSD 검토 | 다의어 층화 표본과 무의미번호 사례 검토 | 대기 |

P1과 B1-CSV preflight는 통과했지만 API 전수 호출은 자동 시작하지 않는다.
사용자가 검증된 PowerShell 명령을 직접 실행해야 한다.

## 8. 대량 실행 권한과 운영 방식

Windows PowerShell 5.1 runner, `-PreflightOnly`, 상태판, 중단·재개 절차와
정확한 명령을 준비하고 테스트했다. 사용자가 명령을 직접 실행해야만 대량 API
호출이 시작된다. runner는 외장하드 출력 root와 보호경로, 단일 lock, 공간,
client commit, 입력 회계를 다시 검사한다.

## 9. 저장공간 전략

2026-08-28 실측 D: 여유는 약 57.7 GiB다. P1의 단순 전수 환산은 일반 CSV
약 9.38 GiB, gzip CSV 약 2.00 GiB다. 따라서 CSV-only gate는 안전 여유를
포함해 15 GiB로 두고 통과시켰다. TextGrid 등 추가 대량 파생의 80 GiB gate는
계속 닫혀 있다.

- 기존 52.66 GiB `morph_search.v3`를 복제하지 않음
- 원 TextGrid 428만 개를 복제하지 않음
- 새 WSD CSV/sidecar 본체도 외장하드에만 저장
- 로컬 SSD와 GitHub에는 대용량 결과를 저장하지 않음
- 정규화한 compact WSD sidecar를 우선 생성
- 전수 출력은 `utterances.csv.gz`, `morphemes.csv.gz`,
  `sense_dictionary.csv.gz`의 파일별 묶음
- 파일별 receipt를 마지막에 원자 승격하고 완료 SHA가 맞는 파일만 재사용
- 15 GiB 미만이면 B1-CSV도 fail-closed

## 10. 실행 전 확인 항목

- 공식 문서의 WSD 옵션과 현재 계정 한도 재확인
- P1 240/240과 독립 감사 통과
- batch 40 단일 worker 40/40·약 7.27발화/초 확인
- 4-worker 동시 batch는 `Service Unavailable`이므로 production에서 금지
- 외장하드 CSV·TextGrid·WAV 보호경로 snapshot 또는 manifest 확인
- 출력 root 미존재, 덮어쓰기 false 확인
- 전수 runner의 재개·backoff·rate-limit·원자 승격 테스트 통과

## 11. 현재 정지점과 다음 결정

현재 전수 API 호출은 시작하지 않았다. 다음 행동은 사용자가
`run_bareun_wsd_csv_full.ps1 -Execute` 명령을 직접 실행하는 것이다. 단일 worker
실측 단순 환산은 약 8.1일이며, 중단 시 같은 명령에 `-Resume`을 붙인다.

환경 Gate의 실제 검증 결과는
`RESULT_bareun_WSD_environment_gate_20260828.md`에 기록한다.
P1과 전수 준비 결과는 `RESULT_bareun_WSD_csv_pilot_P1_20260828.md`에 기록한다.
