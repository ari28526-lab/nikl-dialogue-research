# 런북: 어절(語節) 전량 재정렬 — phones 연결발음 교정 + 형태소 tier (2026-07-16)

## 왜 (문제 진단)
기존 정렬은 `.lab`을 **형태소 단위**로 넣어(make_labs), MFA가 형태소마다 따로 G2P →
phone 라벨이 **고립형**이 됨. 실측: 발화 `저는 여행 다니는 것을`의 `것을`이
`k ʌ t̚ ɨ ɭ`=**[걷을]**로 정렬됨(연음 [거슬] 아님). **형태소 경계를 넘는 음운현상
(연음·경음화·ㄴ첨가)이 phone 라벨에 안 담김** → 형태음운 변이(특히 ㄴ삽입) 분석 불가.

원인: "words tier를 형태소로" 하려고 형태소를 MFA에 그대로 먹였는데, 그러면 분절뿐
아니라 **발음(음소정보)까지 형태소 고립형**이 됨. 의도는 "어절 연결발음 + 형태소 정보".

## 무엇 (목적 B — 사용자 확정)
**한 파일에 4-tier**로 재생성:
| tier | 내용 | 출처 |
|---|---|---|
| words | **어절** | 신규 어절 MFA |
| phones | **연결 실제 발음**(것을→거슬) | 신규 어절 MFA |
| morphemes | **형태소 경계** | 기존 `06_textgrid_merged` words tier 재사용 |
| utterance | form | 01_bareun_raw |
- 결과: `D:\20_AUDIO\06_textgrid_eojeol`. 기존 `06_textgrid_merged`(형태소·구)는 **읽기
  전용 보존**(morphemes tier 소스 겸 "형태소 길이" 부차 레이어).

## 어떻게 (파이프라인, 재사용)
`.lab`만 형태소→**어절**(form 표층, 어절별 한글만)로 바꾸고 나머지는 기존 파이프라인 재사용.
**★ lab은 원래 make_labs처럼 wav 옆에 '제자리' 생성(하드링크 없음)** — 하드링크 코퍼스는
USB에서 느려 폐기(원래 정렬이 <3일이던 비결이 제자리 lab이었음).
스크립트(리포):
- `scripts/python/realign_eojeol_build_corpus.py` — form→어절 lab을 **wav 폴더에 제자리** 생성
  (코퍼스 = `03_wav/individual/{y}` 그대로)
- MFA: `mfa align D:\20_AUDIO\03_wav\individual\{y} korean_mfa korean_mfa out --num_jobs 4 --no_tokenization --clean --temporary_directory D:\mfa_eojeol\tmp --output_format long_textgrid` (모델·사전=1차와 동일 korean_mfa v3.0)
- `scripts/python/realign_eojeol_merge_output.py` — MFA출력+기존 형태소경계 → 4-tier → `06_textgrid_eojeol`
- 러너: `scripts/run_eojeol_realign.ps1` (연도별 lab→align→merge, 재개 가능: 연도 `.done` 마커)
- ETA: ~3~4일(제자리 lab). 병목=MFA 정렬 자체(줄일 수 없음). 추가 최적화 여지=병합을 MFA
  DB 직독으로(≈1일 절감, 단 리스크) — 현재는 검증된 long_textgrid 경로 사용.

## 실행 (밤샘)
```powershell
# 리포 루트에서
powershell -ExecutionPolicy Bypass -File scripts\run_eojeol_realign.ps1
```
- 연도별 순차. 중단 시 재실행하면 완료 연도(.done)·기존 산출 파일 건너뜀.
- 로그: `D:\mfa_eojeol\logs\`. **도는 동안 D: 읽는 다른 작업 금지(경합).**
- 완료 후: `06_textgrid_eojeol`가 음운변이 분석 주 레이어. paths.json `textgrid_eojeol`.

## 사전검증 (2026-07-16, 통과)
문법·임포트 OK / form_to_lab 어절 정상(것을 한 토큰) / 기존 형태소경계 파싱 OK.
한계: 숫자·외국어 어절은 lab에서 제외(기존 make_labs와 동일 동작, 회귀 아님).

## 남은 것
- [ ] 배치 실행(사용자, 밤샘) → 커버리지 재확인.
- [ ] 완료 후 A6(fetch_audio)·검색이 `textgrid_eojeol`을 쓰도록 점검.
- [ ] METHODS 3.5에 이 교정 반영(1차=형태소 고립형 결함 → 어절 재정렬로 교정).
