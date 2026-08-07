# 공통발음 r3 Jamo G2P 후보 생성 완료 기록

- 실행 ID: `common_pron_mfa_r3_20260807`
- 실행 시작: 2026-08-07 20:51:40 KST
- 정상 종료: 2026-08-08 02:42:10 KST
- 상태: `success_candidates_not_selected`
- 범위: 후보 생성·검증만 완료; canonical 선택·adoption·연도별 MFA·TextGrid 변경 없음

## 왜 수행했는가

r2 MFA 입력사전은 일부 표면형에서 별도로 계산한 음운규칙 예상형을 일관되게
전달하지 못했다. 특정 예만 고치는 대신 2020–2025의 규칙 민감 source
312,410형·4,472,892회에서 중복 제거한 규칙 목표 한글형 310,605개를 동일한
동결 Jamo G2P로 계산했다. 이 출력은 실제 실현 발음이나 최종 발음 정답이 아니라,
후속 exact broad-Roman 일치 Gate에 넣을 후보이다.

## 실행 계약과 결과

- shard: 25,000개 이하 13개(마지막 10,605개)
- 입력 규칙 목표형: 310,605개
- 생성된 1-best 후보: 310,605개
- FST no-path: 0
- 입력 밖 key: 0
- shard 내부·전체 shard 간 중복 key: 0
- `spn`: 0
- Korean MFA acoustic v3.3.0 inventory 밖 phone: 0
- 중단된 미검증 `.dict`: 0
- 원자료·TextGrid 수정: 0

후보 단계 manifest:

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
03_g2p_rule_targets_1best\G2P_CANDIDATE_OUTPUTS_MANIFEST.json
SHA-256 b8772dcd5fb5923b7653cce1aead6a7ca3528b0058081a3c5d239066876bd8f6
```

읽기 전용 독립 감사:

```text
outputs/reports/AUDIT_common_pron_mfa_r3_g2p_candidates_20260808.json
SHA-256 9c558435f264b8a5f9a075579bd3c0b8466d11183799e1c4e9e1efa65499863f
```

동결 acoustic model SHA-256:

```text
94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c
```

실행 manifest가 기록한 코드 commit은 `ed9b051`, 독립 read-only 감사기가
기록한 commit은 `f0a826e`다.

## 시행착오와 안전 처리

1. 사용자가 프로젝트 밖에서 상대경로 상태 명령을 실행해 상태판을 찾지 못했다.
   G2P는 시작 전이었고 이후 모든 사용자 명령을 프로젝트 절대경로로 바꿨다.
2. 첫 본 실행은 Windows PowerShell 5.1의 `[uint32]0x80000001` 변환 오류로 첫
   shard 전에 중단됐다. lock·부분 산출물은 남지 않았다. `Convert.ToUInt32`로
   고치고 실제 절전 방지 활성화·복원을 preflight에 포함한 뒤 재실행했다.
3. 완료 후 독립 감사에서 기존 `finalize` 명령은 검증과 함께 D:의 shard 보고서를
   다시 쓰는 성격임을 확인했다. 샌드박스가 쓰기를 차단했고 D: 변경은 없었다.
   이후 `audit-phase` 읽기 전용 경로를 추가해 SHA·phone inventory·전역 key
   coverage를 원본 무변경으로 다시 검증했다.

## 해석 제한과 다음 Gate

310,605/310,605 coverage는 G2P 계산이 완전하다는 뜻이지, 310,605개 발음이 모두
최종 채택됐다는 뜻이 아니다. 다음 허용 단계는 각 후보의 broad Roman을 독립
규칙 목표 Roman과 정확히 비교하여 일치·불일치·보류를 분리하는 것이다. 이후
canonical 선택표, r3 MFA 사전, adoption Gate가 통과하기 전에는 연도별 MFA나
TextGrid materialization으로 넘어가지 않는다.

최종 TextGrid에는 향후 채택된 r3 사전 SHA·contract ID·`alignment_origin`이
실제로 기록되어야 한다. 기존 r2 TextGrid의 phone 문자만 제자리 치환하는 방식은
허용하지 않는다.
