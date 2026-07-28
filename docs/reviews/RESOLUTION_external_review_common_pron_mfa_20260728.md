# 외부 공통사전·MFA 코드 리뷰 반영 결과

작성일: 2026-07-28

원 리뷰:
`docs/reviews/incoming/EXTERNAL_REVIEW_common_pron_mfa_claude-code_20260728.md`

## 반영

- MFA-001: 공식 commit과 acoustic v3.3.0·Jamo G2P v3.2.0·dictionary
  SHA를 실행 직전 검증한다.
- MFA-002: 구 결과 mismatch 0을 채택 gate에서 제거하고 전수 차이
  inventory와 연구자 승인으로 교체했다.
- MFA-003: 기본은 승인된 공통사전이며 legacy inline G2P는 명시적
  과거 재현 옵션으로만 남겼다.
- MFA-004: alignment DB와 최종 TextGrid phone tier의 `spn`을 모두
  hard failure로 처리한다.
- MFA-005: 압축 archive는 트리의 모든 `*.db` 전후 SHA, 파일 수·바이트,
  CRC와 archive SHA를 기록하고 삭제 기능을 제공하지 않는다.
- MFA-006: 직접 연도별 러너도 bulk lock을 취득하며 공통 G2P lock과
  양방향 상호 배제한다.
- MFA-007: 신규 MFA temp/output은 D:로 고정한다.
- MFA-008: 상태판의 재개 속도·ETA는 현재 lock 이후 새로 검증된
  shard와 현재 출력만 사용한다.

## 추가 보강

- U+11B3은 같은 Jamo 모델 입력에만 완전분해하고 원 표층키를 복원한다.
  정확한 4어절 외 예외는 차단하며 4행 연구자 승인 전 final을 금지한다.
- 최종 여섯 연도의 acoustic·dictionary·G2P·runtime·manifest·adoption
  SHA 동일성을 별도 전수 감사한다.
- 생성기 코드의 LF 정규화 SHA를 prepare 계약에 포함한다.

## 현재 판정

코드 준비와 r2 입력·4건 후보 준비는 완료됐다. 완성 r2 사전과 연도별
MFA 사용 승인은 아직 없으므로 대량 연도별 정렬은 시작하지 않는다.
