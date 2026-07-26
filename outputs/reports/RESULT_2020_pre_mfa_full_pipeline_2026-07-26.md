# 2020 pre-MFA·MFA 완료 결과

## 결론

2020은 CSV 생성부터 4-tier TextGrid staging까지 전 단계가 완료됐다.
2021–2025는 시작하지 않았다.

- pre-MFA CSV: 5,103,356발화·17,156세션, build success
- 2020 usable lab: 869,840
- 2020 MFA TextGrid: 866,196
- 정렬 coverage: 99.58%
- 기본+retry beam 난정렬: 3,644
- 난정렬 inventory: 3,644 ID, 215세션, WAV 존재 3,644/3,644
- 4-tier 생성: 866,196
- 병합 실패·form 누락·morpheme tier 누락: 모두 0
- 독립 전수 열거: 866,196, 0바이트 0
- 세션 폴더: 2,231
- 경계 표본 15개: 네 tier 모두 0초→전체 duration, 실패 0
- 2021 temp/output/staging/marker: 모두 없음
- 기존 TextGrid 정본: 자동 승격·덮어쓰기 없음

최종 staging:

`D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2020`

## 해석 주의

“2020 완료”는 파이프라인 단계가 모두 끝났다는 뜻이다. 모든 발화가
정렬됐다는 뜻은 아니다. 3,644건은 ID를 추출해 확대 beam으로 부분
재시도해야 한다.

재시도 ID:

`outputs\tables\2020_mfa_missing_textgrid_ids_20260726.csv`

`phones` tier는 MFA가 만든 대략적인 시간 분절이며 음운현상의 실제
실현 여부를 자동 판정하는 값이 아니다. 최종 판정은 WAV·TextGrid를
연구자가 직접 확인하는 흐름을 유지한다.

## 가장 큰 병목

2020 MFA TextGrid export가 약 15시간 57분 걸렸다. worker 4개를
의도했지만 실제로는 worker 1개가 사실상 순차 처리했다. 2021부터
동일 실행을 반복하기 전에 queue 종료 경쟁 조건을 수정하고
파일럿 benchmark를 해야 한다.

그 밖의 우선 개선은 다음과 같다.

1. 정상 일시정지를 `failed`가 아닌 `paused`로 기록
2. 원 MFA output 보존/정리 정책 결정
3. 3,644 난정렬 ID와 318/544/53건 원인 교차표 생성
4. JSONL heartbeat와 chunk manifest 추가
5. 4-tier 병합의 세션 단위 병렬화 검증

상세 근거와 최소 재실행 설계:

`docs/decisions/AUDIT_2020_pre_mfa_full_pipeline_2026-07-26.md`
