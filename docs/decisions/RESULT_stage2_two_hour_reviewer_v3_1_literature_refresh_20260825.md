# 7현상 2시간 파일럿 v3.1 문헌 갱신 및 시작 가능 판정

날짜: 2026-08-25 KST

## 결론

7현상×12사례 파일럿은 `researcher_review_package_v3_1_20260825`와
`actual_research_guides_v2_20260825`를 사용해 시작할 수 있다. 연구자 청취와
실현 판정은 아직 0건이며, 이 결과는 준비 완료이지 현상 실현 확인 완료가 아니다.

구 `researcher_review_package_v2`의 문헌 패널을 그대로 사용하지 않았다. 최신
정본 claim ledger 173행을 입력으로 범위 카드의 문헌 참조를 append-only 방식으로
갱신하고, 표본·대화·메타데이터·WAV·TextGrid는 검증된 v2와 동일하게 유지한
C-only 재패키징을 수행했다.

## 검증된 산출물

- reviewer: `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/researcher_review_package_v3_1_20260825`
- reviewer 감사: 같은 상위 폴더의 `reviewer_package_audit_v3_1_20260825/AUDIT_STAGE2_TWO_HOUR_REVIEWER.json`, `passed=true`
- 실제 연구 안내서: 같은 상위 폴더의 `actual_research_guides_v2_20260825`
- 안내서 감사: 같은 상위 폴더의 `actual_research_guides_audit_v2_20260825/AUDIT_STAGE2_ACTUAL_RESEARCH_GUIDES.json`, `passed=true`
- 새 대화 인계본: `outputs/SEVEN_PHENOMENA_PILOT_REVIEW_HANDOFF_20260825/START_HERE.md`

검증 수치는 84사례, 현상별 12, 연도별 2, 고유 발화 82, exact WAV 84,
source TextGrid 84, 분리된 `praat_work` TextGrid 84이다. 화면에 결속된 문헌
claim은 구 v2의 85행에서 103행으로 증가했다. 감사기는 현재 정본 ledger와
화면의 claim 필드 일치, 범위 카드 참조 일치, v2 대비 비문헌 자산 불변을 모두
검사했다.

## 새 자동화

- `scripts/python/refresh_stage2_scope_cards_from_appended_claims.py`: 기존 동결
  claim 156행이 현재 ledger의 정확한 prefix인지 확인한 뒤, 뒤에 추가된 claim만
  현상별 범위 카드 참조에 보탠다. 기존 의미·모집단 계약은 바꾸지 않는다.
- `scripts/python/build_stage2_two_hour_seven_phenomena_reviewer.py`의
  `--refresh-literature-from-claims`: 검증된 reviewer 자산을 재사용하고 문헌 패널만
  최신 claim ledger로 다시 만든다.
- `scripts/python/audit_stage2_two_hour_seven_phenomena_reviewer.py`의 최신 claim
  검증: 문헌 변경은 명시적으로 허용하되 그 밖의 샘플 자산 변화는 실패시킨다.
- `scripts/python/audit_literature_tree_coverage.py`: 로컬 `00_참고문헌` 전체 파일을
  source inventory·instance ledger와 SHA 기준으로 대조한다.

## 문헌 완전성 한계

로컬 전수 감사에서 파일 478개 중 443개가 정본 physical instance로 등록되어
있었다. 미등록 35개는 등록본과 동일 SHA 25, OCR 변형 4, NotebookLM 파생 음성
4, 보충 데이터 1, 보충 소프트웨어 1로 분류되었고, 로컬 미등록 학술 저작 후보는
0이었다.

그러나 Dropbox 전역 검색에서는 로컬 정본에 없는 것으로 보이는 문헌 후보 8건을
찾았다. 이는 identity·중복·관련성 검토 전 후보이며 source ID를 부여하거나 정본에
편입하지 않았다. 세부 목록은 인계본의
`DROPBOX_LITERATURE_GAP_CANDIDATES_20260825.jsonl`에 있다. 따라서 파일럿 시작은
막지 않지만 PT·NAL·LLN·VH 관련 문헌 결론은 이 후보 검토 전까지 잠정으로 둔다.

## 사용 규칙

- 사용: v3.1 reviewer와 v2 실제 연구 안내서.
- 사용 금지: 문헌 156행 시점의 v2 reviewer.
- 보존 증거: `researcher_review_package_v3_20260825`는 최초 갱신 영수증 상단에
  구 입력 수치가 남았으므로 연구에 사용하지 않는다.
- 자동 실현 판정 금지. 탐색 JSONL과 정식 realization ledger를 분리한다.
- 첫 세션은 NI 한 현상, 12사례, 120분으로 시작하고 먼저 페이지·오디오 1건을
  짧게 확인한다.

## Dropbox 전달

검토·실행본은 Dropbox `00_연구_파일럿_임시/20260825_7현상_파일럿_사전검토`에
배치했다. 시작 파일은 `START_HERE.md`, 실제 실행 자산은 `PILOT_RUNTIME` 아래에
있다. Dropbox 동기화가 잡은 `.partial` 폴더에는 최종본에도 보충된 테스트 파일
1개가 잔류한다. 연구자는 날짜 폴더만 사용하며 `.partial`은 사용하지 않는다.
