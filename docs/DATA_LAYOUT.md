# 데이터 배치도 — r2 생산 기준

최종 갱신: 2026-08-05 KST

자산의 존재·완료 상태는 [ASSETS_LEDGER.md](ASSETS_LEDGER.md)가 정본이다. 이
문서는 현재 생산에서 사용하는 좌표와 폴더 역할만 설명한다.

## D: DATA_SSD

```text
D:\
├─ 00_RAW                         원 JSON·reference, 수정 금지
├─ 10_LAYERS
│  ├─ 01_bareun_raw               연도·세션 형태소 CSV
│  ├─ 05_search_master            동결 510만 발화 입력
│  ├─ 09_morph_search_v3_staging  pre-MFA 조합검색 7표
│  └─ 10_pronunciation_reference  사전 발음 registry·연결·감사 파생층
├─ 20_AUDIO
│  ├─ 03_wav                      원 WAV·LAB, 수정 금지
│  ├─ 04_wav_id_recovered_staging 2020 MFA 전용 파생 WAV
│  └─ 08_textgrid_research_v2_staging
│                                  신규 r2 6-tier·동반표(2020 완료)
├─ mfa_common_pron
│  └─ releases\common_pron_mfa_r2_20260728
│                                  현재 공통 Jamo r2
├─ mfa_eojeol                     marker·lock·log·계약
├─ mfa_tmp                        D: 선택 시 연도별 MFA 임시 DB
└─ mfa_eojeol_out                 legacy export 폴백 경로
```

구 `06_textgrid_merged`와 `06_textgrid_eojeol`은 현 6-tier direct-DB 생산의 입력이
아니다. E: archive 후 D:에서 정리하며, 상세 이력은
`archive/ARCHIVE_MANIFEST_20260802.md`에 둔다.

## C: 저장소

```text
C:\Users\ari30\research\2026_summer_research
├─ config      경로·schema
├─ scripts     재현 가능한 실행기
├─ docs        현재 정본과 방법론
├─ outputs     작은 보고서·검토표·manifest
├─ logs        실행 로그
└─ work        재생성 가능한 임시 작업
```

대형 WAV·TextGrid·MFA DB는 Git에 넣지 않는다.

2020은 `08_textgrid_research_v2_staging\2020`에 TextGrid 868,187개와 동반표
4개를 완성했고 독립 감사·24개 표본·Gate B를 통과했다. 2021도 1,371,883개
TextGrid·동반표·독립 전수 감사·DB 표본 재수출을 완료했고 연구자 표본 Gate를
진행 중이다. 2022–2025는 승인 제외 계약과 LAB marker까지 준비됐지만 신규 MFA
결과는 아직 없다.

`10_pronunciation_reference`는 기존 MFA phone을 바꾸는 사전 폴더가 아니다.
우리말샘 `pron_1/pron_2`와 명시적으로 구분한 legacy 기계 fallback을 한 번만
저장하고, 연도별 형태소 occurrence와 ID로 연결해 규칙 예상형·MFA 입력 phone과
비교하는 재사용 가능한 참조층이다.

## E: archive

```text
E:\READ_ONLY_ARCHIVE\2026_summer_research\<archive_id>
```

과거 산출물은 항목별 압축본과 manifest를 함께 둔다. archive 검증 전에는 D:
대응 원본을 없애지 않는다. E: archive는 현재 생산 입력으로 자동 선택하지 않는다.

## 발화 좌표

```text
utt_id     = SDRW2000000521.1.1.175
session_id = 첫 점 앞 SDRW2000000521
year       = session ID의 연도 코드 → 2020
발화 파일  = <root>\<year>\<session_id>\<utt_id>.<ext>
```

2020은 원 배포 WAV의 ID 밀림 때문에 MFA에서만
`04_wav_id_recovered_staging\individual\2020`을 사용한다. 2021–2025는 원
`03_wav\individual\<year>`을 사용한다. resolver는 2020 passed contract가 없으면
원 WAV로 조용히 fallback하지 않는다.

## 연구 출력 좌표

- 원자료 좌표: 발화·어절·형태소·기호 검색 7표
- MFA 좌표: word/phone interval과 6-tier TextGrid
- post-MFA 좌표: 발화·word·phone·QC 동반표 4개
- 연구자 판정 좌표: 선별 bundle의 수동 실현 여부·KOINA·보조모델

이 좌표들을 하나의 시간경계로 합치지 않는다. `morph_analysis_utt`는 발화 전체
span에 표시하는 형태소 검색 문자열이지 자동 음향 형태소 경계가 아니다.
