# DB v1 표적 occurrence–TextGrid 문맥 시간 연결 파일럿 결과

작성일: 2026-08-18 KST

## 목적

후보 검색표만으로는 연구자가 TextGrid에서 표적 환경을 다시 찾아야 한다.
따라서 morph search의 `left_eojeol_idx/right_eojeol_idx`를 기존 6-tier
TextGrid의 `words` interval에 연결해 검토할 **어절 문맥 구간**을 파생했다.

이 구간은 음운 현상의 실제 시작·끝, 삽입 분절, 실현 여부가 아니다. 실제 판정은
WAV·TextGrid를 본 연구자가 수행한다.

## 결과

| 상태 | 수 |
|---|---:|
| 단일 어절 문맥 구간 연결 | 12 |
| 인접 두 어절 문맥 구간 연결 | 7 |
| 인프라 우선순위 검사라 시간 비적용 | 2 |
| TextGrid 자산 부재·회수 대기 | 1 |
| 합계 | 22 |

언어학적 환경 후보 20개 중 자산이 있는 19개가 모두 연결됐다. 각 연결에서
다음을 검사했다.

- active 발화의 어절 수와 TextGrid 비어 있지 않은 `words` 수 일치
- 문장부호만 제거한 active 어절열과 TextGrid word label열 일치
- 형태소 경계의 1-based 어절 index가 word tier 범위 안에 있음
- 선택 interval의 xmin/xmax와 출력 시간 일치
- active TextGrid SHA-256 일치

동일 발화에 후보 형태소 경계가 여러 개 있으면 occurrence별 행을 유지한다.
예를 들어 한 어절 안의 서로 다른 형태소 경계는 같은 word context 시간을 가질
수 있지만 `target_occurrence_id`와 `occurrence_index`는 다르다.

## 안전 경계

- `target_xmin/xmax`는 **review context span**이다.
- phone boundary, 실제 ㄴ 삽입, 음운 실현을 자동 판정하지 않았다.
- TextGrid·WAV·RC0·RC1·MFA DB를 수정하지 않았다.
- TextGrid가 없는 후보를 삭제하지 않고 `pending_textgrid_asset_unavailable`로
  보존했다.
- 인프라 질의 두 건은 언어학적 occurrence가 아니므로 시간을 억지로 붙이지
  않았다.

## 다음 단계

이제 인프라 검증은 충분하다. 다음 작업은 더 많은 파일럿 검수가 아니라 실제 연구
질의 정의다. 연구별 형태소·의미번호·표기 환경 query set을 동결한 뒤 같은
builder와 linker로 후보표를 만들고, 그때 WAV·TextGrid·CSV 검토 bundle을
생성한다. KOINA나 이어붙인 대화 분석은 확정 후보 중 선택된 자료에만 수행한다.

## 정본 자산

- 연결 결과:
  `outputs/pilots/db_v1_target_interval_link_pilot_20260818`
- 독립 감사:
  `outputs/reports/AUDIT_db_v1_target_interval_link_pilot_20260818.json`
- linker:
  `scripts/python/link_db_v1_target_intervals.py`
- auditor:
  `scripts/python/audit_db_v1_target_intervals.py`

독립 감사 상태는 `passed_context_span_link_no_realization_judgement`다.
