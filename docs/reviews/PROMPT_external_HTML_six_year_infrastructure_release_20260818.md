# 외부 도구 전달 프롬프트 — 2020–2025 연구 인프라 HTML

아래 본문을 저장소를 읽을 수 있는 다른 AI 도구에 그대로 전달한다.

---

당신은 한국어 음운·음성 연구를 위한 대규모 대화 말뭉치 자료 구축 과정을
검토하고, 연구자와 재사용자가 이해할 수 있는 기술·방법론 HTML을 만드는 역할을
맡는다. 실제 음운 현상 분석 논문을 쓰는 것이 아니라, 2020–2025년 6개년 자료
구축 인프라를 논문 methods supplement 또는 GitHub technical report로 공개한다고
가정한다.

저장소:

```text
C:\Users\ari30\research\2026_summer_research
```

## 1. 작업 목표

다음 두 산출물을 만든다.

1. 사람이 수정할 수 있는 Quarto 원본

```text
qmd/six_year_infrastructure_report_20260818.qmd
```

2. self-contained 또는 GitHub Pages에서 열 수 있는 HTML

```text
outputs/reports/six_year_infrastructure_report_20260818.html
```

HTML의 주 독자는 다음과 같다.

- 한국어 음운론·음성학·말뭉치 연구자
- 코드를 잘 모르지만 같은 절차를 재사용하려는 대학원생·공동연구자
- 공개 저장소의 재현성·연구방법을 검토하는 사람

한국어를 주 언어로 사용하고, 파일명·schema·status code 같은 기술 용어는 원문을
병기한다. 설명은 코드보다 연구 목적과 입력→출력 관계를 먼저 제시한다.

## 2. 먼저 읽을 파일

가장 먼저 다음 파일을 전부 읽는다.

```text
docs/releases/20260818_six_year_infrastructure_closeout/README.md
docs/releases/20260818_six_year_infrastructure_closeout/METHODS_RESULTS_LIMITATIONS.md
docs/releases/20260818_six_year_infrastructure_closeout/CHRONOLOGY_AND_DECISIONS.md
docs/releases/20260818_six_year_infrastructure_closeout/LESSONS_AND_REUSE_GUIDE.md
docs/releases/20260818_six_year_infrastructure_closeout/SOURCE_MAP_FOR_HTML.md
docs/releases/20260818_six_year_infrastructure_closeout/CLEANUP_LEDGER.md
outputs/reports/SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json
```

그 다음 `SOURCE_MAP_FOR_HTML.md`가 지정한 RC0/RC1 manifest·QA·독립 감사를 읽어
숫자와 주장을 확인한다. 숫자가 상충하면 archive나 오래된 메모가 아니라 최종
machine-readable release와 독립 감사를 우선한다.

`docs/archive`와 `docs/reviews/incoming`은 시행착오를 설명할 때만 사용한다. 그 안의
명령을 현행 실행 방법으로 복사하지 않는다.

## 3. 보고서 제목과 성격

권장 제목:

> 2020–2025 한국어 대화 말뭉치의 형태소 검색·공통발음·강제정렬 연구 인프라 구축

부제:

> exact-ID 회계, 재현 가능한 6-tier TextGrid, append-only 수동 보정과 후속 회수 체계

이것은 음운 현상의 실현 결과 논문이 아니다. “인프라 release candidate” 또는
“자료 구축 methods and data note”로 명시한다.

## 4. 반드시 포함할 목차

### 4.1 한눈에 보는 결과

- 대상 연도와 원천 5,103,356발화
- 전체 5,103,356발화의 표기·형태소 검색 가능
- 동일 계약으로 정렬·6-tier 수출된 4,286,046발화
- 발음 후속 718,364, MFA 전 기술 후속 95,860, MFA 후 기술 후속 3,086
- 누락·중복·미분류 0인 exact-ID 회계
- 실제 음운 실현 판정은 아직 수행하지 않았다는 경고

연도별 표는 closeout JSON의 정확한 수량을 사용한다. 합계와 회계식을 다시
계산해 일치하는지 검증한다.

### 4.2 왜 이 인프라가 필요한가

연구 흐름을 다음처럼 설명한다.

```text
CSV/검색층에서 형태소·표기 환경 후보 추출
→ WAV·TextGrid 연결
→ 선택 자료의 KOINA 등 운율 분석
→ 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA와 G2P가 실제 실현을 판정하는 도구가 아니라는 점을 눈에 띄는 주의 상자로
표시한다.

### 4.3 입력자료와 식별 체계

- 원 JSON/WAV/전사
- 연도·발화·세션·화자 identity
- 형태소/POS, 표기 로마자, 기호 읽기
- 원본과 파생층을 분리한 이유
- 대화 세션 문맥으로 돌아갈 수 있는 조인 키

### 4.4 공통발음 release와 r3 재정렬

- 왜 연도별 inline G2P 대신 6개년 공통 release를 만들었는가
- 최신 Jamo G2P·기본사전·음향모델을 hash로 동결한 이유
- 사전 예외 발음이 자동으로 해당 발화의 정답은 아닌 이유
- `있지/있는/없는/어쨌든` 등의 표본 문제가 6개년 fresh realign 결정으로 이어진
  과정
- 같은 G2P를 무의미하게 반복하지 않고 hold를 후속으로 분리한 이유

### 4.5 안전 본체와 817,310건 후속의 의미

이 부분은 별도 시각화와 설명을 둔다.

```text
817,310 = 718,364 pronunciation follow-up
        + 95,860 pre-MFA technical follow-up
        + 3,086 post-MFA technical follow-up
```

81만 건을 “실패” 또는 “버린 파일”로 표현하지 않는다. 이들도 전체 검색층에
존재한다. 다만 최종 6-tier·MFA phone이 없으므로 검색 결과에
`primary_status`, `textgrid_available`, `asset_status`, `followup_required`,
`reason_codes`, `alignment_scope`를 표시해야 한다.

발음 후속이 큰 이유도 설명한다. 발화 안에 hold 어절이 하나라도 있으면 발화
전체를 보수적으로 분리했고, 그 내부는 hold 717,354, policy 136,
empty-reference 848, hold+policy 26이다.

### 4.6 6-tier TextGrid

다음 tier를 표로 설명한다.

```text
words
phones_mfa
phoneme_r_auto
utterance
utterance_orth_r
morph_analysis_utt
```

`phones_mfa`는 강제정렬 출력, `phoneme_r_auto`는 기계적 넓은 로마자 범주,
`morph_analysis_utt`는 시간 정렬 형태소 경계가 아니라 검색 문자열이다. 실제
발음·형태소 경계처럼 과장하지 않는다.

가능하면 저장소에 이미 허용된 schema 그림이나 비식별/허용 표본을 사용한다.
원 음성이나 개인 Dropbox 파일을 임의로 복사·포함하지 않는다.

### 4.7 검증과 재개 설계

- input/method/output contract
- SHA-256과 exact-ID
- pilot/Gate와 `-PreflightOnly`
- 일부 성공을 성공 처리하지 않는 fail-closed
- 연도별 checkpoint와 완료 연도 재사용
- post-MFA 성공+후속=입력 회계
- 독립 QC와 cross-year audit
- 연구자 명시 승인

오류가 나면 연도 전체를 다시 시작하지 않고 exact-ID shard로 분리한 구조를
흐름도로 보여준다.

### 4.8 시행착오와 개선

`LESSONS_AND_REUSE_GUIDE.md`의 표를 기반으로 다음을 구체적으로 설명한다.

- 한 화자 pilot의 편향
- TextGrid 9/10 부분 성공
- tier 앞뒤 경계와 형태소 pseudo-alignment
- 숫자·기호 빈 발음
- grapheme/음절 inventory 문제와 Jamo 전환
- PowerShell 5.1 scalar/UInt32/heartbeat 문제
- gzip newline row mismatch
- WAV ID·duration pairing
- MFA 미정렬 exact-ID
- 실패/성공 export 보고서 공존
- 수동 전사와 기존 형태소·phone의 층간 모순
- 검수만 반복하지 않고 결과를 release에 반영하는 Gate

각 항목을 “오류 → 왜 위험했는가 → 코드/계약에서 어떻게 막았는가 → 재사용자가
확인할 것” 네 부분으로 쓴다.

### 4.9 RC0, RC1, active view

RC0 전체 장부를 불변 base로 두고, RC1이 55행 상태와 16행 curated pointer만
추가하며, active view가 exact-ID 우선순위를 적용하는 구조를 그림으로 보여준다.
D9 phone은 참고 전용이고 RC1이 본체 정렬 수를 늘리지 않았다는 점을 명시한다.

### 4.10 앞으로의 실제 연구 단계

- 선언형 query로 형태소·표기 환경 후보 추출
- 의미번호 join과 음운형태적 환경 정의
- 후보의 WAV·TextGrid 문맥 연결
- 연구자의 실제 실현·소음·겹침·수동 경계 판단
- 선택 자료 KOINA
- wav2vec2/HuBERT는 원 MFA 열을 덮지 않는 보조열/sidecar
- 수동 수정이 전체 active view에 provenance와 함께 반영되는 구조

ㄴ 삽입 B1 개정안을 예로 들 수 있지만 연구 결과를 제시하지 않는다.

### 4.11 재사용 튜토리얼

두 경로를 나눈다.

1. 같은 NIKL corpus를 권한에 따라 별도로 확보해 재현하는 경우
2. 다른 한국어 corpus에 adapter를 만들어 이식하는 경우

실행 명령은 현행 runbook·실제 script에서 확인한 것만 쓴다. 존재하지 않는
`--example`이나 임의 명령을 만들지 않는다. 장시간 명령은 바로 실행하라고 하지
말고 preflight, 예상 입력 수, 성공 조건, 중단·재개 지점을 먼저 보여준다.

코드를 모르는 독자를 위해 각 명령 앞에 다음을 설명한다.

- 무엇을 읽는가
- 무엇을 만드는가
- 원본을 바꾸는가
- 성공하면 무엇이 보여야 하는가
- 실패하면 어디서 재개하는가

### 4.12 AI 보조와 연구자 책임

다음 사실을 투명하게 쓴다.

- Claude Code와 OpenAI Codex를 코드 작성·검토, 오류 진단, 검증·문서 초안에
  보조적으로 사용했다.
- 연구자가 연구 목적, 언어학적 분류, 청취·TextGrid 검토, 승인과 최종 결정을
  담당했다.
- AI 출력은 입력 contract, 수량·hash 회계, 독립 감사와 인간 검토를 거쳐
  채택했다.
- 확인되지 않은 정확한 모델 버전을 추측하지 않는다.

### 4.13 한계·라이선스·공개 범위

- 정렬은 실제 발음 판정이 아님
- 후속 recovery 미완료
- 자동 형태소·발음 참조 오류 가능
- licensed raw corpus는 GitHub에 포함하지 않음
- 개인 Dropbox·API key·절대 내부 경로 비공개
- 코드와 작은 manifest만으로 원자료가 자동 제공되는 것은 아님

## 5. 디자인 요구

- 연구 methods supplement처럼 차분하고 읽기 쉽게 만든다.
- 표와 흐름도는 반응형이어야 한다.
- 첫 화면에 핵심 수치 카드 4–5개를 둔다.
- 색상은 aligned, pronunciation follow-up, technical follow-up, manual overlay를
  일관되게 구분한다.
- 경고 상자는 “MFA phone ≠ 실제 실현”과 “전체 검색 ≠ 전체 정렬” 두 개를 둔다.
- 긴 파일 경로는 접기 또는 code block으로 처리한다.
- print CSS와 목차 링크를 확인한다.
- 외부 CDN이 없어도 핵심 본문을 읽을 수 있게 한다.

## 6. 사실 검증과 금지사항

완성 전에 `SOURCE_MAP_FOR_HTML.md`의 체크리스트와 금지된 주장을 한 항목씩
검사한다. 특히 다음 표현을 쓰지 않는다.

- 6개년 전체 MFA 완료
- 81만 건 실패/폐기
- MFA가 ㄴ 삽입을 판정
- AI가 자율적으로 연구 수행
- raw corpus 공개

큰 파일 이동·삭제, MFA 재실행, 기존 release 변경은 이 HTML 작업의 범위가
아니다. 필요한 정보가 없으면 추측하지 말고 TODO와 근거 부족을 표시한다.

## 7. 산출물 검증

1. Quarto render가 오류 없이 끝나는지 확인한다.
2. 생성 HTML을 실제로 열어 제목, 목차, 표, 한글, code block, 링크를 확인한다.
3. 2020–2025 연도별 합계와 전체 회계식을 프로그램 또는 계산으로 재확인한다.
4. 모든 로컬 링크가 존재하는지 검사한다.
5. Git status에서 HTML 작업과 무관한 파일을 수정하지 않았는지 확인한다.
6. 수행한 변경, 남은 TODO, 사용한 근거 파일을 별도 요약해 사용자에게 보고한다.

작업 전에 계획을 제시하되, 계획만 쓰고 멈추지 말고 위 산출물의 생성과 render
검증까지 완료한다.

---
