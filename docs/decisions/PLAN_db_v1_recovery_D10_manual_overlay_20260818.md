# 연구 DB v1 recovery D10 수동 overlay 계획

기록일: 2026-08-18 KST

## 목적

D9 연구자 검토에서 음성 보존 가치가 확인됐지만 현재 자동 정렬을 그대로 쓸 수
없는 16건만 수정 전사와 수동 TextGrid overlay로 복구한다. 전체연도 MFA, D9
재실행, 원 WAV·LAB·TextGrid 덮어쓰기는 하지 않는다.

## 작업 분류

- `localized_manual_edit` 9건: 중복·과잉 앞뒤 문구를 제거하고 기존의 대체로 맞는
  경계를 보존하면서 국소 수정한다.
- `full_manual_realignment` 6건: 실제 음성보다 LAB가 크게 길거나 어휘가 달라
  word tier를 실제 문장으로 처음부터 다시 작성한다.
- `single_word_manual_recovery` 1건: 깨끗한 단일어 `그`만 수동 경계로 보존한다.

비언어음·불완전 자음·TV/배경음악은 word label에 억지로 넣지 않고 overlay
메타데이터에 별도 기록한다. `신도시의`의 [에] 가능성이나 빠른 `그러니까`는 철자
전사를 바꾸는 근거로 쓰지 않고 추후 실제 발음 연구에서 판단한다.

## provenance와 채택

수동본은 원본과 D9 결과를 참조하는 exact-ID 파생 레이어다. 수정자는 원 전사를
덮어쓰지 않고 `proposed_transcription`, 수정 이유, 경계 변경, 수정 시각을 남긴다.
수동 완료 뒤 독립 검사가 WAV 길이, tier 범위, 빈틈/겹침, 단어열과 provenance를
확인한다.

기술 제외 2건은 작업 묶음에 넣지 않으며 증거만 보존한다. D9 정렬 승인 1건도
16건과 섞어 자동 채택하지 않고, 같은 검사가 끝난 뒤 별도 6-tier enrichment·DB
overlay Gate로 연결한다.

## 2026-08-18 실행 결과와 현재 정지점

제안 전사·D9 연구자 기록·source identity의 자동 감사를 통과한 뒤 16건의 격리
작업 사본을 다음 위치에 만들었다.

```text
D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_MANUAL_OVERLAY_0001
```

각 세트는 WAV, 원 LAB, 제안 LAB, D9 참고 TextGrid, 수동 작업 TextGrid로
구성된다. 국소 수정 9건만 D9 word 경계를 작업 초안으로 사용하고 전체 재정렬
6건과 단일어 1건의 작업 tier는 빈 상태로 시작한다. 생성·독립 감사 결과는
`RESULT_db_v1_recovery_D10_materialization_20260818.md`에 기록했다.

현재 정지점은 `materialized_pending_researcher_manual_overlay`다. 원본·r3·6-tier·
DB v1 변경과 MFA 실행은 여전히 0건이며, 다음은 연구자의 `words_manual_working`
수정과 별도 adoption Gate다.
