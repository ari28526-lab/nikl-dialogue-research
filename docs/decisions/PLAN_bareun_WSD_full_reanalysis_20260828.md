# 바른 WSD 포함 형태소 전면 재분석 계획

작성일: 2026-08-28

상태: **환경 Gate E0 통과, 파일럿·전수 실행 미승인**

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

## 4. 고정 API 계약

- 클라이언트: `bareunpy==2.1.0`
- 공식 commit: `8107424892d76ac855918c20a0fb82faa877e530`
- endpoint: `api.bareun.ai:443`
- method: `AnalyzeSyntaxList` (`taglist`)
- `with_sense=true`
- `auto_split=false`, `auto_spacing=true`, `auto_jointing=true`
- 초기 batch: 40발화

`taglist`를 쓰는 이유는 입력 발화 단위를 유지하기 위해서다. 파일럿에서 응답
개수와 입력 개수가 1:1인지 매 batch 확인하고, 불일치는 출력하지 않고 실패
checkpoint로 남긴다.

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
| P1 | 소규모 파일럿 | 응답 1:1, schema, 재개, 출력 용량, 비용 회계 | 미승인 |
| B1 | 전수 실행 | P1 통과, 80 GiB 이상, 보호경로 검사, 명시 승인 | 닫힘 |
| A1 | 전수 감사 | 입력 zero-drop, batch 회계, SHA, 실패 재처리 0 | 대기 |
| W1 | WSD 검토 | 다의어 층화 표본과 무의미번호 사례 검토 | 대기 |

E0를 마쳐도 B1은 자동으로 열리지 않는다. 사용자가 환경·문서와 P1 결과를
확인한 뒤 전수 실행을 별도로 승인해야 한다.

## 8. 대량 실행 권한과 운영 방식

P1을 통과한 뒤에도 전수 작업은 Codex가 자동·백그라운드로 시작하지 않는다.
Windows PowerShell 5.1 호환 runner, `-PreflightOnly`, 상태판, 중단·재개 절차와
정확한 명령을 먼저 준비하고 테스트한다. 그 뒤 사용자가 명령을 직접 실행해야만
대량 API 호출이 시작된다. runner는 외장하드 출력 root와 보호경로, 단일 lock,
공간, client commit, 입력 회계를 다시 검사해야 한다.

## 9. 저장공간 전략

2026-08-28 실측 D: 여유는 약 57.7 GiB다. 환경 gate 최저 50 GiB는 넘지만
전수 bulk gate 80 GiB에는 미달한다.

- 기존 52.66 GiB `morph_search.v3`를 복제하지 않음
- 원 TextGrid 428만 개를 복제하지 않음
- 새 WSD CSV/sidecar 본체도 외장하드에만 저장
- 로컬 SSD와 GitHub에는 대용량 결과를 저장하지 않음
- 정규화한 compact WSD sidecar를 우선 생성
- P1에서 발화당 출력 byte를 측정해 전수 예상치와 checkpoint 여유를 계산
- 저장공간이 확보되기 전 B1은 fail-closed

## 10. 실행 전 확인 항목

- 공식 문서의 WSD 옵션과 현재 계정 한도 재확인
- `preflight_bareun_wsd_environment.py --full-input-scan --live-api` 통과
- P1 결과 문서와 schema 승인
- 외장하드 CSV·TextGrid·WAV 보호경로 snapshot 또는 manifest 확인
- 출력 root 미존재, 덮어쓰기 false 확인
- 전수 runner의 재개·backoff·rate-limit·원자 승격 테스트 통과

## 11. 현재 정지점과 다음 결정

현재는 환경과 계획 문서를 GitHub에 올리는 지점에서 멈춘다. 전수 API 호출은
수행하지 않는다. 다음 사용자 결정은 **P1 소규모 WSD 파일럿 실행 승인** 한
가지다. P1은 전수 실행이 아니며 출력 크기와 실제 응답 계약을 동결하기 위한
최소 단위다.

환경 Gate의 실제 검증 결과는
`RESULT_bareun_WSD_environment_gate_20260828.md`에 기록한다.
