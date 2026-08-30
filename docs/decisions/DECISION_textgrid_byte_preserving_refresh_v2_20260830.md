# TextGrid byte-preserving refresh v2 결정

작성일: 2026-08-30 KST

상태: **사용자 채택 — 현재 v1 실행은 불변, 다음 전수 갱신 전 파일럿 Gate 적용**

## 결정

현재 실행 중인 Bareun v3.1 형태소 TextGrid v1은 중단·재시작하거나 새 구현과
섞지 않고 기존 계약대로 생성과 독립 감사를 완료한다.

다음 Bareun 엔진 갱신처럼 기존 TextGrid의 특정 발화 수준 label만 바꾸는 전수
작업은 전체 TextGrid를 parser object로 재직렬화하는 방식을 기본값으로 삼지
않는다. 별도 run ID와 versioned output root에서 **원본 byte를 보존하면서 목표
label span만 교체하는 streaming refresh v2**를 먼저 파일럿하고, 검증을 통과한
구현을 사용한다.

WSD 결과를 TextGrid 표시층으로 materialize할 때도 같은 엔진을 재사용한다.
다만 WSD CSV/Parquet sidecar가 정본이라는 원칙은 유지한다. 기존
`sense_analysis_utt` tier의 label을 갱신할 때는 replace 연산을 쓸 수 있지만,
그 tier가 없는 6-tier TextGrid에 새 tier를 추가하는 일은 header와 item 수까지
바꾸므로 별도의 append 연산·파일럿·승인을 거친다. WSD 값을
`morph_analysis_utt`에 섞지 않는다.

## 현재 실행을 재시작하지 않는 근거

2026-08-30 14:35 KST 읽기 전용 측정에서 현재 v1은 2,309,104 / 4,286,046건
(53.875%)을 생성했고 1,976,942건이 남았다. 최근 실측은 다음과 같다.

| 구간 | 처리속도 | 현재 방식의 생성 잔여시간 |
|---|---:|---:|
| 최근 1시간 | 63,386건/시간 | 31.19시간 |
| 최근 2시간 | 70,037건/시간 | 28.23시간 |
| 최근 4시간 | 74,396건/시간 | 26.57시간 |

상태판의 약 14.5시간은 초반의 빠른 구간을 포함한 누적 평균이라 최근 속도를
대표하지 않는다. 같은 방식으로 처음부터 다시 시작하면 최근 속도 기준 약
57.6–67.6시간이 필요하다. 새 구현으로 처음부터 다시 시작해 현재 실행을
계속하는 것보다 빨라지려면 생성 단계만 비교해도 최소 2.168배 빨라야 한다.
구현·파일럿·감사 계약 전환 시간까지 고려하면 현재 실행 중단을 정당화하려면
실제 볼륨 파일럿에서 안정적으로 최소 2.5배, 가능하면 3배가 먼저 입증돼야 한다.
그 증거가 없으므로 현재 v1에는 이 결정을 소급 적용하지 않는다.

## v1 병목과 v2 목표

현재 v1의 aligned TextGrid 한 건은 build에서 대략 다음 다섯 full-file pass를
거친다.

1. source SHA 읽기
2. source 전체 parse 읽기
3. destination 전체 쓰기
4. destination 전체 재parse 읽기
5. destination SHA 읽기

이후 독립 감사가 source·destination SHA와 두 파일의 parse를 다시 수행해 네 번
읽는다. v2는 source를 한 번 읽는 동안 SHA·구조·목표 span을 함께 확인하고,
destination을 한 번 쓰는 동안 SHA를 계산한다. 독립 감사도 source와 destination을
각 한 번 읽으며 SHA와 구조 검사를 함께 수행해 전체 pass를 약 9회에서 4–5회로
줄이는 것을 목표로 한다.

이 최적화는 4,286,046개의 directory entry·파일 open·destination write 비용을
없애지 않는다. 따라서 독립적으로 Praat에서 즉시 열 수 있는 전수 파일이라는
연구 요구를 유지하면서 불필요한 반복 읽기와 전체 재직렬화만 제거한다.

## 물리 산출물 계약

- 정렬된 4,286,046건은 각각 독립적인 Praat-openable TextGrid로 생성한다.
- MFA가 없는 817,310건은 파일을 꾸며 만들지 않고 `no_mfa_alignment`로 zero-drop
  회계한다.
- 새 label이 기존 label과 같은 발화도 독립 파생본 요구 때문에 source와 byte가
  같은 새 파일을 만든다.
- hardlink는 source와 file object를 공유하므로 금지한다.
- changed-only overlay와 archive-only 묶음은 검색·운반·백업 보조층으로는 쓸 수
  있지만 최종 독립 TextGrid release를 대신하지 않는다.
- source TextGrid·WAV는 읽기 전용이며, 새 output은 별도 versioned root에 만든다.
  overwrite와 source in-place patch는 금지한다.

## byte-preserving replace 계약

1. source를 strict UTF-8로 읽고 frozen manifest의 크기·SHA와 대조한다.
2. canonical long TextGrid의 tier 순서와 이름을 구조적으로 확인한다. Bareun
   refresh는 정확히 여섯 번째 `morph_analysis_utt` tier와 그 안의 유표 interval
   하나만 목표로 삼는다.
3. 전역 문자열 replace를 금지한다. 같은 문자열이 다른 tier에 있어도 목표 tier의
   정확히 한 label span만 선택한다.
4. 새 label은 동결 sidecar와 exact-ID로 연결한다. 현행 정규화 계약대로 줄구분자는
   공백으로 처리하고 허용되지 않은 C0 control은 fail-closed로 거부한다. Praat
   문자열 안의 `"`는 `""`로 escape한다.
5. source를 한 번 streaming하며 source SHA를 계산하고, destination과 같은
   volume의 고유 temp 파일에 `prefix + escaped new label + suffix`를 쓴다. 쓰는
   동안 destination SHA와 byte 수를 계산한다.
6. 목표 span 밖 prefix와 suffix는 source byte와 완전히 같아야 한다. line ending,
   숫자 표기, 공백, 기존 five-tier와 형태소 시간 경계를 재포맷하지 않는다.
7. source stat을 작업 전후 비교하고, temp flush/fsync·크기 검증 뒤 같은 volume에서
   원자적으로 이름을 확정한다. 기존 destination은 덮어쓰지 않는다.
8. source/destination SHA·byte 수·storage ID·상대경로·label 변경 여부를 receipt와
   checkpoint에 기록한다.

## 독립 감사와 채택 Gate

독립 감사기는 생성기와 같은 write helper를 재사용하지 않는다. source와
destination을 fresh disk read하고 다음을 전수 확인한다.

- frozen source SHA와 destination SHA
- 목표 tier·목표 label span이 정확히 하나라는 구조
- 새 label과 frozen Bareun/WSD sidecar의 exact 일치
- 교체 span 밖 prefix/suffix byte identity
- 4,286,046 derived와 817,310 `no_mfa_alignment`의 zero-drop 회계
- receipt·checkpoint·inventory의 exact-ID, byte 수, 경로와 SHA 일치
- `alignment_conflict`는 token 수와 word 수 차이의 표지이며 자동 실패가 아님

전수 실행 전 층화 파일럿은 최소한 다음을 포함한다.

- label changed / unchanged
- LF / CRLF / BOM 유무
- 한글, Praat 따옴표, 빈 문자열, 허용되지 않은 control character
- target tier 누락·중복, interval 누락·중복
- crash 직전/직후와 `-Resume`, 기존 destination 거부
- 현 writer와의 semantic equality, 일반 full parser 재개방, 실제 Praat 호환
- 실제 source/output 볼륨에서 worker 1/2/4와 SQLite transaction batch 크기 비교

worker 수와 batch 크기는 추정으로 고정하지 않는다. 파일 수·SHA·출력 의미가
같다는 감사 뒤 실제 처리속도와 저장소 안전선을 함께 보고 선택한다.

## 적용 경계

- 현재 `bareun_morph_textgrid_full_20260829`의 runner·config·manifest·output에는
  v2 코드를 섞지 않는다.
- 현재 v1은 완료 후 독립 SHA 감사와 외장 SSD copy-first Gate를 그대로 따른다.
- 다음 Bareun 엔진 갱신 또는 WSD TextGrid 전수 materialization 전에 별도 v2
  runner·auditor·tests·run ID·output root를 만든다.
- 파일럿이 실패하거나 성능 이득이 불명확하면 원본과 현재 완성본을 보존하고
  production을 시작하지 않는다.
