# workflow reset archive manifest

생성일: 2026-08-01 KST

삭제는 하지 않았다. 현재 실행에서 제외된 문서는 Git 이력과 아래 상태로
보존한다.

| 원래 경로 | 현재 경로 | 처리 | 이유 |
|---|---|---|---|
| `docs/environment/PROJECT_CURRENT_STATE.md` | `docs/archive/PROJECT_CURRENT_STATE_20260801_full.md` | 물리 archive | append-only 누적본을 교체형 현재 상태에서 분리 |
| `docs/TODO_A단계.md` | 동일 | superseded header | 2026-07-23 G2P 이전 TODO |
| `docs/WORKFLOW.md` | 동일 | historical header | 연구 개요는 유효하나 생산 명령은 낡음 |
| `docs/HANDOFF_pilot_search_master.md` | 동일 | superseded header | 구 세션 진입점 |
| `docs/HANDOFF_search_master_session2.md` | 동일 | superseded header | 구 세션 진입점 |
| `docs/GUIDE_실행순서_제3자용.md` | 동일 | superseded header | 구 감사·파일럿 순서 |

이동하지 않은 핵심 근거:

- `docs/decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`
- `outputs/presentations/MFA_research_infrastructure_final_prebulk_20260801.pptx`
- `outputs/presentations/MFA_research_infrastructure_final_prebulk_20260801.pdf`

구 파일럿 output과 D:/E:/H: 대형 파일은 이번 reset에서 삭제·이동하지 않았다.
용량 정리는 전수 계산과 겹치지 않는 시점에 별도 dry-run과 승인으로 수행한다.
