# 결정: MFA r2는 음운 실현 판정이 아닌 인프라 수용 파일럿을 먼저 통과한다

- 날짜: 2026-07-30
- 상태: 기계 검증 완료, 연구자 인프라 검토 대기
- 범위: 2020–2025 공통발음사전 MFA r2의 본작업 직전 소규모 검증

## 연구 흐름

현재 구축하는 것은 구체적인 음운 현상의 실현 여부를 자동 판정하는 체계가
아니다. 연구 단계에서는 검색 CSV에서 형태소·표기 환경 후보를 찾고, 대응하는
WAV와 TextGrid를 모은 뒤 KOINA 등 운율 정보를 결합하고, 연구자가 음성과
TextGrid를 직접 확인해 실현 여부를 판정한다.

따라서 이번 파일럿의 질문은 “ㄴ 삽입이 실현되었는가”가 아니라 다음과 같다.

1. CSV의 발화 ID·화자·세션·어절 정보로 WAV와 TextGrid를 안정적으로 찾는가?
2. 공통발음사전 r2와 고정 음향모델이 6개 연도에 같은 방법 계약으로 쓰이는가?
3. 4-tier TextGrid의 구조·처음/끝 경계·출처가 후속 검색과 수동 판정에
   충분한가?
4. DB와 최종 TextGrid가 재현 가능하게 연결되는가?
5. 연구자 검토 파일을 한 폴더에서 혼동 없이 사용할 수 있는가?

`phones` tier는 MFA 정렬·탐색을 위한 보조 분절이다. 실제 음운 실현의 판정값으로
사용하지 않는다.

## 파일럿 표본

- 연도: 2020–2025
- 연도당: 10발화
- 연도당 실제 화자: 5명
- 화자당: 2발화
- 연도당 서로 다른 세션: 5개
- 선택 seed: `mfa_r2_infrastructure_pilot_v1`
- WAV/검색 CSV 길이 대응이 불량한 세션은 사유를 기록하고 제외한다.

## 입력 계약

- LAB 정본 필드: 동결 pre-MFA 검색 마스터의 `pron_reference_form`
- 구 `form`으로 LAB을 만드는 파일럿 경로는 사용하지 않는다.
- 숫자·기호·외국어 전용 원문 어절이 MFA LAB에서 제외될 때
  `source_eojeol_index → mfa_word_index` 대응표에 `null`로 명시한다.
- 선택된 세션 CSV는 파일별 SHA256과 aggregate SHA256으로 동결한다.

## MFA 방법 계약

- 공통사전 release:
  `common_pron_mfa_r2_20260728`
- 발음 모드:
  `common_pron_mfa_r2_latest_jamo`
- 공통사전 SHA256:
  `24c406604c86a5df833a7e47d809f252d6fc39dc566a6d3818b3d3ffeb04fb86`
- 고정 음향모델 SHA256:
  `94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c`
- Jamo G2P 모델은 공통사전 생성 근거로 계약에 남기지만 정렬 실행 중
  inline G2P는 사용하지 않는다.
- 연도별 관측 phone 집합은 코퍼스 내용에 따라 달라도 된다. 방법론적 동일성은
  같은 허용 phone inventory와 그 SHA, 같은 모델·사전·런타임 계약으로
  증명한다.
- `spn` interval, 허용 inventory 밖 phone, 계약 불일치는 실패다.

## 출력과 tier 출처

MFA의 대량 raw TextGrid export는 생략하고 SQLite DB에서 최종 4-tier를 직접
만든다.

| tier | 출처 | 역할 |
|---|---|---|
| `words` | MFA word intervals | 어절 정렬과 탐색 |
| `phones` | MFA phone intervals | 정렬·탐색 보조 |
| `morphemes` | 기존 `06_textgrid_merged`의 words 경계 | 형태소 위치 보조 |
| `utterance` | 동결 검색 마스터의 `form` | 발화 전사와 ID 연결 |

모든 tier는 0–xmax 범위를 빈 interval까지 포함해 연속적으로 덮어야 한다.
DB→TextGrid 재수출 표본이 tier payload와 일치해야 한다.

## 저장 구조

대형·임시 실행 구조는 D:에만 둔다.

```text
D:\mfa_eojeol\pilots\r2_infrastructure\mfa_r2_infra_pilot_20260730
```

사용자 검토본은 모든 기계 gate 통과 뒤 Dropbox의 한 폴더에 평면 구조로
만든다.

```text
C:\Users\ari30\Dropbox\MFA_R2_INFRA_PILOT_20260730
  2020__발화ID.wav
  2020__발화ID.TextGrid
  2020__발화ID.lab
  2020__발화ID.csv
  ...
  REVIEW.csv
  REVIEW.xlsx
  MANIFEST.csv
  BUNDLE_MANIFEST.json
  README.md
```

전체 코퍼스 산출물은 규모 때문에 연도·세션 폴더를 유지한다. 평면 구조는
60발화 파일럿 검토본에만 적용한다.

## 기계 gate와 연구자 gate 분리

기계 통과:

- r2 adoption과 실물 SHA 재검증
- MFA 로컬 안전 패치 검증
- 5화자·5세션 표본 균형
- 정렬 DB 존재와 10/10 4-tier export
- 4-tier 구조·경계·WAV 길이 검증
- DB↔TextGrid 세션별 표본 재수출 동등성
- 연도별 phone inventory와 `spn=0`
- 6개년 동일 방법 계약

연구자 검토:

- 같은 접두사의 WAV/TextGrid/LAB/CSV가 실제로 잘 연결되는지
- tier 구조와 경계가 Praat 검토에 편리한지
- CSV 열이 향후 형태소·표기 환경 검색과 파일 수집에 충분한지

연구자 검토에서 구체적 음운 실현은 판정하지 않는다. 파일럿의 기계 통과만으로
본작업을 자동 승인하지 않으며, 검토표의 `인프라 통과` 결정이 별도로 필요하다.

검토표 15개 열의 사용자 요청 배경·의미·출처·판정값·후속 활용은
`GUIDE_mfa_r2_infrastructure_review_columns_20260730.md`를 정본으로
사용한다.

## 2026-07-30 실행 중 발견한 보호장치 충돌

1. 숨은 PowerShell의 CP949 출력으로 IPA 문자를 출력하지 못해 첫 실행이 MFA
   전에 중단됐다. Python 표준출력을 UTF-8로 고정했다.
2. 안전 러너가 먼저 만든 `state/logs/temp`를 표본 builder가 미완료 표본으로
   오인해 두 번째 실행이 MFA 전에 중단됐다. 러너가 소유하는 정확한 제어
   항목만 허용하고 `corpus/csv/manifest` 부분 산출물은 계속 거부하도록 했다.
3. PowerShell 5.1이 MFA의 정상 stderr `INFO`를 `NativeCommandError`로
   승격해 2020 모델 적재 중 러너를 중단했다. MFA 호출 구간에서만 stderr를
   수집하고 실제 프로세스 종료 코드를 gate로 사용하도록 바로잡았다.
4. 2020 정렬은 10/10로 끝났지만 최초 direct-DB export gate가 MFA 내부
   예약 발음행 `<unk> → spn` 한 건을 실제 정렬 interval로 오인했다.
   DB를 읽기 전용으로 대조한 결과 `<unk>`, `<cutoff>`, `[bracketed]`,
   `[laughter]`의 예약 `spn` 발음은 어느 word/phone interval에도 쓰이지
   않았고 실제 `spn` phone interval은 0개였다. 따라서 gate를
   `pronunciation` 테이블의 미사용 예약행 수가 아니라 실제
   `phone_interval JOIN phone`의 `spn` 수로 교정했다. 회수 과정에서는
   이미 완료된 2020 정렬 DB를 재사용하고 export·구조 감사·DB 재수출
   동등성·phone inventory gate만 다시 실행했다.
5. 2021 phone inventory JSON은 정상 UTF-8이지만 Windows PowerShell 5.1의
   통합 stdout 로그에서 IPA phone이 CP949로 잘못 디코딩되어 깨져 보였다.
   기계 판정은 JSON 원본을 읽으므로 결과값에는 영향이 없고, 원본에서
   allowed 109·observed 46·inventory 이탈 0·실제 `spn=0`을 재확인했다.
   후속 실행 로그의 사람이 읽는 재현성을 위해 러너의 Console 및 native
   pipeline 출력 인코딩을 UTF-8로 명시했다.

네 경우 모두 원시 corpus, 공통사전, 기존 TextGrid와 Dropbox 결과를 변경하지
않았고, 재현 로그를 보존했다.

## 2020 회수 결과

- MFA 정렬: 10/10
- direct DB 4-tier: 10/10
- 4-tier 독립 구조 감사: valid 10, invalid 0
- 형태소 tier 누락: 0
- 실제 `spn` phone interval: 0
- 허용 inventory 밖 phone: 0
- DB→TextGrid 표본: 5세션 모두 tier payload 동등, 5/5 byte exact
- 허용 phone inventory: 109개,
  SHA256
  `da65d15ff9e98496b688747d268b87d77639d961d46009e1adb568088880944b`

2020은 재정렬 없이 보존 DB에서 후속 gate를 재실행해
`state\2020.machine_done.json`을 생성했다. 이 회수는 실패를 숨긴
승인이 아니라, 잘못 정의된 gate를 실제 연구 산출물의 사용 interval 기준으로
수정한 뒤 동일한 검증 사슬을 다시 통과시킨 것이다.

## 2021 결과와 2022 전환

- 2021 기계 QC: 통과
- direct DB 4-tier·독립 경계 감사·DB 재수출 표본·phone inventory:
  모두 성공 marker에 결합
- 허용 phone inventory: 109
- 관측 phone: 46
- 허용 inventory 밖 phone: 0
- 실제 `spn` phone interval: 0
- 2022 시작 시각: 2026-07-30 13:11:18 KST

연도 전환은 2021의 `state\2021.machine_done.json`이 생성된 뒤에만
일어났다. 연구자 인프라 검토는 여섯 연도의 기계 gate가 모두 통과하고
Dropbox 묶음이 생성된 뒤 수행한다.

## 2022–2023 결과와 2024 전환

- 2022 기계 QC 통과: 2026-07-30 13:26:13 KST
- 2023 기계 QC 통과: 2026-07-30 13:42:57 KST
- 두 연도 모두 실제 `spn` phone interval 0, 허용 inventory 밖 phone 0
- 2024 시작: 2026-07-30 13:42:57 KST
- 2024 진행 중 stderr 오류 0

각 연도는 직전 연도의 direct export·독립 4-tier 감사·DB 재수출 5세션·
phone inventory 보고서가 성공한 뒤에만 `machine_done` marker를 만들고
다음 연도를 시작했다.

## 2024 결과와 2025 전환

- 2024 기계 QC 통과: 2026-07-30 14:00:27 KST
- 실제 `spn` phone interval 0
- 허용 phone inventory 밖 phone 0
- 마지막 연도 2025 시작: 2026-07-30 14:00:27 KST
- 시작 직후 corpus 10발화·5화자 인식과 text normalization 통과

## 2025 결과와 6개년 교차 감사

- 2025 기계 QC 통과: 2026-07-30 14:17:04 KST
- direct DB 4-tier: 10/10
- 실제 `spn` phone interval: 0
- 허용 inventory 밖 phone: 0
- `cross_year_method_audit.json`: `status=passed`
- 기대/관측 연도: 6/6
- 연도 간 방법 계약 불일치: 0
- 동일 phone 생성 기준: 참
- 동일 허용 phone inventory와 SHA: 참
- 모든 관측 phone의 허용 inventory 밖 항목: 0

연도별 실제 관측 phone 집합 자체는 표본 어휘가 다르므로 같게 강제하지 않았다.
동일 방법론의 근거는 같은 공통사전·음향모델·입력 계약·허용 inventory와
각 연도 관측 집합이 그 inventory의 부분집합이라는 결합이다.

## 실행 중 코드 보완과 방법 동일성 범위

장기 PowerShell 프로세스는 2026-07-30 12:54 KST에 읽어 들인 러너의
제어 흐름으로 2025까지 실행했다. 실행 중 발견 사항을 후속 전수 작업에
반영하기 위해 저장소의 러너·재개 marker·로그 인코딩·패키징·검토표 gate는
보완했지만, 이미 떠 있던 PowerShell 프로세스의 연도별 정렬 제어 흐름은
바뀌지 않았다.

파일럿의 정렬 방법 동일성에 직접 관련된 다음 요소는 2020 회수 export부터
2021–2025까지 고정한다.

- 공통사전과 SHA
- acoustic model과 SHA
- inline G2P 금지
- LAB의 `pron_reference_form`과 동결 세션 CSV aggregate SHA
- direct DB 4-tier exporter의 실제 `spn` interval 기준
- 4-tier 구조·경계 감사와 phone inventory 기준

실행 중 바꾼 `verify_mfa_db_4tier_sample.py`의 내용은 input contract ID를
보고서에 추가할 수 있게 한 선택적 메타데이터 인자뿐이며, DB 재수출·tier
비교 알고리즘은 바꾸지 않았다. Dropbox 패키징과 연구자 XLSX 검증 보완은
정렬이 모두 끝난 뒤 처음 호출되는 단계다.

따라서 이 파일럿은 같은 모델·사전·정렬·export 기준의 6개년 호환성 증거로
사용하되, “6개년이 하나의 Git commit으로 실행됐다”는 근거로 과장하지 않는다.
파일럿에서 발견한 수정과 회귀시험을 모두 끝낸 최종 commit을 동결한 다음,
2020–2025 전수 MFA는 그 commit으로 수행한다.

## Dropbox 패키징 잠금과 안전 복구

60발화의 복사·SHA 검증·manifest 작성은 완료됐으나, 마지막 partial
디렉터리 승격에서 Dropbox가 폴더 handle을 잠가 `WinError 32`가 발생했다.
이 실패는 정렬·DB·원시 corpus와 무관했고 다음 상태를 보존했다.

- 완성 partial 파일: 244개
- payload: WAV 60, TextGrid 60, LAB 60, 행별 CSV 60
- 지원 파일: `REVIEW.csv`, `MANIFEST.csv`, `README.md`
- payload 목적지 SHA/bytes 불일치: 0
- 기록된 원본 SHA와 현재 원본 불일치: 0
- 기계 marker·DB 재수출 표본·6개년 감사 fingerprint 불일치: 0

이 과정에서 manifest v1이 partial 절대경로를 목적지 경로로 기록해, 정상
rename 뒤에는 경로가 낡는 설계 결함도 발견했다. 패키저를 다음과 같이
교정했다.

1. 목적지 기록은 평면 `relative_path`만 사용한다.
2. bundle schema를 `mfa_r2_flat_review_bundle.v2`로 올린다.
3. Dropbox의 일시적 rename 잠금은 제한 시간 안에서만 backoff 재시도한다.
4. 이미 완성된 v1 partial은 payload·원본·근거 파일을 전수 재해시한 뒤
   v2로 정규화하고, 원래 manifest SHA와 복구 이유를 보존한다.

복구는 2026-07-30 14:27:50 KST에 성공했고 최종 위치는 다음과 같다.

```text
C:\Users\ari30\Dropbox\MFA_R2_INFRA_PILOT_20260730
```

복구 보고서:
`outputs/reports/RECOVER_mfa_r2_pilot_bundle_20260730.json`

## 최종 전달 감사와 현재 판정

`REVIEW.xlsx`를 openpyxl로 생성한 뒤 다시 열어 다음을 확인했다.

- Dropbox 평면 폴더 파일: 246개
- 검토 발화: 60개, 연도당 10개
- 검토표: 15열, `검토입력`·`안내` 2개 시트
- WAV/TextGrid/LAB/CSV 상대 링크: 240/240
- 결정 dropdown 규칙: 2개
- table: `MfaR2InfrastructureReview`
- 연구자 검토 상태: `pending`
- 실제 음운 실현 판정 수행: 거짓

최종 전달 감사:
`outputs/reports/AUDIT_mfa_r2_pilot_review_delivery_20260730.json`

따라서 **기계 인프라 수용 파일럿은 통과**했다. 다만 이는 전수 MFA 승인이나
구체적 음운 실현 판정이 아니다. 사용자가 `REVIEW.xlsx`에서 연결·tier·경계·
CSV 검색 편의성을 검토해 인프라 승인 결정을 남긴 뒤에만 2020 r2 전수
MFA로 전환한다.
