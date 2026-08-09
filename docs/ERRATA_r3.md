# r3 구현 ERRATA 큐

최초 작성: 2026-08-09 KST
상태: append-only 운영 기록

이 파일은 현재 체크리스트를 중단시키지 않는 결함·개선 사항을 기록한다.
기존 행을 지우거나 의미를 바꾸지 않고, 처리 시 새 `RESOLVED` 행을 아래에
추가한다.

등급은 다음 세 가지만 사용한다.

- `STOP`: 이미 생성된 정본이 오염됐거나 오염 중이어서 즉시 중단한다.
- `FIX-NEXT`: 아직 실행 전인 코드·계약 결함이며 지정된 구현 단계에서 고친다.
- `RECORD`: 표기·문서·향후 개선 사항이며 현재 작업을 중단하지 않는다.

## 2026-08-09 외부 리뷰 이관

- [FIX-NEXT] 2026-08-09 | `run_eojeol_realign.ps1` `Archive-StaleTemp` | 명시적 clean 재시도 경로의 함수 인자 수가 맞지 않음 | 체크리스트 5 r3 runner에서 교정·합성 호출 시험
- [FIX-NEXT] 2026-08-09 | `audit_mfa_r3_full_realign_policy.py` | r2 hard-code 탐지가 3개 파일·부분 문자열에 한정됨 | 체크리스트 7 정책 감사 v2
- [FIX-NEXT] 2026-08-09 | `build_common_pron_r3_staged_approval.py` | 동일 승인 JSON을 workflow provenance 변경 때 제자리 갱신함 | 체크리스트 1 불변 승인+별도 sidecar
- [FIX-NEXT] 2026-08-09 | `tests/test_powershell_safety.ps1` | 고정 allowlist·dead 검사 블록 때문에 신규 r3 스크립트가 자동 포함되지 않음 | 체크리스트 7
- [FIX-NEXT] 2026-08-09 | r3 checkpoint 재개 | lock·D: `DATA_SSD` 확인을 runner 본체와 재개 경로에 공통 적용해야 함 | 체크리스트 5
- [FIX-NEXT] 2026-08-09 | r3 장시간 실행 | 절전 방지 enable/restore를 wrapper가 아닌 runner 본체에 둬야 함 | 체크리스트 5
- [FIX-NEXT] 2026-08-09 | r3 저장공간 Gate | r2 고정 45/55GiB 대신 연도별 corpus·temp·DB·staging 산식 필요 | 체크리스트 5
- [FIX-NEXT] 2026-08-09 | follow-up selection bias | 연도·사유·음운환경별 coverage와 정렬층 존재 여부를 표준 보고해야 함 | 체크리스트 3·6
- [FIX-NEXT] 2026-08-09 | 화자 적응 | 세션별 전체/safe 발화 수·safe 음성 길이를 기록하고 약한 적응은 제외 대신 flag | 체크리스트 3·6
- [FIX-NEXT] 2026-08-09 | r3 validator | 발음 mode를 r2 리터럴이 아니라 채택 manifest에서 유도 | 체크리스트 2·4
- [FIX-NEXT] 2026-08-09 | r3 lock 목록 | 존재하지 않는 역사 lock 참조 대신 release-scoped 단일 lock 계약 사용 | 체크리스트 5
- [FIX-NEXT] 2026-08-09 | r3 temp root | C:로 조용히 전환하지 않고 release-scoped D: 경로를 명시적으로 고정 | 체크리스트 5
- [RECORD] 2026-08-09 | Stage 21 회귀 경계 | 외부 리뷰의 `±20ms`는 예시이며 방법론 근거 없이 고정하지 않음; phone byte 일치와 구조 QC를 hard gate로 하고 큰 경계 이탈만 조건부 검토 | 체크리스트 6
- [RECORD] 2026-08-09 | 화자 적응 해석 | follow-up이 세션 내 무작위라는 근거는 현재 없음; 세션 전체 제외는 하지 않되 분포를 실측해 flag·보고 | 체크리스트 3·6
- [RECORD] 2026-08-09 | 문서 권위 | 프로세스 리뷰의 `CLAUDE.md` 언급은 이 저장소의 권위 문서인 `AGENTS.md`로 해석 | 문서 정리 단계

현재 `STOP` 항목은 없다. production Gate가 닫혀 있어 위 결함은 아직 정본
산출물을 오염시키지 않았다.
