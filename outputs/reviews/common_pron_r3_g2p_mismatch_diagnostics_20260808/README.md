# 공통발음 r3 불일치 패턴 결정표 안내

이 폴더는 G2P 후보와 독립 규칙 Roman 목표가 정확히 일치하지 않은 항목을
반복 패턴 단위로 압축한 연구자 검토용 handoff다. 개별 어휘 21만여 개를 사람이
전수 검토하는 표가 아니며, 공통발음 r3 채택 승인표도 아니다.

## 무엇을 줄였는가

- 불일치 target: 214,321개
- source 표면형: 215,184개
- source 출현: 2,796,609회
- 전체 편집 패턴: 2,625개
- 결정표 행: 56개
- 56개 행이 포괄하는 불일치 출현: 2,590,212회(92.620%)

선정 기준은 전체 출현 상위 30개 패턴, 각 진단 class의 출현 상위 5개,
표상 차이이지만 아직 완전한 근거가 없는 패턴 전부, 기존 문제 발화가 포함된
회귀 패턴이다. 동일 패턴은 한 번만 제시한다.

## 핵심 열

| 열 | 의미 |
|---|---|
| `review_order` | 검토 순서 |
| `selection_reasons` | 상위 빈도·class 대표·회귀 표본 등 이 행을 뽑은 이유 |
| `diagnostic_layer` | 표상 동등성 후보, 표상 추가 검토, model 내부 대조, 실질 차이 후보 |
| `diagnostic_class` | 길이·활음 병합, 단일 치환, 단위 누락 등 세부 자동 진단 |
| `edit_signature` | 후보 broad Roman과 규칙 Roman 사이의 순서 보존 편집 요약 |
| `target_count` | 이 패턴에 속한 중복 제거 G2P target 수 |
| `source_type_count` | 이 패턴에 연결된 source 표면형 수 |
| `total_occurrences` | 2020–2025 전체 출현 수 |
| `count_2020`–`count_2025` | 연도별 출현 수 |
| `example_targets_json` | 대표 target과 후보·규칙 Roman 근거 |
| `example_tokens_json` | 대표 source·형태소·사전 근거 |
| `proposed_policy` | 자동 승인 아닌 다음 검토 방향 |
| `review_question_ko` | 연구자가 나중에 판단할 질문 |
| `decision`, `notes` | 나중의 명시적 결정·메모 입력란 |
| `automatic_equivalence_approved` | 전 행 `false`; 이번 단계에서 자동 동등성 승인 없음 |

## 해석 원칙

- `representation_equivalence_candidate`는 acoustic-model phone 하나가 `Y/W`의
  활음성 또는 장음·중복 Roman 단위를 함께 나타낼 가능성이 있다는 뜻이다.
  최종 동등성 승인이라는 뜻이 아니다.
- `substantive_difference_candidate`는 자동 G2P 1-best를 그대로 선택하지 말고,
  규칙·사전·형태소 근거를 이용한 다른 projection을 찾아야 한다는 뜻이다.
- `contrast_review_required`는 같은 acoustic-model broad group 안의 대조라 해도
  연구 기준상 무시할 수 있는지 별도 확인해야 한다는 뜻이다.
- 이 표를 채우지 않아도 현재 진단 결과는 유효하다. 최종 canonical 선택을
  시작할 때 반복 정책을 명시적으로 결정하는 입력으로 사용한다.

관련 결과 문서:
`docs/decisions/RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`
