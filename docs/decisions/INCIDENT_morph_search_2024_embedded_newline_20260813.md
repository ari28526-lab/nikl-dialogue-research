# 2024 조합검색 CSV 내부 줄바꿈 사고와 재발 방지

## 결론

2026-08-13 14:48 KST의 2024 `morph_search.v3` 첫 실행은 shard 1의
`utterance_master_v2.csv`를 gzip으로 묶는 단계에서 안전 중단됐다. 원인은
CSV 필드 안에 합법적으로 인용된 줄바꿈 한 개가 있는데, 패키징 코드가 물리적인
텍스트 줄 수를 CSV 레코드 수로 간주한 것이었다.

이 실패는 원 WAV·원 JSON·원 CSV·공통발음사전·MFA DB·TextGrid를 수정하지
않았다. 성공한 shard manifest도 생성되지 않았고, 실패 산출물은 삭제하지 않고
`archive_failed` 아래에 격리했다.

## 실제 사례와 원인

- 대상: `utt_id=SARW2400000002.1.1.113`
- 필드: `original_form`
- 값에는 `유니크 아이템 역시도 각종 조꽁\n부 옵션이 많이 사라진다고 합니다.`와
  같이 CSV 규격상 허용되는 인용 필드 내부 LF가 있다.
- 논리 CSV 레코드는 18,870개지만 물리 줄은 18,871줄이다.
- 기존 gzip 패키징·검증·연도 병합 코드가 `readline()`과 줄 반복으로 행 수를
  세어 `expected=18870 actual=18871`로 중단했다.

2020–2023에서 같은 오류가 보이지 않은 것은 해당 코드가 옳았기 때문이 아니라,
먼저 처리된 shard에서 이 형태의 필드 내부 줄바꿈이 나타나지 않았기 때문이다.

## 수정

`scripts/python/build_morph_search_year_sharded.py`에서 다음을 동일하게 바꿨다.

1. 원 CSV와 gzip 검증의 행 수를 `csv.reader`가 반환하는 **논리 레코드**로 센다.
2. gzip에는 검증한 원 CSV 바이트를 그대로 복사해 인용·내부 줄바꿈을 보존한다.
3. 연도 병합도 `csv.reader`/`csv.writer`로 수행한다.
4. master 중복 ID 검사는 문자열 `split(',')`가 아니라 헤더의 `utt_id` 열을
   이용한다.
5. 활성 `.partial`이 있으면 실제 재개 전에 fail-closed하며,
   `archive_failed`의 보존 증거는 활성 산출물로 오인하지 않는다.

회귀시험에는 필드 내부 줄바꿈이 있는 레코드를 추가했다.

## 실패 증거 보존

실패한 shard 1 패키지와 당시 progress는 다음 아래에 보존했다.

```text
D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801\2024\
  shards\shard_00001\archive_failed\package_physical_line_count_20260813_145140\
```

별도 Codex 실행 제한시간 때문에 끝나지 않은 2024 입력계약 임시 산출물도 삭제하지
않고 다음에 격리했다.

```text
D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\
  03_year_input_contracts\archive_failed\2024_codex_timeout_20260813_145416\
```

두 경로는 생산 입력이 아니며 재개 코드가 사용하지 않는다.

## 실제 2024 회귀 결과

수정 뒤 실패했던 shard 1만 제한 재실행했다.

- 상태: `paused_after_max_shards` (의도한 안전 정지)
- 완료 shard: 1/33
- `utterance_master_v2.csv.gz`: 18,870 논리 레코드
- gzip SHA-256:
  `04e3afb024458e412f8a604d2d117583bf9b4fc9732404cfc0069699b57754e0`
- 필드 내부 줄바꿈 보존: 통과
- 활성 `.partial`: 0

2024 exact-ID 입력계약 독립감사도 통과했다.

- source: 728,257
- pronunciation-safe: 595,743
- follow-up: 132,514
- pre-MFA 제외 적용: 1,339
- 최종 예상 MFA 안전 본체: 594,404
- 예상 입력의 WAV 누락: 0
- corpus에만 있는 추가 WAV: 24 (자동 선택하지 않음)
- 감사 상태:
  `passed_independent_exact_id_audit_pending_alignment_contract_gate_closed`

## 재발 방지 운영 규칙

새 연도의 전체 조합검색을 처음 실행할 때에는 다음 순서를 고정한다.

1. PowerShell 5.1 safety/runtime 검사
2. runner `-PreflightOnly`
3. `-MaxShards 1` 실제 데이터 회귀
4. shard manifest의 `status=success`, 논리 레코드 수, 활성 `.partial=0` 확인
5. 그 뒤에만 나머지 shard 재개

진행률이나 터미널의 퍼센트만 성공 근거로 사용하지 않는다. 연도 완료는 모든 shard
manifest, annual manifest, source contract가 통과해야 하며, MFA 시작은 별도의
연도 입력계약·정렬계약·이전 연도 전환 Gate까지 통과해야 한다.

## 왜 즉시 포착되지 않았는가

실행 스크립트 자체는 오류가 발생한 첫 shard에서 정상적으로 fail-closed했다.
그러나 당시 대화 측 점검은 실행 중인 PowerShell을 독립적으로 계속 관찰하는
백그라운드 감시가 아니라 사용자가 전달한 출력과 명시적 상태 조회에 의존했다.
따라서 실패 직후 자동 알림이 발생하지 않았다. 앞으로 장시간 실행을 인계할 때에는
상태 스크립트와 실패 progress를 확인하는 점검 시점을 명시하고, 다음 단계 진입은
완료 marker를 읽어야만 가능하게 유지한다.
