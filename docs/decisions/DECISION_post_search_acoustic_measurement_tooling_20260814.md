# 검색 후 선택 자료의 음향 측정·검토 도구 계층 결정

작성일: 2026-08-14
상태: 설계 채택, 구현은 2025 생산 Gate 뒤 별도 단계

## 목적

현재 생산물의 핵심은 2020–2025 공통 계약으로 만든 6-tier TextGrid와 동반표다.
음운·형태 환경 검색으로 후보를 고른 뒤 연구자가 실제 실현을 듣고 보고 판정하며,
선택 자료에는 KOINA 또는 다른 음향 분석을 적용한다. 이때 kPhonetica와 다른
도구는 MFA phone을 대체하는 정답 생성기가 아니라, 수동 검토와 재현 가능한
측정을 돕는 후처리 도구로만 사용한다.

## kPhonetica 판단

`C:\Users\ari30\Dropbox\kPhonetica_2.08`의 GUI·음소분절 매뉴얼·예제는 다음
기능을 설계하는 참고 자료로 유용하다.

- 파형·스펙트로그램·F0·에너지·포먼트의 한 화면 검토
- 문장·어절·음절·음소·운율 label의 계층적 수동 주석
- 기존 `.lbl`의 음소 label을 TextGrid에 추가하는 변환

그러나 자동 label 기능은 오래된 Windows GUI와 HTK 계열 자원에 결합되어 있고
공식적인 배치 CLI/API가 확인되지 않았다. label inventory도 현재 MFA phone과
동일하지 않다. 따라서 GUI 자동화를 생산 의존성으로 삼거나 `phones_mfa`를
덮어쓰지 않는다.

## 채택할 후처리 구조

### 1. 선택 발화 manifest

검색 결과에서 다음 최소 키를 동결한다.

```text
selection_id, year, utt_id, speaker_id, wav_path, textgrid_path,
target_tier, target_interval_index, target_label,
source_xmin, source_xmax, stitched_file_id, stitched_offset_seconds
```

`source_xmin/xmax`와 이어붙이기 offset을 함께 보존해야 KOINA용 결합 음원에서
얻은 측정을 원 발화·CSV·TextGrid로 되돌릴 수 있다.

### 2. 음향 측정 동반표

F0, voicing, intensity, duration, formant 등은 TextGrid tier를 계속 늘리지 않고
long-form CSV 또는 Parquet에 기록한다. 각 행은 interval key와 다음 provenance를
가진다.

```text
measure_name, value, unit, time_seconds,
method, tool_name, tool_version, parameters_json,
validity_flag, qc_reason, reviewer, reviewed_at
```

경계·label과 측정값을 분리하면 동일 TextGrid에 여러 알고리즘 결과를 안전하게
비교할 수 있고, 후속 재측정도 정렬을 다시 하지 않고 해당 측정 shard만 바꿀 수
있다.

### 3. 선택적 kPhonetica `.lbl` importer

과거 또는 수동 작업에서 생성된 `.lbl`이 있을 때만 raw label을 보존하여 companion
table로 가져온다. 필요하면 `phones_kphonetica_candidate`라는 별도 후보 tier를
만들 수 있지만, 명시적 mapping version과 unmapped label을 기록하고
`phones_mfa`·`phoneme_r_auto`를 변경하지 않는다.

## 도구 우선순위

1. Praat/Parselmouth: 선택 발화의 F0·강도·포먼트 등 재현 가능한 Python batch
2. praatIO: 현재 TextGrid의 안전한 읽기·쓰기·tier/interval 조작
3. FastTrackPy: 모음·포먼트 연구의 표적 subset에 한해 후보 추적과 측정
4. EMU-SDMS: 대규모 계층 주석 질의와 검토 UI가 실제 병목이 될 때 선택 도입
5. openSMILE: 정서·음질·발화양식 등 넓은 feature set이 연구 질문에 필요할 때만

도구를 먼저 전수 적용하지 않는다. 연구 질문과 표적 단위가 정해진 후 선택
manifest를 입력으로 작은 검증 표본을 통과한 측정만 shard 단위로 확장한다.

## 자료 구축에서 추가로 보존할 항목

- 원본과 파생 산출물의 SHA·도구 버전·매개변수
- 자동값, 연구자 판정, 제외 사유의 분리
- 측정 실패와 값 없음의 구분
- 겹침말·주변소음·잘림·낮은 신뢰도 flag
- 음성 구간의 원 좌표와 이어붙인 좌표
- 후보 생성 시점의 검색 조건과 query version
- 재측정·재판정 이력과 이전 값 보존

이 구조는 kPhonetica 설치 여부와 무관하게 재현되며, 필요한 기능만 Python으로
구현할 수 있다. 첫 구현 후보는 `build_selected_acoustic_measurements.py`와
`import_kphonetica_lbl.py`지만 2025 r3 생산을 방해하지 않도록 별도 작업으로 둔다.
