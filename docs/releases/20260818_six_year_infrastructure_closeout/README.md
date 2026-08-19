# 2020–2025 대화 말뭉치 연구 인프라 closeout

기준일: 2026-08-18 KST

대상: 국립국어원 대화 말뭉치 2020–2025년 6개년

성격: 논문 결과가 아니라 **재현 가능한 자료 구축 인프라의 1단계 완결 기록**

## 2026-08-19 배포 범위

이 closeout에서 배포하는 것은 자료구축 1단계의 기계적 분석·MFA 인프라뿐이다.
범용 `morph_search.v3`는 완성된 기계 인프라로 포함하지만, 특정 음운 현상의
query·후보·검토·실현 판정인 2단계 G1–G8은 배포 대상에서 제외한다.

배포는 다음 두 경로를 구분한다.

1. [프로그램을 모르는 독자를 위한 HTML 안내](../../../outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html)
2. [D: 동결 드라이브 인계](DISTRIBUTION_D_DRIVE.md)
3. [원자료 직접 확보형 코드 재현판](DISTRIBUTION_CODE_ONLY.md)

코드 재현판은 향후 GitHub에 선별 공개할 수 있도록 설계하되 현재 공개가 확정된
것은 아니다. 전체 저장소 snapshot이 아니라
[별도 allowlist Gate](PUBLIC_CODE_RELEASE_CANDIDATE.md)를 사용한다.

## 이 closeout이 뜻하는 것

이 묶음은 형태소·표기 환경으로 연구 후보를 찾고, 해당 WAV·TextGrid·CSV를
연결하며, 선별 자료에 운율 분석을 적용하고 연구자가 실제 실현 여부를 판정할 수
있도록 만든 기반을 설명한다. 6개년 원천 발화의 기술 상태를 exact-ID로 모두
회계하고, 같은 발음·음향·TextGrid 계약으로 MFA 안전 본체를 정렬했으며, 실패와
보류 항목을 사라지게 하지 않고 후속 장부에 남겼다.

다음은 이 단계의 완료 범위다.

1. 원천 5,103,356발화를 누락·중복 없이 상호배타적 상태로 분류했다.
2. 2020–2025년을 같은 `common_pron_mfa_r3_20260809` 발음 release와 동결된
   음향모델·phone inventory·runtime·6-tier schema로 새로 정렬했다.
3. 4,286,046발화의 연구용 6-tier TextGrid를 연도별 보존 DB에서 수출하고 독립
   QC를 통과시켰다.
4. 기술적 제외 98,946건과 발음 후속 718,364건을 삭제하지 않고 이유별 recovery
   장부로 유지했다.
5. 형태소 조합검색 6개년 5,103,356발화·50,955,891형태소 token을 구축했다.
6. 수동 수정은 기본 release를 덮어쓰지 않는 RC1 sidecar와 active-view 계약으로
   연결했다.
7. 후보→WAV/TextGrid→어절 문맥 시간 연결이 가능한지 소표본으로 검증했다.

7번은 인프라 능력에 대한 내부 검증 근거다. 그 파일럿과 이후 특정 현상 후보는
2026-08-19 A단계 배포 산출물에 포함하지 않는다.

전체 5,103,356발화는 표기·형태소 검색층에 남아 있다. 정렬 본체 밖
817,310건도 검색에서 사라지지 않으며, 검색 결과에 상태와 후속 이유를 붙여
TextGrid·phone 사용 가능 범위를 구분한다. 즉 “6개년 전체 검색 가능”과
“6개년 전체 MFA 정렬 완료”는 다른 주장이다. 전자는 맞고, 후자는
4,286,046발화 범위에서만 맞다.

## 숫자로 보는 정본

| 연도 | 원천 발화 | 정렬·6-tier | MFA 전 기술 후속 | MFA 후 기술 후속 | 발음 후속 |
|---:|---:|---:|---:|---:|---:|
| 2020 | 870,437 | 782,432 | 1,675 | 283 | 86,047 |
| 2021 | 1,373,920 | 1,206,862 | 937 | 437 | 165,684 |
| 2022 | 866,359 | 751,383 | 870 | 338 | 113,768 |
| 2023 | 677,262 | 494,228 | 87,809 | 352 | 94,873 |
| 2024 | 728,257 | 593,530 | 1,339 | 874 | 132,514 |
| 2025 | 587,121 | 457,611 | 3,230 | 802 | 125,478 |
| **합계** | **5,103,356** | **4,286,046** | **95,860** | **3,086** | **718,364** |

회계식은 다음과 같다.

```text
5,103,356
= 4,286,046 aligned_safe_body
+    95,860 pre_mfa_technical_exclusion
+     3,086 post_mfa_technical_exclusion
+   718,364 pronunciation_followup
+         0 methodological_exclusion
```

`methodological_exclusion=0`은 모든 음원이 연구에 적합하다는 뜻이 아니다. 소음,
화자 겹침, 실제 실현, 연구 질문에 따른 제외는 후보 추출 후 연구자가 판단한다.
현재 수치는 그 판단 전의 인프라 회계다.

## 반드시 구분할 결과물

- `CSV/검색층`: 표기, 형태소, 기호 읽기, 발음 참조 및 결합검색을 위한 데이터.
- `MFA phones`: 동결 사전과 음향모델을 사용한 강제정렬 출력. 실제 발음의 정답이
  아니다.
- `phoneme_r_auto`: MFA phone을 기계적으로 넓은 로마자 음소 범주로 표시한 보조층.
  기저형이나 연구자 음운 판정이 아니다.
- `TextGrid 6-tier`: 음성 정렬과 검색·검토를 연결하는 연구용 파생 자산.
- `RC1 overlay`: 연구자가 수정한 소수 exact-ID를 원본과 RC0를 덮어쓰지 않고
  우선 적용하는 append-only 보정층.
- `target manifest`: 후보를 찾고 자산과 연결하는 인프라. ㄴ 삽입 등 실제 실현
  판정 결과가 아니다.

검색 결과에서 후속 자료를 숨기지 않으려면 최소한 `primary_status`,
`textgrid_available`, `asset_status`, `followup_required`, `reason_codes`,
`alignment_scope`를 함께 내보낸다.

## 정본 진입점

외부 설명이나 HTML을 만들 때는 아래 순서로 읽는다.

1. `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/README.md`
2. `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/QA_REPORT.json`
3. `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/METHODS_A_C.md`
4. `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818/README.md`
5. `docs/environment/PROJECT_CURRENT_STATE.md`
6. 이 폴더의 `METHODS_RESULTS_LIMITATIONS.md`, `LESSONS_AND_REUSE_GUIDE.md`,
   `SOURCE_MAP_FOR_HTML.md`

역사 archive는 시행착오를 설명할 때만 사용하며 현재 실행 지침으로 인용하지
않는다.

## 이 단계가 완료하지 않은 것

- ㄴ 삽입 등 개별 음운 현상의 실현 여부 판정
- KOINA 또는 다른 운율 분석의 6개년 전수 실행
- wav2vec/HuBERT phone output의 전수 생성
- 모든 기술·발음 후속 817,255건의 회수
- 원 음성·전사·TextGrid의 외부 재배포 권리 확정
- 통계 분석과 논문 결론

따라서 이 closeout의 적절한 명칭은 “2020–2025 연구 자료 구축 인프라 및
회수·추적 체계”다. “6개년 음운 현상 분석 결과”라고 부르면 안 된다.

## 문서 구성

- `METHODS_RESULTS_LIMITATIONS.md`: 방법, 산출물, 검증, 한계
- `CHRONOLOGY_AND_DECISIONS.md`: 초기 pilot부터 RC0/RC1까지의 설계 변경 연대기
- `LESSONS_AND_REUSE_GUIDE.md`: 시행착오, 재발 방지, 비개발자 재사용 절차
- `SOURCE_MAP_FOR_HTML.md`: HTML 작성자가 읽을 정본과 금지된 추론
- `CLEANUP_LEDGER.md`: 삭제·보존·후속 정리 장부
- `DISTRIBUTION_D_DRIVE.md`: 허가 보유자에게 D: 동결본을 인계하는 절차
- `DISTRIBUTION_CODE_ONLY.md`: 원자료 직접 확보형 코드 재현 절차
- `PUBLIC_CODE_RELEASE_CANDIDATE.md`: 향후 GitHub 선별 공개 전 Gate
- `outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html`:
  비전공자용 단일 HTML 안내서
- `docs/reviews/PROMPT_external_HTML_six_year_infrastructure_release_20260818.md`:
  외부 AI 도구에 그대로 전달할 작업 프롬프트

## AI 사용과 연구자 책임

연구자는 연구 목적, 분류 원칙, 발음·정렬의 해석, 청취·TextGrid 검토, 범위별
승인과 최종 결정을 담당했다. Claude Code와 Codex는 코드·문서 초안, 오류 진단,
검증 스크립트, checkpoint와 manifest 작성에 보조적으로 사용됐다. AI 출력은
정답으로 채택하지 않았으며, 생산 단계는 고정된 입력·SHA-256·수량 회계·독립
감사·연구자 명시 승인을 통과해야 했다. 세부 공개 문구는
`METHODS_RESULTS_LIMITATIONS.md`의 AI 보조 절을 따른다.
