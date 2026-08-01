# 2026년 8월 작업 기록

## 2026-08-01 — 로마자 음소 보조층 원격 검토 링크 보정

### 문제 발견

사용자가 외부 컴퓨터에서 Dropbox 동기화 본을 열었을 때 새 5-tier
TextGrid 링크를 열 수 없었다. 12발화의 WAV·기존 4-tier·새 5-tier
파일은 모두 Dropbox 검토 폴더에 있었으나, workbook 하이퍼링크가
생성 컴퓨터의 `D:\...` 절대경로를 담고 있었다.

### 조치

- 기존 `PHONEME_ROMAN_PILOT.xlsx`는 덮어쓰지 않았다.
- `PHONEME_ROMAN_PILOT_PORTABLE_20260801.xlsx`를 새로 생성했다.
- 12행의 WAV·기존 4-tier·새 5-tier, 총 36개 hyperlink를 같은 폴더의
  파일명만 사용하는 상대경로로 변경했다.
- workbook 재로딩, 36개 링크의 상대경로·대상 존재, 원본 미변경,
  네 시트 렌더링을 검증했다.
- Dropbox 전달본과 프로젝트 검증본의 SHA-256은
  `2d21408ed215c8778e1b2a530753eb6486794e596a7ed2301df9c8c7ba0fb714`로
  일치했다.
- 이후 `build_phoneme_roman_pilot.py`도 최초 생성부터 상대링크만 허용하도록
  바꾸어 재발을 차단했다.

### 연구 및 데이터 영향

- D: 원본/파일럿 정렬 산출물은 변경하지 않았다.
- `phones_mfa`, 음성, TextGrid 경계, 로마자 대응값은 변경하지 않았다.
- 검토 접근성만 보정했으며 어떤 연구자 실현 판정도 추가하지 않았다.

## 2026-08-01 — 서울 코퍼스 참조 tier 재설계 검토

- 사용자가 `phoneme_r_auto`를 철자·예측발음에서 기저형을 역복원하는
  층이 아니라 `phones_mfa`의 broad Roman 음운전사로 재정의했다.
- 이 수정을 구현하던 중 사용자가 tier 전체 구성을 먼저 재검토하도록
  요청해, 코드는 미완성 초안 상태에서 중지하고 산출물·커밋·푸시를
  하지 않았다.
- `WorkshopLecture1-v4.pdf` 45쪽과 `KCI_FI002007633.pdf` 7쪽을 전체 텍스트
  추출하고, tier 예시·음소 기호표·검색 예시가 있는 페이지를 PNG로
  렌더링해 시각 확인했다.
- 서울 코퍼스의 7-tier는 철자형/발음형 utterance·phrasal-word,
  두 phrasal-word 로마자, phoneme로 구성된다. 음소·어절·발화
  경계를 동기화했으며 실제 발음형은 사람 전사·수정을 거친 값이다.
- 현재 프로젝트는 이 원칙을 참조하되 G2P/사전 예측발음을 서울 코퍼스의
  수동 발음형과 같게 취급하지 않는 6-tier 적용안을 작성했다.
- 제안 tier는 `words / phones_mfa / phoneme_r_auto / utterance /
  utterance_orth_r / morph_analysis_utt`이다. 세 발화 수준 tier는 같은
  word-derived span을 쓰고, 형태소 문자열은 실측 시간경계를 주장하지
  않는다.
- 제안 정본:
  `docs/decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`.

### KOINA 및 연결 발화 호환성 추가 검토

- 연구자가 추후 KOINA를 선별 적용하고 여러 발화 파일을 이어 붙일 수
  있다고 명시했다.
- KOINA는 전수 기본 6-tier가 아니라 `utt_id`로 결합하는 독립 파생
  산출물로 유지하는 안을 설계 문서에 추가했다.
- KOINA가 자체 생성한 word/phoneme 정렬은 공통 MFA의 `words`와
  `phones_mfa`를 덮어쓰지 않고, 필요할 때 `koina_*_auto`로 분리한다.
- 연결 TextGrid에서는 세 발화 수준 tier를 원 발화마다 반복하고,
  연결본 전용 `source_utt_id`와 필요 시 `speaker` tier를 둔다.
- 현재 `stitch_session.py`는 0.05초 인공 무음과 구형
  `morphemes_legacy`를 사용하는 맥락 검토용이다. 인공 seam을 자연스러운
  AP/IP 경계로 오인할 위험이 있어, 새 tier와 `review/koina_batch/
  continuous_source` mode 계약을 구현하기 전에는 KOINA 분석 입력으로
  사용하지 않기로 했다.
- 연결 좌표는 `stitched_id/order/utt_id/source time/stitched time/gap/
  contract SHA` manifest로 원 발화에 역매핑할 수 있게 한다.

## 2026-08-01 — 서울 코퍼스 참조 6-tier 확정 및 최소 파일럿

### 연구자 결정

- 차기 기본 연구 표시를 `words / phones_mfa / phoneme_r_auto /
  utterance / utterance_orth_r / morph_analysis_utt` 6-tier로 확정했다.
- 철자 로마자는 현행 `form_roman`, 형태소 tier는 한글 `형태소/POS`를
  사용한다. 두 tier 모두 형태소 음향 시간경계를 주장하지 않는다.
- KOINA는 선별 파생 산출물이며 기본본에 빈 tier를 만들지 않는다.

### 구현과 구버전 보존

- 기존 `research_textgrid.py`와 4/5-tier 출력은 수정·삭제하지 않았다.
- 새 `research_textgrid_v2.py`에 6-tier 작성·검증과 연결 검토본 생성을
  분리했다.
- 연결본은 기본 6-tier에 `source_utt_id/speaker`를 추가하고, 각 원발화의
  source time과 stitched time을 manifest로 기록한다.
- 기존 `stitch_session.py`는 구형 맥락 검토 도구로 보존했다. 새 코드에서
  `stitch_mode=review`, `koina_cross_seam_allowed=false`를 강제했다.

### 최소 파일럿 결과

- 프로젝트 보존본:
  `outputs/textgrid_6tier_mini_pilot_20260801`
- 단일 발화: `SDRW2000000510.1.1.98` (`혹시 요즘`), 6-tier 1건
- 연결본: 같은 세션·같은 화자
  `SDRW2200001103.1.1.67 → SDRW2200001103.1.1.269`, 0.05초 인공 gap,
  8-tier 1건
- 두 연결 발화는 비인접하므로 자연스러운 대화 연속 자료가 아니다.
  연결 구조·좌표 검토에만 사용하며 seam 횡단 운율 해석을 금지했다.
- 단위시험 13건 통과. 실자료 독립 검증에서 입력 9개·출력 9개의 SHA,
  모든 tier의 0–xmax 연속성, 기존 word/phone 보존, phone–phoneme 경계,
  발화 수준 세 tier 경계, 연결 원시간 역매핑이 모두 통과했다.
- KOINA는 실행하지 않았고 KOINA 빈 tier도 생성하지 않았다.

### 재현성 메타데이터 보정

- 첫 최소본은 미완성 v2 초안의 `phoneme_roman_aux.v2`를 manifest에
  기록했다. 구 5-tier 코드를 그대로 보존하고 새 6-tier를 별도 모듈로
  분리하기로 했으므로 현재 재현 가능한 의존성은 기존 phone mapping
  `phoneme_roman_aux.v1`과 새 표시 계약 `research_textgrid.v2`의 조합이다.
- 첫 실물은 삭제하지 않고
  `outputs/textgrid_6tier_mini_pilot_20260801_pre_repro_fix_ARCHIVE`로 옮겼다.
- 현재 코드로 동일 최소본을 새 최종 root에 다시 생성하고 독립 검증을
  재실행했다. 최종 `PILOT_VERIFICATION.json`은 `status=success`다.

### Dropbox 전달

- 전달 위치:
  `C:\Users\ari30\Dropbox\TEXTGRID_6TIER_MINI_PILOT_20260801`
- 첫 복사 명령은 `Copy-Item -LiteralPath`에 wildcard를 사용해 대상 폴더만
  만들고 파일 0개 상태에서 안전 중단됐다. 프로젝트 보존본과 원 입력에는
  변화가 없었다.
- 비어 있는 대상임을 확인한 뒤 검증된 11개 파일을 절대경로로 개별 복사했고,
  프로젝트 보존본과 파일별 SHA-256이 전부 일치했다.
- 생성 직후의 dirty worktree commit 표시를 보완하기 위해 최종 구현 commit
  `fb275b7`과 세 스크립트·시험·파일럿 manifest SHA를 묶은
  `CODE_PROVENANCE.json`을 추가했다. 이 파일도 복사 SHA가 일치한다.
- 최종 전달본은 12파일·308,428 bytes다.
