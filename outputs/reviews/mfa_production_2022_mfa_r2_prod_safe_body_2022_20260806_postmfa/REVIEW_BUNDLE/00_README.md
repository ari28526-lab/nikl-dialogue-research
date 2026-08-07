# 2022 MFA 최종 인프라 표본 검토

이 폴더는 실제 음운 실현 여부를 판정하는 단계가 아니라, 전수 산출물의 연결과 사용 가능성을 확인하는 최종 Gate입니다.

각 번호에서 다음만 확인합니다.

1. WAV가 재생되고 LAB과 같은 발화인지
2. 같은 번호의 TextGrid가 열리고 6개 tier가 보이는지
3. words/phones_mfa/phoneme_r_auto/utterance/utterance_orth_r/morph_analysis가 대체로 맞고 연구 검색에 사용할 수 있는지
4. 좌우 빈 구간과 tier 경계가 파일 시간 범위 안에서 정상인지

문제가 없으면 03_RESEARCHER_REVIEW.csv의 decision을 approved로, 문제가 있으면 needs_attention으로 적고 notes에 이유를 남깁니다. 파일 이름과 식별자·경로 열은 바꾸지 않습니다.
