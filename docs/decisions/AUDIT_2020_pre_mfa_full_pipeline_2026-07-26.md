# 2020 pre-MFA·MFA 전 단계 완료 및 병목 감사

작성일: 2026-07-26

대상 run: `pre_mfa_v1_20260725`

실행 기준 Git: `195d71f377993dedd6dab4fae4133682b74fb576`

판정: **2020 파이프라인 단계 완료, 2021–2025 미시작**

## 1. 이 완료가 연구에서 뜻하는 것

연구 흐름은 다음과 같다.

1. 형태소·표기 환경을 CSV에서 검색해 후보 발화를 고른다.
2. 해당 WAV와 TextGrid를 모은다.
3. KOINA 운율 분석을 결합한다.
4. 연구자가 WAV와 TextGrid를 직접 보고 실현 여부를 판정한다.

MFA `phones` tier는 대략적인 시간 분절이며 실현 여부의 자동 판정값이
아니다. 이번 완료는 이 연구를 위한 **검색·자료연결·시간정렬 인프라**를
2020 한 연도에서 처음부터 끝까지 통과시켰다는 뜻이다.

“2020 100% 완료”는 모든 파이프라인 단계가 완료됐다는 뜻이지, 모든
발화가 정렬됐다는 뜻은 아니다. usable lab 869,840개 중 866,196개가
정렬됐고 3,644개는 기본+retry beam에서 정렬되지 않았다.

## 2. 실행 정체성과 불변 자료

| 항목 | 값 |
|---|---|
| wrapper 실행 | 2026-07-25 13:23:06 → 2026-07-26 18:23:30 |
| pre-MFA CSV | `D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725` |
| 2020 최종 staging | `D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2020` |
| 기존 정본 | `D:\20_AUDIO\06_textgrid_eojeol` — 자동 승격·덮어쓰기 없음 |
| MFA state | `D:\mfa_eojeol` |
| 2020 입력계약 | `fa96caf4a37c556b929febbfa172500b2dfe615cfb554e816b070766bc8b3038` |
| 2020 align marker | `D:\mfa_eojeol\done\2020.align_done` |
| 2020 merge marker | `D:\mfa_eojeol\done\2020.merge_done` |
| 병합 보고서 | `D:\mfa_eojeol\logs\merge_report_2020_eojeol_g2p_2020_20260725_140554.json` |

원자료, 기존 CSV 정본, 기존 TextGrid 정본은 수정하지 않았다. 새 결과는
staging에만 기록됐고 `merge_done`에도 `promotion_required=true`가
명시돼 있다.

## 3. 완료 증거 사슬

| 단계 | 증거 | 판정 |
|---|---|---|
| pre-MFA CSV | build meta `status=success`; 5,103,356발화·17,156세션 | 통과 |
| CSV 핵심 일치 | `meta_missing=0`, `json_missing=0`, `eojeol_mismatch=0`, `dialogue_link_error=0` | 통과 |
| 2020 lab 계약 | `2020.lab_input_done.json`; 계약 ID 일치 | 통과 |
| MFA usable 입력 | lab 869,840 | 기준 |
| MFA 정렬 | TextGrid 866,196 / lab 869,840 = 99.58% | 99% gate 통과 |
| align marker | 2026-07-26 16:28:54, 계약 ID·수량 일치 | 통과 |
| 4-tier 병합 | source 866,196, created 866,196, failed 0 | 통과 |
| 형태소·form 결합 | `morpheme_tier_missing=0`, `form_missing=0` | 통과 |
| merge marker | 2026-07-26 18:12:14, 계약 ID 일치 | 통과 |
| 독립 전수 열거 | TextGrid 866,196, 0바이트 0, 2,231세션 | 통과 |
| tier 경계 표본 | 5개 균등 세션 × 처음·중간·끝 3개 = 15개, 실패 0 | 통과 |
| 2021 미진입 | temp/output/staging/done marker 모두 없음 | 통과 |
| 실행 종료 | lock 없음, MFA/Python 없음, 중간 output 정리됨 | 통과 |

병합 writer는 866,196개 모두에 대해 쓰기 전에 다음을 전수 검증했다.

- tier 순서: `words`, `phones`, `morphemes`, `utterance`
- 전체 duration 일치
- interval이 0 미만이거나 duration을 넘지 않음
- words·phones·utterance가 비어 있지 않음
- 임시파일 검증 뒤 원자적 승격

`interval_tier()`는 각 tier 앞의 빈 구간을 0초부터 채우고 뒤의 빈 구간을
전체 duration까지 채운다. 독립 표본 15개에서도 모든 tier의 시작=0,
끝=duration, 내부 공백·겹침 없음이 확인됐다.

## 4. 시간과 자원 실측

| 단계 | 시간 | 관찰 |
|---|---:|---|
| pre-MFA CSV build | 약 42분 | 510만 행 |
| 2020 lab 계약 검증 | 약 12분 | 기존 852,674 검증, 17,176 변경 반영 |
| MFA setup·G2P·MFCC·graph | 약 7시간 27분 | MFCC 오류 0 |
| 실제 alignment | 약 1시간 7분 | 4 jobs |
| phone/word interval 수집 | 약 1시간 37분 | DB 수집 |
| TextGrid export | **약 15시간 57분** | 사실상 worker 1개 |
| 4-tier 병합 | 약 1시간 43분 | 866,196개, 약 140파일/초 |
| MFA 중간파일 정리 | 약 11분 | 소형파일 대량 삭제 |
| wrapper 전체 | 약 29시간 | 2020 완료 후 의도적 pause 포함 |

D: 여유는 시작 333.3GB에서 최저 약 299.1GB까지 내려갔다가 temp와
MFA 중간출력 정리 후 319.0GB로 회복했다. 용량 부족은 없었지만,
2021은 2020보다 크므로 성능·보존 정책을 먼저 고치는 것이 타당하다.

## 5. 가장 중요한 병목과 개선 우선순위

### P0 — 2021 전에 반드시 처리

#### EXPORT-002: export worker가 사실상 1개만 생존

- 2020 export가 약 15시간 57분으로 MFA 전체 시간의 가장 큰 비중을
  차지했다.
- DB에는 4 job이 있고 MFA 코드는 약 217,540파일씩 4 batch와 4 worker를
  의도하지만, 실제 하위 Python export worker는 PID 23616 하나만
  처음부터 끝까지 처리했다.
- 대형 `multiprocessing.Queue`에 batch를 넣은 뒤 고정 1초 후
  `finished_adding`을 세우고 worker가 1초 `Empty`에서 종료하는 경쟁
  조건이 유력하다. 아직 재현 실험 전이므로 확정 원인으로 쓰지 않는다.

개선:

1. sentinel/ack 기반 queue 종료로 바꾼다.
2. worker별 시작·batch 수신·완료를 JSONL로 기록한다.
3. 1만·5만·20만 파일 파일럿에서 worker 1/2/4의 수량·해시·시간을 비교한다.
4. 출력 수량과 실패 ID가 동일한 경우에만 전량에 적용한다.

#### QC-ALIGN-001: 난정렬 3,644개를 ID로 고정

- 전체 재실행 대상이 아니다.
- usable lab basename − staging TextGrid basename 차집합을 전수 계산해
  `outputs/tables/2020_mfa_missing_textgrid_ids_20260726.csv`로 고정했다.
- lab ID 869,840, TextGrid ID 866,196, 차집합 3,644, 반대 차집합 0,
  중복 ID 0이다. 3,644건 모두 WAV가 존재한다.
- 215세션에 분포하며 최다 세션은 `SDRW2000000257` 205건이다.
- 기본 실패를 세션·길이·문자유형·화자별로 층화해 확대 beam 격리
  재시도를 수행한다.
- 회수본은 원 staging을 직접 덮지 않고 별도 residual staging에 둔다.

#### PAUSE-001: 정상 일시정지가 `failed`로 기록됨

- 현재 wrapper는 `paused` 상태를 몰라, 사용자 요청에 따른 2021 차단
  exit 75를 raw summary에서 `failed`로 기록했다.
- `-PauseAfterYear 2020` 정식 옵션과 `status=paused`,
  `paused_after_year`, `resume_years`를 추가해야 한다.
- run별 emergency pause 파일은 유지하되 wrapper가 exit 75를 정상
  제어 상태로 해석해야 한다.

#### MFA-RAW-001: 성공 뒤 원 MFA TextGrid와 temp가 자동 삭제됨

- 최종 4-tier staging에는 words·phones 시간정보가 그대로 보존돼 있어
  연구용 MFA alignment는 확보됐다.
- 다만 원 2-tier MFA 파일과 alignment DB의 bit-for-bit 보존본은 없다.
- 이후 연도에서는 merge/QC 승인 전 원 MFA output을 지우지 않거나,
  run별 무압축 tar+SHA-256 manifest를 만든 뒤 디렉터리를 정리하는
  정책을 검토한다.

### P1 — 안전성과 관찰성 개선

#### MON-001: 영구 heartbeat와 하위 단계 로그 부족

- stderr는 export 시작·종료만 보여 주고 50,000개 청크 진행을 남기지
  않았다.
- wrapper transcript에도 하위 PowerShell/Python의 세부 출력이 충분히
  남지 않았다.

개선:

- 단계, 연도, PID, CPU 누적, batch/청크, 출력 누적, D: 여유를
  append-only JSONL heartbeat로 1분마다 기록한다.
- parent·child stdout/stderr를 run ID가 있는 로그로 tee한다.
- 30분 정체 판정은 CPU·I/O·queue ack를 함께 사용한다.

#### MON-003: 감시 전수 열거가 본 작업과 경쟁

- 약 20만 파일부터 `Get-ChildItem -Recurse | Sort-Object`가 120초
  timeout됐다.
- `.NET EnumerateFiles`와 `rg --files`도 export 부하 중에는 timeout됐다.

개선:

- 생성기가 chunk 완료마다 누적 수량을 manifest에 기록한다.
- 감시기는 전수 디렉터리 열거를 하지 않고 manifest만 읽는다.
- 독립 전수 열거는 연도 완료 gate에서 한 번만 수행한다.

#### MERGE-001: 단일 프로세스 4-tier 병합

- 866,196개에 6,188.807초, 약 140파일/초였다.
- export보다 작지만 2021 규모에서는 약 2시간 45분 수준으로 늘 수 있다.

개선:

- 세션 단위 worker pool을 사용하되 파일별 staged write와 원자적 승격을
  유지한다.
- worker별 report를 합쳐 `created+skipped+failed=source_total`을
  중앙 gate에서 검증한다.

#### CLEANUP-001: 86만 소형파일 삭제에 약 11분

- 병합 성공 뒤 `D:\mfa_eojeol_out\2020` 정리가 wrapper를 붙잡았다.

개선:

- 완료 원출력을 run별 `cleanup_pending`으로 원자적 rename한 뒤 wrapper는
  즉시 끝내고, 별도 저우선순위 cleanup이 삭제한다.
- QC 보존 정책이 결정되기 전에는 자동 삭제하지 않는다.

## 6. 데이터 품질 후속 항목

| ID | 수량 | 의미 | 최소 재처리 |
|---|---:|---|---|
| `CSV-001` | speaker missing 1,767 | 원 JSON/metadata 화자 ID 점검 | 해당 CSV 행·세션 |
| `PRON-001` | full 55,198 / 2020 6,214 | 기호·숫자·미해결 발음 근거 | 발음 열과 lab만 |
| `PRON-002` | 2020 53 | empty reference form | 해당 발화만 |
| `AUDIO-001` | 2020 544 | search 행에 WAV 없음 | 오디오 inventory 해당 ID |
| `AUDIO-002` | 318 | audio 870,158 − usable lab 869,840 | ID 교차표 |
| `SESSION-001` | 1세션 | search 2,232 − MFA 2,231 | 해당 세션 |
| `ALIGN-001` | 3,644 | 기본+retry beam 난정렬 | residual MFA만 |

이 항목들은 서로 겹칠 수 있으므로 각각을 더해 총 누락이라고 해석하면
안 된다. ID 단위 교차표를 만든 뒤 원인을 배타적으로 분류해야 한다.
`ALIGN-001`은 이번 차집합 inventory로 ID가 확정됐으며, 3,644건 모두
WAV가 있어 `AUDIO-001`과는 구분된다.

## 7. 단계별 최소 재실행 원칙

| 문제 | 처음부터 다시 할 필요 없는 시작점 |
|---|---|
| 화자·발음 CSV 열 수정 | search master 해당 세션/행 → 해당 lab |
| WAV 누락 복구 | 해당 ID inventory → 해당 lab/MFA |
| 3,644 난정렬 | residual corpus → 확대 beam MFA |
| tier 라벨·경계 표시 변경 | 현재 4-tier staging을 입력으로 파생본 생성 |
| export 병렬화 | 보존된 작은 temp 파일럿 또는 새 소규모 corpus |
| KOINA 결합 | 검증된 4-tier staging과 WAV를 ID로 join |

MFA phones는 실현 판정값이 아니므로, phones를 이용한 자동 음운현상
판정으로 범위를 넓히지 않는다.

## 8. 2021 재개 전 gate

1. export worker 경쟁 조건 재현·수정·파일럿 benchmark
2. `paused` 상태와 `-PauseAfterYear` 정식 구현
3. 원 MFA output 보존/정리 정책 결정
4. 3,644 실패 ID와 318/544/53건의 교차 inventory 생성
5. 2020 4-tier 인간 표본 검토
6. 2021 한 연도만 별도 RunId로 실행
7. 2021 완료 gate 통과 뒤에만 다음 연도 진행

## 9. 원시 증거와 기록

- 최종 점검대장:
  `docs/decisions/MONITOR_pre_mfa_bulk_pre_mfa_v1_20260725.md`
- wrapper raw summary:
  `logs/pre_mfa_bulk_pre_mfa_v1_20260725_latest.json`
- wrapper transcript:
  `logs/pre_mfa_bulk_pre_mfa_v1_20260725_20260725_132306.log`
- MFA stderr:
  `D:\mfa_eojeol\logs\mfa_2020_stderr.log`
- align marker:
  `D:\mfa_eojeol\done\2020.align_done`
- merge marker:
  `D:\mfa_eojeol\done\2020.merge_done`
- merge report:
  `D:\mfa_eojeol\logs\merge_report_2020_eojeol_g2p_2020_20260725_140554.json`
- 실행 전 코드 archive:
  `archive/code_pre_bulk_20260724`
- 실행 코드 기준:
  Git `195d71f377993dedd6dab4fae4133682b74fb576`
- 난정렬 ID CSV/JSON:
  `outputs/tables/2020_mfa_missing_textgrid_ids_20260726.csv`,
  `outputs/tables/2020_mfa_missing_textgrid_ids_20260726.json`
