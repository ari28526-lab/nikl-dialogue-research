# 2단계 G3 결과: 2020 단일 연도 생산 감사 통과

작성일: 2026-08-18 KST
전제: G1 query 동결(SHA `744bd8cb…`), G2 join 계약 동결(SHA `12d81163…`),
연구자 G3 진행 지시(같은 날 세션).

## 실행 요약 (전부 실측)

1. **preflight**: 2020 boundaries 50만 행 표본 스캔 → 예상 후보 102,848행,
   출력 경로 부재·C: 여유 51.2GiB 확인, 세 스크립트 py_compile 3/3.
2. **후보 생성** (`build_db_v1_target_manifest.py --years 2020`, 동결 config
   무변경): **101,638행** = QN1 어절 내부 42,604 + QN2 어절 간 59,034
   (preflight 추정 대비 오차 1.2%). 고유 발화 93,360, RC1 curated 발화 1건
   포함. manifest에 `runtime_year_filter=[2020]`과 동결 query SHA 기록.
   출력: `outputs/candidates/n_insertion_v1_2020_g3_20260818`
   (CSV 262,300,565 bytes, SHA `411c8851…`).
3. **변수 join** (`join_n_insertion_candidate_variables.py`, G2 계약 구현):
   zero-drop 101,638 in = out.
   - sense join: 위치·표면형·품사 불일치 **0건**(morph_tag_mismatch 0,
     no_row 0, 누락 세션 파일 0) — A2 토큰화 일치가 파일럿 26/26에 이어
     전수 10만 행 규모에서도 확인됨.
   - 왼쪽 joined 75,236 + joined_not_target 26,402(왼쪽 J/E/S — 왼쪽 품사
     무제한 방침의 예상 결과), 오른쪽 joined 101,636 + not_target 2
     (S-계열 태그 흔적, 상태로 보존).
   - etym/freq join: 양측 100% (165,920항 사전이 출현 형태소 전부 커버).
   - `boundary_etym_class`: etym_unknown 79,790(78.5% — 용언·조사 등
     사전 etym 빈값, 계약대로 미추정 보존) / mixed 12,614 /
     native_compound 8,538 / loan_involved 585 /
     **sino_internal_candidate 111**(한자어 내부 ㄴ삽입 후보).
   출력: `outputs/candidates/n_insertion_v1_2020_g3_joined_20260818`
   (CSV 284,627,076 bytes, SHA `c6f7e388…`).
4. **독립 감사** (`audit_stage2_g3_n_insertion.py`, 생성기와 별도 코드):
   **13/13 통과, status `passed`** —
   `outputs/reports/AUDIT_stage2_g3_n_insertion_2020_20260818.json`.
   동결 SHA 3중 결속, 10만 행 전수 조건 재평가, occurrence ID 유일성,
   zero-drop, 상태 카운트 독립 재집계, 표본 재파생(원천 직접 재조회) 일치.

## 운영 기록 (재발 방지)

- Desktop Commander `start_process`가 출력 없는 장시간 python을 기다리다
  브리지 60초 한도에서 타임아웃 → 이후 **detached 실행 launcher(.ps1) +
  로그·산출물 판정** 패턴으로 전환(스킬 §2·§7 원칙 그대로).
- 타임아웃된 첫 호출이 실제로는 실행돼 완주했고, 재실행 시도는 builder의
  기존 출력 비덮어쓰기 가드(FileExistsError)가 정확히 차단했다 — 거짓 이중
  실행 없음.
- 대용량 후보 CSV 2개(262MB/284MB)는 GitHub에 올리지 않는다(.gitignore
  규칙 추가). manifest·감사 JSON만 저장소에 기록하고 실물은 로컬
  `outputs/candidates`가 정본이다.

## G3가 판정하지 않은 것

실현 여부·시간 연결·검토 표본은 이 Gate의 범위가 아니다. 101,638행은
"ㄴ삽입 가능 환경의 넓은 후보"이며 실현 판정(G7)과 무관하다.

## 다음 Gate

- **G4**: 같은 동결 SHA로 2021–2025 연도별 생성+join+감사 (연도당 위와
  동일 절차, checkpoint = 연도별 출력 폴더). 연구자 GO 필요.
- **G5**: 문맥 시간 연결(linker) — G4 후.
- 미결 결정: **G6 표본 전략**(전수 청취 vs 층화 우선). RC1 curated 후보
  1건의 enrichment 여부는 검토 표본 확정 시 판단.
