# 구 MFA 산출물 외장 archive 압축 전환

작성일: 2026-07-28

수백만 개의 작은 TextGrid를 E:에 낱개로 복사하는 방식은 보존 목적에
비해 NTFS metadata I/O 비용이 지나치게 크다. 2026-07-28의 loose-file
Robocopy는 중단했으며 D: 원본은 삭제·변경되지 않았다.

새 보존 단위는 2020 TextGrid, 2021 TextGrid, 2021 MFA DB/temp, stale
temp, 실패 model clone의 항목별 `.7z`다. 각 archive는 다음을 모두
통과해야 한다.

1. D: `DATA_SSD`와 고정 source allowlist 확인
2. 생성 전후 원본 파일 수·총바이트 일치
3. 7-Zip CRC 전수 검사
4. archive 내부 파일 수·비압축 바이트와 원본 일치
5. 트리 안 모든 `*.db`의 생성 전후 SHA256 일치 및 manifest 기록
6. 완성 archive SHA256 기록
7. `.partial`에서 최종 이름으로 원자적 승격

새 스크립트는 원본 삭제 기능을 제공하지 않는다. E:는 보존 archive
읽기에는 사용할 수 있지만 MFA 실행·출력 root로는 사용하지 않는다.
구 `pre_jamo_20260728` loose-file 폴더는 불완전한 부분 사본이며 검증
archive가 아니다.
