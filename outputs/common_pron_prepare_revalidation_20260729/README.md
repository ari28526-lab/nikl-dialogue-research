# 공통발음사전 r2 prepare 코드 계약 재검증

- 검증일: 2026-07-29
- 대상 release: `common_pron_mfa_r2_20260728`
- 기존 prepare builder SHA-256:
  `c93648bd045047b0daa22cb0ce6b94e1f5fcb966e1fddd29de1d8ae4c5d361b3`
- 현재 builder SHA-256:
  `b477c9b49620d8a829cc0e390359a142d4535c694b3bd1719bc4fb5d22e7f420`

현재 코드로 prepare 단계를 별도 경로에서 다시 실행한 뒤 기존 release와
다음을 비교했다.

1. 입력 5종의 byte 수와 SHA-256
2. 정책, G2P·phone·어휘 계약 및 전체 count
3. OOV inventory, grapheme audit, Jamo 보조 입력 3종
4. 35개 G2P 입력 shard 각각의 행 수, byte 수, SHA-256

비교 결과 차이는 0건이다. 따라서 기존 prepare 산출물을 다시 만들거나
이미 검증한 G2P shard를 폐기하지 않고, 현재 downstream 검토·최종화 코드로
이어갈 수 있다. 실행 시에는 전환 registry와 이 evidence manifest 자체의
SHA-256도 다시 검증한다.

실제 비교 증거는
`isolated_current_prepare_manifest.json`에 보존한다. 별도 재생성 경로의
대용량 임시 파일은 최종 사전 입력으로 사용하지 않는다.
