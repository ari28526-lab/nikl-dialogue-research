# 프로젝트 현재 상태 정본

최종 갱신: 2026-07-29 22:10 KST

이 문서는 긴 대화, 세션 전환, 자동 context compaction 뒤에도 이미 확정된
결정과 바로 다음 작업을 잃지 않기 위한 단일 상태 정본이다. 새 작업을
시작하는 사람이나 도구는 최근 대화만 보고 명령을 제안하지 말고 반드시
이 문서와 실제 상태판을 먼저 대조한다.

## 연구 목적과 불변 원칙

- CSV에서 형태소·표기 환경을 검색해 대응 WAV·TextGrid를 모은다.
- KOINA 운율 분석과 연구자의 청취·시각 판정으로 실제 실현을 분석한다.
- MFA/G2P phone은 정렬용 보조 정보이며 실제 실현 판정값이 아니다.
- `D:\`가 메인 실행·산출물 드라이브다.
- 외장 HDD는 검증된 archive용이며 MFA 실행 root로 사용하지 않는다.
- 원 WAV·원 JSON·원 LAB·구결과를 조용히 수정하거나 덮어쓰지 않는다.

## 확정된 공통 발음·MFA 기준

- acoustic: Korean MFA v3.3.0
- G2P: Jamo v3.2.0, `unicode_decomposition=true`
- 공통사전: `common_pron_mfa_r2_20260728`
- 공통사전 SHA256:
  `24c406604c86a5df833a7e47d809f252d6fc39dc566a6d3818b3d3ffeb04fb86`
- `spn=0`, 관측 OOV missing=0, phone inventory 이탈=0
- 예외 27건은 연구자가 권고 발음으로 승인했고 최종 r2에 반영됐다.
- 구결과와 차이가 작더라도 2020–2025 여섯 연도를 모두 같은 r2
  사전·acoustic·G2P·adoption 계약으로 다시 정렬한다.
- 2020·2021 difference inventory는 구결과 재사용 판정이 아니라
  전환 원인과 규모를 남기는 감사 자료다.

## 완료 상태

- r2 공통사전 final manifest: 성공
- G2P shard: 35/35
- 2020·2021 difference inventory: 완료
- 2020 TextGrid inventory: 866,196/866,196
- difference 분류 행: 425,428
- 연도별 MFA adoption: 아직 `pending`
- 2020–2025 r2 재정렬: 아직 시작 전

## 바로 다음 작업

2026-07-29 밤에는 구 pre-Jamo 산출물을 E:에 **항목별 7z로 압축하고
검증**한다. 수백만 작은 파일을 낱개로 Robocopy하지 않는다.

```powershell
& "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "C:\Users\ari30\research\2026_summer_research\scripts\archive_pre_jamo_outputs_compressed.ps1" -ArchiveDrive "E:"
```

이 작업은 원본 삭제 기능이 없으며 다음을 검사한다.

- 7-Zip CRC 전수 검사
- 원본과 archive 내부 파일 수·비압축 바이트 일치
- 모든 DB의 작업 전후 SHA256 일치
- 완성 archive SHA256
- `.partial`에서 최종 파일로 원자 승격

구형 `archive_pre_jamo_outputs_to_external.ps1`은 loose-file 방식이라
사용 중단됐다. `-PruneAfterVerify`가 있는 구형 명령을 제안하거나
실행하지 않는다.

## 압축 archive 다음 순서

1. E: 압축 archive manifest와 각 항목 `verified` 상태 확인
2. 기존 연구자 결정과 difference inventory를 묶은 adoption v3 생성
3. adoption `allow_yearly_mfa=true` 검증
4. r2 기준 2020 MFA 실행
5. 2020 독립 QC 뒤 2021–2025 순차 실행
6. 마지막에 6개년 alignment contract 동일성 감사

## 세션·대화 전환 복구 절차

실질적 명령이나 대량 작업을 제안하기 전에 다음 순서를 지킨다.

1. 이 문서를 끝까지 읽는다.
2. `docs/environment/linguistics-research-environment-master-notes.md`를
   읽는다.
3. `scripts/show_common_pron_mfa_status.ps1`과 archive manifest 등 실제
   상태를 읽기 전용으로 확인한다.
4. `git status`와 최근 결정문을 확인한다.
5. 이 문서의 확정 결정과 충돌하는 구형 스크립트·명령은 제안하지 않는다.
6. 큰 단계가 끝날 때마다 완료 상태와 ‘바로 다음 작업’을 이 문서에
   갱신하고 작업 이력·결정문·커밋에 함께 남긴다.

새 대화는 이 정본을 읽는 한 안전하게 이어갈 수 있지만, 새 대화 자체가
상태 관리의 대안은 아니다.
