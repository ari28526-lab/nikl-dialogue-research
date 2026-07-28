# 외부 코드 리뷰 요청 프롬프트 — 공통 발음사전·MFA

아래 프롬프트의 저장소·브랜치·commit을 그대로 사용해 주세요. 리뷰 결과는
Markdown 파일로 받아 이 프로젝트에 보존한다.

---

당신은 한국어 음성학·코퍼스언어학 연구용 대량 MFA 파이프라인의 독립
코드 리뷰어다. 코드를 직접 변경하지 말고 저장소를 읽어 증거 기반으로
검토하라.

저장소:
`https://github.com/ari28526-lab/nikl-dialogue-research`

브랜치:
`agent/harden-pre-bulk-pipelines`

검토 기준 commit:
`<PUSH_AFTER_REVIEW_CHECKPOINT_COMMIT>`

연구 흐름은 다음과 같다.

1. 형태소 분석 CSV에서 특정 형태소 또는 표기상 음운 환경을 검색한다.
2. 해당 WAV·TextGrid를 연결한다.
3. KOINA 운율 분석을 추가한다.
4. 연구자가 WAV와 TextGrid를 보고 실제 실현 여부를 판정한다.
5. G2P phone은 실제 실현의 자동 판정값이 아니라 MFA 정렬용 사전 phone이다.

최신 결정은 공식 Hugging Face
`MontrealCorpusTools/korean_mfa` commit
`0091ffa1f1ef7df380a4f799b3fb5bc80c3f65cd`의 acoustic v3.3.0,
Jamo G2P v3.2.0(`unicode_decomposition=true`), 같은 dictionary를
2020–2025 전체에 동일 적용하는 것이다. 구 2020·2021은 `spn` 누락이
확인되어 baseline으로만 archive하고 전 연도를 새 기준으로 다시 정렬한다.

우선 다음 파일을 반드시 읽어라.

- `docs/decisions/DECISION_latest_jamo_common_pron_mfa_20260728.md`
- `docs/decisions/MONITOR_common_pron_mfa_r1_20260728.md`
- `scripts/python/package_hf_korean_mfa_bundle.py`
- `scripts/python/build_common_pron_mfa_lexicon.py`
- `scripts/run_common_pron_mfa_r1.ps1`
- `scripts/show_common_pron_mfa_status.ps1`
- `scripts/archive_pre_jamo_outputs_to_external.ps1`
- `scripts/run_eojeol_realign.ps1`
- `scripts/run_pre_mfa_bulk_safe.ps1`
- 관련 `tests/`

특히 다음을 검토하라.

1. 최신 acoustic·dictionary·Jamo G2P를 한 묶음으로 동결하는 방식이
   방법론적으로 일관적인가?
2. 모델 version·upstream commit·SHA256·phone inventory·LF symbol
   검증이 충분한가? 파일 존재나 exit 0을 성공으로 오판할 경로가 남았는가?
3. 최신 Jamo가 모르는 NFKD 종성 `ᆳ`(U+11B3)을
   `ᆯ(U+11AF)+ᆺ(U+11BA)`으로 완전분해해 같은 rewriter에 넣는 방안이
   안전한가? 더 단순하고 재현 가능한 동일-Jamo 해결책이 있는가?
4. 866k 이상 OOV shard에서 누락·중복·`spn`·phone inventory 이탈·부분
   성공을 모두 차단하는가?
5. 구 r1의 2020·2021 mismatch=0 동등성 gate는 최신 모델 전환 뒤 더 이상
   채택 gate가 될 수 없다. 코드에 구 gate가 새 r2를 잘못 차단하거나 반대로
   구결과를 새결과로 승인할 위험이 있는가?
6. 2020–2025를 같은 기준으로 재실행했다는 논문 방법론 근거에 필요한
   manifest·모델 지문·입력계약·연도별 QC가 충분한가?
7. D: 메인/E: archive 경계, lock, 부분 산출 archive, 재개, 저장공간,
   삭제 allowlist가 안전한가?
8. 정확도를 해치지 않으면서 G2P·MFA·TextGrid export 시간을 줄일 수 있는
   명확한 병목 개선이 있는가?
9. CSV의 형태소·철자 로마자·사전 발음 보조열과 MFA phone을 독립적으로
   유지한다는 연구 설계가 코드에서 훼손될 위험이 있는가?

다음 형식으로만 답하라.

## 1. 최종 판정

`GO`, `CONDITIONAL GO`, `NO-GO` 중 하나와 5문장 이내 근거.

## 2. 발견사항

각 항목을 아래 필드로 작성하라.

- ID: `MFA-001` 형식
- Severity: `BLOCKER`, `HIGH`, `MEDIUM`, `LOW`
- Confidence: `HIGH`, `MEDIUM`, `LOW`
- 위치: 정확한 `파일:행`
- 증거: 코드가 실제로 무엇을 하는지
- 재현법: 가능한 최소 명령·입력
- 연구 영향: 정합성·일관성·효율성 중 무엇이 깨지는지
- 제안 수정: 최소 수정안
- 수정 후 검증: 통과해야 할 구체적 테스트·수치

같은 원인의 파생 증상은 한 항목으로 합쳐라. 스타일 취향은 쓰지 말고,
실패·데이터 손상·방법론 불일치·재현성·실질 병목만 보고하라.

## 3. `ᆳ` 처리 판정

현재 완전분해 방안의 채택/수정/기각 중 하나를 고르고, phone inventory를
바꾸지 않는 구체적 대안을 제시하라. `spn`을 최종 허용하는 제안은 금지한다.

## 4. 전 연도 재실행 계약 체크리스트

각 항목을 `PASS`, `FAIL`, `MISSING EVIDENCE`로 판정하고 필요한 증거를
한 줄로 적어라.

## 5. 실행 전 필수 수정 순서

BLOCKER/HIGH만 의존 순서대로 나열하라.

## 6. 성능 개선

결과를 바꾸지 않는 최적화와 결과를 바꿀 수 있는 최적화를 분리하라.
예상 이득의 근거가 없으면 “계측 필요”라고 써라.

리뷰에서 실행하지 못한 것은 추측으로 성공 판정하지 말고
`MISSING EVIDENCE`로 표시하라.

---

## 결과를 Codex에 돌려주는 방법

가장 좋은 형식은 위 응답 전체를 UTF-8 Markdown으로 저장한
`EXTERNAL_REVIEW_common_pron_mfa_<도구명>_20260728.md`다. 파일을 이
대화에 첨부하거나 전문을 붙여넣는다. Codex는 각 ID별로
`수용 / 부분 수용 / 기각 / 추가 재현 필요`를 판정하고, 근거·수정 commit·
회귀시험을 대응표로 남긴다.
