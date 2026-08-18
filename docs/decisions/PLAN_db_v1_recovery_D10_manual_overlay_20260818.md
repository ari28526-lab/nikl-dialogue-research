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

## 현재 정지점

`outputs/releases/nikl_dialogue_research_db_v1_recovery_d10_manual_overlay_gate_20260818`
에 16건의 제안 전사와 난이도 분류를 만들었다. 아직 WAV 복사, LAB/TextGrid 수정,
MFA, 6-tier/DB 변경은 모두 0건이다. 다음은 제안 전사와 D9 연구자 기록·source
identity를 자동 감사한 뒤, 격리 작업 사본을 만드는 단계다.
