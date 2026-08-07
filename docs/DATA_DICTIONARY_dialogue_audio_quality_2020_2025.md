# 2020–2025 대화 음원 품질 감사 데이터 사전

최종 갱신: 2026-08-07 KST

이 자료는 정렬 결과를 대신하지 않고 `utt_id`·`session_id`로 기존 검색표,
동반 CSV/Parquet, MFA DB, TextGrid와 결합하는 보조 품질층이다. 모든 결정열의
초깃값은 `pending`이며 자동 제외를 뜻하지 않는다.

## `01_UTTERANCE_STRUCTURAL_FLAGS.csv.gz`

| 열 | 의미와 활용 |
|---|---|
| `year` | 코퍼스 연도 |
| `session_id` | 대화 세션 ID; 세션 단위 소음·겹침 검토에 사용 |
| `utt_id` | WAV·CSV·TextGrid·MFA DB 결합의 기본키 |
| `speaker_id` | 원 JSON 화자 ID |
| `start_sec`, `end_sec`, `duration_sec` | 원 JSON 시간 좌표 |
| `json_note` | 원 JSON note 원문 |
| `json_overlap_note` | note에 `발화겹침`이 명시됐는지 |
| `time_overlap` | 같은 세션의 다른 발화 시간구간과 실제 중첩되는지 |
| `max_time_overlap_sec` | 해당 발화가 다른 발화와 겹치는 최대 시간 |
| `boundary_abut_prev`, `boundary_abut_next` | 앞·뒤 발화 경계가 허용오차 안에서 맞닿는지; 잘림 판정이 아님 |
| `prev_gap_sec`, `next_gap_sec` | 앞·뒤 발화와의 시간 간격 |
| `reason_codes` | 원자료 구조 근거의 기계 판정 목록 |
| `evidence_class` | `confirmed_source_overlap` 또는 `audio_review_required` |
| `recommended_scope` | 검토 방향이며 승인 계약이 아님 |
| `researcher_decision` | 항상 `pending`으로 생성 |

## `02_SESSION_SUMMARY.csv.gz`

세션별 전체 발화 수, 원 시간 오류, JSON note 겹침, 시간 중첩, 경계 맞닿음,
간격 분포와 검토 우선순위를 담는다. 연도별 주석 관행 차이를 파악하고 음향 표본을
세션 층화할 때 사용한다.

## `03_AUDIO_SAMPLE/01_AUDIO_SAMPLE_METRICS.csv.gz`

| 열 묶음 | 의미와 활용 |
|---|---|
| `wav_*`, `sample_rate`, `channels`, `sample_width_bytes`, `duration_sec` | WAV 존재·헤더·기본 형식 감사 |
| `low_energy_floor_dbfs` | 20ms 프레임 에너지의 10백분위; noise proxy 구성요소 |
| `median_frame_dbfs`, `high_energy_dbfs`, `dynamic_range_db` | 발화 내부 에너지 분포 |
| `start_edge_dbfs`, `end_edge_dbfs` | 시작·끝 50ms 에너지 |
| `start_edge_relative_high_db`, `end_edge_relative_high_db` | 발화 고에너지 기준 edge 상대값; 잘림 검토 신호 |
| `digital_clip_fraction`, `dc_offset` | 디지털 포화·DC 편향 점검 |
| `read_status` | `readable` 또는 정확한 읽기 실패 원인 |
| `researcher_decision` | 항상 `pending`으로 생성 |

## `03_AUDIO_SAMPLE/02_SESSION_AUDIO_SUMMARY.csv.gz`

| 열 | 의미와 활용 |
|---|---|
| `wav_count`, `sampled_wav_count`, `readable_wav_count`, `invalid_wav_count` | 세션 WAV 및 표본 coverage |
| `full_session_profile` | 문제 세션을 표본이 아니라 전수 측정했는지 |
| `researcher_reported_noise` | 연구자가 직접 소음을 보고한 세션인지 |
| `median_low_energy_floor_dbfs` | 세션 noise proxy 원값 |
| `median_dynamic_range_db` | 세션 표본의 중앙 동적범위 |
| `median_*_edge_relative_high_db` | 세션 edge 경향 |
| `active_start_edge_pct`, `active_end_edge_pct` | edge 검토 신호가 나온 표본 비율 |
| `noise_proxy_percentile` | 연도 내부 세션 순위; SNR이나 소음 확정값이 아님 |
| `review_priority` | invalid/researcher-reported/top-5%/routine 검토 순서 |
| `researcher_decision` | 항상 `pending`으로 생성 |

## `SUMMARY_2020_2025.csv`

연도별 구조 감사와 음향 표본 감사의 핵심 수치를 한 행으로 요약한다.
`high_noise_proxy_review_sessions`는 설계상 상위 약 5%이므로 연도별 실제 소음률로
해석하지 않는다. `invalid_sampled_wavs`는 표본 탐지 수이고,
`full_scan_bad_wavs`는 해당 연도 전체 WAV의 `<=44B` inventory 수다.
`automatic_exclusion_performed=false`와
`researcher_decision=pending`이 고정되어야 한다.

## 연도별 `05_BAD_WAV_FULL_SCAN.csv`

전체 WAV를 읽기 전용으로 열거해 44바이트 이하인 파일을 기록한다.
`lab_present=true`인 ID만 현재 MFA 입력 위험 항목이므로 승인된
`alignment_and_analysis` 계약과 대조한다. `lab_present=false`는 디스크에 남은
불량 WAV의 존재 기록이며, 현재 search master와 LAB에도 없으면 새 제외 후보나
정렬 재실행 사유가 아니다. 원 WAV를 이동하거나 수정하지 않는다.

## `2022/04_FOCUS_PROFILE_438_PLUS_CONTROLS/01_FOCUS_EVIDENCE.csv`

2022 `mfa_alignment_missing` 438건과 aligned control 4건을 정확한 ID로 결합한다.

| 열 묶음 | 의미와 활용 |
|---|---|
| `candidate_review_order`, `pilot_review_order`, `sample_role` | 전수 후보 순서와 20개 표본 순서를 구분 |
| `input_reason_code` | 기존 post-MFA 상태 |
| `structural_*` | 원자료 겹침·경계 근거 |
| `*_edge_relative_high_db`, `active_*_edge_review` | exact WAV edge 측정과 검토 신호 |
| `session_noise_proxy_percentile`, `session_audio_review_priority` | 세션 수준 음향 검토 우선순위 |
| `review_signals` | 서로 중복 가능한 근거 묶음 |
| `scope_if_researcher_approves` | 승인 시 가능한 scope 후보; 승인 자체가 아님 |
| `researcher_decision`, `researcher_notes` | 연구자 판단 기록용 빈 열 |

## 해석 금지 사항

- `phones_mfa` 또는 이 품질표로 실제 음운 실현을 자동 판정하지 않는다.
- 경계가 맞닿는다는 이유만으로 잘렸다고 판정하지 않는다.
- noise proxy 순위만으로 심한 소음이라고 판정하지 않는다.
- 연도별 JSON 표지 방식이 다르므로 겹침 수 0을 현상 부재로 해석하지 않는다.
