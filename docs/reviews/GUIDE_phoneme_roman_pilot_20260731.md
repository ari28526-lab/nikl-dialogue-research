# 로마자 음소 보조층 파일럿 — 아침 검토 안내

## 지금 열 파일

```text
C:\Users\ari30\Dropbox\MFA_RESEARCH_SCHEMA_REVIEW_12_20260731\
PHONEME_ROMAN_PILOT_PORTABLE_20260801.xlsx
```

PowerShell 실행은 필요 없다. 대량 MFA도 아직 시작하지 않는다.
이 portable workbook의 WAV·기존 4-tier·새 5-tier 링크는 모두 같은
Dropbox 폴더의 파일명을 사용하므로, 폴더 전체가 동기화된 다른
컴퓨터에서도 열려야 한다.

## 한 번에 한 행씩 보는 순서

1. `발화_검토` 시트 1행을 찾는다.
2. `WAV`를 열어 같은 발화인지 확인한다.
3. `기존_4tier`를 열어 기존 `phones_mfa`를 확인한다.
4. `새_5tier`를 열어 마지막 `phoneme_r_auto`를 확인한다.
5. `MFA_phone_로마자열`과 `자동_음소_로마자열`이 이해 가능한지 본다.
6. `phone_범주`, `철자_예측_참조`, `경계`만 먼저 입력한다.
7. 문제가 있을 때만 `대응_세부` 시트에서 같은 `utt_id`를 필터한다.

첫 행 `혹시 요즘`의 예상 핵심은 다음이다.

```text
phones_mfa IPA:         ɸʷ o k ɕ͈ i | j o dʑ ɨ m
phone_class_r_auto:     H O G SS I | Y O J EU M
phoneme_lexical_r_auto: H O k SS I | Y O J EU m
```

`G/k`, `M/m`은 초성/종성 위치 표기 차이 때문에
`position_compatible`로 처리된다. 새 tier에서 `?`로 시작하는 것은 자동
대응이 완전 일치하지 않은 구간이다.

## 무엇을 판정하지 않는가

- 이 단계에서 음운현상의 실제 실현 여부를 판정하지 않는다.
- 자동 음소 후보가 실제 발음의 정답인지 승인하지 않는다.
- 새 5-tier가 기본 TextGrid가 되는 것도 아직 승인하지 않는다.

판정 대상은 검색용 로마자와 철자·예측발음 참조가 실용적인지, 기존 경계가
보존됐는지다.

## 결합검색 데모와의 순서

먼저 이 workbook 1행을 확인한 뒤, 같은 폴더의
`COMBINED_SEARCH_DEMO.xlsx`에서 Q1 첫 결과를 본다. 두 검토가 모두 끝나면
형태소/철자 환경 검색 결과와 post-MFA 로마자 phone 보조층을 같은 후보
추출 workflow로 연결할 수 있다.
