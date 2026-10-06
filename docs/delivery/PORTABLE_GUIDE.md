# 연구 자료 직접 열기

> 2026-10-07: 음성 미확보·대응 미확정 1,436개를 명시한 승인 범위의 로컬 배포 준비가 완료됐습니다. [완료·복구 범위](RECOVERY_AND_COMPLETION_20261007.md)를 먼저 읽고, 실제 패키지의 `START_HERE_COMPLETED.md`와 `DELIVERY_FINAL.json`을 기준으로 확인합니다. 아래 준비 단계 설명은 자료 구조와 단계별 검증 범위를 설명하는 이력입니다.

이 안내와 도구 묶음은 배포 준비본입니다. 자료 전체 전달 완료는 패키지 루트의 DELIVERY_FINAL.json으로 확인합니다. 코드 표본 검증, COPY_FINAL.json, 자료별 FINAL.json은 각각 범위가 다릅니다.

## 여는 순서

1. 이 GUIDE.md와 source_inventory.json에서 자료의 역할과 패키지 내부 위치를 확인합니다. 경로는 패키지 루트 기준입니다. research_tools_v2 폴더만 다른 곳으로 옮겨도 코드 설명은 열리지만, 실제 조회에는 자료 패키지가 필요합니다. 이전 research_tools_v1은 준비 이력으로 보존합니다.
2. 최신 분석은 latest_release/bareun_3.2_20260926/production/discourse_json의 담화 JSON을 엽니다. modu는 원 document 단위, seoul은 녹음 240조각, seoul_interviews는 상위 40인터뷰입니다. 빈 구간과 분석 없는 구간도 원 순서에 남습니다.
3. 특정 발화는 examples.json의 문맥 조회 명령에 실제 ID를 넣어 찾습니다. common_parquet/discourse는 조회용이며 원 JSON을 대체하지 않습니다. metadata/semantic_links/FINAL.json 생성 후에는 발화 ID로 음성·TextGrid·정렬 동반표·분석·역사 보완의 연결을 함께 조회할 수 있습니다.
4. 세종·문맥사전·의미 후보 근거는 historical_versions 및 common_parquet/supplement에서 확인합니다. 3.1 보완 결과를 3.2의 판정으로 읽지 않습니다.
5. 연구 질문별 코드와 결과는 별도 출력 폴더에 저장합니다. 패키지의 원본이나 기존 버전을 직접 고치지 않습니다.

supplement_reader/index.html에는 실제 저장 결과 7개와 사용판 등록 출처 49건을 넣었습니다. 형태소 원행, 기계 선택·충돌·보류, 세종 미해결, 의미 후보의 필드와 근거를 펼쳐 볼 수 있습니다. 원 표본과 당시 생성 시각을 보존했으며 새 전수 분석 결과로 표시하지 않습니다. examples.json은 명령 인자 템플릿이고 supplement_reader/examples.json이 실제 저장 표본입니다.

구형 TextGrid는 metadata/historical_textgrid_links/FINAL.json 완료 후 query_delivery_historical_textgrid.py로 발화 ID를 조회합니다. --verify-sha는 선택한 파일 하나만 검증합니다. no_mfa_alignment와 no_historical_analysis_record를 구분하며 후자를 정렬 실패로 세지 않습니다. 원 구형 목록의 행 순서를 새로 매긴 historical_inventory_ordinal_zero_based는 원 분석의 source_row_index와 다릅니다.

## 버전과 판정

| 자료 | 역할과 읽을 때의 한계 |
| --- | --- |
| 최신 바른 3.2 계열 | 공급자가 서버/모델을 선언한 실행입니다. 개별 응답 버전과 실행 전체 모델 불변은 미확인입니다. 서울 with_sense=true, 모두 false입니다. |
| 3.1 기본 분석 | 당시 저장 CSV/DB와 CSV에서 내보낸 JSON입니다. 새 JSON 생성 시각과 과거 분석 시각은 다릅니다. CSV 기반 JSON을 원 API 응답이라고 부르지 않습니다. |
| 문맥사전 적용판 | 저장 규칙과 근거에 따른 기계 적용 결과입니다. 원 DB·규칙·영수증과 새 export를 구분합니다. |
| 세종 applied_r02 | 적용/미해결 결정과 근거를 저장한 별도 역사 버전입니다. |
| 의미 후보 | 후보·점수·출처·보류를 보존합니다. 인간 확정 정답이 아닙니다. |
| 비교/수정 검토 | 배열 차이와 확정 기술 오류를 구분합니다. 언어학적 차이는 검토 대상으로 남습니다. 저장 응답 재현에서 확정 추출 수정은 0건이었습니다. |

## 필드와 좌표

- utterance_id/utt_id는 원 발화 연결 키입니다. 발화 ID와 담화/코퍼스/버전을 함께 사용합니다. 숫자처럼 보여도 문자열을 유지합니다.
- turn_order, 원 배열 순서, _source_row_index는 자료마다 정의가 다릅니다. 표본 조회 결과를 원문 순서와 대조하며 임의로 0/1 기반을 통일하지 않습니다.
- form 및 원 JSON payload는 원문과 원 null/빈 문자열을 보존합니다. CSV 기반 Parquet의 원 열은 문자열이며 명시적 계산 열 _delivery_typed_를 구별합니다.
- start/end 등 원 시간은 원 음성 좌표입니다. 잘린 WAV의 clip-local 시간과 원 녹음 시간은 구별합니다. 없는 절대시각이나 면담자 개인 ID를 만들지 않습니다.
- 형태소의 문자 좌표, 원문 좌표, 음성 구간 시간은 서로 다른 좌표입니다. 형태소 순번을 어절이나 타임스탬프에 대응시키지 않습니다.
- source_export/source_sha256/source_row_index/item_json은 저장 근거를 다시 찾기 위한 필드입니다. SQLite storage type과 BLOB base64는 원 값 보존에 사용합니다.
- source_discourse 및 references의 path는 패키지 상대경로이고 sha256/bytes는 연결 대상의 기록값입니다. 과거 원 자료 안의 절대경로는 provenance이며 휴대 가능한 조회 경로가 아닙니다.

## 음성과 TextGrid

음성 클립 복사는 독립적인 로컬 배포 묶음에서 재생할 수 있도록 하는 최초 복사입니다. 이후 분석 수정 때 동일 음성을 다시 복사하지 않습니다. 모두의 새 alignment_only.v1은 5층이고, 서울 원본은 7층입니다. 모두의 과거 일반 TextGrid는 6층이며 morph_analysis_utt는 구형 발화 전체 분석 문자열입니다. 세종/의미 보완이 그 층에 반영됐다고 가정하지 않습니다. 정렬 없는 817,310 분석발화도 CSV·JSON·연결 목록에 남습니다.

모두의 전체 원 JSON 구간 5,157,997개와 분석발화 5,103,356개, 정렬 4,286,046개는 분모가 다릅니다. 서울 128,313구간도 분석발화 수와 다릅니다. H 원 PCM 두 표본의 WAV payload 일치는 전수 원 PCM 보존이나 담화 전체 음성 확보 증거가 아닙니다. 제공 범위 확인이 남아 있습니다.

## 설치와 실행

Python 3.13 및 PyArrow 21.0.0, R 4.6.1 및 Arrow 25.0.1 환경에서 검증했습니다. Python Parquet 조회에는 requirements.txt가 필요합니다. R은 arrow, jsonlite, dplyr, tidyselect가 필요합니다. 자동 설치나 현재 분석 환경 변경은 하지 않습니다. 별도 환경을 준비하고 실행 파일과 라이브러리 경로를 지정합니다. 수정판 관리 도구는 Windows의 msvcrt 잠금을 사용하므로 현재 검증 범위는 Windows입니다.

scripts/python과 scripts/R의 상대 배치를 유지합니다. examples.json은 실행 인자 배열이며 셸 명령 문자열이 아닙니다. PACKAGE, OUTPUT, 실제 발화/담화 ID를 채운 뒤 subprocess 등으로 실행합니다. 출력은 패키지 밖 별도 경로를 권장합니다.

query_delivery_parquet의 --max-files는 작은 실행 범위를 제한합니다. 0은 전체입니다. query_delivery_tabular와 R 집계 예제는 전체 해당 표를 읽으므로 가벼운 상태 확인에 사용하지 않습니다. 문맥/근거 조회도 선택한 파티션을 읽으며 즉시 응답 시간을 보장하지 않습니다.

## 수정 시 반복 비용

최초 패키지 검증 이후 update_delivery_revision으로 명시적 변경 파일 목록만 별도 수정판에 기록합니다. 기본판과 과거 수정판은 보존합니다. query_delivery_links의 --revision으로 수정판을 명시적으로 선택합니다. 바뀌지 않은 음성/TextGrid는 그대로 참조합니다. 변경된 원 JSON은 연결 문서/영수증도 일치해야 조회됩니다.

수정판 R 조회는 Python과 경로 해석/SHA 로직을 공유한 뒤 R에서 선택 원 JSON의 ID·값·순서를 독립 대조합니다. 독립 R 경로 해석/SHA 검증은 아닙니다. 변경된 담화와 Parquet만 재생성하는 상위 연결은 아직 구현 중이며 자동 증분 갱신 전체가 완성됐다고 보지 않습니다.

## 아직 남은 최종 확인

전수 복사와 독립 SHA, 연결 색인, 원음성 제공범위, 구형 TextGrid 발화 연결, 코드/안내 최종 동봉, 실제 전체 패키지의 Python/R 동일 작은 질의 및 다른 루트 재열기, 결합 DELIVERY_FINAL 검증이 남아 있습니다. 이 안내는 준비본이며 단계 완료 때 갱신합니다.
