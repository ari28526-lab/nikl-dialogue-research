# 바른 v3.1 형태소 TextGrid 파일럿 결과

작성일: 2026-08-29 KST

상태: **기계 감사 통과, 사용자 대표 3건 확인 대기**

## 결론

2020~2025년에서 연도별 2건씩, 총 12건의 파생 6-tier TextGrid를 만들었다.
기존 형태소 표지와 달라진 6건과 동일한 6건을 균형 있게 포함했다. 독립 감사 결과
12건 모두 통과했다.

- 원본 TextGrid SHA-256 불변
- 앞의 다섯 tier 시간·label 의미 불변
- `morph_analysis_utt` 시간 경계 불변
- 새 `morph_analysis_utt` label이 바른 v3.1 형태소 final과 정확히 일치
- WAV 접근 없음
- MFA 재실행 없음
- 빈 기존·신규 형태소 label 없음

이 결과는 발화 전체를 표시하는 형태소 tier의 갱신이다. 형태소마다 새 음향 시간
경계를 추정하거나 의미번호를 붙인 결과가 아니다.

## 사용자 확인 범위

사용자는 파일럿 12건 전체를 다시 감사할 필요가 없다. 산출물 안의
`USER_TODO.md`에 제시된 대표 3건만 보고 각 번호에 `OK` 또는 `보류: 이유`로
답하면 된다. 세 건은 다음을 대표한다.

1. 어미 품사 판정이 달라진 짧은 발화
2. 이전·신규 분석이 같은 짧은 발화
3. 격조사 품사 판정이 달라진 긴 발화

## 용량 판단

파일럿 크기로 추정한 전수 파생 TextGrid 용량은 약 42.928 GiB다. 측정 당시 D:
여유 공간은 56.199 GiB였고, 전수 완료 뒤 추정 여유 공간은 13.271 GiB다.
계획의 안전 기준 15 GiB보다 작으므로 현재 상태에서는 전수 생성을 시작하지 않는다.

전수 단계 전에는 최소 약 1.729 GiB를 더 확보해야 수치상 기준을 넘지만, 추정 오차와
운영 여유를 고려해 5 GiB 이상을 추가 확보하는 편이 안전하다. 공간 확보 뒤에도
전수 명령 전 `PreflightOnly`에서 실제 여유 공간과 예상 크기를 다시 계산해야 한다.

## 재현 자산

- 설정: `config/bareun_morph_textgrid_pilot_v1.json`
- 생성기: `scripts/python/build_bareun_morph_textgrid_pilot.py`
- 독립 감사기: `scripts/python/audit_bareun_morph_textgrid_pilot.py`
- 회귀 테스트: `tests/test_bareun_morph_textgrid_pilot.py`
- 감사 결과: `outputs/reports/AUDIT_bareun_morph_textgrid_v3_1_pilot_20260829.json`

원문 문장과 개인 절대경로가 들어 있는 파일럿 산출물 및 사용자 TODO는 로컬 검토
자산으로만 유지하고 공개 Git 문서에는 복제하지 않는다.
