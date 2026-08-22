# 외부 도구용 프롬프트 — PV 파일럿 설계 검토·구현 (2026-08-19)

아래 구분선 안 블록을 그대로 외부 도구(Codex 등)에 붙여넣는다. 이 프롬프트는
설계 검토를 먼저 요구하고, 구현은 사용자 GO 뒤에만 진행하게 한다.

---

C:\Users\ari30\research\2026_summer_research 저장소에서 작업한다.

[역할] 한국어 형태음운 연구 저장소의 2단계 "PV 파일럿"(일곱 현상 미리듣기
스윕) 설계를 검토하고, 사용자가 GO를 주면 승인된 범위만 구현한다.

[먼저 읽을 것 — 순서대로]
1. CLAUDE.md  (프로젝트 불변 규칙. 이 프롬프트와 충돌하면 CLAUDE.md 우선)
2. docs/decisions/PLAN_stage2_seven_phenomena_PV_pilot_20260819.md  (이번 작업 정본)
3. docs/decisions/PLAN_stage2_target_query_and_realization_design_20260818.md
4. docs/decisions/RESULT_stage2_G1_query_freeze_20260818.md 부터 G4, D_mirror까지 5개 RESULT
5. config/target_queries/n_insertion_production_v1_20260818.json,
   config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json
6. scripts/python/build_db_v1_target_manifest.py, join_n_insertion_candidate_variables.py,
   link_db_v1_target_intervals.py, audit_stage2_g3_n_insertion.py,
   morph_schema.py(경계·unit 열 정의), stitch_session.py, locate_utt.py
7. phenomena/34_n_insertion/definition.md
8. PV-B 참고: docs/decisions/DECISION_post_search_acoustic_measurement_tooling_20260814.md,
   docs/decisions/PLAN_KOINA_intonation_IP_AP.md,
   docs/reviews/REVIEW_hyunjung_joo_KOINA_prosody_literature_20260810.md

수치·경로·열 이름은 문서 요약을 믿지 말고 manifest·감사 JSON·실제 gz 헤더
1행 실측으로 확인한다(예: morph_units 헤더는 실측 전 추정 금지).

[작업 순서 — 반드시 이 순서]
1. 설계 검토: 계획 정본(위 2번) §2–§6을 검토해 (a) 오류·위험 (b) 더 단순한
   대안 (c) 실측으로 확인할 항목을 docs/reviews/incoming/ 아래 새 파일로
   보고하고 정지한다. 코드를 아직 쓰지 않는다.
2. 사용자 GO 후 구현: 계획 §5의 작업 목록 1–9만 구현한다. 범위 추가 금지.
3. 검증: 스크립트마다 py_compile + 대표 시나리오 dry test(성공/실패/기존
   출력 존재 시 중단)를 수행하고 결과를 로그 파일로 남긴다.
4. 실행 준비: 사용자가 실행할 단일 wrapper 명령(run_pv_preview_pilot.ps1,
   -PreflightOnly 포함)을 문서로 안내한다. 실제 실행·청취 개시는 사용자 몫.
5. 결과 기록: 실행 완료 후 RESULT 문서 초안과 감사 JSON 경로를 보고한다.

[안전 규칙 — 위반 시 즉시 정지]
- D:\00_RAW, D:\10_LAYERS 검색 7표, RC0/RC1 release, r3 DB·6-tier·동반표,
  outputs/candidates의 ㄴ삽입 G1–G4 산출물은 읽기 전용. 수정·삭제·이동 금지.
- MFA, KOINA, wav2vec2, 대량 음성 처리 실행 금지. 전수 스캔 대신
  max_occurrences 상한으로 조기 중단.
- 신규 출력은 outputs/pilots/pv_seven_phenomena_20260819/ 아래에만.
  기존 출력 비덮어쓰기(FileExistsError 패턴), .partial 원자 승격, SHA manifest.
- 자동 실현 판정 금지. PV 기록은 탐색 전용이며 정식 판정 ledger와 분리.
- 후보·표본 행을 조용히 삭제하지 않는다(zero-drop: 입력 = 출력 + 상태).
- .ps1은 UTF-8 BOM 필수(첫 3바이트 EF BB BF 확인), Windows PowerShell 5.1
  호환(&&, ??, 삼항 금지). Python은
  C:\Users\ari30\miniforge3\envs\mfa\python.exe 를 사용하고
  sys.stdout.reconfigure(encoding="utf-8")를 넣는다.
- 장시간 명령은 detached 실행 + 로그 파일 판정(콘솔 대기 금지).
- git commit·push는 사용자가 명시 지시할 때만. Bareun secret 등 비밀값을
  출력·복사하지 않는다.
- 기존 스크립트(builder 등)는 가능한 한 무수정 재사용한다. 수정이 불가피하면
  사유를 보고하고 승인 후 최소 변경 + 기존 ㄴ삽입 산출물 재현 회귀로 검증한다.

[산출·보고 형식]
- 검토 보고: docs/reviews/incoming/EXTERNAL_REVIEW_pv_pilot_<식별자>_20260819.md
- 구현 후: 변경 파일 목록, 검증 로그 경로, 실행 안내 명령, 미해결 질문.
- 모든 보고는 한국어로, 실측 근거(파일 경로·행 수·SHA)와 함께.

---

## 사용 방법 메모 (이 저장소 기록용)

- 사용자 검토용 HTML: outputs/reports/PLAN_stage2_seven_phenomena_PV_pilot_20260819.html
- 이 프롬프트가 가리키는 정본: docs/decisions/PLAN_stage2_seven_phenomena_PV_pilot_20260819.md
- 프롬프트·계획 모두 2026-08-19 계획 세션 산출물이며 커밋 전 상태로 생성됨.
