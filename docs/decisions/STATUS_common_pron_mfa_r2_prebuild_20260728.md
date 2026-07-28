# 공통사전 기준 작업 상태: r2 준비·4건 후보 완료, 최종 사전 생성 전

작성일: 2026-07-28

## 현재 상태

- 외부 코드 리뷰의 BLOCKER/HIGH 항목을 반영해 r2 생성·검증 코드와
  연도별 MFA 채택 gate를 구현했다.
- **완성된 공통사전 실물은 아직 없다.**
- `common_pron_mfa_r1_20260728`은 첫 G2P shard 검증에서 strict
  grapheme 누락을 발견해 중단됐다. 이는 거짓 성공이 아니라 의도한
  안전장치의 작동이며, r1은 생산 사용 불가·폐기 기준선이다.
- 최신 공식 Jamo G2P v3.2.0과 acoustic v3.3.0을 쓰는 r2의 입력 준비와
  `ᆳ` 4어절 후보 생성은 완료했다. 881,237개 관측 어절 중 최신
  기본사전 OOV는 866,692개이며, 표준 shard 대상 866,688개와 동일
  Jamo rewrite 대상 4개로 분리된다.
- 2026-07-28 16:36의 최초 후보 release는 코드 계약 SHA를 manifest에
  넣기 전 생성됐으므로 생산본으로 이어가지 않는다. 삭제하지 않고
  `D:\mfa_common_pron\archive_obsolete\common_pron_mfa_r2_20260728_pre_code_contract_20260728_1644`
  에 보존했다.
- commit `7c7e9d73cfad7af036b1922ac2dfa34b2ae7b5a7`로 다시 준비한 현재
  release 계약 ID는
  `c6a877ff731e871310870afaffd34dbfed82a78fb43e4032561acfe68517ffcd`,
  생성기 LF 정규화 SHA256은
  `6b3fcedc5141c09b667305f9c25d879d21e31e56cf6b0d1d2a661118d03462bc`
  다.
- 4어절 후보 phone은 모두 `spn=0`, acoustic inventory 이탈=0,
  표층키 복원 4/4를 통과했으나 연구자 검토표의 `decision`은 아직
  `pending`이다.
- 따라서 현재 어떤 연도의 MFA도 “공통사전 기준 재실행 완료”로
  간주하지 않는다.

## 실행 정책

1. 연도별 MFA의 기본 경로는 검증된 공통사전 manifest를 필수로 한다.
2. 인자 생략 시 설치 사전과 inline G2P로 자동 복귀하는 동작은
   금지한다.
3. legacy inline G2P는 과거 재현·진단에만 명시적 opt-in으로 허용하고,
   결과 marker에 legacy임을 기록한다.
4. r2는 최신 동결 모델 SHA pin, Jamo grapheme coverage, `missing=0`,
   `spn=0`, phone inventory 이탈 0을 모두 통과해야 한다.
5. 구 2020·2021 결과와의 비교는 동일성 채택 gate가 아니라 전수 차이
   inventory로 남긴다. 결함을 고친 새 결과가 구결과와 달라지는 것은
   예상된 연구 증거다.
6. 차이 분류와 `ᆳ` 4어절 phone에 대한 연구자 승인이 기록되기 전에는
   r2를 연도별 MFA에 사용하지 않는다.
7. 생성기 코드의 LF 정규화 SHA256을 prepare 계약에 포함한다. 커밋 전
   산출물이나 다른 코드로 만든 shard를 이름만 같다고 재사용하지 않는다.

## 용어

- **코드 준비 완료**: 재현 가능한 생성·검증 절차가 존재한다는 뜻.
- **r2 준비 완료**: OOV inventory·입력 shard·모델 pin·4건 후보가
  생성됐지만 최종 사전은 아직 없다는 뜻.
- **r2 실물 완료**: 모든 shard, 최종 사전, manifest와 hard gate가
  성공했다는 뜻.
- **연도별 사용 승인**: r2 실물 완료에 더해 차이 inventory와 연구자
  승인이 끝났다는 뜻.

세 상태를 문서·상태판·실행 marker에서 혼용하지 않는다.
