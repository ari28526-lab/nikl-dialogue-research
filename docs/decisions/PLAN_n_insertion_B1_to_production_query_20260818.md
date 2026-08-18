# ㄴ 삽입 B1 정의에서 생산 후보 추출까지의 Gate

작성일: 2026-08-18 KST

## 현재 판단

후보 검색·RC1 precedence·TextGrid word-context 시간 연결 기술은 작은 파일럿을
통과했다. 더 많은 인프라 표본을 반복할 이유는 없다. 다만 기존 2026-07-15 B1
초안은 MFA phone을 핵심 실현 판정처럼 기술해 현행 방법론과 충돌했다. 해당
초안은 archive하고 현행 개정안을 만들었다.

## 생산 query v1의 두 모집단

### 1. 어절 내부 경계

- `boundary_scope = intra_eojeol`
- 왼쪽 형태소 마지막 한글 음절에 종성 존재
- 오른쪽 형태소 첫 음절: 초성 ㅇ, 중성 `ㅣ·ㅑ·ㅕ·ㅛ·ㅠ·ㅖ·ㅒ`
- 오른쪽 품사가 J* 또는 E*면 제외
- 숫자·기호 unit 인접 제외
- 형태소/POS 조합으로 N+N, 접두+N, 용언/기타 경계를 별도 분류

### 2. 어절 간 경계

- `boundary_scope = inter_eojeol`
- 왼쪽 어절 마지막 형태소의 종성 존재
- 오른쪽 어절 첫 형태소의 초성·중성 조건은 위와 동일
- 조사·어미 시작, 숫자·기호 인접 제외
- 구문·운율 변수는 후보 생성 조건과 분리해 후속 결합

두 모집단을 한 query ID로 합치지 않는다. 같은 발화의 여러 경계는 서로 다른
`target_occurrence_id`로 보존한다.

## 생산 전에 반드시 결합할 정보

- RC0 기본 + RC1 curated active 전사·TextGrid
- 왼쪽/오른쪽 형태소, 품사, 어절/발화 내 index
- 의미번호 `sense_id/source/status/candidates/confidence`
- 철자 Roman, 규칙·사전 발음 참조
- 화자·대화상대·세션·사회변수
- WAV·base/curated TextGrid pointer와 word-context xmin/xmax
- 자산 부재·recovery·음질 상태

의미번호는 ㄴ 삽입 후보 환경 자체를 자동 확정하는 필터가 아니다. 다의성·미부여
상태를 포함한 분석 변수와 사전 발음 join key로 보존한다.

## Gate 순서

1. 연구자가 개정 B1의 포함·제외 범위를 확정한다.
2. 두 query를 선언형 config로 동결하고 query SHA를 기록한다.
3. 2020 한 연도에서 **수량·열·상태만** 감사한다. 새 청취 파일럿은 하지 않는다.
4. 같은 query SHA로 2020–2025 후보를 연도 checkpoint형으로 생성한다.
5. occurrence→TextGrid context linker를 적용한다.
6. 수동 판정용 WAV·TextGrid·CSV bundle과 workbook을 만든다.
7. `realization_decision`은 연구자만 append-only로 기록한다.

단계 3의 목적은 연구 정의를 다시 검토하는 것이 아니라 전수 출력에서 의미번호
join 누락, ID 중복, 자산 상태 은폐가 없는지 확인하는 생산 감사다.

## 지금 열지 않는 작업

- 전 연도 MFA 재실행
- MFA phone 기반 ㄴ 삽입 자동 판정
- RC1 16건의 전면 형태소·phone enrichment
- 전수 WAV·TextGrid 복사
- KOINA 전수 실행

RC1 수동 보정 발화가 실제 후보에 포함되면 해당 exact ID에 대해서만 형태소
re-analysis와 수동 경계 revision을 후속 Gate로 연결한다.
