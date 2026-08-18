# DB v1 overlay-aware target manifest 파일럿 결과

작성일: 2026-08-18 KST

## 왜 이 단계로 전환했는가

RC1의 수동 보정 16건은 이미 word 경계, 최종 전사, 철자 Roman, 활성 TextGrid
pointer와 provenance가 보존돼 있다. 전체 5,103,356발화에 비해 이 16건의
형태소·phone을 지금 모두 다시 만드는 것은 연구 진도를 내는 핵심 병목이 아니다.
따라서 RC1을 동결하고, 실제 연구 표적을 검색할 때 RC0 기본값과 RC1 수동
보정값을 자동으로 합치는 범용 후보 manifest를 먼저 검증했다.

## 파일럿 범위

두 질의를 선언형 JSON으로 고정했다.

1. `Q0_ACTIVE_OVERLAY_SMOKE_2020`: RC1 수동 보정 두 발화를 exact ID로 찾아
   active precedence를 검사하는 인프라 질의다. 언어학적 표적이 아니다.
2. `Q1_N_INSERTION_LIKE_ORTH_ENV_2020`: 왼쪽 형태소 말음이 있고, 오른쪽
   형태소가 초성 ㅇ과 `ㅣ·ㅑ·ㅕ·ㅛ·ㅠ` 중 하나로 시작하는 형태소 경계 20개를
   뽑았다. 이는 ㄴ 삽입 **가능 환경의 넓은 후보**이며 실현 여부 판정이 아니다.

## 결과

| 항목 | 결과 |
|---|---:|
| 질의 | 2개 |
| 후보 occurrence | 22개 |
| 고유 발화 | 20개 |
| RC1 curated precedence 적용 | 2개 |
| WAV·TextGrid 수동 검토 가능 | 21개 |
| 메타데이터 전용·정렬/회수 대기 | 1개 |

RC1 두 발화에서는 구 전사 대신 연구자 수동값이 실제 manifest에 들어갔다.

- `SDRW2000000115.1.1.149`: `영화 잘 영화 잘알이` → `영화 잘`
- `SDRW2000000180.1.1.67`: 중복·오기 전사 → `학 상자를 날라야 되니까는`

독립 감사는 다음을 재계산해 모두 통과했다.

- 질의 조건과 각 evidence 행의 재일치
- `(year, utt_id)` RC1 curated 우선순위
- 검토 가능 후보의 WAV·TextGrid 실재
- 자산이 없는 후보의 명시적 metadata-only 표지
- 빈 `target_xmin/target_xmax`와 별도 시간 연결 대기 상태
- 자동 실현 판정, MFA, 원자료·RC0·RC1·TextGrid 수정 0건

## 방법론적 해석

이 단계의 출력은 연구 결론표가 아니라 **후보 추출표**다. 철자·형태소 환경은
후보를 재현 가능하게 좁히고, MFA TextGrid와 WAV는 연구자가 실제 실현을 듣고
판정하는 근거를 제공한다. G2P나 MFA phone을 실현 판정의 정답으로 사용하지
않는다. KOINA 및 이어붙인 대화 자료도 이 manifest에서 선별한 발화를 후속
작업으로 연결하되, 원 발화 ID와 source interval provenance를 유지해야 한다.

## 다음 순서

1. 이 pilot query 형식을 실제 연구의 형태소·의미번호·표기 환경 질의로 확장한다.
2. 후보 occurrence를 TextGrid의 word interval에 연결해 `target_xmin/xmax`를
   채우는 별도 파생 단계를 만든다. 연결 실패는 후보를 삭제하지 않고 상태로 남긴다.
3. WAV·TextGrid·CSV를 복사하는 검토 bundle은 확정 질의에 대해서만 만든다.
4. RC1 16건의 형태소·phone enrichment는 실제 표적에 포함된 exact ID에만
   수행한다.

이 순서로 D7–D10 청취 검토나 2020–2025 MFA를 반복하지 않는다.

## 정본 자산

- 질의 정의:
  `config/target_queries/db_v1_target_manifest_pilot_20260818.json`
- 파일럿 결과:
  `outputs/pilots/db_v1_target_manifest_pilot_20260818`
- 독립 감사:
  `outputs/reports/AUDIT_db_v1_target_manifest_pilot_20260818.json`
- builder:
  `scripts/python/build_db_v1_target_manifest.py`
- auditor:
  `scripts/python/audit_db_v1_target_manifest.py`

감사 상태는 `passed_pilot_query_and_active_precedence`다.
