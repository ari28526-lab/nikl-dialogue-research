# 2020–2025 생산 완료 뒤 후속 연구 인프라 로드맵

작성일: 2026-08-14
상태: 실행 전 계획 정본

## 1. 목적과 실행 시점

이 계획은 2020–2025 r3 안전 본체의 MFA·6-tier·동반표·독립 QC가 모두 완료된
뒤 실행한다. 현재 완성본을 다시 만들거나 덮어쓰는 계획이 아니다. 후속 작업은
모두 `release_id + year + utt_id` exact-ID를 기준으로 추가 계층을 만들고, 원자료와
안전 본체를 읽기 전용으로 보존한다.

실행 순서는 다음 하나로 고정한다.

```text
2020–2025 안전 본체 동결
  → 전 연도 제외·후속 exact-ID 통합 대장
  → 회수 가능분 사유별 재처리 shard
  → 기본본+회수분의 append-only 통합 view
  → 표적 검색·추출 manifest
  → 수동 TextGrid 수정 overlay와 변경 이력
  → 세션 단위 JSON 파생 view
  → 재사용 가능한 HTML 매뉴얼
```

## 2. MFA 제외분 재처리

### 2.1 먼저 합칠 대장

현재 연도별로 흩어진 다음 범주를 한 행 한 발화의 통합 ledger로 만든다.

- pronunciation-safe 밖의 후속 발화
- pre-MFA `audio_pairing_unresolved`
- `empty_reference_unresolved_symbol`
- `text_duration_impossible` 및 0초 구간
- post-MFA `mfa_alignment_missing`
- 소리 없음·손상 WAV·구간 잘림 등 음원 품질 범주
- 연구 방법상 의도적으로 분석에서 제외한 범주

최소 열은 다음과 같다.

```text
release_id, year, utt_id, session_id, speaker_id,
exclusion_stage, exclusion_reason, evidence_path,
source_wav_sha256, source_csv_sha256,
recovery_eligibility, recovery_shard_id,
status, reviewed_by, reviewed_at
```

동일 발화가 여러 범주에 들어가면 행을 복제하지 않고 reason relation을 별도
테이블로 둔다. 전수 식 `source = safe_body + followup + final_methodological_exclusion`
이 정확히 성립해야 다음 단계로 간다.

### 2.2 재처리 원칙

1. 음원 매핑, 지속시간, 문자·LAB, MFA 기술 미정렬을 사유별 shard로 분리한다.
2. 같은 동결 음향모델·공통발음사전·phone inventory를 사용한다.
3. 기존 DB와 6-tier를 수정하지 않고 후속 DB·TextGrid root에 새로 쓴다.
4. 성공분은 append-only 통합 view에 연결하고 실패분은 원 사유와 새 실패 사유를
   모두 남긴다.
5. 연도 전체 재실행 대신 실패 shard만 재개한다.

재처리 결과 상태는 최소 `recovered_aligned`, `still_technical_unresolved`,
`audio_unrecoverable`, `methodological_exclusion`로 구분한다. 청취하지 않은 기술
상태를 실제 음운 실현 판정으로 표현하지 않는다.

### 2.3 완료 조건

- 전 연도 exact-ID 중복·누락·미분류 0
- 각 후속 shard의 입력·출력·실패 manifest 존재
- 안전 본체 SHA 불변
- 통합 view에서 provenance 없는 정렬 0
- 회수 불가능분의 명시적 최종 사유 100%

## 3. 표적 추출과 수동 수정의 전체 반영 구조

### 3.1 표적 검색 정본

표적은 하나의 문자열이 아니라 다음 조건 조합으로 찾는다.

- 형태소 표면형·원형·품사
- 형태소 의미번호와 의미번호 출처
- 어절 철자·형태소/어절 Roman 검색키
- 규칙·사전 발음 참조 정보
- 앞뒤 형태소·음절·분절음 환경
- 화자·대화상대·세션·사회변수
- MFA word/phone 시간과 품질 flag

의미번호는 모든 형태소에 자동으로 확정된 값이 있다고 가정하지 않는다. 다음 열을
분리한다.

```text
sense_id, sense_source, sense_status,
sense_candidate_ids, sense_confidence, sense_review_note
```

### 3.2 추출 manifest

각 연구마다 query 자체와 결과를 동결한다.

```text
study_id, query_id, query_version, extracted_at,
year, utt_id, target_occurrence_id,
morph_id, eojeol_id, sense_id,
wav_path, base_textgrid_path, curated_textgrid_path,
target_xmin, target_xmax, context_before, context_after,
quality_flags, inclusion_status
```

WAV·TextGrid·관련 CSV는 manifest의 exact-ID에서 패키징한다. 사용자가 일일이
파일을 찾지 않도록 표적별 또는 연도별 검토 bundle과 review workbook을 자동으로
만든다.

### 3.3 수동 TextGrid 수정 overlay

안전 본체 TextGrid를 직접 편집하지 않는다. 수동 수정은 다음 event log를 정본으로
남긴다.

```text
edit_id, study_id, year, utt_id, base_release_id,
base_textgrid_sha256, parent_revision,
tier_name, interval_identity,
old_xmin, old_xmax, old_label,
new_xmin, new_xmax, new_label,
edit_reason, editor, edited_at, review_status
```

`apply_manual_textgrid_edits.py`가 base+승인 event를 읽어 curated TextGrid와 수정
동반표를 재생성한다. 충돌, base SHA 변경, 겹치는 interval, 경계 역전은 fail-closed로
중단한다. 연구 중 추가 수정도 새 event로 이어 붙이고 과거 값을 덮어쓰지 않는다.

전체 검색층에는 원 TextGrid를 바꾸는 대신 다음 포인터를 갱신한다.

```text
active_annotation_source = base | curated
active_annotation_revision
active_textgrid_path
manual_edit_count
```

따라서 한 연구에서 승인한 수정이 다음 추출과 세션 JSON에도 자동 반영되면서,
언제든 base 정렬과 차이를 재현할 수 있다.

## 4. 세션 단위 대화 JSON

### 4.1 역할

CSV·Parquet는 분석과 조합검색의 정본으로 유지한다. 세션 JSON은 같은 대화가
발화별 파일로 끊겨 보이는 문제를 해결하는 읽기·교환용 materialized view다.
따라서 JSON을 새 분석 정본으로 만들거나 CSV를 폐기하지 않는다.

### 4.2 권장 단위와 형식

- 한 세션 한 파일: `session_id.json.gz`
- 대량 순차 처리용 index: `sessions.jsonl.gz`
- 구조 검증: `session_dialogue.schema.json`
- 음성·TextGrid·대형 phone 배열은 필요 이상으로 중복하지 않고 경로와 SHA로 참조

### 4.3 잠정 구조

```json
{
  "schema_version": "nikl_dialogue_session.v1",
  "release_id": "...",
  "year": 2025,
  "session_id": "...",
  "participants": [],
  "utterances": [
    {
      "utt_id": "...",
      "order": 1,
      "speaker_id": "...",
      "addressee_ids": [],
      "orthography": {"original": "...", "form": "..."},
      "morphemes": [
        {"form": "...", "lemma": "...", "pos": "...", "sense_id": null}
      ],
      "pronunciation": {
        "orthographic_roman": "...",
        "rule_or_dictionary_reference": [],
        "mfa_phone_intervals_ref": "...",
        "manual_realization": null
      },
      "assets": {"wav": "...", "base_textgrid": "...", "curated_textgrid": null},
      "timeline": {"source_xmin": null, "source_xmax": null, "stitched_offset": null},
      "quality_flags": []
    }
  ]
}
```

MFA phone은 정렬 산출물, 규칙·사전 발음은 참조 후보, `manual_realization`은
연구자가 판정한 경우만 채운다. 이 세 종류를 하나의 `pronunciation` 값으로 합치지
않는다. 원 JSON의 대화 순서·화자 관계를 우선 보존하고, 절대 세션 시간이 없는
발화는 임의의 연속시간을 원자료 시간처럼 만들지 않는다. 이어붙인 분석 자료에는
별도 mapping으로 원 발화 좌표를 보존한다.

### 4.4 먼저 결정해야 할 세부 사항

- 원 JSON에서 안정적으로 얻을 수 있는 발화 순서와 대화상대 ID
- 한 발화에 여러 의미번호 후보를 담는 방식
- 겹침 발화와 동시발화 표현
- 세션 원음이 없는 경우의 timeline 의미
- manual edit revision을 JSON에 내장할지 참조할지
- phone interval을 JSON에 내장할 표본 범위와 외부 참조 범위

위 항목을 5세션 표본으로 검증한 후에만 전수 생성한다.

## 5. 다른 연구자도 재사용할 HTML 매뉴얼

### 5.1 산출물

`manual/` 아래 Quarto 기반 정적 HTML을 만든다. 원자료나 대형 산출물을 복사하지
않고 작은 예제 한 세션과 schema·코드·보고서를 포함한다.

```text
manual/
  index.qmd
  01_research_flow.qmd
  02_csv_build.qmd
  03_mfa_alignment.qmd
  04_textgrid_and_companion_tables.qmd
  05_target_extraction_and_manual_edits.qmd
  06_session_json.qmd
  07_troubleshooting.qmd
  08_data_sharing_and_release.qmd
  data_dictionary/
  examples/
  scripts/
```

### 5.2 각 단계의 설명 형식

모든 페이지는 다음 순서를 따른다.

1. 연구에서 왜 필요한가
2. 입력 파일과 필수 열
3. 코드가 하는 핵심 변환
4. 작은 실제 예시의 입력→출력
5. 생성되는 파일과 다음 단계의 join key
6. 검증 조건과 실패 시 정지점
7. 재실행·재개 방법
8. 논문 방법에 기록할 항목

기술 상자는 `주의`, `자동 판정 아님`, `원자료 변경 금지`, `Windows PowerShell
5.1`, `용량·checkpoint`, `연구자 승인 필요`로 구분한다. 과거 시행착오는 단순
연대기가 아니라 재발 가능한 failure mode와 예방 규칙으로 요약한다.

### 5.3 재사용 코드

- 환경·경로 preflight
- CSV logical record reader와 schema validator
- exact-ID inventory/reconciliation
- TextGrid tier·경계 validator
- target manifest builder와 review bundle packager
- manual edit event validator/applier
- session JSON builder와 JSON Schema validator
- manifest·SHA·methods summary 생성기

매뉴얼의 숫자와 상태는 하드코딩하지 않고 완료 manifest에서 읽어 빌드한다.

## 6. 구현 우선순위와 Gate

| 단계 | 먼저 만들 것 | 다음 단계 진입 조건 |
|---|---|---|
| A | 6개년 base release manifest | 2020–2025 QC passed·SHA 동결 |
| B | exclusion ledger·reason relation | 전수 exact-ID 회계, 미분류 0 |
| C | reason별 recovery shard | base SHA 불변·shard QC passed |
| D | target query·manifest | 의미번호/환경 join 표본 검증 |
| E | manual edit event·curated overlay | round-trip·충돌·provenance 시험 통과 |
| F | session JSON v1 | 5세션 schema·순서·화자·좌표 수동 검토 |
| G | Quarto HTML manual | 예제 명령 재현·링크·렌더링 전수 확인 |

## 7. 이번 계획에서 하지 않는 것

- kPhonetica를 필수 의존성으로 넣지 않는다.
- wav2vec·MFA·사전 발음을 실제 실현의 자동 정답으로 합치지 않는다.
- 연구별 수동 수정으로 6개년 base TextGrid를 직접 덮어쓰지 않는다.
- 세션 JSON에 음성 원본을 base64 등으로 중복 저장하지 않는다.
- 완료된 연도 전체를 후속 오류 한 건 때문에 다시 실행하지 않는다.

## 8. 공동연구·공개용 데이터 release

### 8.1 기본 원칙

내부 작업 경로 `D:\...`를 그대로 전달하지 않는다. 모든 공유본은 상대경로,
고정된 schema, exact-ID, SHA-256 manifest를 갖는 별도 release builder로 만든다.
초본과 수정본을 둘 다 보존하되 어느 것이 현재 분석판인지 명시한다.

```text
release_<version>/
  README.html
  CITATION.cff
  LICENSES/
  manifest/release_manifest.json
  manifest/files_sha256.csv
  schema/
  metadata/
  wav/
  textgrid/base/
  textgrid/curated/
  edits/manual_edit_events.jsonl
  tables/base/
  tables/curated/
  sessions/
  documentation/
```

`base`는 자동 생산 당시 동결본, `curated`는 승인된 수동 수정 반영본이다. 수정본만
따로 배포하지 않고 base release ID·base SHA·edit event를 함께 제공하여 차이를
재현하게 한다. WAV가 잘리거나 이어붙은 경우 원 WAV SHA, 구간 좌표, 파생 WAV
SHA, stitch mapping을 함께 기록한다.

### 8.2 공유 profile

| profile | 대상 | 포함 원칙 |
|---|---|---|
| `internal_full` | 연구자 내부 보존 | 권한이 있는 원자료·모든 파생본·검토 이력 |
| `collaborator_restricted` | 승인된 공동연구자 | 연구협약과 접근권한이 허용하는 WAV·전사·파생본 |
| `public_derived` | 연구결과 공개 | 재배포가 허용된 파생표·schema·코드·작은 예제 중심 |

말뭉치 원자료와 WAV의 재배포 가능 여부는 추정하지 않는다. 실제 release 전에
원 말뭉치 이용약관·라이선스, 연구윤리/동의 범위, 음성·전사 내 개인정보를 별도
체크리스트로 확인한다. 허용되지 않은 WAV는 복사하지 않고 원자료 취득 안내와
stable ID·checksum·파생 구간 정보만 제공한다.

### 8.3 공유 전 자동 검사

- release manifest의 모든 상대경로 존재·SHA 일치
- WAV↔TextGrid↔CSV↔JSON exact-ID 및 duration 일치
- base↔curated parent revision과 edit event 전수 연결
- 절대 로컬 경로·API key·비밀값 0
- 직접식별자·자유전사 개인정보 검토 상태 명시
- profile별 허용/제외 파일 allowlist
- schema validation과 작은 표본의 실제 재현
- 코드 commit·환경·도구 버전·모델·사전 계약 기록

`build_research_data_release.py --profile ...`은 허용 파일만 새 staging에 복사하고,
검사가 모두 통과한 뒤에만 배포 archive를 만든다. 원자료 폴더와 내부 완성본을
직접 압축하는 방식은 사용하지 않는다.

### 8.4 버전과 인용

공유 release는 `vMAJOR.MINOR.PATCH`와 DOI/저장소 식별자를 염두에 둔다. schema나
연구 판정 범위가 바뀌면 major/minor를 올리고, 파일 교정만 있으면 patch로 남긴다.
각 논문·공동연구의 분석 manifest에는 사용한 data release, code commit, query
version, curated revision을 기록하여 같은 결과를 다시 구성할 수 있게 한다.

이 계획의 schema 이름·디렉터리·CLI는 2025 안전 본체 완료 후 작은 표본과 외부
리뷰를 거쳐 별도 결정 문서에서 동결한다.
