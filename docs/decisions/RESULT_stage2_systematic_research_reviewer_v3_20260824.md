# Stage2 체계적 연구 reviewer v3 — 구현·감사 결과

## 결과

- v1/v2를 수정하지 않고 `researcher_review_package_v3_systematic`을 새로 만들었다.
- 기존 v1 JSONL을 그대로 import할 수 있고 새 저장행은 append-only v2 schema다.
- 사례별 연구자 우선 메모 7개, 형태소·POS·운율·장르·자료품질·복수 membership
  필드와 현상별 최신 생각 집계·Markdown 내보내기를 추가했다.
- PT 전용 3판정(저해음 뒤 경음화·합성어 경음화·사이시옷)과 NAN 전용 2판정
  (후행 /ㄴ·ㅁ·삽입 n/, 기준층·운율층)을 별도로 제공한다.
- TextGrid 그림을 미리보기라고 명시하고 localhost whitelist helper를 통해 실제
  Praat에서 WAV+praat_work TextGrid를 여는 버튼을 추가했다. Praat는 설치하지 않았다.
- 4시간 선행연구 종합용 5단계 HTML, Markdown 템플릿, Claude Cowork prompt,
  gap register, candidate sampling frame을 묶었다.

## 문헌·표본 감사

- claim ledger: 156→173행, CLM-0157~0173 append.
- 신지영(2011)은 NAN의 직접 운율 영역 근거, Jun(1998)은 영역 논쟁·경계 단서
  불일치의 방법론 근거로 분리했다.
- 현재 84건은 탐색 표본이다. 특히 PT 12건은 compoundness probe, NAN은 /ㄴ/
  중심, LLN은 /ㄹ+ㄴ/ 중심이므로 균형 본표본으로 해석하지 않는다.

## 검증 결과

- 신규 v3 단위 테스트 7/7, 관련 Stage2 회귀 테스트 합계 26/26 통과.
- 독립 감사: manifest 274파일, exact 재사용 파일 256개, sample 84,
  phenomenon 7, claim ledger 173행 통과.
- 기존 사용자 JSONL 2행 parse·sample/summary 호환, SHA-256
  `142c64c092dd724c27daf72846afb2ecc174f136ed4a4bd428a8e1274ecf9a6a`.
- localhost Praat launcher의 sample whitelist·패키지 경로 이탈 거부 통과.
- 브라우저: PT→NAN 전용필드 전환, NAN 표본 경고, 4시간 HTML 5단계,
  콘솔 오류 0건 확인.
- v2 source manifest SHA는 전후
  `9a9c0ae7880971c32b16f33f1e3511bdf8d4da64d7560a86b5a3deee313356a1`로 동일.

## 하지 않은 일

- 연구자 청취·실현 판정, Praat 경계 수정, 원자료 수정, 자동 실현 판정,
  동결 query/config 승격은 수행하지 않았다.
