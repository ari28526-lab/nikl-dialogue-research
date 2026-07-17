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
- MFA: `mfa align D:\20_AUDIO\03_wav\individual\{y} korean_mfa korean_mfa out --num_jobs 4 --no_tokenization --clean --temporary_directory C:\mfa_tmp --output_format long_textgrid` (모델·사전=1차와 동일 korean_mfa v3.0; **temp는 C: SSD** — 아래 가속 결정 참조)
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

## 아카이브 재활용 검토 — 재활용 불가 확정 (2026-07-16 아침)
"2020~2024는 예전에 어절로 정렬했으니 재활용하면 되지 않나?"를 실물로 검토한 결과:
- **실제 정렬 산출물 2개 모두 phones가 형태소 고립형**:
  - 현재 `20_AUDIO/05_mfa_output/2020` : 것을 phones = `k ʌ t̚ ɨ ɭ` = **[걷을]**
  - 아카이브 `90_ARCHIVE/06_textgrid_merged_구판_2020`(6-tier: words/phones/form/
    pronunciation/morphs/speaker) : 것을 phones = **[걷을]** (동일)
- **구판의 `pronunciation` tier엔 연결발음이 텍스트로 존재**: 것을 = `G EO S EU L`
  = **[거슬]**. 즉 어절 연결발음을 *계산은* 했으나(사용자 기억의 근거), **시간정렬은
  안 된 텍스트**일 뿐. 시간정렬된 phones는 2020~2024도 형태소 고립형.
- 옛 lab(`04_00_04_mfa_input_구식`)·`00_이전시도`는 USB에서 파일 접근조차 타임아웃날
  만큼 느려 전수 확인 불가했으나, **실제 정렬 산출물 2종이 모두 고립형**이므로 결론 불변.
- **결론**: 시간정렬된 연결 phones를 가진 재활용 가능 산출물은 없음 → **재정렬 불가피.**
  (재활용으로 시간 절약 불가. USB+585만 파일로 인해 전량은 multi-day, 하드웨어 한계.)
- 근본 가속은 **wav을 빠른 디스크로 이전(~290GB 필요)**뿐 — 별도 판단 대기.

## 가속 결정 (2026-07-17)
**SSD 구매 안 함**(사용자 결정, 비용) → 무료 가속만 적용 + 병목 실측 후 추가 판단:
1. **MFA temp → `C:\mfa_tmp`(SSD)**: MFA는 정렬 반복 중 wav이 아니라 temp의
   특징값(MFCC)·PostgreSQL DB를 계속 읽음 — USB에 두면 그게 병목. wav은 특징
   추출 때 1회만 읽음. 연도당 temp ~20-35GB, `--clean`으로 연도마다 비워짐.
   러너에 C: 여유 30GB 가드 추가(부족 시 중단).
2. **lab 생성 scandir 최적화**: 발화별 `exists()` 2-3회(각 USB 왕복, "12발화/s"의
   유력 주범) → 세션당 폴더 목록 1회. 510만 발화 기준 메타데이터 왕복 수백만 회 제거.
3. **Defender 제외 + 절전 해제**: `scripts/setup_mfa_speed_once.ps1` (관리자 1회).
   D:\20_AUDIO·D:\10_LAYERS·D:\mfa_eojeol·C:\mfa_tmp·miniforge3 제외.
4. **병목 계측 파일럿**: `scripts/run_pilot_bottleneck.ps1` — 2020 50세션(~5천 발화)
   복사본(D: 유지)으로 본 배치와 동일 설정 MFA를 돌리며 5초 간격 CPU%·디스크
   사용률 CSV 기록. **판정 규칙**: 정렬 구간 CPU ≥85% 지속 = CPU 병목(디스크
   대책 무의미, 남는 카드는 SAT off뿐 — 품질 대가라 비권장) / CPU 낮고 D: 바쁨
   = I/O 병목(→ C: 분기 청크 스테이징 검토). 발화/s 실측으로 본 배치 ETA 재계산.
- 검토했으나 보류: SAT(화자적응) off(~절반 절감이나 경계 정밀도 하락 — 길이 연구라
  비채택), 병합 MFA DB 직독(~1일 절감, 미검증 리스크), C: 스테이징(파일럿 결과 대기).

## 남은 것
- [ ] `setup_mfa_speed_once.ps1` 관리자 실행(사용자, 1회) → 파일럿 실행 → 병목 판정.
- [ ] 배치 실행(사용자, 밤샘, 여러 날) → 커버리지 재확인.
- [ ] 완료 후 A6(fetch_audio)·검색이 `textgrid_eojeol`을 쓰도록 점검.
- [ ] METHODS 3.5에 이 교정 반영(1차=형태소 고립형 결함 → 어절 재정렬로 교정).
- [ ] (선택) wav 빠른 디스크 이전 검토(전량 재정렬 가속 유일 수단).
