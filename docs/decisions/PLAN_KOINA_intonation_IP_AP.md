# 억양전사(IP/AP) 계획: KOINA 활용 (2026-07-09)

목표: 일상대화 음성에 **IP(억양구) / AP(강세구) 경계 수준**의 억양전사를
자동 부여. 세부 성조(K-ToBI 전체)는 하지 않음.

## 1. KOINA 검토 결과

- KOINA(원유권 2025, 건국대 박사논문; github.com/YugwonWon/KOINA, v1.1.0)
- 기능: Momel 기반 F0 목표점 추출·최소화, pitch doubling/halving 보정,
  MFA(korean_mfa) 강제정렬, TextGrid 출력
- 출력 tier: utterance / word / syllable / phoneme / phoneme_kr /
  Points(Momel F0 목표점) / TCoG — **IP/AP 레이블은 직접 출력하지 않음**
  → 경계 판정 레이어는 자체 작성 필요 (2절)
- README 예시 파일명이 `SDRW2200000001.1.1.1.wav` = 우리와 같은
  NIKL 일상대화 코퍼스 기반으로 개발된 도구 → 입력 형식 그대로 호환
  (TSV: filename, sex, text — sex는 _speakers.csv에서, text는 form에서)
- 라이선스: MIT Non-Commercial — 학술 연구 사용 가능. 인용:
  원유권(2025) 박사논문 + Zenodo DOI 10.5281/zenodo.18666913

## 2. 제약과 실행 환경 결정

- Momel 실행 파일이 **Linux 전용**(`src/lib/momel/momel_linux`)
  → Windows 로컬 실행 불가. 선택지:
  - (권장) **Colab에서 실행** — 리눅스, 기존 Colab 워크플로우와 일치.
    conda로 MFA 3.2.1 + koina 환경 구성. 음성 표본만 G:에 업로드
  - (차선) Docker Desktop 설치 후 공식 이미지 — 8GB RAM PC에 부담, 보류
- 전량(449만 발화) 적용은 비현실적. **검색 기반 on-demand 전사**로 설계:
  형태소·의미번호·IPA 검색 → utt_id → wav 추출 → KOINA + IP/AP 판정
  (연구 대상 발화 수백~수천 개 단위)

## 3. IP/AP 판정 레이어 설계 (자체 작성)

KOINA 출력(F0 목표점 + word/syllable 정렬)에 규칙 기반 판정 적용,
`prosody` tier(interval, 라벨 AP/IP)를 TextGrid에 추가.

IP 경계 단서 (Jun 2000 K-ToBI 기준):
- 휴지: 어절 경계 무성 구간 > 임계값(초기값 150-200ms, 파일럿에서 조정)
- 어말 장음화: IP 말 음절 지속시간의 화자별 z-score > 임계값
- 경계 성조: 마지막 음절 구간 F0 목표점의 뚜렷한 상승/하강 (H%, L%)
- F0 리셋: 다음 구 시작 F0가 직전 구 말보다 유의하게 복귀

AP 경계 단서:
- 어절 경계 + F0 상승 재시작 (AP 초 T-H 패턴), IP 단서 미달
- AP는 보통 어절 1-3개 → 어절 경계마다 후보, 위 단서로 병합/분리

우선순위: IP 단서 충족 → IP; 아니면 AP 후보 판정. 모든 IP 경계는
AP 경계를 겸함(K-ToBI 위계).

## 4-진행. 파일럿 실행 완료 (2026-07-15)
- 표본: gold 16,439발화(다층위 부분집합)에서 500발화 (세션 75개 층화)
- Colab에서 KOINA Momel 로드 성공 + parselmouth 기반 IP/AP 규칙 v0 적용
- 산출: prosody_utts.csv (IP/AP 경계·경계성조 H%/L%/F%·F0 통계·휴지·
  말속도·Momel 목표점) + prosody tier 추가 TextGrid 500개
- 파이프라인은 현상별 온디맨드 재사용 가능 (스크립트 상단 폴더명만 변경)
- **다음: 사용자 청취 검증** — results/tg의 TextGrid 표본을 Praat에서
  소리와 함께 열어 IP/AP 경계·성조의 타당성 확인 → 임계값(v0: 휴지
  0.15s/0.05s, F0 리셋 2st, 성조 1.5st) 보정 → 규칙 v1 확정

## 4. 단계별 계획

- [ ] (a) 파일럿 표본: 04_00 `03_wav`에서 발화 100개 추출 (남/녀,
      독백/대화 균형) + TSV 생성 (filename, sex, text)
- [ ] (b) Colab 노트북 작성: KOINA 설치 → 표본 실행 → TextGrid 회수
- [ ] (c) IP/AP 판정 스크립트(`prosody_boundary.py`) 작성 — KOINA
      TextGrid 입력, prosody tier 추가 출력
- [ ] (d) 수동 검증: 20-30발화를 직접 청취·판정하여 자동 결과와 비교
      (일치율 보고 → 논문 방법론에 포함), 임계값 조정
- [ ] (e) 적용 범위 결정: 검색 결과 발화에 on-demand 적용 파이프라인
- [ ] (f) METHODS 문서에 절차·수치 기록, 인용 정보 추가

## 5. 활용 구상

검색→음성 연계(04_00 PLAN 문서 2절)와 결합하면:
형태소/의미/IPA 검색 → 해당 발화 wav+TextGrid → KOINA 억양전사 →
IP/AP 경계 tier까지 갖춘 발화별 분석 패키지. 형태음운 변이와
운율 경계(IP/AP) 상호작용 분석 가능 (예: 구 경계 ㄴ삽입과 AP/IP 경계).

관련: 원유권(2025); Jun, S.-A.(2000) K-ToBI labelling conventions;
METHODS_bareun_dialogue_reanalysis.md
