# 바른 v3.1.0+ 형태소·WSD CSV 파일럿 P1 결과

검증일: 2026-08-28

결론: **P1 통과, CSV-only 전수 runner 준비 완료·미시작**

## 무엇을 검증했는가

바른 클라우드 서버 v3.1.0 이상에서 기존 형태소 분석을 재사용하지 않고 형태소
분절과 품사를 새로 계산했다. 같은 요청에 `with_sense=true`를 켜 동형이의어
의미번호·우리말샘 식별자·확률을 함께 받았다. `bareunpy` 2.1.0은 Python
클라이언트 버전이며 서버 엔진 버전과 구분한다.

입력은 완결된 과거 CSV의 `utt_id`, `speaker_id`, `form`만 사용했다. 과거
`tagged`, `n_morphs`는 API 입력에 쓰지 않았다.

공식 근거는 바른의
[동형이의어 의미 구분 API](https://bareun.ai/docs/howtouse/homonym-sense/)와
[bareunpy 2.1.0 변경사항](https://github.com/bareun-nlp/bareunpy)이다. 후자는
WSD에 바른 서버 v3.1.0 이상이 필요하고 현재 `api.bareun.ai`에서 사용할 수
있다고 명시한다.

## P1 결과

| 항목 | 결과 |
|---|---:|
| 표본 | 240발화, 2020–2025 각 40 |
| 선택 원 CSV | 24개, 앞·중간·뒤 결정 표본 |
| 입력 공백 어절 | 1,324 |
| 새 응답 token | 1,324 |
| 새 형태소 | 2,530 |
| WSD가 붙은 형태소 | 776 |
| 중복 제거 의미 항목 | 397 |
| batch | 10발화×24 |
| batch 재시도 | 0 |
| 단건 폴백 | 0 |
| 실행 시간 | 약 186.8초 |
| 원 CSV SHA 변경 | 0 |
| TextGrid·WAV 접근 | 0 |
| 독립 감사 | `passed=true`, 오류 0 |

외장하드 결과:

```text
D:/10_LAYERS/11_bareun_wsd/bareun_wsd_full_20260828/pilot_p1_20260828
```

## 실패에서 확인한 운영 계약

처음 사용한 `AnalyzeSyntaxList(taglist)` 40발화 batch는 세 차례
`Service Unavailable`로 실패했고, 두 번째 시도는 사용자 중단 뒤 프로세스를
종료했다. 두 시도의 `.building` 표본표는 실패 증거 폴더로 보존했으며 완성본으로
승격하지 않았다.

과거 510만 발화 전수에서 성공한 `AnalyzeSyntax(tags)` 경로로 되돌린 뒤 P1이
통과했다. production 전 성능 시험에서는 `tags` 40발화가 40/40, 약 5.50초,
7.27발화/초였다. 반면 4개의 40발화 batch 동시 호출은
`Service Unavailable`을 일으켰다. 따라서 production은 worker 1, batch 40으로
고정한다.

## 출력 schema와 용량

각 원 CSV마다 다음 세 압축 CSV와 receipt를 별도 디렉터리에 만든다.

- `utterances.csv.gz`: 발화 ID·화자·원문·새 분석 회계
- `morphemes.csv.gz`: 새 token·형태소·품사·UTF-32 offset·확률·WSD 필드
- `sense_dictionary.csv.gz`: 의미번호·우리말샘 식별자·뜻풀이 중복 제거표
- `RECEIPT.json`: 원 CSV SHA와 세 출력의 byte·SHA·행 회계

P1 단순 전수 환산은 일반 CSV 약 9.38 GiB, gzip CSV 약 2.00 GiB다. D: 여유는
약 57.67 GiB여서 CSV-only 15 GiB gate를 통과한다. TextGrid 등 추가 파생의
80 GiB gate는 별개로 계속 닫혀 있다.

## 실행·재개·감사

전수 runner는 파일별 `.building`에서 작성하고 receipt까지 완성한 뒤 디렉터리를
원자 승격한다. 중단 뒤 `-Resume`은 완료 receipt와 원·출력 SHA가 모두 맞는
파일만 건너뛴다. 전수 완료 조건은 17,156파일, 5,103,356발화,
27,646,899입력 어절의 zero-drop이다.

PowerShell 5.1 공통 safety 74파일, runtime compatibility 74스크립트와 대상
`-PreflightOnly`가 모두 통과했다. 현재 상태판은 `not_started`이며 대량 API
호출은 사용자가 실행 명령을 직접 입력하기 전에는 시작하지 않는다.
