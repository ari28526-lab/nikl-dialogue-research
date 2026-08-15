# 연구 DB v1 준비 A–C 방법

## 목적

연구의 최종 목적은 형태소·표기상 음운 환경으로 후보를 찾고, 해당 WAV와
TextGrid를 결합한 뒤, 선별 자료에 KOINA 등 운율 분석을 적용하고 연구자가 실제
실현 여부를 판단하는 것이다. 따라서 강제정렬 성공 자료만 모으는 것으로는
충분하지 않다. 원천 발화 전체가 현재 어느 단계에 있고 왜 본체에 포함되거나
후속으로 남았는지를 exact-ID로 설명할 수 있어야 한다.

A–C는 다음 두 문제를 막기 위해 수행했다.

- 연도별 작업을 완료한 뒤 같은 기준을 썼다는 근거를 다시 만들지 못하는 문제
- 기술 실패나 발음 보류 발화가 암묵적으로 사라져 연구 표본과 분모가 달라지는 문제

## A. 6개년 base 동결과 같은 방법론 교차 감사

각 연도의 `YEAR_INPUT_CONTRACT`, `ALIGNMENT_CONTRACT`, `ALIGN_DONE`, 최종 export,
독립 QC state와 동반표 manifest를 연결했다. 다음 공통 항목이 2020–2025에서
동일한지 비교했다.

- 발음 release와 pronunciation contract
- 최종 MFA dictionary SHA-256
- Korean MFA acoustic model SHA-256
- Jamo G2P provenance SHA-256
- Python·MFA·Pynini runtime
- safe-body routing contract
- `fresh_r3_full_realign` origin
- `research_textgrid.v2` 6-tier schema

연도별 exact-ID 입력 계약과 corpus contract는 해당 연도의 자료 범위이므로 서로
다른 것이 정상이다. 관측 phone의 출현 빈도나 부분집합도 연도별 말뭉치 차이이며
방법론 불일치로 보지 않는다.

최종 2024 export는 최초 실패 보고서와 2발화 표적 회수 뒤 성공 보고서가 함께
보존돼 있다. 단순 파일명이나 수정 시각으로 정본을 추측하지 않고, 독립 QC state에
동결된 `export_report_sha256`과 정확히 일치하는 보고서만 채택했다. 이 규칙은 실패
증거를 삭제하지 않으면서도 과거 실패를 최종 결과로 오인하지 않게 한다.

보존 MFA DB와 연도별 동반표 4종은 이 실행에서 실제 SHA를 다시 계산해 기존
marker/manifest와 일치함을 확인했다. 개별 TextGrid 4,286,046개의 전수 byte-Merkle
inventory는 별도 release QA I로 남겼다. 현재 A–C에서는 이미 통과한 연도별 전수
구조 감사, TextGrid 수량, 동반표 exact-ID, DB 재수출 표본 24/24를 근거로 쓴다.

## B. 저장공간·archive 읽기 전용 계획

D:는 원자료, r3 DB, 최종 6-tier, 모델과 계약의 정본 위치로 유지한다. E:는 향후
별도 승인된 `copy → manifest → SHA/CRC 검증 → read-only freeze` archive의 우선
대상이다. H:는 현재 여유 용량상 전체 mirror가 아니라 선택적 이중 백업 후보로
둔다. 이 단계에서는 파일을 이동·삭제·압축하지 않았다.

장부는 압축했을 때 수십 MB 수준이므로 프로젝트 `outputs/releases`에 두되 Git의
`*.gz` 제외 규칙을 따른다. 코드·방법·작은 JSON manifest만 Git으로 공유한다.
향후 D recovery shard는 별도의 용량 Gate를 통과하기 전 시작하지 않는다.

## C. 5,103,356발화 exact-ID 상태 장부

연도별 `pronunciation_safe_ids`와 `pronunciation_followup_ids`의 합집합을 원천
발화 범위로 삼았다. safe 내부에서는 승인된 `pre_mfa_exclusion_ids`를 먼저 빼고,
남은 집합이 `expected_mfa_input_ids`와 행 단위로 완전히 같은지 검사했다. MFA 입력
안에서는 연구자 승인 post-MFA exact-ID를 분리하고 나머지가 독립 QC의 최종
TextGrid 수와 같은지 확인했다.

각 발화는 다음 `primary_status` 중 하나만 가진다.

| 상태 | 뜻 | MFA 입력 | 최종 6-tier | 후속 필요 |
|---|---|---:|---:|---:|
| `aligned_safe_body` | r3 정렬·독립 QC를 통과한 본체 | 예 | 예 | 아니오 |
| `pre_mfa_technical_exclusion` | WAV/시간/기호 등 기술 사유로 MFA 전 제외 | 아니오 | 아니오 | 예 |
| `post_mfa_technical_exclusion` | MFA 입력에는 있었으나 완전한 word+phone interval 부재 | 예 | 아니오 | 예 |
| `pronunciation_followup` | 발음 입력 근거를 더 확정한 뒤 정렬할 별도 대상 | 아니오 | 아니오 | 예 |

`methodological_exclusion`은 0이다. 연구자의 음운 실현 판정, 소음·겹침에 따른 주
분석 제외, 연구 질문과 무관한 발화 제거를 기술 상태와 섞지 않았기 때문이다.

### 장부 열

| 열 | 의미와 활용 |
|---|---|
| `year`, `utt_id`, `session_id`, `source_csv` | WAV·TextGrid·형태소/검색표·세션 대화로 돌아가는 기본 조인 키 |
| `primary_status` | 현재 발화의 상호배타적 1차 상태 |
| `status_family` | aligned/technical/pronunciation 범주의 간단한 집계 키 |
| `reason_codes_json` | 기술 사유 또는 발음 routing 사유의 기계 판독 목록 |
| `mfa_expected` | 해당 발화가 동결 r3 MFA 입력 집합에 포함됐는지 |
| `textgrid_available` | 최종 6-tier가 현재 존재하는지 |
| `followup_required` | recovery 또는 발음 해결 후속 대상인지 |
| `alignment_scope` | 후속 조치가 정렬·분석 양쪽인지, 발음 해결 선행인지 |
| `evidence_key` | 원 결정을 재현할 정본 목록의 종류 |
| `year_input_contract_id`, `alignment_contract_id` | 연도 입력과 정렬 방법론에 대한 provenance 결속 |

발음 보류의 실제 토큰 목록은 장부에 반복 복제하지 않는다. 정본
`pronunciation_followup_ids_<YEAR>.csv.gz`에 그대로 남기고 장부는 그 근거 종류와
exact-ID를 참조한다.

## 중단·재개와 독립 감사

각 연도 압축 장부를 원자적으로 쓴 뒤 입력 SHA와 출력 SHA를 가진
`YEAR_LEDGER_MANIFEST`를 만든다. 재실행할 때 입력 signature와 장부 SHA가 같으면
완료 연도를 재사용한다. 실제 실행에서 2024의 최초 실패 export 선택 문제로 한 번
안전 중단됐지만, 2020–2023 체크포인트는 재계산하지 않았다.

생성기와 별도인 `audit_db_v1_release_prep.py`가 5,103,356행을 다시 읽어 ID 중복,
연도 결속, 상태 불변식, 계약 ID, 장부 SHA, 출력 manifest, 공통 방법론, DB·동반표
SHA 결속을 재검사했다. 결과는
`outputs/reports/AUDIT_db_v1_release_prep_ac_20260815.json`의 `passed`다.

## 다음 Gate

다음 D단계는 현재 장부의 이유별 후속 shard를 만드는 일이다. 우선순위는
post-MFA 3,086건과 pre-MFA 기술 제외 95,860건의 회수 가능성 분리이며,
pronunciation follow-up 718,364건은 발음 근거 유형별로 나눈다. D는 새 입력·용량·
출력 계약을 만든 뒤 별도로 시작하며, A–C 완료가 자동으로 대량 recovery/MFA나
삭제·이동을 승인하지 않는다.
