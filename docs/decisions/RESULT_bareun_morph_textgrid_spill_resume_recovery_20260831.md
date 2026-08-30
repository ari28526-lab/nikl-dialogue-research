# Bareun 형태소 TextGrid C: spill·재개 복구 결과

날짜: 2026-08-31 KST
상태: **코드 복구 완료·D: 안전 하한에서 실행 일시 정지**

## 결론

기존 3,305,749개 TextGrid와 11,585개 완료 receipt는 보존했다. C: spill의 첫
파일에서 발생한 Windows 경로 길이 오류를 수정하고, 재개 때 완료 receipt 전체를
다시 SHA 검사하던 병목도 체크포인트 전방 재개로 바꿨다. 새 코드는 실패 receipt
11,586부터 즉시 재개해 C: TextGrid 생성을 실제로 확인했다.

다만 기존 저장 라우터는 C: spill 이후에도 작은 receipt를 D:로 다시 보내고,
SQLite·shard inventory가 차지할 D: 제어 용량을 예약하지 않았다. 11,592 receipt,
3,307,029 TextGrid까지 진행한 시점에 D: 여유가 17.997768 GiB로 18 GiB 하한을
2,396,160바이트 밑돌아 PID 27344를 중지했다. 원본·완료 TextGrid·checkpoint를
삭제하거나 이동하지 않았다.

## 원인과 수정

1. C:의 깊은 output 경로에서 외부 temp와 writer 내부 temp가 중첩되어 최종 temp
   경로가 262자가 됐다. 외부 원자적 staging 이름을 짧은 UUID 이름으로 바꿨다.
2. 재개 runner가 완료 11,585 receipt를 약 16초/건으로 다시 SHA 검사해 기존
   구간만 약 51시간이 필요했다. 재개 시 frozen receipt inventory와 SQLite의
   receipt SHA·상태 계약을 대조하고 미완료 receipt만 처리하도록 바꿨다. 전수
   파일 SHA 검증은 원래 계약대로 생성 후 독립 감사에서 수행한다.
3. C: spill 시작 뒤에는 이후 새 receipt의 storage를 C:로 고정했다. 각 receipt
   전에 D: SQLite·shard control 용량을 보수적으로 예약하고, 이 예약 뒤에도
   18 GiB 하한을 유지할 수 없으면 쓰기 전에 `StorageSafetyStop`으로 중단한다.

## 검증 증거

- Python 회귀시험: 11/11 통과
- Windows PowerShell 5.1 safety/runtime: 경로 수정·빠른 재개 시점 80/80 통과
- 실제 체크포인트: 완료 11,585, 미완료 5,571, 첫 미완료 inventory index 11,586
- 실제 재개: receipt 11,586 `storage_id=local_c`, 이후 receipt 11,592까지 완료
- C: spill 확인: 새 TextGrid 521개 이상, 잔여 `.partial` 0개
- 중지 시 상태: TextGrid 3,307,029 / 4,286,046, no-MFA 571,717 /
  817,310, alignment conflict 101,467
- C: 여유 37.809 GiB로 20 GiB 하한 이상
- source TextGrid 수정 없음, WAV 접근 없음, MFA 재실행 없음

## 보존된 변경

- `ce44af0` — 짧은 C: spill staging 경로
- `07dd08b` — 체크포인트 전방 빠른 재개
- 후속 storage safety 보강은 이 문서와 함께 별도 커밋한다.

## 재개 Gate

현재 preflight는 `primary_above_floor=false`로 재개를 거부한다. 권고안은 D:에서
명시적으로 승인된 비정본·재생성 가능 자료 1.5–2 GiB 이상을 확보한 뒤 같은
`-Resume` 명령을 한 번 실행하는 것이다. 안전 하한을 18 GiB 아래로 낮추거나
완료 산출물을 임의 삭제하지 않는다. 새 외장 SSD를 사용하는 경우에도 먼저
read-only inventory, copy-first, 파일 수·바이트·SHA 검증, 별도 삭제 승인을
따른다.
