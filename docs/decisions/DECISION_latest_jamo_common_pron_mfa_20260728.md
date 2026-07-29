# 최신 Jamo 공통 발음사전·MFA 기준 결정 — 2026-07-28

## 연구 목적과 불변 원칙

이 파이프라인의 목적은 CSV에서 형태소 또는 표기상 음운 환경을 검색해
해당 WAV·TextGrid를 연결하고, KOINA 운율 분석과 연구자의 청취·시각
판정으로 실제 실현을 분석할 수 있는 2020–2025 공통 인프라를 만드는
것이다. G2P phone은 실현 판정값이 아니라 MFA 정렬을 위한 사전 phone이다.

- `D:\`는 유일한 메인 작업·실행·최종 산출물 드라이브다.
- 외장 HDD는 구결과와 실패 증거의 보조 archive이며 실행 root가 아니다.
- CSV, 형태소 분석, 원 WAV, 원 LAB은 이번 MFA 재실행에서 바꾸지 않는다.
- 2020–2025 최종 MFA는 동일한 acoustic·dictionary·G2P·phone inventory와
  동일한 실행·QC 계약을 사용한다.
- 우리말샘 발음은 검색용 CSV 보조열에 유지하고 MFA 생산 사전에 자동
  발음 변이로 섞지 않는다.
- wav2vec2 phone은 연구 후보를 좁힌 뒤의 별도 보조열이며 canonical MFA
  phone이나 연구자의 실현 판정을 대체하지 않는다.

## 최종 모델 결정

기존 계산비용은 고려하지 않고 연구 정합성·일관성·재사용성을 기준으로
다음 묶음을 채택한다.

1. 공식 `MontrealCorpusTools/korean_mfa` Hugging Face 저장소
2. commit `0091ffa1f1ef7df380a4f799b3fb5bc80c3f65cd`
3. acoustic `v3.3.0`, train date `2026-05-29`
4. G2P `v3.2.0`, `unicode_decomposition=true`인 Jamo 입력
5. 같은 commit의 `korean_mfa.dict`와 `rules.yaml`
6. acoustic–G2P phone inventory 107개 완전 동일

동결 생산 묶음:

`D:\mfa_common_pron\models\frozen_korean_mfa_acoustic_3.3.0_g2p_3.2.0_0091ffa1`

| 구성 | SHA256 |
|---|---|
| acoustic zip | `94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c` |
| Jamo G2P zip | `4df7c5fa90da1f401e7a44af360be56158a581a54202e38baedeca53cfed38ff` |
| dictionary | `49e223fddb518bc441baa4cb9fec1a108e80dae9a2b54e5834dbff30e89c7d34` |
| phone-set 정렬값 | `6fbbb2cf1853573e0c387b286ddabfe6073ad64e42282317f73fdef95418940d` |

기계 판독 manifest는
`outputs/reports/korean_mfa_latest_jamo_bundle_20260728.json`이다.

## 채택 과정에서 잡힌 실패

### 1. 구 음절 G2P의 숨은 `spn`

구 음절형 G2P는 866,691 OOV 중 5,176개, 654개 음절을 strict inventory
밖으로 판정했다. MFA는 과거 실행에서 이를 실패로 중단하지 않고 `spn`으로
흡수했다. 2021 DB에서 `갭·깻잎·랩을·쏴·아팠던·얜·여쭤보고·쪘어·텀이·힘듦이`
모두 `word_type=oov`, `pronunciation=spn`임을 직접 확인했다.

따라서 구 2020·2021은 최종 기준으로 승격할 수 없고 구기준 baseline으로
보존한 뒤 최신 공통 묶음으로 재실행한다.

### 2. 내장 downloader의 거짓 갱신

MFA 3.4.0에서 `mfa model download ... --force` 세 명령은 exit 0이었으나
acoustic·dictionary·G2P의 바이트와 SHA256이 갱신 전과 완전히 같았다.
출력 성공이나 exit code만으로 최신 모델 확보를 선언하지 않고
version·commit·SHA256을 hard gate로 사용한다.

### 3. Windows CRLF로 인한 최신 G2P 로드 실패

첫 Hugging Face clone은 Git 자동 줄바꿈 변환 때문에 `phones.sym`에 CRLF가
들어갔다. OpenFST는 첫 label을 `0\r`로 읽고 실패했다. 공식 저장소를
`git -c core.autocrlf=false clone`으로 다시 받아 symbol 파일의 CR=0을
확인했다. LF clone과 동결 zip의 동일 10단어 출력 SHA256은
`236f23d2f6424ea9661f0ca965833e57a4324824274e29d3142bcd3d315a08e2`다.

### 4. 최신 Jamo의 복합 종성 `ㄽ`

최신 Jamo를 866,691 구 OOV에 전수 적용하기 전 grapheme gate를 실행한
결과 미지원은 네 어절뿐이었다.

- `외곬수적인`
- `외곬을`
- `외곬의`
- `천구백칤비육`

공통 원인은 NFKD 종성 `ᆳ`(U+11B3) 하나다. 다른 모델이나 `spn`을 섞지
않고 Jamo 입력 정규화에서 `ᆳ → ᆯ(U+11AF)+ᆺ(U+11BA)`으로 완전 분해한
뒤 같은 v3.2.0 rewriter를 쓰는 방향을 채택한다. 이 규칙 외 미지원
grapheme가 나오면 중단한다.

이 네 어절을 임시 `spn`으로 둔 채 MFA를 먼저 실행하지 않는다. 정상 OOV의
G2P 계산은 병행할 수 있지만, 공통사전 `missing=0`, `spn=0`, acoustic
inventory 이탈=0 전에는 연도별 MFA 정렬을 시작하지 않는다.

### 2026-07-29 네 후보 예비 검토와 원본 추적 계획

`03_review/jamo_ls_researcher_review.csv`의 실제 네 후보를 읽기 전용으로
확인했다.

| 표층형 | 완전분해 model input | 현재 같은-model phone | 예비 판정 |
|---|---|---|---|
| `외곬수적인` | `외골ᆺ수적인` | `w eː ɡ o ɭ sʰ s u dʑ ʌ ɟ i n` | 원표층·경계 확인 필요 |
| `외곬을` | `외골ᆺ을` | `w eː ɡ o ɭ sʰ ɨ ɭ` | 제14항의 ㄽ 연음 시 ㅅ 된소리와 대조 필요 |
| `외곬의` | `외골ᆺ의` | `w eː ɡ o ɭ t̚ ɰ i` | 뒤 ㅅ의 다음 음절 이동이 보이지 않아 승인 불가 |
| `천구백칤비육` | `천구백칠ᆺ비육` | `tɕʰ ʌ ŋ ɡ u b ɛː k̚ tɕʰ i ɭ t̚ pʲ i j u k̚` | 숫자 표현의 원문 인코딩·전사 확인 필요 |

따라서 이 네 행은 phone inventory 안에 있다는 이유만으로 승인하지 않는다.
특히 `외곬을/외곬의`는 최신 모델이 미지원한 `ᆳ`을 분포 밖의 완전분해
입력으로 우회한 결과이므로, 모델 출력 자체가 표준 발음 적합성을
보증하지 않는다. 기존 외부 리뷰의 수동 4행 override 대안도 폐기하지
않고, 원전사와 규범 발음을 확인한 뒤 동일 107-phone inventory 안에서
비교한다.

공식 근거를 추가 대조한 결과는 다음과 같다.

- 국립국어원 표준 발음법 제14항은 ㄳ·ㄽ·ㅄ의 뒤 ㅅ이 모음 시작
  조사·어미·접미사 앞에서 연음될 때 [ㅆ]이 된다고 명시하고
  `곬이[골씨]`를 직접 예시한다.
  <https://korean.go.kr/kornorms/regltn/regltnView.do?regltn_code=0002>
- 국립국어원은 `외곬의`를 원칙적으로 `[외골씌]`, 관형격 조사
  `의`의 허용 발음을 적용하면 `[외골쎄]`로도 발음한다고 직접
  답했다.
  <https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=216&pageIndex=1&qna_seq=324494>
- 따라서 `외곬을`은 제14항의 직접 적용으로 `[외골쓸]`이 되는
  규칙적 추론이며, 현재 후보의 plain `sʰ`는 된소리 phone과 대조해야
  한다. `외곬의`의 현재 `...ɭ t̚ ɰ i`는 뒤 ㅅ의 초성 연음이 없어
  공식 원칙과 충돌한다.
- `외곬`은 `[외골]`이 원칙이고 `[웨골]`도 허용되므로, 모델 후보의
  첫 모음 변이는 이 문제와 별도로 다룬다.
  <https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=261&pageIndex=1&qna_seq=313229>
- `외곬`과 `외골수`는 모두 존재하지만 서로 다른 구조와 뜻의
  표준어다. 국립국어원은 `외곬`을 `외-+곬`, `외골수`를 `외-+골수`로
  분석한다. 따라서 관측 `외곬수적인`이 실제로
  `외골수적인`을 잘못 변환한 것이라면 수동 phone 1행으로 덮을 문제가
  아니라 vocabulary 원천·정규화 오류를 고쳐야 한다.
  <https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=216&pageIndex=1&qna_seq=329993>

`천구백칤비육`의 NFKD는
`ㅊㅓㄴ-ㄱㅜ-ㅂㅐㄱ-ㅊㅣㄽ-ㅂㅣ-ㅇㅠㄱ`이다. 이는
`천구백칠십육`의 `...ㅊㅣㄹ-ㅅㅣㅂ...`과 비교할 때 ㅅ·ㅂ·ㅣ의
음절 배치가 달라진 형태로 보인다. 다만 이것은 문자열 구조에 근거한
진단 가설이며, 원본 JSON을 보기 전에는 전사 오류·정규화 오류·실제
발화 중 어느 것인지 확정하지 않는다.

원본 추적은
`scripts/python/trace_common_pron_special_occurrences.py`로 수행한다.
이 도구는 동결 search-master 2020–2025를 공통 vocabulary와 같은
`form_to_lab`로 한 번만 읽고, 일치 발화의 form·original_form·발음 기준열과
원본 JSON을 `year/session_id/utt_id`로 재결합한다. 원본과 search-master가
다르거나 네 target 중 하나라도 찾지 못하면 실패하며 기존 파일을
덮어쓰지 않는다. 원본 불일치는 정상 결과로 숨기지 않고,
`failed_source_mismatch` manifest와 불일치 CSV를 새 경로에 보존하되
발음 승인에는 사용할 수 없게 gate를 내린다. G2P 계산과 D: 읽기 경합을
피하기 위해 현재 전수 shard 계산이 끝난 뒤 실행한다.

## 구결과 archive와 D: 정리

새 외장 HDD는 `E:\`(NTFS, 약 1.86TB 여유)로 확인했다. 다음 약 55.9GiB는
최신 Jamo 이전 기준이므로 E의
`READ_ONLY_ARCHIVE\2026_summer_research\pre_jamo_20260728` 아래에
복사·검증한 뒤 D 정리 후보로 삼는다.

| D 원본 | 파일 수 | 용량(GiB) | 의미 |
|---|---:|---:|---|
| `20_AUDIO\07_textgrid_eojeol_g2p_staging\2020` | 866,196 | 3.692 | 2020 구기준 TextGrid |
| `20_AUDIO\07_textgrid_eojeol_g2p_staging\2021` | 1,371,868 | 7.462 | 2021 구기준 TextGrid |
| `mfa_tmp\2021` | 105 | 43.883 | 2021 DB·재현 cache |
| `mfa_eojeol\archive_stale_temp` | 16 | 0.684 | 과거 stale temp 증거 |
| 최신 모델 첫 CRLF clone | 52 | 0.161 | OpenFST 실패 증거 |

`scripts/archive_pre_jamo_outputs_to_external.ps1`는 robocopy zero-diff,
파일 수·총 바이트, `2021.db` SHA256을 확인한다. 기본은 복사만 하며
`-PruneAfterVerify`에서만 검증된 명시적 allowlist 원본을 제거한다.

## 앞으로의 hard gate

1. 공식 저장소 commit·세 동결 파일 SHA256 일치
2. acoustic–G2P phone inventory 완전 동일
3. Jamo `unicode_decomposition=true`
4. OpenFST symbol 파일 CR=0
5. 전체 관측 OOV grapheme coverage 100%; 허용 확장은 U+11B3 하나
6. shard 입력·출력 단어 집합 완전 동일
7. 단어당 1-best 하나, `spn=0`, phone inventory 이탈=0
8. 최종 dictionary 기본행 byte 보존과 OOV 전수 포함
9. 2020–2025 모두 같은 final dictionary·acoustic SHA
10. 연도별 TextGrid 파일 수·tier 경계·누락·DB integrity 독립 QC
11. 구결과와 새결과는 경로·manifest에서 혼용 금지
12. 파일 존재나 exit 0만으로 성공 판정 금지

## 외부 리뷰 checkpoint

이 commit은 최신 모델 동결 코드·증거, r1 실패 감사, archive 안전장치,
Jamo `ㄽ` 미지원이라는 남은 통합 지점을 공개한다. 외부 리뷰 전에는
최신 공통사전을 사용한 연도별 MFA 정렬을 시작하지 않는다. 외부 리뷰와
병행 가능한 것은 구결과 archive와 정상 OOV의 재개 가능한 G2P 계산뿐이다.
