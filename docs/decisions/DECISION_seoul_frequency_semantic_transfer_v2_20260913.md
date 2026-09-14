# 서울 빈도표의 기존 기계 WSD 결과 연결 수정

2026-09-13 사용자 재집계 지시. 새 WSD 호출 없이 기존 바른·연구사전 결과를 빈도 초안에 연결한다.

구형 빈도 입력기는 사람의 최종 확정을 위해 항상 null로 보존한 comparison.final_selected_group만 읽었다. 그 결과 기존 비교 그룹이 있어도 형태소 split에서 모두 미결정이 되었다. 구형 서울 WSD와 연구사전 결과는 손실되지 않았다.

## 수정본의 선택 규칙

| 기존 비교 상태 | 빈도 초안에서 선택할 그룹 | 근거 구분 |
|---|---|---|
| same_homonym_group | 서로 일치한 그룹 | bareun_dictionary_agreement |
| bareun_group_dictionary_undecided | 바른 그룹 | bareun_only |
| dictionary_proposal_bareun_unmapped | 연구사전 후보 그룹 | dictionary_only_candidate |
| group_conflict | 미결정 | conflict_hold |
| both_unresolved_or_unmapped | 미결정 | 기존 상태 보존 |
| not_lexical_target | 미평가 | 기존 상태 보존 |
| 원 발화에 source_gap 표시 | 미결정 | source_gap_hold 우선 |

선택 그룹은 기계 초안이며 사람 검증을 뜻하지 않는다. human_verified=false를 유지한다. 원 comparison과 final_selected_group은 수정하지 않는다. 세부 출처·바른/연구사전 그룹·선택 결과를 형태소 출현별 원장으로 보존한다. 알 수 없는 상태나 상태와 그룹 값의 모순은 자동 통과시키지 않는다.

## 범위와 검증

서울만 별도 v2 파생본으로 재집계한다. 기존 v1·모두·native 다층위/LS/MP 산출물·원 WSD 입력·의미 번호는 변경하지 않는다. 형태·어휘 구성과 어절 정렬 정책은 기존 함수를 그대로 재사용한다. 기존 합산판의 모든 키·계수·출현 파일 수와 수정본의 일치를 전수 검사한 뒤 참고 빈도가 포함된 합산 CSV·JSONL을 바이트 단위로 재사용한다.

검증은 상태별 단위 시험, 작은 실제 파일럿, 전체 출현 회계, split 합계=collapsed 항목별 일치, 원장에서 재계수한 의미별 형태소 빈도 일치, 실제 복수 그룹으로 나뉜 키의 존재, 충돌·누락 보류에 선택 그룹이 없는지를 포함한다. 의미가 몇 건이라도 실제 연결됐는지도 필수 확인한다. 사람이 확정한 의미 정확도 검사는 별도 연구 범위다.

새 코드: scripts/python/seoul_frequency_semantics_v2.py, scripts/python/recount_seoul_frequency_v2.py. 완료 증거와 현행 결과 경로는 재집계 완료 보고서에 기록한다.
