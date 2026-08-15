# NIKL 대화 연구 DB v1.0.0-rc0 — A–C 준비 패키지

이 폴더는 외부 공개본이 아니라 2020–2025 연구 DB 1차 배포를 준비하기 위한
내부 release candidate다. 기존 `common_pron_mfa_r3_20260809` MFA DB와 최종
6-tier TextGrid는 변경하지 않았다.

현재 완료 범위는 다음과 같다.

1. 6개 연도가 같은 발음 release·사전·음향모델·G2P provenance·MFA runtime·
   TextGrid schema를 사용했는지 교차 감사했다.
2. 현재 D: 생산 자산과 E:/H: archive 후보의 역할을 읽기 전용 계획으로 고정했다.
3. 원천 5,103,356발화를 exact-ID로 하나의 상태에만 배정한 연도별 압축 장부를
   만들고 누락·중복·미분류 0을 확인했다.

핵심 회계는 다음과 같다.

```text
5,103,356
= 4,286,046 aligned_safe_body
+    95,860 pre_mfa_technical_exclusion
+     3,086 post_mfa_technical_exclusion
+   718,364 pronunciation_followup
+         0 methodological_exclusion
```

`methodological_exclusion=0`은 모든 음원이 주 분석에 적합하다는 뜻이 아니다.
실제 연구 질문에 따른 소음·겹침·실현 판정·분석 제외는 표적 추출 뒤 연구자가
별도 overlay/decision ledger로 판단한다. 현재 장부는 인프라 구축 단계의 기술적
상태와 발음 후속 대상을 보존한다.

주요 파일:

- `BASE_RELEASE_MANIFEST_2020_2025.json`: 6개년 base release 정본
- `CROSS_YEAR_CONTRACT_AUDIT.json`: 같은 방법론 적용 근거
- `INPUT_CONTRACT.json`: 입력 증거와 SHA
- `QA_REPORT.json`: 누락·중복·미분류 0 검증
- `STORAGE_READ_ONLY_PLAN.json`: 삭제·이동 없는 저장공간 계획
- `OUTPUT_MANIFEST.json`: 이 패키지 파일 목록과 SHA
- `ledgers/<YEAR>_utterance_status.csv.gz`: 발화별 exact-ID 상태 장부
- `METHODS_A_C.md`: 연구방법·필드·한계·다음 Gate 설명

다음 단계 D는 이유별 recovery shard 구축이다. 이 폴더의 완료는 D의 대량
recovery/MFA, 파일 이동·삭제, 외부 배포를 승인하지 않는다.
