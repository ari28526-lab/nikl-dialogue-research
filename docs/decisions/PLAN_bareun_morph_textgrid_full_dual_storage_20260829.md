# 바른 v3.1 형태소 TextGrid 전수 D/C 이중 저장 계획

작성일: 2026-08-29 KST

상태: **v1 전수 실행 중 — 현재 runner 고정, 다음 갱신 v2 Gate**

## 목표

바른 v3.1 형태소 final을 기존 r3 연구용 6-tier TextGrid 4,286,046건의
`morph_analysis_utt`에 반영한다. 원본 TextGrid·WAV는 수정하지 않고 새 파생본만
만든다. 전수 생성은 D:를 기본으로 하되, 다음 receipt를 D:에 썼을 때 안전선을
넘을 것으로 예상되면 해당 receipt 전체를 C: 임시 저장소로 보낸다.

## 저장소 계약

| 역할 | 저장소 | 남겨 둘 최소 공간 | 용도 |
|---|---:|---:|---|
| 기본 | D: 외장하드 | 18 GiB | control, receipt, 주 파생 TextGrid |
| spill | C: 로컬 | 20 GiB | D: 안전선 보호용 임시 파생 TextGrid |

2026-08-29 측정값은 D: 56.199 GiB, C: 37.760 GiB다. 두 안전선을 제외한
가용량은 약 55.959 GiB이며, 파일럿 추정 전수량 42.928 GiB와 추가 headroom
5 GiB의 합 47.928 GiB보다 크다. 이 수치는 실행 직전 preflight에서 다시
측정한다.

- 저장 선택 단위는 바른 형태소 receipt 하나다. 한 receipt의 파생 파일을 두
  드라이브로 나누지 않는다.
- D: 우선 배치 후 예상 잔여가 18 GiB 미만이면 C:를 검사한다.
- C: 예상 잔여도 20 GiB 미만이면 디스크를 채우지 않고
  `paused_storage_safety`로 멈춘다.
- 각 파생 파일의 저장소 ID와 상대경로·바이트·SHA-256은 SQLite checkpoint와
  receipt inventory에 기록한다.
- C: spill은 `work/` 아래 로컬 전용이며 Git·Dropbox 게시 대상이 아니다.

## TextGrid 갱신 계약

1. `words`, `phones_mfa`, `phoneme_r_auto`, `utterance`,
   `utterance_orth_r`의 시간과 label은 의미상 그대로 보존한다.
2. `morph_analysis_utt`의 기존 시간 경계는 그대로 두고 label만 바른 v3.1
   형태소 final로 교체한다.
3. 새 바른 token 수와 기존 labeled `words` 수가 다르면 word 경계를 고치지
   않는다. 발화 수준 형태소 label은 생성하되 `alignment_conflict`로 기록한다.
4. r3 TextGrid가 없는 발화는 파일을 만들지 않고 `no_mfa_alignment`로 보존한다.
5. WAV 접근과 MFA 재실행은 모두 금지한다.

## 중단·재개

- `CHECKPOINT.sqlite`의 receipt·파일 행을 트랜잭션으로 기록한다.
- 완성 파일은 임시 파일을 검증한 뒤 같은 볼륨에서 원자적으로 이름을 확정한다.
- 파일 확정 직후 checkpoint 전에 프로세스가 끊겨도, 재개 시 기존 파일을 새
  형태소 final 및 원본 tier와 대조해 재사용한다. 검증되지 않은 파일을 덮어쓰지
  않는다.
- 완료 receipt는 receipt와 압축 output inventory의 SHA를 확인한 뒤 건너뛴다.
- 오류·공간 중지는 완료분을 삭제하지 않고 `-Resume`으로 이어간다.

## 완료 상태와 새 외장하드

이번 runner는 D:/C: 분산 상태를 final release로 승격하지 않는다. 전수 생성이
끝나면 `built_pending_external_consolidation`으로 닫고 독립 전수 감사를 수행한다.

새 외장하드가 연결되면 다음 별도 Gate를 따른다.

2026-08-30 사용자 결정으로 신규 SSD 용량은 현실적인 비용을 고려해 2TB로
정했다. 이는 단일 볼륨 영구 통합 결정이 아니며, 현 D: 말뭉치 정본과 신규 SSD의
파생·현상별 작업 역할을 단계적으로 분리한다. 실제 배치와 삭제 승인은
`DECISION_external_ssd_2tb_staged_storage_distribution_20260830.md`를 따른다.

1. 원본 또는 파생본의 새 목적지를 명시한다.
2. 이동이 아니라 복사부터 수행한다.
3. 파일 수·총 바이트·manifest 및 SHA를 전수 검증한다.
4. 경로 manifest를 새 volume과 상대경로로 갱신한다.
5. 사용자에게 검증 결과와 삭제 대상을 다시 제시한다.
6. 별도 명시적 승인 뒤에만 기존 사본을 제거하고 final로 승격한다.

## 이번 준비 단계의 정지점

설정·runner·상태판·독립 감사기·PowerShell 5.1 회귀 검사·실제 경로
`PreflightOnly`가 모두 통과한 뒤, 사용자에게 전수 실행 명령을 제시하고 멈춘다.
Codex 세션에서 4,286,046건 전수를 직접 시작하지 않는다.

## 구현 진입점

- 설정: `config/bareun_morph_textgrid_full_v1.json`
- 전수 생성기: `scripts/python/run_bareun_morph_textgrid_full.py`
- 독립 전수 감사기: `scripts/python/audit_bareun_morph_textgrid_full.py`
- 실행 진입점: `run_bareun_morph_textgrid_full.ps1`
- 읽기 전용 상태판: `show_bareun_morph_textgrid_status.ps1`
- 회귀 검사: `tests/test_bareun_morph_textgrid_full.py`

실행 진입점은 생성이 성공하면 독립 전수 SHA 감사를 같은 PowerShell 창에서
계속한다. 생성이나 감사가 중단되면 완료 receipt를 보존하며, 같은 명령에
`-Resume`을 추가해 이어간다.

## 현재 v1과 다음 갱신의 경계

현재 `bareun_morph_textgrid_full_20260829` 실행에는 runner·config·감사기 변경을
섞지 않고 기존 receipt와 checkpoint로 완료한다. 현재 작업을 중단해 새 방식으로
처음부터 재시작하지 않는다.

다음 Bareun 엔진 갱신처럼 `morph_analysis_utt` label만 다시 바꾸는 전수 작업은
별도 run ID와 output root에서
`DECISION_textgrid_byte_preserving_refresh_v2_20260830.md`의 streaming refresh
파일럿을 먼저 통과해야 한다. source의 목표 label span 밖 byte를 그대로 복사하고
SHA 계산과 구조 검사를 같은 pass에 결합하되, 독립 Praat-openable 파일과 전수
감사 요구는 유지한다.
