# 2020–2025 연구 DB v1 준비 A–C 완료

날짜: 2026-08-15 KST

## 결론

2020–2025 r3 완성본을 변경하지 않고 1차 연구 DB 배포 준비의 A–C를 완료했다.
여섯 연도는 같은 발음 release·dictionary·acoustic model·G2P provenance·runtime·
6-tier schema를 사용한 것으로 교차 감사됐다. 원천 5,103,356발화는 exact-ID로
누락·중복·미분류 없이 다음과 같이 분할됐다.

```text
4,286,046 aligned safe body
   95,860 pre-MFA technical exclusions
    3,086 post-MFA technical exclusions
  718,364 pronunciation follow-up
        0 methodological exclusions at infrastructure stage
```

독립 감사 결과는 `passed`다. 현재 결과는 내부 `v1.0.0-rc0`이며 외부 공개·대량
recovery·추가 MFA·파일 이동·삭제는 아직 수행하거나 승인하지 않았다.

## 핵심 산출물

- 패키지: `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815`
- 독립 감사: `outputs/reports/AUDIT_db_v1_release_prep_ac_20260815.json`
- 생성기: `scripts/python/build_db_v1_release_prep.py`
- 독립 감사기: `scripts/python/audit_db_v1_release_prep.py`

## 시행착오와 재발 방지

첫 실제 실행은 2024에서 안전 중단됐다. 2024에는 최초 전수 export 실패 보고서와
두 발화 표적 회수 뒤 최종 성공 보고서가 함께 보존돼 있었는데, 처음 구현이 좁은
파일명 패턴으로 최초 보고서를 골랐기 때문이다. 실패 증거를 지우거나 최신 파일을
추정하지 않고, 최종 독립 QC state의 `export_report_sha256`과 일치하는 보고서만
선택하도록 수정했다. 이 규칙의 회귀 테스트를 추가했다.

연도별 장부는 입력 signature와 출력 SHA를 가진 체크포인트로 확정한다. 따라서
2024 문제를 고친 뒤 2020–2023은 다시 계산하지 않고 검증된 체크포인트를 재사용했다.

## 방법론 해석

`phones_mfa`와 G2P는 강제정렬용 입력·분절 보조값이지 실제 음운 실현의 자동 판정이
아니다. `aligned_safe_body`도 연구 질문에 자동 포함된다는 뜻이 아니다. 표적 추출
뒤 연구자가 WAV·TextGrid·운율 정보와 함께 실현·소음·겹침·분석 제외를 판정하고,
그 결정은 별도 수동 overlay/decision ledger로 전체 DB에 반영한다.

## 저장공간 결정과 정지점

D:는 r3 정본을 유지한다. E:는 향후 별도 승인된 검증형 read-only archive의 우선
대상, H:는 선택적 이중 백업 후보다. A–C에서는 파일을 이동·삭제·archive하지
않았다. 다음 D 이유별 recovery shard 직전에서 정지하며, 이는 2020–2025 본체
MFA나 전수 TextGrid를 다시 실행하는 승인이 아니다.
