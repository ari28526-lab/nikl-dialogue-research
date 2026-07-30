# 외부 리뷰 조치 기록: r2 MFA 연구 자료 흐름

- 날짜: 2026-07-30
- 대상 리뷰:
  `incoming/EXTERNAL_REVIEW_r2_MFA_research_workflow_3839872_20260730.md`
- 외부 판정: `GO AFTER FIXES`
- 현재 단계: 6개년 r2 기계 파일럿 통과, 연구자 인프라 검토 대기
- 전수 MFA: 시작 전

이 문서는 리뷰 지적을 단순히 “반영함”으로 표시하지 않고, 코드·실물·시험
증거가 있는 항목만 완료로 기록한다. 현재 파일럿은 구체적인 음운 실현 판정이
아니라 CSV–WAV–TextGrid 연결, 동일 MFA 방법 계약, 4-tier 구조와 연구자 검토
편의성을 확인하는 단계다.

## 조치표

| ID | 상태 | 조치와 근거 | 전수 시작 전 남은 일 |
|---|---|---|---|
| MFA-001 | 구현·회귀시험 완료 | `preflight_eojeol_realign.ps1`과 `preflight_next_year_after_qc.py`가 기대 발음 모드를 명시적으로 받고 `common_pron_mfa_r2_latest_jamo` marker를 승인한다. legacy 정상·미지값 거부 시험도 보존한다. | 없음 |
| MFA-002 | 실측·보존 격리 완료 | 구 2020/2021 align/merge marker 4개를 삭제하지 않고 `D:\mfa_eojeol\done\archive_stale\r2_transition_20260730_legacy_markers`로 이동했다. 보고서: `outputs/reports/ARCHIVE_legacy_mfa_markers_for_r2_20260730.json`. 유효한 LAB 입력 marker는 유지했다. | 없음 |
| MFA-003 | 구현·6개년 실측 통과 | `build_mfa_year_phone_inventory.py`가 보존 DB의 실제 phone interval을 집계해 여섯 연도 모두 `spn=0`, 허용 inventory 밖 phone 0을 확인했다. `audit_mfa_cross_year_contracts.py`는 6/6 연도의 동일 phone 생성 기준·허용 inventory SHA와 방법 계약 불일치 0을 기록했다. | 전수 실행에서도 연도별 반복 |
| MFA-004 | 구현·기계 검증 완료, 연구자 실검토 대기 | 파일럿은 연도별 DB→4-tier 재수출 표본을 5세션씩 비교했다. Dropbox에 60발화 평면 묶음과 `REVIEW.xlsx`를 생성하고 240개 링크를 감사했다. `validate_mfa_r2_review_workbook.py`는 XLSX의 허용 입력 열만 회수해 기계가독 승인 보고서를 만들고, `preflight_next_year_after_qc.py`는 표본·연구자 보고서를 필수 입력으로 받아 동일 DB·input/alignment contract를 결합한다. | 연구자 인프라 실검토; 전수에서는 연도별 승인 보고서 경로 사용 |
| CSV-001 | 구현·회귀시험 완료 | LAB 생성 manifest가 `source_eojeol_index → mfa_word_index`를 발화별로 명시하고 비한글 전용 탈락 어절을 `null`로 보존한다. 숫자·기호 포함 fixture로 index 밀림을 검사한다. | post-MFA 레이어 구현 때 이 대응표만 사용 |
| CSV-002 | 파일럿 범위 완료, 전수 범위 미완 | 파일럿이 선택한 30개 세션 CSV는 파일별 SHA와 aggregate SHA로 동결했다. 이는 60발화 파일럿 입력에는 충분하지만 17,156개 전체 세션의 전수 동결 증거는 아니다. | 전수 LAB/MFA 전에 전체 `_session_hashes.json`을 생성하고 입력계약에 포함 |
| CSV-003 | 완료 | D: 우선 정책과 반대였던 preflight 안내문을 교정했다. | 전체 PowerShell 정적시험 |
| CSV-004 | 완료 | 상태 정본의 “6개년 재정렬 완료” 오독 문장을 계획형으로 고치고, 전수 MFA와 60발화 파일럿 상태를 분리했다. | 단계 전환 때 상태 정본 동시 갱신 |
| MFA-005 | 구현·실물 대조 완료 | direct export 보고서와 여섯 연도의 machine marker에 `phones_mfa`, legacy morpheme source, utterance/search source를 기계가독 `tier_provenance`로 남겼다. | 전수 결과에서도 반복 확인 |
| MFA-006 | 완료 | LAB 생성기의 `--search-master-root`를 명시 입력으로 강제했다. | 전체 회귀시험 |
| MFA-007 | 6개년 기계 파일럿 통과 | 새 `run_mfa_r2_infrastructure_pilot.ps1`이 공통사전 r2·고정 acoustic·inline G2P 금지·`pron_reference_form`·direct DB 4-tier·연도 QC를 같은 사슬로 실행해 2020–2025를 모두 통과했다. 구 파일럿 산출물은 시행착오 기록으로 보존한다. 최종 전달 감사는 60발화·payload 240·링크 240을 통과했다. | 연구자 Dropbox 검토와 최종 코드 동결 |

## phone inventory 해석

연도별 실제 관측 phone 집합은 각 표본·코퍼스에 등장한 단어가 다르므로
동일할 필요가 없다. 논문에서 “같은 phone 기준”을 입증하는 근거는 다음의
결합이다.

1. 동일한 동결 acoustic model과 SHA
2. 동일한 공통사전과 SHA
3. 동일한 허용 phone inventory 목록과 SHA
4. 각 연도의 모든 관측 phone이 허용 inventory의 부분집합
5. 각 연도의 실제 `spn` phone interval 0

관측 집합의 연도 차이는 오류가 아니라 기술 통계로 보고한다. 서로 다른
코퍼스에서 우연히 출현하지 않은 phone까지 강제로 동일하게 만들지 않는다.

## 파일럿과 전수 진입의 구분

60발화 파일럿은 여섯 연도의 방법 호환성을 한 번에 찾기 위해 연도 사이를
자동 진행했고, 모든 기계 gate와 6개년 교차 감사를 통과한 뒤에만 Dropbox
평면 묶음을 만들었다. 이제 연구자가 연도별 최소 5화자씩
WAV/TextGrid/LAB/CSV 연결과 tier 사용성을 검토한다.

전수 실행은 다르게 운영한다. 2020 전수 정렬 뒤 독립 QC·DB 재수출
동등성·phone inventory·연구자 표본 승인을 모두 기계가독 보고서로 결합하고,
그 gate가 통과해야 2021로 넘어간다. 따라서 파일럿에서의 자동 연도 진행을
전수 실행의 무인 자동 승인으로 해석하지 않는다.
