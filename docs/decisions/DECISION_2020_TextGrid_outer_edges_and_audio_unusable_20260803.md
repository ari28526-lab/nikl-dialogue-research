# 2020 TextGrid 바깥 경계와 청취 불가 음원 처리 결정

결정일: 2026-08-03 KST
적용 범위: 2020 공통 Jamo r2 생산 DB, 6-tier 생산 산출물, 연구자 검토본

## 문제

연구자 검토에서 TextGrid에 자연 무음 구간이 보이는 파일과 보이지 않는 파일이
섞여 있었고, 일부 tier만 경계가 있는 것처럼 보일 수 있다는 문제가 제기됐다.
또 16개 연결 검토 표본 중 3개는 연구자가 들어도 소리가 들리지 않았다.

## 전수 확인

`D:\mfa_tmp\2020\2020.db`를 수정하지 않고 868,187개 정렬 성공 발화를 전수
집계했다. 유표 word와 유표 phone의 발화 시작·끝 시점은 868,187/868,187,
100% 일치했다.

자연 무음의 존재는 파일별로 달랐다.

- 좌우 모두 자연 무음: 650,259
- 왼쪽만 자연 무음: 75,165
- 오른쪽만 자연 무음: 128,309
- 자연 무음 없음: 14,454

따라서 파일마다 빈 바깥 구간의 존재가 다른 것은 원음 차이이며 tier 손상이나
누락이 아니다. 핵심은 검토 화면 모양이 아니라 **연구 검색용 생산 tier의 경계
계약**이다. 생산 exporter는 다음 계약을 파일마다 검증한다.

- 모든 6개 tier는 0--xmax를 빈틈없이 덮는다.
- `utterance`, `utterance_orth_r`, `morph_analysis_utt`의 유표 레이블은
  같은 첫–마지막 유표 word span을 사용한다. 세 검색 tier의 경계는 완전히 같다.
- `phones_mfa`와 `phoneme_r_auto`의 모든 경계가 같다.
- 2020 DB에서는 유표 word와 phone의 바깥 발화 경계도 전수 일치한다.

2020 전수 6-tier 실물은 아직 내보내기 전이다. 그러므로 이미 잘못 생성된 전수
TextGrid를 수정하는 상황이 아니며, 이 전수 감사와 exporter gate를 통과한 뒤
처음 생성한다.

## 경계 처리 결정

1. 생산 TextGrid와 동반표는 원음의 `source_time`을 유지한다. 원음에 없는
   0.05초를 전수 생산 자료에 넣지 않는다.
2. 자연 무음이 없으면 tier 바깥 테두리 0 또는 xmax가 곧 발화 경계다.
   TextGrid 안에서는 한글 발화·철자 Roman·형태소 분석 문자열이 같은 유표
   발화 span에 있으므로 서로 조합해 검색할 수 있다. CSV/Parquet는 대량 검색과
   `utt_id` 연결의 정본이고 TextGrid는 같은 시간대의 정렬 문맥이다.
3. 연구자가 Praat에서 경계를 쉽게 확인하는 **검토용 복사본에만** WAV 좌우
   0.05초 무음을 추가하고 모든 tier를 같이 이동한다. 모든 tier에 0.05초와
   `xmax-0.05` 경계를 강제한다. 원시간은
   `source_time = review_time - 0.05`로 복원한다.
4. 형태소 문자열을 word·phone 경계마다 기계적으로 나누지 않는다. 그렇게 하면
   형태소 분석 정보가 음향 시간경계인 것처럼 보이는 거짓 정밀도가 생긴다.

Python으로 수정 검토본 4개 TextGrid를 다시 그려 확인했고, 4/4 파일의 6/6
tier가 좌우 0.05초 검토 경계를 모두 통과했다.

## 청취 불가 음원 결정

다음 3개는 디지털 0 음원이 아니라 매우 낮은 레벨의 신호가 남아 있었지만,
연구자 청취에서 소리가 들리지 않았으므로 `audio_unusable`로 기록한다.

| utt_id | RMS dBFS | 결정 | 범위 |
|---|---:|---|---|
| `SDRW2000000257.1.1.231` | -79.307 | approved | alignment_and_analysis |
| `SDRW2000000257.1.1.39` | -70.993 | approved | alignment_and_analysis |
| `SDRW2000000257.1.1.97` | -79.191 | approved | alignment_and_analysis |

이 3개는 현 DB에서도 이미 word+phone 정렬이 없는 발화이므로 성공 TextGrid를
삭제한 것이 아니다. 연구자 원본 Excel의 SHA-256은
`41bc6cd433add52248ef5fcf875238bf89d19d0b4d9ea60b0858c92c1826750b`이며,
정확한 3행 승인표와 함께 manifest에 묶었다.

나머지 표본 13개는 연결이 맞다고 확인됐다. 이후 연구자는 같은 보존 DB를
유지하고 진도를 내도록 지시했다. DB에서 다시 읽은 미정렬 363 ID와 원 후보표가
정확히 같음을 확인한 뒤, 청취 불가 3건은 `audio_unusable`, 나머지 360건은
`mfa_alignment_missing`으로 명시 승인했다. 기존 pre-MFA 1,887건과 합친 최종
계약은 2,250건이며 전수 MFA 재실행은 하지 않는다.

## 산출물

- 수정 검토본: `outputs/reviews/MFA_2020_REVIEW_SIMPLE_V2_20260803`
- Python tier 그림·검사: `outputs/reports/MFA_2020_TIER_BOUNDARY_AUDIT_FIXED_20260803`
- 2020 전수 DB 경계 감사:
  `outputs/reports/AUDIT_2020_FULL_DB_TIER_EDGES_20260803.json`
- 결합 승인 계약:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_export_20260803/2020`
- Dropbox 전달본은 임시 열람 사본이었다. 로컬 근거와 SHA가 보존됐으므로
  연구자가 Dropbox root에서 삭제해도 생산 계약에는 영향이 없다.

검토본 생성 전후 MFA DB 크기와 mtime은 같았고, MFA 재정렬은 수행하지 않았다.
