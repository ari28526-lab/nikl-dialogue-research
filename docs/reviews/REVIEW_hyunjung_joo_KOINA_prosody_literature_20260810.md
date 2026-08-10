# 조현정 공개 연구·KOINA·한국어 운율 문헌 검토

검토일: 2026-08-10 KST

## 검토 질문

1. 조현정의 공개 연구 중 실제 재사용 가능한 코드·자료는 무엇인가?
2. `Accentual-Phrases-in-Seoul-Korean`과 KOINA는 무엇을 각각 담당하는가?
3. 자연 대화 연구에서 AP/IP 자동값을 어떤 지위로 저장해야 하는가?

## 조현정 공개 자산

### 서울말 AP 자료와 Dual-Glob

- `Accentual-Phrases-in-Seoul-Korean` 저장소 자체에는 README만 있고, 외부 Drive의
  10,093개 AP 자료를 안내한다. 18명 방송인, 두 K-ToBI 전사자, 16개 H/L 유형의
  수동 주석 benchmark다.
- Joo & Lee (2026)의 Dual-Glob은 이 F0 윤곽을 contrastive learning으로 분류하며
  accuracy 77.75%, macro F1 51.54%를 보고한다.
- 2026-08-10 공개 검색에서 논문·자료 저장소는 확인했지만, 실행 가능한 Dual-Glob
  학습/추론 코드나 model weight 공개 저장소는 찾지 못했다.

따라서 이 자료는 현재 `AP 유형 비교·annotation guide·후속 분류 benchmark`로는
유용하지만, 현재 MFA나 KOINA를 대체하는 실행 도구는 아니다. macro F1도 희소
유형을 자동 정답으로 확정하기에는 낮으므로 향후 공개 코드가 생겨도 보조 후보로
사용한다.

### fuzzy-logic 코드

- 2026 박사논문은 `hyunjungjoo/fuzzy-logic`의 Python notebook을 공식 코드로
  연결한다.
- 입력은 이미 측정된 `L/H timepoint·F0`와 모음 경계이며, speaker별 정규화,
  slope, triangular/trapezoidal/Gaussian membership function으로 미국 영어의
  `H*`와 `L+H*`를 예측한다.
- 음성에서 F0·AP·경계를 직접 추출하는 프로그램이 아니고 서울말 분류기도 아니다.

나중에 KOINA/Praat에서 추출한 목표점에 불확실성 점수를 부여하는 독립
`prosody_fuzzy_auto` 재구현 아이디어로는 유용하다. 다만 저장소에 명시적 license가
없으므로 코드를 복사·재배포하지 않고 방법을 인용해 독립 구현해야 한다.

### 통계 분석 코드

- `final-project`, `final-presentation`, `QP1-project`에는 남경상도 lexical pitch
  accent 지각 연구의 CSV, R/Rmd, 혼합효과 로지스틱 회귀 분석이 있다.
- 후속 통계모형 설계의 예시는 되지만 서울말 자연 대화의 AP 자동 추출 코드는
  아니다. 공개 저장소에 명시적 license가 없어 분석법 참고와 인용에 한정한다.

## KOINA의 실제 역할과 한계

KOINA v1.1.0은 Momel 기반 F0 목표점·spline·TCoG, pitch doubling/halving 보정,
F0 목표점 단순화, JPEG/TextGrid, 자체 MFA word/phone 정렬을 제공한다. 박사논문은
KOINA 정렬이 방언 코퍼스 word timing과 평균 56–77ms 차이를 보였고, 발화 마지막
90–100% 구간의 F0 시작·끝·평균·최대·최소·기울기·TCoG를 이용한 상승/하강
분류에서 F1 0.90을 보고한다.

이는 `거시 F0 윤곽과 문말 억양 후보 생성`에는 적합하지만 다음을 뜻하지 않는다.

- 프로젝트 r3 MFA의 `words/phones_mfa`보다 정밀하거나 동일한 정렬이라는 뜻이 아님
- AP/IP 경계를 언어학적 정답으로 자동 확정한다는 뜻이 아님
- 형태소 환경이나 연구자의 실제 실현 판정을 대신한다는 뜻이 아님

따라서 KOINA의 자체 정렬은 `koina_word_auto/koina_phone_auto`, F0 목표점과
거시 특징은 `koina_*_auto`로 별도 보존하고 r3 tier를 덮어쓰지 않는다.

## 문헌이 요구하는 자연 대화용 설계

- K-ToBI는 AP/IP와 tone/break를 다층으로 전사하며 음성, F0, word, tone,
  break-index의 결합을 전제로 한다.
- Kim et al. (2008)은 10개 문법 특징과 14개 음향 특징을 함께 써 AP 경계
  82.6%, IP 경계 88.7%를 보고했다. 이는 형태소·문법 DB를 운율 후보 생성에
  결합할 근거다.
- Kang & Kong (2022)은 서울 코퍼스 자연발화에서 pitch reset, segment 영향,
  dephrasing, boundary tone 변이 때문에 intermediate phrase가 모호할 수 있음을
  보였다. 자연 대화에서는 F0 하나만으로 확정 경계를 만들면 안 된다.
- Hatcher et al. (2024)은 AP edge tone의 F0 range와 alignment가 focus·position·
  segmental context에 따라 달라질 수 있음을 보였다. AP 후보는 형태소·분절·담화
  위치와 함께 해석해야 한다.

## 프로젝트 결정

현재 전수 인프라는 변경하지 않는다.

1. r3 MFA 6-tier와 형태소·발화 ID·동반 CSV를 전수 정본으로 완성한다.
2. 연구 주제의 형태소·표기 환경으로 후보를 선별한다.
3. 선별 WAV/TextGrid 또는 seam이 명시된 연결본에만 KOINA를 실행한다.
4. KOINA 원출력, 자동 AP/IP 후보, 조현정 자료와의 유형 비교, 연구자 확정 판정을
   서로 다른 열/tier와 version으로 저장한다.
5. 자동 AP/IP는 confidence와 근거 특징을 가진 후보이며 연구자 확정 전에는
   `manual` 값을 만들지 않는다.

## 주요 출처

- KOINA: https://github.com/YugwonWon/KOINA
- 원유권 (2025), 《한국어 억양 자동 주석기 개발 연구》:
  https://www.riss.kr/search/Search.do?colName=bib_t&isDetailSearch=Y&queryText=tutor%2C%EC%98%A4%EC%9E%AC%ED%98%81&searchGubun=true
- Joo & Lee (2026): https://aclanthology.org/2026.acl-long.1838/
- 조현정 AP 자료: https://github.com/hyunjungjoo/Accentual-Phrases-in-Seoul-Korean
- 조현정 박사논문: https://adamjardine.net/files/joo2026dissertation.pdf
- Joo & Jardine (2025): https://aclanthology.org/2025.scil-1.22/
- K-ToBI: https://linguistics.ucla.edu/people/jun/ktobi/k-tobi-V2.html
- Kim et al. (2008): https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART001264355
- Kang & Kong (2022): https://doi.org/10.17959/sppm.2022.28.1.3
- Hatcher et al. (2024): https://academic.hanyang.ac.kr/documents/11105253/116065349/Hatcher_et_al_2024.pdf/9c225588-eff8-f930-29bc-ab451a3b1bde
