# 연구 DB v1 recovery D6 사후 분기 Gate

기록일: 2026-08-15 KST

## 결론

D5 격리 진단 30건을 성공 11건과 계속 미정렬 19건으로 exact-ID 분리하고,
D5에서 의도적으로 실행하지 않은 0.1초 미만 feature-failure 25건을 원 음원
회수 장부로 다시 결속했다. 별도 감사가 세 분기의 ID·파일·해시·보존 DB 증거를
독립 검증해 다음 상태로 종료했다.

```text
passed_gate_closed_pending_researcher_review_and_separate_approval
```

r3 본체, 연구용 6-tier, DB v1은 변경하지 않았고 자동 병합도 0건이다.

## 성공 11건 검토 묶음

`outputs/reviews/db_v1_recovery_d6_20260815`에 번호가 같은 WAV·LAB·D5
2-tier TextGrid를 한 폴더로 모았다. `00_REVIEW_11.csv`에는 원 CSV 발화·형태소·
시간정보, LAB, WAV/TextGrid 길이, 원본 경로·SHA와 다음 연구자 입력란이 있다.

- `audio_text_match`
- `words_alignment`
- `phones_alignment`
- `boundary_quality`
- `decision`, `notes`

11개 모두 WAV와 TextGrid 길이가 일치하고 tier는 `words`, `phones`다. 이는 채택
전 진단 산출물이며 아직 6-tier로 확장하거나 본체에 넣지 않았다.

## 계속 미정렬 19건

보존 D5 DB를 읽기 전용으로 다시 질의했다. 19건 모두 `ignored=false`,
`num_frames>0`이지만 word interval과 phone interval이 각각 0개였다. 따라서
현재 확인 가능한 기술 분류는 다음 하나다.

```text
alignment_not_emitted_after_fresh_subset = 19
```

이는 음성·전사가 언어학적으로 틀렸다는 판정이 아니다. 다음 행동은 WAV/LAB
identity를 수동 확인한 뒤 exact-ID 재분절 또는 새 통제 진단 Gate를 설계하는
것이다. 같은 입력을 근거 없이 반복 실행하거나 자동 병합하지 않는다.

## 동일 입력 재실행 금지 25건

D5의 정확한 WAV 길이는 모두 0.1초 미만이다. 기존
`D:\10_LAYERS\05_audio_index\source_pcm_check.csv`와 원 CSV 시간정보를 연결한
결과, 24건은 원 PCM도 짧은 것으로 기록됐고 1건은 PCM 자체가 없다고 기록됐다.
현재 원 배포 PCM binary가 확인되지 않아 다음 증거 경로를 보존했다.

```text
source_pcm_check + source_csv(start,end,dur) + canonical_session_path
```

25건은 회수·재구성한 원 길이 음원을 마련하기 전 같은 입력으로 MFA하지 않는다.
이는 연구 제외가 아니라 기술적 보존 상태다.

## 정본 자산

```text
outputs/releases/nikl_dialogue_research_db_v1_recovery_d6_gate_20260815
outputs/reviews/db_v1_recovery_d6_20260815
outputs/reports/RESULT_db_v1_recovery_D6_20260815.json
```

권위 장부는 다음 세 CSV다.

- `D6_SUCCESS_11_REVIEW.csv`
- `D6_MISSING_19_TECHNICAL_LEDGER.csv`
- `D6_NO_RUN_25_AUDIO_RECOVERY.csv`

`INDEPENDENT_AUDIT.json`은 11+19=30, no-run 25, 파일 해시, TextGrid 층위·길이,
DB interval 증거, no-run 비실행 상태를 재검증한다.

## XLSX 로더 상태

현재 Codex 작업에는 공식 `load_workspace_dependencies`가 등록되지 않았고
Spreadsheets 앱 상태도 `not_installed`로 보고됐다. 로컬 plugin cache는 존재하므로
데이터·코드 손상은 아니다. 프로젝트 규칙에 따라 임의 Node 경로나 `openpyxl`로
우회하지 않았다. CSV가 권위 장부이며, 공식 로더가 복구되면 동일 CSV로 검토용
XLSX를 만들고 전 sheet를 시각 검증한다.

## 다음 Gate

연구자는 먼저 성공 11건만 검토한다. 채택, 6-tier 생성, 본체/DB v1 병합은 그
검토와 별도 명시 승인 뒤에 exact-ID 단위로 수행한다. 19건과 25건은 각각 새
기술 회수 shard로 남기며 전 연도 또는 D5 전체를 다시 실행하지 않는다.
