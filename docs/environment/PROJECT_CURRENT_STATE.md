# 프로젝트 현재 상태 정본

최종 갱신: 2026-08-04 KST

이 문서는 append-only 일지가 아니다. 현재 상태가 바뀌면 전체를 교체한다.
이전 전체본은 `docs/archive/PROJECT_CURRENT_STATE_20260801_full.md`에 보존한다.

## 연구 목적

```text
형태소·표기상 음운 환경을 CSV/Parquet에서 검색
  → utt_id로 WAV·TextGrid·메타데이터 수집
  → 선별 후보에만 KOINA·이어붙이기·wav2vec2 보조 분석
  → 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA/G2P phone은 강제정렬을 위한 대략적인 분절 보조값이다. 실제 실현 판정,
음소 전사 정답, 음운론적 분석 결과로 취급하지 않는다.

## 동결된 생산 계약

- 2020–2025를 모두 공통 Jamo r2 기준으로 새로 정렬한다. 구 2020/2021
  정렬은 최종 산출물로 재사용하지 않는다.
- 발음·모델: `common_pron_mfa_r2_20260728`, Korean MFA acoustic v3.3.0,
  Jamo G2P v3.2.0, 연구자 승인 예외 27건. phone 기준은 6개년 동일하다.
- 기본 TextGrid는 6-tier다:
  `words / phones_mfa / phoneme_r_auto / utterance / utterance_orth_r /
  morph_analysis_utt`.
- 모든 tier는 0–xmax를 연속적으로 덮는다. `morph_analysis_utt`는 발화 수준
  형태소 정보이며 형태소 경계를 음향 시간경계라고 주장하지 않는다.
- pre-MFA 검색층은 `morph_search.v3` 연도별 7표, post-MFA 동반층은
  연도별 gzip 4표다. 원자료 좌표, 형태소 좌표, MFA 좌표를 섞지 않는다.
- 우리말샘 1:N 발음은 후속 보조 검색표다. MFA 사전 발음을 자동 교체하지 않는다.
- KOINA, stitch, wav2vec2는 선별 후보에만 추가하며 MFA 열을 덮어쓰지 않는다.
  이어붙인 seam을 가로질러 운율을 해석하지 않는다.
- 이 계약은 최종 점검 슬라이드
  `outputs/presentations/MFA_research_infrastructure_final_prebulk_20260801.pptx`
  및 PDF와 일치해야 한다.

## 실측 완료

- 동결 pre-MFA search master: 2020–2025, 5,103,356발화,
  `_build_meta.status=success`.
- 공통 Jamo r2 release/adoption: `passed`, `allow_yearly_mfa=true`.
- 6-tier exporter, 동반표, DB checkpoint, 독립 연도 감사, DB 표본 재수출,
  승인 제외 계약, 연도 큐 구현.
- 2020 `morph_search.v3`: 23/23 성공, 870,437발화, 7개 연도표 생성,
  중복 0·기호 coverage 일치·현재 lock 없음.
- workflow reset과 음원 대응 gate·복구 코퍼스 계약 반영 뒤 Python 304개 및
  PowerShell 안전검사 34개 파일 통과.
- 2020 공통 Jamo r2 신규 MFA 계산 완료. active 868,550발화 중 868,187발화에
  word+phone interval이 있고 363발화는 post-MFA 미정렬이다. 보존 DB는
  `D:\mfa_tmp\2020\2020.db`, checkpoint marker는
  `D:\mfa_eojeol\done\2020.direct_db_ready`다.
- 2020 결합 제외 계약 2,250건을 확정했다. pre-MFA 1,887건과 보존 DB의 정확한
  post-MFA 미정렬 ID 363건(청취 불가 3 + `mfa_alignment_missing` 360)을
  결합했으며, 전수 MFA 재실행 없이 같은 DB에서 export하도록 동결했다.
- 2020 최종 6-tier 868,187개와 동반표를 보존 DB에서 export했다. 독립 전수 감사와
  DB 재생성 표본 24/24 semantic·byte exact-match를 통과했다.
- 연구자가 24개 생산 표본에서 WAV·LAB·TextGrid 동일 발화, 정렬의 전반적 타당성,
  6개 tier 및 검색 정보의 이해 가능성을 확인했다. 이는 인프라 QC이며 실제 음운
  실현 판정은 수행하지 않았다.
- 2020 Gate B는 2026-08-03에 16/16 core check, 실패 0으로 `passed`였으며
  `allow_remaining_years=true`다.

## 실제 미완료

- 2022–2025 검색표. 2021 검색표와 frozen source contract는 완료됐다.
- 2021–2025 신규 r2 MFA. 2021 정렬 계산은 2026-08-04 20:53:45 KST에
  exit 0으로 완료됐고 보존 DB·계산 checkpoint도 생성됐다. post-MFA
  exact-ID 대조에서 535건(`mfa_alignment_missing` 511,
  `mfa_feature_generation_failed` 24)을 분리했다. 연구자 `ari30`은
  21:35 KST에 535건의 기술적 제외·후속 회수 보존을 명시 승인했고,
  24개 WAV/LAB 청취는 2021 최종 Gate 전으로 유예했다. 승인·DB
  identity preflight는 통과했으며, 아직 6-tier export는 시작하지 않았다.
  2022–2025는 아직 시작하지 않았다.
- 7표+4표 최종 join/Parquet·DuckDB view.
- 우리말샘 1:N 보조표 연결. reference 4종은 2026-07-24 D: 회수 기록이
  있으므로 사용 직전 실물·SHA를 다시 확인한다.

2020 CSV–WAV 복구는 더 이상 미완료 항목이 아니다. 2026-08-02 10:24 KST에
파생 WAV 868,603건, E: ZIP 128개+누락 manifest 1개, 제외 이월 1,834건으로
최종 계약이 `passed`였다.

## workflow reset 판정

- 외부 리뷰 원문은 보존했다.
- 최종 판정은 `GO AFTER SMALL WORKFLOW FIXES`다. 원문 리뷰의
  “코드 수정 없이 GO”는 2020-only 범위와 Gate B가 기본 큐에 연결되지 않은
  사실 때문에 수정했다.
- 폐지: 구 4-tier 60행 잔여 검토, 12발화 utterance_search 재검토,
  5-tier phoneme 수용 검토, difference inventory 반복.
- 통합: 6-tier mini pilot 육안 검토는 2020 첫 생산 표본 검토에 흡수한다.
- 새 파일럿·설계 리뷰는 생산 계약이 실제로 바뀔 때만 다시 연다.

## 현재 안전 정지점

2020 신규 정렬·6-tier export·동반표·독립 감사·24개 생산 표본 연구자 확인·
Gate B가 모두 완료됐다. 최종 TextGrid는
`D:\20_AUDIO\08_textgrid_research_v2_staging\2020`의 868,187개다. 동반표는
utterance 868,187, word 4,973,795, phone 19,101,192, excluded 2,250행이며,
독립 감사의 하드 실패는 0이다. Gate B 보고서는
`outputs/reports/GATE_B_2020_TO_2021.json`, core 보고서는
`outputs/reports/GATE_B_2020_core.json`이다.

연구자는 공식 24개 표본을 모두 검토해 같은 발화, 정렬 대체로 맞음, 6개 tier
정상, 검색 정보 이해 가능으로 승인했다. 승인 기록은
`outputs/reviews/mfa_production_2020_mfa_r2_prod_2020_export_20260803/04_RESEARCHER_APPROVAL.json`이며
`allow_next_year_mfa=true`, `realization_judgment_performed=false`다.

육안상 일부 경계가 없어 보인 네 표본도 실제 TextGrid 값을 확인했다. 모든 tier는
빈 interval을 포함해 0–xmax를 연속적으로 덮고, 세 검색 tier의 유표 span은
`words`의 유표 span과 정확히 같다. 발화 시작·끝이 파일의 0초 또는 xmax와
일치하면 Praat에서 별도 내부 세로선이 보이지 않을 뿐이다. 이는 시간정보 손실이나
검색 결함이 아니다. 생산 source time과 파일 가장자리 경계를 유지하며 인공 내부
경계를 추가하지 않는다.

현재 안전 정지점은 **2020 Gate B 통과, 2021 `morph_search.v3` 7표와 frozen
source contract 완료, 2021 MFA 정렬 exit 0, 보존 DB checkpoint 완료,
post-MFA exact-ID 후보 535건 기술적 제외 승인·export 재개 전**이다. 2021 DB는
`D:\mfa_tmp\2021\2021.db`, marker는
`D:\mfa_eojeol\done\2021.direct_db_ready`다. 정렬·DB 계산을 다시
실행하지 않는다.
5개년 4,232,919발화 중 실패 세션 전 행과 gate 통과
세션의 실제 issue, 빈 참조, 시간 불가능을 합친 112,292개가 연구자 승인 제외이며
안전 본체는 4,120,627개다. 승인 범주는 `audio_pairing_unresolved`,
`empty_reference_unresolved_symbol`, `text_duration_impossible` 세 가지다. 이는
삭제가 아니라 안전 본체에서 분리하는 계약이며 음원 회수 가능분은 동일 모델의
후속 shard로 처리한다. 현재 535건은 이 pre-MFA 제외와 다른
기술적 post-MFA 미정렬 집합이며 자동 승인하지 않았다. 연구자가
이 집합을 승인했으며 청취 검토는 2021 최종 Gate에 결합한다. 상세 과정은
`docs/WORK_HISTORY_2026-08.md`, 실행 명령은
`docs/RUNBOOK_production_2020_2025.md`만 정본으로 사용한다.

2021–2025의 완성된 `morph_search.v3` 7표는 현재 1/5년이다. 2021은
2026-08-04 08:24:33 KST에 시작해 42개 shard를 checkpoint 방식으로 처리했고,
09:45:45에 연간 7표와 source contract를 완료했다. 연간 master는 1,373,920발화다.
독립 검증에서 source contract 12/12 check가 통과했으며, 연간 manifest는
`all_shards_success=true`, `duplicate_utt_id=0`, `deterministic_gzip_mtime=0`,
`orth_symbol_coverage_equal=true`였다. 첫 실행 구간은 09:24:49까지 1시간 이상
집중 모니터링했고 오류·재처리·정체 없이 39/42 shard까지 진행됨을 확인했다.
근거 보고서는 `outputs/reports/SOURCE_CONTRACT_morph_search_v3_20260801_2021.json`과
`outputs/reports/VERIFY_SOURCE_2021_after_morph_search.json`이다. 이 표는 MFA 입력용
search master와 달리 연구자가 형태소·표기 환경을 조합 검색하는 최종 pre-MFA
층이다. 각 연도 MFA 전에 `prepare_production_year_before_mfa.ps1`로 생성·재개하고
source contract를 확정한다. MFA 시작기는 해당 연도 manifest 성공이 없으면
fail-closed한다. 현재 값은 `show_production_year_pre_mfa_status.ps1 -Year 2021`로
확인하며 문서의 관측 시점 숫자보다 이 상태판을 우선한다.

2021 진입 전 저장소 정리에서 2020 완성 자산은 보호한 채 구 문서 3개, 구 코드
13개, 완료 파일럿 5폴더를 archive했다. 이동 전후 파일럿의 파일 수·바이트·트리
SHA가 같았다. 근거는
`docs/archive/ARCHIVE_MANIFEST_pre_2021_20260803.md`다.

외부 작업공간도 정리했다. 기존 E: archive를 대조한 결과 구 2021 TextGrid·DB와
구 2021–2025 `06_textgrid_merged`는 이미 검증 보관·D: 정리 완료 상태였다. 남아
있던 구 2021 활성 로그·완료표시·입력계약 9개(4,208,271 bytes)는
`E:\READ_ONLY_ARCHIVE\2026_summer_research\pre_2021_active_state_20260803`에
7-Zip test와 SHA-256 검증 후 보관했고 활성 사본은 0개다. 기존 2021 `.lab`은
재사용 입력으로 보존했지만 구 완료표시는 제거했으므로, 새 2021 실행에서 전수
재검증된다. 2021–2025 새 정렬 결과 폴더는 아직 0개다.

2021 진입 재확인 중 Gate B wrapper의 구 queue 기본값을 발견해 최종 2020 생산
queue `mfa_r2_prod_2020_export_20260803` 하나만 허용하도록 고정했다. 구 ID는
canonical 보고서를 변경하기 전에 거부되며, 최종 queue로 Gate B 16/16과
`allow_remaining_years=true`를 다시 확인했다. 이 점검에서 2021은 시작하지 않았다.

현행 제외 검토 root는
`outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_safe_body_2021_2025_20260803`다.
행 단위 duration issue만 제외한 최초 queue는 session gate 실패 세션 안의
우연 일치를 안전 발화로 남길 수 있어 실행 정본에서 제외했다. 현행 queue는 실패
세션 전 행을 격리하고 원본 WAV/CSV를 바꾸지 않는다. 2021–2025 후보 수는 각각
1,488 / 1,231 / 103,930 / 1,610 / 4,033이다. 2026-08-04 10:02 KST에
연구자 `ari30`이 세 범주를 명시 승인했으며 자동 승인은 0건이다. 각 연도
`04_RESEARCHER_APPROVAL.json`과 `approved_exclusions.json`은 후보 CSV의 SHA와
입력 계약 ID에 결속돼 있다. 승인 생성은 MFA를 시작하거나 WAV/LAB를 변경하지
않았다.

승인 뒤 실제 MFA queue는 연도별로 분리한다.
`mfa_r2_prod_safe_body_<YEAR>_20260803`이며 각 queue는 정확히 한 연도만
처리한다. 2022–2025는 직전 연도의 source contract, 보존 DB, 6-tier·동반표
독립 전수 감사, DB 표본 동등성, 최소 5세션 연구자 인프라 승인을 결합한 gate가
통과해야 시작할 수 있다. 재개 전 기존 queue state는 SHA-256 검증 history로
보존한다.

2021 실행 전 최종 `-PreflightOnly`는 2026-08-04 10:11 KST에 `GO`였다.
2020 Gate B, 2021 source contract, 승인 제외 1,488건, 공통 Jamo r2·109-phone,
동결 음향모델, D: 여유, PowerShell 안전·호환성 검사와 Python 329개 테스트가
통과했다. 이 관측 자체는 MFA를 시작하지 않았고, 그 직후 사용자 일반
PowerShell에서 2021 장시간 실행 명령을 시작했다.

2021 장시간 실행은 10:23:36 KST에 시작됐고 4,143개 세션·1,373,920행의 LAB
전수 검증을 완료했다. MFA 계산에 들어가기 전 입력감사가 승인 계약 1,488건 중
활성 WAV+LAB 1,089쌍이 실제 입력에서 분리되지 않은 구현 누락과, 원본 CSV
분절시간이 `0.0`인 추가 14건을 발견해 10:49:01에 fail-closed했다. MFA DB와
TextGrid는 생성되지 않았고 원본 WAV/CSV, 2020 완성본은 변경되지 않았다.
실패 queue는 `mfa_failed_checkpoint_preserved`로 보존했다.

재발 방지를 위해 승인된 `alignment_and_analysis` 발화는 원본 WAV/CSV를 그대로
둔 채 파생 LAB만 계약별 폴더에 SHA 검증 후 가역 보존하도록 수정했다. 승인 계약
SHA도 `alignment_contract_id`에 포함해 제외 목록이 달라지면 과거 temp/DB를
재사용하지 못한다. 중단 재개, active/archive 이중 존재 차단, 계약 불일치,
CSV duration 0 후보화와 immutable 후보표 병합을 단위시험으로 검증했다.

기존 1,488행 승인 snapshot은 변경하지 않았다. 새 root
`outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_safe_body_2021_v2_20260804`
에는 기존 1,488건과 새 `csv_duration_invalid` 14건을 합친 **pending 1,502행**이
있다. 새 14건은 `audio_pairing_unresolved`로 안전 본체에서 분리하고 동일 모델의
후속 shard에서 회수 여부를 다룰 후보이며 자동 승인하지 않았다. 연구자 `ari30`은
11:21 KST에 14건을 명시 승인했고, 기존 승인과 결합한 1,502행 계약 SHA는
`ca60cbd3111a4c6d120229d7822e536ea41fe8d6bad0b08f8126cfb429d1f356`이다.
코드·승인 증거 커밋과 새 queue preflight 전까지는 재실행하지 않았으며, 구
queue ID는 앞으로도 재사용하지 않는다.

수정·승인 증거는 커밋 `05078a3`으로 원격에 푸시했다. 새 approval/execution
queue ID `mfa_r2_prod_safe_body_2021_v2_20260804`의 `-PreflightOnly`는
2026-08-04 11:27 KST에 최종 `GO`였다. 승인 1,502행, 2020 Gate B, 2021 source
contract, 공통 Jamo r2·109-phone, D: 322.9GiB, Python 335개, PowerShell 5.1
안전·호환성 검사가 통과했다. 이 관측에서는 MFA를 시작하지 않았다. 다음 동작은
RUNBOOK에 기록한 새 ID의 2021 단일 연도 명령이며, 구 queue ID를 재사용하지 않는다.

2021 v2 queue는 2026-08-04 11:42:13 KST에 실제 시작됐다. 승인 제외 1,502건은
파생 LAB 가역 보관 1,103건과 활성 LAB 없음 399건으로 모두 적용됐다. 원본
WAV/CSV와 2020 완성본은 변경하지 않았다. 승인 반영 뒤 전수 입력감사는 검색
1,373,920행, 안전 본체 1,372,418건, 승인됐으나 활성인 쌍 0, duration 잔여
불일치 0으로 analysis/execution gate를 모두 통과했다. 입력 계약은
`1bda84ba0ce02fed685991f1da0dff3b75577fffa07b05b971293f8c189fe0f8`, 정렬 계약은
`5ff1865744c85d982fc43708d7666f9af061cad833aa7fde04a09bef3238d5dd`다.

실제 MFA는 12:07:23부터 공통 Jamo r2·동결 음향모델·`num_jobs=4`로 실행했고
20:53:45에 exit 0으로 정상 종료됐다.
11:42–12:42 첫 실행 구간 집중 점검에서 하트비트·CPU가 계속 증가했고 오류·watchdog
중단 신호가 없었다. setup 초기 메모리 경고는 일시적이었으며 최대 commit 65.8%에서
개입 없이 해소됐다. 근거는
`outputs/reports/MONITOR_2021_mfa_first_hour_20260804.json`이다. 최종 heartbeat는
`watchdog_killed=false`, alignment error 0, processed 1,372,394,
word·phone interval 모두 있는 ID 1,371,883을 기록했다. 현재 명령을 중복
실행하지 않으며, 2021 6-tier·동반표·독립 감사·DB 표본·연구자 표본 승인이
끝나기 전에는 2022를 시작하지 않는다.

후속 setup 감시에서 MFA가 보고한 4,143 speakers는 source session 수와 정확히
일치했다. 1,416,216 files는 입력감사의 WAV 수이며, search master 밖 WAV-only
42,296개가 포함된 값이다. 예상 밖 활성 LAB는 0이므로 결과 정합성 문제는 없고
초기 I/O 비용만 있다. 2021 입력은 실행 중 바꾸지 않는다. MFCC 구간은
12:54:37–13:56:42에 오류 없이 완료돼 `Calculating CMVN`으로 전환됐다. 근거는
`outputs/reports/MONITOR_2021_mfa_mfcc_to_cmvn_20260804.json`이다. 2022 전에
safe-body corpus view 최적화를 검토할 수 있지만, 이를 새 연구 gate로 삼지는
않는다.

MFA 종료 후 12.7GB DB 계산 checkpoint를 재검증했고
21:08:22에 `2021.direct_db_ready`를 생성했다. direct exporter의 전수
exact-ID 대조는 source 1,373,920, active LAB 1,372,418, DB 1,372,394,
aligned 1,371,883을 교차 비교했다. 다른 hard mismatch는 0이고,
`unknown_active_lab_without_alignment` 535건만 분리해 안전 중단했다.
검토 패키지는 535건을 `mfa_alignment_missing` 511건과
`mfa_feature_generation_failed` 24건으로 구분했고, 20건 후보+4건 정상
대조군 WAV/LAB 표본을 생성했다. 자동 승인은 0건이며 연구자 승인
후에만 같은 DB에서 export를 재개한다.

## 활성 정본

### 2021 post-MFA 재개 계약 교정

21:35 KST에 연구자 `ari30`이 post-MFA 535건을 기술적 제외로 명시 승인했다.
pre-MFA 1,502건과 결합한 export/QC 계약은 2,037건이다. 첫 재개 시도는 이
결합 계약을 정렬 계약에도 사용해 alignment identity를 `5ff186…`에서
`11e9f6…`로 바꾸려 했기 때문에, `direct_db_ready` 계약 불일치 gate에서
파일 생성·MFA 재실행 전에 안전 중단됐다. DB와 2020 완성본은 그대로다.

현행 수정은 정렬 provenance 계약(기존 1,502건)과 export·감사 계약(결합
2,037건)을 별도 인자로 전달한다. 일반 신규 연도는 두 인자가 동일해 기존
계약이 바뀌지 않는다. 2021은 회귀시험·새 execution queue preflight 후 같은
DB에서 export만 재개하며, 유예한 24표본 청취와 최종 Gate 전에는 2022를
시작하지 않는다.

교정 커밋 `5331e53`은 원격에 푸시됐다. 새 queue
`mfa_r2_prod_safe_body_2021_v2_20260804_postmfa_v2`의 `PreflightOnly`는
export/QC 2,037건과 정렬 1,502건을 별도로 검증해 `GO`였다. 1,502건으로
재구성한 alignment ID도 보존 DB marker의 전체 SHA-256 `5ff1865744c85d…`와
exact match이므로, 실제 재개에서 전수 MFA를 다시 계산할 이유가 없다.

- 문서 색인: `docs/README.md`
- 현재 상태: 이 문서
- 생산 실행: `docs/RUNBOOK_production_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 결정 색인: `docs/decisions/_INDEX.md`
- 스크립트 색인: `scripts/SCRIPTS_INDEX.md`

2021 post-MFA v2 재개는 2026-08-04 22:13 KST에 시작됐다. LAB 1,371,883건은
신규 생성·불일치 재작성 없이 전수 일치했고, 정렬 provenance 계약은 보존 DB와 같은
`5ff1865744c85d982fc43708d7666f9af061cad833aa7fde04a09bef3238d5dd`로 복원됐다.
22:42 KST 실행 입력 감사가 보존 DB 승인 ID 511건을 모두 활성 WAV+LAB 쌍이어야 한다고
잘못 요구해 export 전에 안전 중단했다. 원본, 2020 완성본, 2021 DB와 checkpoint는
변경되지 않았다. 감사 조건은 승인된 ID가 이미 비활성인 경우를 안전 상태로 인정하되
미승인 활성 쌍은 계속 차단하도록 교정했고, Python 340개 및 Windows PowerShell 5.1
안전 46파일·호환성 55스크립트 검사를 통과했다. 다음 실행은 새 queue ID로 동일 DB에서
입력 감사를 다시 수행한 뒤 direct 6-tier export만 재개한다.
