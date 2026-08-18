# NIKL dialogue research DB v1.0.0-rc1 — recovery sidecar

이 release는 RC0를 덮어쓰지 않는 append-only sidecar다. 첫 recovery shard 55건의 후속 상태와 연구자 수동 word·전사 16건의 active pointer를 추가한다. r3·6-tier·MFA DB는 변경하지 않았다.

D9 phone은 참고 전용이며, 수정 전사에 대한 형태소와 phone/phoneme은 별도 후속 Gate 전까지 pending이다. 따라서 RC1은 16건을 정렬 성공 본체에 소급 합산하지 않는다.
