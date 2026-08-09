# r3 6-tier exporter·독립 감사 계약 결과 (2026-08-09)

## 목적

외부 리뷰 체크리스트 6(H3)를 반영했다. 기존 승인 6-tier의 이름·시간경계·
언어학적 의미는 바꾸지 않는다. 대신 r3 TextGrid와 동반표가 어느 발음 release,
사전, alignment contract, MFA DB에서 생성됐는지를 manifest만으로 판별하고,
`phoneme_r_auto`가 실제 `phones_mfa`의 결정론적 넓은 Roman 대응인지 독립
전수 감사할 수 있게 했다.

## r3 성공 산출물의 필수 10필드

다음 필드는 r3 export 보고서와 `TABLES_MANIFEST.json` 양쪽에 같은 값으로
기록된다.

1. `pronunciation_release_id`
2. `pronunciation_contract_id`
3. `mfa_dictionary_sha256`
4. `alignment_contract_id`
5. `textgrid_schema`
6. `source_db_sha256`
7. `alignment_origin`
8. `r3_full_realign`
9. `safe_body_routing_contract_id`
10. `followup_inventory_sha256`

값은 실행 인자로 임의 입력하지 않고 `mfa_r3_alignment_contract.v1`의 identity와
실제 파일 바이트에서 가져온다. exporter는 alignment contract ID를 다시
계산하고 dictionary·acoustic·G2P의 경로·크기·SHA를 확인하며, 실제 source DB를
한 번 SHA-256 해시한다. r3 성공 manifest에서 한 필드라도 비거나 다르면 export를
성공으로 승격하지 않는다.

기존 r2 계약과 동반표 schema는 재현·복구용으로 계속 읽을 수 있다. r3 계약이
입력된 경우에만 10필드 hard gate가 추가되므로, 과거 r2 산출물이나 schema를
소급 변경하지 않는다.

## 독립 감사 강화

`audit_mfa_research_6tier_year.py`는 r3에서 다음을 생성기와 별도로 확인한다.

- alignment contract ID 독립 재계산
- dictionary·acoustic·G2P 실제 SHA와 contract identity 대조
- source DB 실제 SHA 재계산
- 10개 manifest 필드의 존재와 값 일치
- 모든 gzip 동반표 행의 `alignment_contract_id` 전수 대조
- 각 `phones_mfa` label에 frozen acoustic `phone_groups`와
  `classify_phone`을 다시 적용해 `phoneme_r_auto` label 전수 재계산
- 기존 6-tier 0–xmax 연속성, phone inventory, `spn`, TextGrid·동반표 ID/SHA
  검사는 그대로 유지

`phoneme_r_auto`는 실제 발음 판정이나 기저 음소 복원이 아니라 MFA phone에서
기계적으로 얻은 넓은 Roman 전사라는 기존 방법론을 유지한다.

## 합성 DB 회귀 결과

기존 r2 호환 검사와 새 r3 검사를 합쳐 40건이 통과했다. 새 r3 fixture는 정상
export·audit 외에 다음 변조를 각각 차단했다.

- TextGrid의 `phoneme_r_auto` label만 변경
- manifest의 `pronunciation_release_id` 변경
- gzip 표의 `alignment_contract_id`를 변경한 뒤 그 파일 SHA까지 다시 기록

따라서 단순 manifest SHA 대조만으로 놓칠 수 있는 행 수준 계약 혼입도 차단한다.

## 변경하지 않은 것과 다음 단계

- production MFA·TextGrid·CSV: 실행 안 함
- Stage 01–21, D: 원자료, r2 DB·TextGrid·CSV: 변경 없음
- release Gate: 닫힘 유지

다음 단계는 체크리스트 7의 PowerShell 전수 검사 배선, r3 preflight에서 두
PowerShell 검사와 Python suite를 실제 호출하는 연결, 전체 신규·수정 코드의
집계 감사를 수행하는 것이다.
